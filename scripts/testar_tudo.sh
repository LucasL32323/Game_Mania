#!/usr/bin/env bash
# =============================================================================
# GameMania 2.0 — roda TODAS as verificações em um ambiente limpo (Linux).
#
#   1. Estático ......... regras fixas do front-end (paleta, CSP, imagens, SRI)
#   2. E2E .............. Chromium real contra API + PostgreSQL (servidor e duplo clique)
#   3. API .............. integração FastAPI + PostgreSQL (criptografia, CSRF, pedidos)
#
# Uso:   bash scripts/testar_tudo.sh
# Usado pela tarefa agendada noturna e pelo GitHub Actions. Cria um banco
# DESCARTÁVEL (gamemania_teste) e uma pasta de trabalho em $GM_WORK (padrão
# /tmp/gm-testes). Nunca lê nem altera backend/.env.
# Saída: código 0 só se tudo passar; a última linha resume os números.
# =============================================================================
set -uo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${GM_WORK:-/tmp/gm-testes}"
PORTA="${GM_PORTA:-8000}"
DB="gamemania_teste"
SUDO=""; [ "$(id -u)" != "0" ] && SUDO="sudo"
FALHOU=0
API_PID=""

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
como_postgres() { if [ "$(id -u)" = "0" ]; then runuser -u postgres -- "$@"; else sudo -u postgres "$@"; fi; }
encerrar() { [ -n "$API_PID" ] && kill "$API_PID" 2>/dev/null; }
trap encerrar EXIT

rm -rf "$WORK" && mkdir -p "$WORK"

# --- Python (venv reaproveita pacotes do sistema, ex.: Playwright já instalado) ---
log "Dependências Python"
python3 -m venv --system-site-packages "$WORK/venv" || { echo "python3-venv ausente"; exit 2; }
PY="$WORK/venv/bin/python"
"$PY" -m pip install -q --disable-pip-version-check -r "$RAIZ/backend/requirements.txt" \
  psycopg2-binary "psycopg[binary]" pillow || { echo "pip install falhou"; exit 2; }
if ! "$PY" -c "import playwright" 2>/dev/null; then
  "$PY" -m pip install -q playwright || exit 2
fi
if [ -z "${PLAYWRIGHT_BROWSERS_PATH:-}" ] && [ -d /opt/pw-browsers ]; then export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers; fi
if ! "$PY" - <<'EOF' 2>/dev/null
from playwright.sync_api import sync_playwright
with sync_playwright() as p: p.chromium.launch().close()
EOF
then
  log "Instalando Chromium do Playwright"
  "$PY" -m playwright install --with-deps chromium || exit 2
fi

# --- 1. Estático --------------------------------------------------------------
log "1/3 Verificações estáticas"
"$PY" "$RAIZ/tests/test_estatico.py" | tee "$WORK/estatico.log"
[ "${PIPESTATUS[0]}" = "0" ] || FALHOU=1

# --- PostgreSQL ---------------------------------------------------------------
log "PostgreSQL (banco descartável $DB)"
if ! command -v psql >/dev/null; then
  $SUDO apt-get update -qq || true
  $SUDO apt-get install -y -qq postgresql >/dev/null || { echo "não foi possível instalar o PostgreSQL"; exit 2; }
fi
$SUDO service postgresql start >/dev/null 2>&1 || $SUDO systemctl start postgresql >/dev/null 2>&1 || true
for _ in $(seq 1 20); do pg_isready -q -h localhost && break; sleep 1; done
pg_isready -q -h localhost || { echo "PostgreSQL não subiu"; exit 2; }
como_postgres psql -q -v ON_ERROR_STOP=1 <<'EOF' || exit 2
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gm_owner') THEN
    CREATE ROLE gm_owner LOGIN SUPERUSER PASSWORD 'devpass';
  END IF;
END $$;
DROP DATABASE IF EXISTS gamemania_teste WITH (FORCE);
CREATE DATABASE gamemania_teste OWNER gm_owner;
EOF
export PGPASSWORD=devpass
PSQL="psql -h localhost -U gm_owner -d $DB -q -v ON_ERROR_STOP=1"
export GM_TEST_DSN="host=localhost dbname=$DB user=gm_owner password=devpass"

# --- Configuração da API só por variáveis de ambiente (o .env do dev fica intocado) ---
chave() { "$PY" -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())"; }
export GM_ENVIRONMENT=development GM_SERVE_FRONTEND=true GM_COOKIE_SECURE=false
export GM_DATABASE_URL="postgresql+asyncpg://gm_owner:devpass@localhost:5432/$DB"
export GM_ANALYTICS_DATABASE_URL="$GM_DATABASE_URL"
export GM_EMAIL_AES_KEYS="{\"1\": \"$(chave)\"}" GM_EMAIL_AES_ACTIVE_KEY_ID=1
export GM_EMAIL_HMAC_KEY="$(chave)" GM_IP_HMAC_KEY="$(chave)" GM_JWT_SECRET="$(chave)$(chave)"
export GM_ALLOWED_ORIGINS="[\"http://localhost:$PORTA\",\"http://testserver\"]"
export GM_ALLOWED_HOSTS='["localhost","127.0.0.1","testserver"]'

