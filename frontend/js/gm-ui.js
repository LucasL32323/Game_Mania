/*!
 * GameMania 2.0 — gm-ui.js
 * Comportamentos de interface (vanilla JS, sem jQuery).
 *
 *   • apiFetch ........ fetch com cookie de sessão + token CSRF + tratamento de 401
 *   • Favoritos ....... [data-gm-favorito] — otimista, aria-pressed, reverte em erro
 *   • Quantidade ...... [data-gm-qtd] — stepper 1..máx (máx = menor entre 10 e estoque)
 *   • Carrinho ........ [data-gm-carrinho] / [data-gm-comprar] — compatível com o 'cart' do compra.js legado
 *   • Consentimento ... banner #gm-consentimento + switch #gm-consent-switch (usa window.GMTracker)
 *   • Dashboard ....... body[data-gm-pagina="dashboard"] — hidrata a partir de GET /api/v1/me/dashboard
 *   • Busca ........... filtra a vitrine da home ao digitar (e via index.html?q= vindo de outras páginas)
 *   • Página carrinho . body[data-gm-pagina="carrinho"] — lista, quantidade, remover e POST /api/v1/orders
 *   • Entrar/cadastro . body[data-gm-pagina="entrar"] — abas, validação, login/cadastro e ?next= seguro
 *   • Ordenação ....... [data-gm-ordenar] — ordena a vitrine de categoria por preço/nome sem recarregar (?ordem=)
 *   • Abas de tipo .... [data-gm-filtrar] — filtra a vitrine por tipo de peça sem recarregar (?tipo=)
 *   • FAQ ............. [data-gm-faq-busca] — busca nas perguntas do suporte e link direto #faq-<id>
 *   • Página 404 ...... body[data-gm-pagina="404"] — endereço procurado, "Voltar" interno, âncoras com <base>
 *   • Imagens ......... sem o arquivo novo em img/, usa o original de imgs/ (plano B) e avisa no console
 *   • Modo arquivo .... aberto com duplo clique (file://): tudo visual funciona, recursos de API avisam
 *
 * Anti-XSS: dados da API NUNCA passam por innerHTML. Tudo é clonado de <template>
 * e preenchido com textContent / setAttribute com validação (ex.: imagens só de /img/).
 */
