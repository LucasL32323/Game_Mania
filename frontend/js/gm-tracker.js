/*!
 * GameMania 2.0 — gm-tracker.js
 * Engine de telemetria first-party (vanilla JS, zero dependências, ~5 KB gzip).
 *
 * O que captura
 *   • page_view ........ início de cada visualização (+ página anterior = histórico de navegação)
 *   • engagement ....... tempo ATIVO na página (aba visível + usuário não ocioso) e scroll máximo
 *   • favorite_add/remove, add_to_cart, begin_checkout, click ... via atributos [data-track]
 *   • search ........... envio de form[role="search"]
 *
 * Como não afeta a performance
 *   • Listeners passivos; scroll processado 1x por frame (requestAnimationFrame).
 *   • Nada é enviado na hora do clique: eventos vão para uma fila em memória e saem
 *     em lotes (≤ 25 eventos / ≤ 60 KB) no requestIdleCallback — sem competir com o render.
 *   • Heartbeats de engajamento são COALESCIDOS (1 por página na fila, o servidor faz GREATEST).
 *   • Saída da página: fetch keepalive (fallback sendBeacon) → sem bloquear a navegação.
 *   • Rede falhou? Backoff exponencial com jitter; offline → persiste e envia na próxima página.
 *
 * Segurança e LGPD
 *   • NÃO envia user_id: o servidor identifica o usuário pelo cookie HttpOnly de sessão
 *     (o script legado lia <meta name="user-id"> e qualquer um podia forjar eventos).
 *   • Opt-in: nada é coletado nem gravado no navegador sem o cookie gm_consent=analytics.
 *     Global Privacy Control (navigator.globalPrivacyControl) = recusa por padrão.
 *   • Só caminhos são enviados — query string e fragmento são descartados (podem conter tokens).
 *   • CSRF: token double-submit no header X-CSRF-Token (ou no corpo, no fallback do sendBeacon).
 *
 * API pública: window.GMTracker = { track, setConsent, hasConsent, flush, history, version }
 * Configuração opcional ANTES deste script: window.GM_TRACKER_CONFIG = { debug: true, ... }
 */
