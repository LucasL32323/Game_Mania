# Roadmap — GameMania 2.0

A rotina noturna pega o **primeiro item `[ ]`** desta lista, faz, testa e marca `[x]` com a data.
Item grande demais para uma noite: faça uma parte coerente, marque `[~]` e descreva o que falta logo abaixo.
O Lucas pode reordenar, apagar ou acrescentar itens a qualquer momento (é só editar este arquivo na `main` ou na `desenvolvimento`).

Legenda: `[ ]` a fazer · `[~]` em andamento · `[x]` feito

## Fase 1 — páginas que o menu já linka (hoje dão 404 no site novo)

- (R08 concluído — ver "Feito")

## Fase 2 — páginas de produto (uma por noite, no padrão do `produto.html`)

- (R09, R10, R11, R12, R13 e R14 concluídos — ver "Feito")
- [ ] **R15 · pccompleto.html** (id 6) — de `legado/pccompleto.html`
- [ ] **R16 · pcdualcore.html** (id 2) — de `legado/pcdualcore.html`
- [ ] **R26 · Páginas dos 9 computadores da categoria** (ids 11–19, hoje com botão "Comprar" direto em `computadores.html`): PC Escritório (`legado/pcescritorio.html`), PC Gamer Básico, Computador Ideal, Computador Produtivo, PC Econômico, PC Ultra Performance, PC Doméstico, PC Workstation e PC Essencial — uma ou duas por noite no padrão do `produto.html`; preencher o `page_path` no seed e trocar o botão por "Mais Informações".
- [ ] **R27 · Páginas das 9 peças de hardware** (ids 31–39, hoje com botão "Comprar" direto em `hardware.html`): GTX 1080 (`legado/gtx1080.html`), Ryzen 7 5800X, i5-10400F, SSD AORUS 512GB, Placa-Mãe Asus B550, RAM AORUS DDR5, Fonte RM1000x, RX Vega 64 (`legado/AMDRadeonRXVega 64.html`) e RTX 2080 Ti (`legado/rtx2080.html`) — uma ou duas por noite no padrão do `produto.html`; preencher o `page_path` no seed e trocar o botão por "Mais Informações".
- [ ] **R28 · Páginas dos 9 periféricos da categoria** (ids 21–23 e 61–66, hoje com botão "Comprar" direto em `perifericos.html`): Teclado Mecânico (`legado/tecladomecanico.html`), Mouse Gamer (`legado/mousegamer.html`), Monitor 24" LED (`legado/Monitorled.html`), Headset com Microfone (`legado/headset.html`), Webcam 1080p, Caixa de som USB, Mousepad Gamer, Impressora Multifuncional (`legado/Impressora.html`) e Suporte para Monitor (`legado/suporte.html` — no site antigo esse arquivo é a página do produto; o `suporte.html` novo é o FAQ do R07, então usar outro nome, ex.: `suporte-monitor.html`) — uma ou duas por noite; preencher o `page_path` no seed (hoje 21–23 apontam para páginas que ainda não existem no site novo) e trocar o botão por "Mais Informações".
- [ ] **R29 · Páginas dos 9 produtos de escritório** (ids 41–49, hoje com botão "Comprar" direto em `escritorio.html`): Cadeira Ergonômica Executiva (`legado/Cadeira.html`), Mesa de Escritório com Gavetas (`legado/Mesa-Escritório.html`), Mesa Compacta (`legado/Mesa-Compacta.html`), Organizador de Mesa, Luminária de Mesa, Mesa Executiva (`legado/Mesa-De-Escritorio.html` — no card do site antigo a estrutura é "aço", na página é "madeira": usar a ficha da página), Estabilizador 500VA (`legado/Estabilizador-de-energia.html`), Protetor de Tela e Cadeira Giratória Office Básica (`legado/Cadeira-Office.html`) — uma ou duas por noite; preencher o `page_path` no seed e trocar o botão por "Mais Informações".
- [ ] **R17 · Páginas dos consoles e periféricos da home** (hoje com botão "Comprar" direto): criar as que tiverem conteúdo suficiente e trocar o botão por "Mais Informações" na vitrine.

## Fase 3 — back-end e conta

- [ ] **R18 · GET /api/v1/products** — catálogo paginado (filtro por categoria, busca por nome com `ILIKE` parametrizado, ordenação), schema Pydantic de saída, testes no `test_api.py`.
- [ ] **R19 · pedidos.html + GET /api/v1/orders** — histórico completo do usuário logado com itens e status; link "Ver todos" do painel.
- [ ] **R20 · Alterar senha (logado)** — `POST /api/v1/auth/password` (senha atual + nova, Argon2id, invalida sessão antiga) e formulário no painel.
- [ ] **R21 · Migrações com Alembic** — substituir `scripts/init_db.py` + `sql/migracoes/` por Alembic (migração inicial = schema atual), sem quebrar o `testar_tudo.sh`.

