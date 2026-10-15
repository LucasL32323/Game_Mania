"""
Configuração central da API GameMania 2.0.

Todos os segredos vêm de variáveis de ambiente (prefixo GM_) ou do arquivo .env.
Nada sensível fica no código-fonte — diferente do server.js legado, que tinha
usuário/senha do MySQL hardcoded.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GM_", env_file=".env", extra="ignore")

    # --- Ambiente ---------------------------------------------------------
    environment: str = "production"          # production | development
    serve_frontend: bool = False             # True só em dev (em produção o Nginx serve /img, /css, /js)
    frontend_dir: str = "../frontend"

    # --- Banco de dados ---------------------------------------------------
    # Pool transacional (e-commerce) e pool de telemetria SEPARADOS:
    # um pico de analytics nunca consome as conexões do checkout.
    database_url: str
    analytics_database_url: str | None = None

    # --- Criptografia de dados pessoais (LGPD) ----------------------------
    # {key_id: base64(32 bytes)} — várias chaves permitem rotação sem downtime.
    email_aes_keys: dict[int, str]
    email_aes_active_key_id: int = 1
    email_hmac_key: str                      # blind index p/ busca por e-mail
    ip_hmac_key: str                         # pseudonimização de IP no tracking

    # --- Sessão / JWT -----------------------------------------------------
    jwt_secret: str
    jwt_ttl_minutes: int = 60 * 8
    cookie_secure: bool = True               # exige HTTPS; habilita prefixo __Host-

    # --- Web ----------------------------------------------------------------
    allowed_origins: list[str] = ["http://localhost:8000"]
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]

    # --- Fila de tracking (ingestão assíncrona) ---------------------------
    tracking_queue_max: int = 50_000         # backpressure: acima disso descarta
    tracking_batch_size: int = 500           # linhas por INSERT em lote
    tracking_flush_seconds: float = 2.0      # latência máxima até o banco

    @property
    def is_dev(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
