# GameMania 2.0

Reformulação do e-commerce GameMania: layout Bootstrap 5 com a paleta e os mascotes originais, e uma camada
de dados (PostgreSQL + FastAPI) com criptografia de dados pessoais e telemetria de navegação first-party.

```
gamemania-2.0/
├── backend/
│   ├── app/
│   │   ├── main.py                 # app FastAPI, middlewares, /api/v1/csrf, /healthz
│   │   ├── config.py               # settings (variáveis GM_*)
│   │   ├── database.py             # pool transacional + pool de analytics separados
│   │   ├── models.py               # tabelas (SQLAlchemy 2.0) — e-mail cifrado via TypeDecorator
│   │   ├── schemas.py              # contratos Pydantic (validação estrita = 1ª defesa XSS/SQLi)
│   │   ├── security/crypto.py      # Argon2id, AES-256-GCM, blind index, pseudonimização de IP
│   │   ├── security/web.py         # CSP, CSRF, cookie de sessão, rate limit
│   │   ├── services/tracking_queue.py  # fila assíncrona + gravação em lote
│   │   └── routers/                # auth, tracking, commerce (favoritos/pedidos), account (dashboard)
│   ├── scripts/init_db.py          # cria as tabelas (dev)
│   ├── sql/analytics.sql           # partições, views analíticas, MV de interesse, roles
│   ├── sql/seed_products.sql       # catálogo: 25 produtos com preço, imagem e página
│   ├── sql/migracoes/              # alterações para bancos já criados
│   ├── requirements.txt
│   └── .env.example
├── frontend/                       # ← conteúdo vai para a RAIZ do seu site (ao lado de imgs/)
│   ├── index.html                  # home / vitrine (substitui o pcgamer.html)
│   ├── produto.html                # página de produto (PC Gamer Ryzen 5 5600G)
│   ├── dashboard.html              # painel do usuário
│   ├── css/gamemania.css           # design system (tokens da marca + ponte com o Bootstrap)
│   ├── js/gm-tracker.js            # engine de telemetria
│   ├── js/gm-ui.js                 # favoritos, carrinho, consentimento, hidratação do painel
│   └── img/                        # imagens REAIS já migradas (44 arquivos, nomes semânticos)
├── legado/                         # site original (somente leitura): textos, preços e imgs/ para migrar páginas
├── scripts/testar_tudo.sh          # bateria completa num comando (estático + E2E + API)
├── tools/pacote_nuvem.py           # salva/recria o código num único documento (nuvem do Claude)
├── tools/migrar_imagens.py         # copia imgs/ → img/ com os nomes novos (Windows/Linux/Mac)
├── tools/migrar_imagens.bat        # o mesmo, com dois cliques no Windows
├── tests/test_estatico.py          # regras fixas: paleta, SRI, CSP, imagens, rodapé idêntico
├── tests/test_api.py               # 38 verificações da API contra PostgreSQL real
├── tests/e2e_frontend.py           # 70 verificações no Chromium (front + API + banco + file://)
├── docs/ROADMAP.md                 # backlog: a rotina noturna faz 1 item por noite
├── docs/prints/                    # capturas desktop/mobile com as imagens reais
├── CLAUDE.md                       # regras do projeto (para pessoas e para a rotina noturna)
└── CHANGELOG.md                    # o que mudou, noite a noite
```

---

## 0. Colocando no seu site (1 passo)

**Jeito mais rápido:** baixe este repositório (Code → Download ZIP), extraia e abra `frontend/index.html`.
A pasta `frontend/` já vem completa, com `css/`, `js/` e as imagens reais em `img/`.

Para usar dentro da pasta do site antigo, use o **`GameMania-site.zip`** (só o front-end, já na estrutura final):

```text
Botão direito no zip → "Extrair tudo..." → escolha a pasta do seu site (onde já ficam imgs/,
pcgamer.html, style.css) → Extrair. Depois abra o index.html.
```

