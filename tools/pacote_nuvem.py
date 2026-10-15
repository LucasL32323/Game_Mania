#!/usr/bin/env python3
"""
Guarda o código do GameMania 2.0 num ÚNICO documento de texto (o "pacote"), para
salvar na nuvem do Claude (Projeto GameMania_2.0 → claude/gamemania-2.0/pacote.md)
enquanto o projeto não tem repositório no GitHub.

    python tools/pacote_nuvem.py empacotar <raiz-do-projeto> <pacote.md>
    python tools/pacote_nuvem.py desempacotar <pacote.md> <pasta-destino>
    python tools/pacote_nuvem.py imagens <raiz-do-projeto>

• O pacote leva só texto (HTML, CSS, JS, Python, SQL, docs). Ficam de fora:
  legado/ e as imagens — elas são baixadas de novo pelo comando "imagens", a partir do
  repositório público LucasL32323/12172025GameMania (o site original).
• Cada arquivo leva o SHA-256 dos bytes originais: o desempacotamento confere tudo e
  falha se algum arquivo vier diferente (ex.: documento truncado).
• Quebras de linha CRLF (o .bat do Windows) e "sem quebra no fim" são restauradas.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ABRE = "⟦GM-ARQUIVO⟧"
FECHA = "⟦GM-FIM⟧"
CABECALHO = re.compile(r"^⟦GM-ARQUIVO⟧ (?P<caminho>\S+) \| sha256=(?P<sha>[0-9a-f]{64}) \| crlf=(?P<crlf>[01]) \| nl=(?P<nl>[01])$")

FORA = ("legado/", "frontend/img/", "docs/prints/", ".git/", "node_modules/", ".nuvem/", ".legado-tmp/")
BINARIOS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".zip", ".bundle", ".pyc", ".woff", ".woff2"}
REPO_LEGADO = "https://github.com/LucasL32323/12172025GameMania.git"


def arquivos(raiz: Path) -> list[Path]:
    lista = []
    for p in sorted(raiz.rglob("*")):
        rel = p.relative_to(raiz).as_posix()
        if not p.is_file() or rel.startswith(FORA) or "/__pycache__/" in f"/{rel}" or p.suffix.lower() in BINARIOS:
            continue
        if rel in ("backend/.env",) or rel.endswith(".log"):
            continue                                            # nunca empacotar segredos ou logs
        lista.append(p)
    return lista


def empacotar(raiz: Path, saida: Path) -> None:
    lista = arquivos(raiz)
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    partes = [
        "# GameMania 2.0 — pacote do código\n",
        f"Gerado em {agora} · {len(lista)} arquivos · não edite à mão (cada arquivo tem SHA-256).\n",
        "Para recriar o projeto: `python tools/pacote_nuvem.py desempacotar pacote.md destino/` e depois "
        "`python tools/pacote_nuvem.py imagens destino/` (baixa legado/ e as imagens reais).\n",
        "Arquivos: " + ", ".join(p.relative_to(raiz).as_posix() for p in lista) + "\n\n",
    ]
    for p in lista:
        dados = p.read_bytes()
        texto = dados.decode("utf-8")                           # falha alto se aparecer binário novo
        crlf = "\r\n" in texto
        texto = texto.replace("\r\n", "\n")
        nl = texto.endswith("\n")
        if not nl:
            texto += "\n"
        if any(l.startswith((ABRE, FECHA)) for l in texto.splitlines()):
            raise SystemExit(f"{p}: contém linha iniciando com o marcador do pacote")
        rel = p.relative_to(raiz).as_posix()
        partes.append(f"{ABRE} {rel} | sha256={hashlib.sha256(dados).hexdigest()} | crlf={int(crlf)} | nl={int(nl)}\n")
        partes.append(texto)
        partes.append(f"{FECHA} {rel}\n\n")
    saida.write_text("".join(partes), encoding="utf-8", newline="\n")
    print(f"{len(lista)} arquivos → {saida} ({saida.stat().st_size // 1024} KB)")


def desempacotar(pacote: Path, destino: Path) -> None:
    linhas = pacote.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    i, total, erros = 0, 0, []
    while i < len(linhas):
        m = CABECALHO.match(linhas[i])
        if not m:
            i += 1
            continue
        rel, fim = m["caminho"], f"{FECHA} {m['caminho']}"
        try:
            j = linhas.index(fim, i + 1)
        except ValueError:
            raise SystemExit(f"pacote truncado: fim de {rel} não encontrado")
        if ".." in Path(rel).parts or rel.startswith("/"):
            raise SystemExit(f"caminho inválido no pacote: {rel}")
        texto = "\n".join(linhas[i + 1:j]) + "\n"
        if m["nl"] == "0":
            texto = texto[:-1]
        if m["crlf"] == "1":
            texto = texto.replace("\n", "\r\n")
        dados = texto.encode("utf-8")
        if hashlib.sha256(dados).hexdigest() != m["sha"]:
            erros.append(rel)
        alvo = destino / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_bytes(dados)
        if rel.endswith(".sh"):
            alvo.chmod(0o755)
        total += 1
        i = j + 1
    if erros:
        raise SystemExit(f"SHA-256 diferente em {len(erros)} arquivo(s): {erros[:5]}")
    if total == 0:
        raise SystemExit("nenhum arquivo encontrado no pacote")
    print(f"{total} arquivos recriados em {destino} (SHA-256 conferido)")


def imagens(raiz: Path) -> None:
    """Baixa o site original para legado/ e migra as imagens reais para frontend/img/."""
    legado = raiz / "legado"
    if not (legado / "imgs").is_dir():
        tmp = raiz / ".legado-tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        subprocess.run(["git", "clone", "-q", "--depth", "1", REPO_LEGADO, str(tmp)], check=True)
        shutil.rmtree(tmp / ".git", ignore_errors=True)
        (tmp / "Git.zip").unlink(missing_ok=True)
        shutil.rmtree(legado, ignore_errors=True)
        tmp.rename(legado)
    subprocess.run([sys.executable, str(raiz / "tools" / "migrar_imagens.py"), str(legado / "imgs"), str(raiz / "frontend" / "img")], check=True)


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("empacotar", "desempacotar", "imagens"):
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "empacotar":
        empacotar(Path(sys.argv[2]).resolve(), Path(sys.argv[3]))
    elif cmd == "desempacotar":
        desempacotar(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        imagens(Path(sys.argv[2]).resolve())
