# Changelog — GameMania 2.0

Uma entrada por mudança, a mais recente no topo. A rotina noturna acrescenta aqui o que fez em cada noite.

## 2026-10-15 — R14 · Página do Notebook Intel (NotebookIntel.html)

- **`frontend/NotebookIntel.html`** (nova): o "Mais Informações" do Notebook Intel (home e Computadores) deixou de cair na 404. Estrutura copiada do `ComputadorGamer.html`/`produto.html` (topo, menu com `aria-current="true"` em Computadores, rodapé byte a byte igual); `body[data-product-id="5"]` (o seed já tinha `page_path = NotebookIntel.html`).
- **Conteúdo do site original** (`legado/NotebookIntel.html`): **ficha técnica com os 10 itens** na mesma ordem (Intel Core i3-10100F 4 núcleos/8 threads até 4,3 GHz, Intel UHD Graphics 630 integrada, 8 GB DDR4 2666 MHz, SSD 480 GB SATA, H410M, 450 W 80 Plus White, Linux Ubuntu 24.04 LTS, Ethernet Gigabit/Wi-Fi 5/Bluetooth 4.2, HDMI/VGA/USB/RJ-45/P2, 1 ano de garantia total com suporte remoto) e **preço R$ 2.199,00** (12x de R$ 183,25), igual ao banco.
- Foto original (`imgs/pc5.png` → `img/produto-notebook-intel.png`, 706×549, já no MAPA) como LCP com `preload`; JSON-LD `Product` + `BreadcrumbList`, canonical e Open Graph.
- Quantidade máxima = estoque do seed (**10**, igual ao limite da API); garantia de **1 ano** nos benefícios (a da página original).
- Mascote secundário no `#slot-mascote-dica-produto` com dica de uso (estudo/trabalho) baseada só na ficha.
- "Quem viu este notebook também curtiu": RTX 3060, Ryzen 5, **Computador Gamer** (id 9, no lugar do PC Profissional) e Nitro X.
- **Correção de catálogo**: o card dizia "Intel i3, 8GB RAM, SSD 256GB", mas a página do produto no site original diz **SSD 480 GB SATA**. Os cards de `index.html` e `computadores.html` agora mostram "Intel i3-10100F, 8GB RAM, SSD 480GB".
- Suposições: a ficha original tem itens de desktop (placa-mãe H410M, fonte 450 W, porta VGA) e um i3-**F** (sem vídeo integrado de verdade) com "UHD Graphics 630"; mantive o texto do site original sem inventar nada — vale o Lucas revisar a ficha. Quando card e página divergem, vale a ficha da página (mesmo critério do R11/R12/R29).
- Testes: a 404 do E2E agora usa `pccompleto.html` (próxima página, R15). E2E com 30 verificações novas (card de Computadores com SSD 480 GB → página com HTTP 200, `<h1>`, id, nome/preço/page_path = Postgres, parcelas, cor do preço, JSON-LD, canonical/OG, menu, breadcrumb, 10 specs na ordem e valores do legado, garantia, LCP eager + preload + `data-gm-legado` com proporção 706×549, mascote, relacionados = [1, 4, 9, 7] com origem no funil, page_view com product_id=5, quantidade máx. = estoque 10, carrinho legado, contador + toast, `add_to_cart` com qty, 2 colunas no desktop, "Comprar agora" 6 + 6 limitado a 10, celular 390 px sem scroll, foto acima do título, alvos ≥ 44 px, sem erros de JS).

RESULTADO: estático 434/434 · E2E 487/487 · API 44/44 · TUDO OK

## 2026-10-15 — R13 · Página do Computador Gamer (ComputadorGamer.html)

- **`frontend/ComputadorGamer.html`** (nova): o "Mais Informações" do Computador Gamer (home e Computadores) deixou de cair na 404. Estrutura copiada do `pcprofissional.html`/`produto.html` (topo, menu com `aria-current="true"` em Computadores, rodapé byte a byte igual); `body[data-product-id="9"]` (o seed já tinha `page_path = ComputadorGamer.html`).
- **Conteúdo do site original** (`legado/ComputadorGamer.html`): resumo "gabinete preto", **ficha técnica com os 11 itens** na mesma ordem (Intel Core i7-11700 8 núcleos/16 threads até 4,9 GHz, Gigabyte B560M DS3H AC, 16 GB 2x8 GB DDR4 3200 MHz, SSD NVMe M.2 512 GB, RTX 3060 12 GB GDDR6, fonte 650 W 80 Plus Bronze, gabinete preto simples em aço, Windows 11 Home 64 bits, Wi-Fi 5/Bluetooth 5.0/Ethernet Gigabit, portas, garantia 3 anos componentes / 1 ano montagem) e **preço R$ 4.499,00** (12x de R$ 374,92), igual ao banco.
- Foto original (`imgs/pc9.png` → `img/produto-computador-gamer.png`, 1134×992, já no MAPA) como LCP com `preload`; JSON-LD `Product` + `BreadcrumbList`, canonical e Open Graph.
- Quantidade máxima = estoque do seed (**7**); garantia de **3 anos + 1 ano de montagem** nos benefícios (a da página original).
- Mascote secundário no `#slot-mascote-dica-produto` com dica baseada só na ficha.
- "Quem viu este PC também curtiu": RTX 3060, Ryzen 5, **PC Profissional** (id 8, no lugar do Ryzen 9) e Nitro X.
- **Correção no carrinho (`js/gm-ui.js` seções 5 e 6)**: o campo de quantidade respeitava o estoque, mas clicar várias vezes em "Adicionar ao carrinho"/"Comprar agora" somava além dele (ex.: 4 + 4 = 8 com estoque 7). Agora os botões com `data-gm-usa-qtd` recebem `data-gm-qtd-max` e a soma no carrinho para no estoque da página (ou em 10, o limite da API). Vale para todas as páginas de produto.
- Suposição: o card do Computador Gamer não cita a placa de vídeo, mas nada nele contradiz a ficha, então os cards das vitrines ficaram como estavam.
- Testes: a 404 do E2E agora usa `NotebookIntel.html` (próxima página, R14). E2E com 27 verificações novas (home → página com HTTP 200, `<h1>`, id, nome/preço/page_path = Postgres, parcelas, cor do preço, JSON-LD, canonical/OG, menu, breadcrumb, 11 specs, garantia, LCP eager + preload + `data-gm-legado`, mascote, relacionados = [1, 4, 8, 7] com origem no funil, page_view com product_id=9, quantidade máx. = estoque 7, carrinho legado, contador + toast, `add_to_cart` com qty, "Comprar agora" 4 + 4 limitado a 7, celular 390 px sem scroll, foto acima do título, alvos ≥ 44 px, sem erros de JS).

