-- =============================================================================
-- Migração 001 — página de detalhes do produto (para bancos criados antes dela).
-- Idempotente. Depois rode seed_products.sql de novo para preencher os valores.
-- =============================================================================
ALTER TABLE products ADD COLUMN IF NOT EXISTS page_path VARCHAR(120);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_products_page_path') THEN
    -- Só nome de arquivo .html: bloqueia javascript:, URLs externas e ../
    ALTER TABLE products ADD CONSTRAINT ck_products_page_path CHECK (page_path ~ '^[A-Za-z0-9._-]+\.html$');
  END IF;
END $$;
