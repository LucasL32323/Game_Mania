#!/usr/bin/env python3
"""
Regras fixas do front-end, verificadas sem navegador nem servidor (roda em ~1 s).

Protege o que o projeto exige e que uma mudança descuidada quebraria sem ninguém notar:
  • paleta da marca congelada (nenhum hexadecimal novo, nenhum token alterado)
  • Bootstrap (versão BS_VERSAO) com SRI e o gamemania.css carregado DEPOIS dele
  • CSP: nada de style="", <style>, on*="", <script> inline (exceto JSON-LD)
  • imagens: caminho relativo img/, classe = nome do arquivo, lazy (exceto 1 LCP),
    width/height/alt, plano B data-gm-legado igual ao mapa de migração
  • slots de mascote no topo, 1 <h1>, rodapé idêntico em todas as páginas
  • JS sem innerHTML/eval/document.write (anti-XSS)

Uso:  python tests/test_estatico.py          (sai com código 1 se algo falhar)
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FRONT = RAIZ / "frontend"
sys.path.insert(0, str(RAIZ / "tools"))
from migrar_imagens import MAPA  # noqa: E402

# Paleta oficial — alterar aqui exige decisão explícita do dono do projeto.
PALETA = {
    "--gm-grafite": "#2e2e2e", "--gm-grafite-escuro": "#1a1a1a", "--gm-superficie": "#303234",
    "--gm-superficie-alta": "#3a3a3a", "--gm-topo": "#212529", "--gm-verde-floresta": "#014421",
    "--gm-azul-marinho": "#001f4d", "--gm-azul-profundo": "#022b69", "--gm-rosa-neon": "#ff004f",
    "--gm-verde-neon": "#00ff99", "--gm-verde-acao": "#00e68a", "--gm-verde-contato": "#00cc7a",
    "--gm-ciano": "#00ffff", "--gm-ciano-suave": "#00cccc", "--gm-texto": "#f0f0f0",
    "--gm-texto-suave": "#cccccc", "--gm-prata": "#d9d9d9", "--gm-brilho-1": "#a6a6a6",
    "--gm-brilho-2": "#bfbfbf",
}
HEX_PERMITIDOS = set(PALETA.values()) | {"#fff", "#ffffff"}
# Bootstrap: ÚNICO lugar com versão e hashes. Para atualizar: troque os 3 valores aqui,
# rode tools/atualizar_bootstrap.py <versão> (regrava as páginas e confere os hashes no npm).
BS_VERSAO = "5.3.8"
SRI_CSS = "sha384-sRIl4kxILFvY47J16cr9ZwB07vP4J8+LH7qKQnuqkuIAvNWLzeN8tE5YBujZqJLB"
SRI_JS = "sha384-FKyoEForCGlyvwx9Hj09JcYn3nv7wiPVlz7YYwJrWVcXK/BmnVDxM+D2scQbITxI"
LEGADO = {novo: antigo for antigo, novos in MAPA.items() for novo in novos}

resultados: list[tuple[bool, str]] = []


def ok(cond: bool, msg: str) -> None:
    resultados.append((bool(cond), msg))
    print(("PASS " if cond else "FAIL ") + msg)


class Pagina(HTMLParser):
    """Coleta tags relevantes; ignora o conteúdo de <template> (preenchido via JS)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str]]] = []
        self.imgs: list[dict[str, str]] = []
        self.scripts: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []
        self.em_template = 0
        self.h1 = 0

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "template":
            self.em_template += 1
        self.tags.append((tag, a))
        if tag == "h1":
            self.h1 += 1
        if tag == "img" and not self.em_template:
            self.imgs.append(a)
        if tag == "script":
            self.scripts.append(a)
        if tag == "link":
            self.links.append(a)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "template":
            self.em_template -= 1


def bloco(html: str, abre: str, fecha: str) -> str:
    i = html.find(abre)
    return html[i: html.find(fecha, i) + len(fecha)] if i >= 0 else ""


