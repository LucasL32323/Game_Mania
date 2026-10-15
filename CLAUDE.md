# GameMania 2.0 — regras do projeto

Lido por qualquer pessoa ou IA que mexa neste repositório (inclusive a rotina noturna).
Responda e comente em **português do Brasil**. Dono do projeto: Lucas (LucasL32323).

## Estrutura

| Pasta | O que é |
|---|---|
| `frontend/` | Site novo: `*.html`, `css/gamemania.css`, `js/gm-ui.js`, `js/gm-tracker.js`, `img/` |
| `backend/` | API FastAPI + SQLAlchemy async + PostgreSQL (criptografia, tracking, pedidos) |
| `legado/` | Site original (snapshot do repositório `12172025GameMania`). **Somente leitura**: fonte de textos, preços e imagens para migrar páginas |
| `tests/` | `test_estatico.py` (regras fixas), `e2e_frontend.py` (Chromium), `test_api.py` (API) |
| `tools/` | `migrar_imagens.py` / `.bat` — copia `legado/imgs` → `frontend/img` com nomes semânticos · `atualizar_bootstrap.py` — troca a versão do Bootstrap + SRI em tudo |
| `docs/ROADMAP.md` | Backlog priorizado. A rotina noturna faz **um item por noite** |

## Regras que não se negociam (o `tests/test_estatico.py` verifica)

1. **Paleta congelada.** Cores só via `var(--gm-*)` do `:root` do `gamemania.css`. Proibido criar ou alterar hexadecimais.
2. **Bootstrap 5.3.8** (CSS e JS) com os mesmos `integrity` (SRI) das páginas atuais — versão e hashes ficam num só lugar (`BS_VERSAO`, `SRI_CSS`, `SRI_JS` em `tests/test_estatico.py`); para atualizar use `python tools/atualizar_bootstrap.py <versão>`; `css/gamemania.css` carregado **depois** dele.
3. **CSP sem `unsafe-inline`**: nenhum `style=""`, `<style>`, `onclick=""` ou `<script>` inline (só `application/ld+json`). CSS novo vai no `gamemania.css`, numa seção numerada e comentada.
4. **Caminhos relativos** (`css/`, `js/`, `img/`, `pagina.html`) — o site precisa abrir com duplo clique, Live Server e pelo FastAPI.
5. **Imagens**: toda `<img>` aponta para `img/<nome-semântico>`, a **classe** contém o nome do arquivo sem extensão, tem `width`, `height`, `alt` e `loading="lazy"` (única exceção: a foto principal de página de produto, com `loading="eager" fetchpriority="high"` + `<link rel="preload">`). Imagem vinda do site original exige:
   - entrada no `MAPA` de `tools/migrar_imagens.py` com o nome **exato** do arquivo em `legado/imgs` (maiúsculas contam);
   - o arquivo copiado em `frontend/img/` (rode `python tools/migrar_imagens.py legado/imgs frontend/img`);
   - `data-gm-legado="imgs/<nome-original>"` na `<img>` (plano B quando o usuário ainda não migrou) — depois de mudar o MAPA, regenere o `.bat` (`tools/migrar_imagens.bat`) com as mesmas linhas `call :copiar`.
6. **Personagens**: o topo sempre tem `#slot-mascote-principal` e `#slot-mascote-secundario`. Áreas novas de mascote seguem `<div id="slot-mascote-<contexto>" class="gm-mascote gm-mascote--<variação>">`.
7. **Topo, menu e rodapé idênticos** ao `frontend/index.html` (copie o bloco inteiro). Só muda o `aria-current` do menu: `"page"` na página do item, `"true"` na seção (ex.: produto de computador → Computadores). O rodapé tem que ser byte a byte igual.
8. **Anti-XSS**: dado vindo da API ou do `localStorage` só entra no DOM por `textContent`/`setAttribute` validado, clonando `<template>`. Proibido `innerHTML`, `insertAdjacentHTML`, `document.write`, `eval`.
9. **1 `<h1>` por página**, `meta description` real (≥ 50 caracteres), `lang="pt-BR"`, `data-bs-theme="dark"`, link "Pular para o conteúdo" + `<main id="conteudo">`.
10. **Back-end**: preço sempre do banco, `user_id` sempre do cookie de sessão, nada de SQL concatenado, Pydantic `extra="forbid"`, segredos só por variável de ambiente. Nunca versione `.env`.

## Padrões

- Página de produto nova = cópia da estrutura de `frontend/produto.html`, com o conteúdo do arquivo equivalente em `legado/` (nome, specs, preço, textos). `body[data-product-id]` = id do produto em `backend/sql/seed_products.sql`; se o produto não existir lá, adicione-o (e o `page_path`).
- Cards de vitrine seguem o markup de `frontend/index.html` (`.gm-card-produto`, botão `Mais Informações` + `.btn-gm-add`).
- Botões de ação usam `data-track` (ver README → Atributos de dados) para o funil do tracker.
- Mobile-first: conferir em 390 px (sem scroll horizontal) e em 1366 px.

## Como testar

```bash
bash scripts/testar_tudo.sh      # ~2 min: estático + E2E (Chromium) + API, tudo em banco descartável
```

Só considere pronto com `RESULTADO: ... TUDO OK`. Os prints ficam em `/tmp/gm-testes/prints/` — **abra e olhe** os das páginas que você mudou. Funcionalidade nova pede teste novo: E2E para comportamento de página, `test_api.py` para rota nova. A varredura do E2E já confere automaticamente toda página de `frontend/` (HTTP 200, imagens, JS, CSP, celular).

## Onde o código fica

Por enquanto **na nuvem do Claude**, no Projeto "GameMania_2.0":

| Documento do Projeto | Conteúdo |
|---|---|
| `claude/gamemania-2.0/pacote.md` | Versão atual: todo o código (texto) num único documento, com SHA-256 por arquivo |
| `claude/gamemania-2.0/pacote-anterior.md` | Versão da noite anterior (para voltar atrás) |
| `claude/gamemania-2.0/LEIA-ME.md` | Como baixar e usar |

`legado/` e as imagens não vão no pacote: `python tools/pacote_nuvem.py imagens <raiz>` baixa o site original
do repositório público `LucasL32323/12172025GameMania` e migra as imagens para `frontend/img/`.

```bash
python tools/pacote_nuvem.py desempacotar pacote.md gamemania-2.0/   # recria o projeto
python tools/pacote_nuvem.py imagens gamemania-2.0/                   # legado/ + frontend/img/
python tools/pacote_nuvem.py empacotar gamemania-2.0/ pacote.md       # depois de mudar
```

Quando o repositório `LucasL32323/GameMania-2.0` existir no GitHub, o código passa a viver lá
(`main` = estável, só o Lucas faz merge; `desenvolvimento` = rotina noturna).
