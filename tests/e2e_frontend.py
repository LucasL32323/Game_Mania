"""
E2E do front-end real (Chromium/Playwright) contra a API FastAPI + PostgreSQL. 70+ verificações
(a varredura 10b cresce sozinha: 1 verificação por página em frontend/):
cores da marca, lazy loading, classes semânticas, CSP, consentimento, funil gravado no banco,
favoritos, carrinho legado, busca, dashboard hidratado, revogação LGPD e layout mobile.

Pré-requisitos
  pip install playwright "psycopg[binary]" && playwright install chromium
  API rodando em GM_E2E_BASE (padrão http://localhost:8000) servindo o front-end com as imagens em /img
  Assets offline (opcional, se o CDN estiver bloqueado): npm i bootstrap@5.3.8 @fontsource/rajdhani @fontsource/comic-neue
  → aponte GM_E2E_NODE_MODULES para essa pasta node_modules.
Obs.: o limite de cadastro é 5/min por IP — aguarde 1 min entre execuções seguidas.
"""
import asyncio, json, os, re, time
import psycopg
from playwright.async_api import async_playwright

BASE = os.environ.get("GM_E2E_BASE", "http://localhost:8000")
NM = os.environ.get("GM_E2E_NODE_MODULES", "./node_modules")
SHOTS = os.environ.get("GM_E2E_SHOTS", "./prints")
DSN = os.environ.get("GM_TEST_DSN", "host=localhost dbname=gamemania user=gm_owner password=devpass")
os.makedirs(SHOTS, exist_ok=True)
FONT_CSS = """
@font-face{font-family:'Rajdhani';font-weight:500;font-display:swap;src:url(https://fonts.gstatic.com/local/rajdhani-latin-500-normal.woff2) format('woff2')}
@font-face{font-family:'Rajdhani';font-weight:600;font-display:swap;src:url(https://fonts.gstatic.com/local/rajdhani-latin-600-normal.woff2) format('woff2')}
@font-face{font-family:'Rajdhani';font-weight:700;font-display:swap;src:url(https://fonts.gstatic.com/local/rajdhani-latin-700-normal.woff2) format('woff2')}
@font-face{font-family:'Comic Neue';font-weight:700;font-display:swap;src:url(https://fonts.gstatic.com/local/comic-neue-latin-700-normal.woff2) format('woff2')}
"""
results = []
def ok(cond, msg):
    results.append((bool(cond), msg)); print(("PASS " if cond else "FAIL ") + msg)

def db(sql, *a):
    with psycopg.connect(DSN) as c:
        return c.execute(sql, a).fetchall()

async def route_cdn(route):
    url = route.request.url
    hdr = {"Access-Control-Allow-Origin": "*"}
    if url.endswith("bootstrap.min.css"):
        return await route.fulfill(path=f"{NM}/bootstrap/dist/css/bootstrap.min.css", content_type="text/css", headers=hdr)
    if url.endswith("bootstrap.bundle.min.js"):
        return await route.fulfill(path=f"{NM}/bootstrap/dist/js/bootstrap.bundle.min.js", content_type="application/javascript", headers=hdr)
    if "fonts.googleapis.com" in url:
        return await route.fulfill(body=FONT_CSS, content_type="text/css", headers=hdr)
    if "fonts.gstatic.com/local/" in url:
        name = url.rsplit("/", 1)[1]
        pkg = "rajdhani" if name.startswith("rajdhani") else "comic-neue"
        return await route.fulfill(path=f"{NM}/@fontsource/{pkg}/files/{name}", content_type="font/woff2", headers=hdr)
    await route.abort()

async def new_context(browser, **kw):
    ctx = await browser.new_context(**kw)
    if os.path.isdir(NM):  # modo offline: serve Bootstrap/fontes locais no lugar do CDN (mesmos bytes → SRI confere)
        await ctx.route(
            re.compile(r"https://(cdn\.jsdelivr\.net|fonts\.googleapis\.com|fonts\.gstatic\.com)/.*"), route_cdn)
    # Config de teste: intervalos curtos (init script roda fora da CSP da página)
    await ctx.add_init_script("window.GM_TRACKER_CONFIG = {flushMs: 1500, heartbeatMs: 2000};")
    return ctx