(function (window, document) {
  'use strict';

  var API = '/api/v1';                                     // API sempre na raiz do servidor
  var LOGIN_URL = 'entreoucadastrese.html';                // páginas: caminhos relativos
  var OFFLINE = location.protocol === 'file:';             // aberto direto do disco, sem servidor
  var CART_KEY = 'cart';                                   // mesma chave do compra.js legado
  var MAX_QTY = 10;                                        // espelha schemas.OrderItemIn

  var brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  var dataCurta = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
  var dataHora = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
  var mesAno = new Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric' });

  var STATUS_LABEL = {
    pending: 'Aguardando pagamento', paid: 'Pago', shipped: 'Enviado',
    delivered: 'Entregue', cancelled: 'Cancelado', refunded: 'Reembolsado'
  };
  var CATEGORIA_LABEL = {
    computadores: 'Computadores', perifericos: 'Periféricos', hardware: 'Hardware',
    escritorio: 'Escritório', consoles: 'Consoles e games'
  };

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  // ===========================================================================
  // 1. API
  // ===========================================================================
  function csrfCookie() {
    var m = document.cookie.match(/(?:^|; )(?:__Host-)?gm_csrf=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : null;
  }

  function ensureCsrf() {
    var t = csrfCookie();
    if (t) return Promise.resolve(t);
    return fetch(API + '/csrf', { credentials: 'same-origin', cache: 'no-store' }).then(csrfCookie);
  }

  function goToLogin() {
    var next = location.pathname + location.search;
    location.assign(LOGIN_URL + '?next=' + encodeURIComponent(next));
  }

  /**
   * @param {string} path  caminho relativo à API (ex.: '/favorites/4')
   * @param {{method?: string, body?: any, redirectOn401?: boolean}} opts
   */
  function apiFetch(path, opts) {
    opts = opts || {};
    if (OFFLINE) {                                         // file:// não tem servidor para responder
      var off = new Error('offline'); off.status = 0; off.offline = true;
      return Promise.reject(off);
    }
    var method = (opts.method || 'GET').toUpperCase();
    var mutating = method !== 'GET' && method !== 'HEAD';
    var prep = mutating ? ensureCsrf() : Promise.resolve(null);

    return prep.then(function (token) {
      var headers = { Accept: 'application/json' };
      if (token) headers['X-CSRF-Token'] = token;
      if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
      return fetch(API + path, {
        method: method,
        credentials: 'same-origin',
        headers: headers,
        body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined
      });
    }).then(function (res) {
      if (res.status === 401 && opts.redirectOn401 !== false) goToLogin();
      if (!res.ok) {
        var err = new Error('HTTP ' + res.status);
        err.status = res.status;
        throw err;
      }
      return res.status === 204 ? null : res.json();
    });
  }

  // ===========================================================================
  // 2. Toasts (Bootstrap) — conteúdo via textContent
  // ===========================================================================
  function toast(message, isError) {
    var host = $('#gm-toasts');
    var tpl = $('#tpl-toast');
    if (!host || !tpl) return;
    var el = tpl.content.firstElementChild.cloneNode(true);
    $('.toast-body', el).textContent = message;
    if (isError) {
      el.classList.add('gm-toast--erro');
      el.setAttribute('role', 'alert');
    }
    host.appendChild(el);
    if (window.bootstrap && bootstrap.Toast) {
      el.addEventListener('hidden.bs.toast', function () { el.remove(); });
      bootstrap.Toast.getOrCreateInstance(el, { delay: 3500 }).show();
    } else {
      el.classList.add('show');
      setTimeout(function () { el.remove(); }, 3500);
    }
  }

  // ===========================================================================
  // 3. Consentimento LGPD
  // ===========================================================================
  function initConsent() {
    var tracker = window.GMTracker;
    var banner = $('#gm-consentimento');
    if (!tracker) return;

    // GPC ativo = recusa presumida: não incomoda o usuário com banner
    if (banner && !tracker.consentDecided() && !tracker.gpc()) banner.hidden = false;

    document.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-gm-consent]');
      if (!btn) return;
      tracker.setConsent(btn.getAttribute('data-gm-consent') === 'aceitar');
      if (banner) banner.hidden = true;
    });

    var sw = $('#gm-consent-switch');
    if (sw) {
      sw.checked = tracker.hasConsent();
      sw.addEventListener('change', function () {
        tracker.setConsent(sw.checked);
        toast(sw.checked ? 'Estatísticas de navegação ativadas.' : 'Coleta desativada e dados locais apagados.');
      });
    }
  }

  // ===========================================================================
  // 4. Favoritos
  // ===========================================================================
  function paintFavorite(btn, on) {
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    // O tracker lê data-track na fase de captura → sempre descreve a PRÓXIMA ação
    btn.setAttribute('data-track', on ? 'favorite_remove' : 'favorite_add');
    var label = $('.gm-favorito__rotulo', btn);
    if (label) label.textContent = on ? 'Favoritado' : 'Favoritar';
    btn.setAttribute('aria-label', on ? 'Remover dos favoritos' : 'Adicionar aos favoritos');
  }

  function initFavorites() {
    var buttons = $$('[data-gm-favorito]');
    if (!buttons.length) return;

    // Botões que o usuário já clicou: a resposta inicial (mais antiga) não pode sobrescrevê-los.
    // Sem isso, um clique rápido antes do GET terminar era "desfeito" visualmente.
    var touched = new WeakSet();

    // Estado inicial (sem sessão → 401 silencioso, botões ficam "Favoritar")
    if (!OFFLINE) apiFetch('/favorites', { redirectOn401: false }).then(function (data) {
      var ids = (data && data.product_ids) || [];
      buttons.forEach(function (b) {
        if (!touched.has(b)) paintFavorite(b, ids.indexOf(Number(b.getAttribute('data-product-id'))) !== -1);
      });
    }).catch(function () { /* visitante: mantém estado padrão */ });

    document.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-gm-favorito]');
      if (!btn || btn.disabled) return;
      var id = parseInt(btn.getAttribute('data-product-id'), 10);
      if (!(id > 0)) return;
      if (OFFLINE) { toast('Favoritos precisam do servidor rodando (uvicorn).', true); return; }
      var wasOn = btn.getAttribute('aria-pressed') === 'true';

      touched.add(btn);
      paintFavorite(btn, !wasOn);                          // otimista
      btn.disabled = true;
      apiFetch('/favorites/' + id, { method: wasOn ? 'DELETE' : 'POST' })
        .then(function () {
          toast(wasOn ? 'Removido dos favoritos.' : 'Adicionado aos favoritos!');
        })
        .catch(function (err) {
          paintFavorite(btn, wasOn);                       // reverte
          if (err.status !== 401) toast('Não foi possível atualizar seus favoritos.', true);
        })
        .then(function () { btn.disabled = false; });
    });
  }

  // ===========================================================================
  // 5. Quantidade
  // ===========================================================================
  function initQuantity() {
    $$('[data-gm-qtd]').forEach(function (box) {
      var input = $('input', box);
      var max = Math.min(MAX_QTY, parseInt(input.getAttribute('max'), 10) || MAX_QTY);
      var targets = $$('[data-gm-usa-qtd]');
      // Limite (estoque do campo, no máximo MAX_QTY) vai junto nos botões: o addToCart
      // não deixa a SOMA no carrinho passar do estoque ao clicar várias vezes.
      targets.forEach(function (t) { t.setAttribute('data-gm-qtd-max', max); });

      function set(v) {
        var n = Math.max(1, Math.min(max, parseInt(v, 10) || 1));
        input.value = n;
        targets.forEach(function (t) { t.setAttribute('data-track-qty', n); });   // vai nas props do tracker
      }
      box.addEventListener('click', function (e) {
        var b = e.target.closest('[data-gm-qtd-passo]');
        if (b) set(Number(input.value) + Number(b.getAttribute('data-gm-qtd-passo')));
      });
      input.addEventListener('change', function () { set(input.value); });
      set(input.value);
    });
  }

  // ===========================================================================
  // 6. Carrinho (localStorage 'cart' — formato do compra.js: {id,title,price,img,qty})
  //    O preço aqui é só exibição: o servidor recalcula tudo em POST /api/v1/orders.
  // ===========================================================================
  function readCart() {
    try { var c = JSON.parse(localStorage.getItem(CART_KEY) || '[]'); return Array.isArray(c) ? c : []; }
    catch (e) { return []; }
  }
  function saveCart(cart) {
    try { localStorage.setItem(CART_KEY, JSON.stringify(cart)); } catch (e) { /* cota */ }
    paintCartCount();
  }
  function paintCartCount() {
    var total = readCart().reduce(function (s, i) { return s + (Number(i.qty) || 0); }, 0);
    $$('[data-gm-carrinho-contador]').forEach(function (el) {
      el.textContent = total > 99 ? '99+' : String(total);
      el.setAttribute('data-qtd', String(total));
    });
    $$('[data-gm-carrinho-rotulo]').forEach(function (el) {
      el.setAttribute('aria-label', 'Carrinho: ' + total + (total === 1 ? ' item' : ' itens'));
    });
  }

  function addToCart(btn) {
    var id = parseInt(btn.getAttribute('data-product-id'), 10);
    var img = btn.getAttribute('data-img') || '';
    if (!(id > 0)) return false;
    var qty = parseInt(btn.getAttribute('data-track-qty'), 10) || 1;
    // Teto = estoque da página de produto (data-gm-qtd-max, definido na seção 5) ou o limite da API
    var teto = Math.min(MAX_QTY, parseInt(btn.getAttribute('data-gm-qtd-max'), 10) || MAX_QTY);
    var cart = readCart();
    var item = cart.filter(function (i) { return i.id === id; })[0];
    if (item) {
      item.qty = Math.min(teto, item.qty + qty);
    } else {
      cart.push({
        id: id,
        title: btn.getAttribute('data-nome') || '',
        price: Number(btn.getAttribute('data-preco')) || 0,
        img: /^\/?img\/[A-Za-z0-9._-]+$/.test(img) ? img : '',     // relativo (img/…) ou absoluto (/img/…)
        qty: Math.min(teto, qty)
      });
    }
    saveCart(cart);
    return true;
  }

  function initCart() {
    paintCartCount();
    window.addEventListener('storage', function (e) { if (e.key === CART_KEY) paintCartCount(); });  // outras abas

    document.addEventListener('click', function (e) {
      var add = e.target.closest('[data-gm-carrinho]');
      if (add && addToCart(add)) { toast('Produto adicionado ao carrinho!'); return; }

      var buy = e.target.closest('[data-gm-comprar]');
      if (buy && addToCart(buy)) location.assign('carrinho.html');   // tracker envia via keepalive no pagehide
    });
  }

  // ===========================================================================
  // 7. Dashboard — hidratação
  // ===========================================================================
  function bind(root, name, value) {
    $$('[data-gm-bind="' + name + '"]', root).forEach(function (el) {
      el.textContent = value;
      el.removeAttribute('data-gm-sample');
    });
  }

  function fill(fragment, field, value) {
    var el = $('[data-campo="' + field + '"]', fragment);
    if (el) el.textContent = value;
    return el;
  }

  // A API devolve caminhos absolutos (/img/...) — o painel é servido pela raiz do servidor
  function safeImg(path) { return /^\/img\/[a-z0-9\-_.]+\.(png|jpe?g|webp|svg|avif)$/i.test(path) ? path : '/img/mascote-secundario.png'; }
  function safePage(path) { return /^[A-Za-z0-9._-]+\.html$/.test(path || '') ? path : 'index.html'; }

  function formatMinutes(min) {
    if (min < 60) return min + ' min';
    var h = Math.floor(min / 60), m = min % 60;
    return h + 'h' + (m ? ' ' + m + 'min' : '');
  }

  function clone(id) { var t = document.getElementById(id); return t ? t.content.cloneNode(true) : null; }

  function renderDashboard(d) {
    var main = $('#conteudo');

    bind(main, 'user.name', d.user.name.split(' ')[0]);
    bind(main, 'user.since', 'Membro desde ' + mesAno.format(new Date(d.user.created_at)));
    bind(main, 'stats.orders', String(d.stats.orders));
    bind(main, 'stats.total_spent', brl.format(Number(d.stats.total_spent)));
    bind(main, 'stats.favorites', String(d.stats.favorites));
    bind(main, 'stats.active_time', formatMinutes(d.stats.active_minutes_30d));

    // Remove os dados de exemplo do template estático
    $$('[data-gm-sample]').forEach(function (el) { el.remove(); });

    // Pedidos
    var tbody = $('#gm-pedidos-corpo');
    d.recent_orders.forEach(function (o) {
      var f = clone('tpl-pedido-linha');
      fill(f, 'code', o.code);
      fill(f, 'items', o.items_label);
      fill(f, 'total', brl.format(Number(o.total)));
      var t = fill(f, 'date', dataCurta.format(new Date(o.created_at)));
      t.setAttribute('datetime', o.created_at);
      var s = fill(f, 'status', STATUS_LABEL[o.status] || o.status);
      s.classList.add('gm-status--' + (STATUS_LABEL[o.status] ? o.status : 'pending'));
      tbody.appendChild(f);
    });
    $('#gm-pedidos-vazio').hidden = d.recent_orders.length > 0;
    $('#gm-pedidos-tabela').hidden = d.recent_orders.length === 0;

    // Favoritos
    var favs = $('#gm-favoritos-lista');
    d.favorites.forEach(function (p) {
      var f = clone('tpl-favorito-card');
      var img = $('img', f);
      var src = safeImg(p.image_path);
      img.src = src;
      img.alt = p.name;
      img.classList.add(src.slice(5).replace(/\.[a-z]+$/i, ''));   // classe = nome semântico do arquivo
      var a = fill(f, 'name', p.name);
      a.href = safePage(p.page_path);
      fill(f, 'price', brl.format(Number(p.price)));
      favs.appendChild(f);
    });
    $('#gm-favoritos-vazio').hidden = d.favorites.length > 0;

    // Interesses
    var ints = $('#gm-interesses-lista');
    d.interests.forEach(function (i) {
      var f = clone('tpl-interesse');
      var label = CATEGORIA_LABEL[i.category] || i.category;
      fill(f, 'category', label);
      fill(f, 'pct', i.score_pct + '%');
      var bar = $('progress', f);
      bar.value = i.score_pct;
      bar.setAttribute('aria-label', 'Interesse em ' + label);
      ints.appendChild(f);
    });
    $('#gm-interesses-vazio').hidden = d.interests.length > 0;

    // Histórico de acessos
    var acc = $('#gm-acessos-lista');
    d.access_history.forEach(function (a) {
      var f = clone('tpl-acesso');
      var dev = fill(f, 'device', a.success ? a.device : 'Tentativa falha · ' + a.device);
      if (!a.success) dev.classList.add('gm-acesso--falha');
      var t = fill(f, 'when', dataHora.format(new Date(a.occurred_at)));
      t.setAttribute('datetime', a.occurred_at);
      acc.appendChild(f);
    });
  }

  function initDashboard() {
    if (document.body.getAttribute('data-gm-pagina') !== 'dashboard') return;
    var main = $('#conteudo');

    // ?demo=1 ou arquivo aberto do disco → mantém os dados de exemplo (sem back-end)
    if (OFFLINE || new URLSearchParams(location.search).get('demo') === '1') {
      document.documentElement.classList.add('gm-demo');
      return;
    }

    main.setAttribute('aria-busy', 'true');
    apiFetch('/me/dashboard')
      .then(renderDashboard)
      .catch(function (err) {
        if (err.status === 401) return;                     // já redirecionou para o login
        $$('[data-gm-sample]').forEach(function (el) {
          if (!el.hasAttribute('data-gm-bind')) { el.remove(); return; }
          el.textContent = el.getAttribute('data-gm-fallback') || '—';
          el.removeAttribute('data-gm-sample');
        });
        toast('Não foi possível carregar sua conta. Tente novamente em instantes.', true);
      })
      .then(function () { main.removeAttribute('aria-busy'); });

    var sair = $('[data-gm-sair]');
    if (sair) {
      sair.addEventListener('click', function () {
        apiFetch('/auth/logout', { method: 'POST', redirectOn401: false })
          .catch(function () { /* sessão já expirada */ })
          .then(function () { location.assign('index.html'); });
      });
    }
  }

  // ===========================================================================
  // 8. Usuário no menu ("Entre ou cadastre-se" → "Olá, Lucas")
  // ===========================================================================
  function initUser() {
    var link = $('[data-gm-usuario]');
    if (!link || OFFLINE) return;
    apiFetch('/auth/me', { redirectOn401: false }).then(function (u) {
      var nome = String(u.name || '').split(' ')[0].slice(0, 30);
      var rotulo = $('.gm-nav__rotulo', link);
      if (rotulo) rotulo.textContent = 'Olá, ' + nome;
      link.setAttribute('href', 'dashboard.html');
      link.setAttribute('aria-label', 'Minha conta (' + nome + ')');
    }).catch(function () { /* visitante */ });
  }

  // ===========================================================================
  // 9. Busca na vitrine (substitui o barrapesquisa.js)
  //    Home: filtra os cards enquanto digita. Outras páginas: o form envia para index.html?q=
  // ===========================================================================
  function normalizar(t) {
    return String(t).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
  }

  function initSearch() {
    var input = $('#gm-busca-q');
    var itens = $$('[data-gm-busca-item]');
    var q = (new URLSearchParams(location.search).get('q') || '').slice(0, 80);
    if (input && q) input.value = q;
    if (!itens.length) return;                             // não é a home

    var status = $('#gm-busca-status');
    var textos = itens.map(function (el) { return normalizar(el.textContent); });

    function aplicar(termo) {
      var t = normalizar(termo);
      var visiveis = 0;
      itens.forEach(function (el, i) {
        var ok = !t || textos[i].indexOf(t) !== -1;
        el.hidden = !ok;
        if (ok) visiveis++;
      });
      $$('[data-gm-busca-secao]').forEach(function (sec) {  // esconde seções que ficaram vazias
        sec.hidden = !!t && !$('[data-gm-busca-item]:not([hidden])', sec);
      });
      $$('[data-gm-busca-ocultar]').forEach(function (el) { el.hidden = !!t; });
      if (!status) return;
      status.hidden = !t;
      status.textContent = '';
      if (!t) return;
      var forte = document.createElement('strong');
      forte.textContent = String(visiveis);
      status.append(forte, visiveis === 1 ? ' resultado para “' : ' resultados para “', termo.trim(), '”. ');
      var limpar = document.createElement('a');
      limpar.href = 'index.html';
      limpar.textContent = 'Limpar busca';
      limpar.addEventListener('click', function (e) { e.preventDefault(); input.value = ''; aplicar(''); history.replaceState(null, '', location.pathname); });
      status.append(limpar);
    }

    var timer = 0;
    if (input) {
      input.addEventListener('input', function () {
        clearTimeout(timer);
        timer = setTimeout(function () { aplicar(input.value); }, 150);
      });
      input.form.addEventListener('submit', function (e) {   // na home não recarrega a página
        e.preventDefault();
        aplicar(input.value);
        var url = input.value.trim() ? '?q=' + encodeURIComponent(input.value.trim()) : location.pathname;
        history.replaceState(null, '', url);
      });
    }
    if (q) aplicar(q);
  }

  // ===========================================================================
  // 10. Imagens: plano B com os arquivos originais do site + aviso no console
  //     1º tenta img/<nome-novo>. Se não existir, usa data-gm-legado (imgs/Logo4.png…),
  //     então o site funciona na hora. Se nem o original existir, mantém o espaço sem
  //     ícone de imagem quebrada e explica no console como resolver.
  // ===========================================================================
  function initImagens() {
    var ausentes = [];
    var legado = 0;
    var aviso = 0;

    function avisar() {
      clearTimeout(aviso);
      aviso = setTimeout(function () {
        if (legado) {
          console.info('[GameMania] ' + legado + ' imagem(ns) carregada(s) da pasta antiga imgs/. ' +
            'Para usar os nomes novos em img/, rode migrar_imagens.bat (Windows) ou python migrar_imagens.py.');
        }
        if (ausentes.length) {
          console.warn('[GameMania] ' + ausentes.length + ' imagem(ns) não encontrada(s) nem em img/ nem em imgs/. ' +
            'Confira os arquivos ou rode migrar_imagens.bat (Windows) / python migrar_imagens.py:\n  ' + ausentes.join('\n  '));
        }
      }, 1200);
    }

    function falhou(img) {
      var original = img.getAttribute('data-gm-legado');
      if (original && !img.hasAttribute('data-gm-legado-usado')) {
        img.setAttribute('data-gm-legado-usado', img.getAttribute('src'));   // guarda o caminho novo
        legado++;
        img.src = original;                                  // tenta o arquivo do site atual
        avisar();
        return;
      }
      if (img.classList.contains('gm-img--ausente')) return;
      img.classList.add('gm-img--ausente');
      var novo = img.getAttribute('data-gm-legado-usado');
      ausentes.push(novo ? novo + ' (e ' + img.getAttribute('src') + ')' : img.getAttribute('src'));
      avisar();
    }

    // Falhas futuras (inclui lazy loading): o evento "error" não borbulha → fase de captura
    document.addEventListener('error', function (e) {
      if (e.target && e.target.tagName === 'IMG') falhou(e.target);
    }, true);
    // Falhas que aconteceram antes deste script (defer) carregar
    $$('img').forEach(function (img) {
      if (img.complete && img.naturalWidth === 0 && img.getAttribute('src')) falhou(img);
    });
  }

  // ===========================================================================
  // 11. Página do carrinho — body[data-gm-pagina="carrinho"]
  //     Lista o localStorage['cart'], altera quantidade (1–10), remove, esvazia e
  //     finaliza em POST /api/v1/orders. Sem sessão a API responde 401 e o apiFetch
  //     leva para entreoucadastrese.html?next=/carrinho.html (o carrinho fica guardado).
  //     Totais aqui são só exibição: o pedido usa o preço do banco.
  // ===========================================================================
  var PAGAMENTO_LABEL = { pix: 'Pix', card: 'Cartão de crédito', boleto: 'Boleto bancário' };
  var MAX_ITENS_PEDIDO = 30;                               // espelha schemas.OrderIn.items (max_length)
  var ERRO_PEDIDO = {
    409: 'Estoque insuficiente para um dos produtos. Diminua a quantidade e tente de novo.',
    422: 'Um ou mais produtos não estão mais disponíveis. Remova-os e tente de novo.',
    429: 'Muitas tentativas seguidas. Aguarde um minuto e tente de novo.'
  };

  // Imagem do item: só arquivos de img/ (caminho relativo, funciona no file://); senão, o mascote
  function cartImg(path) {
    var p = String(path || '').replace(/^\//, '');
    return /^img\/[A-Za-z0-9._-]+\.(png|jpe?g|webp|svg|avif)$/i.test(p) ? p : 'img/mascote-secundario.png';
  }

  // Carrinho vindo do localStorage é dado não confiável (pode ter sido salvo pelo site
  // antigo ou editado à mão): valida tipos, junta ids repetidos e limita a quantidade.
  function normalizeCart(cart) {
    var porId = {};
    var limpo = [];
    cart.forEach(function (i) {
      var id = Number(i && i.id);
      if (!(id > 0) || id !== Math.floor(id)) return;
      var qty = Math.max(1, Math.min(MAX_QTY, parseInt(i.qty, 10) || 1));
      if (porId[id]) { porId[id].qty = Math.min(MAX_QTY, porId[id].qty + qty); return; }
      var item = {
        id: id,
        title: String(i.title || 'Produto GameMania').slice(0, 120),
        price: Math.max(0, Number(i.price) || 0),
        img: cartImg(i.img),
        qty: qty
      };
      porId[id] = item;
      limpo.push(item);
    });
    return limpo;
  }

  function initCarrinho() {
    if (document.body.getAttribute('data-gm-pagina') !== 'carrinho') return;

    var lista = $('#gm-carrinho-lista');
    var cheio = $('#gm-carrinho-cheio');
    var vazio = $('#gm-carrinho-vazio');
    var sucesso = $('#gm-carrinho-sucesso');
    var status = $('#gm-carrinho-status');
    var finalizar = $('[data-gm-finalizar]');
    var rotuloFinalizar = $('[data-gm-finalizar-rotulo]');
    var esvaziar = $('[data-gm-carrinho-esvaziar]');
    var enviando = false;
    var concluido = false;                                 // pedido feito: mostra o estado de sucesso
    var timerEsvaziar = 0;

    function anunciar(msg) { status.textContent = msg; }
    function texto(sel, valor) { $$(sel).forEach(function (el) { el.textContent = valor; }); }
    function atual() { return normalizeCart(readCart()); }
    function acharItem(cart, id) { return cart.filter(function (i) { return i.id === id; })[0]; }

    function pintarTotais(cart) {
      var itens = 0, subtotal = 0;
      cart.forEach(function (i) { itens += i.qty; subtotal += i.price * i.qty; });
      texto('[data-gm-carrinho-itens]', String(itens));
      texto('[data-gm-carrinho-subtotal]', brl.format(subtotal));
      texto('[data-gm-carrinho-total]', brl.format(subtotal));
      texto('[data-gm-carrinho-parcelas]', 'ou 12x de ' + brl.format(subtotal / 12) + ' sem juros no cartão');
      cheio.hidden = concluido || cart.length === 0;
      vazio.hidden = concluido || cart.length > 0;
      sucesso.hidden = !concluido;
      return subtotal;
    }

    function pintarLinha(li, item) {
      $('input', li).value = String(item.qty);
      fill(li, 'subtotal', brl.format(item.price * item.qty));
    }

    function criarLinha(item) {
      var f = clone('tpl-carrinho-item');
      var li = f.firstElementChild;
      li.setAttribute('data-id', String(item.id));
      var img = $('img', li);
      img.src = item.img;                                  // já validado por cartImg()
      img.alt = item.title;
      img.className = 'gm-carrinho-item__img ' + item.img.slice(4).replace(/\.[a-z]+$/i, '');   // classe = nome do arquivo
      fill(li, 'title', item.title);
      fill(li, 'unit', brl.format(item.price));
      $('input', li).setAttribute('aria-label', 'Quantidade de ' + item.title);
      $('[data-gm-item-passo="-1"]', li).setAttribute('aria-label', 'Diminuir quantidade de ' + item.title);
      $('[data-gm-item-passo="1"]', li).setAttribute('aria-label', 'Aumentar quantidade de ' + item.title);
      $('[data-gm-item-remover]', li).setAttribute('aria-label', 'Remover ' + item.title + ' do carrinho');
      pintarLinha(li, item);
      return li;
    }

    // Monta tudo do zero (abertura da página e mudanças vindas de outra aba)
    function render() {
      var cart = atual();
      if (JSON.stringify(cart) !== JSON.stringify(readCart())) saveCart(cart);   // grava a versão saneada
      lista.textContent = '';
      cart.forEach(function (item) { lista.appendChild(criarLinha(item)); });
      pintarTotais(cart);
    }

    function alterarQtd(li, pedida) {
      var id = Number(li.getAttribute('data-id'));
      var cart = atual();
      var item = acharItem(cart, id);
      if (!item) { render(); return; }
      var n = Math.max(1, Math.min(MAX_QTY, pedida || 1));
      item.qty = n;
      saveCart(cart);
      pintarLinha(li, item);
      var total = pintarTotais(cart);
      anunciar((n !== pedida ? 'Quantidade permitida: de 1 a ' + MAX_QTY + '. ' : '') +
        item.title + ': ' + n + (n === 1 ? ' unidade' : ' unidades') + '. Total ' + brl.format(total) + '.');
    }

    function remover(li) {
      var id = Number(li.getAttribute('data-id'));
      var cart = atual();
      var item = acharItem(cart, id);
      cart = cart.filter(function (i) { return i.id !== id; });
      saveCart(cart);
      var vizinho = li.nextElementSibling || li.previousElementSibling;
      li.remove();
      pintarTotais(cart);
      anunciar((item ? item.title : 'Produto') + ' removido do carrinho.');
      // Foco não se perde: vai para o próximo item ou para o título do estado vazio
      if (vizinho) $('[data-gm-item-remover]', vizinho).focus();
      else $('#vazio-titulo').focus();
    }

    function resetarEsvaziar() {
      clearTimeout(timerEsvaziar);
      esvaziar.removeAttribute('data-confirmar');
      esvaziar.textContent = 'Esvaziar carrinho';
    }

    function mostrarSucesso(pedido, metodo) {
      var uuid = String(pedido && pedido.public_id || '');
      // Mesmo formato do painel (account.py): "GM-" + 8 primeiros hexadecimais do UUID
      var codigo = /^[0-9a-f-]{32,36}$/i.test(uuid) ? 'GM-' + uuid.replace(/-/g, '').slice(0, 8).toUpperCase() : '—';
      texto('[data-gm-pedido-codigo]', codigo);
      texto('[data-gm-pedido-total]', brl.format(Number(pedido && pedido.total) || 0));
      texto('[data-gm-pedido-pagamento]', PAGAMENTO_LABEL[metodo]);
      concluido = true;
      lista.textContent = '';
      pintarTotais([]);
      $('#sucesso-titulo').focus();
    }

    function finalizarCompra() {
      if (enviando) return;
      var cart = atual();
      if (!cart.length) { render(); return; }
      if (cart.length > MAX_ITENS_PEDIDO) {
        toast('Um pedido aceita até ' + MAX_ITENS_PEDIDO + ' produtos diferentes. Remova alguns itens.', true);
        return;
      }
      if (OFFLINE) { toast('Para finalizar a compra, abra o site pelo servidor (uvicorn).', true); return; }
      var marcado = $('input[name="gm-pagamento"]:checked');
      var metodo = marcado && PAGAMENTO_LABEL[marcado.value] ? marcado.value : 'pix';

      enviando = true;
      finalizar.disabled = true;
      finalizar.setAttribute('aria-busy', 'true');
      rotuloFinalizar.textContent = 'Enviando pedido…';

      apiFetch('/orders', {
        method: 'POST',
        body: {
          items: cart.map(function (i) { return { product_id: i.id, quantity: i.qty }; }),
          payment_method: metodo
        }
      }).then(function (pedido) {
        saveCart([]);
        mostrarSucesso(pedido, metodo);
        toast('Pedido realizado com sucesso!');
      }).catch(function (err) {
        if (err.status === 401) return;                    // apiFetch já levou para o login
        toast(ERRO_PEDIDO[err.status] || 'Não foi possível finalizar o pedido. Tente novamente em instantes.', true);
      }).then(function () {
        enviando = false;
        finalizar.disabled = false;
        finalizar.removeAttribute('aria-busy');
        rotuloFinalizar.textContent = 'Finalizar compra';
      });
    }

    lista.addEventListener('click', function (e) {
      var li = e.target.closest('.gm-carrinho-item');
      if (!li) return;
      var passo = e.target.closest('[data-gm-item-passo]');
      if (passo) {
        alterarQtd(li, Number($('input', li).value) + Number(passo.getAttribute('data-gm-item-passo')));
        return;
      }
      if (e.target.closest('[data-gm-item-remover]')) remover(li);
    });
    lista.addEventListener('change', function (e) {
      if (e.target.matches('input')) alterarQtd(e.target.closest('.gm-carrinho-item'), parseInt(e.target.value, 10));
    });

    // Esvaziar em 2 cliques: o 1º arma a confirmação por 4 s
    esvaziar.addEventListener('click', function () {
      if (!esvaziar.hasAttribute('data-confirmar')) {
        esvaziar.setAttribute('data-confirmar', '');
        esvaziar.textContent = 'Confirmar: esvaziar?';
        anunciar('Clique de novo para confirmar e esvaziar o carrinho.');
        timerEsvaziar = setTimeout(resetarEsvaziar, 4000);
        return;
      }
      resetarEsvaziar();
      saveCart([]);
      lista.textContent = '';
      pintarTotais([]);
      anunciar('Carrinho esvaziado.');
      $('#vazio-titulo').focus();
    });

    finalizar.addEventListener('click', finalizarCompra);

    // Outra aba mexeu no carrinho: redesenha (exceto depois do pedido concluído)
    window.addEventListener('storage', function (e) { if (e.key === CART_KEY && !concluido) render(); });

    render();
  }

  // ===========================================================================
  // 12. Entre ou cadastre-se — body[data-gm-pagina="entrar"]
  //     Abas Entrar / Criar conta, validação no navegador (espelha schemas.RegisterIn
  //     e LoginIn), POST /api/v1/auth/login | /register e volta para ?next=.
  //     Segurança:
  //       • ?next= só aceita caminho INTERNO do site (bloqueia //host, http:, javascript:,
  //         barra invertida, "..", espaços) → sem open redirect;
  //       • mensagens de erro genéricas: nunca revelam se um e-mail tem conta;
  //       • redirectOn401: false — senha errada não pode cair no goToLogin() (laço).
  // ===========================================================================
  var DESTINO_PADRAO = 'dashboard.html';
  var NOME_PROIBIDO = /[<>"'`]/;                           // mesmo filtro do schemas.RegisterIn
  var ERRO_AUTH = {
    403: 'Sua sessão de segurança expirou. Recarregue a página e tente de novo.',
    429: 'Muitas tentativas seguidas. Aguarde alguns minutos e tente de novo.'
  };
  var ERRO_LOGIN = {
    401: 'E-mail ou senha incorretos.',
    422: 'Confira o e-mail e a senha digitados.'
  };
  var ERRO_CADASTRO = {
    409: 'Não foi possível concluir o cadastro com esses dados. Se você já tem conta, use a aba Entrar.',
    422: 'Confira os dados: nome sem símbolos, e-mail válido e senha com pelo menos 10 caracteres.'
  };

  /**
   * Valida o ?next=. Aceita só "pagina.html" ou "/pasta/pagina.html" (+ query simples)
   * do próprio site; qualquer outra coisa → null (a página usa o destino padrão).
   */
  function destinoSeguro(bruto) {
    var s = typeof bruto === 'string' ? bruto : '';
    if (!s || s.length > 300) return null;
    // Pastas sem ponto (impede ".."), arquivo .html, query só com caracteres seguros.
    // "//evil.com", "/\evil.com", "https:…", "javascript:…" e "data:…" não casam.
    if (!/^\/?(?:[A-Za-z0-9_-]+\/)*[A-Za-z0-9._-]+\.html(?:\?[A-Za-z0-9=&%._~+-]*)?$/.test(s)) return null;
    if (/(^|\/)entreoucadastrese\.html/i.test(s)) return null;        // evita voltar para o próprio login
    try {                                                              // 2ª barreira: mesma origem de fato
      var u = new URL(s, location.href);
      if (u.protocol !== location.protocol || u.host !== location.host) return null;
    } catch (e) { return null; }
    return s;
  }

  function initEntrar() {
    if (document.body.getAttribute('data-gm-pagina') !== 'entrar') return;

    var params = new URLSearchParams(location.search);
    var destino = destinoSeguro(params.get('next'));
    var aviso = $('[data-gm-auth-continuar]');
    if (aviso) aviso.hidden = !destino;

    // ---- Abas (Bootstrap; sem o JS do Bootstrap, alterna as classes à mão) ----
    function mostrarAba(nome) {
      var botao = $('#aba-' + nome);
      if (!botao) return;
      if (window.bootstrap && bootstrap.Tab) { bootstrap.Tab.getOrCreateInstance(botao).show(); return; }
      $$('.gm-auth__abas .nav-link').forEach(function (b) {
        var ativo = b === botao;
        b.classList.toggle('active', ativo);
        b.setAttribute('aria-selected', ativo ? 'true' : 'false');
        b.setAttribute('tabindex', ativo ? '0' : '-1');
        var painel = $(b.getAttribute('data-bs-target'));
        if (!painel) return;
        painel.classList.toggle('show', ativo);
        painel.classList.toggle('active', ativo);
      });
    }
    if (params.get('aba') === 'cadastro' || location.hash === '#criar-conta') mostrarAba('cadastro');

    // Links "Cadastre-se aqui" / "Clique aqui para entrar": troca a aba e foca o 1º campo
    document.addEventListener('click', function (e) {
      var link = e.target.closest('[data-gm-auth-ir]');
      if (!link) return;
      e.preventDefault();
      var nome = link.getAttribute('data-gm-auth-ir') === 'cadastro' ? 'cadastro' : 'entrar';
      mostrarAba(nome);
      var campo = $('#painel-' + nome + ' input');
      if (campo) setTimeout(function () { campo.focus(); }, 200);   // depois do fade da aba
    });

    // ---- Mostrar / ocultar senha ----
    $$('[data-gm-senha-ver]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var campo = document.getElementById(btn.getAttribute('aria-controls'));
        if (!campo) return;
        var mostrar = campo.type === 'password';
        campo.type = mostrar ? 'text' : 'password';
        btn.setAttribute('aria-pressed', mostrar ? 'true' : 'false');
        btn.setAttribute('aria-label', mostrar ? 'Ocultar senha' : 'Mostrar senha');
        btn.textContent = mostrar ? 'Ocultar' : 'Mostrar';
      });
    });

    // ---- Validação (marca o campo com .is-invalid + aria-invalid) ----
    function marcar(campo, invalido) {
      campo.classList.toggle('is-invalid', invalido);
      if (invalido) campo.setAttribute('aria-invalid', 'true');
      else campo.removeAttribute('aria-invalid');
      return invalido;
    }
    // Regra de cada campo (espelha schemas.LoginIn / RegisterIn)
    function campoInvalido(campo, form) {
      var v = campo.value;
      var cadastro = form.getAttribute('data-gm-auth') === 'cadastro';
      switch (campo.name) {
        case 'email':
          v = v.trim();
          return !v || v.length > 254 || !campo.checkValidity() || v.indexOf('.', v.indexOf('@')) === -1;
        case 'name':
          v = v.trim();
          return v.length < 2 || v.length > 100 || NOME_PROIBIDO.test(v);
        case 'password':
          return cadastro ? v.length < 10 || v.length > 128 : !v;
        case 'confirmar':
          return !v || v !== $('input[name="password"]', form).value;
        default:
          return false;
      }
    }
    function validar(form) {
      return $$('input', form).filter(function (c) {
        if (c.name === 'email') c.value = c.value.trim();
        return marcar(c, campoInvalido(c, form));
      });
    }

    // Corrigiu um campo marcado → reavalia só ele, na hora (sem esperar novo envio)
    document.addEventListener('input', function (e) {
      var campo = e.target;
      if (!campo.matches || !campo.matches('.gm-auth__form .is-invalid')) return;
      marcar(campo, campoInvalido(campo, campo.form));
    });

    function mostrarErro(form, msg) {
      var caixa = $('[data-gm-auth-erro]', form);
      caixa.textContent = msg || '';
      caixa.hidden = !msg;
    }

    // ---- Envio ----
    $$('form[data-gm-auth]').forEach(function (form) {
      var botao = $('[data-gm-auth-enviar]', form);
      var rotulo = $('[data-gm-auth-rotulo]', form);
      var textoBotao = rotulo.textContent;
      var enviando = false;

      form.addEventListener('submit', function (e) {
        e.preventDefault();
        if (enviando) return;
        mostrarErro(form, '');
        var problemas = validar(form);
        if (problemas.length) { problemas[0].focus(); return; }
        if (OFFLINE) { mostrarErro(form, 'Para entrar ou criar sua conta, abra o site pelo servidor (uvicorn).'); return; }

        var cadastro = form.getAttribute('data-gm-auth') === 'cadastro';
        var senha = $('input[name="password"]', form);
        var corpo = { email: $('input[name="email"]', form).value, password: senha.value };
        if (cadastro) corpo.name = $('input[name="name"]', form).value.trim();

        enviando = true;
        botao.disabled = true;
        botao.setAttribute('aria-busy', 'true');
        rotulo.textContent = cadastro ? 'Criando sua conta…' : 'Entrando…';

        apiFetch(cadastro ? '/auth/register' : '/auth/login', { method: 'POST', body: corpo, redirectOn401: false })
          .then(function () {
            rotulo.textContent = cadastro ? 'Conta criada! Redirecionando…' : 'Pronto! Redirecionando…';
            location.replace(destino || DESTINO_PADRAO);     // replace: "voltar" não reabre o login
          })
          .catch(function (err) {
            var mapa = cadastro ? ERRO_CADASTRO : ERRO_LOGIN;
            mostrarErro(form, mapa[err.status] || ERRO_AUTH[err.status] ||
              'Não foi possível falar com a loja agora. Tente novamente em instantes.');
            if (!cadastro && err.status === 401) { senha.value = ''; senha.focus(); }
            enviando = false;
            botao.disabled = false;
            botao.removeAttribute('aria-busy');
            rotulo.textContent = textoBotao;
          });
      });
    });
  }

  // ===========================================================================
  // 13. Ordenação de vitrines — <select data-gm-ordenar="#lista">
  //     Componente reutilizável (computadores.html; próximas: hardware, periféricos…).
  //     Contrato do HTML:
  //       • <select data-gm-ordenar="#id-da-lista"> com options relevancia | preco-asc |
  //         preco-desc | nome-asc | nome-desc (só os valores de ORDENS são aceitos);
  //       • itens da lista: [data-gm-ordenar-item][data-ordem-preco="1234.56"][data-ordem-nome="…"];
  //       • opcional: [data-gm-ordenar-caixa] (fica hidden até o JS rodar — sem JS não aparece
  //         um seletor que não funciona) e [data-gm-ordenar-contagem="#id-da-lista"]
  //         com data-singular / data-plural (role=status: o leitor de tela anuncia a mudança).
  //     Reordena movendo os próprios nós (sem recriar HTML → nada de innerHTML, eventos
  //     e imagens já carregadas são preservados). A escolha vai para ?ordem= (link
  //     compartilhável, "voltar" preserva) e só é lida de volta se estiver na lista branca.
  // ===========================================================================
  var ORDENS = {
    'relevancia': { rotulo: 'por relevância' },
    'preco-asc':  { rotulo: 'do menor para o maior preço' },
    'preco-desc': { rotulo: 'do maior para o menor preço' },
    'nome-asc':   { rotulo: 'por nome, de A a Z' },
    'nome-desc':  { rotulo: 'por nome, de Z a A' }
  };
  var compararNomes = new Intl.Collator('pt-BR', { sensitivity: 'base', numeric: true }).compare;

  /** Ordena uma cópia dos itens. Empate (ex.: dois PCs de R$ 7.499) mantém a ordem original. */
  function ordenarItens(itens, ordem) {
    function preco(el) { var v = parseFloat(el.getAttribute('data-ordem-preco')); return isFinite(v) ? v : Infinity; }
    function nome(el) { return el.getAttribute('data-ordem-nome') || ''; }
    function pos(el) { return Number(el.getAttribute('data-ordem-pos')) || 0; }
    return itens.slice().sort(function (a, b) {
      var r = 0;
      if (ordem === 'preco-asc') r = preco(a) - preco(b);
      else if (ordem === 'preco-desc') r = preco(b) - preco(a);
      else if (ordem === 'nome-asc') r = compararNomes(nome(a), nome(b));
      else if (ordem === 'nome-desc') r = compararNomes(nome(b), nome(a));
      return r || pos(a) - pos(b);
    });
  }

  function pintarContagem(alvoSel, ordem) {
    $$('[data-gm-ordenar-contagem]').forEach(function (el) {
      if (el.getAttribute('data-gm-ordenar-contagem') !== alvoSel) return;
      var lista = document.querySelector(alvoSel);
      if (!lista) return;
      var n = $$('[data-gm-ordenar-item]', lista).filter(function (i) { return !i.hidden; }).length;
      var forte = document.createElement('strong');
      forte.textContent = String(n);
      var palavra = n === 1 ? (el.getAttribute('data-singular') || 'item') : (el.getAttribute('data-plural') || 'itens');
      el.textContent = '';
      el.append(forte, ' ' + palavra);
      // Aba de tipo ativa (seção 14) — o rótulo vem do texto do próprio botão
      var filtro = lista.getAttribute('data-gm-filtro-rotulo');
      if (filtro) {
        var detFiltro = document.createElement('span');
        detFiltro.className = 'gm-ordenar-barra__detalhe';
        detFiltro.textContent = ' · ' + filtro;
        el.append(detFiltro);
      }
      if (ordem && ordem !== 'relevancia' && ORDENS[ordem]) {
        var detalhe = document.createElement('span');
        detalhe.className = 'gm-ordenar-barra__detalhe';
        detalhe.textContent = ' · ' + ORDENS[ordem].rotulo;
        el.append(detalhe);
      }
    });
  }

  function initOrdenar() {
    $$('select[data-gm-ordenar]').forEach(function (sel) {
      var alvoSel = sel.getAttribute('data-gm-ordenar') || '';
      if (!/^#[A-Za-z][\w-]*$/.test(alvoSel)) return;      // só um id simples: nada de seletor arbitrário
      var lista = document.querySelector(alvoSel);
      if (!lista) return;
      var itens = $$('[data-gm-ordenar-item]', lista);
      if (!itens.length) return;
      itens.forEach(function (el, i) { el.setAttribute('data-ordem-pos', String(i)); });   // ordem "Relevância"

      function aplicar(ordem, gravarUrl) {
        if (!Object.prototype.hasOwnProperty.call(ORDENS, ordem)) ordem = 'relevancia';
        sel.value = ordem;
        var frag = document.createDocumentFragment();
        ordenarItens(itens, ordem).forEach(function (el) { frag.appendChild(el); });   // move, não recria
        lista.appendChild(frag);
        lista.setAttribute('data-gm-ordem', ordem);
        pintarContagem(alvoSel, ordem);
        if (gravarUrl) {
          var url = new URL(location.href);
          if (ordem === 'relevancia') url.searchParams.delete('ordem'); else url.searchParams.set('ordem', ordem);
          try { history.replaceState(null, '', url.pathname + url.search + url.hash); } catch (e) { /* file:// restrito */ }
        }
      }

      var caixa = sel.closest('[data-gm-ordenar-caixa]');
      if (caixa) caixa.hidden = false;
      sel.addEventListener('change', function () { aplicar(sel.value, true); });
      var pedida = (new URLSearchParams(location.search).get('ordem') || '').slice(0, 20);
      aplicar(pedida, false);                              // inválida → relevância (lista branca)
    });
  }

  // ===========================================================================
  // 14. Abas de tipo nas vitrines — <div data-gm-filtrar="#lista">
  //     Componente reutilizável (hardware.html; próximas: periféricos, escritório…).
  //     Contrato do HTML:
  //       • contêiner [data-gm-filtrar="#id-da-lista"] (role=group, começa hidden: sem JS
  //         a lista completa aparece e não sobra botão sem função);
  //       • botões [data-gm-filtro="todos"|"<tipo>"] com aria-pressed e, dentro deles,
  //         [data-gm-filtro-qtd] (o JS preenche com a quantidade de itens do tipo);
  //       • itens da lista: [data-gm-ordenar-item][data-gm-tipo="<tipo>"].
  //     Filtra só com o atributo hidden (nada é recriado) e reaproveita a contagem da
  //     seção 13 (role=status anuncia "3 produtos · Placas de vídeo"). Convive com a
  //     ordenação: ordenar move todos os itens, filtrar só mostra/esconde.
  //     A escolha vai para ?tipo= e só é aceita de volta se existir um botão com esse valor
  //     (lista branca montada a partir do próprio HTML).
  // ===========================================================================
  function initFiltrar() {
    $$('[data-gm-filtrar]').forEach(function (grupo) {
      var alvoSel = grupo.getAttribute('data-gm-filtrar') || '';
      if (!/^#[A-Za-z][\w-]*$/.test(alvoSel)) return;      // só um id simples
      var lista = document.querySelector(alvoSel);
      if (!lista) return;
      var itens = $$('[data-gm-ordenar-item]', lista);
      var botoes = $$('button[data-gm-filtro]', grupo);
      if (!itens.length || !botoes.length) return;

      // Lista branca: valores dos botões que existem na página (formato seguro)
      var validos = {};
      botoes.forEach(function (b) {
        var v = b.getAttribute('data-gm-filtro') || '';
        if (/^[a-z0-9-]{1,40}$/.test(v)) validos[v] = b;
      });
      if (!validos.todos) return;

      // Quantidade de cada aba (o HTML não precisa manter número fixo à mão)
      botoes.forEach(function (b) {
        var v = b.getAttribute('data-gm-filtro');
        var n = v === 'todos' ? itens.length
          : itens.filter(function (i) { return i.getAttribute('data-gm-tipo') === v; }).length;
        var qtd = b.querySelector('[data-gm-filtro-qtd]');
        if (qtd) qtd.textContent = String(n);
        if (!n && v !== 'todos') b.hidden = true;            // aba vazia não aparece
      });

      function rotuloDe(botao) {
        // Texto do botão sem o número da quantidade (ex.: "Placas de vídeo")
        var partes = [];
        botao.childNodes.forEach(function (n) { if (n.nodeType === 3) partes.push(n.textContent); });
        return partes.join('').trim();
      }

      function aplicar(tipo, gravarUrl) {
        if (!Object.prototype.hasOwnProperty.call(validos, tipo) || validos[tipo].hidden) tipo = 'todos';
        itens.forEach(function (el) {
          el.hidden = tipo !== 'todos' && el.getAttribute('data-gm-tipo') !== tipo;
        });
        botoes.forEach(function (b) {
          b.setAttribute('aria-pressed', b.getAttribute('data-gm-filtro') === tipo ? 'true' : 'false');
        });
        lista.setAttribute('data-gm-tipo-ativo', tipo);
        if (tipo === 'todos') lista.removeAttribute('data-gm-filtro-rotulo');
        else lista.setAttribute('data-gm-filtro-rotulo', rotuloDe(validos[tipo]));
        pintarContagem(alvoSel, lista.getAttribute('data-gm-ordem') || 'relevancia');
        if (gravarUrl) {
          var url = new URL(location.href);
          if (tipo === 'todos') url.searchParams.delete('tipo'); else url.searchParams.set('tipo', tipo);
          try { history.replaceState(null, '', url.pathname + url.search + url.hash); } catch (e) { /* file:// restrito */ }
        }
      }

      botoes.forEach(function (b) {
        b.addEventListener('click', function () { aplicar(b.getAttribute('data-gm-filtro'), true); });
      });
      grupo.hidden = false;
      var pedido = (new URLSearchParams(location.search).get('tipo') || '').slice(0, 40);
      aplicar(pedido, false);                              // inválido → "todos" (lista branca)
    });
  }

  // ===========================================================================
  // 15. Perguntas frequentes — <input data-gm-faq-busca="#lista"> (suporte.html)
  //     Contrato do HTML:
  //       • lista #id com grupos [data-gm-faq-grupo] e, dentro deles, itens
  //         [data-gm-faq-item] (accordion-item do Bootstrap, com id próprio);
  //       • caixa da busca [data-gm-faq-busca-caixa] começa hidden (sem JS tudo aparece);
  //       • status [data-gm-faq-status] (role=status), estado vazio [data-gm-faq-vazio]
  //         e atalhos [data-gm-faq-atalhos] (somem durante a busca).
  //     Busca sem acento e sem diferenciar maiúsculas (pergunta + resposta), só com
  //     hidden + textContent. Link direto para uma pergunta: suporte.html#faq-frete-prazo
  //     abre a resposta; abrir uma pergunta grava o #id na URL (link compartilhável).
  //     O hash só é aceito se for o id de um item existente (lista branca do próprio HTML).
  // ===========================================================================
  function initFaq() {
    var input = $('[data-gm-faq-busca]');
    if (!input) return;
    var alvoSel = input.getAttribute('data-gm-faq-busca') || '';
    if (!/^#[A-Za-z][\w-]*$/.test(alvoSel)) return;        // só um id simples
    var lista = document.querySelector(alvoSel);
    if (!lista) return;
    var itens = $$('[data-gm-faq-item]', lista);
    if (!itens.length) return;

    var grupos = $$('[data-gm-faq-grupo]', lista);
    var status = $('[data-gm-faq-status]');
    var vazio = $('[data-gm-faq-vazio]');
    var atalhos = $('[data-gm-faq-atalhos]');
    var caixa = $('[data-gm-faq-busca-caixa]');
    var textos = itens.map(function (el) { return normalizar(el.textContent); });
    var porId = {};
    itens.forEach(function (el) { if (/^faq-[a-z0-9-]{1,60}$/.test(el.id)) porId[el.id] = el; });

    function colapso(item) {
      var painel = $('.accordion-collapse', item);
      return painel && window.bootstrap ? window.bootstrap.Collapse.getOrCreateInstance(painel, { toggle: false }) : null;
    }

    function aplicar(termo) {
      var t = normalizar(termo);
      var visiveis = 0;
      itens.forEach(function (el, i) {
        var mostra = !t || textos[i].indexOf(t) !== -1;
        el.hidden = !mostra;
        if (mostra) visiveis++;
      });
      grupos.forEach(function (g) { g.hidden = !$('[data-gm-faq-item]:not([hidden])', g); });
      if (atalhos) atalhos.hidden = !!t;
      if (vazio) vazio.hidden = !t || visiveis > 0;
      if (!status) return;
      status.textContent = '';
      if (!t) return;
      var forte = document.createElement('strong');
      forte.textContent = String(visiveis);
      status.append(forte, visiveis === 1 ? ' dúvida encontrada para “' : ' dúvidas encontradas para “', termo.trim(), '”');
    }

    var timer = 0;
    input.addEventListener('input', function () {
      clearTimeout(timer);
      timer = setTimeout(function () { aplicar(input.value); }, 120);
    });
    if (input.form) input.form.addEventListener('submit', function (e) { e.preventDefault(); aplicar(input.value); });
    if (caixa) caixa.hidden = false;

    // Abrir uma pergunta grava o #id na URL (sem pular a página)
    itens.forEach(function (item) {
      item.addEventListener('shown.bs.collapse', function () {
        if (!porId[item.id]) return;
        try { history.replaceState(null, '', location.pathname + location.search + '#' + item.id); } catch (e) { /* file:// */ }
      });
    });

    // Link direto: #faq-<id> abre a resposta e rola até ela
    function abrirDoHash() {
      var id = decodeURIComponent(location.hash.slice(1)).slice(0, 70);
      if (!Object.prototype.hasOwnProperty.call(porId, id)) return;
      var item = porId[id];
      var c = colapso(item);
      if (c) c.show();
      item.scrollIntoView({ block: 'start' });
    }
    window.addEventListener('hashchange', abrirDoHash);
    abrirDoHash();
  }

  // ===========================================================================
  // 16. Página não encontrada — body[data-gm-pagina="404"] (404.html)
  //     • Mostra o endereço que a pessoa tentou abrir (só textContent, limitado a
  //       120 caracteres). Aberta direto (404.html) ou por duplo clique, fica escondido.
  //     • Botão "Voltar" só aparece quando a visita veio de outra página do próprio
  //       site (referrer da mesma origem) — evita mandar a pessoa para fora da loja.
  //     • Em rotas aninhadas o servidor insere <base href="/"> (backend/app/frontend.py);
  //       com ele, "#conteudo" viraria "/#conteudo" (a home). Os links de âncora são
  //       tratados aqui para continuarem na própria página (pular para o conteúdo).
  // ===========================================================================
  function initPagina404() {
    if (document.body.getAttribute('data-gm-pagina') !== '404') return;

    // Endereço procurado
    var caixa = $('[data-gm-404-endereco-caixa]');
    var alvo = $('[data-gm-404-endereco]');
    var caminho = location.pathname + location.search;
    if (caixa && alvo && !OFFLINE && !/\/404\.html$/.test(location.pathname)) {
      try { caminho = decodeURI(caminho); } catch (e) { /* %xx inválido: mostra como veio */ }
      alvo.textContent = caminho.length > 120 ? caminho.slice(0, 119) + '…' : caminho;
      caixa.hidden = false;
    }

    // Voltar à página anterior (só dentro do site)
    var voltar = $('[data-gm-voltar]');
    var origemInterna = false;
    try { origemInterna = !!document.referrer && new URL(document.referrer).origin === location.origin; } catch (e) { /* referrer inválido */ }
    if (voltar && origemInterna && history.length > 1) {
      voltar.hidden = false;
      voltar.addEventListener('click', function () { history.back(); });
    }

    // Âncoras na própria página mesmo com <base href="/">
    if (!$('base[href]')) return;
    document.addEventListener('click', function (e) {
      var link = e.target && e.target.closest ? e.target.closest('a[href^="#"]') : null;
      if (!link) return;
      var id = link.getAttribute('href').slice(1);
      var destino = /^[A-Za-z][\w-]{0,60}$/.test(id) ? document.getElementById(id) : null;
      if (!destino) return;
      e.preventDefault();
      destino.scrollIntoView({ block: 'start' });
      destino.focus({ preventScroll: true });
    });
  }

  // ===========================================================================
  // 17. Boot
  // ===========================================================================
  function boot() {
    initImagens();
    initConsent();
    initUser();
    initSearch();
    initQuantity();
    initCart();
    initFavorites();
    initDashboard();
    initCarrinho();
    initEntrar();
    initOrdenar();
    initFiltrar();     // depois da ordenação: a contagem já sabe a ordem escolhida
    initFaq();
    initPagina404();
  }

  window.GMUI = {
    apiFetch: apiFetch, toast: toast, cart: { read: readCart, add: addToCart },
    auth: { destinoSeguro: destinoSeguro },                // exposto para os testes E2E
    ordenar: { ordens: Object.keys(ORDENS) }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})(window, document);
