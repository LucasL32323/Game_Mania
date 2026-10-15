#!/usr/bin/env python3
"""
Gera imagens PROVISÓRIAS para os testes (as imagens reais do site não ficam no repositório).

Uso:
    python tests/gerar_placeholders.py <pasta-destino> [--legado]

    sem --legado → nomes novos em <pasta-destino> (img/mascote-principal.png ...)
    com --legado → nomes ORIGINAIS do site atual (imgs/Logo4.png ...), para testar o plano B

A lista de arquivos vem do tools/migrar_imagens.py: cada imagem que uma página referencia
precisa estar no MAPA, senão o teste estático acusa.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
from migrar_imagens import MAPA  # noqa: E402

# Paleta da marca (mesmos hexadecimais de frontend/css/gamemania.css)
ROSA, CIANO, VERDE, MARINHO, GRAFITE = (255, 0, 79), (0, 204, 204), (0, 255, 153), (0, 31, 77), (26, 26, 26)
REDES = {"rede-facebook": (59, 89, 152), "rede-instagram": (225, 48, 108), "rede-youtube": (255, 0, 0), "rede-tiktok": (240, 240, 240)}


def fonte(tamanho: int):
    for caminho in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"):
        if Path(caminho).exists():
            return ImageFont.truetype(caminho, tamanho)
    return ImageFont.load_default()


def texto_centro(d: ImageDraw.ImageDraw, largura: int, y: int, texto: str, tamanho: int, cor) -> None:
    f = fonte(tamanho)
    d.text(((largura - d.textlength(texto, font=f)) / 2, y), texto, font=f, fill=cor)


def mascote(cor) -> Image.Image:
    im = Image.new("RGBA", (320, 320), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([90, 10, 230, 140], fill=cor)
    d.rounded_rectangle([80, 120, 240, 315], radius=40, fill=cor)
    for x in (125, 170):
        d.ellipse([x, 55, x + 25, 85], fill="white")
        d.ellipse([x + 8, 65, x + 20, 80], fill=MARINHO)
    return im


def produto(rotulo: str) -> Image.Image:
    im = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([130, 60, 270, 340], radius=10, fill=GRAFITE, outline=(0, 255, 255), width=3)
    d.rectangle([140, 80, 260, 250], fill=MARINHO)
    for i in range(3):
        d.ellipse([188, 100 + i * 50, 212, 124 + i * 50], outline=ROSA, width=3)
    texto_centro(d, 400, 355, rotulo, 15, VERDE)
    return im


def banner(n: str) -> Image.Image:
    im = Image.new("RGB", (1296, 400), (20, 24, 80))
    d = ImageDraw.Draw(im)
    for k in range(0, 1296, 60):
        d.line([(k, 0), (k + 200, 400)], fill=(40, 40, 140), width=18)
    texto_centro(d, 1296, 160, f"Banner {n} — provisório", 64, ROSA)
    return im


def icone(cor) -> Image.Image:
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([6, 6, 58, 58], outline=cor, width=6)
    d.ellipse([24, 24, 40, 40], fill=cor)
    return im


def desenhar(nome_novo: str) -> Image.Image:
    base = nome_novo.rsplit(".", 1)[0]
    if base == "mascote-principal" or base == "favicon":
        return mascote(ROSA)
    if base == "mascote-secundario":
        return mascote(CIANO)
    if base.startswith("produto-"):
        return produto(base.removeprefix("produto-"))
    if base.startswith("banner-"):
        return banner(base.split("-")[1])
    if base == "icone-destaques":
        return icone((255, 215, 0))
    return icone(REDES.get(base, (0, 230, 138)))


def salvar(im: Image.Image, destino: Path) -> None:
    ext = destino.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        im.convert("RGB").save(destino, "JPEG", quality=85)
    elif ext == ".webp":
        im.save(destino, "WEBP", quality=85)
    else:
        im.save(destino)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    destino = Path(sys.argv[1])
    legado = "--legado" in sys.argv[2:]
    destino.mkdir(parents=True, exist_ok=True)
    total = 0
    for antigo, novos in MAPA.items():
        if legado:
            salvar(desenhar(novos[0]), destino / antigo)
            total += 1
        else:
            for novo in novos:
                salvar(desenhar(novo), destino / novo)
                total += 1
    print(f"{total} imagem(ns) provisória(s) em {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