> Não abra o `index.html` de dentro do zip: o Windows abre só aquele arquivo, sem `css/` e `js/`,
> e a página aparece sem estilo. Sempre extraia antes.

**Imagens:** as páginas já mostram as imagens da sua pasta `imgs/` na hora. Cada `<img>` aponta para
`img/<nome-semântico>` e tem `data-gm-legado="imgs/<arquivo-original>"`; se o arquivo novo ainda não
existir, o `gm-ui.js` carrega o original. Para migrar de vez para `img/` (recomendado antes de publicar),
dê dois cliques em `migrar_imagens.bat` (Windows) ou rode `python migrar_imagens.py`. Nenhum dos dois apaga
nada de `imgs/`.

| Aberto como | O que funciona |
|---|---|
| Duplo clique (`file://`) | Todo o visual, menu, carrossel, busca na vitrine, carrinho. Painel abre em modo demonstração; favoritos e rastreamento ficam desligados (não há API) |
| Live Server | Igual ao duplo clique (a API não está nesse servidor) |
| `uvicorn` (FastAPI) | Tudo: login, favoritos, painel real, pedidos, rastreamento |

As páginas antigas continuam funcionando lado a lado. Nelas, o link "Destaques" aponta para `pcgamer.html`:
troque por `index.html` (ou mantenha uma cópia do `index.html` com o nome `pcgamer.html` até migrar tudo).

Se alguma imagem não existir nem em `img/` nem em `imgs/`, a página não quebra: o espaço é mantido e o
**console do navegador (F12)** lista os arquivos que faltam.

---

## 1. Rodando em desenvolvimento

Pré-requisitos: Python 3.11+ e PostgreSQL 15+.

```bash
# 1) Banco
createdb gamemania

# 2) API
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# gere as chaves e cole no .env (uma por variável):
python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())"

# 3) Schema + analytics + catálogo
python -m scripts.init_db
psql -d gamemania -f sql/analytics.sql
psql -d gamemania -f sql/seed_products.sql
#    banco criado com a versão anterior? rode antes: psql -d gamemania -f sql/migracoes/001_products_page_path.sql

# 4) Imagens do site antigo → nomes novos (dentro de frontend/)
cd ../frontend && python ../tools/migrar_imagens.py /caminho/do/site-antigo/imgs img && cd ../backend

# 5) Subir (serve API + front em http://localhost:8000)
uvicorn app.main:app --reload
```

| URL | O que é |
|---|---|
| `http://localhost:8000/index.html` | Home / vitrine |
| `http://localhost:8000/produto.html` | Página de produto |
| `http://localhost:8000/dashboard.html` | Painel (exige login; sem sessão → redireciona) |
| `http://localhost:8000/dashboard.html?demo=1` | Painel com dados de exemplo, sem back-end |
| `http://localhost:8000/docs` | Swagger (somente com `GM_ENVIRONMENT=development`) |

> No `.env` de dev, `GM_COOKIE_SECURE=false` (HTTP). Em produção, `true` → cookies com prefixo `__Host-`.

---

## 2. Front-end

### Identidade visual

Todos os hexadecimais estão em `:root` no `gamemania.css` (seção 01) e seguem o que **o site atual mostra
na tela**: topo + menu em `#212529` (a classe `bg-dark` do Bootstrap vencia o `#014421` do `style.css`),
filete `#ff004f`, letreiro em Comic Sans maiúsculo com brilho, "Mais Informações" em `#014421`,
preços `#00ff99`, cards `#303234`, fundo `#2e2e2e`, rodapé `#1a1a1a`.
Alterações de tema devem mexer só nos tokens, nunca nos valores.

### Imagens e mascotes

Regra: toda `<img>` aponta para `img/` (no servidor = `/img/`), e **a classe da `<img>` é o nome do arquivo sem extensão**.
Slots de personagem seguem o contrato:

```html
<div id="slot-mascote-<contexto>" class="gm-mascote gm-mascote--<variação>">
  <img class="gm-mascote__img mascote-principal" src="img/mascote-principal.png" alt="" loading="lazy" decoding="async">
</div>
```

