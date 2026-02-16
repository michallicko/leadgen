/**
 * Leadgen Dashboard - Auth Module
 * Handles JWT login/logout, token refresh, and role-based UI gating.
 */
(function () {
  'use strict';

  var API_BASE = 'https://leadgen.visionvolve.com/api';
  var TOKEN_KEY = 'lg_access_token';
  var REFRESH_KEY = 'lg_refresh_token';
  var USER_KEY = 'lg_user';

  // ---- DOM helpers ----

  function el(tag, attrs, children) {
    var e = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === 'textContent') e.textContent = attrs[k];
        else if (k === 'className') e.className = attrs[k];
        else e.setAttribute(k, attrs[k]);
      });
    }
    if (children) {
      children.forEach(function (c) { if (c) e.appendChild(c); });
    }
    return e;
  }

  function svgNS(tag, attrs) {
    var e = document.createElementNS('http://www.w3.org/2000/svg', tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    return e;
  }

  // ---- Token helpers ----

  function getAccessToken() { return localStorage.getItem(TOKEN_KEY); }
  function getRefreshToken() { return localStorage.getItem(REFRESH_KEY); }

  function storeTokens(access, refresh) {
    localStorage.setItem(TOKEN_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  }

  function clearTokens() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
  }

  function decodeJWT(token) {
    try {
      var parts = token.split('.');
      if (parts.length !== 3) return null;
      return JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
    } catch (e) { return null; }
  }

  function isTokenExpired(token) {
    var payload = decodeJWT(token);
    if (!payload || !payload.exp) return true;
    return payload.exp * 1000 < Date.now();
  }

  function getStoredUser() {
    try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch (e) { return null; }
  }

  // ---- Namespace routing ----

  function getNamespace() {
    var path = window.location.pathname;
    var match = path.match(/^\/([a-z0-9][a-z0-9_-]*)(?:\/|$)/i);
    if (!match) return null;
    var slug = match[1].toLowerCase();
    if (slug.indexOf('.') !== -1) return null;
    return slug;
  }

  function getDefaultNamespace(user) {
    if (!user || !user.roles) return null;
    var namespaces = Object.keys(user.roles);
    return namespaces.length > 0 ? namespaces[0] : null;
  }

  function isRootPage() {
    var path = window.location.pathname;
    return path === '/' || path === '/index.html';
  }

  function redirectToLogin() {
    var ns = getNamespace();
    if (ns) {
      var returnPath = window.location.pathname + window.location.search;
      window.location.href = '/?return=' + encodeURIComponent(returnPath);
      return true;
    }
    return false;
  }

  function redirectAuthenticated(user) {
    // Check for return URL first (e.g. /?return=/acme/messages)
    var params = new URLSearchParams(window.location.search);
    var returnUrl = params.get('return');
    if (returnUrl && returnUrl.charAt(0) === '/' && returnUrl !== '/' && returnUrl !== '/index.html') {
      window.location.href = returnUrl;
      return true;
    }

    // Only auto-redirect from root page
    if (!isRootPage()) return false;

    if (user.is_super_admin) {
      window.location.href = '/admin.html';
      return true;
    }

    var ns = getDefaultNamespace(user);
    if (ns) {
      window.location.href = '/' + ns + '/';
      return true;
    }

    return false;
  }

  // ---- Build brand logo SVG ----

  function buildLogo() {
    var img = document.createElement('img');
    img.src = 'visionvolve-logo-white.svg';
    img.alt = 'VisionVolve';
    img.style.height = '40px';
    img.style.width = 'auto';
    return img;
  }

  // ---- Build lock icon SVG ----

  function buildLockIcon() {
    var svg = svgNS('svg', { width: '14', height: '14', viewBox: '0 0 24 24', fill: 'none',
      stroke: 'currentColor', 'stroke-width': '2', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' });
    svg.appendChild(svgNS('rect', { x: '3', y: '11', width: '18', height: '11', rx: '2', ry: '2' }));
    svg.appendChild(svgNS('path', { d: 'M7 11V7a5 5 0 0 1 10 0v4' }));
    return svg;
  }

  // ---- Login overlay ----

  function createLoginOverlay() {
    var errorDiv = el('div', { id: 'auth_error', className: 'auth-error', style: 'display:none;' });

    var btnText = el('span', { textContent: 'Sign In', className: 'auth-btn__text' });
    var btnShimmer = el('span', { className: 'auth-btn__shimmer' });
    var submitBtn = el('button', { type: 'submit', className: 'auth-btn', id: 'auth_submit' }, [btnText, btnShimmer]);

    var emailInput = el('input', { type: 'email', id: 'auth_email', name: 'email',
      autocomplete: 'email', required: '', placeholder: 'you@company.com' });
    var passwordInput = el('input', { type: 'password', id: 'auth_password', name: 'password',
      autocomplete: 'current-password', required: '', placeholder: '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022' });

    var form = el('form', { id: 'auth_form', autocomplete: 'on' }, [
      el('div', { className: 'auth-field' }, [
        el('label', { for: 'auth_email', textContent: 'Email address' }),
        el('div', { className: 'auth-input-wrap' }, [emailInput])
      ]),
      el('div', { className: 'auth-field' }, [
        el('label', { for: 'auth_password', textContent: 'Password' }),
        el('div', { className: 'auth-input-wrap' }, [passwordInput])
      ]),
      errorDiv,
      submitBtn
    ]);

    // Secure badge
    var secureBadge = el('div', { className: 'auth-secure' }, [
      buildLockIcon(),
      el('span', { textContent: 'Encrypted connection' })
    ]);

    // Card
    var card = el('div', { className: 'auth-card' }, [
      el('div', { className: 'auth-card__glow' }),
      el('div', { className: 'auth-brand' }, [
        el('div', { className: 'auth-brand__icon' }, [buildLogo()]),
        el('div', { className: 'auth-brand__name', textContent: 'Leadgen' }),
        el('div', { className: 'auth-brand__tagline', textContent: 'Pipeline Command Center' })
      ]),
      el('div', { className: 'auth-divider' }),
      form,
      secureBadge
    ]);

    // Background layers
    var bgMesh = el('div', { className: 'auth-bg-mesh' });
    var bgGrid = el('div', { className: 'auth-bg-grid' });
    var bgVignette = el('div', { className: 'auth-bg-vignette' });

    var overlay = el('div', { id: 'auth_overlay' }, [bgMesh, bgGrid, bgVignette, card]);
    document.body.appendChild(overlay);

    // Focus effects
    [emailInput, passwordInput].forEach(function (inp) {
      inp.addEventListener('focus', function () { inp.parentNode.classList.add('focused'); });
      inp.addEventListener('blur', function () { inp.parentNode.classList.remove('focused'); });
    });

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      doLogin();
    });
  }

  function showOverlay() {
    var o = document.getElementById('auth_overlay');
    if (o) {
      o.classList.add('visible');
      // Reset entrance animation
      var card = o.querySelector('.auth-card');
      if (card) {
        card.classList.remove('auth-entered');
        requestAnimationFrame(function () {
          requestAnimationFrame(function () { card.classList.add('auth-entered'); });
        });
      }
    }
  }

  function hideOverlay() {
    var o = document.getElementById('auth_overlay');
    if (o) o.classList.remove('visible');
  }

  function showLoginError(msg) {
    var e = document.getElementById('auth_error');
    if (e) {
      e.textContent = msg;
      e.style.display = '';
      e.classList.remove('auth-shake');
      void e.offsetWidth; // reflow
      e.classList.add('auth-shake');
    }
  }

  // ---- API calls ----

  function doLogin() {
    var email = document.getElementById('auth_email').value.trim();
    var password = document.getElementById('auth_password').value;
    var btn = document.getElementById('auth_submit');
    var errEl = document.getElementById('auth_error');
    if (errEl) errEl.style.display = 'none';

    if (!email || !password) { showLoginError('Email and password required.'); return; }

    btn.disabled = true;
    btn.classList.add('auth-btn--loading');
    var btnText = btn.querySelector('.auth-btn__text');
    if (btnText) btnText.textContent = 'Authenticating...';

    fetch(API_BASE + '/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email, password: password })
    })
    .then(function (resp) {
      if (!resp.ok) return resp.json().then(function (d) { throw new Error(d.error || 'Login failed'); });
      return resp.json();
    })
    .then(function (data) {
      storeTokens(data.access_token, data.refresh_token);
      localStorage.setItem(USER_KEY, JSON.stringify(data.user));
      if (redirectAuthenticated(data.user)) return;
      hideOverlay();
      applyRoleGating(data.user);
      if (typeof window.__onAuthReady === 'function') window.__onAuthReady();
    })
    .catch(function (err) {
      showLoginError(err.message);
    })
    .finally(function () {
      btn.disabled = false;
      btn.classList.remove('auth-btn--loading');
      if (btnText) btnText.textContent = 'Sign In';
    });
  }

  function doRefresh() {
    var refreshToken = getRefreshToken();
    if (!refreshToken) return Promise.reject(new Error('No refresh token'));

    return fetch(API_BASE + '/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken })
    })
    .then(function (resp) {
      if (!resp.ok) throw new Error('Refresh failed');
      return resp.json();
    })
    .then(function (data) {
      storeTokens(data.access_token, null);
      return data.access_token;
    });
  }

  // ---- Role gating ----

  function getUserRole(user) {
    if (!user) return 'viewer';
    if (user.is_super_admin) return 'admin';
    var roles = user.roles || {};
    var vals = Object.values(roles);
    if (vals.indexOf('admin') !== -1) return 'admin';
    if (vals.indexOf('editor') !== -1) return 'editor';
    return 'viewer';
  }

  function applyRoleGating(user) {
    var role = getUserRole(user);
    document.body.setAttribute('data-role', role);

    var gated = document.querySelectorAll('[data-min-role]');
    var hierarchy = { admin: 3, editor: 2, viewer: 1 };
    var userLevel = hierarchy[role] || 0;

    for (var i = 0; i < gated.length; i++) {
      var required = hierarchy[gated[i].getAttribute('data-min-role')] || 0;
      gated[i].style.display = userLevel >= required ? '' : 'none';
    }

    // Populate the shared nav component (nav.js)
    if (window.LeadgenNav && window.LeadgenNav.applyAuth) {
      window.LeadgenNav.applyAuth(user);
    }
  }

  // ---- Logout ----

  function doLogout() {
    clearTokens();
    window.location.href = '/';
  }

  // ---- Inject styles ----

  function injectStyles() {
    // Load fonts
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://fonts.googleapis.com/css2?family=Lexend+Deca:wght@400;500;600;700&family=Work+Sans:wght@300;400;500;600;700&display=swap';
    document.head.appendChild(link);

    var style = document.createElement('style');
    style.textContent = [
      /* ---- Overlay ---- */
      '#auth_overlay{position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;transition:opacity .5s cubic-bezier(.4,0,.2,1);overflow:hidden;}',
      '#auth_overlay.visible{opacity:1;pointer-events:all;}',

      /* ---- Animated mesh background — VisionVolve purple/cyan ---- */
      '.auth-bg-mesh{position:absolute;inset:0;background:#0D0F14;}',
      '.auth-bg-mesh::before{content:"";position:absolute;inset:-50%;width:200%;height:200%;' +
        'background:radial-gradient(ellipse at 30% 20%,rgba(110,44,139,.18) 0%,transparent 50%),' +
        'radial-gradient(ellipse at 70% 80%,rgba(0,184,207,.12) 0%,transparent 50%),' +
        'radial-gradient(ellipse at 50% 50%,rgba(74,29,94,.1) 0%,transparent 60%);' +
        'animation:authMeshDrift 20s ease-in-out infinite alternate;}',

      /* ---- Grid overlay ---- */
      '.auth-bg-grid{position:absolute;inset:0;' +
        'background-image:linear-gradient(rgba(110,44,139,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(110,44,139,.04) 1px,transparent 1px);' +
        'background-size:48px 48px;mask-image:radial-gradient(ellipse at center,black 30%,transparent 70%);}',

      /* ---- Vignette ---- */
      '.auth-bg-vignette{position:absolute;inset:0;' +
        'background:radial-gradient(ellipse at center,transparent 40%,rgba(13,15,20,.8) 100%);}',

      /* ---- Card ---- */
      '.auth-card{position:relative;width:100%;max-width:400px;padding:44px 40px 36px;' +
        'background:rgba(20,23,30,.85);backdrop-filter:blur(24px) saturate(1.5);-webkit-backdrop-filter:blur(24px) saturate(1.5);' +
        'border:1px solid rgba(110,44,139,.2);border-radius:20px;' +
        'box-shadow:0 0 0 1px rgba(255,255,255,.03),0 24px 80px -12px rgba(0,0,0,.6),0 0 120px -40px rgba(110,44,139,.2);' +
        'transform:translateY(20px) scale(.98);opacity:0;transition:transform .7s cubic-bezier(.4,0,.2,1),opacity .7s cubic-bezier(.4,0,.2,1);}',
      '.auth-card.auth-entered{transform:translateY(0) scale(1);opacity:1;}',

      /* Card glow — purple/cyan conic */
      '.auth-card__glow{position:absolute;inset:-1px;border-radius:21px;' +
        'background:conic-gradient(from 180deg at 50% 50%,rgba(110,44,139,.25),transparent 25%,transparent 75%,rgba(0,184,207,.15));' +
        'animation:authGlowSpin 8s linear infinite;opacity:.6;z-index:-1;filter:blur(1px);}',

      /* ---- Brand ---- */
      '.auth-brand{text-align:center;margin-bottom:28px;}',
      '.auth-brand__icon{display:flex;justify-content:center;margin-bottom:16px;}',
      '.auth-brand__icon img{height:40px;width:auto;animation:authIconPulse 4s ease-in-out infinite;}',
      '.auth-brand__name{font-family:"Lexend Deca",-apple-system,sans-serif;font-size:1.5rem;font-weight:700;letter-spacing:-.02em;' +
        'color:#E8EAF0;line-height:1;}',
      '.auth-brand__tagline{font-family:"Work Sans",-apple-system,sans-serif;font-size:.75rem;font-weight:400;letter-spacing:.12em;text-transform:uppercase;' +
        'color:rgba(139,146,160,.7);margin-top:8px;}',

      /* ---- Divider — purple→cyan gradient ---- */
      '.auth-divider{height:1px;margin:0 0 28px;' +
        'background:linear-gradient(90deg,transparent,rgba(110,44,139,.3) 30%,rgba(0,184,207,.2) 70%,transparent);}',

      /* ---- Form ---- */
      '#auth_form{font-family:"Work Sans",-apple-system,sans-serif;}',
      '.auth-field{margin-bottom:20px;}',
      '.auth-field label{display:block;font-size:.75rem;font-weight:500;letter-spacing:.06em;text-transform:uppercase;' +
        'color:rgba(139,146,160,.8);margin-bottom:8px;}',

      /* Input wrapper with animated purple→cyan border */
      '.auth-input-wrap{position:relative;border-radius:10px;background:rgba(13,15,20,.6);' +
        'border:1px solid rgba(110,44,139,.2);transition:border-color .3s,box-shadow .3s;}',
      '.auth-input-wrap.focused{border-color:rgba(110,44,139,.5);' +
        'box-shadow:0 0 0 3px rgba(110,44,139,.08),0 0 20px -4px rgba(110,44,139,.15);}',
      '.auth-input-wrap::after{content:"";position:absolute;bottom:-1px;left:50%;width:0;height:2px;' +
        'background:linear-gradient(90deg,#6E2C8B,#00B8CF);border-radius:1px;' +
        'transition:width .35s cubic-bezier(.4,0,.2,1),left .35s cubic-bezier(.4,0,.2,1);}',
      '.auth-input-wrap.focused::after{width:100%;left:0;}',

      '.auth-field input{width:100%;padding:12px 14px;background:transparent;border:none;' +
        'color:#E8EAF0;font-family:"Work Sans",-apple-system,sans-serif;font-size:.9rem;outline:none;}',
      '.auth-field input::placeholder{color:rgba(139,146,160,.35);}',

      /* ---- Error ---- */
      '.auth-error{font-family:"Work Sans",-apple-system,sans-serif;color:#F87171;font-size:.82rem;margin-bottom:14px;text-align:center;' +
        'padding:10px 14px;background:rgba(248,113,113,.06);border:1px solid rgba(248,113,113,.15);border-radius:8px;}',
      '.auth-shake{animation:authShake .4s ease;}',

      /* ---- Button — VisionVolve purple gradient ---- */
      '.auth-btn{position:relative;width:100%;padding:13px;border:none;border-radius:10px;cursor:pointer;overflow:hidden;' +
        'background:linear-gradient(135deg,#6E2C8B,#4A1D5E);' +
        'box-shadow:0 2px 12px -2px rgba(110,44,139,.4),inset 0 1px 0 rgba(255,255,255,.08);' +
        'transition:transform .15s,box-shadow .2s;}',
      '.auth-btn:hover{transform:translateY(-1px);box-shadow:0 4px 20px -2px rgba(110,44,139,.5),0 0 30px -4px rgba(0,184,207,.15),inset 0 1px 0 rgba(255,255,255,.1);}',
      '.auth-btn:active{transform:translateY(0);}',
      '.auth-btn:disabled{opacity:.6;cursor:not-allowed;transform:none;}',
      '.auth-btn__text{position:relative;z-index:1;font-family:"Work Sans",-apple-system,sans-serif;font-size:.9rem;font-weight:600;color:#fff;letter-spacing:.02em;}',

      /* Shimmer sweep */
      '.auth-btn__shimmer{position:absolute;inset:0;background:linear-gradient(105deg,transparent 40%,rgba(255,255,255,.1) 50%,transparent 60%);' +
        'transform:translateX(-100%);transition:none;}',
      '.auth-btn:hover .auth-btn__shimmer{transform:translateX(100%);transition:transform .6s ease;}',

      /* Loading state */
      '.auth-btn--loading{pointer-events:none;}',
      '.auth-btn--loading .auth-btn__text::after{content:"";display:inline-block;width:14px;height:14px;margin-left:8px;' +
        'border:2px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:authSpin .6s linear infinite;vertical-align:middle;}',

      /* ---- Secure badge ---- */
      '.auth-secure{display:flex;align-items:center;justify-content:center;gap:6px;margin-top:24px;' +
        'font-family:"Work Sans",-apple-system,sans-serif;font-size:.72rem;letter-spacing:.04em;color:rgba(139,146,160,.45);}',
      '.auth-secure svg{opacity:.5;}',

      /* ---- Animations ---- */
      '@keyframes authMeshDrift{0%{transform:translate(-5%,-5%) rotate(0deg);}100%{transform:translate(5%,5%) rotate(8deg);}}',
      '@keyframes authGlowSpin{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}',
      '@keyframes authIconPulse{0%,100%{opacity:1;transform:scale(1);}50%{opacity:.85;transform:scale(.97);}}',
      '@keyframes authShake{0%,100%{transform:translateX(0);}20%{transform:translateX(-8px);}40%{transform:translateX(6px);}60%{transform:translateX(-4px);}80%{transform:translateX(2px);}}',
      '@keyframes authSpin{to{transform:rotate(360deg);}}'
    ].join('\n');
    document.head.appendChild(style);
  }

  // ---- Init ----

  function initAuth(onReady) {
    window.__onAuthReady = onReady || null;

    injectStyles();
    createLoginOverlay();

    var token = getAccessToken();

    if (!token || isTokenExpired(token)) {
      var refreshToken = getRefreshToken();
      if (refreshToken && !isTokenExpired(refreshToken)) {
        doRefresh()
          .then(function () {
            var user = getStoredUser();
            if (redirectAuthenticated(user)) return;
            hideOverlay();
            applyRoleGating(user);
            if (onReady) onReady();
          })
          .catch(function () {
            if (!redirectToLogin()) showOverlay();
          });
      } else {
        if (!redirectToLogin()) showOverlay();
      }
    } else {
      var user = getStoredUser();
      if (redirectAuthenticated(user)) return;
      hideOverlay();
      applyRoleGating(user);
      if (onReady) onReady();
    }

    // Periodic token check (every 5 min)
    setInterval(function () {
      var t = getAccessToken();
      if (!t || isTokenExpired(t)) {
        doRefresh().catch(function () {
          if (!redirectToLogin()) showOverlay();
        });
      }
    }, 5 * 60 * 1000);
  }

  // ---- Public API ----
  window.LeadgenAuth = {
    init: initAuth,
    logout: doLogout,
    getToken: getAccessToken,
    getUser: getStoredUser,
    getUserRole: function () { return getUserRole(getStoredUser()); },
    applyRoleGating: function () { applyRoleGating(getStoredUser()); },
    getNamespace: getNamespace
  };
})();