preparar_banco() {
  $PSQL -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" >/dev/null || return 1
  (cd "$RAIZ/backend" && "$PY" -m scripts.init_db) || return 1
  $PSQL -f "$RAIZ/backend/sql/analytics.sql" >/dev/null || return 1
  $PSQL -f "$RAIZ/backend/sql/seed_products.sql" >/dev/null || return 1
}
preparar_banco || { echo "falha ao criar o schema"; exit 2; }

# --- Sites de teste: imagens reais do repositório; provisórias só se faltarem ---
log "Montando sites de teste"
SITE="$WORK/site"; ARQ="$WORK/site-arquivo"; LEG="$WORK/site-legado"
cp -r "$RAIZ/frontend" "$SITE"
[ -f "$SITE/img/mascote-principal.png" ] || "$PY" "$RAIZ/tests/gerar_placeholders.py" "$SITE/img"
cp -r "$SITE" "$ARQ" && rm -f "$ARQ/img/produto-notebook-gamer.png"            # 1 imagem faltando de propósito
cp -r "$RAIZ/frontend" "$LEG" && rm -rf "$LEG/img"                             # só a pasta imgs/ original (plano B)
if [ -d "$RAIZ/legado/imgs" ]; then cp -r "$RAIZ/legado/imgs" "$LEG/imgs"
else "$PY" "$RAIZ/tests/gerar_placeholders.py" "$LEG/imgs" --legado; fi
# Versão do Bootstrap lida do teste estático (fonte única: BS_VERSAO em tests/test_estatico.py)
BS_VERSAO="$(sed -n 's/^BS_VERSAO = "\(.*\)"$/\1/p' "$RAIZ/tests/test_estatico.py")"
npm install -s --no-audit --no-fund --prefix "$WORK/nm" "bootstrap@$BS_VERSAO" @fontsource/rajdhani @fontsource/comic-neue >/dev/null 2>&1 \
  && export GM_E2E_NODE_MODULES="$WORK/nm/node_modules" \
  || echo "aviso: npm indisponível — o E2E usará o CDN direto"

# --- 2. E2E -------------------------------------------------------------------
log "2/3 E2E no Chromium"
(cd "$RAIZ/backend" && GM_FRONTEND_DIR="$SITE" exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORTA" >"$WORK/api.log" 2>&1) &
API_PID=$!
for _ in $(seq 1 30); do curl -sf "http://localhost:$PORTA/healthz" >/dev/null && break; sleep 1; done
if curl -sf "http://localhost:$PORTA/healthz" >/dev/null; then
  GM_E2E_BASE="http://localhost:$PORTA" GM_E2E_SHOTS="$WORK/prints" GM_E2E_FILE_SITE="$ARQ" GM_E2E_LEGADO_SITE="$LEG" \
    timeout 600 "$PY" "$RAIZ/tests/e2e_frontend.py" | tee "$WORK/e2e.log"
  [ "${PIPESTATUS[0]}" = "0" ] && ! grep -q "^FAIL" "$WORK/e2e.log" || FALHOU=1
else
  echo "FAIL API não respondeu em /healthz (veja $WORK/api.log)" | tee "$WORK/e2e.log"; tail -20 "$WORK/api.log"; FALHOU=1
fi
kill "$API_PID" 2>/dev/null; wait "$API_PID" 2>/dev/null; API_PID=""

# --- 3. API -------------------------------------------------------------------
log "3/3 Integração da API"
preparar_banco || { echo "falha ao recriar o schema"; exit 2; }
(cd "$RAIZ/backend" && timeout 300 "$PY" ../tests/test_api.py) | tee "$WORK/api-testes.log"
[ "${PIPESTATUS[0]}" = "0" ] && ! grep -q "^FAIL" "$WORK/api-testes.log" || FALHOU=1

# --- Resumo -------------------------------------------------------------------
conta() { printf '%s/%s' "$(grep -c '^PASS' "$1" 2>/dev/null || echo 0)" "$(grep -cE '^(PASS|FAIL)' "$1" 2>/dev/null || echo 0)"; }
echo
echo "Prints do E2E: $WORK/prints"
echo "RESULTADO: estático $(conta "$WORK/estatico.log") · E2E $(conta "$WORK/e2e.log") · API $(conta "$WORK/api-testes.log") · $([ $FALHOU = 0 ] && echo 'TUDO OK' || echo 'HÁ FALHAS')"
exit $FALHOU