| Slot | Arquivo | Variação | Onde |
|---|---|---|---|
| `#slot-mascote-principal` | `mascote-principal.png` (ex-`Logo4.png`) | `--topo` | Topo, à esquerda do letreiro |
| `#slot-mascote-secundario` | `mascote-secundario.png` (ex-`Logo3.png`) | `--topo --inclinado` | Topo, à direita (rotate −1°, herdado do `#logo3`) |
| `#slot-mascote-dica-produto` | `mascote-secundario.png` | `--dica` | Produto: balão de fala com a dica |
| `#slot-mascote-painel` | `mascote-principal.png` | `--painel` | Painel: a cabeça "fura" o filete rosa |
| `#slot-mascote-favoritos-vazio` | `mascote-secundario.png` | `--vazio` | Painel: estado vazio dos favoritos |

Trocar o personagem de um slot = trocar só o `src` (e a classe). Use PNG/SVG com fundo transparente e
recorte justo (sem margem transparente grande), senão o efeito de "sair do painel" fica menor.

Mapeamento completo (44 arquivos) legado → novo: `tools/migrar_imagens.py`. Nenhum arquivo precisa ser
criado à mão: o `favicon.png` sai do `Logo4.png`, e produto sem foto no painel usa o `mascote-secundario.png`.

**Lazy loading:** todas as imagens usam `loading="lazy"`, **exceto a foto principal do produto**
(`loading="eager"` + `fetchpriority="high"` + `<link rel="preload">`). Ela é o LCP da página; com lazy,
o navegador só a pediria depois do layout e o LCP pioraria.

> Os prints em `docs/prints/` usam imagens **provisórias** geradas para o teste (os arquivos de `imgs/` não
> vieram junto). Com as imagens originais em `img/`, o layout é o mesmo.

**WebP (recomendado):** `cwebp -q 82 in.png -o out.webp` reduz ~60–80% dos PNGs. Ao converter, troque o
`src` para `.webp` (não usei `<picture>` com fallback para não quebrar se o `.webp` não existir).

### Atributos de dados