RESULTADO: estático 409/409 · E2E 456/456 · API 44/44 · TUDO OK

## 2026-10-15 — R12 · Página do PC Profissional (pcprofissional.html)

- **`frontend/pcprofissional.html`** (nova): o "Mais Informações" do PC Profissional (home, Computadores, relacionados das outras páginas de produto e favoritos do painel) deixou de cair na 404. Estrutura copiada do `PCGamerNitro.html`/`produto.html` (topo, menu com `aria-current="true"` em Computadores, rodapé byte a byte igual); `body[data-product-id="8"]` (o seed já tinha `page_path = pcprofissional.html`).
- **Conteúdo do site original** (`legado/pcprofissional.html`): resumo "gabinete preto", **ficha técnica com os 11 itens** na mesma ordem (Intel Core i7-12700 12 núcleos/20 threads até 4,9 GHz, ASUS PRIME B660-PLUS D4, 32 GB 2x16 GB DDR5 5200 MHz, SSD NVMe M.2 1 TB, RTX 4070 12 GB GDDR6X, fonte 750 W 80 Plus Gold modular, Mid Tower preto com vidro temperado, Windows 11 Pro 64 bits, Wi-Fi 6/Bluetooth 5.2/Ethernet 2.5G, portas, garantia 4 anos componentes / 2 anos montagem) e **preço R$ 5.299,00** (12x de R$ 441,58), igual ao banco.
- Foto original (`imgs/pc8.png` → `img/produto-pc-profissional.png`, 774×774, já no MAPA) como LCP com `preload`; JSON-LD `Product` + `BreadcrumbList`, canonical e Open Graph.
- Quantidade máxima = estoque do seed (**6**); garantia de **4 anos** nos benefícios (a da página original).
- Mascote secundário no `#slot-mascote-dica-produto` com dica baseada só na ficha.
- "Quem viu este PC também curtiu": sai o próprio PC Profissional, entra o PC Gamer Nitro X (id 7, `PCGamerNitro.html`).
- **Correção de catálogo**: o card dizia "SSD 1TB + HD 2TB" (texto do card do `legado/pcgamer.html`), mas a página do produto no site original não tem HD. Os cards de `index.html`, `computadores.html`, `produto.html`, `pcgamerrtx3060.html`, `Ryzen95900x.html` e `PCGamerNitro.html` agora mostram "i7-12700, 32GB DDR5, SSD NVMe 1TB, RTX 4070", igual à ficha.
- Suposições: nome mantido como "PC Profissional" (card e banco), não "PC Profissional Intel Core" (título da página antiga); quando card e página divergem, vale a ficha da página (mesmo critério do R11/R29).
- Testes: a 404 do E2E agora usa `ComputadorGamer.html` (próxima página, R13); a checagem do card do Nitro X ficou específica (o card do PC Profissional agora cita a RTX 4070 de verdade). E2E com 29 verificações novas (Computadores → página com HTTP 200, `<h1>`, id, nome/preço/page_path = Postgres, parcelas, cor do preço, JSON-LD, canonical/OG, menu, breadcrumb, 11 specs, garantia, cards das 6 vitrines sem "HD 2TB", LCP eager + preload + `data-gm-legado`, mascote, relacionados = [1, 4, 3, 7] com origem no funil, page_view com product_id=8, quantidade máx. = estoque 6, carrinho legado, contador + toast, `add_to_cart` com qty, "Comprar agora", celular 390 px sem scroll, foto acima do título, alvos ≥ 44 px, sem erros de JS).

RESULTADO: estático 384/384 · E2E 428/428 · API 44/44 · TUDO OK

## 2026-10-15 — R11 · Página do PC Gamer Nitro X (PCGamerNitro.html)

