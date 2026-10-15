#!/usr/bin/env python3
"""
Atualiza o Bootstrap de TODAS as páginas de frontend/ com um comando, sem editar HTML à mão.

    python tools/atualizar_bootstrap.py 5.3.8          # versão exata (nunca "5" ou "latest")
    python tools/atualizar_bootstrap.py 5.3.8 --checar # só confere, não grava nada

O que faz:
  1. Baixa a versão pedida do registro npm (pasta temporária) e calcula o SHA-384 dos dois
     arquivos que o site usa: dist/css/bootstrap.min.css e dist/js/bootstrap.bundle.min.js.
     Os hashes saem dos BYTES publicados, então o SRI sempre bate com o que o jsDelivr serve.
  2. Troca versão + integrity nas <link>/<script> de cada frontend/*.html.
  3. Atualiza a fonte única de verdade em tests/test_estatico.py (BS_VERSAO, SRI_CSS, SRI_JS)
     e a regra 2 do CLAUDE.md. O scripts/testar_tudo.sh lê a versão do test_estatico.py.

Depois rode:  bash scripts/testar_tudo.sh   (o estático confere SRI em toda página).
Requer Node/npm. Funciona em Windows, Linux e macOS.
"""
from __future__ import annotations

import base64
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FRONT = RAIZ / "frontend"
TESTE = RAIZ / "tests" / "test_estatico.py"
CLAUDE_MD = RAIZ / "CLAUDE.md"
ARQ_CSS = "dist/css/bootstrap.min.css"
ARQ_JS = "dist/js/bootstrap.bundle.min.js"

# <link ... href=".../bootstrap@X/dist/css/bootstrap.min.css" ... integrity="sha384-...">
RE_CSS = re.compile(r'(bootstrap@)[0-9][0-9A-Za-z.\-]*(/dist/css/bootstrap\.min\.css"\s+integrity=")sha384-[A-Za-z0-9+/=]+(")')
RE_JS = re.compile(r'(bootstrap@)[0-9][0-9A-Za-z.\-]*(/dist/js/bootstrap\.bundle\.min\.js"\s+integrity=")sha384-[A-Za-z0-9+/=]+(")')


def sri(caminho: Path) -> str:
    return "sha384-" + base64.b64encode(hashlib.sha384(caminho.read_bytes()).digest()).decode()


def baixar(versao: str, pasta: Path) -> Path:
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        sys.exit("npm não encontrado. Instale o Node.js (https://nodejs.org) e tente de novo.")
    r = subprocess.run([npm, "install", "--silent", "--no-audit", "--no-fund", "--prefix", str(pasta), f"bootstrap@{versao}"],
                       capture_output=True, text=True)
    pacote = pasta / "node_modules" / "bootstrap"
    if r.returncode != 0 or not (pacote / ARQ_CSS).is_file():
        sys.exit(f"Não consegui baixar bootstrap@{versao} do npm.\n{r.stderr.strip()[:500]}")
    return pacote


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    checar = "--checar" in sys.argv
    if len(args) != 1 or not re.fullmatch(r"\d+\.\d+\.\d+", args[0]):
        print(__doc__)
        return 1
    versao = args[0]

    with tempfile.TemporaryDirectory() as tmp:
        pacote = baixar(versao, Path(tmp))
        h_css, h_js = sri(pacote / ARQ_CSS), sri(pacote / ARQ_JS)
    print(f"bootstrap@{versao}\n  CSS {h_css}\n  JS  {h_js}")

    paginas = sorted(FRONT.glob("*.html"))
    mudancas: dict[Path, str] = {}
    for p in paginas:
        html = p.read_text(encoding="utf-8")
        novo, n_css = RE_CSS.subn(rf"\g<1>{versao}\g<2>{h_css}\g<3>", html)
        novo, n_js = RE_JS.subn(rf"\g<1>{versao}\g<2>{h_js}\g<3>", novo)
        if n_css != 1 or n_js != 1:
            sys.exit(f"{p.name}: esperava 1 <link> e 1 <script> do Bootstrap (achei {n_css} e {n_js}). Nada foi gravado.")
        if novo != html:
            mudancas[p] = novo

    teste = TESTE.read_text(encoding="utf-8")
    teste_novo = re.sub(r'^BS_VERSAO = "[^"]*"$', f'BS_VERSAO = "{versao}"', teste, flags=re.M)
    teste_novo = re.sub(r'^SRI_CSS = "[^"]*"$', f'SRI_CSS = "{h_css}"', teste_novo, flags=re.M)
    teste_novo = re.sub(r'^SRI_JS = "[^"]*"$', f'SRI_JS = "{h_js}"', teste_novo, flags=re.M)
    if teste_novo != teste:
        mudancas[TESTE] = teste_novo
    regra = CLAUDE_MD.read_text(encoding="utf-8")
    regra_nova = re.sub(r"\*\*Bootstrap \d+\.\d+\.\d+\*\*", f"**Bootstrap {versao}**", regra)
    if regra_nova != regra:
        mudancas[CLAUDE_MD] = regra_nova

    if not mudancas:
        print("Tudo já está nessa versão, com os hashes corretos.")
        return 0
    for p in mudancas:
        print(("  mudaria " if checar else "  atualizado ") + p.relative_to(RAIZ).as_posix())
    if checar:
        return 1                                            # útil em CI: "há atualização pendente"
    for p, conteudo in mudancas.items():
        p.write_text(conteudo, encoding="utf-8")
    print("Pronto. Agora rode: bash scripts/testar_tudo.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