(function (window, document) {
  'use strict';

  if (window.GMTracker) return;                       // proteção contra inclusão dupla

  // Página aberta direto do disco (file://): não existe API → tracker desligado,
  // mas com a mesma interface para o gm-ui.js não precisar de "if".
  if (location.protocol === 'file:') {
    window.GMTracker = {
      version: '2.0.0', offline: true,
      track: function () { return false; },
      setConsent: function () {},
      hasConsent: function () { return false; },
      consentDecided: function () { return true; },     // sem banner: não há o que consentir
      gpc: function () { return false; },
      flush: function () { return Promise.resolve(); },
      history: function () { return []; }
    };
    return;
  }

  // ---------------------------------------------------------------------------
  // 1. Configuração
  // ---------------------------------------------------------------------------
  var cfg = Object.assign(
    {
      endpoint: '/api/v1/track',
      csrfEndpoint: '/api/v1/csrf',
      heartbeatMs: 15000,          // amostra de engajamento
      flushMs: 10000,              // envio periódico da fila
      idleMs: 60000,               // sem interação por 60 s = ocioso (para de contar)
      sessionTimeoutMs: 30 * 60 * 1000,
      maxBatchEvents: 25,          // o servidor aceita até 50; margem de segurança
      maxBatchBytes: 60 * 1024,    // limite do keepalive/sendBeacon é 64 KB
      maxQueue: 200,               // backpressure local: descarta os mais antigos
      maxTrail: 20,                // páginas guardadas no histórico local
      debug: false
    },
    window.GM_TRACKER_CONFIG || {}
  );

  var KEY_SESSION = 'gm_sess';
  var KEY_VISITOR = 'gm_vid';
  var KEY_TRAIL = 'gm_trail';
  var KEY_PENDING = 'gm_q';
  var CONSENT_COOKIE = 'gm_consent';

  // Espelha o regex do servidor (schemas.PATH_PATTERN)
  var PATH_OK = /^\/[A-Za-z0-9\-._~/%]{0,511}$/;
  var PROP_KEY_OK = /^[a-z_]{1,32}$/;

  // Ações declaradas em data-track → tipo de evento aceito pela API
  var ACTION_MAP = {
    favorite_add: 'favorite_add',
    favorite_remove: 'favorite_remove',
    add_to_cart: 'add_to_cart',
    begin_checkout: 'begin_checkout',
    buy_now: 'begin_checkout'
  };

  // ---------------------------------------------------------------------------
  // 2. Estado
  // ---------------------------------------------------------------------------
  var state = {
    running: false,
    session: null,          // { id, last }
    visitorId: null,
    pageView: null,         // { id, path, referrerPath, productId, lastSentSeconds }
    queue: [],
    sending: false,
    retryAttempt: 0,
    retryTimer: 0,
    flushTimer: 0,
    heartbeatTimer: 0,
    idleTimer: 0,
    idleScheduled: false,
    forceCsrf: false,
    csrfPromise: null
  };

  // Relógio de tempo ativo (performance.now é monotônico: imune a mudança de hora)
  var clock = { activeMs: 0, since: null, lastInput: now() };
  var scroll = { max: 0, ticking: false };

  // ---------------------------------------------------------------------------
  // 3. Utilitários
  // ---------------------------------------------------------------------------
  function now() { return window.performance ? performance.now() : Date.now(); }

  function log() {
    if (cfg.debug && window.console) console.debug.apply(console, ['[GMTracker]'].concat([].slice.call(arguments)));
  }

  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    var b = crypto.getRandomValues(new Uint8Array(16));
    b[6] = (b[6] & 0x0f) | 0x40;                      // versão 4
    b[8] = (b[8] & 0x3f) | 0x80;                      // variante RFC 4122
    var h = [].map.call(b, function (x) { return (x + 0x100).toString(16).slice(1); }).join('');
    return h.slice(0, 8) + '-' + h.slice(8, 12) + '-' + h.slice(12, 16) + '-' + h.slice(16, 20) + '-' + h.slice(20);
  }

  function store(kind) {                              // localStorage pode lançar (Safari privado, cota)
    try { return window[kind]; } catch (e) { return null; }
  }
  function readJSON(key) {
    var s = store('localStorage');
    try { return s ? JSON.parse(s.getItem(key)) : null; } catch (e) { return null; }
  }
  function writeJSON(key, value) {
    var s = store('localStorage');
    try { if (s) s.setItem(key, JSON.stringify(value)); } catch (e) { /* cota cheia: ignora */ }
  }
  function removeKey(key) {
    var s = store('localStorage');
    try { if (s) s.removeItem(key); } catch (e) { /* noop */ }
  }

  function getCookie(name) {
    var parts = document.cookie ? document.cookie.split('; ') : [];
    for (var i = 0; i < parts.length; i++) {
      var eq = parts[i].indexOf('=');
      if (parts[i].slice(0, eq) === name) return decodeURIComponent(parts[i].slice(eq + 1));
    }
    return null;
  }

  function readCsrfCookie() { return getCookie('__Host-gm_csrf') || getCookie('gm_csrf'); }

  /** Só o caminho, codificado para passar no regex do servidor. */
  function sanitizePath(pathname) {
    var p = String(pathname || '/').replace(/[^A-Za-z0-9\-._~/%]/g, function (c) {
      var code = c.charCodeAt(0);
      return code < 128 ? '%' + (code < 16 ? '0' : '') + code.toString(16).toUpperCase() : '';
    });
    if (p.charAt(0) !== '/') p = '/' + p;
    p = p.slice(0, 512);
    return PATH_OK.test(p) ? p : '/';
  }

  function referrerInfo() {
    if (!document.referrer) return { path: null, host: null };
    try {
      var url = new URL(document.referrer);
      if (url.origin === location.origin) return { path: sanitizePath(url.pathname), host: null };
      return { path: null, host: /^[A-Za-z0-9.\-:]+$/.test(url.host) ? url.host.slice(0, 255) : null };
    } catch (e) {
      return { path: null, host: null };
    }
  }

  function currentProductId() {
    var id = parseInt(document.body && document.body.getAttribute('data-product-id'), 10);
    return id > 0 ? id : null;
  }

  /** Converte data-track-* do elemento em props (chave [a-z_], valor ≤ 120 chars, máx. 8). */
  function propsFrom(el) {
    var props = {};
    var count = 0;
    for (var i = 0; i < el.attributes.length && count < 8; i++) {
      var attr = el.attributes[i];
      if (attr.name.indexOf('data-track-') !== 0) continue;
      var key = attr.name.slice(11).replace(/-/g, '_');
      if (!PROP_KEY_OK.test(key)) continue;
      props[key] = coerce(attr.value);
      count++;
    }
    return count ? props : null;
  }

  function coerce(value) {
    var v = String(value).replace(/[\u0000-\u001f\u007f]/g, '').trim().slice(0, 120);
    return /^-?\d{1,9}(\.\d+)?$/.test(v) ? Number(v) : v;
  }

  function scheduleIdle(fn) {
    if (window.requestIdleCallback) return requestIdleCallback(fn, { timeout: 2000 });
    return setTimeout(fn, 1);
  }

  // ---------------------------------------------------------------------------
  // 4. Consentimento (LGPD)
  // ---------------------------------------------------------------------------
  function consentValue() { return getCookie(CONSENT_COOKIE); }

  function hasConsent() {
    // Opt-in explícito. Sem cookie = sem coleta (inclusive com GPC ativo).
    return consentValue() === 'analytics';
  }

  function setConsent(granted) {
    var secure = location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = CONSENT_COOKIE + '=' + (granted ? 'analytics' : 'none') +
      '; Max-Age=' + 60 * 60 * 24 * 180 + '; Path=/; SameSite=Lax' + secure;

    if (granted) {
      start();
    } else {
      stop();
      // Direito de revogação: apaga tudo que o tracker guardou no navegador
      [KEY_SESSION, KEY_VISITOR, KEY_TRAIL, KEY_PENDING].forEach(removeKey);
    }
    document.dispatchEvent(new CustomEvent('gm:consent', { detail: { analytics: !!granted } }));
  }

  // ---------------------------------------------------------------------------
  // 5. Sessão, visitante e histórico de navegação
  // ---------------------------------------------------------------------------
  function ensureSession() {
    var t = Date.now();
    var s = state.session || readJSON(KEY_SESSION);
    if (!s || !s.id || t - (s.last || 0) > cfg.sessionTimeoutMs) {
      s = { id: uuid(), last: t };
      removeKey(KEY_TRAIL);                              // histórico é por sessão
      log('nova sessão', s.id);
    }
    s.last = t;
    state.session = s;
    writeJSON(KEY_SESSION, s);

    if (!state.visitorId) {
      state.visitorId = readJSON(KEY_VISITOR);
      if (!state.visitorId) { state.visitorId = uuid(); writeJSON(KEY_VISITOR, state.visitorId); }
    }
    return s;
  }

  function touchSession() {
    if (!state.session) return;
    state.session.last = Date.now();
    writeJSON(KEY_SESSION, state.session);
  }

  function pushTrail(path) {
    var trail = readJSON(KEY_TRAIL) || [];
    trail.push({ p: path, t: Date.now() });
    writeJSON(KEY_TRAIL, trail.slice(-cfg.maxTrail));
  }

  function history() { return (readJSON(KEY_TRAIL) || []).slice(); }

  // ---------------------------------------------------------------------------
  // 6. Tempo ativo e scroll
  // ---------------------------------------------------------------------------
  function resumeClock() {
    if (clock.since === null && document.visibilityState === 'visible') clock.since = now();
  }
  function pauseClock(at) {
    if (clock.since === null) return;
    clock.activeMs += Math.max(0, (at || now()) - clock.since);
    clock.since = null;
  }
  function activeSeconds() {
    var ms = clock.activeMs + (clock.since === null ? 0 : now() - clock.since);
    return Math.min(86400, Math.round(ms / 1000));
  }
  function resetClock() {
    clock.activeMs = 0; clock.since = null; clock.lastInput = now();
    scroll.max = 0;
    resumeClock();
  }

  function onInput() {                                // chamado por mousemove/scroll/tecla: O(1)
    clock.lastInput = now();
    resumeClock();
  }

  function checkIdle() {                              // leitura sem mexer o mouse conta até idleMs
    if (clock.since !== null && now() - clock.lastInput > cfg.idleMs) {
      pauseClock(clock.lastInput + cfg.idleMs);
      log('ocioso — relógio pausado');
    }
  }

  function measureScroll() {
    scroll.ticking = false;
    var doc = document.documentElement;
    var height = Math.max(doc.scrollHeight, document.body ? document.body.scrollHeight : 0);
    var pct = height > 0 ? Math.round(((window.scrollY || doc.scrollTop) + window.innerHeight) / height * 100) : 100;
    if (pct > scroll.max) scroll.max = Math.min(100, pct);
  }
  function onScroll() {
    onInput();
    if (!scroll.ticking) { scroll.ticking = true; requestAnimationFrame(measureScroll); }
  }

  // ---------------------------------------------------------------------------
  // 7. Page views e engajamento
  // ---------------------------------------------------------------------------
  function startPageView() {
    ensureSession();
    var ref = referrerInfo();
    state.referrerHost = ref.host;
    state.pageView = {
      id: uuid(),
      path: sanitizePath(location.pathname),
      referrerPath: ref.path,
      productId: currentProductId(),
      lastSentSeconds: -1
    };
    resetClock();
    requestAnimationFrame(measureScroll);              // páginas curtas já começam em 100%
    pushTrail(state.pageView.path);
    enqueue(baseEvent('page_view'));
  }

  function baseEvent(type) {
    var pv = state.pageView;
    var ev = { type: type, ts: new Date().toISOString(), page_view_id: pv.id, path: pv.path };
    if (pv.referrerPath && type === 'page_view') ev.referrer_path = pv.referrerPath;
    if (pv.productId) ev.product_id = pv.productId;
    return ev;
  }

  function sampleEngagement(force) {
    if (!state.running || !state.pageView) return;
    checkIdle();
    var secs = activeSeconds();
    if (!force && secs === state.pageView.lastSentSeconds) return;   // nada mudou: não gera ruído
    state.pageView.lastSentSeconds = secs;
    var ev = baseEvent('engagement');
    ev.active_seconds = secs;
    ev.scroll_pct = scroll.max;
    enqueue(ev);
  }

  // ---------------------------------------------------------------------------
  // 8. Fila e envio em lote
  // ---------------------------------------------------------------------------
  function enqueue(ev) {
    if (!state.running) return;
    if (ev.type === 'engagement') {                    // coalescência: 1 amostra por página
      state.queue = state.queue.filter(function (q) {
        return !(q.type === 'engagement' && q.page_view_id === ev.page_view_id);
      });
    }
    state.queue.push(ev);
    if (state.queue.length > cfg.maxQueue) state.queue.splice(0, state.queue.length - cfg.maxQueue);
    touchSession();
    log('enfileirado', ev.type, ev);
  }

  /** Retira da fila o maior lote que respeita os limites de quantidade e bytes. */
  function takeBatch(csrfInBody) {
    var events = [];
    var body = null;
    while (state.queue.length && events.length < cfg.maxBatchEvents) {
      var candidate = events.concat(state.queue[0]);
      var json = JSON.stringify(payload(candidate, csrfInBody));
      if (json.length > cfg.maxBatchBytes && events.length) break;
      if (json.length > cfg.maxBatchBytes) { state.queue.shift(); continue; }   // evento sozinho grande demais
      events = candidate;
      body = json;
      state.queue.shift();
    }
    return events.length ? { events: events, body: body } : null;
  }

  function payload(events, csrfToken) {
    var p = { session_id: state.session.id, events: events };
    if (state.visitorId) p.visitor_id = state.visitorId;
    if (state.referrerHost) p.referrer_host = state.referrerHost;
    if (csrfToken) p.csrf_token = csrfToken;
    return p;
  }

  function csrfToken(force) {
    var t = readCsrfCookie();
    if (t && !force) return Promise.resolve(t);
    if (!state.csrfPromise) {
      state.csrfPromise = fetch(cfg.csrfEndpoint, { credentials: 'same-origin', cache: 'no-store' })
        .then(function () { return readCsrfCookie(); })
        .catch(function () { return null; })
        .then(function (tok) { state.csrfPromise = null; return tok; });
    }
    return state.csrfPromise;
  }

  function requeue(events) {
    state.queue = events.concat(state.queue).slice(-cfg.maxQueue);
  }

  function scheduleRetry() {
    state.retryAttempt = Math.min(state.retryAttempt + 1, 6);
    var delay = Math.min(60000, 1000 * Math.pow(2, state.retryAttempt)) * (0.75 + Math.random() * 0.5);
    clearTimeout(state.retryTimer);
    state.retryTimer = setTimeout(flush, delay);
    log('nova tentativa em', Math.round(delay), 'ms');
  }

  /** Envio normal (página aberta): fetch assíncrono no tempo ocioso do navegador. */
  function flush() {
    state.idleScheduled = false;
    if (!state.running || state.sending || !state.queue.length) return Promise.resolve();
    if (navigator.onLine === false) { scheduleRetry(); return Promise.resolve(); }

    state.sending = true;
    var force = state.forceCsrf;
    state.forceCsrf = false;
    return csrfToken(force).then(function (token) {
      var batch = takeBatch(null);
      if (!batch) return;
      return fetch(cfg.endpoint, {
        method: 'POST',
        credentials: 'same-origin',
        // keepalive: o lote sobrevive se o usuário navegar enquanto ele está em trânsito
        // (ex.: clicou em "Comprar agora" logo após outro evento)
        keepalive: batch.body.length < cfg.maxBatchBytes,
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token || '' },
        body: batch.body
      }).then(function (res) {
        if (res.ok) {
          state.retryAttempt = 0;
          log('lote aceito', batch.events.length);
          if (state.queue.length) scheduleFlush();
        } else if (res.status === 429 || res.status >= 500) {
          requeue(batch.events); scheduleRetry();
        } else if (res.status === 403 && state.retryAttempt === 0) {
          // Token expirou/rotacionou: pede um cookie novo ao servidor e tenta UMA vez
          state.forceCsrf = true;
          requeue(batch.events); state.retryAttempt = 1; scheduleFlush();
        } else {
          log('lote descartado (HTTP ' + res.status + ')');  // 4xx: payload inválido não melhora com retry
        }
      }, function () {
        requeue(batch.events); scheduleRetry();            // falha de rede
      });
    }).then(function () { state.sending = false; }, function () { state.sending = false; });
  }

  function scheduleFlush() {
    if (state.idleScheduled || !state.running) return;
    state.idleScheduled = true;
    scheduleIdle(flush);
  }

  /** Saída da página: não pode ser assíncrono "de verdade" — o navegador pode matar a aba. */
  function flushOnExit() {
    if (!state.running || !state.queue.length) return;
    if (navigator.onLine === false) {                    // offline: guarda para a próxima página
      writeJSON(KEY_PENDING, state.queue.slice(-cfg.maxQueue));
      state.queue = [];
      return;
    }
    var token = readCsrfCookie();
    var batch;
    while ((batch = takeBatch(null))) {
      var sent = false;
      if (token && window.fetch) {
        try {
          fetch(cfg.endpoint, {
            method: 'POST', credentials: 'same-origin', keepalive: true,
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token },
            body: batch.body
          }).catch(function () { /* sem como reenfileirar após o unload */ });
          sent = true;
        } catch (e) { sent = false; }                    // keepalive indisponível / cota excedida
      }
      if (!sent && navigator.sendBeacon && token) {
        // text/plain = requisição "simples": sem preflight; token CSRF vai no corpo
        var body = JSON.stringify(payload(batch.events, token));
        sent = navigator.sendBeacon(cfg.endpoint, new Blob([body], { type: 'text/plain;charset=UTF-8' }));
      }
      if (!sent) { requeue(batch.events); writeJSON(KEY_PENDING, state.queue); state.queue = []; return; }
    }
    removeKey(KEY_PENDING);
  }

  // ---------------------------------------------------------------------------
  // 9. Captura de interações (delegação: 1 listener para a página inteira)
  // ---------------------------------------------------------------------------
  function onClick(e) {
    if (!state.running) return;
    var el = e.target && e.target.closest ? e.target.closest('[data-track]') : null;
    if (!el) return;
    // Fase de CAPTURA: roda antes do gm-ui.js alternar o data-track do favorito
    var action = String(el.getAttribute('data-track')).toLowerCase().slice(0, 40);
    var type = ACTION_MAP[action] || 'click';
    var ev = baseEvent(type);
    var pid = parseInt(el.getAttribute('data-product-id'), 10);
    if (pid > 0) ev.product_id = pid;
    var props = propsFrom(el) || {};
    if (type === 'click') props.target = action.replace(/[^a-z0-9_\-]/g, '_');
    if (action === 'buy_now') props.source = 'buy_now';
    if (Object.keys(props).length) ev.props = props;
    enqueue(ev);
    if (type !== 'click') scheduleFlush();               // eventos de funil saem logo, no idle
  }

  function onSubmit(e) {
    if (!state.running) return;
    var form = e.target;
    if (!form || !form.matches || !form.matches('form[role="search"]')) return;
    var input = form.querySelector('input[type="search"], input[name="q"]');
    var q = input ? coerce(input.value).toString().slice(0, 80) : '';
    if (!q) return;
    var ev = baseEvent('search');
    ev.props = { q: q };
    enqueue(ev);
    flushOnExit();                                       // o submit navega: envia já com keepalive
  }

  function onVisibility() {
    if (!state.running) return;
    if (document.visibilityState === 'hidden') {
      pauseClock();
      sampleEngagement(true);
      flushOnExit();                                     // último momento confiável no mobile
    } else {
      var expired = !state.session || Date.now() - state.session.last > cfg.sessionTimeoutMs;
      if (expired) { state.session = null; startPageView(); } else { onInput(); }
    }
  }

  function onPageHide() {
    if (!state.running) return;
    pauseClock();
    sampleEngagement(true);
    flushOnExit();
  }

  function onPageShow(e) {
    if (e.persisted && state.running) startPageView(); // voltou do bfcache = nova visualização
  }

  // ---------------------------------------------------------------------------
  // 10. Ciclo de vida
  // ---------------------------------------------------------------------------
  var passive = { passive: true, capture: true };
  var INPUT_EVENTS = ['pointerdown', 'pointermove', 'keydown', 'touchstart', 'wheel'];

  function start() {
    if (state.running || !hasConsent()) return;
    state.running = true;

    var pending = readJSON(KEY_PENDING);                 // eventos que ficaram offline
    removeKey(KEY_PENDING);
    if (Array.isArray(pending)) state.queue = pending.slice(-cfg.maxQueue);

    INPUT_EVENTS.forEach(function (t) { document.addEventListener(t, onInput, passive); });
    window.addEventListener('scroll', onScroll, { passive: true });
    document.addEventListener('click', onClick, true);
    document.addEventListener('submit', onSubmit, true);
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('pagehide', onPageHide);
    window.addEventListener('pageshow', onPageShow);
    window.addEventListener('online', scheduleFlush);

    startPageView();
    state.heartbeatTimer = setInterval(sampleEngagement, cfg.heartbeatMs);
    state.flushTimer = setInterval(scheduleFlush, cfg.flushMs);
    state.idleTimer = setInterval(checkIdle, 5000);
    scheduleFlush();
    log('iniciado', cfg);
  }

  function stop() {
    if (!state.running) return;
    state.running = false;
    INPUT_EVENTS.forEach(function (t) { document.removeEventListener(t, onInput, passive); });
    window.removeEventListener('scroll', onScroll, { passive: true });
    document.removeEventListener('click', onClick, true);
    document.removeEventListener('submit', onSubmit, true);
    document.removeEventListener('visibilitychange', onVisibility);
    window.removeEventListener('pagehide', onPageHide);
    window.removeEventListener('pageshow', onPageShow);
    window.removeEventListener('online', scheduleFlush);
    [state.heartbeatTimer, state.flushTimer, state.idleTimer].forEach(clearInterval);
    clearTimeout(state.retryTimer);
    state.queue = [];
    state.session = null;
    state.visitorId = null;
    state.pageView = null;
    log('parado');
  }

  /** Evento customizado para outros scripts (ex.: gm-ui.js). Tipos: os mesmos aceitos pela API. */
  function track(type, props, productId) {
    if (!state.running || !state.pageView) return false;
    var allowed = ['click', 'search', 'favorite_add', 'favorite_remove', 'add_to_cart', 'begin_checkout'];
    if (allowed.indexOf(type) === -1) return false;
    var ev = baseEvent(type);
    if (productId > 0) ev.product_id = productId;
    if (props && typeof props === 'object') {
      var clean = {};
      Object.keys(props).slice(0, 8).forEach(function (k) { if (PROP_KEY_OK.test(k)) clean[k] = coerce(props[k]); });
      if (Object.keys(clean).length) ev.props = clean;
    }
    enqueue(ev);
    scheduleFlush();
    return true;
  }

  window.GMTracker = {
    version: '2.0.0',
    track: track,
    setConsent: setConsent,
    hasConsent: hasConsent,
    consentDecided: function () { return consentValue() !== null; },
    gpc: function () { return navigator.globalPrivacyControl === true; },
    flush: function () { return flush(); },
    history: history
  };

  // Script carregado com defer: o DOM já existe. Começa fora do caminho crítico.
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else scheduleIdle(start);
})(window, document);