- **`frontend/PCGamerNitro.html`** (nova): o "Mais Informações" do PC Gamer Nitro X (home, Computadores, relacionados das outras páginas de produto e favoritos do painel) deixou de cair na 404. Estrutura copiada do `Ryzen95900x.html`/`produto.html` (topo, menu com `aria-current="true"` em Computadores, rodapé byte a byte igual); `body[data-product-id="7"]` (o seed já tinha `page_path = PCGamerNitro.html`).
- **Conteúdo do site original** (`legado/PCGamerNitro.html`): nome, resumo "gabinete colorido", **ficha técnica com os 11 itens** na mesma ordem (Ryzen 7 5700X 8C/16T até 4,6 GHz, ASUS TUF Gaming B550-PLUS Wi-Fi, 32 GB 2x16 GB DDR4 3600 MHz, SSD NVMe M.2 1 TB, RTX 4060 Ti 8 GB GDDR6, fonte 650 W 80 Plus Bronze, gabinete RGB Mid Tower com vidro temperado, Linux Ubuntu 24.04 LTS, Wi-Fi 6/Bluetooth 5.2/Gigabit, portas, garantia 3 anos componentes / 2 anos montagem) e **preço R$ 7.499,00** (12x de R$ 624,92), igual ao banco.
- Foto original (`imgs/pc7.png` → `img/produto-pc-gamer-nitro-x.png`, 774×774, já no MAPA) como LCP com `preload`; JSON-LD `Product` + `BreadcrumbList`, canonical e Open Graph.
- Quantidade máxima = estoque do seed (**4**).
- Mascote secundário no `#slot-mascote-dica-produto` com dica baseada só na ficha (inclui o aviso de que o PC vem com Ubuntu).
- "Quem viu este PC também curtiu": sai o próprio Nitro X, entra o PC Gamer Ryzen 9 (id 3, `Ryzen95900x.html`).
- **Correção de catálogo**: o card do Nitro X dizia "RTX 4070" (texto do card do `legado/pcgamer.html`), mas a página do produto no site original diz **RTX 4060 Ti 8 GB**. Os cards de `index.html`, `computadores.html`, `produto.html`, `pcgamerrtx3060.html` e `Ryzen95900x.html` agora mostram "RTX 4060 Ti", igual à ficha.
- Suposição: quando card e página do site original divergem, vale a ficha da página (mesmo critério já anotado no R29).
- Testes: a 404 do E2E agora usa `pcprofissional.html` (próxima página, R12). E2E com 29 verificações novas (home → página com HTTP 200, `<h1>`, id, nome/preço/page_path = Postgres, parcelas, cor do preço, JSON-LD, canonical/OG, menu, breadcrumb, 11 specs, garantia, card da home sem "RTX 4070", LCP eager + preload + `data-gm-legado`, mascote, relacionados = [1, 4, 3, 8] com origem no funil, page_view com product_id=7, quantidade máx. = estoque 4, carrinho legado, contador + toast, `add_to_cart` com qty, "Comprar agora", celular 390 px sem scroll, foto acima do título, alvos ≥ 44 px, sem erros de JS).

RESULTADO: estático 359/359 · E2E 399/399 · API 44/44 · TUDO OK

## 2026-10-15 — R10 · Página do PC Gamer Ryzen 9 (Ryzen95900x.html)

- **`frontend/Ryzen95900x.html`** (nova): o "Mais Informações" do PC Gamer Ryzen 9 (home, Computadores, relacionados do `produto.html`/`pcgamerrtx3060.html` e favoritos do painel) deixou de cair na 404. Estrutura copiada do `produto.html` (topo, menu com `aria-current="true"` em Computadores, rodapé idêntico); `body[data-product-id="3"]` (o seed já tinha `page_path = Ryzen95900x.html`).
- **Conteúdo do site original**: nome e preço do card "PC Gamer Ryzen 9" (`legado/pcgamer.html`: **R$ 7.499,00**, 12x de R$ 624,92 — igual ao banco) e **ficha técnica com 11 itens**: os 9 do processador da `legado/Ryzen95900x.html` (Ryzen 9 5900X, Zen 3, 12 núcleos / 24 threads, 3,7 GHz base / até 4,8 GHz, 64 MB L3, 7 nm, 105 W, AM4 com placas série 500/400, garantia 3 anos) + memória 32 GB e SSD 1 TB do card.
- Foto original (`imgs/pc3.png` → `img/produto-pc-gamer-ryzen9-5900x.png`, 722×859) como LCP com `preload`; JSON-LD `Product` + `BreadcrumbList`, canonical e Open Graph.
- Quantidade máxima = estoque do seed (**5**), pelo `max` do campo (o `gm-ui.js` já respeitava).
- Mascote secundário no `#slot-mascote-dica-produto` com dica baseada só na ficha.
- "Quem viu este PC também curtiu": sai o próprio Ryzen 9, entra o PC Gamer RTX 3060 (id 1, `pcgamerrtx3060.html`).
- Suposição: a página antiga descrevia **só o processador** (por R$ 2.499,00), mas o card que leva até ela vende o **PC Gamer Ryzen 9 por R$ 7.499,00** (preço do banco). Mantive o produto/preço do card e usei as specs do processador como ficha; não há GPU/fonte/gabinete no site original, então nada foi inventado. A garantia mostrada é a do processador (3 anos).
- Testes: a 404 do E2E agora usa `PCGamerNitro.html` (próxima página, R11). E2E com 27 verificações novas (Computadores → página com HTTP 200, `<h1>`, id, nome/preço/page_path = Postgres, parcelas, cor do preço, JSON-LD, canonical/OG, menu, breadcrumb, 11 specs, garantia, LCP eager + preload + `data-gm-legado`, mascote, relacionados = [1, 4, 7, 8], page_view com product_id=3, quantidade máx. = estoque 5, carrinho legado, contador + toast, `add_to_cart` com qty, "Comprar agora", celular 390 px sem scroll, foto acima do título, alvos ≥ 44 px, sem erros de JS).

RESULTADO: estático 334/334 · E2E 370/370 · API 44/44 · TUDO OK

## 2026-10-15 — R09 · Página do PC Gamer RTX 3060 (pcgamerrtx3060.html)