def checar_css() -> None:
    css = (FRONT / "css" / "gamemania.css").read_text(encoding="utf-8")
    raiz = bloco(css, ":root {", "}")
    tokens = dict(re.findall(r"(--gm-[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8})", raiz))
    ok(all(tokens.get(k, "").lower() == v for k, v in PALETA.items()), "css: tokens da paleta intactos")
    novos = sorted(set(tokens) - set(PALETA))
    ok(not novos, f"css: nenhum token de cor novo em :root {novos or ''}")
    soltos = sorted({h.lower() for h in re.findall(r"#[0-9a-fA-F]{3,8}\b", css.replace(raiz, ""))} - HEX_PERMITIDOS)
    ok(not soltos, f"css: nenhuma cor fora da paleta (use var(--gm-*)) {soltos or ''}")


def checar_js() -> None:
    proibidos = re.compile(r"\.innerHTML\s*=|\.outerHTML\s*=|insertAdjacentHTML|document\.write\(|\beval\(|new Function\(")
    for js in sorted((FRONT / "js").glob("*.js")):
        achados = [f"{n}: {l.strip()[:60]}" for n, l in enumerate(js.read_text(encoding="utf-8").splitlines(), 1)
                   if proibidos.search(l) and not l.lstrip().startswith(("*", "//", "/*"))]
        ok(not achados, f"js/{js.name}: sem innerHTML/eval/document.write {achados[:2] or ''}")


def checar_pagina(arq: Path) -> str:
    html = arq.read_text(encoding="utf-8")
    p = Pagina()
    p.feed(html)
    nome = arq.name

    ok('<html lang="pt-BR" data-bs-theme="dark">' in html, f"{nome}: <html lang=pt-BR data-bs-theme=dark>")
    ok(any(t == "meta" and a.get("name") == "viewport" for t, a in p.tags), f"{nome}: meta viewport")
    ok(any(t == "meta" and a.get("name") == "description" and len(a.get("content", "")) >= 50 for t, a in p.tags),
       f"{nome}: meta description (≥ 50 caracteres)")
    ok(p.h1 == 1, f"{nome}: exatamente 1 <h1> ({p.h1})")

    # CSS: Bootstrap com SRI e gamemania.css uma vez, depois dele
    folhas = [l for l in p.links if l.get("rel") == "stylesheet"]
    hrefs = [l.get("href", "") for l in folhas]
    i_bs = next((i for i, h in enumerate(hrefs) if f"bootstrap@{BS_VERSAO}/dist/css/bootstrap.min.css" in h), -1)
    ok(i_bs >= 0 and folhas[i_bs].get("integrity") == SRI_CSS, f"{nome}: Bootstrap {BS_VERSAO} CSS com SRI")
    gm = [i for i, h in enumerate(hrefs) if h == "css/gamemania.css"]
    ok(len(gm) == 1 and gm[0] > i_bs, f"{nome}: css/gamemania.css 1 vez, depois do Bootstrap ({len(gm)} vez(es))")

    # Scripts: só externos com defer + JSON-LD
    srcs = [s.get("src", "") for s in p.scripts]
    bs = [s for s in p.scripts if f"bootstrap@{BS_VERSAO}/dist/js/bootstrap.bundle.min.js" in s.get("src", "")]
    ok(len(bs) == 1 and bs[0].get("integrity") == SRI_JS and "defer" in bs[0], f"{nome}: Bootstrap {BS_VERSAO} JS com SRI e defer")
    for js in ("js/gm-tracker.js", "js/gm-ui.js"):
        ok(any(s.get("src") == js and "defer" in s for s in p.scripts), f"{nome}: {js} com defer")
    ok(srcs.index("js/gm-tracker.js") < srcs.index("js/gm-ui.js") if all(j in srcs for j in ("js/gm-tracker.js", "js/gm-ui.js")) else False,
       f"{nome}: gm-tracker.js antes do gm-ui.js")
    inline = [s for s in p.scripts if not s.get("src") and s.get("type") != "application/ld+json"]
    ok(not inline, f"{nome}: nenhum <script> inline (CSP)")

    # CSP: sem estilos e handlers inline
    ok(not any("style" in a for _, a in p.tags), f"{nome}: nenhum atributo style=")
    ok("<style" not in html, f"{nome}: nenhuma tag <style>")
    handlers = sorted({k for _, a in p.tags for k in a if k.startswith("on")})
    ok(not handlers, f"{nome}: nenhum handler inline {handlers or ''}")

    # Caminhos relativos (funciona com duplo clique, Live Server e servidor)
    absolutos = sorted(set(re.findall(r'(?:src|href|data-img)="(/[^/][^"]*)"', html)))
    ok(not absolutos, f"{nome}: caminhos relativos (sem src/href começando com /) {absolutos[:3] or ''}")

    # Imagens
    ruins, sem_dim, sem_alt, sem_legado, eager = [], [], [], [], []
    for im in p.imgs:
        src = im.get("src", "")
        if not src.startswith("img/"):
            ruins.append(src)
            continue
        arquivo = src[4:]
        if arquivo.rsplit(".", 1)[0] not in im.get("class", "").split():
            ruins.append(src)
        if not (im.get("width") and im.get("height")):
            sem_dim.append(src)
        if "alt" not in im:
            sem_alt.append(src)
        esperado = f"imgs/{LEGADO[arquivo]}" if arquivo in LEGADO else None
        if im.get("data-gm-legado") != esperado:
            sem_legado.append(arquivo)
        if im.get("loading") != "lazy":
            eager.append(im)
    ok(not ruins, f"{nome}: <img> em img/ com classe = nome do arquivo {ruins[:3] or ''}")
    ok(not sem_dim, f"{nome}: <img> com width/height (sem layout shift) {sem_dim[:3] or ''}")
    ok(not sem_alt, f"{nome}: <img> com alt {sem_alt[:3] or ''}")
    ok(not sem_legado, f"{nome}: data-gm-legado igual ao mapa de migração {sem_legado[:3] or ''}")
    ok(len(eager) <= 1 and all(e.get("fetchpriority") == "high" for e in eager),
       f"{nome}: loading=lazy em todas, exceto no máximo 1 LCP com fetchpriority=high ({len(eager)} eager)")
    sem_mapa = sorted({im["src"][4:] for im in p.imgs if im.get("src", "").startswith("img/") and im["src"][4:] not in LEGADO})
    ok(not sem_mapa, f"{nome}: toda imagem está no MAPA do tools/migrar_imagens.py {sem_mapa[:3] or ''}")

    # Estrutura da marca
    ids = {a.get("id") for _, a in p.tags}
    ok({"slot-mascote-principal", "slot-mascote-secundario"} <= ids, f"{nome}: slots de mascote no topo")
    ok("conteudo" in ids and 'class="gm-pular" href="#conteudo"' in html, f"{nome}: link 'Pular para o conteúdo' + main#conteudo")
    ok(any(t == "header" and "gm-topo" in a.get("class", "") for t, a in p.tags), f"{nome}: header.gm-topo")
    rodape = bloco(html, '<footer id="contato" class="gm-rodape">', "</footer>")
    ok(bool(rodape), f"{nome}: footer.gm-rodape")
    return rodape


