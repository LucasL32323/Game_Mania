"""
Suíte de integração da API (TestClient + PostgreSQL real). 44 verificações.

Pré-requisitos: banco criado (scripts/init_db.py + sql/analytics.sql + sql/seed_products.sql),
.env com GM_ALLOWED_ORIGINS/HOSTS incluindo "http://testserver" e "testserver".
Rodar de dentro de backend/:   GM_TEST_DSN="dbname=gamemania user=... password=... host=localhost" python ../tests/test_api.py
Use um banco DESCARTÁVEL: o teste cria usuários, pedidos e baixa estoque.
"""
import sys, time, uuid, json
sys.path.insert(0, '.')  # executar a partir de backend/
from datetime import datetime, timezone
import os
import bcrypt, psycopg2
from fastapi.testclient import TestClient
from app.main import app

H = {"Origin": "http://testserver"}
db = psycopg2.connect(os.environ.get("GM_TEST_DSN", "dbname=gamemania user=gm_owner password=devpass host=localhost")); db.autocommit = True
def q(sql, *a):
    cur = db.cursor(); cur.execute(sql, a); 
    try: return cur.fetchall()
    except psycopg2.ProgrammingError: return None

ok = lambda cond, msg: print(("PASS " if cond else "FAIL ") + msg) or (cond or sys.exit(1))

with TestClient(app, base_url="http://testserver") as c:
    r = c.get("/api/v1/csrf"); ok(r.status_code == 204 and c.cookies.get("gm_csrf"), "csrf cookie emitido")
    tok = c.cookies.get("gm_csrf")
    ok(r.headers.get("content-security-policy","").startswith("default-src 'self'"), "CSP presente")

    r = c.post("/api/v1/auth/register", json={"name":"Jogador Teste","email":"Teste@GameMania.com.br","password":"senhaForte123"}, headers=H)
    ok(r.status_code == 403, f"register sem token CSRF bloqueado ({r.status_code})")
    r = c.post("/api/v1/auth/register", json={"name":"Jogador Teste","email":"Teste@GameMania.com.br","password":"senhaForte123"}, headers={**H,"X-CSRF-Token":tok,"Origin":"http://evil.com"})
    ok(r.status_code == 403, "register com Origin estranha bloqueado")
    r = c.post("/api/v1/auth/register", json={"name":"<script>x</script>","email":"a@b.com","password":"senhaForte123"}, headers={**H,"X-CSRF-Token":tok})
    ok(r.status_code == 422, "nome com <script> rejeitado")
    r = c.post("/api/v1/auth/register", json={"name":"Jogador Teste","email":"Teste@GameMania.com.br","password":"senhaForte123"}, headers={**H,"X-CSRF-Token":tok})
    ok(r.status_code == 201 and r.json()["email"] == "teste@gamemania.com.br", f"register ok {r.status_code} {r.text[:120]}")
    row = q("select email_encrypted, email_bidx, password_hash from users where name='Jogador Teste'")[0]
    enc = bytes(row[0])
    ok(b"gamemania" not in enc and enc[0]==1 and enc[1]==1 and len(enc)==2+12+len("teste@gamemania.com.br")+16, f"email cifrado AES-GCM ({len(enc)} bytes, sem texto claro)")
    ok(len(bytes(row[1]))==32, "blind index 32 bytes")
    ok(row[2].startswith("$argon2id$v=19$m=65536,t=3,p=4$"), "senha em Argon2id")

    r = c.post("/api/v1/auth/register", json={"name":"Outro","email":"teste@gamemania.com.br","password":"senhaForte123"}, headers={**H,"X-CSRF-Token":c.cookies.get("gm_csrf")})
    ok(r.status_code == 409, "e-mail duplicado (case-insensitive) barrado via blind index")

    c.post("/api/v1/auth/logout", headers={**H,"X-CSRF-Token":c.cookies.get("gm_csrf")})
    r = c.post("/api/v1/auth/login", json={"email":"teste@gamemania.com.br","password":"errada123"}, headers={**H,"X-CSRF-Token":c.cookies.get("gm_csrf")})
    ok(r.status_code == 401, "login senha errada 401")
    r2 = c.post("/api/v1/auth/login", json={"email":"naoexiste@x.com","password":"errada123"}, headers={**H,"X-CSRF-Token":c.cookies.get("gm_csrf")})
    ok(r2.status_code == 401 and r2.json()==r.json(), "e-mail inexistente: mesma resposta (sem enumeração)")

    # usuário legado com bcrypt do server.js
    from app.security.crypto import get_email_cipher
    ci = get_email_cipher()
    legacy = bcrypt.hashpw(b"senhaAntiga1", bcrypt.gensalt(10)).decode()
    q("insert into users (public_id,name,email_encrypted,email_bidx,password_hash) values (%s,%s,%s,%s,%s)",
      str(uuid.uuid4()), "Legado", ci.encrypt("legado@gamemania.com.br"), ci.blind_index("legado@gamemania.com.br"), legacy)