- **`frontend/pcgamerrtx3060.html`** (nova): o "Mais Informações" do PC Gamer RTX 3060 (home, Computadores, relacionados do `produto.html` e favoritos do painel) deixou de cair na 404. Estrutura copiada do `produto.html` (topo, menu com `aria-current="true"` em Computadores, rodapé idêntico), conteúdo do `legado/pcgamerrtx3060.html`: nome, resumo, **ficha técnica com os 11 itens** (i5-10400F, RTX 3060 12 GB GDDR6, 16 GB DDR4 3200 MHz 2x8 GB, SSD NVMe 512 GB, B560, fonte 600 W 80 Plus Bronze, gabinete Mid Tower com lateral em acrílico, Windows 11 Home, Wi-Fi AC/Bluetooth 4.2, portas, garantia) e **preço R$ 4.999,00** (12x de R$ 416,58), igual ao banco.
- `body[data-product-id="1"]` (seed já tinha `page_path = pcgamerrtx3060.html`): page views, carrinho, "Comprar agora" e favoritos atribuídos ao produto certo; quantidade até 10 (limite da API; estoque 12).
- Foto original (`imgs/pc1.png` → `img/produto-pc-gamer-rtx3060.png`, 530×638) como LCP com `preload`; JSON-LD `Product` + `BreadcrumbList`, canonical e Open Graph da página.
- Mascote secundário no `#slot-mascote-dica-produto` com uma dica deste PC (baseada só na ficha técnica).
- "Quem viu este PC também curtiu": o próprio RTX 3060 saiu e entrou o PC Gamer Ryzen 5 (id 4, `produto.html`).
- **Acessibilidade em todas as páginas de produto**: `css/gamemania.css` seção 22 — botões −/+ e campo de quantidade passam de ~38 px para 44 px de alvo de toque (antes ficavam abaixo do recomendado no celular).
- Suposição: a garantia mostrada é a da página original deste PC (**15 meses** direto com o fabricante ou com a loja), não os "2 anos + 1 ano de montagem" do PC Ryzen 5.
- Testes: a 404 agora é testada com `Ryzen95900x.html` (próxima página ainda não migrada, R10). E2E com 27 verificações novas (home → página com HTTP 200, `<h1>`, id, nome/preço/page_path = Postgres, parcelas, cor do preço, JSON-LD, canonical/OG, menu, breadcrumb, 11 specs, LCP eager + preload + `data-gm-legado`, mascote, relacionados, page_view com product_id=1, quantidade máx. 10, carrinho legado, contador + toast, `add_to_cart` com qty no funil, "Comprar agora", celular 390 px sem scroll, foto acima do título, alvos ≥ 44 px, sem erros de JS).

RESULTADO: estático 309/309 · E2E 342/342 · API 44/44 · TUDO OK

## 2026-10-15 — R08 · Página não encontrada (404.html)

- **`frontend/404.html`** (nova): qualquer link quebrado do site agora cai numa página da marca em vez do "Not Found" cru — inclusive os 9 "Mais Informações" da vitrine que apontam para páginas de produto ainda não migradas (R09–R16). Topo, menu (sem item marcado) e rodapé copiados do `index.html`; breadcrumb Destaques › Página não encontrada; `noindex, follow` e sem canonical.
- **Destaque do erro**: "404" no rosa-neon com o brilho do letreiro, `<h1>` "Página não encontrada", texto curto e o personagem principal em `#slot-mascote-404` (acima do título no celular, à direita no desktop).
- **Endereço procurado** mostrado só com `textContent` (máx. 120 caracteres; um endereço com HTML aparece como texto). Escondido quando a 404 é aberta direto ou por duplo clique.
- **"Voltar à página anterior"** só aparece quando a visita veio de outra página do próprio site (referrer da mesma origem) — nunca manda a pessoa para fora da loja.
- **Busca** larga ("Ex.: RTX, Ryzen, headset, cadeira...") que leva para `index.html?q=` com a vitrine já filtrada (componente da home).
- **Explore o catálogo**: atalhos para as 5 seções do menu com ícone original e a quantidade de produtos de cada categoria (9 · 19 · 13 · 9 — o E2E confere contra os cards de cada página), com `data-track="erro_404_categoria"` para o funil; link para o suporte e o WhatsApp.
- **Servidor (dev)**: `backend/app/frontend.py` (`FrontendEstatico`) — rota inexistente do site → `404.html` com **status HTTP 404** e `Cache-Control: no-store`; rota aninhada (ex.: `/loja/pc/x`) recebe `<base href="/">` para os caminhos relativos não quebrarem; `/api/...` inexistente continua **404 em JSON** (`{"detail": "Não encontrado"}`), nunca HTML. `gm-ui.js` seção 16 (Boot passou a 17) trata as âncoras `#…` com o `<base>` ("Pular para o conteúdo" não leva para a home).
- `css/gamemania.css`: nova seção 21 (destaque do erro, busca, cards de atalho; alvos de toque ≥ 44 px). README: atributo `body[data-gm-pagina="404"]` e configuração do Nginx em produção (`error_page 404 /404.html` + `sub_filter` do `<base>`).
- Suposição: em produção quem serve o site é o Nginx; deixei a configuração documentada no README (não há arquivo de Nginx no projeto).
- Testes: E2E com 31 verificações novas (link quebrado da home → HTTP 404 amigável, CSS, cor do "404", mascote, menu/breadcrumb, noindex, endereço, atalhos = menu, quantidades = categorias, `data-track`, ícones, "Voltar", busca → `index.html?q=ryzen`, `/404.html` direto, rota aninhada com `<base>`/CSS/imagens, "Pular para o conteúdo" sem sair da página, atalho na rota aninhada, endereço com HTML sem XSS, `/api/...` em JSON, layout desktop e celular 390 px, alvos ≥ 44 px, sem erros de JS); `test_api.py` com 6 verificações novas das rotas inexistentes.

RESULTADO: estático 284/284 · E2E 315/315 · API 44/44 · TUDO OK

## 2026-10-15 — R07 · Central de suporte (suporte.html)