| Atributo | Quem lê | Efeito |
|---|---|---|
| `body[data-product-id]` | tracker | Atribui page view e tempo de tela ao produto |
| `data-track="<ação>"` | tracker | `favorite_add`, `favorite_remove`, `add_to_cart`, `begin_checkout`, `buy_now` (→ `begin_checkout`); qualquer outro valor → evento `click` com `props.target` |
| `data-track-<chave>="<valor>"` | tracker | Vira `props.<chave>` (ex.: `data-track-origem="relacionados"`); até 8 chaves `[a-z_]` |
| `data-product-id` (no botão) | tracker + ui | Produto do evento / da ação |
| `data-gm-favorito` | ui | Botão de favorito (POST/DELETE `/api/v1/favorites/{id}`, otimista, `aria-pressed`) |
| `data-gm-carrinho` / `data-gm-comprar` | ui | Adiciona ao `localStorage['cart']` (formato do `compra.js`) / adiciona e vai ao carrinho |
| `data-nome`, `data-preco`, `data-img` | ui | Exibição no carrinho (**o preço real é recalculado pela API no pedido**) |
| `data-gm-qtd` + `data-gm-qtd-passo` | ui | Stepper 1–10 (limitado pelo `max` = estoque) |
| `data-gm-usa-qtd` | ui | Recebe `data-track-qty` com a quantidade escolhida |
| `data-gm-bind`, `data-gm-sample`, `data-gm-fallback` | ui | Hidratação do painel (ver comentário no `dashboard.html`) |
| `data-gm-busca-item` / `-secao` / `-ocultar` | ui | Card filtrável / seção que some se ficar vazia / bloco escondido durante a busca (carrossel) |
| `body[data-gm-pagina="carrinho"]` | ui | Página do carrinho: lista o `localStorage['cart']`, `data-gm-item-passo`/`data-gm-item-remover` por item, `data-gm-carrinho-esvaziar` (2 cliques), `data-gm-finalizar` → `POST /api/v1/orders` |
| `select[data-gm-ordenar="#lista"]` | ui | Ordena a vitrine sem recarregar (`relevancia`, `preco-asc`, `preco-desc`, `nome-asc`, `nome-desc`) e grava em `?ordem=`; itens `[data-gm-ordenar-item][data-ordem-preco][data-ordem-nome]`; `[data-gm-ordenar-caixa]` aparece só com JS; `[data-gm-ordenar-contagem="#lista"]` + `data-singular`/`data-plural` mostra a contagem |
| `[data-gm-filtrar="#lista"]` | ui | Abas de tipo da vitrine (hardware.html…): botões `[data-gm-filtro="todos"\|"<tipo>"]` com `aria-pressed` e `[data-gm-filtro-qtd]` (quantidade preenchida pelo JS); itens com `[data-gm-tipo]`; esconde com `hidden`, grava em `?tipo=` (só aceita valores de botões existentes) e soma o rótulo da aba à contagem do `[data-gm-ordenar-contagem]` |
| `[data-gm-faq-busca="#lista"]` | ui | Busca nas perguntas frequentes (suporte.html): itens `[data-gm-faq-item]` (accordion-item com id `faq-<assunto>`) dentro de `[data-gm-faq-grupo]`; status `[data-gm-faq-status]`, estado vazio `[data-gm-faq-vazio]`, atalhos `[data-gm-faq-atalhos]`; busca sem acento só com `hidden`/`textContent`; `#faq-<id>` na URL abre a resposta (só ids existentes) |
| `body[data-gm-pagina="404"]` | ui | Página não encontrada (404.html): mostra o endereço procurado em `[data-gm-404-endereco]` (só `textContent`), botão `[data-gm-voltar]` só quando a visita veio do próprio site e âncoras `#…` funcionando mesmo com o `<base href="/">` que o servidor insere em rotas aninhadas |
| `data-gm-usuario` | ui | Link da conta: vira "Olá, <nome>" quando logado |
| `form[role="search"]` | tracker | Registra o termo buscado (máx. 80 caracteres) |

### Configuração do tracker (opcional)

Como a CSP proíbe script inline, defina num arquivo próprio carregado **antes** do `gm-tracker.js`:

```js
// /js/gm-tracker-config.js
window.GM_TRACKER_CONFIG = { debug: true, heartbeatMs: 15000, flushMs: 10000, idleMs: 60000 };
```

API pública: `GMTracker.track(tipo, props, productId)`, `setConsent(bool)`, `hasConsent()`, `flush()`, `history()`.

---

## 3. Produção

| Item | Recomendação |
|---|---|
| Servidor | `uvicorn app.main:app --workers 4 --proxy-headers --forwarded-allow-ips=<IP do Nginx>` com `GM_SERVE_FRONTEND=false` |
| Nginx | Servir `/img`, `/css`, `/js` com `Cache-Control: public, max-age=31536000, immutable` (versione os arquivos) e `client_max_body_size 64k` em `/api/v1/track` |
| Página 404 | `error_page 404 /404.html;` + `location = /404.html { internal; sub_filter '<head>' '<head><base href="/">'; sub_filter_once on; }` (o `<base>` mantém CSS/imagens em rotas aninhadas; mesmo comportamento do `backend/app/frontend.py` em dev). Rotas `/api/...` inexistentes continuam 404 em JSON |
| HTTPS | Obrigatório: `GM_COOKIE_SECURE=true` (cookies `__Host-`, HSTS) |
| Banco | Rodar a API com a role `gamemania_app` e o pool de telemetria com `gamemania_analytics` (menor privilégio; ver `analytics.sql`); BI lê só as views com `gamemania_bi` |
| pg_cron | Criar partições do mês seguinte e `REFRESH MATERIALIZED VIEW CONCURRENTLY mv_user_interest` a cada 15 min (comandos comentados no `analytics.sql`) |
| Escala do tracking | A fila é por processo: com vários workers/servidores, troque a `asyncio.Queue` por Redis Streams ou Kafka mantendo a interface `offer()` |
| Migrações | Alembic em vez de `init_db.py` |
| Rate limit | O `slowapi` usa memória local; com vários servidores, configure storage Redis |

