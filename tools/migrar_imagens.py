#!/usr/bin/env python3
"""
Copia as imagens do site atual (pasta imgs/) para img/ com os nomes semânticos
usados pelas páginas novas (a classe de cada <img> = nome do arquivo).

Uso (na pasta raiz do site, onde ficam imgs/ e as páginas .html):
    python tools/migrar_imagens.py                 # origem imgs/  → destino img/
    python tools/migrar_imagens.py C:/site/imgs C:/site/img

Funciona em Windows, Linux e macOS. Não apaga nem sobrescreve nada: só copia.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

# arquivo no site atual  ->  arquivo(s) novo(s) em img/
MAPA: dict[str, list[str]] = {
    # Personagens (slots #slot-mascote-*) — o principal também vira favicon
    "Logo4.png": ["mascote-principal.png", "favicon.png"],
    "Logo3.png": ["mascote-secundario.png"],
    # Ícones
    "carrinhocompra1.png": ["icone-carrinho.png"],
    "entreoucadastreseicone.png": ["icone-usuario.png"],
    "pcicon.png": ["icone-destaques.png"],
    "Address.png": ["icone-endereco.png"],
    "Telephone.png": ["icone-telefone.png"],
    "email.png": ["icone-email.png"],
    "horario.png": ["icone-horario.png"],
    # Página Entre ou cadastre-se (abas Entrar / Criar conta)
    "loginperfil.png": ["icone-entrar.png"],
    "cadastroimg.png": ["icone-cadastro.png"],
    # Redes sociais
    "facebook.png": ["rede-facebook.png"],
    "instagram.png": ["rede-instagram.png"],
    "youtube.png": ["rede-youtube.png"],
    "tiktok.png": ["rede-tiktok.png"],
    # Carrossel (na ordem em que aparecem no site)
    "banner1.jpg": ["banner-1.jpg"],
    "banner4.png": ["banner-2.png"],
    "Banner5.jpg": ["banner-3.jpg"],
    "Banner3.jpg": ["banner-4.jpg"],
    "banner2.png": ["banner-5.png"],
    # Computadores (vitrine "Destaques")
    "pc1.png": ["produto-pc-gamer-rtx3060.png"],
    "pc2.png": ["produto-pc-escritorio-dual-core.png"],
    "pc3.png": ["produto-pc-gamer-ryzen9-5900x.png"],
    "pc4.png": ["produto-pc-gamer-ryzen5-5600g.png"],
    "pc5.png": ["produto-notebook-intel.png"],
    "pc6.png": ["produto-computador-completo.png"],
    "pc7.png": ["produto-pc-gamer-nitro-x.png"],
    "pc8.png": ["produto-pc-profissional.png"],
    "pc9.png": ["produto-computador-gamer.png"],
    "NotebookGamer.png": ["produto-notebook-gamer.png"],
    # Consoles, games e periféricos
    "x360.png": ["produto-controle-xbox-360.png"],
    "playstation5.webp": ["produto-playstation-5.webp"],
    "Headset7.1.webp": ["produto-headset-gamer-7-1.webp"],
    "XBoxSX.webp": ["produto-xbox-series-x.webp"],
    "VolanteGamer.webp": ["produto-volante-gamer.webp"],
    "NintendoSwitch-removebg-preview.png": ["produto-nintendo-switch-oled.png"],
    "SuporteHeadset.webp": ["produto-suporte-headset.webp"],
    "mininintendo.webp": ["produto-super-nintendo-mini.webp"],
    "monitor144hz.webp": ["produto-monitor-gamer-144hz.webp"],
    "playstation2.webp": ["produto-playstation-2-slim.webp"],
    "MonitorLed.png": ["produto-monitor-24-led.png"],
    "MouseGamer.png": ["produto-mouse-gamer.png"],
    "Headset.png": ["produto-headset.png"],
    "gtx1080.png": ["produto-gtx1080.png"],
    "cadeira.png": ["produto-cadeira-office.png"],
    # Página Computadores (computadores.html) — vitrine da categoria, na ordem do site atual
    "Computadores.computadores.png": ["icone-computadores.png"],
    "pc01.png": ["produto-pc-escritorio.png"],
    "pc02.png": ["produto-pc-gamer-basico.png"],
    "pc03.png": ["produto-computador-ideal.png"],
    "pc04.png": ["produto-computador-produtivo.png"],
    "pc05.png": ["produto-pc-economico.png"],
    "pc06.png": ["produto-pc-ultra-performance.png"],
    "pc07.png": ["produto-pc-domestico.png"],
    "pc08.png": ["produto-pc-workstation.png"],
    "pc09.png": ["produto-pc-essencial.png"],
    # Página Hardware (hardware.html) — vitrine da categoria, na ordem do site atual
    # (gtx1080.png já está acima: produto-gtx1080.png)
    "placamaeicon.png": ["icone-hardware.png"],
    "Ryzen 75800x.png": ["produto-ryzen7-5800x.png"],
    "inteli510400f.png": ["produto-intel-i5-10400f.png"],
    "SSDGiga.png": ["produto-ssd-aorus-512gb.png"],
    "Asusb550.png": ["produto-placa-mae-asus-b550.png"],
    "Ram.png": ["produto-memoria-aorus-ddr5.png"],
    "Fonte.png": ["produto-fonte-rm1000x.png"],
    "RXVega.png": ["produto-radeon-rx-vega-64.png"],
    "Rtx2080ti.png": ["produto-rtx2080-ti.png"],
    # Página Periféricos (perifericos.html) — vitrine da categoria, na ordem do site atual
    # (MonitorLed.png, MouseGamer.png e Headset.png já estão acima)
    "mouseiconpng.png": ["icone-perifericos.png"],
    "tecladomecanico.png": ["produto-teclado-mecanico.png"],
    "webcam.png": ["produto-webcam-1080p.png"],
    "caixadesom.png": ["produto-caixa-de-som-usb.png"],
    "Mousepad.png": ["produto-mousepad-gamer.png"],
    "impressora.png": ["produto-impressora-multifuncional.png"],
    "suportemonitor.png": ["produto-suporte-monitor.png"],
    # Página Escritório (escritorio.html) — vitrine da categoria, na ordem do site atual
    # (cadeira.png já está acima)
    "escritoriopng.png": ["icone-escritorio.png"],
    "Cadeiraergonomica.png": ["produto-cadeira-ergonomica-executiva.png"],
    "mesaescritorio.png": ["produto-mesa-escritorio-gavetas.png"],
    "Mesaescritorio2.png": ["produto-mesa-compacta.png"],
    "organizadormesa.png": ["produto-organizador-de-mesa.png"],
    "luminaria.png": ["produto-luminaria-de-mesa.png"],
    "mesaescritorio3.png": ["produto-mesa-executiva.png"],
    "filtro.png": ["produto-estabilizador-500va.png"],
    "protetortela.png": ["produto-protetor-de-tela.png"],
}


def main() -> int:
    origem = Path(sys.argv[1] if len(sys.argv) > 1 else "imgs").resolve()
    destino = Path(sys.argv[2] if len(sys.argv) > 2 else "img").resolve()
    if not origem.is_dir():
        print(f"Pasta de origem não encontrada: {origem}")
        print("Rode na raiz do site (onde fica a pasta imgs/) ou informe o caminho: python tools/migrar_imagens.py <imgs> <img>")
        return 1
    destino.mkdir(parents=True, exist_ok=True)

    # Índice sem diferenciar maiúsculas (Banner5.jpg x banner5.jpg)
    arquivos = {p.name.lower(): p for p in origem.iterdir() if p.is_file()}
    copiados = mantidos = 0
    faltando: list[str] = []

    for antigo, novos in MAPA.items():
        fonte = arquivos.get(antigo.lower())
        if fonte is None:
            faltando.append(antigo)
            continue
        for novo in novos:
            alvo = destino / novo
            if alvo.exists():
                mantidos += 1
                continue
            shutil.copy2(fonte, alvo)
            copiados += 1
            print(f"ok  {fonte.name:<40} -> img/{novo}")

    print(f"\n{copiados} copiada(s), {mantidos} já existia(m) em {destino}")
    if faltando:
        print("Não encontradas na origem (confira o nome):")
        for nome in faltando:
            print(f"  - {nome}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