- **`frontend/suporte.html`** (nova): o link "Suporte" do rodapé (em todas as páginas) deixou de dar 404. Topo, menu e rodapé copiados do `index.html` (nenhum item do menu marcado, já que Suporte não está nele); breadcrumb Destaques › Suporte.
- **Canais de atendimento** em cards (1 coluna no celular, 2 no tablet, 4 no desktop): WhatsApp com link direto `wa.me/551392124291` (destacado com o filete rosa e com `data-track="whatsapp"` para o funil), telefone, e-mail e loja em Santos com link para o mapa, além do horário — os mesmos dados do rodapé original.
- **Perguntas frequentes** em `accordion` do Bootstrap: 11 perguntas em 5 assuntos (Trocas e devoluções · Garantia · Frete e entrega · Pagamento · Montagem), com atalhos para cada assunto. Respostas só com fatos do site original (frete grátis para todo o país, cartão em até 12x sem juros/Pix/boleto, entrega em 5 a 7 dias úteis, retirada na loja, PCs montados e testados com 2 anos de garantia nos componentes e 1 ano na montagem) e da lei (CDC: 7 dias de arrependimento, art. 49; 90 dias de garantia legal, art. 26). Nenhum valor ou prazo inventado.
- **Busca de dúvidas** (novo componente `[data-gm-faq-busca]`, `gm-ui.js` seção 15; Boot passou a 16): filtra pergunta + resposta ao digitar, sem acento e sem diferenciar maiúsculas, esconde assuntos vazios, anuncia "3 dúvidas encontradas" por `role=status` e, sem resultado, mostra o personagem em `#slot-mascote-faq-vazio` com atalho para o WhatsApp. Só `hidden`/`textContent` (anti-XSS). Sem JS a busca fica escondida e todas as perguntas aparecem.
- **Link direto para uma pergunta**: `suporte.html#faq-frete-prazo` abre a resposta; abrir uma pergunta grava o `#id` na URL (pronto para mandar no WhatsApp). Só ids que existem na página são aceitos.
- **SEO**: JSON-LD `BreadcrumbList` + `FAQPage` com exatamente as mesmas perguntas e respostas da página (o E2E confere).
- Personagem secundário em `#slot-mascote-suporte` ao lado do título.
- `css/gamemania.css`: nova seção 20 (cards de canal, busca, accordion com as variáveis do Bootstrap trocadas por tokens da marca: pergunta aberta em verde-neon, seta pintada em ciano/verde-neon por máscara — o ícone padrão do Bootstrap vinha azul, fora da paleta; alvos de toque ≥ 44 px). README: atributo `data-gm-faq-busca` documentado.
- Suposição: o `legado/suporte.html` é a página do produto "Suporte para Monitor" (ver R28), não um FAQ; por isso o conteúdo do FAQ veio das outras páginas do site original e do rodapé.
- E2E: 32 verificações novas (link do rodapé, `<h1>`, menu sem `aria-current`, breadcrumb, mascote, 4 canais, `data-track`, 11 perguntas/5 assuntos, JSON-LD = página, abrir/fechar no mesmo assunto, cor da marca, `#id` na URL, busca sem acento, singular/plural, assuntos e atalhos escondidos, busca sem resultado com XSS virando texto, limpar busca, Enter sem recarregar, link direto, `#hash` malicioso ignorado, 4 canais lado a lado no desktop, celular 390 px sem scroll, canais empilhados, alvos ≥ 44 px, toque abre a resposta, sem erros de JS).

RESULTADO: estático 259/259 · E2E 284/284 · API 38/38 · TUDO OK

## 2026-10-15 — R06 · Página Escritório (escritorio.html)

- **`frontend/escritorio.html`** (nova): o item "Escritório" do menu deixou de dar 404 — com isso **as 5 categorias do menu existem** no site novo. Vitrine com os **9 produtos do `legado/escritorio.html`** (Cadeira Ergonômica Executiva, Mesa de Escritório com Gavetas, Mesa Compacta para Escritório, Organizador de Mesa, Luminária de Mesa, Mesa Executiva de Escritório, Estabilizador de Energia 500VA, Protetor de Tela para Monitor, Cadeira Giratória Office Básica), com specs, preços e fotos do site original, na mesma ordem.
- **Abas de tipo** (reuso do `[data-gm-filtrar]`, sem JS novo nem CSS novo): Todos · Cadeiras (2) · Mesas (3) · Acessórios de mesa (3) · Energia (1), combinadas com a ordenação e com `?tipo=`/`?ordem=` na URL (lista branca).
- **Catálogo maior no banco**: ids **42–49** no `backend/sql/seed_products.sql` (categoria `escritorio`), então "Comprar" e "Finalizar compra" funcionam com eles.
- **Correção de preço**: o id 41 ("Cadeira Office") estava no seed com **R$ 649,00** e `page_path` = `Cadeira-Office.html` (página que não existe no site novo). O site original vende a **Cadeira Giratória Office Básica por R$ 250,00** (vitrine e página do produto); nome e preço corrigidos, `page_path` NULL até o R29.
- Mesa de R$ 310,00: o card antigo chama de "Mesa de Escritório" e a página do produto de "Mesa Executiva de Escritório"; usei o nome da página (evita confusão com a "Mesa de Escritório com Gavetas") e as specs do card.
- Breadcrumb Destaques › Escritório, **JSON-LD** `BreadcrumbList` + `ItemList(9)`, menu com `aria-current="page"` em Escritório, personagem principal no `#slot-mascote-categoria`, ícone original da categoria (`escritoriopng.png` → `img/icone-escritorio.png`).
- Imagens: 9 entradas novas no MAPA e no `.bat` (8 fotos + ícone; `cadeira.png` já estava mapeada). Obs.: `filtro.png`, `protetortela.png` e `mesaescritorio3.png` têm ~1,1–1,2 MB cada — entram no R23 (webp).
- Roadmap: novo item **R29** (páginas dos 9 produtos de escritório).
- E2E: 30 verificações novas (9 cards, contagem, menu com um único `aria-current`, breadcrumb, mascote, `<h1>` único, JSON-LD, ordem original, 9 produtos no Postgres, preços = banco, id 41 corrigido, quantidade por aba, aba Mesas, aba + ordenação, troca de aba mantendo a ordem, "Todos", nome Z–A pt-BR, `?tipo=energia`, `?tipo=`/`?ordem=` maliciosos, imagens migradas, carrinho e "Comprar", pedido via API com total do banco, celular 390 px sem scroll, abas com alvo ≥ 44 px e cards em 2 colunas).