async def main():
    console_errors, track_posts = [], []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await new_context(browser, viewport={"width": 1366, "height": 900}, locale="pt-BR")
        page = await ctx.new_page()
        page.on("console", lambda m: m.type in ("error", "warning") and console_errors.append(m.text))
        page.on("pageerror", lambda e: console_errors.append(str(e)))
        page.on("request", lambda r: r.url.endswith("/api/v1/track") and track_posts.append(r))

        # ---------- 1. Produto: sem consentimento nada é enviado ----------
        await page.goto(f"{BASE}/produto.html", wait_until="load")
        await page.wait_for_timeout(2500)
        ok(await page.is_visible("#gm-consentimento"), "banner LGPD visível sem decisão prévia")
        ok(len(track_posts) == 0, f"sem consentimento: 0 POST /track (obtido {len(track_posts)})")
        ok(await page.evaluate("getComputedStyle(document.querySelector('.gm-marca')).color") == "rgb(255, 0, 79)", "letreiro em #ff004f")
        ok(await page.evaluate("getComputedStyle(document.querySelector('.gm-topo')).backgroundColor") == "rgb(33, 37, 41)", "topo no grafite do site atual (#212529)")
        ok(await page.evaluate("getComputedStyle(document.querySelector('.gm-nav')).backgroundColor") == "rgb(33, 37, 41)", "menu no mesmo bloco do topo (#212529)")
        ok(await page.evaluate("getComputedStyle(document.querySelector('.gm-preco__valor')).color") == "rgb(0, 255, 153)", "preço em #00ff99")
        ok(await page.evaluate("document.fonts.check('700 16px Rajdhani')"), "Rajdhani carregada")
        imgs = await page.evaluate("""[...document.images].map(i => ({src: i.getAttribute('src'), abs: new URL(i.src).pathname, cls: i.className, lazy: i.loading, fp: i.getAttribute('fetchpriority')}))""")
        ok(all(i["src"].startswith("img/") and i["abs"].startswith("/img/") for i in imgs), f"todas as {len(imgs)} <img> em img/ (resolvem para /img/ no servidor)")
        eager = [i for i in imgs if i["lazy"] != "lazy"]
        ok(len(eager) == 1 and eager[0]["fp"] == "high", f"lazy em {len(imgs)-len(eager)}/{len(imgs)}; exceção única = LCP ({eager[0]['src'] if eager else '-'})")
        stem = lambda s: s.rsplit('/', 1)[1].rsplit('.', 1)[0]
        ok(all(stem(i["src"]) in i["cls"].split() for i in imgs), "classe de cada <img> = nome semântico do arquivo")
        styled = await page.evaluate("[...document.querySelectorAll('[style]')].map(e => e.tagName + ' ' + e.getAttribute('style'))")
        ok(not styled, f"zero atributos style inline no DOM {styled}")
        ok(await page.evaluate("document.querySelectorAll('h1').length") == 1, "exatamente 1 <h1>")
        ld = await page.evaluate("JSON.parse(document.querySelector('script[type=\"application/ld+json\"]').textContent)")
        ok(ld["@graph"][0]["offers"]["price"] == "3799.00", "JSON-LD Product válido (3799.00 BRL)")
        await page.screenshot(path=f"{SHOTS}/produto-desktop.png", full_page=True)

        # ---------- 2. Aceitar → page_view gravado ----------
        await page.click("[data-gm-consent=aceitar]")
        ok(not await page.is_visible("#gm-consentimento"), "banner some após aceitar")
        await page.wait_for_timeout(3000)
        ok(len(track_posts) >= 1, f"POST /track disparado após consentimento ({len(track_posts)})")
        ok(track_posts[0].headers.get("x-csrf-token"), "header X-CSRF-Token presente")
        body = json.loads(track_posts[0].post_data)
        ok("user_id" not in json.dumps(body), "payload do tracker sem user_id")
        sess = body["session_id"]
        pv = db("select path, product_id from page_views where session_id=%s", sess)
        ok(pv and pv[0] == ("/produto.html", 4), f"page_view no Postgres com product_id=4: {pv}")

        # ---------- 3. Quantidade + carrinho ----------
        await page.click("[data-gm-qtd-passo='1']")
        await page.click("[data-gm-carrinho][data-product-id='4']")
        await page.wait_for_timeout(600)
        cart = await page.evaluate("JSON.parse(localStorage.getItem('cart'))")
        ok(cart == [{"id": 4, "title": "PC Gamer Ryzen 5 5600G", "price": 3799, "img": "img/produto-pc-gamer-ryzen5-5600g.png", "qty": 2}], f"carrinho no formato legado: {cart}")
        ok(await page.text_content("[data-gm-carrinho-contador]") == "2", "contador do carrinho = 2")
        ok(await page.is_visible(".gm-toast"), "toast exibido")

        # ---------- 4. Scroll + tempo ativo ----------
        for _ in range(6):
            await page.mouse.wheel(0, 700); await page.wait_for_timeout(400)
        await page.wait_for_timeout(2500)

        # ---------- 5. Favorito sem login → redireciona ----------
        async with page.expect_navigation():
            await page.click("[data-gm-favorito]")
        ok("/entreoucadastrese.html?next=%2Fproduto.html" in page.url, f"favoritar deslogado → login com next ({page.url.replace(BASE,'')})")
        await page.wait_for_timeout(3000)   # janela de lote do worker = 2 s
        ev = dict(db("select event_type, count(*) from analytics_events where session_id=%s group by 1", sess))
        ok(ev.get("add_to_cart") == 1 and ev.get("favorite_add") == 1, f"eventos de funil gravados: {ev}")
        props = db("select props from analytics_events where session_id=%s and event_type='add_to_cart'", sess)
        ok(props and props[0][0].get("qty") == 2, f"props do add_to_cart: {props[0][0] if props else None}")
        eng = db("select active_seconds, max_scroll_pct from page_views where session_id=%s and path='/produto.html'", sess)
        ok(eng and eng[0][0] >= 5 and eng[0][1] == 100, f"engajamento: {eng[0][0]}s ativos, scroll {eng[0][1]}%")

        # ---------- 6. Login (API) → favoritar de verdade ----------
        await page.goto(f"{BASE}/produto.html", wait_until="load")
        reg = await page.evaluate("""GMUI.apiFetch('/auth/register', {method:'POST', body:{name:'Lucas Teste', email:'lucas@gamemania.com.br', password:'senhaSuperForte1'}})""")
        ok(reg["email"] == "lucas@gamemania.com.br", "cadastro via apiFetch (CSRF automático)")
        await page.reload(wait_until="load")
        await page.click("[data-gm-favorito]")
        await page.wait_for_timeout(800)
        ok(await page.get_attribute("[data-gm-favorito]", "aria-pressed") == "true", "favorito: aria-pressed=true")
        ok(await page.get_attribute("[data-gm-favorito]", "data-track") == "favorite_remove", "data-track alterna para favorite_remove")
        fav = db("select count(*) from favorites f join users u on u.id=f.user_id where f.product_id=4")
        ok(fav[0][0] == 1, "favorito gravado na tabela favorites")
        await page.reload(wait_until="load"); await page.wait_for_timeout(500)
        ok(await page.get_attribute("[data-gm-favorito]", "aria-pressed") == "true", "estado do favorito restaurado após reload (GET /favorites)")
        await page.screenshot(path=f"{SHOTS}/produto-favoritado.png")

        # ---------- 7. Pedido + busca ----------
        order = await page.evaluate("""GMUI.apiFetch('/orders', {method:'POST', body:{items:[{product_id:4, quantity:1},{product_id:22, quantity:2}], payment_method:'pix'}})""")
        ok(order["total"] in ("3977.00", "3977.0", 3977), f"pedido criado com preço do servidor: {order['total']}")
        await page.fill("#gm-busca-q", "rtx 3060")
        await page.press("#gm-busca-q", "Enter")
        await page.wait_for_timeout(3000)   # janela de lote do worker = 2 s
        q = db("select props->>'q' from analytics_events where event_type='search'")
        ok(q and q[-1][0] == "rtx 3060", f"busca registrada: {q}")
        ok("/index.html?q=rtx+3060" in page.url, f"busca de outra página leva à vitrine ({page.url.replace(BASE,'')})")
        vis = await page.evaluate("[...document.querySelectorAll('[data-gm-busca-item]')].filter(e => !e.hidden).map(e => e.querySelector('.gm-card-produto__nome').textContent)")
        ok(vis == ["PC Gamer RTX 3060"], f"vitrine filtrada pelo ?q=: {vis}")

        # ---------- 8. Dashboard hidratado ----------
        await page.goto(f"{BASE}/dashboard.html", wait_until="load")
        await page.wait_for_timeout(2200)
        ok(await page.text_content("[data-gm-bind='user.name']") == "Lucas", "saudação com o nome real")
        ok(await page.evaluate("document.querySelectorAll('[data-gm-sample]').length") == 0, "dados de exemplo removidos")
        rows = await page.evaluate("[...document.querySelectorAll('#gm-pedidos-corpo tr')].map(r => r.innerText.replace(/\\s+/g,' '))")
        ok(len(rows) == 1 and "R$ 3.977,00" in rows[0], f"pedido na tabela: {rows}")
        ok(await page.text_content("[data-gm-bind='stats.favorites']") == "1", "stats: 1 favorito")
        favhref = await page.get_attribute("#gm-favoritos-lista a", "href")
        ok(favhref == "produto.html", f"favorito leva à página do produto (page_path do banco): {favhref}")
        favimg = await page.get_attribute("#gm-favoritos-lista img", "class")
        ok(favimg and "produto-pc-gamer-ryzen5-5600g" in favimg, f"favorito hidratado com classe semântica: {favimg}")
        ok(await page.evaluate("document.querySelector('#gm-consent-switch').checked"), "switch de privacidade reflete consentimento")
        acc = await page.evaluate("document.querySelectorAll('#gm-acessos-lista li').length")
        ok(acc >= 1, f"histórico de acessos: {acc} registro(s)")
        await page.screenshot(path=f"{SHOTS}/dashboard-real-desktop.png", full_page=True)

        # XSS: nome malicioso não vira HTML (registro rejeita <>, mas testa o render mesmo assim)
        injected = await page.evaluate("""(() => { const f = document.getElementById('tpl-acesso').content.cloneNode(true);
            f.querySelector('[data-campo=device]').textContent = '<img src=x onerror=alert(1)>'; const ul=document.createElement('ul'); ul.appendChild(f);
            return ul.querySelector('img') === null; })()""")
        ok(injected, "templates + textContent: payload XSS renderizado como texto")

        # ---------- 9. Revogar consentimento ----------
        await page.click("#gm-consent-switch")
        await page.wait_for_timeout(300)
        left = await page.evaluate("['gm_sess','gm_vid','gm_trail','gm_q'].filter(k => localStorage.getItem(k) !== null)")
        ok(left == [], f"revogação apaga identificadores locais (restantes: {left})")
        n_before = len(track_posts)
        await page.mouse.wheel(0, 500); await page.wait_for_timeout(3000)
        ok(len(track_posts) == n_before, "após revogar: nenhum novo POST /track")

        # ---------- 9b. Home (vitrine) ----------
        await page.goto(f"{BASE}/index.html", wait_until="load"); await page.wait_for_timeout(1500)
        ok(await page.evaluate("document.querySelectorAll('[data-gm-busca-item]').length") == 20, "home: 20 produtos na vitrine")
        ok(await page.evaluate("document.querySelectorAll('#gm-carrossel .carousel-item').length") == 5, "home: carrossel com 5 banners")
        ok(await page.text_content("[data-gm-usuario] .gm-nav__rotulo") == "Olá, Lucas", "menu mostra o usuário logado")
        await page.fill("#gm-busca-q", "ryzen"); await page.wait_for_timeout(400)
        vis = await page.evaluate("[...document.querySelectorAll('[data-gm-busca-item]')].filter(e => !e.hidden).length")
        ok(vis == 3, f"busca ao digitar 'ryzen': {vis} cards (Ryzen 9, Ryzen 5, Nitro X/Ryzen 7)")
        ok(await page.evaluate("document.querySelector('[data-gm-busca-ocultar]').hidden"), "carrossel some durante a busca")
        ok("3 resultados" in (await page.text_content("#gm-busca-status")), "status da busca anunciado (role=status)")
        await page.fill("#gm-busca-q", ""); await page.wait_for_timeout(400)
        ok(await page.evaluate("[...document.querySelectorAll('[data-gm-busca-item]')].filter(e => !e.hidden).length") == 20, "limpar busca restaura a vitrine")
        for _ in range(12):
            await page.mouse.wheel(0, 900); await page.wait_for_timeout(150)
        await page.wait_for_timeout(800)
        ok(await page.evaluate("document.querySelectorAll('.gm-img--ausente').length") == 0, "home: nenhuma imagem ausente (mapa de migração cobre todas)")
        await page.evaluate("window.scrollTo(0,0)"); await page.wait_for_timeout(300)
        await page.screenshot(path=f"{SHOTS}/home-desktop.png", full_page=True)
        async with page.expect_navigation():
            await page.click("[data-gm-comprar][data-product-id='52']")
        ok(page.url.endswith("/carrinho.html"), "'Comprar' em produto sem página → carrinho")
        cart = await page.evaluate("JSON.parse(localStorage.getItem('cart')).map(i => i.id)")
        ok(52 in cart, f"PlayStation 5 no carrinho legado: {cart}")

        # ---------- 9c. Carrinho (carrinho.html) — logado ----------
        brl_txt = lambda sel: page.evaluate("s => document.querySelector(s).textContent.replace(/\\u00a0/g, ' ')", sel)
        await page.wait_for_timeout(600)
        nomes = await page.evaluate("[...document.querySelectorAll('#gm-carrinho-lista .gm-carrinho-item__nome')].map(e => e.textContent)")
        ok(nomes == ["PC Gamer Ryzen 5 5600G", "PlayStation 5"], f"carrinho lista os itens do localStorage: {nomes}")
        ok(await brl_txt("[data-gm-carrinho-total]") == "R$ 12.097,00", f"total = 2×3.799 + 4.499 ({await brl_txt('[data-gm-carrinho-total]')})")
        ok(await page.is_visible("#gm-carrinho-cheio") and not await page.is_visible("#gm-carrinho-vazio"), "estado 'com itens' visível")
        cimgs = await page.evaluate("[...document.querySelectorAll('#gm-carrinho-lista img')].map(i => ({cls: i.className, src: i.getAttribute('src'), w: i.naturalWidth}))")
        ok(cimgs and all(stem(i["src"]) in i["cls"].split() and i["src"].startswith("img/") and i["w"] > 0 for i in cimgs),
           f"fotos do carrinho em img/, carregadas, classe = nome do arquivo: {[i['cls'] for i in cimgs]}")
        await page.screenshot(path=f"{SHOTS}/carrinho-desktop.png", full_page=True)
        item4 = "#gm-carrinho-lista [data-id='4']"
        await page.click(f"{item4} [data-gm-item-passo='1']")
        await page.wait_for_timeout(200)
        q = await page.evaluate("JSON.parse(localStorage.getItem('cart')).find(i => i.id === 4).qty")
        ok(q == 3 and await brl_txt(f"{item4} [data-campo=subtotal]") == "R$ 11.397,00", f"+ aumenta a quantidade e o subtotal (qty={q})")
        ok(await page.text_content("[data-gm-carrinho-contador]") == "4", "contador do topo acompanha o carrinho (4)")
        await page.fill(f"{item4} input", "15"); await page.dispatch_event(f"{item4} input", "change")
        await page.wait_for_timeout(200)
        ok(await page.input_value(f"{item4} input") == "10", "quantidade limitada a 10 (igual à API)")
        ok("de 1 a 10" in (await page.text_content("#gm-carrinho-status")), "limite anunciado ao leitor de tela (role=status)")
        await page.fill(f"{item4} input", "1"); await page.dispatch_event(f"{item4} input", "change")
        await page.click("#gm-carrinho-lista [data-id='52'] [data-gm-item-remover]")
        await page.wait_for_timeout(200)
        cart = await page.evaluate("JSON.parse(localStorage.getItem('cart'))")
        ok([(i["id"], i["qty"]) for i in cart] == [(4, 1)], f"remover tira o item do localStorage: {cart}")
        ok(await page.evaluate("document.activeElement.matches('[data-gm-item-remover]')"), "foco vai para o próximo item após remover")
        # XSS: título e imagem maliciosos no localStorage viram texto / imagem padrão
        await page.evaluate("""localStorage.setItem('cart', JSON.stringify([...JSON.parse(localStorage.getItem('cart')),
            {id: 21, title: '<img src=x onerror=alert(1)>', price: 1, img: 'javascript:alert(1)', qty: 1},
            {id: -5, title: 'inválido', price: 1, qty: 1}]))""")
        await page.reload(wait_until="load"); await page.wait_for_timeout(500)
        x = await page.evaluate("""(() => { const li = document.querySelector("#gm-carrinho-lista [data-id='21']");
            return {txt: li.querySelector('[data-campo=title]').textContent, imgs: li.querySelectorAll('img').length,
                    src: li.querySelector('img').getAttribute('src'), n: document.querySelectorAll('#gm-carrinho-lista li').length}; })()""")
        ok(x == {"txt": "<img src=x onerror=alert(1)>", "imgs": 1, "src": "img/mascote-secundario.png", "n": 2},
           f"carrinho: payload XSS vira texto, img inválida vira mascote, id inválido descartado: {x}")
        await page.click("#gm-carrinho-lista [data-id='21'] [data-gm-item-remover]")
        # Esvaziar pede confirmação (1º clique não apaga)
        await page.click("[data-gm-carrinho-esvaziar]")
        ok(len(await page.evaluate("JSON.parse(localStorage.getItem('cart'))")) == 1, "esvaziar: 1º clique só pede confirmação")
        await page.wait_for_timeout(4300)   # confirmação expira em 4 s
        ok(await page.text_content("[data-gm-carrinho-esvaziar]") == "Esvaziar carrinho", "confirmação de esvaziar expira sozinha")
        # Finalizar logado → pedido no banco com preço do servidor
        await page.check("#gm-pagamento-boleto")
        await page.click("[data-gm-finalizar]")
        await page.wait_for_selector("#gm-carrinho-sucesso:not([hidden])", timeout=5000)
        codigo = await page.text_content("[data-gm-pedido-codigo]")
        ok(re.fullmatch(r"GM-[0-9A-F]{8}", codigo or ""), f"pedido confirmado com código {codigo}")
        ped = db("select o.total, o.payment_method::text, sum(i.quantity) from orders o join order_items i on i.order_id=o.id "
                 "group by o.id order by o.id desc limit 1")
        ok(ped and float(ped[0][0]) == 3799.0 and ped[0][1].lower() == "boleto" and ped[0][2] == 1, f"pedido gravado no Postgres: {ped}")
        ok(codigo == "GM-" + db("select replace(public_id::text,'-','') from orders order by id desc limit 1")[0][0][:8].upper(), "código igual ao do painel (GM- + UUID)")
        ok(await page.evaluate("JSON.parse(localStorage.getItem('cart'))") == [] and await page.text_content("[data-gm-carrinho-contador]") == "0",
           "carrinho limpo e contador zerado após o pedido")
        await page.screenshot(path=f"{SHOTS}/carrinho-sucesso-desktop.png", full_page=True)
        await page.reload(wait_until="load"); await page.wait_for_timeout(400)
        ok(await page.is_visible("#gm-carrinho-vazio") and await page.is_visible("#slot-mascote-carrinho-vazio img"), "carrinho vazio mostra o mascote")
        await page.screenshot(path=f"{SHOTS}/carrinho-vazio-desktop.png", full_page=True)

        # ---------- 9d. Entre ou cadastre-se (entreoucadastrese.html) — visitante ----------
        actx = await new_context(browser, viewport={"width": 1366, "height": 900}, locale="pt-BR")
        a = await actx.new_page()
        a.on("pageerror", lambda e: console_errors.append("entrar: " + str(e)))
        auth_posts = []
        a.on("request", lambda r: "/api/v1/auth/" in r.url and r.method == "POST" and auth_posts.append(r.url.rsplit("/", 1)[1]))
        # ?next= seguro: só caminho interno (testa o validador direto, sem gastar o limite de 5 logins/min)
        casos = {"/carrinho.html": True, "carrinho.html": True, "index.html?q=rtx+3060": True, "/pasta/produto.html": True,
                 "//evil.com": False, "https://evil.com": False, "javascript:alert(1)": False, "/\\evil.com": False,
                 "\\\\evil.com/x.html": False, "data:text/html,x.html": False, " /carrinho.html": False, "../x.html": False,
                 "/%2F%2Fevil.com": False, "entreoucadastrese.html": False, "http://localhost:8000/carrinho.html": False, "": False}
        await a.goto(f"{BASE}/entreoucadastrese.html", wait_until="load")
        got = await a.evaluate("cs => Object.fromEntries(cs.map(c => [c, GMUI.auth.destinoSeguro(c) === c]))", list(casos))
        ruins = {k: v for k, v in got.items() if v != casos[k]}
        ok(not ruins, f"?next=: aceita só caminho interno e bloqueia open redirect ({len(casos)} casos) {ruins or ''}")
        ok(not await a.is_visible("[data-gm-auth-continuar]"), "sem ?next=: aviso 'continuar' escondido")
        ok(await a.get_attribute("#aba-entrar", "aria-selected") == "true" and await a.is_visible("#entrar-email"), "abre na aba Entrar")
        ok(await a.get_attribute("[data-gm-usuario]", "aria-current") == "page", "menu: atalho 'Entre ou cadastre-se' marcado como página atual")
        ok(await a.evaluate("document.querySelector('.icone-entrar').naturalWidth > 0 && document.querySelector('.icone-cadastro').naturalWidth > 0"),
           "ícones originais de login/cadastro (loginperfil, cadastroimg) carregados de img/")
        await a.screenshot(path=f"{SHOTS}/entrar-desktop.png", full_page=True)
        # Abrir direto na aba de cadastro (links do site antigo) + validação no navegador
        await a.goto(f"{BASE}/entreoucadastrese.html?aba=cadastro&next=%2Fcarrinho.html", wait_until="load")
        await a.wait_for_timeout(400)
        ok(await a.is_visible("#cadastro-nome") and await a.get_attribute("#aba-cadastro", "aria-selected") == "true", "?aba=cadastro abre na aba Criar conta")
        ok(await a.is_visible("[data-gm-auth-continuar]"), "com ?next= válido: aviso 'você volta para a página em que estava'")
        await a.click("#painel-cadastro [data-gm-auth-enviar]")
        inval = await a.evaluate("[...document.querySelectorAll('#painel-cadastro .is-invalid')].map(e => e.id)")
        ok(inval == ["cadastro-nome", "cadastro-email", "cadastro-senha", "cadastro-confirmar"] and not auth_posts,
           f"cadastro vazio: 4 campos marcados e nada enviado à API ({inval}, POSTs {auth_posts})")
        ok(await a.evaluate("document.activeElement.id") == "cadastro-nome", "foco vai para o 1º campo inválido")
        await a.fill("#cadastro-nome", "Ana <b>")
        await a.fill("#cadastro-email", "ana@gamemania.com.br")
        await a.fill("#cadastro-senha", "curta")
        await a.fill("#cadastro-confirmar", "outra-coisa")
        await a.click("#painel-cadastro [data-gm-auth-enviar]")
        inval = await a.evaluate("[...document.querySelectorAll('#painel-cadastro .is-invalid')].map(e => e.id)")
        ok(inval == ["cadastro-nome", "cadastro-senha", "cadastro-confirmar"] and not auth_posts,
           f"nome com < >, senha < 10 e confirmação diferente são barrados ({inval})")
        ok(await a.is_visible("#cadastro-confirmar-erro") and "não conferem" in await a.text_content("#cadastro-confirmar-erro"), "mensagem 'As senhas não conferem' visível")
        await a.screenshot(path=f"{SHOTS}/entrar-cadastro-erros-desktop.png", full_page=True)
        await a.click("#painel-cadastro [data-gm-senha-ver]")
        ok(await a.get_attribute("#cadastro-senha", "type") == "text" and await a.get_attribute("#painel-cadastro [data-gm-senha-ver]", "aria-pressed") == "true",
           "botão Mostrar senha alterna o campo (aria-pressed)")
        # Cadastro duplicado: mensagem genérica (não confirma que o e-mail existe)
        await a.fill("#cadastro-nome", "Outra Pessoa")
        await a.fill("#cadastro-email", "lucas@gamemania.com.br")
        await a.fill("#cadastro-senha", "senhaForte123")
        await a.fill("#cadastro-confirmar", "senhaForte123")
        ok(await a.evaluate("document.querySelectorAll('#painel-cadastro .is-invalid').length") == 0, "campos corrigidos perdem a marca vermelha ao digitar")
        await a.click("#painel-cadastro [data-gm-auth-enviar]")
        await a.wait_for_selector("#painel-cadastro [data-gm-auth-erro]:not([hidden])", timeout=5000)
        dup = await a.text_content("#painel-cadastro [data-gm-auth-erro]")
        ok("Não foi possível concluir o cadastro" in dup and "já existe" not in dup and "cadastrado" not in dup,
           f"e-mail já usado: mensagem genérica ({dup!r})")
        ok(await a.text_content("#painel-cadastro [data-gm-auth-rotulo]") == "Criar conta" and not await a.is_disabled("#painel-cadastro [data-gm-auth-enviar]"),
           "botão volta ao normal após o erro")
        # Cadastro novo → sessão aberta e volta para o ?next=
        await a.fill("#cadastro-nome", "Ana Teste")
        await a.fill("#cadastro-email", "ana@gamemania.com.br")
        async with a.expect_navigation():
            await a.click("#painel-cadastro [data-gm-auth-enviar]")
        ok(a.url == f"{BASE}/carrinho.html", f"cadastro → volta para o next ({a.url.replace(BASE, '')})")
        me = await a.evaluate("GMUI.apiFetch('/auth/me')")
        ok(me["name"] == "Ana Teste" and me["email"] == "ana@gamemania.com.br", f"cadastro abriu a sessão: {me['name']}")
        n_users = db("select count(*) from users")[0][0]
        ok(n_users == 2, f"usuário gravado no Postgres (total {n_users})")
        await a.evaluate("GMUI.apiFetch('/auth/logout', {method: 'POST', redirectOn401: false})")
        # Senha errada: erro genérico, fica na página, senha apagada
        await a.goto(f"{BASE}/entreoucadastrese.html?next=%2Fcarrinho.html", wait_until="load")
        await a.fill("#entrar-email", "ana@gamemania.com.br")
        await a.fill("#entrar-senha", "senhaErrada999")
        await a.click("#painel-entrar [data-gm-auth-enviar]")
        await a.wait_for_selector("#painel-entrar [data-gm-auth-erro]:not([hidden])", timeout=5000)
        ok(await a.text_content("#painel-entrar [data-gm-auth-erro]") == "E-mail ou senha incorretos.", "senha errada: 'E-mail ou senha incorretos.'")
        ok("/entreoucadastrese.html" in a.url and await a.input_value("#entrar-senha") == "" and
           await a.evaluate("document.activeElement.id") == "entrar-senha", "senha errada: continua na página, campo de senha limpo e focado")
        await a.screenshot(path=f"{SHOTS}/entrar-erro-desktop.png", full_page=True)
        # next malicioso é ignorado → vai para o painel
        await a.goto(f"{BASE}/entreoucadastrese.html?next=https%3A%2F%2Fevil.com%2Fx.html", wait_until="load")
        ok(not await a.is_visible("[data-gm-auth-continuar]"), "next externo: aviso 'continuar' não aparece")
        await a.fill("#entrar-email", "ana@gamemania.com.br")
        await a.fill("#entrar-senha", "senhaForte123")
        async with a.expect_navigation():
            await a.press("#entrar-senha", "Enter")
        ok(a.url == f"{BASE}/dashboard.html", f"login com next=https://evil.com → ignora e vai para o painel ({a.url})")
        await a.wait_for_timeout(1500)
        ok(await a.text_content("[data-gm-bind='user.name']") == "Ana", "painel abre com a conta que acabou de entrar")
        ok(auth_posts == ["register", "register", "logout", "login", "login"], f"POSTs de auth esperados: {auth_posts}")
        # Celular: abas e formulário cabem em 390 px
        amctx = await new_context(browser, viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="pt-BR")
        am = await amctx.new_page()
        await am.goto(f"{BASE}/entreoucadastrese.html?next=%2Fcarrinho.html", wait_until="load"); await am.wait_for_timeout(1000)
        ok(await am.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "entrar mobile sem scroll horizontal")
        abas = await am.evaluate("""(() => { const [e, c] = [...document.querySelectorAll('.gm-auth__abas .nav-link')].map(b => b.getBoundingClientRect());
            return e.top === c.top && e.right <= c.left + 1 && c.right <= window.innerWidth; })()""")
        ok(abas, "entrar mobile: as duas abas lado a lado, sem cortar")
        ok(await am.evaluate("document.querySelector('.gm-auth').getBoundingClientRect().top < document.querySelector('.gm-auth-lado').getBoundingClientRect().top"),
           "entrar mobile: formulário antes do bloco do mascote")
        await am.screenshot(path=f"{SHOTS}/entrar-mobile.png", full_page=True)
        await am.click("#aba-cadastro"); await am.wait_for_timeout(400)
        await am.screenshot(path=f"{SHOTS}/entrar-cadastro-mobile.png", full_page=True)
        await amctx.close(); await actx.close()

        # ---------- 9e. Computadores (computadores.html) — vitrine da categoria + ordenação ----------
        cctx = await new_context(browser, viewport={"width": 1366, "height": 900}, locale="pt-BR")
        cp = await cctx.new_page()
        cp.on("pageerror", lambda e: console_errors.append("computadores: " + str(e)))
        nomes = "[...document.querySelectorAll('#gm-lista-computadores [data-gm-ordenar-item]')].map(e => e.getAttribute('data-ordem-nome'))"
        precos = "[...document.querySelectorAll('#gm-lista-computadores [data-gm-ordenar-item]')].map(e => Number(e.getAttribute('data-ordem-preco')))"
        await cp.goto(f"{BASE}/computadores.html", wait_until="load"); await cp.wait_for_timeout(800)
        if await cp.is_visible("#gm-consentimento"):
            await cp.click("[data-gm-consent=recusar]")      # o banner fixo não pode cobrir os botões dos cards
        ok(await cp.evaluate("document.querySelectorAll('#gm-lista-computadores .gm-card-produto').length") == 19, "computadores: 19 cards (10 destaques + 9 do site original)")
        ok((await cp.text_content("[data-gm-ordenar-contagem]")).strip() == "19 computadores", "computadores: contagem '19 computadores'")
        ok(await cp.get_attribute("#gm-menu a[href='computadores.html']", "aria-current") == "page"
           and await cp.get_attribute("#gm-menu a[href='index.html']", "aria-current") is None, "computadores: menu marca Computadores como página atual")
        ok(await cp.evaluate("[...document.querySelectorAll('.gm-trilha li')].map(l => l.textContent.trim()).join(' > ')") == "Destaques > Computadores", "computadores: breadcrumb Destaques > Computadores")
        ok(await cp.is_visible("#gm-ordenar-computadores"), "computadores: seletor de ordenação visível com JS")
        ok(await cp.evaluate("document.querySelector('#slot-mascote-categoria img').naturalWidth > 0"), "computadores: personagem no #slot-mascote-categoria")
        ld = await cp.evaluate("JSON.parse(document.querySelector('script[type=\"application/ld+json\"]').textContent)")
        ok(ld["@graph"][1]["mainEntity"]["numberOfItems"] == 19 and ld["@graph"][0]["@type"] == "BreadcrumbList", "computadores: JSON-LD com BreadcrumbList + ItemList(19)")
        rel = await cp.evaluate(nomes)
        ok(rel[0] == "PC Gamer RTX 3060" and rel[10] == "PC Escritório", f"computadores: ordem padrão = destaques e depois o site original ({rel[0]}, {rel[10]})")
        semdb = db("select count(*) from products where id between 11 and 19 and category='computadores' and is_active")
        ok(semdb[0][0] == 9, f"computadores: 9 produtos novos no banco (seed_products.sql): {semdb[0][0]}")
        # preços da página = preços do banco (o servidor recalcula no pedido; a vitrine não pode mentir)
        pag = await cp.evaluate("Object.fromEntries([...document.querySelectorAll('.btn-gm-add')].map(b => [b.dataset.productId, b.dataset.preco]))")
        banco = {str(i): f"{p:.2f}" for i, p in db("select id, price from products where category='computadores'")}
        ok(all(banco.get(k) == v for k, v in pag.items()), f"computadores: preços da vitrine iguais aos do banco ({len(pag)} produtos)")
        # Menor preço: R$ 1.899 (Dual Core) vem antes do R$ 1.900 (Econômico)
        await cp.select_option("#gm-ordenar-computadores", "preco-asc"); await cp.wait_for_timeout(200)
        pr = await cp.evaluate(precos)
        ok(pr == sorted(pr) and pr[0] == 1899 and (await cp.evaluate(nomes))[1] == "PC Econômico", f"ordenar menor preço: {pr[:3]}…")
        ok("ordem=preco-asc" in cp.url, "ordenação vai para a URL (?ordem=preco-asc)")
        ok("menor para o maior" in (await cp.text_content("[data-gm-ordenar-contagem]")), "contagem anuncia a ordenação (role=status)")
        await cp.select_option("#gm-ordenar-computadores", "preco-desc"); await cp.wait_for_timeout(200)
        pr = await cp.evaluate(precos)
        ok(pr == sorted(pr, reverse=True) and pr[0] == 10500, f"ordenar maior preço: {pr[:3]}…")
        n = await cp.evaluate(nomes)
        ok(n[2:4] == ["PC Gamer Ryzen 9", "PC Gamer Nitro X"], f"empate de preço (R$ 7.499) mantém a ordem original: {n[2:4]}")
        await cp.select_option("#gm-ordenar-computadores", "nome-asc"); await cp.wait_for_timeout(200)
        n = await cp.evaluate(nomes)
        ok(n[:3] == ["Computador Completo", "Computador Gamer", "Computador Ideal"] and n[-1] == "PC Workstation", f"ordenar nome A–Z (pt-BR): {n[:3]} … {n[-1]}")
        await cp.select_option("#gm-ordenar-computadores", "nome-desc"); await cp.wait_for_timeout(200)
        ok((await cp.evaluate(nomes))[0] == "PC Workstation", "ordenar nome Z–A")
        await cp.goto(f"{BASE}/computadores.html?ordem=preco-desc", wait_until="load"); await cp.wait_for_timeout(500)
        ok(await cp.input_value("#gm-ordenar-computadores") == "preco-desc" and (await cp.evaluate(precos))[0] == 10500, "link com ?ordem=preco-desc abre já ordenado")
        await cp.goto(f"{BASE}/computadores.html?ordem=%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E", wait_until="load"); await cp.wait_for_timeout(500)
        ok(await cp.input_value("#gm-ordenar-computadores") == "relevancia" and (await cp.evaluate(nomes)) == rel, "?ordem= inválida/maliciosa é ignorada (lista branca → relevância)")
        await cp.select_option("#gm-ordenar-computadores", "relevancia"); await cp.wait_for_timeout(200)
        ok("ordem=" not in cp.url and (await cp.evaluate(nomes)) == rel, "voltar para Relevância restaura a ordem e limpa a URL")
        for _ in range(10):
            await cp.mouse.wheel(0, 900); await cp.wait_for_timeout(120)
        await cp.wait_for_timeout(700)
        ok(await cp.evaluate("document.querySelectorAll('.gm-img--ausente').length") == 0, "computadores: nenhuma imagem ausente (pc01–pc09 migradas)")
        await cp.evaluate("window.scrollTo(0,0)"); await cp.wait_for_timeout(300)
        await cp.screenshot(path=f"{SHOTS}/computadores-desktop.png", full_page=True)
        # Carrinho: produto novo (sem página própria) → "Comprar" leva ao carrinho; ícone adiciona
        await cp.click("[data-gm-carrinho][data-product-id='18']"); await cp.wait_for_timeout(400)
        ok(await cp.text_content("[data-gm-carrinho-contador]") == "1", "computadores: ícone do carrinho adiciona PC Workstation")
        async with cp.expect_navigation():
            await cp.click("[data-gm-comprar][data-product-id='15']")
        cart = await cp.evaluate("JSON.parse(localStorage.getItem('cart'))")
        ok(cp.url.endswith("/carrinho.html") and [(i["id"], i["price"]) for i in cart] == [(18, 10500), (15, 1900)],
           f"'Comprar' do PC Econômico → carrinho com os 2 produtos novos: {[(i['id'], i['price']) for i in cart]}")
        await cp.wait_for_timeout(600)
        ok(await cp.evaluate("document.querySelectorAll('#gm-carrinho-lista li').length") == 2, "carrinho.html lista os produtos da categoria")
        # Celular 390 px
        ccm = await new_context(browser, viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="pt-BR")
        cm = await ccm.new_page()
        await cm.goto(f"{BASE}/computadores.html", wait_until="load"); await cm.wait_for_timeout(900)
        ok(await cm.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "computadores mobile sem scroll horizontal")
        sob = await cm.evaluate("""(() => { const r = s => document.querySelector(s).getBoundingClientRect();
            const a = r('[data-gm-ordenar-contagem]'), b = r('.gm-ordenar'), t = r('.gm-categoria-topo__texto'), m = r('#slot-mascote-categoria');
            return (a.bottom > b.top + 1) || (t.right > m.left + 1); })()""")
        ok(not sob, "computadores mobile: contagem/ordenação empilhadas e personagem sem sobrepor o título")
        ok(await cm.evaluate("getComputedStyle(document.querySelector('.gm-vitrine .row')).display") == "flex"
           and await cm.evaluate("document.querySelectorAll('#gm-lista-computadores > .col')[0].getBoundingClientRect().width < 200"), "computadores mobile: 2 colunas de cards")
        await cm.screenshot(path=f"{SHOTS}/computadores-mobile.png", full_page=True)
        await ccm.close(); await cctx.close()

        # ---------- 9f. Hardware (hardware.html) — vitrine + abas de tipo + ordenação ----------
        hctx = await new_context(browser, viewport={"width": 1366, "height": 900}, locale="pt-BR")
        hp = await hctx.new_page()
        hp.on("pageerror", lambda e: console_errors.append("hardware: " + str(e)))
        hitens = "#gm-lista-hardware [data-gm-ordenar-item]"
        visiveis = f"[...document.querySelectorAll('{hitens}')].filter(e => !e.hidden).map(e => e.getAttribute('data-ordem-nome'))"
        hprecos = f"[...document.querySelectorAll('{hitens}')].filter(e => !e.hidden).map(e => Number(e.getAttribute('data-ordem-preco')))"
        contagem = lambda: hp.evaluate("document.querySelector('[data-gm-ordenar-contagem]').textContent.trim()")
        await hp.goto(f"{BASE}/hardware.html", wait_until="load"); await hp.wait_for_timeout(800)
        if await hp.is_visible("#gm-consentimento"):
            await hp.click("[data-gm-consent=recusar]")
        ok(await hp.evaluate("document.querySelectorAll('#gm-lista-hardware .gm-card-produto').length") == 9, "hardware: 9 cards (os 9 equipamentos do site original)")
        ok(await contagem() == "9 produtos", f"hardware: contagem '9 produtos' ({await contagem()})")
        ok(await hp.get_attribute("#gm-menu a[href='hardware.html']", "aria-current") == "page"
           and await hp.get_attribute("#gm-menu a[href='computadores.html']", "aria-current") is None, "hardware: menu marca Hardware como página atual")
        ok(await hp.evaluate("[...document.querySelectorAll('.gm-trilha li')].map(l => l.textContent.trim()).join(' > ')") == "Destaques > Hardware", "hardware: breadcrumb Destaques > Hardware")
        ok(await hp.evaluate("document.querySelector('#slot-mascote-categoria img').naturalWidth > 0"), "hardware: personagem no #slot-mascote-categoria")
        ld = await hp.evaluate("JSON.parse(document.querySelector('script[type=\"application/ld+json\"]').textContent)")
        ok(ld["@graph"][1]["mainEntity"]["numberOfItems"] == 9 and ld["@graph"][0]["itemListElement"][1]["name"] == "Hardware", "hardware: JSON-LD com BreadcrumbList + ItemList(9)")
        hrel = await hp.evaluate(visiveis)
        ok(hrel[0] == "Placa de Vídeo GTX 1080" and hrel[-1] == "GeForce RTX 2080 Ti", f"hardware: ordem do site original ({hrel[0]} … {hrel[-1]})")
        hdb = db("select count(*) from products where id between 31 and 39 and category='hardware' and is_active")
        ok(hdb[0][0] == 9, f"hardware: 9 produtos de hardware no banco (seed_products.sql): {hdb[0][0]}")
        pag = await hp.evaluate("Object.fromEntries([...document.querySelectorAll('.btn-gm-add')].map(b => [b.dataset.productId, b.dataset.preco]))")
        banco = {str(i): f"{p:.2f}" for i, p in db("select id, price from products where category='hardware'")}
        ok(len(pag) == 9 and all(banco.get(k) == v for k, v in pag.items()), f"hardware: preços da vitrine iguais aos do banco ({len(pag)} produtos)")
        ok(banco.get("31") == "1799.00", f"hardware: GTX 1080 com o preço do site original (R$ 1.799,00): {banco.get('31')}")
        ok(await hp.evaluate("[...document.querySelectorAll('.gm-card-produto__preco data')].every(d => d.textContent.trim() === 'R$ ' + Number(d.value).toLocaleString('pt-BR', {minimumFractionDigits: 2}))"),
           "hardware: preço exibido = valor do <data> em R$ (pt-BR)")
        # Abas de tipo
        ok(await hp.is_visible(".gm-filtro") and await hp.is_visible("#gm-ordenar-hardware"), "hardware: abas de tipo e seletor de ordenação visíveis com JS")
        qtds = await hp.evaluate("Object.fromEntries([...document.querySelectorAll('[data-gm-filtro]')].map(b => [b.dataset.gmFiltro, b.querySelector('[data-gm-filtro-qtd]').textContent]))")
        ok(qtds == {"todos": "9", "placas-de-video": "3", "processadores": "2", "placas-mae": "1", "memoria-ram": "1", "armazenamento": "1", "fontes": "1"}, f"hardware: quantidade em cada aba {qtds}")
        await hp.click("[data-gm-filtro='placas-de-video']"); await hp.wait_for_timeout(200)
        ok(await hp.evaluate(visiveis) == ["Placa de Vídeo GTX 1080", "AMD Radeon RX Vega 64", "GeForce RTX 2080 Ti"], f"aba Placas de vídeo mostra só as 3 placas: {await hp.evaluate(visiveis)}")
        ok(await contagem() == "3 produtos · Placas de vídeo", f"contagem anuncia a aba (role=status): {await contagem()}")
        ok(await hp.get_attribute("[data-gm-filtro='placas-de-video']", "aria-pressed") == "true"
           and await hp.get_attribute("[data-gm-filtro='todos']", "aria-pressed") == "false", "aba ativa com aria-pressed=true (e só ela)")
        ok("tipo=placas-de-video" in hp.url, "aba vai para a URL (?tipo=placas-de-video)")
        ok(await hp.evaluate("getComputedStyle(document.querySelector('[data-gm-filtro][aria-pressed=true]')).backgroundColor") == "rgb(0, 255, 153)", "aba ativa no verde-neon da marca")
        # Filtro + ordenação juntos
        await hp.select_option("#gm-ordenar-hardware", "preco-asc"); await hp.wait_for_timeout(200)
        ok(await hp.evaluate(hprecos) == [1199, 1799, 1899], f"aba + menor preço: {await hp.evaluate(hprecos)}")
        ok(await contagem() == "3 produtos · Placas de vídeo · do menor para o maior preço", f"contagem com aba e ordem: {await contagem()}")
        ok("tipo=placas-de-video" in hp.url and "ordem=preco-asc" in hp.url, "URL guarda aba e ordem juntas")
        await hp.click("[data-gm-filtro='processadores']"); await hp.wait_for_timeout(200)
        ok(await hp.evaluate(visiveis) == ["Intel Core i5-10400F", "AMD Ryzen 7 5800X"], f"aba Processadores mantém a ordem por preço: {await hp.evaluate(visiveis)}")
        await hp.click("[data-gm-filtro='todos']"); await hp.wait_for_timeout(200)
        pr = await hp.evaluate(hprecos)
        ok(len(pr) == 9 and pr == sorted(pr) and pr[0] == 450 and pr[-1] == 1920, f"'Todos' volta aos 9, ainda por menor preço: {pr}")
        ok("tipo=" not in hp.url and "ordem=preco-asc" in hp.url, "'Todos' limpa o ?tipo= e mantém a ordem")
        await hp.select_option("#gm-ordenar-hardware", "nome-asc"); await hp.wait_for_timeout(200)
        n = await hp.evaluate(visiveis)
        ok(n[:2] == ["AMD Radeon RX Vega 64", "AMD Ryzen 7 5800X"] and n[-1] == "SSD Gigabyte AORUS RGB M.2 NVMe 512GB", f"hardware: nome A–Z (pt-BR): {n[:2]} … {n[-1]}")
        # Link compartilhado e valores maliciosos
        await hp.goto(f"{BASE}/hardware.html?tipo=fontes&ordem=preco-desc", wait_until="load"); await hp.wait_for_timeout(500)
        ok(await hp.evaluate(visiveis) == ["Fonte Corsair RM1000x"] and await hp.get_attribute("[data-gm-filtro='fontes']", "aria-pressed") == "true",
           "link com ?tipo=fontes abre já na aba Fontes")
        await hp.goto(f"{BASE}/hardware.html?tipo=%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E", wait_until="load"); await hp.wait_for_timeout(500)
        ok(len(await hp.evaluate(visiveis)) == 9 and await hp.get_attribute("[data-gm-filtro='todos']", "aria-pressed") == "true"
           and await hp.evaluate("document.querySelectorAll('.gm-filtro img, .gm-ordenar-barra img').length") == 0, "?tipo= malicioso é ignorado (lista branca → Todos, nada injetado)")
        await hp.goto(f"{BASE}/hardware.html?tipo=todos2", wait_until="load"); await hp.wait_for_timeout(400)
        ok(len(await hp.evaluate(visiveis)) == 9, "?tipo= inexistente → Todos")
        for _ in range(8):
            await hp.mouse.wheel(0, 900); await hp.wait_for_timeout(120)
        await hp.wait_for_timeout(700)
        ok(await hp.evaluate("document.querySelectorAll('.gm-img--ausente').length") == 0, "hardware: nenhuma imagem ausente (9 imagens migradas)")
        await hp.evaluate("window.scrollTo(0,0)"); await hp.wait_for_timeout(300)
        await hp.screenshot(path=f"{SHOTS}/hardware-desktop.png", full_page=True)
        # Carrinho: ícone adiciona; "Comprar" adiciona e vai ao carrinho; pedido logado com preço do banco
        await hp.click("[data-gm-carrinho][data-product-id='36']"); await hp.wait_for_timeout(400)
        ok(await hp.text_content("[data-gm-carrinho-contador]") == "1", "hardware: ícone do carrinho adiciona a Memória RAM")
        async with hp.expect_navigation():
            await hp.click("[data-gm-comprar][data-product-id='31']")
        cart = await hp.evaluate("JSON.parse(localStorage.getItem('cart'))")
        ok(hp.url.endswith("/carrinho.html") and [(i["id"], i["price"]) for i in cart] == [(36, 1200), (31, 1799)],
           f"'Comprar' da GTX 1080 → carrinho com as 2 peças: {[(i['id'], i['price']) for i in cart]}")
        await hp.wait_for_timeout(600)
        ok(await hp.evaluate("document.querySelectorAll('#gm-carrinho-lista li').length") == 2, "carrinho.html lista as peças de hardware")
        # Pedido com a sessão logada do teste principal (sem novo cadastro: limite de 5/min por IP)
        lp = await ctx.new_page()
        await lp.goto(f"{BASE}/hardware.html", wait_until="load")
        ped = await lp.evaluate("""GMUI.apiFetch('/orders', {method:'POST', body:{items:[{product_id:31, quantity:1}, {product_id:36, quantity:1}], payment_method:'pix'}})""")
        ok(ped and float(ped.get("total", 0)) == 2999.0, f"hardware: pedido aceito com o total do banco (1.799 + 1.200 = 2.999): {ped and ped.get('total')}")
        itens_db = db("select i.product_id from order_items i join orders o on o.id = i.order_id where o.public_id = %s order by 1", ped.get("public_id"))
        ok([r[0] for r in itens_db] == [31, 36], f"hardware: itens do pedido gravados no Postgres: {itens_db}")
        await lp.close()
        # Celular 390 px
        hcm = await new_context(browser, viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="pt-BR")
        hm = await hcm.new_page()
        await hm.goto(f"{BASE}/hardware.html", wait_until="load"); await hm.wait_for_timeout(900)
        ok(await hm.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "hardware mobile sem scroll horizontal (abas rolam dentro da faixa)")
        faixa = await hm.evaluate("""(() => { const f = document.querySelector('.gm-filtro'), r = f.getBoundingClientRect();
            const b = [...f.querySelectorAll('[data-gm-filtro]')].map(x => x.getBoundingClientRect());
            return {dentro: r.left >= 0 && r.right <= window.innerWidth, rola: f.scrollWidth > f.clientWidth,
                    linha: b.every(x => Math.abs(x.top - b[0].top) < 1), alvo: b.every(x => x.height >= 44)}; })()""")
        ok(all(faixa.values()), f"hardware mobile: abas numa linha só, rolando dentro da faixa, alvo de toque ≥ 44 px {faixa}")
        await hm.click("[data-gm-filtro='placas-de-video']"); await hm.wait_for_timeout(300)
        ok(await hm.evaluate(f"[...document.querySelectorAll('{hitens}')].filter(e => !e.hidden).length") == 3
           and await hm.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "hardware mobile: toque na aba filtra (3 placas) sem estourar a largura")
        await hm.click("[data-gm-filtro='todos']"); await hm.wait_for_timeout(300)
        await hm.screenshot(path=f"{SHOTS}/hardware-mobile.png", full_page=True)
        await hcm.close(); await hctx.close()

        # ---------- 9g. Periféricos (perifericos.html) — vitrine + abas de tipo + ordenação ----------
        pctx = await new_context(browser, viewport={"width": 1366, "height": 900}, locale="pt-BR")
        pp = await pctx.new_page()
        pp.on("pageerror", lambda e: console_errors.append("perifericos: " + str(e)))
        pitens = "#gm-lista-perifericos [data-gm-ordenar-item]"
        pvis = f"[...document.querySelectorAll('{pitens}')].filter(e => !e.hidden).map(e => e.getAttribute('data-ordem-nome'))"
        pprecos = f"[...document.querySelectorAll('{pitens}')].filter(e => !e.hidden).map(e => Number(e.getAttribute('data-ordem-preco')))"
        pcont = lambda: pp.evaluate("document.querySelector('[data-gm-ordenar-contagem]').textContent.trim()")
        await pp.goto(f"{BASE}/perifericos.html", wait_until="load"); await pp.wait_for_timeout(800)
        if await pp.is_visible("#gm-consentimento"):
            await pp.click("[data-gm-consent=recusar]")
        ok(await pp.evaluate("document.querySelectorAll('#gm-lista-perifericos .gm-card-produto').length") == 13, "periféricos: 13 cards (9 do site original + 4 da home)")
        ok(await pcont() == "13 produtos", f"periféricos: contagem '13 produtos' ({await pcont()})")
        ok(await pp.get_attribute("#gm-menu a[href='perifericos.html']", "aria-current") == "page"
           and await pp.get_attribute("#gm-menu a[href='hardware.html']", "aria-current") is None, "periféricos: menu marca Periféricos como página atual")
        ok(await pp.evaluate("[...document.querySelectorAll('.gm-trilha li')].map(l => l.textContent.trim()).join(' > ')") == "Destaques > Periféricos", "periféricos: breadcrumb Destaques > Periféricos")
        ok(await pp.evaluate("document.querySelector('#slot-mascote-categoria img').naturalWidth > 0"), "periféricos: personagem no #slot-mascote-categoria")
        ok(await pp.evaluate("document.querySelectorAll('h1').length") == 1 and "Periféricos à venda" in (await pp.text_content("h1")), "periféricos: um único <h1> 'Periféricos à venda'")
        ld = await pp.evaluate("JSON.parse(document.querySelector('script[type=\"application/ld+json\"]').textContent)")
        ok(ld["@graph"][1]["mainEntity"]["numberOfItems"] == 13 and ld["@graph"][0]["itemListElement"][1]["name"] == "Periféricos"
           and ld["@graph"][1]["mainEntity"]["itemListElement"][2]["item"]["name"] == 'Monitor 24" LED', "periféricos: JSON-LD com BreadcrumbList + ItemList(13)")
        prel = await pp.evaluate(pvis)
        ok(prel[0] == "Teclado Mecânico" and prel[8] == "Suporte para Monitor" and prel[-1] == "Monitor Gamer 144Hz", f"periféricos: ordem do site original ({prel[0]} … {prel[8]} … {prel[-1]})")
        pdb = db("select count(*) from products where id between 61 and 66 and category='perifericos' and is_active")
        ok(pdb[0][0] == 6, f"periféricos: 6 produtos novos no banco (ids 61–66 no seed_products.sql): {pdb[0][0]}")
        pag = await pp.evaluate("Object.fromEntries([...document.querySelectorAll('.btn-gm-add')].map(b => [b.dataset.productId, b.dataset.preco]))")
        banco = {str(i): f"{p:.2f}" for i, p in db("select id, price from products where category='perifericos'")}
        ok(len(pag) == 13 and all(banco.get(k) == v for k, v in pag.items()), f"periféricos: preços da vitrine iguais aos do banco ({len(pag)} produtos)")
        ok(await pp.evaluate("[...document.querySelectorAll('.gm-card-produto__preco data')].every(d => d.textContent.trim() === 'R$ ' + Number(d.value).toLocaleString('pt-BR', {minimumFractionDigits: 2}))"),
           "periféricos: preço exibido = valor do <data> em R$ (pt-BR)")
        ok(await pp.evaluate("document.querySelector('[data-product-id=\"21\"].btn-gm-add').dataset.nome") == 'Monitor 24" LED', "periféricos: aspas do nome do monitor preservadas nos data-* (escapadas no HTML)")
        # Abas de tipo
        ok(await pp.is_visible(".gm-filtro") and await pp.is_visible("#gm-ordenar-perifericos"), "periféricos: abas de tipo e seletor de ordenação visíveis com JS")
        qtds = await pp.evaluate("Object.fromEntries([...document.querySelectorAll('[data-gm-filtro]')].map(b => [b.dataset.gmFiltro, b.querySelector('[data-gm-filtro-qtd]').textContent]))")
        ok(qtds == {"todos": "13", "teclados-e-mouses": "3", "monitores": "3", "audio": "4", "webcam-e-impressao": "2", "games": "1"}, f"periféricos: quantidade em cada aba {qtds}")
        await pp.click("[data-gm-filtro='audio']"); await pp.wait_for_timeout(200)
        ok(await pp.evaluate(pvis) == ["Headset com Microfone", "Caixa de som USB", "Headset Gamer 7.1", "Suporte para Headset"], f"aba Áudio mostra os 4 itens de som: {await pp.evaluate(pvis)}")
        ok(await pcont() == "4 produtos · Áudio", f"periféricos: contagem anuncia a aba: {await pcont()}")
        ok("tipo=audio" in pp.url, "periféricos: aba vai para a URL (?tipo=audio)")
        await pp.click("[data-gm-filtro='monitores']"); await pp.wait_for_timeout(200)
        await pp.select_option("#gm-ordenar-perifericos", "preco-asc"); await pp.wait_for_timeout(200)
        ok(await pp.evaluate(pprecos) == [85, 750, 1499], f"aba Monitores + menor preço: {await pp.evaluate(pprecos)}")
        ok(await pcont() == "3 produtos · Monitores · do menor para o maior preço", f"periféricos: contagem com aba e ordem: {await pcont()}")
        await pp.click("[data-gm-filtro='todos']"); await pp.wait_for_timeout(200)
        pr = await pp.evaluate(pprecos)
        ok(len(pr) == 13 and pr == sorted(pr) and pr[0] == 35 and pr[-1] == 1499, f"periféricos: 'Todos' volta aos 13, ainda por menor preço: {pr}")
        await pp.select_option("#gm-ordenar-perifericos", "nome-asc"); await pp.wait_for_timeout(200)
        n = await pp.evaluate(pvis)
        ok(n[0] == "Caixa de som USB" and n[-1] == "Webcam 1080p" and n.index("Mouse Gamer") < n.index("Mousepad Gamer"), f"periféricos: nome A–Z (pt-BR): {n[0]} … {n[-1]}")
        await pp.goto(f"{BASE}/perifericos.html?tipo=games", wait_until="load"); await pp.wait_for_timeout(500)
        ok(await pp.evaluate(pvis) == ["Volante Gamer"] and await pp.get_attribute("[data-gm-filtro='games']", "aria-pressed") == "true", "periféricos: link com ?tipo=games abre já na aba Games")
        await pp.goto(f"{BASE}/perifericos.html?tipo=%22%3E%3Csvg%20onload%3Dalert(1)%3E", wait_until="load"); await pp.wait_for_timeout(500)
        ok(len(await pp.evaluate(pvis)) == 13 and await pp.evaluate("document.querySelectorAll('.gm-filtro svg, .gm-ordenar-barra svg').length") == 0, "periféricos: ?tipo= malicioso é ignorado (Todos, nada injetado)")
        for _ in range(10):
            await pp.mouse.wheel(0, 900); await pp.wait_for_timeout(120)
        await pp.wait_for_timeout(700)
        ok(await pp.evaluate("document.querySelectorAll('.gm-img--ausente').length") == 0, "periféricos: nenhuma imagem ausente (7 imagens novas migradas)")
        await pp.evaluate("window.scrollTo(0,0)"); await pp.wait_for_timeout(300)
        await pp.screenshot(path=f"{SHOTS}/perifericos-desktop.png", full_page=True)
        # Carrinho e pedido com preço do banco
        await pp.click("[data-gm-carrinho][data-product-id='64']"); await pp.wait_for_timeout(400)
        ok(await pp.text_content("[data-gm-carrinho-contador]") == "1", "periféricos: ícone do carrinho adiciona o Mousepad")
        async with pp.expect_navigation():
            await pp.click("[data-gm-comprar][data-product-id='61']")
        cart = await pp.evaluate("JSON.parse(localStorage.getItem('cart'))")
        ok(pp.url.endswith("/carrinho.html") and [(i["id"], i["price"]) for i in cart] == [(64, 35), (61, 120)],
           f"periféricos: 'Comprar' do Teclado → carrinho com os 2 itens: {[(i['id'], i['price']) for i in cart]}")
        lp = await ctx.new_page()
        await lp.goto(f"{BASE}/perifericos.html", wait_until="load")
        ped = await lp.evaluate("""GMUI.apiFetch('/orders', {method:'POST', body:{items:[{product_id:61, quantity:2}, {product_id:21, quantity:1}], payment_method:'pix'}})""")
        ok(ped and float(ped.get("total", 0)) == 990.0, f"periféricos: pedido aceito com o total do banco (2×120 + 750 = 990): {ped and ped.get('total')}")
        await lp.close()
        # Celular 390 px
        pcm = await new_context(browser, viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="pt-BR")
        pm = await pcm.new_page()
        await pm.goto(f"{BASE}/perifericos.html", wait_until="load"); await pm.wait_for_timeout(900)
        ok(await pm.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "periféricos mobile sem scroll horizontal")
        faixa = await pm.evaluate("""(() => { const f = document.querySelector('.gm-filtro'), r = f.getBoundingClientRect();
            const b = [...f.querySelectorAll('[data-gm-filtro]')].map(x => x.getBoundingClientRect());
            return {dentro: r.left >= 0 && r.right <= window.innerWidth, linha: b.every(x => Math.abs(x.top - b[0].top) < 1), alvo: b.every(x => x.height >= 44)}; })()""")
        ok(all(faixa.values()), f"periféricos mobile: abas numa linha, dentro da tela, alvo de toque ≥ 44 px {faixa}")
        ok(await pm.evaluate("(() => { const c = [...document.querySelectorAll('#gm-lista-perifericos .col')].slice(0, 2).map(e => e.getBoundingClientRect()); return Math.abs(c[0].top - c[1].top) < 1 && c[1].left > c[0].right - 1; })()"),
           "periféricos mobile: cards em 2 colunas")
        await pm.screenshot(path=f"{SHOTS}/perifericos-mobile.png", full_page=True)
        await pcm.close(); await pctx.close()

        # ---------- 9h. Escritório (escritorio.html) — vitrine + abas de tipo + ordenação ----------
        ectx = await new_context(browser, viewport={"width": 1366, "height": 900}, locale="pt-BR")
        ep = await ectx.new_page()
        ep.on("pageerror", lambda e: console_errors.append("escritorio: " + str(e)))
        eitens = "#gm-lista-escritorio [data-gm-ordenar-item]"
        evis = f"[...document.querySelectorAll('{eitens}')].filter(e => !e.hidden).map(e => e.getAttribute('data-ordem-nome'))"
        eprecos = f"[...document.querySelectorAll('{eitens}')].filter(e => !e.hidden).map(e => Number(e.getAttribute('data-ordem-preco')))"
        econt = lambda: ep.evaluate("document.querySelector('[data-gm-ordenar-contagem]').textContent.trim()")
        await ep.goto(f"{BASE}/escritorio.html", wait_until="load"); await ep.wait_for_timeout(800)
        if await ep.is_visible("#gm-consentimento"):
            await ep.click("[data-gm-consent=recusar]")
        ok(await ep.evaluate("document.querySelectorAll('#gm-lista-escritorio .gm-card-produto').length") == 9, "escritório: 9 cards (os 9 do site original)")
        ok(await econt() == "9 produtos", f"escritório: contagem '9 produtos' ({await econt()})")
        ok(await ep.get_attribute("#gm-menu a[href='escritorio.html']", "aria-current") == "page"
           and await ep.evaluate("document.querySelectorAll('#gm-menu [aria-current]').length") == 1, "escritório: menu marca só Escritório como página atual")
        ok(await ep.evaluate("[...document.querySelectorAll('.gm-trilha li')].map(l => l.textContent.trim()).join(' > ')") == "Destaques > Escritório", "escritório: breadcrumb Destaques > Escritório")
        ok(await ep.evaluate("document.querySelector('#slot-mascote-categoria img').naturalWidth > 0"), "escritório: personagem no #slot-mascote-categoria")
        ok(await ep.evaluate("document.querySelectorAll('h1').length") == 1 and "Escritório e home office" in (await ep.text_content("h1")), "escritório: um único <h1> 'Escritório e home office'")
        ld = await ep.evaluate("JSON.parse(document.querySelector('script[type=\"application/ld+json\"]').textContent)")
        ok(ld["@graph"][1]["mainEntity"]["numberOfItems"] == 9 and ld["@graph"][0]["itemListElement"][1]["name"] == "Escritório"
           and len(ld["@graph"][1]["mainEntity"]["itemListElement"]) == 9, "escritório: JSON-LD com BreadcrumbList + ItemList(9)")
        erel = await ep.evaluate(evis)
        ok(erel[0] == "Cadeira Ergonômica Executiva" and erel[-1] == "Cadeira Giratória Office Básica", f"escritório: ordem do site original ({erel[0]} … {erel[-1]})")
        edb = db("select count(*) from products where id between 41 and 49 and category='escritorio' and is_active")
        ok(edb[0][0] == 9, f"escritório: 9 produtos no banco (ids 41–49 no seed_products.sql): {edb[0][0]}")
        pag = await ep.evaluate("Object.fromEntries([...document.querySelectorAll('.btn-gm-add')].map(b => [b.dataset.productId, b.dataset.preco]))")
        banco = {str(i): f"{p:.2f}" for i, p in db("select id, price from products where category='escritorio'")}
        ok(len(pag) == 9 and all(banco.get(k) == v for k, v in pag.items()), f"escritório: preços da vitrine iguais aos do banco ({len(pag)} produtos)")
        ok(banco.get("41") == "250.00" and db("select page_path from products where id=41")[0][0] is None,
           "escritório: Cadeira Office (id 41) corrigida para R$ 250,00 do site original e sem página quebrada")
        ok(await ep.evaluate("[...document.querySelectorAll('.gm-card-produto__preco data')].every(d => d.textContent.trim() === 'R$ ' + Number(d.value).toLocaleString('pt-BR', {minimumFractionDigits: 2}))"),
           "escritório: preço exibido = valor do <data> em R$ (pt-BR)")
        # Abas de tipo
        ok(await ep.is_visible(".gm-filtro") and await ep.is_visible("#gm-ordenar-escritorio"), "escritório: abas de tipo e seletor de ordenação visíveis com JS")
        qtds = await ep.evaluate("Object.fromEntries([...document.querySelectorAll('[data-gm-filtro]')].map(b => [b.dataset.gmFiltro, b.querySelector('[data-gm-filtro-qtd]').textContent]))")
        ok(qtds == {"todos": "9", "cadeiras": "2", "mesas": "3", "acessorios": "3", "energia": "1"}, f"escritório: quantidade em cada aba {qtds}")
        await ep.click("[data-gm-filtro='mesas']"); await ep.wait_for_timeout(200)
        ok(await ep.evaluate(evis) == ["Mesa de Escritório com Gavetas", "Mesa Compacta para Escritório", "Mesa Executiva de Escritório"], f"aba Mesas mostra as 3 mesas: {await ep.evaluate(evis)}")
        ok(await econt() == "3 produtos · Mesas" and "tipo=mesas" in ep.url, f"escritório: contagem anuncia a aba e vai para a URL: {await econt()}")
        await ep.select_option("#gm-ordenar-escritorio", "preco-asc"); await ep.wait_for_timeout(200)
        ok(await ep.evaluate(eprecos) == [280, 310, 420], f"aba Mesas + menor preço: {await ep.evaluate(eprecos)}")
        await ep.click("[data-gm-filtro='acessorios']"); await ep.wait_for_timeout(200)
        ok(await ep.evaluate(eprecos) == [35, 60, 70] and await econt() == "3 produtos · Acessórios de mesa · do menor para o maior preço",
           f"escritório: troca de aba mantém a ordem: {await ep.evaluate(eprecos)} / {await econt()}")
        await ep.click("[data-gm-filtro='todos']"); await ep.wait_for_timeout(200)
        er = await ep.evaluate(eprecos)
        ok(len(er) == 9 and er == sorted(er) and er[0] == 35 and er[-1] == 480, f"escritório: 'Todos' volta aos 9, ainda por menor preço: {er}")
        await ep.select_option("#gm-ordenar-escritorio", "nome-desc"); await ep.wait_for_timeout(200)
        n = await ep.evaluate(evis)
        ok(n[0] == "Protetor de Tela para Monitor" and n[-1] == "Cadeira Ergonômica Executiva", f"escritório: nome Z–A (pt-BR): {n[0]} … {n[-1]}")
        await ep.goto(f"{BASE}/escritorio.html?tipo=energia", wait_until="load"); await ep.wait_for_timeout(500)
        ok(await ep.evaluate(evis) == ["Estabilizador de Energia 500VA"] and await ep.get_attribute("[data-gm-filtro='energia']", "aria-pressed") == "true",
           "escritório: link com ?tipo=energia abre já na aba Energia")
        await ep.goto(f"{BASE}/escritorio.html?tipo=%22%3E%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E&ordem=javascript:alert(1)", wait_until="load"); await ep.wait_for_timeout(500)
        ok(len(await ep.evaluate(evis)) == 9 and await ep.evaluate("document.querySelector('#gm-ordenar-escritorio').value") == "relevancia"
           and await ep.evaluate("document.querySelectorAll('.gm-filtro img, .gm-ordenar-barra img').length") == 0, "escritório: ?tipo= e ?ordem= maliciosos são ignorados")
        for _ in range(8):
            await ep.mouse.wheel(0, 900); await ep.wait_for_timeout(120)
        await ep.wait_for_timeout(700)
        ok(await ep.evaluate("document.querySelectorAll('.gm-img--ausente').length") == 0, "escritório: nenhuma imagem ausente (9 imagens novas migradas)")
        await ep.evaluate("window.scrollTo(0,0)"); await ep.wait_for_timeout(300)
        await ep.screenshot(path=f"{SHOTS}/escritorio-desktop.png", full_page=True)
        # Carrinho e pedido com preço do banco
        await ep.click("[data-gm-carrinho][data-product-id='46']"); await ep.wait_for_timeout(400)
        ok(await ep.text_content("[data-gm-carrinho-contador]") == "1", "escritório: ícone do carrinho adiciona a Luminária")
        async with ep.expect_navigation():
            await ep.click("[data-gm-comprar][data-product-id='42']")
        cart = await ep.evaluate("JSON.parse(localStorage.getItem('cart'))")
        ok(ep.url.endswith("/carrinho.html") and [(i["id"], i["price"]) for i in cart] == [(46, 70), (42, 480)],
           f"escritório: 'Comprar' da Cadeira Ergonômica → carrinho com os 2 itens: {[(i['id'], i['price']) for i in cart]}")
        lp = await ctx.new_page()
        await lp.goto(f"{BASE}/escritorio.html", wait_until="load")
        ped = await lp.evaluate("""GMUI.apiFetch('/orders', {method:'POST', body:{items:[{product_id:41, quantity:2}, {product_id:48, quantity:1}], payment_method:'pix'}})""")
        ok(ped and float(ped.get("total", 0)) == 640.0, f"escritório: pedido aceito com o total do banco (2×250 + 140 = 640): {ped and ped.get('total')}")
        await lp.close()
        # Celular 390 px
        ecm = await new_context(browser, viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="pt-BR")
        em = await ecm.new_page()
        await em.goto(f"{BASE}/escritorio.html", wait_until="load"); await em.wait_for_timeout(900)
        ok(await em.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "escritório mobile sem scroll horizontal")
        faixa = await em.evaluate("""(() => { const f = document.querySelector('.gm-filtro'), r = f.getBoundingClientRect();
            const b = [...f.querySelectorAll('[data-gm-filtro]')].map(x => x.getBoundingClientRect());
            return {dentro: r.left >= 0 && r.right <= window.innerWidth, linha: b.every(x => Math.abs(x.top - b[0].top) < 1), alvo: b.every(x => x.height >= 44)}; })()""")
        ok(all(faixa.values()), f"escritório mobile: abas numa linha, dentro da tela, alvo de toque ≥ 44 px {faixa}")
        ok(await em.evaluate("(() => { const c = [...document.querySelectorAll('#gm-lista-escritorio .col')].slice(0, 2).map(e => e.getBoundingClientRect()); return Math.abs(c[0].top - c[1].top) < 1 && c[1].left > c[0].right - 1; })()"),
           "escritório mobile: cards em 2 colunas")
        await em.screenshot(path=f"{SHOTS}/escritorio-mobile.png", full_page=True)
        await ecm.close(); await ectx.close()

        # ---------- 9i. Suporte (suporte.html) — canais + FAQ (accordion) + busca + link direto ----------
        sctx = await new_context(browser, viewport={"width": 1366, "height": 900}, locale="pt-BR")
        sp = await sctx.new_page()
        serros = []
        sp.on("pageerror", lambda e: serros.append(str(e)))
        sp.on("dialog", lambda d: (serros.append("dialog: " + d.message), asyncio.ensure_future(d.dismiss())))
        await sp.goto(f"{BASE}/index.html", wait_until="load")
        async with sp.expect_navigation():
            await sp.click(".gm-rodape a[href='suporte.html']")
        ok(sp.url.endswith("/suporte.html"), "suporte: link 'Suporte' do rodapé abre a página (antes dava 404)")
        await sp.wait_for_timeout(400)
        ok(await sp.text_content("h1") == "Central de suporte" and await sp.evaluate("document.querySelectorAll('h1').length") == 1, "suporte: <h1> único 'Central de suporte'")
        ok(await sp.evaluate("document.querySelectorAll('#gm-menu [aria-current]').length") == 0, "suporte: nenhum item do menu marcado (a página não está no menu)")
        ok(await sp.text_content(".gm-trilha [aria-current='page']") == "Suporte", "suporte: breadcrumb Destaques › Suporte")
        ok(await sp.is_visible("#slot-mascote-suporte .mascote-secundario"), "suporte: personagem no #slot-mascote-suporte")
        canais = await sp.evaluate("[...document.querySelectorAll('.gm-canal a')].map(a => a.getAttribute('href'))")
        ok(canais == ["https://wa.me/551392124291", "tel:+551392124291", "mailto:contato@gamemania.com.br",
                      "https://www.google.com/maps?q=Av.+Washington+Lu%C3%ADs,+105,+Santos+-+SP"], f"suporte: 4 canais iguais aos do rodapé {canais}")
        ok(await sp.get_attribute(".gm-canal--destaque a", "data-track") == "whatsapp", "suporte: WhatsApp entra no funil (data-track)")
        perguntas = await sp.evaluate("[...document.querySelectorAll('[data-gm-faq-item] .accordion-button')].map(b => b.textContent.trim())")
        grupos = await sp.evaluate("[...document.querySelectorAll('[data-gm-faq-grupo] h3')].map(h => h.textContent)")
        ok(len(perguntas) == 11 and grupos == ["Trocas e devoluções", "Garantia", "Frete e entrega", "Pagamento", "Montagem"],
           f"suporte: 11 perguntas em 5 assuntos {grupos}")
        ld = await sp.evaluate("""(() => { const g = JSON.parse(document.querySelector('script[type="application/ld+json"]').textContent)['@graph'];
            const f = g.find(x => x['@type'] === 'FAQPage');
            return {tipos: g.map(x => x['@type']), q: f.mainEntity.map(m => m.name),
                    r: f.mainEntity.map(m => m.acceptedAnswer.text)}; })()""")
        respostas = await sp.evaluate("[...document.querySelectorAll('[data-gm-faq-item] .accordion-body')].map(b => b.textContent)")
        ok(ld["tipos"] == ["BreadcrumbList", "FAQPage"] and ld["q"] == perguntas and ld["r"] == respostas,
           "suporte: JSON-LD FAQPage com as mesmas 11 perguntas e respostas da página")
        ok(await sp.evaluate("document.querySelectorAll('.accordion-collapse.show').length") == 0, "suporte: todas as respostas começam fechadas")
        # Abrir uma pergunta: cor da marca + #id na URL
        await sp.click("#faq-frete-valor .accordion-button"); await sp.wait_for_timeout(500)
        ok(await sp.is_visible("#faq-frete-valor-resp") and await sp.get_attribute("#faq-frete-valor .accordion-button", "aria-expanded") == "true",
           "suporte: clicar na pergunta abre a resposta (aria-expanded=true)")
        ok("frete é grátis para todo o Brasil" in await sp.text_content("#faq-frete-valor-resp"), "suporte: resposta do frete (frete grátis, do site original)")
        ok(await sp.evaluate("getComputedStyle(document.querySelector('#faq-frete-valor .accordion-button')).color") == "rgb(0, 255, 153)",
           "suporte: pergunta aberta em verde-neon (#00ff99)")
        ok(sp.url.endswith("#faq-frete-valor"), f"suporte: abrir a pergunta grava o link direto na URL ({sp.url.rsplit('/', 1)[-1]})")
        await sp.click("#faq-frete-prazo .accordion-button"); await sp.wait_for_timeout(500)
        ok(not await sp.is_visible("#faq-frete-valor-resp") and await sp.is_visible("#faq-frete-prazo-resp"), "suporte: no mesmo assunto, abrir outra fecha a anterior")
        # Busca nas perguntas
        ok(await sp.is_visible("#gm-faq-busca"), "suporte: busca de dúvidas visível com JS")
        fvis = "[...document.querySelectorAll('[data-gm-faq-item]')].filter(i => !i.hidden).map(i => i.id)"
        fstatus = "document.querySelector('[data-gm-faq-status]').textContent"
        await sp.fill("#gm-faq-busca", "GARANTÍA"); await sp.wait_for_timeout(400)
        ok(await sp.evaluate(fvis) == ["faq-defeito-chegada", "faq-garantia-prazo", "faq-garantia-acionar"],
           f"suporte: busca ignora acento e maiúsculas ('GARANTÍA'): {await sp.evaluate(fvis)}")
        ok(await sp.evaluate(fstatus) == "3 dúvidas encontradas para “GARANTÍA”", f"suporte: status anuncia o resultado: {await sp.evaluate(fstatus)}")
        ok(await sp.evaluate("[...document.querySelectorAll('[data-gm-faq-grupo]')].filter(g => !g.hidden).map(g => g.id)") == ["faq-trocas", "faq-garantia"]
           and not await sp.is_visible("[data-gm-faq-atalhos]"), "suporte: assuntos sem resultado e atalhos somem durante a busca")
        await sp.fill("#gm-faq-busca", "pix"); await sp.wait_for_timeout(400)
        ok(await sp.evaluate(fvis) == ["faq-pagamento-formas"] and await sp.evaluate(fstatus) == "1 dúvida encontrada para “pix”",
           f"suporte: busca 'pix' → formas de pagamento (singular): {await sp.evaluate(fstatus)}")
        await sp.fill("#gm-faq-busca", "<img src=x onerror=alert(1)>"); await sp.wait_for_timeout(400)
        ok(await sp.evaluate(fvis) == [] and await sp.is_visible("[data-gm-faq-vazio]") and await sp.is_visible("#slot-mascote-faq-vazio")
           and await sp.evaluate("document.querySelectorAll('[data-gm-faq-status] img').length") == 0,
           "suporte: busca sem resultado mostra personagem + WhatsApp, e o termo vira texto (sem XSS)")
        await sp.fill("#gm-faq-busca", ""); await sp.wait_for_timeout(400)
        ok(len(await sp.evaluate(fvis)) == 11 and await sp.is_visible("[data-gm-faq-atalhos]") and not await sp.is_visible("[data-gm-faq-vazio]")
           and await sp.evaluate(fstatus) == "", "suporte: limpar a busca volta às 11 perguntas")
        await sp.press("#gm-faq-busca", "Enter"); await sp.wait_for_timeout(300)
        ok(sp.url.split("#")[0].endswith("/suporte.html"), "suporte: Enter na busca não recarrega nem troca de página")
        # Link direto (#faq-...) e hash malicioso
        sp2 = await sctx.new_page()
        sp2.on("pageerror", lambda e: serros.append(str(e)))
        await sp2.goto(f"{BASE}/suporte.html#faq-pagamento-formas", wait_until="load"); await sp2.wait_for_timeout(900)
        ok(await sp2.is_visible("#faq-pagamento-formas-resp") and "Pix" in await sp2.text_content("#faq-pagamento-formas-resp"),
           "suporte: link direto #faq-pagamento-formas já abre a resposta")
        await sp2.goto(f"{BASE}/index.html", wait_until="load")   # sai da página: trocar só o #hash não recarrega
        await sp2.goto(f"{BASE}/suporte.html#%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E", wait_until="load"); await sp2.wait_for_timeout(700)
        ok(await sp2.evaluate("document.querySelectorAll('.accordion-collapse.show').length") == 0, "suporte: #hash malicioso/inexistente é ignorado")
        await sp2.close()
        await sp.goto(f"{BASE}/suporte.html", wait_until="load"); await sp.wait_for_timeout(600)
        await sp.screenshot(path=f"{SHOTS}/suporte-desktop.png", full_page=True)
        ok(await sp.evaluate("(() => { const c = [...document.querySelectorAll('.gm-suporte-canais .col')].map(e => e.getBoundingClientRect().top); return c.every(t => Math.abs(t - c[0]) < 1); })()"),
           "suporte desktop: 4 canais lado a lado")
        # Celular 390 px
        scm = await new_context(browser, viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="pt-BR")
        sm = await scm.new_page()
        await sm.goto(f"{BASE}/suporte.html", wait_until="load"); await sm.wait_for_timeout(900)
        ok(await sm.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "suporte mobile sem scroll horizontal")
        ok(await sm.evaluate("(() => { const c = [...document.querySelectorAll('.gm-suporte-canais .col')].slice(0, 2).map(e => e.getBoundingClientRect()); return c[1].top >= c[0].bottom - 1; })()"),
           "suporte mobile: canais empilhados em 1 coluna")
        alvos = await sm.evaluate("[...document.querySelectorAll('.gm-canal a, .gm-faq .accordion-button, #gm-faq-busca')].map(e => e.getBoundingClientRect().height).filter(h => h < 44).length")
        ok(alvos == 0, f"suporte mobile: links, perguntas e busca com alvo de toque ≥ 44 px ({alvos} menores)")
        await sm.click("#faq-montagem-pronto .accordion-button"); await sm.wait_for_timeout(500)
        ok(await sm.is_visible("#faq-montagem-pronto-resp"), "suporte mobile: toque abre a resposta")
        await sm.screenshot(path=f"{SHOTS}/suporte-mobile.png", full_page=True)
        ok(not serros, f"suporte: sem erros de JS nem alert() {serros[:2]}")
        await scm.close(); await sctx.close()

        # ---------- 9j. Página não encontrada (404.html) — servida pelo FastAPI em rotas inexistentes ----------
        ectx = await new_context(browser, viewport={"width": 1366, "height": 900}, locale="pt-BR")
        ep = await ectx.new_page()
        eerros = []
        ep.on("pageerror", lambda e: eerros.append(str(e)))
        ep.on("dialog", lambda d: (eerros.append("dialog: " + d.message), asyncio.ensure_future(d.dismiss())))
        await ep.goto(f"{BASE}/index.html", wait_until="load")
        destino = await ep.get_attribute("a[href='pccompleto.html']", "href")
        async with ep.expect_navigation() as nav:
            await ep.click("a[href='pccompleto.html']")
        resp = await nav.value
        await ep.wait_for_timeout(500)
        ok(destino and resp.status == 404, f"404: link da home para página ainda não migrada responde HTTP 404 ({resp.status})")
        ok(await ep.text_content("h1") == "Página não encontrada" and await ep.evaluate("document.querySelectorAll('h1').length") == 1,
           "404: mostra a página amigável com <h1> único 'Página não encontrada'")
        ok(await ep.evaluate("getComputedStyle(document.querySelector('.gm-topo')).backgroundColor") == "rgb(33, 37, 41)", "404: CSS da marca carregado")
        ok(await ep.evaluate("getComputedStyle(document.querySelector('.gm-erro__codigo')).color") == "rgb(255, 0, 79)", "404: código '404' no rosa-neon (#ff004f)")
        ok(await ep.is_visible("#slot-mascote-404 .mascote-principal")
           and await ep.evaluate("document.querySelector('#slot-mascote-404 img').naturalWidth") > 0, "404: personagem no #slot-mascote-404")
        ok(await ep.evaluate("document.querySelectorAll('#gm-menu [aria-current]').length") == 0
           and await ep.text_content(".gm-trilha [aria-current='page']") == "Página não encontrada", "404: menu sem item marcado + breadcrumb")
        ok(await ep.get_attribute("meta[name=robots]", "content") == "noindex, follow" and await ep.evaluate("!document.querySelector('link[rel=canonical]')"),
           "404: noindex e sem canonical")
        ok(await ep.text_content("[data-gm-404-endereco]") == "/pccompleto.html" and await ep.is_visible("[data-gm-404-endereco]"),
           f"404: mostra o endereço procurado ({await ep.text_content('[data-gm-404-endereco]')})")
        ok(await ep.evaluate("!document.querySelector('base')"), "404: rota de 1 nível não recebe <base> (âncoras normais)")
        # Atalhos: as 5 seções do menu, com a mesma quantidade de produtos das páginas de categoria
        atalhos = await ep.evaluate("[...document.querySelectorAll('.gm-atalho')].map(a => ({href: a.getAttribute('href'), qtd: (a.querySelector('[data-gm-404-qtd]') || {}).textContent || ''}))")
        menu = await ep.evaluate("[...document.querySelectorAll('#gm-menu .nav-link')].map(a => a.getAttribute('href'))")
        ok([a["href"] for a in atalhos] == menu, f"404: atalhos = as 5 seções do menu, na mesma ordem {[a['href'] for a in atalhos]}")
        reais = await ep.evaluate("""Promise.all(['hardware.html', 'computadores.html', 'perifericos.html', 'escritorio.html'].map(p =>
            fetch(p).then(r => r.text()).then(t => new DOMParser().parseFromString(t, 'text/html').querySelectorAll('.gm-card-produto').length + ' produtos')))""")
        ok([a["qtd"] for a in atalhos[1:]] == reais, f"404: quantidade de cada atalho = cards da categoria {reais}")
        ok(await ep.evaluate("[...document.querySelectorAll('.gm-atalho[data-track=erro_404_categoria]')].map(a => a.dataset.trackCategoria).join()")
           == "destaques,hardware,computadores,perifericos,escritorio", "404: atalhos entram no funil (data-track + categoria)")
        ok(await ep.evaluate("[...document.querySelectorAll('.gm-erro-categorias img')].every(i => i.naturalWidth > 0)"), "404: ícones das categorias carregados")
        # Voltar (veio da home → aparece e volta)
        ok(await ep.is_visible("[data-gm-voltar]"), "404: botão 'Voltar' aparece quando a visita veio do próprio site")
        async with ep.expect_navigation():
            await ep.click("[data-gm-voltar]")
        ok(ep.url.endswith("/index.html"), f"404: 'Voltar' retorna à página anterior ({ep.url.rsplit('/', 1)[-1]})")
        # Busca da 404 → vitrine da home filtrada
        await ep.goto(f"{BASE}/pagina-que-nao-existe.html", wait_until="load")
        await ep.fill("#gm-404-q", "ryzen")
        async with ep.expect_navigation():
            await ep.press("#gm-404-q", "Enter")
        await ep.wait_for_timeout(600)
        ok(ep.url.endswith("/index.html?q=ryzen") and await ep.is_visible("#gm-busca-status")
           and "ryzen" in await ep.text_content("#gm-busca-status"), f"404: busca leva para index.html?q=ryzen filtrado ({ep.url.rsplit('/', 1)[-1]})")
        # Direto em /404.html: 200, sem endereço e sem 'Voltar'
        e2 = await ectx.new_page()
        e2.on("pageerror", lambda e: eerros.append(str(e)))
        r2 = await e2.goto(f"{BASE}/404.html", wait_until="load"); await e2.wait_for_timeout(400)
        ok(r2.status == 200 and not await e2.is_visible("[data-gm-404-endereco-caixa]") and not await e2.is_visible("[data-gm-voltar]"),
           "404: aberta direto (/404.html) não mostra endereço nem 'Voltar'")
        # Rota aninhada: <base href="/"> mantém CSS/imagens e o 'Pular para o conteúdo' não sai da página
        r3 = await e2.goto(f"{BASE}/loja/pc/inexistente", wait_until="load")
        for _ in range(6):
            await e2.mouse.wheel(0, 900); await e2.wait_for_timeout(80)
        await e2.wait_for_timeout(500)
        ok(r3.status == 404 and await e2.evaluate("document.querySelector('base').getAttribute('href')") == "/", f"404: rota aninhada → HTTP {r3.status} com <base href='/'>")
        ok(await e2.evaluate("getComputedStyle(document.querySelector('.gm-topo')).backgroundColor") == "rgb(33, 37, 41)"
           and await e2.evaluate("[...document.images].filter(i => i.complete && i.naturalWidth === 0).length") == 0,
           "404: rota aninhada com CSS e imagens carregados (sem caminhos quebrados)")
        await e2.evaluate("window.scrollTo(0, 0)")
        await e2.focus(".gm-pular"); await e2.keyboard.press("Enter"); await e2.wait_for_timeout(400)
        ok(e2.url == f"{BASE}/loja/pc/inexistente" and await e2.evaluate("document.activeElement.id") == "conteudo",
           f"404: com <base>, 'Pular para o conteúdo' fica na página e foca o conteúdo ({e2.url.replace(BASE, '')})")
        async with e2.expect_navigation():
            await e2.click(".gm-atalho[href='hardware.html']")
        ok(e2.url == f"{BASE}/hardware.html", f"404: atalho da rota aninhada abre /hardware.html ({e2.url.replace(BASE, '')})")
        # Endereço malicioso vira texto
        r4 = await e2.goto(f"{BASE}/%3Cimg%20src=x%20onerror=alert(1)%3E.html", wait_until="load"); await e2.wait_for_timeout(500)
        ok(r4.status == 404 and await e2.text_content("[data-gm-404-endereco]") == "/<img src=x onerror=alert(1)>.html"
           and await e2.evaluate("document.querySelectorAll('.gm-erro img').length") == 1, "404: endereço com HTML aparece como texto (sem XSS)")
        # API inexistente continua JSON (o front-end chama a API com fetch)
        api = await e2.evaluate("fetch('/api/v1/rota-que-nao-existe').then(async r => ({s: r.status, t: r.headers.get('content-type'), j: await r.json()}))")
        ok(api["s"] == 404 and api["t"].startswith("application/json") and api["j"] == {"detail": "Não encontrado"}, f"404: /api/... inexistente responde JSON, não HTML ({api})")
        await e2.close()
        await ep.goto(f"{BASE}/pccompleto.html", wait_until="load"); await ep.wait_for_timeout(600)
        await ep.screenshot(path=f"{SHOTS}/404-desktop.png", full_page=True)
        ok(await ep.evaluate("(() => { const c = [...document.querySelectorAll('.gm-erro-categorias .col')].map(e => e.getBoundingClientRect().top); return c.every(t => Math.abs(t - c[0]) < 1); })()"),
           "404 desktop: 5 atalhos lado a lado")
        ok(await ep.evaluate("(() => { const t = document.querySelector('.gm-erro__texto').getBoundingClientRect(), m = document.querySelector('#slot-mascote-404').getBoundingClientRect(); return m.left >= t.right - 1; })()"),
           "404 desktop: personagem à direita do texto")
        # Celular 390 px
        ecm = await new_context(browser, viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="pt-BR")
        em = await ecm.new_page()
        em.on("pageerror", lambda e: eerros.append(str(e)))
        rm = await em.goto(f"{BASE}/pccompleto.html", wait_until="load"); await em.wait_for_timeout(900)
        ok(rm.status == 404 and await em.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "404 mobile sem scroll horizontal")
        ok(await em.evaluate("(() => { const c = [...document.querySelectorAll('.gm-erro-categorias .col')].slice(0, 2).map(e => e.getBoundingClientRect()); return c[1].top >= c[0].bottom - 1; })()"),
           "404 mobile: atalhos empilhados em 1 coluna")
        ok(await em.evaluate("(() => { const m = document.querySelector('#slot-mascote-404').getBoundingClientRect(), h = document.querySelector('.gm-erro__titulo').getBoundingClientRect(); return m.bottom <= h.top + 1 && m.width >= 120; })()"),
           "404 mobile: personagem acima do título")
        alvos = await em.evaluate("[...document.querySelectorAll('.gm-erro__acoes .btn:not([hidden]), #gm-404-q, .gm-erro-busca button, .gm-atalho')].map(e => e.getBoundingClientRect().height).filter(h => h < 44).length")
        ok(alvos == 0, f"404 mobile: botões, busca e atalhos com alvo de toque ≥ 44 px ({alvos} menores)")
        await em.screenshot(path=f"{SHOTS}/404-mobile.png", full_page=True)
        ok(not eerros, f"404: sem erros de JS nem alert() {eerros[:2]}")
        await ecm.close(); await ectx.close()

        # ---------- 9k. Página de produto: PC Gamer RTX 3060 (pcgamerrtx3060.html, R09) ----------
        rctx = await new_context(browser, viewport={"width": 1366, "height": 900}, locale="pt-BR")
        rp = await rctx.new_page()
        rerros, rtrack = [], []
        rp.on("pageerror", lambda e: rerros.append(str(e)))
        rp.on("dialog", lambda d: (rerros.append("dialog: " + d.message), asyncio.ensure_future(d.dismiss())))
        rp.on("request", lambda r: r.url.endswith("/api/v1/track") and rtrack.append(r))
        # Chega pela vitrine da home: "Mais Informações" do card deixa de cair na 404
        await rp.goto(f"{BASE}/index.html", wait_until="load")
        async with rp.expect_navigation() as nav:
            await rp.click("a[href='pcgamerrtx3060.html'][data-track=mais_informacoes]")
        rr = await nav.value
        await rp.wait_for_timeout(800)
        ok(rr.status == 200 and rp.url.endswith("/pcgamerrtx3060.html"), f"RTX 3060: 'Mais Informações' da home abre a página (HTTP {rr.status})")
        ok(await rp.text_content("h1") == "PC Gamer RTX 3060" and await rp.evaluate("document.querySelectorAll('h1').length") == 1, "RTX 3060: <h1> único com o nome do site original")
        ok(await rp.evaluate("document.body.dataset.productId") == "1", "RTX 3060: body[data-product-id] = 1 (id do seed)")
        nome_db, preco_db, pag_db = db("select name, price, page_path from products where id=1")[0]
        ok(nome_db == "PC Gamer RTX 3060" and pag_db == "pcgamerrtx3060.html", f"RTX 3060: produto e page_path no Postgres ({nome_db}, {pag_db})")
        ok(await rp.get_attribute(".gm-preco__valor", "value") == f"{preco_db:.2f}" == "4999.00", f"RTX 3060: preço da página = preço do banco ({preco_db})")
        ok((await rp.text_content(".gm-preco__valor")).replace("\u00a0", " ") == "R$ 4.999,00"
           and "12x de R$ 416,58" in await rp.text_content(".gm-preco__parcelas"), "RTX 3060: preço e parcelas (4.999 ÷ 12 = 416,58)")
        ok(await rp.evaluate("getComputedStyle(document.querySelector('.gm-preco__valor')).color") == "rgb(0, 255, 153)", "RTX 3060: preço no verde-neon da marca")
        ld = await rp.evaluate("JSON.parse(document.querySelector('script[type=\"application/ld+json\"]').textContent)['@graph']")
        ok(ld[0]["name"] == "PC Gamer RTX 3060" and ld[0]["offers"]["price"] == "4999.00" and ld[0]["sku"] == "GM-PC-RTX3060"
           and ld[0]["offers"]["url"].endswith("/pcgamerrtx3060.html") and ld[1]["itemListElement"][2]["name"] == "PC Gamer RTX 3060",
           "RTX 3060: JSON-LD Product (nome, SKU, 4999.00, URL) + BreadcrumbList")
        ok(await rp.get_attribute("link[rel=canonical]", "href") == "https://www.gamemania.com.br/pcgamerrtx3060.html"
           and await rp.get_attribute("meta[property='product:price:amount']", "content") == "4999.00", "RTX 3060: canonical e preço no Open Graph")
        ok(await rp.evaluate("[...document.querySelectorAll('#gm-menu [aria-current]')].map(a => a.getAttribute('href') + '=' + a.getAttribute('aria-current')).join()")
           == "computadores.html=true", "RTX 3060: menu marca a seção Computadores (aria-current=true)")
        ok(await rp.evaluate("[...document.querySelectorAll('.gm-trilha li')].map(l => l.textContent.trim()).join(' › ')")
           == "Destaques › Computadores › PC Gamer RTX 3060", "RTX 3060: breadcrumb Destaques › Computadores › produto")
        specs = await rp.evaluate("Object.fromEntries([...document.querySelectorAll('.gm-specs dt')].map(d => [d.textContent, d.nextElementSibling.textContent]))")
        ok(len(specs) == 11 and "RTX 3060 12 GB GDDR6" in specs.get("Placa de vídeo", "") and "i5-10400F" in specs.get("Processador", "")
           and "600 W" in specs.get("Fonte", "") and "15 meses" in specs.get("Garantia", ""), f"RTX 3060: ficha técnica do site original (11 itens: {list(specs)[:3]}...)")
        lcp = await rp.evaluate("(() => { const i = document.querySelector('#slot-produto-principal img'); return [i.getAttribute('src'), i.loading, i.getAttribute('fetchpriority'), i.dataset.gmLegado, i.naturalWidth, i.className]; })()")
        ok(lcp[:4] == ["img/produto-pc-gamer-rtx3060.png", "eager", "high", "imgs/pc1.png"] and lcp[4] > 0 and "produto-pc-gamer-rtx3060" in lcp[5]
           and await rp.get_attribute("link[rel=preload][as=image]", "href") == lcp[0], f"RTX 3060: foto do site original como LCP (eager + preload): {lcp[:4]}")
        ok(await rp.is_visible("#slot-mascote-dica-produto .mascote-secundario") and "RTX 3060" in await rp.text_content(".gm-dica__balao"),
           "RTX 3060: mascote no #slot-mascote-dica-produto com dica deste PC")
        rel = await rp.evaluate("[...document.querySelectorAll('.gm-vitrine [data-gm-carrinho]')].map(b => +b.dataset.productId)")
        ok(len(rel) == 4 and 1 not in rel and 4 in rel, f"RTX 3060: relacionados sem o próprio produto, com o PC Ryzen 5 ({rel})")
        ok(await rp.evaluate("document.querySelector('.gm-vitrine a[data-product-id=\"4\"]').getAttribute('href')") == "produto.html", "RTX 3060: card do PC Ryzen 5 leva ao produto.html")
        # Consentimento → page_view atribuído ao produto 1
        await rp.click("[data-gm-consent=aceitar]"); await rp.wait_for_timeout(3200)
        rsess = json.loads(rtrack[0].post_data)["session_id"] if rtrack else None
        rpv = db("select path, product_id from page_views where session_id=%s and path='/pcgamerrtx3060.html'", rsess)
        ok(rpv and rpv[0][1] == 1, f"RTX 3060: page_view no Postgres com product_id=1 ({rpv})")
        # Quantidade (máx. 10) + carrinho
        for _ in range(12):
            await rp.click("[data-gm-qtd-passo='1']")
        ok(await rp.input_value("#gm-qtd-produto") == "10", f"RTX 3060: quantidade limitada a 10 ({await rp.input_value('#gm-qtd-produto')})")
        await rp.fill("#gm-qtd-produto", "2")
        await rp.click("[data-gm-carrinho][data-product-id='1']:not(.btn-gm-add)"); await rp.wait_for_timeout(600)
        cart = await rp.evaluate("JSON.parse(localStorage.getItem('cart'))")
        ok(cart == [{"id": 1, "title": "PC Gamer RTX 3060", "price": 4999, "img": "img/produto-pc-gamer-rtx3060.png", "qty": 2}], f"RTX 3060: carrinho no formato legado ({cart})")
        ok(await rp.text_content("[data-gm-carrinho-contador]") == "2" and await rp.is_visible(".gm-toast"), "RTX 3060: contador = 2 e toast")
        await rp.wait_for_timeout(2500)
        rev = db("select props from analytics_events where session_id=%s and event_type='add_to_cart'", rsess)
        ok(rev and rev[-1][0].get("qty") == 2, f"RTX 3060: add_to_cart no funil com qty=2 ({rev[-1][0] if rev else None})")
        await rp.screenshot(path=f"{SHOTS}/pcgamerrtx3060-desktop.png", full_page=True)
        async with rp.expect_navigation():
            await rp.click("[data-gm-comprar][data-product-id='1']")
        cart = await rp.evaluate("JSON.parse(localStorage.getItem('cart'))")
        ok(rp.url.endswith("/carrinho.html") and [(i["id"], i["qty"]) for i in cart] == [(1, 4)], f"RTX 3060: 'Comprar agora' soma a quantidade e vai ao carrinho ({[(i['id'], i['qty']) for i in cart]})")
        # Celular 390 px
        rcm = await new_context(browser, viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="pt-BR")
        rm = await rcm.new_page()
        rm.on("pageerror", lambda e: rerros.append(str(e)))
        await rm.goto(f"{BASE}/pcgamerrtx3060.html", wait_until="load"); await rm.wait_for_timeout(900)
        ok(await rm.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "RTX 3060 mobile: sem scroll horizontal")
        ok(await rm.evaluate("(() => { const f = document.querySelector('#slot-produto-principal').getBoundingClientRect(), h = document.querySelector('h1').getBoundingClientRect(); return h.top >= f.bottom - 1; })()"),
           "RTX 3060 mobile: foto acima do título (1 coluna)")
        alvos = await rm.evaluate("[...document.querySelectorAll('[data-gm-comprar], .btn-gm-carrinho, [data-gm-favorito], [data-gm-qtd-passo], #gm-qtd-produto')].map(e => e.getBoundingClientRect().height).filter(h => h < 44).length")
        ok(alvos == 0, f"RTX 3060 mobile: botões de compra e quantidade com alvo de toque ≥ 44 px ({alvos} menores)")
        await rm.screenshot(path=f"{SHOTS}/pcgamerrtx3060-mobile.png", full_page=True)
        ok(not rerros, f"RTX 3060: sem erros de JS nem alert() {rerros[:2]}")
        await rcm.close(); await rctx.close()

        # ---------- 9l. Página de produto: PC Gamer Ryzen 9 (Ryzen95900x.html, R10) ----------
        zctx = await new_context(browser, viewport={"width": 1366, "height": 900}, locale="pt-BR")
        zp = await zctx.new_page()
        zerros, ztrack = [], []
        zp.on("pageerror", lambda e: zerros.append(str(e)))
        zp.on("dialog", lambda d: (zerros.append("dialog: " + d.message), asyncio.ensure_future(d.dismiss())))
        zp.on("request", lambda r: r.url.endswith("/api/v1/track") and ztrack.append(r))
        # Chega pela vitrine de Computadores (antes caía na 404)
        await zp.goto(f"{BASE}/computadores.html", wait_until="load")
        async with zp.expect_navigation() as nav:
            await zp.click("a[href='Ryzen95900x.html'][data-track=mais_informacoes]")
        zr = await nav.value
        await zp.wait_for_timeout(800)
        ok(zr.status == 200 and zp.url.endswith("/Ryzen95900x.html"), f"Ryzen 9: 'Mais Informações' de Computadores abre a página (HTTP {zr.status})")
        ok(await zp.text_content("h1") == "PC Gamer Ryzen 9" and await zp.evaluate("document.querySelectorAll('h1').length") == 1, "Ryzen 9: <h1> único com o nome do card original")
        ok(await zp.evaluate("document.body.dataset.productId") == "3", "Ryzen 9: body[data-product-id] = 3 (id do seed)")
        zn, zpreco, zpag, zest = db("select name, price, page_path, stock from products where id=3")[0]
        ok(zn == "PC Gamer Ryzen 9" and zpag == "Ryzen95900x.html", f"Ryzen 9: produto e page_path no Postgres ({zn}, {zpag})")
        ok(await zp.get_attribute(".gm-preco__valor", "value") == f"{zpreco:.2f}" == "7499.00", f"Ryzen 9: preço da página = preço do banco ({zpreco})")
        ok((await zp.text_content(".gm-preco__valor")).replace(" ", " ") == "R$ 7.499,00"
           and "12x de R$ 624,92" in await zp.text_content(".gm-preco__parcelas"), "Ryzen 9: preço e parcelas (7.499 ÷ 12 = 624,92)")
        ok(await zp.evaluate("getComputedStyle(document.querySelector('.gm-preco__valor')).color") == "rgb(0, 255, 153)", "Ryzen 9: preço no verde-neon da marca")
        zld = await zp.evaluate("JSON.parse(document.querySelector('script[type=\"application/ld+json\"]').textContent)['@graph']")
        ok(zld[0]["name"] == "PC Gamer Ryzen 9" and zld[0]["offers"]["price"] == "7499.00" and zld[0]["sku"] == "GM-PC-R9-5900X"
           and zld[0]["offers"]["url"].endswith("/Ryzen95900x.html") and zld[1]["itemListElement"][2]["name"] == "PC Gamer Ryzen 9",
           "Ryzen 9: JSON-LD Product (nome, SKU, 7499.00, URL) + BreadcrumbList")
        ok(await zp.get_attribute("link[rel=canonical]", "href") == "https://www.gamemania.com.br/Ryzen95900x.html"
           and await zp.get_attribute("meta[property='product:price:amount']", "content") == "7499.00"
           and (await zp.get_attribute("meta[property='og:image']", "content")).endswith("/img/produto-pc-gamer-ryzen9-5900x.png"), "Ryzen 9: canonical, preço e imagem no Open Graph")
        ok(await zp.evaluate("[...document.querySelectorAll('#gm-menu [aria-current]')].map(a => a.getAttribute('href') + '=' + a.getAttribute('aria-current')).join()")
           == "computadores.html=true", "Ryzen 9: menu marca a seção Computadores (aria-current=true)")
        ok(await zp.evaluate("[...document.querySelectorAll('.gm-trilha li')].map(l => l.textContent.trim()).join(' › ')")
           == "Destaques › Computadores › PC Gamer Ryzen 9", "Ryzen 9: breadcrumb Destaques › Computadores › produto")
        zspecs = await zp.evaluate("Object.fromEntries([...document.querySelectorAll('.gm-specs dt')].map(d => [d.textContent, d.nextElementSibling.textContent]))")
        ok(len(zspecs) == 11 and zspecs.get("Processador") == "AMD Ryzen 9 5900X" and zspecs.get("Arquitetura") == "Zen 3"
           and zspecs.get("Núcleos / threads") == "12 núcleos / 24 threads" and "4,8 GHz" in zspecs.get("Frequência", "")
           and zspecs.get("Cache") == "64 MB L3" and zspecs.get("TDP") == "105 W" and "AM4" in zspecs.get("Soquete", "")
           and zspecs.get("Memória") == "32 GB de RAM" and zspecs.get("Armazenamento") == "SSD de 1 TB" and "3 anos" in zspecs.get("Garantia", ""),
           f"Ryzen 9: ficha técnica do site original (11 itens: {list(zspecs)[:4]}...)")
        ok("3 anos" in await zp.text_content(".gm-beneficios"), "Ryzen 9: garantia de 3 anos nos benefícios (igual à ficha)")
        zlcp = await zp.evaluate("(() => { const i = document.querySelector('#slot-produto-principal img'); return [i.getAttribute('src'), i.loading, i.getAttribute('fetchpriority'), i.dataset.gmLegado, i.naturalWidth, i.className]; })()")
        ok(zlcp[:4] == ["img/produto-pc-gamer-ryzen9-5900x.png", "eager", "high", "imgs/pc3.png"] and zlcp[4] > 0 and "produto-pc-gamer-ryzen9-5900x" in zlcp[5]
           and await zp.get_attribute("link[rel=preload][as=image]", "href") == zlcp[0], f"Ryzen 9: foto do site original como LCP (eager + preload): {zlcp[:4]}")
        ok(await zp.is_visible("#slot-mascote-dica-produto .mascote-secundario") and "Ryzen 9 5900X" in await zp.text_content(".gm-dica__balao"),
           "Ryzen 9: mascote no #slot-mascote-dica-produto com dica deste PC")
        zrel = await zp.evaluate("[...document.querySelectorAll('.gm-vitrine [data-gm-carrinho]')].map(b => +b.dataset.productId)")
        ok(zrel == [1, 4, 7, 8], f"Ryzen 9: relacionados sem o próprio produto, com o RTX 3060 ({zrel})")
        ok(await zp.evaluate("document.querySelector('.gm-vitrine a[data-product-id=\"1\"]').getAttribute('href')") == "pcgamerrtx3060.html", "Ryzen 9: card do RTX 3060 leva à página dele")
        # Consentimento → page_view atribuído ao produto 3
        await zp.click("[data-gm-consent=aceitar]"); await zp.wait_for_timeout(3200)
        zsess = json.loads(ztrack[0].post_data)["session_id"] if ztrack else None
        zpv = db("select path, product_id from page_views where session_id=%s and path='/Ryzen95900x.html'", zsess)
        ok(zpv and zpv[0][1] == 3, f"Ryzen 9: page_view no Postgres com product_id=3 ({zpv})")
        # Quantidade limitada ao estoque do seed (5)
        for _ in range(8):
            await zp.click("[data-gm-qtd-passo='1']")
        ok(await zp.input_value("#gm-qtd-produto") == str(zest) == "5", f"Ryzen 9: quantidade limitada ao estoque ({await zp.input_value('#gm-qtd-produto')}, estoque {zest})")
        await zp.fill("#gm-qtd-produto", "2")
        await zp.click("[data-gm-carrinho][data-product-id='3']:not(.btn-gm-add)"); await zp.wait_for_timeout(600)
        zcart = await zp.evaluate("JSON.parse(localStorage.getItem('cart'))")
        ok(zcart == [{"id": 3, "title": "PC Gamer Ryzen 9", "price": 7499, "img": "img/produto-pc-gamer-ryzen9-5900x.png", "qty": 2}], f"Ryzen 9: carrinho no formato legado ({zcart})")
        ok(await zp.text_content("[data-gm-carrinho-contador]") == "2" and await zp.is_visible(".gm-toast"), "Ryzen 9: contador = 2 e toast")
        await zp.wait_for_timeout(2500)
        zev = db("select props from analytics_events where session_id=%s and event_type='add_to_cart'", zsess)
        ok(zev and zev[-1][0].get("qty") == 2, f"Ryzen 9: add_to_cart no funil com qty=2 ({zev[-1][0] if zev else None})")
        await zp.screenshot(path=f"{SHOTS}/Ryzen95900x-desktop.png", full_page=True)
        async with zp.expect_navigation():
            await zp.click("[data-gm-comprar][data-product-id='3']")
        zcart = await zp.evaluate("JSON.parse(localStorage.getItem('cart'))")
        ok(zp.url.endswith("/carrinho.html") and [(i["id"], i["qty"]) for i in zcart] == [(3, 4)], f"Ryzen 9: 'Comprar agora' soma a quantidade e vai ao carrinho ({[(i['id'], i['qty']) for i in zcart]})")
        # Celular 390 px
        zcm = await new_context(browser, viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="pt-BR")
        zm = await zcm.new_page()
        zm.on("pageerror", lambda e: zerros.append(str(e)))
        await zm.goto(f"{BASE}/Ryzen95900x.html", wait_until="load"); await zm.wait_for_timeout(900)
        ok(await zm.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Ryzen 9 mobile: sem scroll horizontal")
        ok(await zm.evaluate("(() => { const f = document.querySelector('#slot-produto-principal').getBoundingClientRect(), h = document.querySelector('h1').getBoundingClientRect(); return h.top >= f.bottom - 1; })()"),
           "Ryzen 9 mobile: foto acima do título (1 coluna)")
        zalvos = await zm.evaluate("[...document.querySelectorAll('[data-gm-comprar], .btn-gm-carrinho, [data-gm-favorito], [data-gm-qtd-passo], #gm-qtd-produto')].map(e => e.getBoundingClientRect().height).filter(h => h < 44).length")
        ok(zalvos == 0, f"Ryzen 9 mobile: botões de compra e quantidade com alvo de toque ≥ 44 px ({zalvos} menores)")
        await zm.screenshot(path=f"{SHOTS}/Ryzen95900x-mobile.png", full_page=True)
        ok(not zerros, f"Ryzen 9: sem erros de JS nem alert() {zerros[:2]}")
        await zcm.close(); await zctx.close()

        # ---------- 9m. Página de produto: PC Gamer Nitro X (PCGamerNitro.html, R11) ----------
        nctx = await new_context(browser, viewport={"width": 1366, "height": 900}, locale="pt-BR")
        np_ = await nctx.new_page()
        nerros, ntrack = [], []
        np_.on("pageerror", lambda e: nerros.append(str(e)))
        np_.on("dialog", lambda d: (nerros.append("dialog: " + d.message), asyncio.ensure_future(d.dismiss())))
        np_.on("request", lambda r: r.url.endswith("/api/v1/track") and ntrack.append(r))
        # Chega pela vitrine da home (antes caía na 404)
        await np_.goto(f"{BASE}/index.html", wait_until="load")
        async with np_.expect_navigation() as nav:
            await np_.click("a[href='PCGamerNitro.html'][data-track=mais_informacoes]")
        nr = await nav.value
        await np_.wait_for_timeout(800)
        ok(nr.status == 200 and np_.url.endswith("/PCGamerNitro.html"), f"Nitro X: 'Mais Informações' da home abre a página (HTTP {nr.status})")
        ok(await np_.text_content("h1") == "PC Gamer Nitro X" and await np_.evaluate("document.querySelectorAll('h1').length") == 1, "Nitro X: <h1> único com o nome do produto")
        ok(await np_.evaluate("document.body.dataset.productId") == "7", "Nitro X: body[data-product-id] = 7 (id do seed)")
        nn, npreco, npag, nest = db("select name, price, page_path, stock from products where id=7")[0]
        ok(nn == "PC Gamer Nitro X" and npag == "PCGamerNitro.html", f"Nitro X: produto e page_path no Postgres ({nn}, {npag})")
        ok(await np_.get_attribute(".gm-preco__valor", "value") == f"{npreco:.2f}" == "7499.00", f"Nitro X: preço da página = preço do banco ({npreco})")
        ok((await np_.text_content(".gm-preco__valor")).replace("\u00a0", " ") == "R$ 7.499,00"
           and "12x de R$ 624,92" in await np_.text_content(".gm-preco__parcelas"), "Nitro X: preço e parcelas (7.499 ÷ 12 = 624,92)")
        ok(await np_.evaluate("getComputedStyle(document.querySelector('.gm-preco__valor')).color") == "rgb(0, 255, 153)", "Nitro X: preço no verde-neon da marca")
        nld = await np_.evaluate("JSON.parse(document.querySelector('script[type=\"application/ld+json\"]').textContent)['@graph']")
        ok(nld[0]["name"] == "PC Gamer Nitro X" and nld[0]["offers"]["price"] == "7499.00" and nld[0]["sku"] == "GM-PC-NITRO-X"
           and nld[0]["offers"]["url"].endswith("/PCGamerNitro.html") and nld[1]["itemListElement"][2]["name"] == "PC Gamer Nitro X",
           "Nitro X: JSON-LD Product (nome, SKU, 7499.00, URL) + BreadcrumbList")
        ok(await np_.get_attribute("link[rel=canonical]", "href") == "https://www.gamemania.com.br/PCGamerNitro.html"
           and await np_.get_attribute("meta[property='product:price:amount']", "content") == "7499.00"
           and (await np_.get_attribute("meta[property='og:image']", "content")).endswith("/img/produto-pc-gamer-nitro-x.png"), "Nitro X: canonical, preço e imagem no Open Graph")
        ok(await np_.evaluate("[...document.querySelectorAll('#gm-menu [aria-current]')].map(a => a.getAttribute('href') + '=' + a.getAttribute('aria-current')).join()")
           == "computadores.html=true", "Nitro X: menu marca a seção Computadores (aria-current=true)")
        ok(await np_.evaluate("[...document.querySelectorAll('.gm-trilha li')].map(l => l.textContent.trim()).join(' › ')")
           == "Destaques › Computadores › PC Gamer Nitro X", "Nitro X: breadcrumb Destaques › Computadores › produto")
        nspecs = await np_.evaluate("Object.fromEntries([...document.querySelectorAll('.gm-specs dt')].map(d => [d.textContent, d.nextElementSibling.textContent]))")
        ok(len(nspecs) == 11 and "Ryzen 7 5700X" in nspecs.get("Processador", "") and "B550-PLUS" in nspecs.get("Placa-mãe", "")
           and nspecs.get("Memória") == "32 GB (2x16 GB) DDR4 3600 MHz" and nspecs.get("Armazenamento") == "SSD NVMe M.2 1 TB"
           and nspecs.get("Placa de vídeo") == "NVIDIA GeForce RTX 4060 Ti 8 GB GDDR6" and nspecs.get("Fonte") == "650 W 80 Plus Bronze"
           and "vidro temperado" in nspecs.get("Gabinete", "") and nspecs.get("Sistema operacional") == "Linux Ubuntu 24.04 LTS"
           and "Wi-Fi 6" in nspecs.get("Conectividade", "") and "USB-C" in nspecs.get("Portas", "") and "2 anos na montagem" in nspecs.get("Garantia", ""),
           f"Nitro X: ficha técnica do site original (11 itens: {list(nspecs)[:4]}...)")
        ok("2 anos na montagem" in await np_.text_content(".gm-beneficios"), "Nitro X: garantia dos benefícios igual à ficha")
        # Card da vitrine com a mesma placa de vídeo da ficha (antes dizia RTX 4070)
        ok(await np_.evaluate("fetch('index.html').then(r => r.text()).then(t => t.includes('5700X, 32GB RAM, SSD NVMe 1TB, RTX 4060 Ti') && !t.includes('5700X, 32GB RAM, SSD NVMe 1TB, RTX 4070'))"),
           "Nitro X: card da home mostra a RTX 4060 Ti da ficha técnica")
        nlcp = await np_.evaluate("(() => { const i = document.querySelector('#slot-produto-principal img'); return [i.getAttribute('src'), i.loading, i.getAttribute('fetchpriority'), i.dataset.gmLegado, i.naturalWidth, i.className]; })()")
        ok(nlcp[:4] == ["img/produto-pc-gamer-nitro-x.png", "eager", "high", "imgs/pc7.png"] and nlcp[4] > 0 and "produto-pc-gamer-nitro-x" in nlcp[5]
           and await np_.get_attribute("link[rel=preload][as=image]", "href") == nlcp[0], f"Nitro X: foto do site original como LCP (eager + preload): {nlcp[:4]}")
        ok(await np_.is_visible("#slot-mascote-dica-produto .mascote-secundario") and "RTX 4060 Ti" in await np_.text_content(".gm-dica__balao"),
           "Nitro X: mascote no #slot-mascote-dica-produto com dica deste PC")
        nrel = await np_.evaluate("[...document.querySelectorAll('.gm-vitrine [data-gm-carrinho]')].map(b => +b.dataset.productId)")
        ok(nrel == [1, 4, 3, 8], f"Nitro X: relacionados sem o próprio produto, com o Ryzen 9 ({nrel})")
        ok(await np_.evaluate("document.querySelector('.gm-vitrine a[data-product-id=\"3\"]').getAttribute('href')") == "Ryzen95900x.html"
           and await np_.evaluate("document.querySelector('.gm-vitrine [data-gm-carrinho][data-product-id=\"3\"]').dataset.trackOrigem") == "relacionados",
           "Nitro X: card do Ryzen 9 leva à página dele (origem 'relacionados' no funil)")
        # Consentimento → page_view atribuído ao produto 7
        await np_.click("[data-gm-consent=aceitar]"); await np_.wait_for_timeout(3200)
        nsess = json.loads(ntrack[0].post_data)["session_id"] if ntrack else None
        npv = db("select path, product_id from page_views where session_id=%s and path='/PCGamerNitro.html'", nsess)
        ok(npv and npv[0][1] == 7, f"Nitro X: page_view no Postgres com product_id=7 ({npv})")
        # Quantidade limitada ao estoque do seed (4)
        for _ in range(7):
            await np_.click("[data-gm-qtd-passo='1']")
        ok(await np_.input_value("#gm-qtd-produto") == str(nest) == "4", f"Nitro X: quantidade limitada ao estoque ({await np_.input_value('#gm-qtd-produto')}, estoque {nest})")
        await np_.fill("#gm-qtd-produto", "2")
        await np_.click("[data-gm-carrinho][data-product-id='7']:not(.btn-gm-add)"); await np_.wait_for_timeout(600)
        ncart = await np_.evaluate("JSON.parse(localStorage.getItem('cart'))")
        ok(ncart == [{"id": 7, "title": "PC Gamer Nitro X", "price": 7499, "img": "img/produto-pc-gamer-nitro-x.png", "qty": 2}], f"Nitro X: carrinho no formato legado ({ncart})")
        ok(await np_.text_content("[data-gm-carrinho-contador]") == "2" and await np_.is_visible(".gm-toast"), "Nitro X: contador = 2 e toast")
        await np_.wait_for_timeout(2500)
        nev = db("select props from analytics_events where session_id=%s and event_type='add_to_cart'", nsess)
        ok(nev and nev[-1][0].get("qty") == 2, f"Nitro X: add_to_cart no funil com qty=2 ({nev[-1][0] if nev else None})")
        await np_.screenshot(path=f"{SHOTS}/PCGamerNitro-desktop.png", full_page=True)
        async with np_.expect_navigation():
            await np_.click("[data-gm-comprar][data-product-id='7']")
        ncart = await np_.evaluate("JSON.parse(localStorage.getItem('cart'))")
        ok(np_.url.endswith("/carrinho.html") and [(i["id"], i["qty"]) for i in ncart] == [(7, 4)], f"Nitro X: 'Comprar agora' soma a quantidade e vai ao carrinho ({[(i['id'], i['qty']) for i in ncart]})")
        # Celular 390 px
        ncm = await new_context(browser, viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="pt-BR")
        nm = await ncm.new_page()
        nm.on("pageerror", lambda e: nerros.append(str(e)))
        await nm.goto(f"{BASE}/PCGamerNitro.html", wait_until="load"); await nm.wait_for_timeout(900)
        ok(await nm.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Nitro X mobile: sem scroll horizontal")
        ok(await nm.evaluate("(() => { const f = document.querySelector('#slot-produto-principal').getBoundingClientRect(), h = document.querySelector('h1').getBoundingClientRect(); return h.top >= f.bottom - 1; })()"),
           "Nitro X mobile: foto acima do título (1 coluna)")
        nalvos = await nm.evaluate("[...document.querySelectorAll('[data-gm-comprar], .btn-gm-carrinho, [data-gm-favorito], [data-gm-qtd-passo], #gm-qtd-produto')].map(e => e.getBoundingClientRect().height).filter(h => h < 44).length")
        ok(nalvos == 0, f"Nitro X mobile: botões de compra e quantidade com alvo de toque ≥ 44 px ({nalvos} menores)")
        await nm.screenshot(path=f"{SHOTS}/PCGamerNitro-mobile.png", full_page=True)
        ok(not nerros, f"Nitro X: sem erros de JS nem alert() {nerros[:2]}")
        await ncm.close(); await nctx.close()

        # ---------- 9n. Página de produto: PC Profissional (pcprofissional.html, R12) ----------
        pctx = await new_context(browser, viewport={"width": 1366, "height": 900}, locale="pt-BR")
        pp = await pctx.new_page()
        perros, ptrack = [], []
        pp.on("pageerror", lambda e: perros.append(str(e)))
        pp.on("dialog", lambda d: (perros.append("dialog: " + d.message), asyncio.ensure_future(d.dismiss())))
        pp.on("request", lambda r: r.url.endswith("/api/v1/track") and ptrack.append(r))
        # Chega pela vitrine de Computadores (antes caía na 404)
        await pp.goto(f"{BASE}/computadores.html", wait_until="load")
        async with pp.expect_navigation() as nav:
            await pp.click("a[href='pcprofissional.html'][data-track=mais_informacoes]")
        pr = await nav.value
        await pp.wait_for_timeout(800)
        ok(pr.status == 200 and pp.url.endswith("/pcprofissional.html"), f"PC Profissional: 'Mais Informações' de Computadores abre a página (HTTP {pr.status})")
        ok(await pp.text_content("h1") == "PC Profissional" and await pp.evaluate("document.querySelectorAll('h1').length") == 1, "PC Profissional: <h1> único com o nome do produto")
        ok(await pp.evaluate("document.body.dataset.productId") == "8", "PC Profissional: body[data-product-id] = 8 (id do seed)")
        pn, ppreco, ppag, pest = db("select name, price, page_path, stock from products where id=8")[0]
        ok(pn == "PC Profissional" and ppag == "pcprofissional.html", f"PC Profissional: produto e page_path no Postgres ({pn}, {ppag})")
        ok(await pp.get_attribute(".gm-preco__valor", "value") == f"{ppreco:.2f}" == "5299.00", f"PC Profissional: preço da página = preço do banco ({ppreco})")
        ok((await pp.text_content(".gm-preco__valor")).replace(" ", " ") == "R$ 5.299,00"
           and "12x de R$ 441,58" in await pp.text_content(".gm-preco__parcelas"), "PC Profissional: preço e parcelas (5.299 ÷ 12 = 441,58)")
        ok(await pp.evaluate("getComputedStyle(document.querySelector('.gm-preco__valor')).color") == "rgb(0, 255, 153)", "PC Profissional: preço no verde-neon da marca")
        pld = await pp.evaluate("JSON.parse(document.querySelector('script[type=\"application/ld+json\"]').textContent)['@graph']")
        ok(pld[0]["name"] == "PC Profissional" and pld[0]["offers"]["price"] == "5299.00" and pld[0]["sku"] == "GM-PC-PRO-I7"
           and pld[0]["offers"]["url"].endswith("/pcprofissional.html") and pld[1]["itemListElement"][2]["name"] == "PC Profissional",
           "PC Profissional: JSON-LD Product (nome, SKU, 5299.00, URL) + BreadcrumbList")
        ok(await pp.get_attribute("link[rel=canonical]", "href") == "https://www.gamemania.com.br/pcprofissional.html"
           and await pp.get_attribute("meta[property='product:price:amount']", "content") == "5299.00"
           and (await pp.get_attribute("meta[property='og:image']", "content")).endswith("/img/produto-pc-profissional.png"), "PC Profissional: canonical, preço e imagem no Open Graph")
        ok(await pp.evaluate("[...document.querySelectorAll('#gm-menu [aria-current]')].map(a => a.getAttribute('href') + '=' + a.getAttribute('aria-current')).join()")
           == "computadores.html=true", "PC Profissional: menu marca a seção Computadores (aria-current=true)")
        ok(await pp.evaluate("[...document.querySelectorAll('.gm-trilha li')].map(l => l.textContent.trim()).join(' › ')")
           == "Destaques › Computadores › PC Profissional", "PC Profissional: breadcrumb Destaques › Computadores › produto")
        pspecs = await pp.evaluate("Object.fromEntries([...document.querySelectorAll('.gm-specs dt')].map(d => [d.textContent, d.nextElementSibling.textContent]))")
        ok(len(pspecs) == 11 and "i7-12700" in pspecs.get("Processador", "") and "20 threads" in pspecs.get("Processador", "")
           and pspecs.get("Placa-mãe") == "ASUS PRIME B660-PLUS D4" and pspecs.get("Memória") == "32 GB (2x16 GB) DDR5 5200 MHz"
           and pspecs.get("Armazenamento") == "SSD NVMe M.2 1 TB" and pspecs.get("Placa de vídeo") == "NVIDIA GeForce RTX 4070 12 GB GDDR6X"
           and pspecs.get("Fonte") == "750 W 80 Plus Gold modular" and "vidro temperado" in pspecs.get("Gabinete", "")
           and pspecs.get("Sistema operacional") == "Windows 11 Pro 64 bits" and "Ethernet 2.5G" in pspecs.get("Conectividade", "")
           and "USB 2.0" in pspecs.get("Portas", "") and "4 anos" in pspecs.get("Garantia", ""),
           f"PC Profissional: ficha técnica do site original (11 itens: {list(pspecs)[:4]}...)")
        ok("4 anos nos principais componentes" in await pp.text_content(".gm-beneficios"), "PC Profissional: garantia dos benefícios igual à ficha (4 anos)")
        # Cards das vitrines sem o "HD 2TB" que a ficha não tem
        ok(await pp.evaluate("""Promise.all(['index.html', 'computadores.html', 'produto.html', 'pcgamerrtx3060.html', 'Ryzen95900x.html', 'PCGamerNitro.html'].map(p =>
              fetch(p).then(r => r.text()).then(t => t.includes('i7-12700, 32GB DDR5, SSD NVMe 1TB, RTX 4070') && !t.includes('HD 2TB')))).then(v => v.every(Boolean))"""),
           "PC Profissional: cards das 6 vitrines com SSD NVMe 1TB + RTX 4070 da ficha (sem 'HD 2TB')")
        plcp = await pp.evaluate("(() => { const i = document.querySelector('#slot-produto-principal img'); return [i.getAttribute('src'), i.loading, i.getAttribute('fetchpriority'), i.dataset.gmLegado, i.naturalWidth, i.className]; })()")
        ok(plcp[:4] == ["img/produto-pc-profissional.png", "eager", "high", "imgs/pc8.png"] and plcp[4] > 0 and "produto-pc-profissional" in plcp[5]
           and await pp.get_attribute("link[rel=preload][as=image]", "href") == plcp[0], f"PC Profissional: foto do site original como LCP (eager + preload): {plcp[:4]}")
        ok(await pp.is_visible("#slot-mascote-dica-produto .mascote-secundario") and "i7-12700" in await pp.text_content(".gm-dica__balao"),
           "PC Profissional: mascote no #slot-mascote-dica-produto com dica deste PC")
        prel = await pp.evaluate("[...document.querySelectorAll('.gm-vitrine [data-gm-carrinho]')].map(b => +b.dataset.productId)")
        ok(prel == [1, 4, 3, 7], f"PC Profissional: relacionados sem o próprio produto, com o Nitro X ({prel})")
        ok(await pp.evaluate("document.querySelector('.gm-vitrine a[data-product-id=\"7\"]').getAttribute('href')") == "PCGamerNitro.html"
           and await pp.evaluate("document.querySelector('.gm-vitrine [data-gm-carrinho][data-product-id=\"7\"]').dataset.trackOrigem") == "relacionados",
           "PC Profissional: card do Nitro X leva à página dele (origem 'relacionados' no funil)")
        # Consentimento → page_view atribuído ao produto 8
        await pp.click("[data-gm-consent=aceitar]"); await pp.wait_for_timeout(3200)
        psess = json.loads(ptrack[0].post_data)["session_id"] if ptrack else None
        ppv = db("select path, product_id from page_views where session_id=%s and path='/pcprofissional.html'", psess)
        ok(ppv and ppv[0][1] == 8, f"PC Profissional: page_view no Postgres com product_id=8 ({ppv})")
        # Quantidade limitada ao estoque do seed (6)
        for _ in range(9):
            await pp.click("[data-gm-qtd-passo='1']")
        ok(await pp.input_value("#gm-qtd-produto") == str(pest) == "6", f"PC Profissional: quantidade limitada ao estoque ({await pp.input_value('#gm-qtd-produto')}, estoque {pest})")
        await pp.fill("#gm-qtd-produto", "3")
        await pp.click("[data-gm-carrinho][data-product-id='8']:not(.btn-gm-add)"); await pp.wait_for_timeout(600)
        pcart = await pp.evaluate("JSON.parse(localStorage.getItem('cart'))")
        ok(pcart == [{"id": 8, "title": "PC Profissional", "price": 5299, "img": "img/produto-pc-profissional.png", "qty": 3}], f"PC Profissional: carrinho no formato legado ({pcart})")
        ok(await pp.text_content("[data-gm-carrinho-contador]") == "3" and await pp.is_visible(".gm-toast"), "PC Profissional: contador = 3 e toast")
        await pp.wait_for_timeout(2500)
        pev = db("select props from analytics_events where session_id=%s and event_type='add_to_cart'", psess)
        ok(pev and pev[-1][0].get("qty") == 3, f"PC Profissional: add_to_cart no funil com qty=3 ({pev[-1][0] if pev else None})")
        await pp.screenshot(path=f"{SHOTS}/pcprofissional-desktop.png", full_page=True)
        async with pp.expect_navigation():
            await pp.click("[data-gm-comprar][data-product-id='8']")
        pcart = await pp.evaluate("JSON.parse(localStorage.getItem('cart'))")
        ok(pp.url.endswith("/carrinho.html") and [(i["id"], i["qty"]) for i in pcart] == [(8, 6)], f"PC Profissional: 'Comprar agora' soma a quantidade (até o estoque) e vai ao carrinho ({[(i['id'], i['qty']) for i in pcart]})")
        # Celular 390 px
        pcm = await new_context(browser, viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="pt-BR")
        pm = await pcm.new_page()
        pm.on("pageerror", lambda e: perros.append(str(e)))
        await pm.goto(f"{BASE}/pcprofissional.html", wait_until="load"); await pm.wait_for_timeout(900)
        ok(await pm.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "PC Profissional mobile: sem scroll horizontal")
        ok(await pm.evaluate("(() => { const f = document.querySelector('#slot-produto-principal').getBoundingClientRect(), h = document.querySelector('h1').getBoundingClientRect(); return h.top >= f.bottom - 1; })()"),
           "PC Profissional mobile: foto acima do título (1 coluna)")
        palvos = await pm.evaluate("[...document.querySelectorAll('[data-gm-comprar], .btn-gm-carrinho, [data-gm-favorito], [data-gm-qtd-passo], #gm-qtd-produto')].map(e => e.getBoundingClientRect().height).filter(h => h < 44).length")
        ok(palvos == 0, f"PC Profissional mobile: botões de compra e quantidade com alvo de toque ≥ 44 px ({palvos} menores)")
        await pm.screenshot(path=f"{SHOTS}/pcprofissional-mobile.png", full_page=True)
        ok(not perros, f"PC Profissional: sem erros de JS nem alert() {perros[:2]}")
        await pcm.close(); await pctx.close()

        # ---------- 9o. Página de produto: Computador Gamer (ComputadorGamer.html, R13) ----------
        gctx = await new_context(browser, viewport={"width": 1366, "height": 900}, locale="pt-BR")
        gp = await gctx.new_page()
        gerros, gtrack = [], []
        gp.on("pageerror", lambda e: gerros.append(str(e)))
        gp.on("dialog", lambda d: (gerros.append("dialog: " + d.message), asyncio.ensure_future(d.dismiss())))
        gp.on("request", lambda r: r.url.endswith("/api/v1/track") and gtrack.append(r))
        # Chega pela home (antes caía na 404)
        await gp.goto(f"{BASE}/index.html", wait_until="load")
        async with gp.expect_navigation() as nav:
            await gp.click("a[href='ComputadorGamer.html'][data-track=mais_informacoes]")
        gr = await nav.value
        await gp.wait_for_timeout(800)
        ok(gr.status == 200 and gp.url.endswith("/ComputadorGamer.html"), f"Computador Gamer: 'Mais Informações' da home abre a página (HTTP {gr.status})")
        ok(await gp.text_content("h1") == "Computador Gamer" and await gp.evaluate("document.querySelectorAll('h1').length") == 1, "Computador Gamer: <h1> único com o nome do produto")
        ok(await gp.evaluate("document.body.dataset.productId") == "9", "Computador Gamer: body[data-product-id] = 9 (id do seed)")
        gn, gpreco, gpag, gest = db("select name, price, page_path, stock from products where id=9")[0]
        ok(gn == "Computador Gamer" and gpag == "ComputadorGamer.html", f"Computador Gamer: produto e page_path no Postgres ({gn}, {gpag})")
        ok(await gp.get_attribute(".gm-preco__valor", "value") == f"{gpreco:.2f}" == "4499.00", f"Computador Gamer: preço da página = preço do banco ({gpreco})")
        ok((await gp.text_content(".gm-preco__valor")).replace("\u00a0", " ") == "R$ 4.499,00"
           and "12x de R$ 374,92" in await gp.text_content(".gm-preco__parcelas"), "Computador Gamer: preço e parcelas (4.499 ÷ 12 = 374,92)")
        ok(await gp.evaluate("getComputedStyle(document.querySelector('.gm-preco__valor')).color") == "rgb(0, 255, 153)", "Computador Gamer: preço no verde-neon da marca")
        gld = await gp.evaluate("JSON.parse(document.querySelector('script[type=\"application/ld+json\"]').textContent)['@graph']")
        ok(gld[0]["name"] == "Computador Gamer" and gld[0]["offers"]["price"] == "4499.00" and gld[0]["sku"] == "GM-PC-GAMER-I7"
           and gld[0]["offers"]["url"].endswith("/ComputadorGamer.html") and gld[1]["itemListElement"][2]["name"] == "Computador Gamer",
           "Computador Gamer: JSON-LD Product (nome, SKU, 4499.00, URL) + BreadcrumbList")
        ok(await gp.get_attribute("link[rel=canonical]", "href") == "https://www.gamemania.com.br/ComputadorGamer.html"
           and await gp.get_attribute("meta[property='product:price:amount']", "content") == "4499.00"
           and (await gp.get_attribute("meta[property='og:image']", "content")).endswith("/img/produto-computador-gamer.png"), "Computador Gamer: canonical, preço e imagem no Open Graph")
        ok(await gp.evaluate("[...document.querySelectorAll('#gm-menu [aria-current]')].map(a => a.getAttribute('href') + '=' + a.getAttribute('aria-current')).join()")
           == "computadores.html=true", "Computador Gamer: menu marca a seção Computadores (aria-current=true)")
        ok(await gp.evaluate("[...document.querySelectorAll('.gm-trilha li')].map(l => l.textContent.trim()).join(' › ')")
           == "Destaques › Computadores › Computador Gamer", "Computador Gamer: breadcrumb Destaques › Computadores › produto")
        gspecs = await gp.evaluate("Object.fromEntries([...document.querySelectorAll('.gm-specs dt')].map(d => [d.textContent, d.nextElementSibling.textContent]))")
        ok(len(gspecs) == 11 and "i7-11700" in gspecs.get("Processador", "") and "16 threads" in gspecs.get("Processador", "")
           and gspecs.get("Placa-mãe") == "Gigabyte B560M DS3H AC" and gspecs.get("Memória") == "16 GB (2x8 GB) DDR4 3200 MHz"
           and gspecs.get("Armazenamento") == "SSD NVMe M.2 512 GB" and gspecs.get("Placa de vídeo") == "NVIDIA GeForce RTX 3060 12 GB GDDR6"
           and gspecs.get("Fonte") == "650 W 80 Plus Bronze" and "aço" in gspecs.get("Gabinete", "")
           and gspecs.get("Sistema operacional") == "Windows 11 Home 64 bits" and "Bluetooth 5.0" in gspecs.get("Conectividade", "")
           and "USB-C" in gspecs.get("Portas", "") and "1 ano na montagem" in gspecs.get("Garantia", ""),
           f"Computador Gamer: ficha técnica do site original (11 itens: {list(gspecs)[:4]}...)")
        ok("3 anos nos principais componentes e 1 ano na montagem" in await gp.text_content(".gm-beneficios"), "Computador Gamer: garantia dos benefícios igual à ficha (3 anos + 1 ano)")
        glcp = await gp.evaluate("(() => { const i = document.querySelector('#slot-produto-principal img'); return [i.getAttribute('src'), i.loading, i.getAttribute('fetchpriority'), i.dataset.gmLegado, i.naturalWidth, i.className]; })()")
        ok(glcp[:4] == ["img/produto-computador-gamer.png", "eager", "high", "imgs/pc9.png"] and glcp[4] > 0 and "produto-computador-gamer" in glcp[5]
           and await gp.get_attribute("link[rel=preload][as=image]", "href") == glcp[0], f"Computador Gamer: foto do site original como LCP (eager + preload): {glcp[:4]}")
        ok(await gp.is_visible("#slot-mascote-dica-produto .mascote-secundario") and "i7-11700" in await gp.text_content(".gm-dica__balao"),
           "Computador Gamer: mascote no #slot-mascote-dica-produto com dica deste PC")
        grel = await gp.evaluate("[...document.querySelectorAll('.gm-vitrine [data-gm-carrinho]')].map(b => +b.dataset.productId)")
        ok(grel == [1, 4, 8, 7], f"Computador Gamer: relacionados sem o próprio produto, com o PC Profissional ({grel})")
        ok(await gp.evaluate("document.querySelector('.gm-vitrine a[data-product-id=\"8\"]').getAttribute('href')") == "pcprofissional.html"
           and await gp.evaluate("[...document.querySelectorAll('.gm-vitrine [data-gm-carrinho]')].every(b => b.dataset.trackOrigem === 'relacionados')"),
           "Computador Gamer: card do PC Profissional leva à página dele (origem 'relacionados' em todos)")
        # Consentimento → page_view atribuído ao produto 9
        await gp.click("[data-gm-consent=aceitar]"); await gp.wait_for_timeout(3200)
        gsess = json.loads(gtrack[0].post_data)["session_id"] if gtrack else None
        gpv = db("select path, product_id from page_views where session_id=%s and path='/ComputadorGamer.html'", gsess)
        ok(gpv and gpv[0][1] == 9, f"Computador Gamer: page_view no Postgres com product_id=9 ({gpv})")
        # Quantidade limitada ao estoque do seed (7)
        for _ in range(9):
            await gp.click("[data-gm-qtd-passo='1']")
        ok(await gp.input_value("#gm-qtd-produto") == str(gest) == "7", f"Computador Gamer: quantidade limitada ao estoque ({await gp.input_value('#gm-qtd-produto')}, estoque {gest})")
        await gp.fill("#gm-qtd-produto", "4")
        await gp.click("[data-gm-carrinho][data-product-id='9']:not(.btn-gm-add)"); await gp.wait_for_timeout(600)
        gcart = await gp.evaluate("JSON.parse(localStorage.getItem('cart'))")
        ok(gcart == [{"id": 9, "title": "Computador Gamer", "price": 4499, "img": "img/produto-computador-gamer.png", "qty": 4}], f"Computador Gamer: carrinho no formato legado ({gcart})")
        ok(await gp.text_content("[data-gm-carrinho-contador]") == "4" and await gp.is_visible(".gm-toast"), "Computador Gamer: contador = 4 e toast")
        await gp.wait_for_timeout(2500)
        gev = db("select props from analytics_events where session_id=%s and event_type='add_to_cart'", gsess)
        ok(gev and gev[-1][0].get("qty") == 4, f"Computador Gamer: add_to_cart no funil com qty=4 ({gev[-1][0] if gev else None})")
        await gp.screenshot(path=f"{SHOTS}/ComputadorGamer-desktop.png", full_page=True)
        async with gp.expect_navigation():
            await gp.click("[data-gm-comprar][data-product-id='9']")
        gcart = await gp.evaluate("JSON.parse(localStorage.getItem('cart'))")
        ok(gp.url.endswith("/carrinho.html") and [(i["id"], i["qty"]) for i in gcart] == [(9, 7)], f"Computador Gamer: 'Comprar agora' soma 4 + 4 limitado ao estoque 7 e vai ao carrinho ({[(i['id'], i['qty']) for i in gcart]})")
        # Celular 390 px
        gcm = await new_context(browser, viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="pt-BR")
        gm = await gcm.new_page()
        gm.on("pageerror", lambda e: gerros.append(str(e)))
        await gm.goto(f"{BASE}/ComputadorGamer.html", wait_until="load"); await gm.wait_for_timeout(900)
        ok(await gm.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Computador Gamer mobile: sem scroll horizontal")
        ok(await gm.evaluate("(() => { const f = document.querySelector('#slot-produto-principal').getBoundingClientRect(), h = document.querySelector('h1').getBoundingClientRect(); return h.top >= f.bottom - 1; })()"),
           "Computador Gamer mobile: foto acima do título (1 coluna)")
        galvos = await gm.evaluate("[...document.querySelectorAll('[data-gm-comprar], .btn-gm-carrinho, [data-gm-favorito], [data-gm-qtd-passo], #gm-qtd-produto')].map(e => e.getBoundingClientRect().height).filter(h => h < 44).length")
        ok(galvos == 0, f"Computador Gamer mobile: botões de compra e quantidade com alvo de toque ≥ 44 px ({galvos} menores)")
        await gm.screenshot(path=f"{SHOTS}/ComputadorGamer-mobile.png", full_page=True)
        ok(not gerros, f"Computador Gamer: sem erros de JS nem alert() {gerros[:2]}")
        await gcm.close(); await gctx.close()

        # ---------- 9p. Página de produto: Notebook Intel (NotebookIntel.html, R14) ----------
        nctx = await new_context(browser, viewport={"width": 1366, "height": 900}, locale="pt-BR")
        np_ = await nctx.new_page()
        nerros, ntrack = [], []
        np_.on("pageerror", lambda e: nerros.append(str(e)))
        np_.on("dialog", lambda d: (nerros.append("dialog: " + d.message), asyncio.ensure_future(d.dismiss())))
        np_.on("request", lambda r: r.url.endswith("/api/v1/track") and ntrack.append(r))
        # Chega pela categoria Computadores (antes caía na 404)
        await np_.goto(f"{BASE}/computadores.html", wait_until="load")
        ok(await np_.evaluate("[...document.querySelectorAll('.gm-card-produto')].filter(c => c.querySelector('[data-product-id=\"5\"]')).every(c => c.querySelector('.gm-card-produto__specs').textContent === 'Intel i3-10100F, 8GB RAM, SSD 480GB')"),
           "Notebook Intel: card de Computadores com o SSD de 480 GB da ficha (antes 256 GB)")
        async with np_.expect_navigation() as nav:
            await np_.click("a[href='NotebookIntel.html'][data-track=mais_informacoes]")
        nr = await nav.value
        await np_.wait_for_timeout(800)
        ok(nr.status == 200 and np_.url.endswith("/NotebookIntel.html"), f"Notebook Intel: 'Mais Informações' de Computadores abre a página (HTTP {nr.status})")
        ok(await np_.text_content("h1") == "Notebook Intel" and await np_.evaluate("document.querySelectorAll('h1').length") == 1, "Notebook Intel: <h1> único com o nome do produto")
        ok(await np_.evaluate("document.body.dataset.productId") == "5", "Notebook Intel: body[data-product-id] = 5 (id do seed)")
        nn, npreco, npag, nest = db("select name, price, page_path, stock from products where id=5")[0]
        ok(nn == "Notebook Intel" and npag == "NotebookIntel.html", f"Notebook Intel: produto e page_path no Postgres ({nn}, {npag})")
        ok(await np_.get_attribute(".gm-preco__valor", "value") == f"{npreco:.2f}" == "2199.00", f"Notebook Intel: preço da página = preço do banco ({npreco})")
        ok((await np_.text_content(".gm-preco__valor")).replace(" ", " ") == "R$ 2.199,00"
           and "12x de R$ 183,25" in await np_.text_content(".gm-preco__parcelas"), "Notebook Intel: preço e parcelas (2.199 ÷ 12 = 183,25)")
        ok(await np_.evaluate("getComputedStyle(document.querySelector('.gm-preco__valor')).color") == "rgb(0, 255, 153)", "Notebook Intel: preço no verde-neon da marca")
        nld = await np_.evaluate("JSON.parse(document.querySelector('script[type=\"application/ld+json\"]').textContent)['@graph']")
        ok(nld[0]["name"] == "Notebook Intel" and nld[0]["offers"]["price"] == "2199.00" and nld[0]["sku"] == "GM-NB-I3"
           and nld[0]["offers"]["url"].endswith("/NotebookIntel.html") and nld[1]["itemListElement"][2]["name"] == "Notebook Intel",
           "Notebook Intel: JSON-LD Product (nome, SKU, 2199.00, URL) + BreadcrumbList")
        ok(await np_.get_attribute("link[rel=canonical]", "href") == "https://www.gamemania.com.br/NotebookIntel.html"
           and await np_.get_attribute("meta[property='product:price:amount']", "content") == "2199.00"
           and (await np_.get_attribute("meta[property='og:image']", "content")).endswith("/img/produto-notebook-intel.png"), "Notebook Intel: canonical, preço e imagem no Open Graph")
        ok(await np_.evaluate("[...document.querySelectorAll('#gm-menu [aria-current]')].map(a => a.getAttribute('href') + '=' + a.getAttribute('aria-current')).join()")
           == "computadores.html=true", "Notebook Intel: menu marca a seção Computadores (aria-current=true)")
        ok(await np_.evaluate("[...document.querySelectorAll('.gm-trilha li')].map(l => l.textContent.trim()).join(' › ')")
           == "Destaques › Computadores › Notebook Intel", "Notebook Intel: breadcrumb Destaques › Computadores › produto")
        nspecs = await np_.evaluate("[...document.querySelectorAll('.gm-specs dt')].map(d => [d.textContent, d.nextElementSibling.textContent])")
        ok([k for k, _ in nspecs] == ["Processador", "Placa de vídeo", "Memória", "Armazenamento", "Placa-mãe", "Fonte",
                                      "Sistema operacional", "Conectividade", "Portas", "Garantia"],
           f"Notebook Intel: ficha com os 10 itens do site original, na mesma ordem ({[k for k, _ in nspecs][:3]}...)")
        nsd = dict(nspecs)
        ok("i3-10100F" in nsd["Processador"] and "8 threads" in nsd["Processador"] and nsd["Placa de vídeo"] == "Integrada Intel UHD Graphics 630"
           and nsd["Memória"] == "8 GB DDR4 2666 MHz" and nsd["Armazenamento"] == "SSD 480 GB SATA" and nsd["Placa-mãe"] == "H410M"
           and nsd["Fonte"] == "450 W 80 Plus White" and nsd["Sistema operacional"] == "Linux Ubuntu 24.04 LTS"
           and "Bluetooth 4.2" in nsd["Conectividade"] and "VGA" in nsd["Portas"] and "suporte técnico remoto" in nsd["Garantia"],
           "Notebook Intel: valores da ficha iguais aos do legado/NotebookIntel.html")
        ok("1 ano de garantia total com suporte técnico remoto" in await np_.text_content(".gm-beneficios"), "Notebook Intel: garantia dos benefícios igual à ficha (1 ano)")
        nlcp = await np_.evaluate("(() => { const i = document.querySelector('#slot-produto-principal img'); return [i.getAttribute('src'), i.loading, i.getAttribute('fetchpriority'), i.dataset.gmLegado, i.naturalWidth, i.className, i.width / i.height]; })()")
        ok(nlcp[:4] == ["img/produto-notebook-intel.png", "eager", "high", "imgs/pc5.png"] and nlcp[4] > 0 and "produto-notebook-intel" in nlcp[5]
           and abs(nlcp[6] - 706 / 549) < 0.02 and await np_.get_attribute("link[rel=preload][as=image]", "href") == nlcp[0],
           f"Notebook Intel: foto do site original como LCP (eager + preload, proporção 706×549): {nlcp[:4]}")
        ok(await np_.is_visible("#slot-mascote-dica-produto .mascote-secundario") and "i3-10100F" in await np_.text_content(".gm-dica__balao"),
           "Notebook Intel: mascote no #slot-mascote-dica-produto com dica deste notebook")
        nrel = await np_.evaluate("[...document.querySelectorAll('.gm-vitrine [data-gm-carrinho]')].map(b => +b.dataset.productId)")
        ok(nrel == [1, 4, 9, 7], f"Notebook Intel: relacionados sem o próprio produto, com o Computador Gamer ({nrel})")
        ok(await np_.evaluate("document.querySelector('.gm-vitrine a[data-product-id=\"9\"]').getAttribute('href')") == "ComputadorGamer.html"
           and await np_.evaluate("[...document.querySelectorAll('.gm-vitrine [data-gm-carrinho]')].every(b => b.dataset.trackOrigem === 'relacionados')"),
           "Notebook Intel: card do Computador Gamer leva à página dele (origem 'relacionados' em todos)")
        # Consentimento → page_view atribuído ao produto 5
        await np_.click("[data-gm-consent=aceitar]"); await np_.wait_for_timeout(3200)
        nsess = json.loads(ntrack[0].post_data)["session_id"] if ntrack else None
        npv = db("select path, product_id from page_views where session_id=%s and path='/NotebookIntel.html'", nsess)
        ok(npv and npv[0][1] == 5, f"Notebook Intel: page_view no Postgres com product_id=5 ({npv})")
        # Quantidade limitada ao estoque do seed (10 — igual ao limite da API)
        for _ in range(12):
            await np_.click("[data-gm-qtd-passo='1']")
        ok(await np_.input_value("#gm-qtd-produto") == str(nest) == "10", f"Notebook Intel: quantidade limitada ao estoque ({await np_.input_value('#gm-qtd-produto')}, estoque {nest})")
        await np_.fill("#gm-qtd-produto", "6")
        await np_.click("[data-gm-carrinho][data-product-id='5']:not(.btn-gm-add)"); await np_.wait_for_timeout(600)
        ncart = await np_.evaluate("JSON.parse(localStorage.getItem('cart'))")
        ok(ncart == [{"id": 5, "title": "Notebook Intel", "price": 2199, "img": "img/produto-notebook-intel.png", "qty": 6}], f"Notebook Intel: carrinho no formato legado ({ncart})")
        ok(await np_.text_content("[data-gm-carrinho-contador]") == "6" and await np_.is_visible(".gm-toast"), "Notebook Intel: contador = 6 e toast")
        await np_.wait_for_timeout(2500)
        nev = db("select props from analytics_events where session_id=%s and event_type='add_to_cart'", nsess)
        ok(nev and nev[-1][0].get("qty") == 6, f"Notebook Intel: add_to_cart no funil com qty=6 ({nev[-1][0] if nev else None})")
        await np_.screenshot(path=f"{SHOTS}/NotebookIntel-desktop.png", full_page=True)
        ok(await np_.evaluate("(() => { const f = document.querySelector('#slot-produto-principal').getBoundingClientRect(), h = document.querySelector('h1').getBoundingClientRect(); return h.left >= f.right - 1; })()"),
           "Notebook Intel desktop: foto à esquerda e compra à direita (2 colunas)")
        async with np_.expect_navigation():
            await np_.click("[data-gm-comprar][data-product-id='5']")
        ncart = await np_.evaluate("JSON.parse(localStorage.getItem('cart'))")
        ok(np_.url.endswith("/carrinho.html") and [(i["id"], i["qty"]) for i in ncart] == [(5, 10)], f"Notebook Intel: 'Comprar agora' soma 6 + 6 limitado a 10 e vai ao carrinho ({[(i['id'], i['qty']) for i in ncart]})")
        # Celular 390 px
        ncm = await new_context(browser, viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="pt-BR")
        nm = await ncm.new_page()
        nm.on("pageerror", lambda e: nerros.append(str(e)))
        await nm.goto(f"{BASE}/NotebookIntel.html", wait_until="load"); await nm.wait_for_timeout(900)
        ok(await nm.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Notebook Intel mobile: sem scroll horizontal")
        ok(await nm.evaluate("(() => { const f = document.querySelector('#slot-produto-principal').getBoundingClientRect(), h = document.querySelector('h1').getBoundingClientRect(); return h.top >= f.bottom - 1; })()"),
           "Notebook Intel mobile: foto acima do título (1 coluna)")
        nalvos = await nm.evaluate("[...document.querySelectorAll('[data-gm-comprar], .btn-gm-carrinho, [data-gm-favorito], [data-gm-qtd-passo], #gm-qtd-produto')].map(e => e.getBoundingClientRect().height).filter(h => h < 44).length")
        ok(nalvos == 0, f"Notebook Intel mobile: botões de compra e quantidade com alvo de toque ≥ 44 px ({nalvos} menores)")
        await nm.screenshot(path=f"{SHOTS}/NotebookIntel-mobile.png", full_page=True)
        ok(not nerros, f"Notebook Intel: sem erros de JS nem alert() {nerros[:2]}")
        await ncm.close(); await nctx.close()

        # ---------- 10. Mobile + demo ----------
        mctx = await new_context(browser, viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="pt-BR")
        m = await mctx.new_page()
        m.on("console", lambda msg: msg.type == "error" and console_errors.append("mobile: " + msg.text))
        await m.goto(f"{BASE}/produto.html", wait_until="load"); await m.wait_for_timeout(1500)
        ow = await m.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        ok(ow, "produto mobile sem scroll horizontal")
        await m.screenshot(path=f"{SHOTS}/produto-mobile.png", full_page=True)
        await m.goto(f"{BASE}/index.html", wait_until="load"); await m.wait_for_timeout(1200)
        ok(await m.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "home mobile sem scroll horizontal")
        await m.screenshot(path=f"{SHOTS}/home-mobile.png", full_page=True)
        await m.goto(f"{BASE}/dashboard.html?demo=1", wait_until="load"); await m.wait_for_timeout(2200)
        ok(await m.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "dashboard mobile sem scroll horizontal")
        await m.screenshot(path=f"{SHOTS}/dashboard-demo-mobile.png", full_page=True)
        dctx = await new_context(browser, viewport={"width": 1366, "height": 900}, locale="pt-BR")
        d = await dctx.new_page()
        await d.goto(f"{BASE}/dashboard.html?demo=1", wait_until="load"); await d.wait_for_timeout(2200)
        await d.screenshot(path=f"{SHOTS}/dashboard-demo-desktop.png", full_page=True)
        # dashboard sem sessão e sem demo → login
        await d.goto(f"{BASE}/dashboard.html", wait_until="load"); await d.wait_for_timeout(800)
        ok("entreoucadastrese.html?next=%2Fdashboard.html" in d.url, "dashboard sem sessão → redireciona para login")
        # carrinho sem sessão: finalizar → login com next, carrinho preservado
        await d.goto(f"{BASE}/carrinho.html", wait_until="load")
        await d.evaluate("localStorage.setItem('cart', JSON.stringify([{id: 22, title: 'Mouse Gamer', price: 89, img: 'img/produto-mouse-gamer.png', qty: 2}]))")
        await d.reload(wait_until="load"); await d.wait_for_timeout(400)
        async with d.expect_navigation():
            await d.click("[data-gm-finalizar]")
        ok("entreoucadastrese.html?next=%2Fcarrinho.html" in d.url, f"finalizar deslogado → login com next ({d.url.replace(BASE, '')})")
        ok(await d.evaluate("JSON.parse(localStorage.getItem('cart')).length") == 1, "carrinho preservado para depois do login")
        # carrinho no celular (390 px) com item
        await m.goto(f"{BASE}/carrinho.html", wait_until="load")
        await m.evaluate("localStorage.setItem('cart', JSON.stringify([{id: 4, title: 'PC Gamer Ryzen 5 5600G', price: 3799, img: 'img/produto-pc-gamer-ryzen5-5600g.png', qty: 2}, {id: 22, title: 'Mouse Gamer', price: 89, img: 'img/produto-mouse-gamer.png', qty: 1}]))")
        await m.reload(wait_until="load"); await m.wait_for_timeout(1200)
        ok(await m.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "carrinho mobile sem scroll horizontal")
        sobrepoe = await m.evaluate("""(() => { const li = document.querySelector('#gm-carrinho-lista li');
            const r = s => li.querySelector(s).getBoundingClientRect();
            const a = r('.gm-carrinho-item__qtd'), b = r('.gm-carrinho-item__subtotal');
            return a.right > b.left + 1 && a.bottom > b.top; })()""")
        ok(not sobrepoe, "carrinho mobile: quantidade e subtotal não se sobrepõem")
        await m.screenshot(path=f"{SHOTS}/carrinho-mobile.png", full_page=True)

        # ---------- 10b. Varredura de TODAS as páginas de frontend/ (cobre páginas novas automaticamente) ----------
        from pathlib import Path
        paginas = sorted(p.name for p in (Path(__file__).resolve().parents[1] / "frontend").glob("*.html"))
        v = await ctx.new_page()                       # mesma sessão logada do teste (o painel não redireciona)
        verros = []
        v.on("pageerror", lambda e: verros.append(f"{v.url.rsplit('/', 1)[-1]}: {e}"))
        v.on("console", lambda msg: msg.type == "error" and ("Content Security Policy" in msg.text or "Refused" in msg.text)
             and verros.append(f"{v.url.rsplit('/', 1)[-1]}: {msg.text[:120]}"))
        for nome in paginas:
            await v.set_viewport_size({"width": 1366, "height": 900})
            resp = await v.goto(f"{BASE}/{nome}", wait_until="load")
            for _ in range(10):
                await v.mouse.wheel(0, 1200); await v.wait_for_timeout(80)
            await v.wait_for_timeout(700)
            quebradas = await v.evaluate("[...document.images].filter(i => i.complete && i.naturalWidth === 0).map(i => i.getAttribute('src'))")
            await v.set_viewport_size({"width": 390, "height": 844}); await v.wait_for_timeout(250)
            estoura = await v.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            ok(resp is not None and resp.status == 200 and not quebradas and not estoura,
               f"varredura {nome}: HTTP {resp.status if resp else '-'}, imagens quebradas {quebradas[:2] or 0}, scroll horizontal no celular: {'sim' if estoura else 'não'}")
        ok(not verros, f"varredura: {len(paginas)} página(s) sem erro de JS nem violação de CSP {verros[:2] or ''}")
        await v.close()

        # ---------- 11. Duplo clique no arquivo (file://), com 1 imagem faltando ----------
        pasta = os.environ.get("GM_E2E_FILE_SITE")
        if pasta:
            fctx = await new_context(browser, viewport={"width": 1366, "height": 900}, locale="pt-BR")
            f = await fctx.new_page()
            ferros, favisos, freqs = [], [], []
            f.on("pageerror", lambda e: ferros.append(str(e)))
            f.on("console", lambda msg: msg.type == "warning" and favisos.append(msg.text))
            f.on("request", lambda r: "/api/" in r.url and freqs.append(r.url))
            await f.goto(f"file://{pasta}/produto.html", wait_until="load"); await f.wait_for_timeout(1500)
            ok(await f.evaluate("getComputedStyle(document.querySelector('.gm-topo')).backgroundColor") == "rgb(33, 37, 41)", "file://: CSS carregado (antes a página ficava sem estilo)")
            ok(await f.evaluate("getComputedStyle(document.querySelector('.gm-rodape')).backgroundColor") == "rgb(26, 26, 26)", "file://: rodapé estilizado")
            ok(await f.evaluate("document.querySelector('.mascote-principal').naturalWidth") > 0, "file://: mascote carregado de img/")
            ok(not await f.is_visible("#gm-consentimento"), "file://: sem banner (não há coleta)")
            await f.goto(f"file://{pasta}/index.html", wait_until="load")
            for _ in range(12):
                await f.mouse.wheel(0, 900); await f.wait_for_timeout(150)
            await f.wait_for_timeout(1800)
            ausentes = await f.evaluate("[...document.querySelectorAll('.gm-img--ausente')].map(i => i.className.split(' ')[0])")
            ok(ausentes == ["produto-notebook-gamer"], f"file://: sem img/ nem imgs/, vira espaço reservado sem ícone quebrado: {ausentes}")
            ok(any("migrar_imagens.py" in a for a in favisos), "file://: console explica como migrar as imagens")
            legado = os.environ.get("GM_E2E_LEGADO_SITE")   # pasta com imgs/ (nomes originais) e sem img/
            if legado:
                await f.goto(f"file://{legado}/index.html", wait_until="load")
                for _ in range(12):
                    await f.mouse.wheel(0, 900); await f.wait_for_timeout(150)
                await f.wait_for_timeout(1500)
                r = await f.evaluate("({usadas: document.querySelectorAll('[data-gm-legado-usado]').length, ausentes: document.querySelectorAll('.gm-img--ausente').length, quebradas: [...document.images].filter(i => i.complete && i.naturalWidth === 0).length})")
                ok(r["usadas"] >= 50 and r["ausentes"] == 0 and r["quebradas"] == 0, f"file://: sem migrar, usa as imagens originais de imgs/ ({r})")
            await f.goto(f"file://{pasta}/dashboard.html", wait_until="load"); await f.wait_for_timeout(1200)
            ok(await f.evaluate("document.documentElement.classList.contains('gm-demo')"), "file://: painel abre em modo demonstração")
            ok(not ferros and not freqs, f"file://: sem erros de JS ({ferros[:1]}) e sem chamadas à API ({len(freqs)})")

        await browser.close()

    csp = [e for e in console_errors if "Content Security Policy" in e or "Refused" in e]
    ok(not csp, f"zero violações de CSP ({csp[:2]})")
    other = [e for e in console_errors if e not in csp and "404" not in e and "Failed to load resource" not in e]
    ok(not other, f"zero erros de JS ({other[:3]})")
    passed = sum(r[0] for r in results)
    print(f"\n{passed}/{len(results)} verificações OK")

if __name__ == "__main__":
    asyncio.run(main())
