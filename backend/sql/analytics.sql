-- =============================================================================
-- GameMania 2.0 — Camada analítica (PostgreSQL 15+)
-- Executar DEPOIS de criar as tabelas (Alembic / Base.metadata.create_all).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1) Partições mensais de analytics_events
--    DEFAULT recebe qualquer linha fora do intervalo (nenhum INSERT falha).
--    Agende gm_create_event_partition para criar os próximos meses com antecedência.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics_events_default PARTITION OF analytics_events DEFAULT;

CREATE OR REPLACE FUNCTION gm_create_event_partition(p_month date)
RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_start timestamptz := date_trunc('month', p_month)::timestamp AT TIME ZONE 'UTC';
    v_end   timestamptz := (date_trunc('month', p_month) + interval '1 month')::timestamp AT TIME ZONE 'UTC';
    v_name  text        := format('analytics_events_%s', to_char(p_month, 'YYYY_MM'));
BEGIN
    -- format(%I / %L) escapa identificadores e literais: sem SQL dinâmico injetável
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF analytics_events FOR VALUES FROM (%L) TO (%L)',
        v_name, v_start, v_end
    );
END;
$$;

-- Mês atual + 2 próximos
SELECT gm_create_event_partition((date_trunc('month', now()) + make_interval(months => m))::date)
FROM generate_series(0, 2) AS m;

-- Com pg_cron:
-- SELECT cron.schedule('gm-particoes', '0 3 1 * *',
--   $$SELECT gm_create_event_partition((date_trunc('month', now()) + interval '2 months')::date)$$);


-- -----------------------------------------------------------------------------
-- 2) Páginas mais visitadas (30 dias) — tempo ATIVO real, não aba aberta
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_top_pages_30d AS
SELECT
    path,
    count(*)                              AS views,
    count(DISTINCT session_id)            AS sessions,
    round(avg(active_seconds))::int       AS avg_active_seconds,
    round(avg(max_scroll_pct))::int       AS avg_scroll_pct
FROM page_views
WHERE started_at >= now() - interval '30 days'
GROUP BY path;


-- -----------------------------------------------------------------------------
-- 3) Itens mais comprados (somente pedidos pagos)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_top_products AS
SELECT
    p.id,
    p.name,
    p.category,
    sum(oi.quantity)                 AS units_sold,
    sum(oi.quantity * oi.unit_price) AS revenue,
    count(DISTINCT o.user_id)        AS buyers
FROM order_items oi
JOIN orders   o ON o.id = oi.order_id AND o.status IN ('paid', 'shipped', 'delivered')
JOIN products p ON p.id = oi.product_id
GROUP BY p.id, p.name, p.category;


-- -----------------------------------------------------------------------------
-- 4) Funil de conversão diário (sessões distintas por etapa)
--    Produto visto → Carrinho → Checkout → Compra
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_conversion_funnel_daily AS
WITH steps AS (
    SELECT (started_at AT TIME ZONE 'America/Sao_Paulo')::date AS day, session_id, 1 AS step
    FROM page_views
    WHERE product_id IS NOT NULL
    UNION ALL
    SELECT (occurred_at AT TIME ZONE 'America/Sao_Paulo')::date, session_id,
           CASE event_type WHEN 'add_to_cart' THEN 2 WHEN 'begin_checkout' THEN 3 ELSE 4 END
    FROM analytics_events
    WHERE event_type IN ('add_to_cart', 'begin_checkout', 'purchase') AND session_id IS NOT NULL
)
SELECT
    day,
    count(DISTINCT session_id) FILTER (WHERE step = 1) AS product_views,
    count(DISTINCT session_id) FILTER (WHERE step = 2) AS added_to_cart,
    count(DISTINCT session_id) FILTER (WHERE step = 3) AS began_checkout,
    count(DISTINCT session_id) FILTER (WHERE step = 4) AS purchased,
    round(100.0 * count(DISTINCT session_id) FILTER (WHERE step = 4)
          / nullif(count(DISTINCT session_id) FILTER (WHERE step = 1), 0), 2) AS conversion_pct
FROM steps
GROUP BY day;