## Fase 4 — qualidade

- [ ] **R22 · Acessibilidade automática** — rodar axe-core (npm) no E2E em todas as páginas e corrigir as violações sérias/críticas.
- [ ] **R23 · Imagens leves** — gerar `.webp` das imagens acima de 300 KB em `frontend/img` (ex.: `banner-2.png`, 3,3 MB), trocar o `src` e manter o `data-gm-legado`; medir o ganho em KB no CHANGELOG.
- [ ] **R24 · Painel de métricas para o dono (admin.html)** — lê as views `vw_top_products`, `vw_conversion_funnel_daily`, `vw_return_rate_30d` por uma rota restrita a administrador.

## Depois do roadmap

Com tudo `[x]`, a rotina escolhe a melhoria de maior impacto que encontrar (bug, acessibilidade, performance, SEO, segurança), registra aqui como novo item `R25+` e faz.

## Feito

<!-- A rotina noturna move os itens concluídos para cá: - [x] R01 · ... — AAAA-MM-DD -->

- [x] **R01 · carrinho.html** — 2026-10-14 — lista o `localStorage['cart']` (formato do `compra.js`: `{id,title,price,img,qty}`), alterar quantidade (1–10) e remover, subtotal só para exibição, estado vazio com `#slot-mascote-carrinho-vazio`, botão "Finalizar compra" → `POST /api/v1/orders` (login obrigatório; sem sessão → `entreoucadastrese.html?next=`), toast de sucesso e limpeza do carrinho. Conteúdo/estilo de referência: `legado/carrinho.html`. E2E: adicionar na home → aparece no carrinho → alterar qtd → remover → finalizar logado cria pedido no banco.
- [x] **R02 · entreoucadastrese.html** — 2026-10-14 — abas Entrar / Criar conta (Bootstrap `nav-tabs`), `POST /api/v1/auth/login` e `/register` via `GMUI.apiFetch`, mensagens de erro genéricas (sem revelar se o e-mail existe), redireciona para `?next=` **somente se for caminho relativo interno** (bloquear `//`, `http:`, `javascript:` — open redirect), slot de mascote. Referência: `legado/entreoucadastrese.html`, `legado/cadastro.html`. E2E: cadastro → volta para o `next`; senha errada mostra erro; `next=https://evil.com` é ignorado.
- [x] **R25 · Bootstrap 5.3.8 + versão em fonte única** — 2026-10-14 — 5.3.3 → 5.3.8 nas 5 páginas, SRI conferido contra os bytes do npm; versão e hashes só em `tests/test_estatico.py` (`BS_VERSAO`, `SRI_CSS`, `SRI_JS`); `tools/atualizar_bootstrap.py <versão>` atualiza tudo num comando (`--checar` para CI).
- [x] **R03 · computadores.html** — 2026-10-14 — vitrine da categoria com os 19 computadores (10 destaques + 9 de `legado/computadores.html`, preços do site original, ids 11–19 novos no `seed_products.sql`), contagem de itens, breadcrumb + JSON-LD (BreadcrumbList/ItemList), slot `#slot-mascote-categoria`, ordenação por relevância/preço/nome sem recarregar com `?ordem=` em lista branca — componente reutilizável `select[data-gm-ordenar]` no `gm-ui.js` (seção 13) para o R04–R06.
- [x] **R04 · hardware.html** — 2026-10-14 — vitrine com as 9 peças de `legado/hardware.html` (ids 32–39 novos no seed; GTX 1080 corrigida para o preço do site original), abas de tipo reutilizáveis `[data-gm-filtrar]` (`gm-ui.js` seção 14, `?tipo=` em lista branca) combinadas com a ordenação do R03.
- [x] **R05 · perifericos.html** — 2026-10-15 — vitrine com 13 periféricos (9 de `legado/perifericos.html` + 4 da home), ids 61–66 novos no seed, abas Teclados e mouses · Monitores · Áudio · Webcam e impressão · Games + ordenação (componentes do R03/R04).
- [x] **R06 · escritorio.html** — 2026-10-15 — vitrine com os 9 produtos de `legado/escritorio.html`, ids 42–49 novos no seed e id 41 corrigido (R$ 250,00, sem página quebrada), abas Cadeiras · Mesas · Acessórios de mesa · Energia + ordenação (componentes do R03/R04).
- [x] **R07 · suporte.html** — 2026-10-15 — central de suporte com 4 canais (WhatsApp `wa.me/551392124291`, telefone, e-mail, loja com mapa) e horário; FAQ em `accordion` Bootstrap com 11 perguntas em 5 assuntos (trocas, garantia, frete, pagamento, montagem) baseadas no site original + CDC; busca sem acento, link direto `#faq-<id>`, JSON-LD `FAQPage`, slots `#slot-mascote-suporte` e `#slot-mascote-faq-vazio`.
- [x] **R08 · 404.html** — 2026-10-15 — página "não encontrada" com o "404" em neon, personagem em `#slot-mascote-404`, endereço procurado (texto puro), "Voltar" só para visitas internas, busca que leva para `index.html?q=` e atalhos para as 5 seções do menu com a quantidade de produtos de cada uma; FastAPI (dev) serve a 404 com status 404 em qualquer rota inexistente (`<base href="/">` em rotas aninhadas) e mantém `/api/...` inexistente em JSON (`backend/app/frontend.py`).
- [x] **R09 · pcgamerrtx3060.html** (id 1) — 2026-10-15 — página do PC Gamer RTX 3060 no padrão do `produto.html` com nome, ficha técnica (11 itens), preço (R$ 4.999,00) e foto de `legado/pcgamerrtx3060.html`; garantia de 15 meses (a da página original), relacionados sem o próprio produto; botões −/+ e campo de quantidade com alvo de toque ≥ 44 px em todas as páginas de produto (CSS seção 22).
- [x] **R10 · Ryzen95900x.html** (id 3) — 2026-10-15 — página do PC Gamer Ryzen 9 no padrão do `produto.html`: nome e preço do card original (R$ 7.499,00, igual ao banco), ficha com os 11 itens (processador da `legado/Ryzen95900x.html` + 32 GB/SSD 1 TB do card), foto `pc3.png`, quantidade limitada ao estoque (5), relacionados com o RTX 3060; a 404 do E2E passou a ser testada com `PCGamerNitro.html` (R11).
- [x] **R11 · PCGamerNitro.html** (id 7) — 2026-10-15 — página do PC Gamer Nitro X no padrão do `produto.html` com os 11 itens da ficha de `legado/PCGamerNitro.html` (Ryzen 7 5700X, RTX 4060 Ti 8 GB, 32 GB DDR4 3600, SSD NVMe 1 TB, B550, 650 W, Ubuntu 24.04), R$ 7.499,00, foto `pc7.png`, quantidade até o estoque (4), relacionados com o Ryzen 9; cards da vitrine corrigidos de "RTX 4070" para "RTX 4060 Ti" (igual à ficha); a 404 do E2E passou a ser testada com `pcprofissional.html` (R12).
- [x] **R12 · pcprofissional.html** (id 8) — 2026-10-15 — página do PC Profissional no padrão do `produto.html` com os 11 itens da ficha de `legado/pcprofissional.html` (i7-12700, B660-PLUS D4, 32 GB DDR5 5200, SSD NVMe 1 TB, RTX 4070 12 GB, 750 W Gold modular, Windows 11 Pro, Ethernet 2.5G), R$ 5.299,00, foto `pc8.png`, quantidade até o estoque (6), garantia de 4 anos, relacionados com o Nitro X; cards das vitrines corrigidos de "SSD 1TB + HD 2TB" para "SSD NVMe 1TB, RTX 4070" (igual à ficha); a 404 do E2E passou a ser testada com `ComputadorGamer.html` (R13).
- [x] **R13 · ComputadorGamer.html** (id 9) — 2026-10-15 — página do Computador Gamer no padrão do `produto.html` com os 11 itens da ficha de `legado/ComputadorGamer.html` (i7-11700, Gigabyte B560M DS3H AC, 16 GB DDR4 3200, SSD NVMe 512 GB, RTX 3060 12 GB, 650 W Bronze, Windows 11 Home), R$ 4.499,00, foto `pc9.png`, quantidade até o estoque (7), garantia 3 anos + 1 ano de montagem, relacionados com o PC Profissional; `gm-ui.js` passou a limitar a **soma** no carrinho ao estoque da página (antes só o campo era limitado); a 404 do E2E passou a ser testada com `NotebookIntel.html` (R14).
- [x] **R14 · NotebookIntel.html** (id 5) — 2026-10-15 — página do Notebook Intel no padrão do `produto.html` com os 10 itens da ficha de `legado/NotebookIntel.html` (i3-10100F, UHD 630, 8 GB DDR4 2666, SSD 480 GB SATA, Ubuntu 24.04 LTS, Wi-Fi 5/BT 4.2), R$ 2.199,00, foto `pc5.png` (706×549), quantidade até o estoque (10), garantia de 1 ano com suporte remoto, relacionados com o Computador Gamer; cards da home e de Computadores corrigidos de "SSD 256GB" para "SSD 480GB" (igual à ficha); a 404 do E2E passou a ser testada com `pccompleto.html` (R15).