RESULTADO: estático 234/234 · E2E 252/252 · API 38/38 · TUDO OK

## 2026-10-15 — R05 · Página Periféricos (perifericos.html)

- **`frontend/perifericos.html`** (nova): o item "Periféricos" do menu deixou de dar 404. Vitrine com **13 periféricos** — os **9 do `legado/perifericos.html`** (Teclado Mecânico, Mouse Gamer, Monitor 24" LED, Headset com Microfone, Webcam 1080p, Caixa de som USB, Mousepad Gamer, Impressora Multifuncional, Suporte para Monitor) + os 4 periféricos da home (Headset Gamer 7.1, Volante Gamer, Suporte para Headset, Monitor Gamer 144Hz), com specs, preços e fotos do site original.
- **Abas de tipo** (reuso do `[data-gm-filtrar]` do R04, sem JS novo): Todos · Teclados e mouses (3) · Monitores (3) · Áudio (4) · Webcam e impressão (2) · Games (1), combinadas com a ordenação do R03 e com `?tipo=`/`?ordem=` na URL.
- **Catálogo maior no banco**: ids **61–66** no `backend/sql/seed_products.sql` (categoria `perifericos`), então "Comprar" e "Finalizar compra" funcionam com eles. O E2E confere que o preço de cada card é igual ao do banco.
- Breadcrumb Destaques › Periféricos, **JSON-LD** `BreadcrumbList` + `ItemList(13)`, menu com `aria-current="page"` em Periféricos, personagem secundário no `#slot-mascote-categoria`.
- Imagens: 7 entradas novas no MAPA e no `.bat` (6 fotos + ícone original `mouseiconpng.png` → `img/icone-perifericos.png`). Obs.: `impressora.png` tem 1,5 MB — entra no R23 (webp).
- Mouse Gamer: o card do site antigo diz R$ 90,00, a página do produto diz R$ 89,00; mantido R$ 89,00 (igual ao banco e à página do produto).
- Os 4 periféricos da home não têm specs no site original, então os cards deles ficam sem a linha de specs (nada inventado).
- Roadmap: novo item **R28** (páginas dos 9 periféricos; atenção ao conflito de nome `suporte.html` = produto no site antigo × FAQ no novo).
- E2E: 31 verificações novas (13 cards, contagem, menu, breadcrumb, mascote, `<h1>` único, JSON-LD, ordem original, 6 produtos no Postgres, preços = banco, aspas do nome do monitor nos `data-*`, quantidade por aba, aba Áudio, aba + ordenação, nome A–Z pt-BR, `?tipo=games`, `?tipo=` malicioso, imagens migradas, carrinho e "Comprar", pedido via API com total do banco, celular 390 px sem scroll e em 2 colunas).

RESULTADO: estático 209/209 · E2E 222/222 · API 38/38 · TUDO OK

## 2026-10-14 — R04 · Página Hardware (hardware.html)

- **`frontend/hardware.html`** (nova): o item "Hardware" do menu deixou de dar 404. Vitrine com as **9 peças do `legado/hardware.html`** — Placa de Vídeo GTX 1080, AMD Ryzen 7 5800X, Intel Core i5-10400F, SSD Gigabyte AORUS 512GB, Placa-Mãe Asus B550, Memória RAM AORUS DDR5, Fonte Corsair RM1000x, AMD Radeon RX Vega 64 e GeForce RTX 2080 Ti — com specs, preços e fotos do site original.
- **Abas de tipo** (novo componente reutilizável `[data-gm-filtrar="#lista"]`, `gm-ui.js` seção 14; Boot passou a 15): Todos · Placas de vídeo · Processadores · Placas-mãe · Memória RAM · Armazenamento · Fontes, com a quantidade de cada aba calculada pelo JS. Filtra só com `hidden` (sem `innerHTML`), funciona junto com a ordenação do R03 (ex.: "3 produtos · Placas de vídeo · do menor para o maior preço"), grava `?tipo=` na URL e só aceita de volta valores de botões que existem na página. Botões com `aria-pressed`; sem JS as abas ficam escondidas e a lista completa aparece. Pronto para o R05 (periféricos) e R06 (escritório).
- **Catálogo maior no banco**: ids **32–39** no `backend/sql/seed_products.sql` (categoria `hardware`), então "Comprar" e "Finalizar compra" funcionam com eles.
- **Correção de preço**: a GTX 1080 (id 31) estava no seed com R$ 1.899,00 (o preço da RTX 2080 Ti); o site original vende por **R$ 1.799,00** (vitrine e página do produto). O `page_path` dela voltou a NULL até a página ser migrada (novo item **R27**).
- Ryzen 7 5800X: o card do site antigo dizia "12 núcleos, 24 threads"; usei a ficha técnica da própria página do produto no site original (8 núcleos / 16 threads, até 4.7 GHz).
- Personagem no `#slot-mascote-categoria`; ícone original da categoria (`placamaeicon.png` → `img/icone-hardware.png`). 10 entradas novas no MAPA e no `.bat` (9 fotos + ícone). Obs.: `Asusb550.png` tem 1,8 MB — entra no R23 (webp).
- `css/gamemania.css`: nova seção 19 (abas em pílula; no celular rolam dentro da faixa, sem scroll horizontal na página, alvo de toque ≥ 44 px; ativo em verde-neon). README: atributo `data-gm-filtrar` documentado. Roadmap: novo item **R27**.
- E2E: 38 verificações novas (9 cards, contagem, menu, breadcrumb, mascote, JSON-LD, 9 produtos no Postgres, preços = banco, GTX 1080 = R$ 1.799, quantidade por aba, filtro de placas de vídeo, `aria-pressed`, `?tipo=`, cor da aba ativa, filtro + ordenação, troca de aba mantendo a ordem, "Todos" limpa a URL, nome A–Z, link compartilhado, `?tipo=` malicioso e inexistente, imagens migradas, carrinho e "Comprar", pedido via API com total do banco e itens gravados, celular 390 px).

RESULTADO: estático 184/184 · E2E 191/191 · API 38/38 · TUDO OK

## 2026-10-14 — R03 · Página Computadores (computadores.html)

- **`frontend/computadores.html`** (nova): o item "Computadores" do menu deixou de dar 404. Vitrine com **19 computadores** — os 10 da home + os **9 do `legado/computadores.html`** (PC Escritório, PC Gamer Básico, Computador Ideal, Computador Produtivo, PC Econômico, PC Ultra Performance, PC Doméstico, PC Workstation, PC Essencial), com specs, preços e fotos do site original.
- **Catálogo maior no banco**: ids **11–19** no `backend/sql/seed_products.sql` (categoria `computadores`, `page_path` NULL até o R26), então "Finalizar compra" funciona com eles. O E2E confere que o preço de cada card é igual ao do banco.
- **Ordenação sem recarregar**: Relevância, Menor/Maior preço, Nome A–Z/Z–A. Componente reutilizável `select[data-gm-ordenar="#lista"]` (`gm-ui.js`, nova seção 13; Boot passou a 14): move os próprios nós (sem `innerHTML`), empate de preço mantém a ordem original, nomes comparados em pt-BR (`Intl.Collator`). A escolha vai para `?ordem=` (link compartilhável) e só é aceita de volta se estiver na lista branca. Sem JS o seletor fica escondido.
- **Contagem de itens** com `role=status` ("19 computadores · do menor para o maior preço"), **breadcrumb** Destaques › Computadores e **JSON-LD** `BreadcrumbList` + `ItemList` (SEO). Menu com `aria-current="page"` em Computadores.
- Personagem no novo slot `#slot-mascote-categoria` ao lado do título. Ícone original da categoria (`Computadores.computadores.png` → `img/icone-computadores.png`).
- Imagens: 10 entradas novas no MAPA e no `.bat` (`pc01.png`…`pc09.png` → `img/produto-pc-*.png`). Obs.: somam ~8 MB (todas com lazy loading) — entram no R23 (webp).
- `css/gamemania.css`: nova seção 18 (cabeçalho da categoria, barra de contagem/ordenação; empilha no celular). README: atributo `data-gm-ordenar` documentado.
- Roadmap: novo item **R26** (páginas dos 9 computadores novos).
- E2E: 28 verificações novas (19 cards, contagem, menu, breadcrumb, mascote, JSON-LD, 9 produtos no Postgres, preços = banco, 4 ordenações, empate estável, `?ordem=` válido e malicioso, volta à relevância, imagens migradas, ícone do carrinho e "Comprar" → carrinho.html com os produtos novos, celular 390 px sem scroll/sobreposição e em 2 colunas).

RESULTADO: estático 159/159 · E2E 153/153 · API 38/38 · TUDO OK

## 2026-10-14 — R25 · Bootstrap 5.3.8 e atualização em um comando

- Bootstrap **5.3.3 → 5.3.8** (CSS + bundle JS) em todas as páginas. Hashes SRI calculados dos bytes publicados no npm e conferidos com os da documentação oficial:
  CSS `sha384-sRIl4kxILFvY47J16cr9ZwB07vP4J8+LH7qKQnuqkuIAvNWLzeN8tE5YBujZqJLB` · JS `sha384-FKyoEForCGlyvwx9Hj09JcYn3nv7wiPVlz7YYwJrWVcXK/BmnVDxM+D2scQbITxI`.
- **Fonte única de verdade**: versão e hashes ficam só em `tests/test_estatico.py` (`BS_VERSAO`, `SRI_CSS`, `SRI_JS`); o `scripts/testar_tudo.sh` lê a versão de lá (antes estava escrita à mão em 13 lugares).
- **`tools/atualizar_bootstrap.py <versão>`** (novo): baixa a versão do npm, calcula o SRI e regrava páginas, teste e CLAUDE.md; recusa versão não exata (`5`, `latest`); `--checar` só confere (sai com 1 se houver atualização pendente — pronto para CI). Testado subindo e descendo de versão numa cópia do projeto.

RESULTADO: estático 134/134 · E2E 125/125 · API 38/38 · TUDO OK

## 2026-10-14 — R02 · Entre ou cadastre-se (entreoucadastrese.html)

- **`frontend/entreoucadastrese.html`** (nova): o link "Entre ou cadastre-se" do topo, o "Favoritar" deslogado e o "Finalizar compra" deslogado não dão mais 404. Abas Bootstrap **Entrar / Criar conta** (`nav-tabs`), com os ícones originais do site (`loginperfil.png` → `img/icone-entrar.png`, `cadastroimg.png` → `img/icone-cadastro.png`, no MAPA e no `.bat`).
- Login e cadastro via `GMUI.apiFetch` (`POST /api/v1/auth/login` e `/register`, CSRF automático, `redirectOn401: false` para senha errada não cair em laço de redirecionamento). Com sucesso volta para o `?next=` ou, sem ele, para o painel (`location.replace`: o "voltar" não reabre o login).
- **Open redirect bloqueado**: o `?next=` só aceita `pagina.html` / `/pasta/pagina.html` do próprio site (recusa `//host`, `http(s):`, `javascript:`, `data:`, barra invertida, `..`, espaços e a própria página de login) e ainda confere a mesma origem com `new URL`.
- **Sem enumeração de e-mails**: mensagens genéricas ("E-mail ou senha incorretos.", "Não foi possível concluir o cadastro com esses dados…"); 429 e 403 com textos próprios.
- Validação no navegador espelhando o `schemas.py` (nome 2–100 sem `< > " ' \``, e-mail, senha ≥ 10, confirmação igual), com `.is-invalid` + `aria-invalid`, foco no 1º campo inválido e a marca saindo ao corrigir. Botão "Mostrar senha" com `aria-pressed`. `autocomplete` certo para gerenciadores de senha.
- `?aba=cadastro` ou `#criar-conta` abrem direto na aba de cadastro (links do site antigo). Aviso "você volta para a página em que estava" quando há `?next=`.
- Mascote no novo slot `#slot-mascote-login`, ao lado das vantagens da conta. Mobile-first: no celular o formulário vem antes.
- `js/gm-ui.js`: nova seção 12 (Boot passou a 13), `GMUI.auth.destinoSeguro` exposto para teste. `css/gamemania.css`: nova seção 17 (só `var(--gm-*)`; vermelho do Bootstrap trocado pelo rosa-neon da marca).
- E2E: 28 verificações novas (16 casos de `?next=` malicioso/válido, abas, validação sem chamar a API, cadastro duplicado com mensagem genérica, cadastro → volta ao `next` com sessão aberta e usuário no Postgres, senha errada, `next=https://evil.com` ignorado → painel, celular 390 px).

RESULTADO: estático 134/134 · E2E 125/125 · API 38/38 · TUDO OK

## 2026-10-14 — R01 · Página do carrinho (carrinho.html)

- **`frontend/carrinho.html`** (nova): o link do carrinho no topo e no rodapé deixou de dar 404. Lista os itens do `localStorage['cart']` (mesmo formato do `compra.js` do site original), com foto, preço unitário, quantidade (− / + / digitada, de 1 a 10 como a API), subtotal por item e botão Remover.
- Resumo do pedido com subtotal, frete grátis, total, parcelamento em 12x e escolha de pagamento (Pix, cartão ou boleto). "Finalizar compra" chama `POST /api/v1/orders` (o servidor recalcula os preços); sem login, leva para `entreoucadastrese.html?next=/carrinho.html` e o carrinho fica guardado.
- Pedido confirmado mostra o código no mesmo formato do painel (`GM-XXXXXXXX`), o total confirmado pelo servidor, limpa o carrinho e zera o contador do topo.
- Estados com mascote: carrinho vazio (`#slot-mascote-carrinho-vazio`) e pedido confirmado (`#slot-mascote-pedido-confirmado`).
- "Esvaziar carrinho" em 2 cliques (o 1º pede confirmação e expira em 4 s), sem `window.confirm`.
- Segurança: o carrinho do navegador é tratado como dado não confiável — ids inválidos descartados, quantidades limitadas, imagem só de `img/` (senão o mascote), textos só por `textContent` + `<template>`.
- Acessibilidade: mudanças de quantidade/remoção anunciadas por `role=status`; o foco vai para o próximo item ao remover; rótulos com o nome do produto em cada botão.
- `js/gm-ui.js`: nova seção 11 (página do carrinho); `css/gamemania.css`: nova seção 16 (carrinho, mobile-first).
- E2E: 23 verificações novas (listagem, total, +/−, limite de 10, remover, XSS no localStorage, esvaziar, pedido logado gravado no Postgres com boleto, código igual ao do painel, estado vazio, finalizar deslogado → login com `next`, celular 390 px sem sobreposição).

RESULTADO: estático 109/109 · E2E 97/97 · API 38/38 · TUDO OK

## 2026-10-14 — Automação

- Projeto salvo na nuvem do Claude (Projeto GameMania_2.0 → `claude/gamemania-2.0/pacote.md`) com `tools/pacote_nuvem.py`; `legado/` (site original, somente leitura) e as **imagens reais** são baixados do repositório público `12172025GameMania`.
- `scripts/testar_tudo.sh`: bateria completa num comando (estático + E2E no Chromium + API com PostgreSQL descartável).
- `tests/test_estatico.py`: regras fixas do projeto (paleta congelada, SRI, CSP, imagens, rodapé idêntico) — 84 verificações.
- E2E: varredura automática de todas as páginas de `frontend/` (HTTP, imagens quebradas, JS, CSP, scroll no celular).
- GitHub Actions (`.github/workflows/testes.yml`) pronto para quando o repositório `GameMania-2.0` existir.
- Rotina noturna (22:50, horário de Brasília): um item do `docs/ROADMAP.md` por noite, salvo na nuvem só com testes verdes.

### Correções encontradas ao ligar os testes com as imagens reais
- Três nomes do mapa de imagens não batiam com os arquivos reais em maiúsculas/minúsculas (`Address.png`, `email.png`, `MouseGamer.png`): o plano B de imagens falharia em servidor Linux. Corrigido no mapa, nas páginas e no `.bat`.
- Fotos de produto mais altas que largas vazavam da moldura do card e cobriam o nome do produto. A moldura agora limita a foto (`max-height`), em qualquer proporção.
- O teste da API tinha o mês da partição de eventos fixo (setembro) e passaria a falhar todo mês. Agora usa o mês corrente.
- Com chaves aleatórias a cada execução, o teste do IP pseudonimizado falhava em ~1% das vezes (procurava "200" dentro de um hash hexadecimal, onde pode aparecer por acaso). Agora confere o formato do hash e a ausência do IP em claro.