---

## 4. Segurança e LGPD (resumo)

| Ameaça | Defesa |
|---|---|
| Vazamento do banco | E-mail em AES-256-GCM (chave fora do banco, rotação por `key_id`); senha em Argon2id (m=64 MiB, t=3); IP pseudonimizado |
| XSS | CSP sem `unsafe-inline`; dados da API só via `textContent`/`<template>`; validação Pydantic (`extra=forbid`) |
| CSRF | Cookie SameSite + checagem de Origin + token double-submit `__Host-gm_csrf` |
| SQL injection | Somente ORM/Core com parâmetros vinculados; IDs tipados no path |
| Fraude de preço | Preço e total sempre calculados no servidor (`SELECT … FOR UPDATE`) |
| Eventos forjados | `user_id` vem do cookie assinado; `purchase` só é emitido pelo servidor |
| Força bruta / enumeração | Rate limit + bloqueio após 10 falhas/15 min; resposta idêntica para e-mail inexistente |
| Privacidade | Telemetria opt-in (`gm_consent`), GPC respeitado, revogação apaga IDs locais, query string nunca é enviada |

---

## 5. Testes

```bash
bash scripts/testar_tudo.sh
```

Um comando, ~2 minutos, em Linux (ou WSL): cria um PostgreSQL **descartável** (`gamemania_teste`),
configura a API só por variáveis de ambiente (seu `backend/.env` não é lido nem alterado), sobe o servidor e roda:

| Suíte | O que cobre |
|---|---|
| `tests/test_estatico.py` | Paleta congelada, Bootstrap 5.3.8 com SRI, CSP (sem estilo/script inline), imagens (`img/`, classe, lazy, `data-gm-legado`, nomes exatos), slots de mascote, rodapé idêntico, JS sem `innerHTML` |
| `tests/e2e_frontend.py` | Chromium real: cores, carrinho, favoritos, busca, funil gravado no banco, painel, LGPD, celular, duplo clique (`file://`) e **varredura de todas as páginas** de `frontend/` |
| `tests/test_api.py` | Criptografia, CSRF, enumeração de usuário, preço do servidor, estoque, tracking |

A última linha resume: `RESULTADO: estático 84/84 · E2E 74/74 · API 38/38 · TUDO OK`. Prints em `/tmp/gm-testes/prints/`.
O mesmo script roda no GitHub Actions a cada push em `main` e `desenvolvimento` (quando o repositório existir).

---

## 6. Automação (rotina noturna)

Todo dia às **22:50 (Brasília)** uma tarefa agendada do Claude:

1. baixa o código salvo na nuvem do Claude (Projeto GameMania_2.0 → `claude/gamemania-2.0/pacote.md`) e recria o projeto, com `legado/` e imagens reais;
2. pega o primeiro item `[ ]` do `docs/ROADMAP.md` e implementa seguindo o `CLAUDE.md`;
3. roda `scripts/testar_tudo.sh` e olha os prints;
4. **só com tudo verde**: atualiza ROADMAP e CHANGELOG, salva a versão nova no Projeto (a anterior vira `pacote-anterior.md`) e te manda o resumo + o site pronto em zip;
5. se algo falhar e não der para corrigir, **não salva nada** e explica o que falhou — a versão boa continua intacta.

Para mudar a prioridade, edite o `docs/ROADMAP.md` (ou peça na conversa do Projeto).
Quando o repositório no GitHub existir, a rotina passa a trabalhar nele (branch `desenvolvimento` + PR para a `main`).