def checar_imagens_reais() -> None:
    """Nomes exatos (servidor Linux diferencia maiúsculas): mapa ↔ legado/imgs ↔ frontend/img."""
    legado = RAIZ / "legado" / "imgs"
    if legado.is_dir():
        reais = {p.name for p in legado.iterdir()}
        errados = [a for a in MAPA if a not in reais]
        ok(not errados, f"mapa: nomes idênticos aos de legado/imgs (maiúsculas contam) {errados[:3] or ''}")
    img = FRONT / "img"
    if img.is_dir():
        faltam = sorted({n for ns in MAPA.values() for n in ns} - {p.name for p in img.iterdir()})
        ok(not faltam, f"frontend/img completo (rode tools/migrar_imagens.py) {faltam[:3] or ''}")


def main() -> int:
    paginas = sorted(FRONT.glob("*.html"))
    ok(len(paginas) >= 3, f"{len(paginas)} página(s) em frontend/")
    checar_css()
    checar_js()
    checar_imagens_reais()
    rodapes = {arq.name: checar_pagina(arq) for arq in paginas}
    base = rodapes.get("index.html", "")
    diferentes = [n for n, r in rodapes.items() if r != base]
    ok(not diferentes, f"rodapé idêntico ao do index.html em todas as páginas {diferentes or ''}")

    falhas = sum(1 for r in resultados if not r[0])
    print(f"\n{len(resultados) - falhas}/{len(resultados)} verificações estáticas OK")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
