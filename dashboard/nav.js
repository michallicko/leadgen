/**
 * Leadgen Navigation — Two-Tier Pillar System
 * ES5 IIFE — renders nav from config, integrates with auth.js
 */
(function () {
  'use strict';

  // ---- SVG Icon paths (stroke-based, 18x18 viewBox assumed via 0 0 24 24) ----
  var ICONS = {
    playbook: '<svg viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/><path d="M8 7h8M8 11h6"/></svg>',
    radar: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/><path d="M12 2v4M12 18v4"/></svg>',
    reach: '<svg viewBox="0 0 24 24"><path d="M22 2L11 13"/><path d="M22 2L15 22l-4-9-9-4z"/></svg>',
    echo: '<svg viewBox="0 0 24 24"><path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/></svg>',
    gear: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>'
  };

  // ---- Pillar config ----
  var PILLARS = [
    {
      id: 'playbook',
      label: 'Playbook',
      subtitle: 'Strategy',
      icon: 'playbook',
      defaultPage: 'playbook',
      pages: [
        { id: 'playbook', label: 'ICP Summary', href: 'playbook.html', minRole: 'viewer' }
      ]
    },
    {
      id: 'radar',
      label: 'Radar',
      subtitle: 'Intelligence',
      icon: 'radar',
      defaultPage: 'contacts',
      pages: [
        { id: 'contacts', label: 'Contacts', href: 'contacts.html', minRole: 'viewer' },
        { id: 'companies', label: 'Companies', href: 'companies.html', minRole: 'viewer' },
        { id: 'import', label: 'Import', href: 'import.html', minRole: 'editor' },
        { id: 'enrich', label: 'Enrich', href: 'enrich.html', minRole: 'editor' }
      ]
    },
    {
      id: 'reach',
      label: 'Reach',
      subtitle: 'Outreach',
      icon: 'reach',
      defaultPage: 'messages',
      pages: [
        { id: 'messages', label: 'Messages', href: 'messages.html', minRole: 'viewer' }
      ]
    },
    {
      id: 'echo',
      label: 'Echo',
      subtitle: 'Evaluate',
      icon: 'echo',
      defaultPage: 'echo',
      pages: [
        { id: 'echo', label: 'Dashboard Demo', href: 'echo.html', minRole: 'viewer' }
      ]
    }
  ];

  // ---- Gear menu config ----
  var GEAR_SECTIONS = [
    {
      header: 'Workspace',
      items: [
        { id: 'admin', label: 'Users & Roles', href: 'admin.html', minRole: 'admin', rootLevel: true }
      ]
    },
    {
      header: 'System',
      superOnly: true,
      items: [
        { id: 'llm-costs', label: 'LLM Costs', href: 'llm-costs.html', minRole: 'admin', rootLevel: true }
      ]
    }
  ];

  var ROLE_HIERARCHY = { admin: 3, editor: 2, viewer: 1 };

  // ---- Helpers ----

  function mk(tag, attrs, children) {
    var e = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === 'className') e.className = attrs[k];
        else if (k.indexOf('on') === 0) e.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
        else e.setAttribute(k, attrs[k]);
      });
    }
    if (children) {
      (Array.isArray(children) ? children : [children]).forEach(function (c) {
        if (!c) return;
        if (typeof c === 'string') e.appendChild(document.createTextNode(c));
        else e.appendChild(c);
      });
    }
    return e;
  }

  function setIconHTML(el, iconKey) {
    // Safe: only uses hardcoded SVG strings from ICONS constant
    var svg = ICONS[iconKey];
    if (svg) el.innerHTML = svg; // eslint-disable-line -- static SVG constant
  }

  function getNamespace() {
    if (window.LeadgenAuth && window.LeadgenAuth.getNamespace) {
      return window.LeadgenAuth.getNamespace();
    }
    var path = window.location.pathname;
    var match = path.match(/^\/([a-z0-9][a-z0-9_-]*)(?:\/|$)/i);
    if (!match) return null;
    var slug = match[1].toLowerCase();
    return slug.indexOf('.') !== -1 ? null : slug;
  }

  function makeHref(href, rootLevel) {
    if (rootLevel) return '/' + href;
    var ns = getNamespace();
    if (!ns) return href;
    var page = href.replace('.html', '');
    return '/' + ns + '/' + page;
  }

  // ---- Render ----

  function render() {
    var target = document.getElementById('app-nav');
    if (!target) return;

    var pillarId = document.body.getAttribute('data-pillar') || '';
    var pageId = document.body.getAttribute('data-page') || '';

    // Build Tier 1
    var tier1 = mk('div', { className: 'nav-tier1' });

    // Brand
    var brand = mk('a', { className: 'nav-brand', href: '/' }, [
      mk('img', { className: 'nav-brand__logo', src: 'visionvolve-icon-color.svg', alt: 'VisionVolve' }),
      mk('span', { className: 'nav-brand__title' }, 'Leadgen')
    ]);
    tier1.appendChild(brand);

    // Pillars
    var pillarsWrap = mk('div', { className: 'nav-pillars' });
    PILLARS.forEach(function (p) {
      var isActive = p.id === pillarId;
      var defaultHref = makeHref(p.pages[0].href, false);

      var pillarEl = mk('a', {
        className: 'nav-pillar' + (isActive ? ' active' : ''),
        href: defaultHref,
        'data-pillar-id': p.id
      });

      var iconWrap = mk('span', { className: 'nav-pillar__icon' });
      setIconHTML(iconWrap, p.icon);
      pillarEl.appendChild(iconWrap);

      pillarEl.appendChild(mk('span', { className: 'nav-pillar__label' }, p.label));

      pillarsWrap.appendChild(pillarEl);
    });
    tier1.appendChild(pillarsWrap);

    // Right section
    var right = mk('div', { className: 'nav-right' });

    // Namespace switcher placeholder
    right.appendChild(mk('span', { id: 'nav_ns_slot' }));

    // User info
    var userWrap = mk('span', { className: 'nav-user' });
    userWrap.appendChild(mk('span', { id: 'nav_user_name', className: 'nav-user__name' }));
    userWrap.appendChild(mk('span', { id: 'nav_super_badge' }));
    right.appendChild(userWrap);

    // Gear button
    var gearWrap = mk('div', { className: 'nav-gear-wrap', id: 'nav_gear_wrap' });
    var gearBtn = mk('button', { className: 'nav-gear', id: 'nav_gear_btn', 'aria-label': 'Settings' });
    var gearIconSpan = mk('span', { className: 'nav-gear__icon-inner' });
    setIconHTML(gearIconSpan, 'gear');
    gearBtn.appendChild(gearIconSpan);
    gearBtn.appendChild(mk('span', { className: 'nav-gear__dot' }));
    gearWrap.appendChild(gearBtn);

    // Gear dropdown
    var gearMenu = mk('div', { className: 'nav-gear-menu', id: 'nav_gear_menu' });
    GEAR_SECTIONS.forEach(function (section) {
      var sec = mk('div', {
        className: 'nav-gear-menu__section',
        'data-super-only': section.superOnly ? 'true' : ''
      });
      sec.appendChild(mk('div', { className: 'nav-gear-menu__header' }, section.header));
      section.items.forEach(function (item) {
        var a = mk('a', {
          className: 'nav-gear-menu__item',
          href: makeHref(item.href, item.rootLevel),
          'data-min-role': item.minRole || 'viewer'
        }, item.label);
        sec.appendChild(a);
      });
      gearMenu.appendChild(sec);
    });
    gearWrap.appendChild(gearMenu);
    right.appendChild(gearWrap);

    // Logout
    right.appendChild(mk('button', {
      className: 'nav-logout',
      onClick: function () {
        if (window.LeadgenAuth) LeadgenAuth.logout();
      }
    }, 'Logout'));

    tier1.appendChild(right);

    // Build Tier 2 (sub-nav)
    var tier2 = mk('div', { className: 'nav-tier2', id: 'nav_tier2' });
    var subLinks = mk('div', { className: 'nav-sub-links' });

    // Find active pillar's pages
    var activePillar = null;
    PILLARS.forEach(function (p) {
      if (p.id === pillarId) activePillar = p;
    });

    if (activePillar && activePillar.pages.length > 1) {
      activePillar.pages.forEach(function (pg) {
        var isPageActive = pg.id === pageId;
        var a = mk('a', {
          className: 'nav-sub-link' + (isPageActive ? ' active' : ''),
          href: makeHref(pg.href, false),
          'data-min-role': pg.minRole || 'viewer'
        }, pg.label);
        subLinks.appendChild(a);
      });
      tier2.appendChild(subLinks);
      tier2.classList.add('visible');
    }

    // Assemble
    var wrapper = mk('div', { className: 'app-nav' });
    wrapper.appendChild(tier1);
    wrapper.appendChild(tier2);
    target.appendChild(wrapper);

    // Gear toggle
    gearBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      gearMenu.classList.toggle('open');
    });
    document.addEventListener('click', function (e) {
      if (!gearWrap.contains(e.target)) {
        gearMenu.classList.remove('open');
      }
    });
  }

  // ---- Auth integration (called by auth.js after login) ----

  function applyAuth(user) {
    if (!user) return;

    var role = 'viewer';
    if (user.is_super_admin) {
      role = 'admin';
    } else {
      var roles = user.roles || {};
      var vals = Object.keys(roles).map(function (k) { return roles[k]; });
      if (vals.indexOf('admin') !== -1) role = 'admin';
      else if (vals.indexOf('editor') !== -1) role = 'editor';
    }
    var userLevel = ROLE_HIERARCHY[role] || 0;

    // Role gating on nav elements
    var gated = document.querySelectorAll('.app-nav [data-min-role]');
    for (var i = 0; i < gated.length; i++) {
      var required = ROLE_HIERARCHY[gated[i].getAttribute('data-min-role')] || 0;
      gated[i].style.display = userLevel >= required ? '' : 'none';
    }

    // Super-only gear sections
    var superSections = document.querySelectorAll('.nav-gear-menu__section[data-super-only="true"]');
    for (var j = 0; j < superSections.length; j++) {
      superSections[j].style.display = user.is_super_admin ? '' : 'none';
    }

    // Hide gear entirely for non-admins
    var gearWrap = document.getElementById('nav_gear_wrap');
    if (gearWrap) {
      gearWrap.style.display = userLevel >= ROLE_HIERARCHY.admin ? '' : 'none';
    }

    // Super badge
    var badgeEl = document.getElementById('nav_super_badge');
    if (badgeEl && user.is_super_admin) {
      while (badgeEl.firstChild) badgeEl.removeChild(badgeEl.firstChild);
      badgeEl.appendChild(mk('span', { className: 'nav-super-badge' }, 'Super'));
    }

    // Super dot on gear
    var gearBtn = document.getElementById('nav_gear_btn');
    if (gearBtn && user.is_super_admin) {
      gearBtn.classList.add('nav-gear--super');
    }

    // User name
    var nameEl = document.getElementById('nav_user_name');
    if (nameEl) nameEl.textContent = user.display_name || user.email || '';

    // Namespace switcher
    buildNavSwitcher(user);

    // Rewrite pillar hrefs with namespace
    rewriteNavHrefs();
  }

  function rewriteNavHrefs() {
    var ns = getNamespace();
    if (!ns) return;

    // Rewrite pillar links
    var pillars = document.querySelectorAll('.nav-pillar');
    for (var i = 0; i < pillars.length; i++) {
      var href = pillars[i].getAttribute('href');
      if (href && href.indexOf('/') !== 0) {
        var page = href.replace('.html', '');
        pillars[i].setAttribute('href', '/' + ns + '/' + page);
      }
    }

    // Rewrite sub-links
    var subs = document.querySelectorAll('.nav-sub-link');
    for (var j = 0; j < subs.length; j++) {
      var subHref = subs[j].getAttribute('href');
      if (subHref && subHref.indexOf('/') !== 0) {
        var subPage = subHref.replace('.html', '');
        subs[j].setAttribute('href', '/' + ns + '/' + subPage);
      }
    }
  }

  function buildNavSwitcher(user) {
    if (!user) return;

    var slot = document.getElementById('nav_ns_slot');
    if (!slot) return;

    // Clear existing
    while (slot.firstChild) slot.removeChild(slot.firstChild);

    var roles = user.roles || {};
    var namespaces = Object.keys(roles);
    var showSwitcher = user.is_super_admin || namespaces.length > 1;
    if (!showSwitcher) return;

    var currentNs = getNamespace();

    var select = mk('select', { id: 'nav_ns_switcher', className: 'nav-ns-switcher' });

    function populateSelect(slugs) {
      while (select.firstChild) select.removeChild(select.firstChild);
      slugs.forEach(function (slug) {
        var opt = mk('option', { value: slug }, slug);
        if (slug === currentNs) opt.selected = true;
        select.appendChild(opt);
      });
    }

    select.addEventListener('change', function () {
      var newNs = select.value;
      if (!newNs || newNs === currentNs) return;
      var path = window.location.pathname;
      var subPage = '';
      if (currentNs) {
        var prefix = '/' + currentNs;
        if (path.indexOf(prefix) === 0) {
          subPage = path.substring(prefix.length);
        }
      }
      if (!subPage || subPage === '/index.html') subPage = '/contacts';
      window.location.href = '/' + newNs + subPage;
    });

    slot.appendChild(select);

    // Super admin: fetch all tenants
    if (user.is_super_admin) {
      var API_BASE = 'https://leadgen.visionvolve.com/api';
      var token = window.LeadgenAuth ? LeadgenAuth.getToken() : '';
      if (token) {
        fetch(API_BASE + '/tenants', {
          headers: { 'Authorization': 'Bearer ' + token }
        })
        .then(function (r) { return r.ok ? r.json() : []; })
        .then(function (tenants) {
          var slugs = tenants
            .filter(function (t) { return t.is_active; })
            .map(function (t) { return t.slug; });
          if (slugs.length > 0) populateSelect(slugs);
        })
        .catch(function () { /* keep user's namespaces */ });
      }
    }

    populateSelect(namespaces);
  }

  // ---- Init ----

  function init() {
    render();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // ---- Public API ----
  window.LeadgenNav = {
    applyAuth: applyAuth,
    rewriteHrefs: rewriteNavHrefs
  };
})();