import app.routers.auth as authmod
# limpa rate limiter entre blocos
from app.security.web import limiter; limiter.reset()

with TestClient(app, base_url="http://testserver") as c:
    c.get("/api/v1/csrf")
    r = c.post("/api/v1/auth/login", json={"email":"legado@gamemania.com.br","password":"senhaAntiga1"}, headers={**H,"X-CSRF-Token":c.cookies.get("gm_csrf")})
    ok(r.status_code == 200, "login com hash bcrypt legado")
    ok(q("select password_hash from users where name='Legado'")[0][0].startswith("$argon2id$"), "hash legado migrado para Argon2id")
    c.post("/api/v1/auth/logout", headers={**H,"X-CSRF-Token":c.cookies.get("gm_csrf")})

    r = c.post("/api/v1/auth/login", json={"email":"TESTE@gamemania.com.br","password":"senhaForte123"}, headers={**H,"X-CSRF-Token":c.cookies.get("gm_csrf")})
    ok(r.status_code == 200 and c.cookies.get("gm_session"), "login ok (e-mail normalizado)")
    tok = c.cookies.get("gm_csrf")
    HH = {**H, "X-CSRF-Token": tok}

    sid, vid, pv = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    batch = {"session_id": sid, "visitor_id": vid, "referrer_host": "www.google.com", "events": [
        {"type":"page_view","ts":now,"page_view_id":pv,"path":"/produto.html","referrer_path":"/computadores.html","product_id":4},
        {"type":"engagement","ts":now,"page_view_id":pv,"path":"/produto.html","active_seconds":95,"scroll_pct":60},
        {"type":"engagement","ts":now,"page_view_id":pv,"path":"/produto.html","active_seconds":40,"scroll_pct":80},
        {"type":"favorite_add","ts":now,"page_view_id":pv,"path":"/produto.html","product_id":4},
        {"type":"add_to_cart","ts":now,"page_view_id":pv,"path":"/produto.html","product_id":4,"props":{"qty":1}},
        {"type":"begin_checkout","ts":now,"page_view_id":pv,"path":"/produto.html","product_id":4},
    ]}
    t0=time.perf_counter(); r = c.post("/api/v1/track", json=batch, headers=HH); dt=(time.perf_counter()-t0)*1000
    ok(r.status_code == 202 and r.json()["accepted"], f"tracking 202 em {dt:.1f} ms (sem I/O de banco)")
    # fallback sendBeacon: text/plain + token no corpo
    b2 = dict(batch, csrf_token=tok, events=[{"type":"engagement","ts":now,"page_view_id":pv,"path":"/produto.html","active_seconds":120,"scroll_pct":90}])
    r = c.post("/api/v1/track", content=json.dumps(b2), headers={**H, "Content-Type":"text/plain;charset=UTF-8"})
    ok(r.status_code == 202, "fallback sendBeacon (text/plain + token no corpo) aceito")
    bad = dict(batch, events=[{"type":"page_view","ts":now,"page_view_id":pv,"path":"javascript:alert(1)"}])
    ok(c.post("/api/v1/track", json=bad, headers=HH).status_code == 422, "path javascript: rejeitado")
    bad = dict(batch, events=[{"type":"purchase","ts":now,"page_view_id":pv,"path":"/x"}])
    ok(c.post("/api/v1/track", json=bad, headers=HH).status_code == 422, "cliente não pode forjar 'purchase'")
    bad = dict(batch, user_id=1)
    ok(c.post("/api/v1/track", json=bad, headers=HH).status_code == 422, "campo user_id do cliente rejeitado (extra=forbid)")
    ok(c.post("/api/v1/track", json=batch, headers=H).status_code == 403, "tracking sem CSRF bloqueado")

    ok(c.post("/api/v1/favorites/4", headers=HH).status_code == 201, "favoritar produto 4")
    ok(c.post("/api/v1/favorites/4", headers=HH).status_code == 201, "favoritar de novo é idempotente")
    ok(c.post("/api/v1/favorites/1", headers=HH).status_code == 201, "favoritar produto 1")
    ok(c.post("/api/v1/favorites/999", headers=HH).status_code == 404, "produto inexistente 404")
    ok(c.post("/api/v1/favorites/1%20OR%201=1", headers=HH).status_code == 422, "injeção no path rejeitada")

    stock_before = q("select stock from products where id=4")[0][0]
    r = c.post("/api/v1/orders", json={"items":[{"product_id":4,"quantity":1},{"product_id":22,"quantity":2},{"product_id":4,"quantity":1}],"payment_method":"pix"}, headers={**HH, "X-GM-Session": sid})
    ok(r.status_code == 201 and r.json()["total"] in ("7776.00", 7776.0, "7776"), f"pedido criado com preço do servidor: {r.json()}")
    ok(q("select stock from products where id=4")[0][0] == stock_before - 2, "estoque decrementado (itens consolidados)")
    q("update orders set status='paid', paid_at=now()")
    r = c.post("/api/v1/orders", json={"items":[{"product_id":7,"quantity":10}],"payment_method":"card"}, headers=HH)
    ok(r.status_code == 409, f"estoque insuficiente barrado ({r.json()['detail']})")

    time.sleep(3.0)  # worker grava em lote (flush 2 s)
    pvrow = q("select active_seconds, max_scroll_pct, referrer_path, product_id, user_id is not null from page_views where id=%s", pv)[0]
    ok(pvrow[0]==120 and pvrow[1]==90 and pvrow[2]=="/computadores.html" and pvrow[3]==4 and pvrow[4], f"page_view consolidado via GREATEST: {pvrow}")
    evs = q("select event_type, tableoid::regclass::text from analytics_events order by id")
    ok([e[0] for e in evs] == ["favorite_add","add_to_cart","begin_checkout","purchase"], f"eventos gravados: {[e[0] for e in evs]}")
    particao = "analytics_events_" + datetime.now(timezone.utc).strftime("%Y_%m")   # mês corrente (não fixo)
    ok(all(e[1] == particao for e in evs), f"eventos na partição do mês ({particao}): {set(e[1] for e in evs)}")
    srow = q("select landing_path, referrer_host, device, length(ip_hash), user_id is not null from analytics_sessions where id=%s", sid)[0]
    ok(srow[0]=="/produto.html" and srow[1]=="www.google.com" and srow[4], f"sessão registrada: {srow}")
    from app.security.crypto import pseudonymize_ip
    h1, h2, h3 = pseudonymize_ip("200.100.50.25"), pseudonymize_ip("200.100.50.99"), pseudonymize_ip("200.100.51.25")
    # hash hex de 32 chars; nunca o IP em claro ("200" pode aparecer por acaso num hex aleatório)
    ok(len(h1)==32 and h1==h2 and h1!=h3 and "200.100" not in h1 and all(c in "0123456789abcdef" for c in h1), "IP pseudonimizado (/24 + HMAC)")

    q("refresh materialized view concurrently mv_user_interest")
    r = c.get("/api/v1/me/dashboard")
    d = r.json()
    ok(r.status_code == 200, "dashboard 200")
    print(json.dumps(d, indent=1, ensure_ascii=False)[:1800])
    ok(d["stats"]["orders"]==1 and d["stats"]["favorites"]==2 and d["stats"]["active_minutes_30d"]==2 and d["stats"]["visits_30d"]==1, "stats corretos")
    ok(d["interests"][0]["category"]=="computadores" and d["interests"][0]["score_pct"]==100, "perfil de interesse calculado")
    print(c.get("/healthz").json())
    print("funil:", q("select * from vw_conversion_funnel_daily"))
    print("top pages:", q("select * from vw_top_pages_30d"))
    print("top products:", q("select name, units_sold, revenue from vw_top_products order by units_sold desc"))
    print("retorno:", q("select * from vw_return_rate_30d"))

    c.post("/api/v1/auth/logout", headers=HH)
    ok(c.get("/api/v1/me/dashboard").status_code == 401, "dashboard sem sessão 401")

    # --- R08: rotas inexistentes (front-end servido pela API em dev) ---
    r = c.get("/pagina-que-nao-existe.html")
    ok(r.status_code == 404 and r.headers["content-type"].startswith("text/html") and "<h1 id=\"erro-titulo\" class=\"gm-erro__titulo\">Página não encontrada</h1>" in r.text,
       f"404 do site devolve a página amigável com status 404 ({r.status_code})")
    ok("<base " not in r.text and r.headers.get("cache-control") == "no-store" and r.headers.get("content-security-policy", "").startswith("default-src 'self'"),
       "404 de 1 nível: sem <base>, no-store e com CSP")
    r = c.get("/loja/pc/inexistente")
    ok(r.status_code == 404 and r.text.count('<base href="/">') == 1 and r.text.index('<base href="/">') < r.text.index("css/gamemania.css"),
       "404 em rota aninhada recebe <base href=\"/\"> antes dos caminhos relativos")
    r = c.get("/api/v1/rota-que-nao-existe")
    ok(r.status_code == 404 and r.headers["content-type"].startswith("application/json") and r.json() == {"detail": "Não encontrado"},
       "rota inexistente da API continua 404 em JSON (nunca HTML)")
    ok(c.get("/api").status_code == 404 and c.get("/api").headers["content-type"].startswith("application/json"), "/api sozinho também responde JSON")
    ok(c.get("/index.html").status_code == 200 and c.get("/").status_code == 200 and c.get("/404.html").status_code == 200,
       "páginas existentes continuam 200 (inclusive /404.html aberta direto)")
print("\nTODOS OS TESTES PASSARAM")
