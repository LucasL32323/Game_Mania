-- =============================================================================
-- Catálogo migrado das páginas estáticas (preços e textos do site atual).
--   image_path → /img/... (CHECK ck_products_image_in_img)
--   page_path  → página de detalhes existente no site (NULL = ainda sem página)
-- Idempotente: rodar de novo atualiza nome/preço/imagem/página, mas NÃO mexe no estoque.
-- =============================================================================
INSERT INTO products (id, sku, slug, name, category, price, stock, image_path, page_path) VALUES
  -- Computadores (vitrine "Destaques")
  (1,  'GM-PC-RTX3060',   'pc-gamer-rtx-3060',        'PC Gamer RTX 3060',          'computadores', 4999.00, 12, '/img/produto-pc-gamer-rtx3060.png',         'pcgamerrtx3060.html'),
  (2,  'GM-PC-G6400',     'pc-escritorio-dual-core',  'PC Escritório Dual Core',    'computadores', 1899.00, 20, '/img/produto-pc-escritorio-dual-core.png',  'pcdualcore.html'),
  (3,  'GM-PC-R9-5900X',  'pc-gamer-ryzen-9',         'PC Gamer Ryzen 9',           'computadores', 7499.00,  5, '/img/produto-pc-gamer-ryzen9-5900x.png',    'Ryzen95900x.html'),
  (4,  'GM-PC-R5-5600G',  'pc-gamer-ryzen-5-5600g',   'PC Gamer Ryzen 5 5600G',     'computadores', 3799.00,  9, '/img/produto-pc-gamer-ryzen5-5600g.png',    'produto.html'),
  (5,  'GM-NB-I3',        'notebook-intel',           'Notebook Intel',             'computadores', 2199.00, 10, '/img/produto-notebook-intel.png',           'NotebookIntel.html'),
  (6,  'GM-PC-COMPLETO',  'computador-completo',      'Computador Completo',        'computadores', 2999.00,  8, '/img/produto-computador-completo.png',      'pccompleto.html'),
  (7,  'GM-PC-NITRO-X',   'pc-gamer-nitro-x',         'PC Gamer Nitro X',           'computadores', 7499.00,  4, '/img/produto-pc-gamer-nitro-x.png',         'PCGamerNitro.html'),
  (8,  'GM-PC-PRO-I7',    'pc-profissional',          'PC Profissional',            'computadores', 5299.00,  6, '/img/produto-pc-profissional.png',          'pcprofissional.html'),
  (9,  'GM-PC-GAMER-I7',  'computador-gamer',         'Computador Gamer',           'computadores', 4499.00,  7, '/img/produto-computador-gamer.png',         'ComputadorGamer.html'),
  (10, 'GM-NB-GAMER',     'notebook-gamer',           'Notebook Gamer',             'computadores', 4999.00,  5, '/img/produto-notebook-gamer.png',           NULL),
  -- Computadores (vitrine da categoria — legado/computadores.html; páginas próprias ainda não migradas)
  (11, 'GM-PC-ESCR-R5',   'pc-escritorio',            'PC Escritório',              'computadores', 3200.00, 10, '/img/produto-pc-escritorio.png',            NULL),
  (12, 'GM-PC-BASICO-I5', 'pc-gamer-basico',          'PC Gamer Básico',            'computadores', 2800.00, 10, '/img/produto-pc-gamer-basico.png',          NULL),
  (13, 'GM-PC-IDEAL-I7',  'computador-ideal',         'Computador Ideal',           'computadores', 4500.00,  8, '/img/produto-computador-ideal.png',         NULL),
  (14, 'GM-PC-PROD-R7',   'computador-produtivo',     'Computador Produtivo',       'computadores', 5800.00,  6, '/img/produto-computador-produtivo.png',     NULL),
  (15, 'GM-PC-ECON-I3',   'pc-economico',             'PC Econômico',               'computadores', 1900.00, 15, '/img/produto-pc-economico.png',             NULL),
  (16, 'GM-PC-ULTRA-I9',  'pc-ultra-performance',     'PC Ultra Performance',       'computadores', 8500.00,  4, '/img/produto-pc-ultra-performance.png',     NULL),
  (17, 'GM-PC-DOM-PG',    'pc-domestico',             'PC Doméstico',               'computadores', 2100.00, 12, '/img/produto-pc-domestico.png',             NULL),
  (18, 'GM-PC-WS-R9',     'pc-workstation',           'PC Workstation',             'computadores',10500.00,  3, '/img/produto-pc-workstation.png',           NULL),
  (19, 'GM-PC-ESSEN-R3',  'pc-essencial',             'PC Essencial',               'computadores', 2300.00, 12, '/img/produto-pc-essencial.png',             NULL),
  -- Periféricos
  (21, 'GM-MON-24LED',    'monitor-24-led',           'Monitor 24" LED',            'perifericos',   750.00, 30, '/img/produto-monitor-24-led.png',           'Monitorled.html'),
  (22, 'GM-MOUSE-GAMER',  'mouse-gamer',              'Mouse Gamer',                'perifericos',    89.00, 80, '/img/produto-mouse-gamer.png',              'mousegamer.html'),
  (23, 'GM-HEADSET-MIC',  'headset-com-microfone',    'Headset com Microfone',      'perifericos',   130.00, 45, '/img/produto-headset.png',                  'headset.html'),
  (24, 'GM-HEADSET-71',   'headset-gamer-7-1',        'Headset Gamer 7.1',          'perifericos',   399.00, 25, '/img/produto-headset-gamer-7-1.webp',       NULL),
  (25, 'GM-VOLANTE',      'volante-gamer',            'Volante Gamer',              'perifericos',  1199.00,  8, '/img/produto-volante-gamer.webp',           NULL),
  (26, 'GM-SUP-HEADSET',  'suporte-para-headset',     'Suporte para Headset',       'perifericos',   149.00, 40, '/img/produto-suporte-headset.webp',         NULL),
  (27, 'GM-MON-144HZ',    'monitor-gamer-144hz',      'Monitor Gamer 144Hz',        'perifericos',  1499.00, 12, '/img/produto-monitor-gamer-144hz.webp',     NULL),
  -- Periféricos (vitrine da categoria — legado/perifericos.html; preços do site original, páginas próprias ainda não migradas)
  -- Obs.: o Mouse Gamer (id 22) aparece por R$ 90,00 no card do site antigo, mas a página do produto vende por R$ 89,00 (mantido).
  (61, 'GM-TECLADO-MEC',  'teclado-mecanico',         'Teclado Mecânico',           'perifericos',   120.00, 30, '/img/produto-teclado-mecanico.png',         NULL),
  (62, 'GM-WEBCAM-1080',  'webcam-1080p',             'Webcam 1080p',               'perifericos',   140.00, 25, '/img/produto-webcam-1080p.png',             NULL),
  (63, 'GM-CXSOM-USB',    'caixa-de-som-usb',         'Caixa de som USB',           'perifericos',    75.00, 40, '/img/produto-caixa-de-som-usb.png',         NULL),
  (64, 'GM-MOUSEPAD-GM',  'mousepad-gamer',           'Mousepad Gamer',             'perifericos',    35.00, 60, '/img/produto-mousepad-gamer.png',           NULL),
  (65, 'GM-IMPR-MULTI',   'impressora-multifuncional','Impressora Multifuncional',  'perifericos',   480.00, 10, '/img/produto-impressora-multifuncional.png', NULL),
  (66, 'GM-SUP-MONITOR',  'suporte-para-monitor',     'Suporte para Monitor',       'perifericos',    85.00, 25, '/img/produto-suporte-monitor.png',          NULL),
  -- Hardware (vitrine da categoria — legado/hardware.html; preços do site original, páginas próprias ainda não migradas)
  -- Obs.: a GTX 1080 estava com 1899.00 (preço da RTX 2080 Ti); o site original vende por R$ 1.799,00.
  (31, 'GM-GPU-GTX1080',  'placa-de-video-gtx-1080',  'Placa de Vídeo GTX 1080',    'hardware',     1799.00,  6, '/img/produto-gtx1080.png',                  NULL),
  (32, 'GM-CPU-R7-5800X', 'amd-ryzen-7-5800x',        'AMD Ryzen 7 5800X',          'hardware',     1920.00,  8, '/img/produto-ryzen7-5800x.png',             NULL),
  (33, 'GM-CPU-I5-10400F','intel-core-i5-10400f',     'Intel Core i5-10400F',       'hardware',     1299.00, 10, '/img/produto-intel-i5-10400f.png',          NULL),
  (34, 'GM-SSD-AORUS-512','ssd-aorus-nvme-512gb',     'SSD Gigabyte AORUS RGB M.2 NVMe 512GB', 'hardware', 450.00, 20, '/img/produto-ssd-aorus-512gb.png',    NULL),
  (35, 'GM-MB-ASUS-B550', 'placa-mae-asus-b550',      'Placa-Mãe Asus B550',        'hardware',      900.00, 10, '/img/produto-placa-mae-asus-b550.png',      NULL),
  (36, 'GM-RAM-AORUS-D5', 'memoria-ram-aorus-ddr5',   'Memória RAM AORUS DDR5',     'hardware',     1200.00, 12, '/img/produto-memoria-aorus-ddr5.png',       NULL),
  (37, 'GM-PSU-RM1000X',  'fonte-corsair-rm1000x',    'Fonte Corsair RM1000x',      'hardware',     1499.00,  8, '/img/produto-fonte-rm1000x.png',            NULL),
  (38, 'GM-GPU-VEGA64',   'amd-radeon-rx-vega-64',    'AMD Radeon RX Vega 64',      'hardware',     1199.00,  5, '/img/produto-radeon-rx-vega-64.png',        NULL),
  (39, 'GM-GPU-2080TI',   'geforce-rtx-2080-ti',      'GeForce RTX 2080 Ti',        'hardware',     1899.00,  5, '/img/produto-rtx2080-ti.png',               NULL),
  -- Escritório (vitrine da categoria — legado/escritorio.html; preços do site original, páginas próprias ainda não migradas)
  -- id 41 corrigido: o site original vende a "Cadeira Giratória Office Básica" por R$ 250,00 (não R$ 649,00)
  (41, 'GM-CADEIRA-OFF',  'cadeira-office',           'Cadeira Giratória Office Básica', 'escritorio', 250.00, 15, '/img/produto-cadeira-office.png',      NULL),
  (42, 'GM-CADEIRA-ERGO', 'cadeira-ergonomica-executiva', 'Cadeira Ergonômica Executiva', 'escritorio', 480.00, 10, '/img/produto-cadeira-ergonomica-executiva.png', NULL),
  (43, 'GM-MESA-GAVETAS', 'mesa-escritorio-gavetas',  'Mesa de Escritório com Gavetas', 'escritorio', 420.00,  8, '/img/produto-mesa-escritorio-gavetas.png', NULL),
  (44, 'GM-MESA-COMPACTA','mesa-compacta-escritorio', 'Mesa Compacta para Escritório', 'escritorio',  280.00, 10, '/img/produto-mesa-compacta.png',           NULL),
  (45, 'GM-ORGANIZ-MESA', 'organizador-de-mesa',      'Organizador de Mesa',        'escritorio',     35.00, 50, '/img/produto-organizador-de-mesa.png',     NULL),
  (46, 'GM-LUMINARIA',    'luminaria-de-mesa',        'Luminária de Mesa',          'escritorio',     70.00, 30, '/img/produto-luminaria-de-mesa.png',       NULL),
  (47, 'GM-MESA-EXEC',    'mesa-executiva-escritorio','Mesa Executiva de Escritório', 'escritorio',  310.00,  8, '/img/produto-mesa-executiva.png',          NULL),
  (48, 'GM-ESTAB-500VA',  'estabilizador-500va',      'Estabilizador de Energia 500VA', 'escritorio', 140.00, 20, '/img/produto-estabilizador-500va.png',     NULL),
  (49, 'GM-PROT-TELA',    'protetor-de-tela-monitor', 'Protetor de Tela para Monitor', 'escritorio',  60.00, 25, '/img/produto-protetor-de-tela.png',        NULL),
  -- Consoles e games
  (51, 'GM-CTRL-X360',    'controle-xbox-360',        'Controle Xbox 360',          'consoles',      149.00, 30, '/img/produto-controle-xbox-360.png',        NULL),
  (52, 'GM-PS5',          'playstation-5',            'PlayStation 5',              'consoles',     4499.00,  6, '/img/produto-playstation-5.webp',           NULL),
  (53, 'GM-XBOX-SX',      'xbox-series-x',            'Xbox Series X',              'consoles',     4299.00,  6, '/img/produto-xbox-series-x.webp',           NULL),
  (54, 'GM-SWITCH-OLED',  'nintendo-switch-oled',     'Nintendo Switch OLED',       'consoles',     2499.00,  8, '/img/produto-nintendo-switch-oled.png',     NULL),
  (55, 'GM-SNES-MINI',    'super-nintendo-mini',      'Super Nintendo Mini',        'consoles',      699.00, 10, '/img/produto-super-nintendo-mini.webp',     NULL),
  (56, 'GM-PS2-SLIM',     'playstation-2-slim',       'PlayStation 2 Slim',         'consoles',      599.00,  4, '/img/produto-playstation-2-slim.webp',      NULL)
ON CONFLICT (id) DO UPDATE SET
  sku = EXCLUDED.sku, slug = EXCLUDED.slug, name = EXCLUDED.name, category = EXCLUDED.category,
  price = EXCLUDED.price, image_path = EXCLUDED.image_path, page_path = EXCLUDED.page_path;

-- Ajusta a sequence após IDs explícitos
SELECT setval(pg_get_serial_sequence('products', 'id'), (SELECT max(id) FROM products));
