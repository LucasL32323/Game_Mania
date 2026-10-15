"""
Camada criptográfica da GameMania 2.0.

┌────────────┬──────────────────────────────┬──────────────────────────────────────┐
│ Dado       │ Técnica                      │ Por quê                              │
├────────────┼──────────────────────────────┼──────────────────────────────────────┤
│ Senha      │ Argon2id (hash + salt 16 B)  │ Irreversível, resistente a GPU/ASIC  │
│ Senha leg. │ bcrypt → rehash p/ Argon2id  │ Migra hashes do server.js no login   │
│ E-mail     │ AES-256-GCM (nonce 96 bits)  │ Reversível só com a chave (LGPD)     │
│ E-mail     │ HMAC-SHA256 (blind index)    │ Busca/UNIQUE sem decifrar o banco    │
│ IP         │ Truncagem + HMAC-SHA256      │ Pseudonimização da telemetria        │
└────────────┴──────────────────────────────┴──────────────────────────────────────┘

Como o AES-256 "substitui e transforma" cada bloco de 16 bytes (14 rodadas):
  1. SubBytes    → substituição não linear byte a byte pela S-box (inverso em GF(2^8)
                   seguido de transformação afim) — é aqui que letras e números do
                   e-mail deixam de ter qualquer relação visível com o original.
  2. ShiftRows   → permutação cíclica das linhas da matriz de estado 4x4.
  3. MixColumns  → multiplicação de cada coluna por matriz fixa em GF(2^8).
  4. AddRoundKey → XOR com a subchave da rodada, derivada da chave exata de 256 bits.

Usamos o modo GCM (e NÃO o ECB): cada cifragem usa um nonce aleatório, então o mesmo
e-mail gera textos cifrados diferentes, e a tag de 128 bits detecta adulteração.
Consequência: não dá para fazer WHERE email = ?. Para login/unicidade usamos o
blind index (HMAC determinístico com chave separada).

Formato armazenado (BYTEA): [versão 1B][key_id 1B][nonce 12B][ciphertext + tag 16B]
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import os
import unicodedata
from functools import lru_cache

import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings

# =============================================================================
# 1) SENHAS — Argon2id (RFC 9106, 2ª configuração recomendada: t=3, m=64 MiB, p=4)
# =============================================================================
_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,  # KiB → 64 MiB por verificação (inviabiliza força bruta em GPU)
    parallelism=4,
    hash_len=32,
    salt_len=16,            # salt aleatório por usuário, embutido no próprio hash
)
MAX_PASSWORD_BYTES = 1024   # evita DoS com senhas gigantes
_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def hash_password(plain: str) -> str:
    """Gera hash Argon2id. Ex.: $argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>"""
    _guard_password_size(plain)
    return _password_hasher.hash(plain)


def verify_password(plain: str, stored_hash: str) -> tuple[bool, str | None]:
    """
    Verifica a senha em tempo constante.

    Retorna (senha_ok, novo_hash). `novo_hash` vem preenchido quando o hash salvo
    precisa ser atualizado — hash bcrypt do sistema legado ou parâmetros Argon2
    antigos — e deve ser persistido pelo chamador logo após o login.
    """
    if len(plain.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return False, None

    # --- Legado: hashes gerados pelo server.js (Node bcrypt, saltRounds=10) ---
    if stored_hash.startswith(_BCRYPT_PREFIXES):
        # O bcrypt do Node trunca em 72 bytes silenciosamente; replicamos para
        # que senhas antigas continuem válidas.
        candidate = plain.encode("utf-8")[:72]
        try:
            ok = bcrypt.checkpw(candidate, stored_hash.encode("utf-8"))
        except ValueError:
            return False, None
        return (True, hash_password(plain)) if ok else (False, None)

    # --- Padrão atual: Argon2id ---
    try:
        _password_hasher.verify(stored_hash, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False, None

    if _password_hasher.check_needs_rehash(stored_hash):
        return True, hash_password(plain)
    return True, None


@lru_cache
def _dummy_hash() -> str:
    return _password_hasher.hash("gamemania-timing-equalizer")


def burn_password_check(plain: str) -> None:
    """
    Executa uma verificação falsa quando o e-mail não existe, para que o tempo de
    resposta seja igual ao de uma senha errada (impede enumeração de contas).
    """
    try:
        _password_hasher.verify(_dummy_hash(), plain[:MAX_PASSWORD_BYTES])
    except VerificationError:
        pass


def _guard_password_size(plain: str) -> None:
    if len(plain.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("Senha excede o tamanho máximo permitido.")


# =============================================================================
# 2) E-MAIL — AES-256-GCM + blind index HMAC-SHA256
# =============================================================================
_FORMAT_VERSION = 1
_NONCE_LEN = 12                      # 96 bits: tamanho recomendado para GCM
_AAD = b"gamemania:users.email:v1"   # "associated data": amarra o cifrado a esta coluna


def normalize_email(email: str) -> str:
    """Normalização única usada tanto na cifragem quanto no blind index."""
    return unicodedata.normalize("NFKC", email).strip().lower()


def _decode_key(b64_value: str, *, name: str) -> bytes:
    key = base64.b64decode(b64_value, validate=True)
    if len(key) != 32:
        raise ValueError(f"{name} precisa ter exatamente 32 bytes (256 bits).")
    return key


class EmailCipher:
    """Cifra/decifra e-mails e gera o índice cego para consultas."""

    def __init__(self, keys: dict[int, bytes], active_key_id: int, hmac_key: bytes) -> None:
        if active_key_id not in keys:
            raise ValueError("GM_EMAIL_AES_ACTIVE_KEY_ID não existe em GM_EMAIL_AES_KEYS.")
        if not all(0 < kid < 256 for kid in keys):
            raise ValueError("key_id deve estar entre 1 e 255.")
        self._aead = {kid: AESGCM(key) for kid, key in keys.items()}
        self._active = active_key_id
        self._hmac_key = hmac_key

    def encrypt(self, email: str) -> bytes:
        plaintext = normalize_email(email).encode("utf-8")
        nonce = os.urandom(_NONCE_LEN)  # NUNCA reutilizar nonce com a mesma chave
        ciphertext = self._aead[self._active].encrypt(nonce, plaintext, _AAD)
        return bytes((_FORMAT_VERSION, self._active)) + nonce + ciphertext

    def decrypt(self, blob: bytes) -> str:
        version, key_id = blob[0], blob[1]
        if version != _FORMAT_VERSION or key_id not in self._aead:
            raise ValueError("Formato ou chave de cifragem desconhecidos.")
        nonce, ciphertext = blob[2 : 2 + _NONCE_LEN], blob[2 + _NONCE_LEN :]
        try:
            return self._aead[key_id].decrypt(nonce, ciphertext, _AAD).decode("utf-8")
        except InvalidTag as exc:  # dado adulterado ou chave errada
            raise ValueError("Falha de integridade ao decifrar e-mail.") from exc

    def needs_reencrypt(self, blob: bytes) -> bool:
        """True se o registro foi cifrado com chave antiga (job de rotação)."""
        return blob[1] != self._active

    def blind_index(self, email: str) -> bytes:
        """HMAC-SHA256 determinístico: mesmo e-mail → mesmo índice, sem revelar o e-mail."""
        return hmac.new(self._hmac_key, normalize_email(email).encode("utf-8"), hashlib.sha256).digest()


@lru_cache
def get_email_cipher() -> EmailCipher:
    s = get_settings()
    keys = {int(k): _decode_key(v, name=f"GM_EMAIL_AES_KEYS[{k}]") for k, v in s.email_aes_keys.items()}
    return EmailCipher(keys, s.email_aes_active_key_id, _decode_key(s.email_hmac_key, name="GM_EMAIL_HMAC_KEY"))


# =============================================================================
# 3) IP — pseudonimização para telemetria
# =============================================================================
@lru_cache
def _ip_key() -> bytes:
    return _decode_key(get_settings().ip_hmac_key, name="GM_IP_HMAC_KEY")


def pseudonymize_ip(raw_ip: str | None) -> str | None:
    """
    Zera o final do IP (/24 no IPv4, /48 no IPv6) e aplica HMAC.
    Permite contar visitantes únicos sem armazenar o IP real.
    """
    if not raw_ip:
        return None
    try:
        ip = ipaddress.ip_address(raw_ip)
    except ValueError:
        return None
    prefix = 24 if ip.version == 4 else 48
    network = ipaddress.ip_network(f"{ip}/{prefix}", strict=False).network_address
    return hmac.new(_ip_key(), network.packed, hashlib.sha256).hexdigest()[:32]