-- -----------------------------------------------------------------------------
-- 5) Frequência de retorno (30 dias)
--    Visitante = visitor_id (anônimo com consentimento) ou usuário logado
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_visitor_return_30d AS
WITH visits AS (
    SELECT
        coalesce(visitor_id::text, 'user:' || user_id::text) AS visitor,
        started_at,
        lag(started_at) OVER (
            PARTITION BY coalesce(visitor_id::text, 'user:' || user_id::text)
            ORDER BY started_at
        ) AS previous_visit
    FROM analytics_sessions
    WHERE started_at >= now() - interval '30 days'
      AND (visitor_id IS NOT NULL OR user_id IS NOT NULL)
)
SELECT
    visitor,
    count(*)                                                                   AS sessions,
    round((avg(extract(epoch FROM started_at - previous_visit)) / 86400)::numeric, 1) AS avg_days_between,
    max(started_at)                                                            AS last_visit
FROM visits
GROUP BY visitor;

CREATE OR REPLACE VIEW vw_return_rate_30d AS
SELECT
    count(*)                                   AS visitors,
    count(*) FILTER (WHERE sessions > 1)       AS returning_visitors,
    round(100.0 * count(*) FILTER (WHERE sessions > 1) / nullif(count(*), 0), 2) AS return_rate_pct
FROM vw_visitor_return_30d;


-- -----------------------------------------------------------------------------
-- 6) Perfil de interesse por usuário (score com decaimento temporal)
--    compra = 5/un · favorito = 3 · 1 ponto por minuto em página de produto (máx. 5)
--    peso * e^(-idade/30 dias): o interesse de ontem vale mais que o de 3 meses atrás
-- -----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_user_interest AS
WITH signals AS (
    SELECT o.user_id, p.category, 5.0 * oi.quantity AS weight, o.created_at AS ts
    FROM order_items oi
    JOIN orders   o ON o.id = oi.order_id
    JOIN products p ON p.id = oi.product_id
    WHERE o.status IN ('paid', 'shipped', 'delivered')
    UNION ALL
    SELECT f.user_id, p.category, 3.0, f.created_at
    FROM favorites f
    JOIN products p ON p.id = f.product_id
    UNION ALL
    SELECT pv.user_id, p.category, least(pv.active_seconds / 60.0, 5.0), pv.started_at
    FROM page_views pv
    JOIN products p ON p.id = pv.product_id
    WHERE pv.user_id IS NOT NULL
      AND pv.started_at >= now() - interval '180 days'
)
SELECT
    user_id,
    category,
    round(sum(weight * exp(-extract(epoch FROM (now() - ts)) / 2592000.0))::numeric, 3) AS score
FROM signals
GROUP BY user_id, category
WITH DATA;

-- Índice único obrigatório para REFRESH ... CONCURRENTLY (não bloqueia leituras)
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_user_interest ON mv_user_interest (user_id, category);

-- Com pg_cron (a cada 15 min):
-- SELECT cron.schedule('gm-interesses', '*/15 * * * *',
--   $$REFRESH MATERIALIZED VIEW CONCURRENTLY mv_user_interest$$);


-- -----------------------------------------------------------------------------
-- 7) Menor privilégio (reduz o estrago de qualquer falha de injeção)
--    gamemania_app       → API transacional
--    gamemania_analytics → worker de telemetria (só escreve telemetria)
--    gamemania_bi        → dashboards internos (só lê views)
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gamemania_app')       THEN CREATE ROLE gamemania_app LOGIN;       END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gamemania_analytics') THEN CREATE ROLE gamemania_analytics LOGIN; END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gamemania_bi')        THEN CREATE ROLE gamemania_bi LOGIN;        END IF;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON users, user_access_log, products, orders, order_items, favorites TO gamemania_app;
GRANT SELECT ON analytics_sessions, page_views, analytics_events, mv_user_interest TO gamemania_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO gamemania_app;

GRANT SELECT, INSERT, UPDATE ON analytics_sessions, page_views TO gamemania_analytics;
GRANT INSERT ON analytics_events TO gamemania_analytics;
GRANT USAGE ON SEQUENCE analytics_events_id_seq TO gamemania_analytics;

GRANT SELECT ON vw_top_pages_30d, vw_top_products, vw_conversion_funnel_daily,
               vw_visitor_return_30d, vw_return_rate_30d TO gamemania_bi;
