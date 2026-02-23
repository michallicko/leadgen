// ─── Backlog App — Dynamic Data Loading ──────────────────────────
// Loads item JSON files from items/ directory based on config.json manifest

var BACKLOG_DATA = [];
var TEST_SCRIPTS = {};
var DOCS_LINKS = [];
var SPRINT_DEFS = [];

var items = [];
var currentFilters = { priority: 'all', status: 'all', effort: 'all', sprint: 'all' };
var currentSort = { key: null, dir: 'asc' };
var currentView = 'table';

// ─── Sprint Config ───────────────────────────────────────────────
var SPRINT_ORDER = ['Sprint 1', 'Sprint 2', 'Sprint 3', 'Backlog'];
var SPRINT_LABELS = { 'Sprint 1': 'S1', 'Sprint 2': 'S2', 'Sprint 3': 'S3', 'Backlog': 'BL' };
var SPRINT_CLASS = { 'Sprint 1': 'sprint-1', 'Sprint 2': 'sprint-2', 'Sprint 3': 'sprint-3', 'Backlog': 'sprint-backlog' };
var SPRINT_FILL_CLASS = { 'Sprint 1': 'sprint-1-fill', 'Sprint 2': 'sprint-2-fill', 'Sprint 3': 'sprint-3-fill', 'Backlog': 'sprint-backlog-fill' };
var SPRINT_SORT_ORDER = { 'Sprint 1': 0, 'Sprint 2': 1, 'Sprint 3': 2, 'Backlog': 3 };
var DONE_STATUSES = ['Done', 'Merged', 'PR Open'];

// ─── Status Config ───────────────────────────────────────────────
var STATUS_ORDER = ['Idea', "Spec'd", 'Building', 'PR Open', 'In Review', 'Merged', 'Done'];
var STATUS_CLASS = {
  'Idea': 'status-idea',
  "Spec'd": 'status-specd',
  'Building': 'status-building',
  'PR Open': 'status-pr-open',
  'In Review': 'status-in-review',
  'Merged': 'status-merged',
  'Done': 'status-done'
};

var PRIORITY_ORDER = { 'Must Have': 0, 'Should Have': 1, 'Could Have': 2 };
var PRIORITY_CLASS = {
  'Must Have': 'priority-must',
  'Should Have': 'priority-should',
  'Could Have': 'priority-could'
};

var EFFORT_ORDER = { 'S': 0, 'M': 1, 'L': 2, 'XL': 3 };
var EFFORT_CLASS = { 'S': 'effort-s', 'M': 'effort-m', 'L': 'effort-l', 'XL': 'effort-xl' };

// ─── Safe DOM Helpers ────────────────────────────────────────────
function escapeHtml(str) {
  var div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

function clearChildren(el) {
  while (el.firstChild) el.removeChild(el.firstChild);
}

function createEl(tag, attrs, children) {
  var el = document.createElement(tag);
  if (attrs) {
    Object.keys(attrs).forEach(function(k) {
      if (k === 'className') el.className = attrs[k];
      else if (k === 'textContent') el.textContent = attrs[k];
      else if (k === 'style') el.setAttribute('style', attrs[k]);
      else if (k.indexOf('on') === 0) el.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
      else el.setAttribute(k, attrs[k]);
    });
  }
  if (children) {
    children.forEach(function(child) {
      if (typeof child === 'string') el.appendChild(document.createTextNode(child));
      else if (child) el.appendChild(child);
    });
  }
  return el;
}

// ─── Markdown Parser (safe DOM) ──────────────────────────────────
function parseMarkdown(md) {
  var container = document.createElement('div');
  container.className = 'spec-content';
  if (!md) return container;

  var lines = md.split('\n');
  var i = 0;
  var currentList = null;
  var currentListType = null;

  function flushList() {
    if (currentList) {
      container.appendChild(currentList);
      currentList = null;
      currentListType = null;
    }
  }

  function applyInline(text) {
    var frag = document.createDocumentFragment();
    var regex = /(\*\*(.+?)\*\*|`([^`]+)`|\*(.+?)\*)/g;
    var lastIndex = 0;
    var match;
    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        frag.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
      }
      if (match[2]) {
        var strong = document.createElement('strong');
        strong.textContent = match[2];
        frag.appendChild(strong);
      } else if (match[3]) {
        var code = document.createElement('code');
        code.textContent = match[3];
        frag.appendChild(code);
      } else if (match[4]) {
        var em = document.createElement('em');
        em.textContent = match[4];
        frag.appendChild(em);
      }
      lastIndex = regex.lastIndex;
    }
    if (lastIndex < text.length) {
      frag.appendChild(document.createTextNode(text.slice(lastIndex)));
    }
    return frag;
  }

  while (i < lines.length) {
    var line = lines[i];

    // Table (markdown pipe tables)
    if (line.trim().indexOf('|') === 0 && line.trim().lastIndexOf('|') > 0) {
      flushList();
      var tableLines = [];
      while (i < lines.length && lines[i].trim().indexOf('|') === 0) {
        tableLines.push(lines[i]);
        i++;
      }
      if (tableLines.length >= 2) {
        var table = document.createElement('table');
        var hasSeparator = tableLines.length >= 2 && /^\s*\|[\s\-:|]+\|\s*$/.test(tableLines[1]);
        var startRow = hasSeparator ? 2 : 1;

        var thead = document.createElement('thead');
        var headerRow = document.createElement('tr');
        var headerCells = tableLines[0].split('|').filter(function(c, idx, arr) { return idx > 0 && idx < arr.length - 1; });
        headerCells.forEach(function(cell) {
          var th = document.createElement('th');
          th.appendChild(applyInline(cell.trim()));
          headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        var tbody = document.createElement('tbody');
        for (var ti = startRow; ti < tableLines.length; ti++) {
          var tr = document.createElement('tr');
          var cells = tableLines[ti].split('|').filter(function(c, idx, arr) { return idx > 0 && idx < arr.length - 1; });
          cells.forEach(function(cell) {
            var td = document.createElement('td');
            var cellText = cell.trim();
            if (cellText === '[ ]' || cellText === '[x]' || cellText === '[X]') {
              var cb = document.createElement('input');
              cb.type = 'checkbox';
              cb.checked = cellText !== '[ ]';
              td.appendChild(cb);
            } else {
              td.appendChild(applyInline(cellText));
            }
            tr.appendChild(td);
          });
          tbody.appendChild(tr);
        }
        table.appendChild(tbody);
        container.appendChild(table);
      }
      continue;
    }

    // Horizontal rule
    if (/^\s*---+\s*$/.test(line)) {
      flushList();
      container.appendChild(document.createElement('hr'));
      i++;
      continue;
    }

    // Code block
    if (line.trim().indexOf('```') === 0) {
      flushList();
      var codeLines = [];
      i++;
      while (i < lines.length && lines[i].trim().indexOf('```') !== 0) {
        codeLines.push(lines[i]);
        i++;
      }
      i++;
      var pre = document.createElement('pre');
      var codeEl = document.createElement('code');
      codeEl.textContent = codeLines.join('\n');
      pre.appendChild(codeEl);
      container.appendChild(pre);
      continue;
    }

    // Headings
    var headingMatch = line.match(/^(#{1,3})\s+(.+)/);
    if (headingMatch) {
      flushList();
      var level = headingMatch[1].length;
      var heading = document.createElement('h' + level);
      heading.appendChild(applyInline(headingMatch[2]));
      container.appendChild(heading);
      i++;
      continue;
    }

    // Blockquote
    if (line.trim().indexOf('> ') === 0) {
      flushList();
      var bq = document.createElement('blockquote');
      var bqP = document.createElement('p');
      bqP.appendChild(applyInline(line.trim().slice(2)));
      bq.appendChild(bqP);
      container.appendChild(bq);
      i++;
      continue;
    }

    // Unordered list
    if (line.match(/^\s*[-*]\s+/)) {
      if (currentListType !== 'ul') {
        flushList();
        currentList = document.createElement('ul');
        currentListType = 'ul';
      }
      var li = document.createElement('li');
      li.appendChild(applyInline(line.replace(/^\s*[-*]\s+/, '')));
      currentList.appendChild(li);
      i++;
      continue;
    }

    // Ordered list
    if (line.match(/^\s*\d+\.\s+/)) {
      if (currentListType !== 'ol') {
        flushList();
        currentList = document.createElement('ol');
        currentListType = 'ol';
      }
      var li2 = document.createElement('li');
      li2.appendChild(applyInline(line.replace(/^\s*\d+\.\s+/, '')));
      currentList.appendChild(li2);
      i++;
      continue;
    }

    // Empty line
    if (line.trim() === '') {
      flushList();
      i++;
      continue;
    }

    // Paragraph
    flushList();
    var p = document.createElement('p');
    p.appendChild(applyInline(line));
    container.appendChild(p);
    i++;
  }
  flushList();
  return container;
}

// ─── Spec Modal ──────────────────────────────────────────────────
var currentSpecItem = null;

function openSpecModal(item) {
  currentSpecItem = item;
  var overlay = document.getElementById('specOverlay');
  var idEl = document.getElementById('specId');
  var titleEl = document.getElementById('specTitle');
  var badgesEl = document.getElementById('specBadges');
  var depsEl = document.getElementById('specDeps');
  var contentEl = document.getElementById('specContent');
  var copyBtn = document.getElementById('specCopy');

  idEl.textContent = item.id;
  titleEl.textContent = item.name;

  // Badges
  clearChildren(badgesEl);
  badgesEl.appendChild(createEl('span', {
    className: 'badge ' + (PRIORITY_CLASS[item.priority] || ''),
    textContent: item.priority
  }));
  badgesEl.appendChild(createEl('span', {
    className: 'effort ' + (EFFORT_CLASS[item.effort] || ''),
    textContent: item.effort
  }));
  badgesEl.appendChild(createEl('span', {
    className: 'badge ' + (STATUS_CLASS[item.status] || ''),
    textContent: item.status
  }));
  badgesEl.appendChild(createEl('span', {
    className: 'sprint-badge ' + (SPRINT_CLASS[item.sprint] || 'sprint-backlog'),
    textContent: item.sprint || 'Backlog'
  }));

  // Deps
  clearChildren(depsEl);
  if (item.deps.length > 0) {
    depsEl.appendChild(createEl('span', { className: 'spec-panel-deps-label', textContent: 'Depends on:' }));
    item.deps.forEach(function(d) {
      depsEl.appendChild(createEl('span', { className: 'dep-tag', textContent: d }));
    });
  }

  // Spec content
  clearChildren(contentEl);
  if (item.spec) {
    contentEl.appendChild(parseMarkdown(item.spec));
  } else if (item.description) {
    contentEl.appendChild(parseMarkdown(item.description));
  } else {
    contentEl.appendChild(createEl('div', {
      className: 'empty-state',
      style: 'padding:32px',
      textContent: 'No specification written yet.'
    }));
  }

  // Reset copy button
  copyBtn.classList.remove('copied');
  var svgNode = copyBtn.querySelector('svg');
  while (copyBtn.lastChild !== svgNode) copyBtn.removeChild(copyBtn.lastChild);
  copyBtn.appendChild(document.createTextNode(' Copy Spec'));

  overlay.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeSpecModal() {
  document.getElementById('specOverlay').classList.remove('open');
  document.body.style.overflow = '';
  currentSpecItem = null;
}

// ─── Test Script Modal ───────────────────────────────────────────
var currentTestSprint = null;

function openTestModal(sprint) {
  currentTestSprint = sprint;
  var md = TEST_SCRIPTS[sprint];
  if (!md) return;

  document.getElementById('testTitle').textContent = sprint + ' \u2014 Manual Tests';
  document.getElementById('testSubtitle').textContent = 'Check off tests as you complete them (state does not persist)';

  var contentEl = document.getElementById('testContent');
  clearChildren(contentEl);
  contentEl.appendChild(parseMarkdown(md));

  // Reset copy button
  var copyBtn = document.getElementById('testCopy');
  copyBtn.classList.remove('copied');
  var svgNode = copyBtn.querySelector('svg');
  while (copyBtn.lastChild !== svgNode) copyBtn.removeChild(copyBtn.lastChild);
  copyBtn.appendChild(document.createTextNode(' Copy Markdown'));

  document.getElementById('testOverlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeTestModal() {
  document.getElementById('testOverlay').classList.remove('open');
  document.body.style.overflow = '';
  currentTestSprint = null;
}

// ─── Render Docs Bar ─────────────────────────────────────────────
function renderDocsBar() {
  var container = document.getElementById('docsBar');
  DOCS_LINKS.forEach(function(link) {
    var a = createEl('a', {
      className: 'doc-link',
      href: '../' + link.href,
      target: '_blank'
    }, [
      createEl('span', { className: 'doc-icon', textContent: link.icon }),
      document.createTextNode(link.label)
    ]);
    container.appendChild(a);
  });
}

// ─── Render Sprint Summary ───────────────────────────────────────
function renderSprintSummary() {
  var container = document.getElementById('sprintSummary');
  clearChildren(container);

  SPRINT_ORDER.forEach(function(sprint) {
    var sprintItems = BACKLOG_DATA.filter(function(d) { return d.sprint === sprint; });
    var total = sprintItems.length;
    var done = sprintItems.filter(function(d) { return DONE_STATUSES.indexOf(d.status) !== -1; }).length;
    var pct = total > 0 ? Math.round((done / total) * 100) : 0;

    var sprintDef = SPRINT_DEFS.filter(function(s) { return s.name === sprint; })[0];
    var sortLabel = sprintDef ? sprintDef.sort_label : (sprint === 'Backlog' ? 'UNSCHEDULED' : sprint.toUpperCase());

    var isActive = currentFilters.sprint === sprint;
    var card = createEl('div', {
      className: 'sprint-card' + (isActive ? ' active' : ''),
      onClick: function() {
        currentFilters.sprint = currentFilters.sprint === sprint ? 'all' : sprint;
        document.querySelectorAll('#sprintFilter .filter-btn').forEach(function(b) {
          b.classList.remove('active');
          if (b.dataset.sprint === currentFilters.sprint) b.classList.add('active');
        });
        applyFilters();
      }
    });

    var header = createEl('div', { className: 'sprint-card-header' });
    var nameEl = createEl('div', {}, [
      createEl('div', { className: 'sprint-card-label', textContent: sortLabel }),
      createEl('div', { className: 'sprint-card-name' }, [
        createEl('span', { className: 'sprint-badge ' + (SPRINT_CLASS[sprint] || ''), style: 'margin-right:6px', textContent: sprint })
      ])
    ]);
    var countEl = createEl('div', { className: 'sprint-card-count', textContent: String(total) });
    header.appendChild(nameEl);
    header.appendChild(countEl);
    card.appendChild(header);

    var progressBar = createEl('div', { className: 'sprint-progress' });
    var fill = createEl('div', {
      className: 'sprint-progress-fill ' + (SPRINT_FILL_CLASS[sprint] || ''),
      style: 'width:' + pct + '%'
    });
    progressBar.appendChild(fill);
    card.appendChild(progressBar);

    var meta = createEl('div', { className: 'sprint-card-meta' });
    meta.appendChild(createEl('span', { textContent: done + '/' + total + ' done' }));
    if (TEST_SCRIPTS[sprint]) {
      var testBtn = createEl('button', {
        className: 'sprint-test-btn',
        title: 'View manual test script for ' + sprint,
        onClick: function(e) {
          e.stopPropagation();
          openTestModal(sprint);
        }
      }, [
        createEl('span', { style: 'display:inline-flex' }, [
          (function() {
            var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            svg.setAttribute('width', '12');
            svg.setAttribute('height', '12');
            svg.setAttribute('viewBox', '0 0 16 16');
            svg.setAttribute('fill', 'currentColor');
            var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', 'M5.854 4.854a.5.5 0 10-.708-.708L3 6.293l-.646-.647a.5.5 0 10-.708.708l1 1a.5.5 0 00.708 0l2.5-2.5zM5.854 8.854a.5.5 0 10-.708-.708L3 10.293l-.646-.647a.5.5 0 10-.708.708l1 1a.5.5 0 00.708 0l2.5-2.5zM8 5h5a.5.5 0 000-1H8a.5.5 0 000 1zm0 4h5a.5.5 0 000-1H8a.5.5 0 000 1zm0 4h5a.5.5 0 000-1H8a.5.5 0 000 1z');
            svg.appendChild(path);
            return svg;
          })()
        ]),
        document.createTextNode('Test')
      ]);
      meta.appendChild(testBtn);
    } else {
      meta.appendChild(createEl('span', { textContent: pct + '%' }));
    }
    card.appendChild(meta);

    container.appendChild(card);
  });
}

// ─── Render Stats ────────────────────────────────────────────────
function renderStats(data) {
  var must = data.filter(function(d){ return d.priority === 'Must Have'; }).length;
  var should = data.filter(function(d){ return d.priority === 'Should Have'; }).length;
  var could = data.filter(function(d){ return d.priority === 'Could Have'; }).length;
  var prOpen = data.filter(function(d){ return d.status === 'PR Open'; }).length;
  var done = data.filter(function(d){ return d.status === 'Done' || d.status === 'Merged'; }).length;

  var bar = document.getElementById('statsBar');
  clearChildren(bar);

  var stats = [
    { cls: 'stat-card total', num: data.length, label: 'Total' },
    { cls: 'stat-card must', num: must, label: 'Must Have' },
    { cls: 'stat-card should', num: should, label: 'Should Have' },
    { cls: 'stat-card could', num: could, label: 'Could Have' },
    { cls: 'stat-card', num: prOpen, label: 'PRs Open', numStyle: 'color:#C2410C' },
    { cls: 'stat-card', num: done, label: 'Done', numStyle: 'color:var(--success)' }
  ];

  stats.forEach(function(s) {
    var numEl = createEl('span', { className: 'stat-number', style: s.numStyle || '' }, [String(s.num)]);
    var card = createEl('div', { className: s.cls }, [numEl, document.createTextNode(' ' + s.label)]);
    bar.appendChild(card);
  });
}

// ─── Filter + Sort ───────────────────────────────────────────────
function applyFilters() {
  var filtered = BACKLOG_DATA.slice();

  if (currentFilters.priority !== 'all') {
    filtered = filtered.filter(function(d) { return d.priority === currentFilters.priority; });
  }
  if (currentFilters.status !== 'all') {
    filtered = filtered.filter(function(d) { return d.status === currentFilters.status; });
  }
  if (currentFilters.effort !== 'all') {
    filtered = filtered.filter(function(d) { return d.effort === currentFilters.effort; });
  }
  if (currentFilters.sprint !== 'all') {
    filtered = filtered.filter(function(d) { return d.sprint === currentFilters.sprint; });
  }

  if (currentSort.key) {
    filtered.sort(function(a, b) {
      var va, vb;
      switch (currentSort.key) {
        case 'priority':
          va = PRIORITY_ORDER[a.priority] !== undefined ? PRIORITY_ORDER[a.priority] : 9;
          vb = PRIORITY_ORDER[b.priority] !== undefined ? PRIORITY_ORDER[b.priority] : 9;
          break;
        case 'effort':
          va = EFFORT_ORDER[a.effort] !== undefined ? EFFORT_ORDER[a.effort] : 9;
          vb = EFFORT_ORDER[b.effort] !== undefined ? EFFORT_ORDER[b.effort] : 9;
          break;
        case 'sprint':
          va = SPRINT_SORT_ORDER[a.sprint] !== undefined ? SPRINT_SORT_ORDER[a.sprint] : 9;
          vb = SPRINT_SORT_ORDER[b.sprint] !== undefined ? SPRINT_SORT_ORDER[b.sprint] : 9;
          break;
        case 'status':
          va = STATUS_ORDER.indexOf(a.status);
          vb = STATUS_ORDER.indexOf(b.status);
          if (va < 0) va = 99;
          if (vb < 0) vb = 99;
          break;
        default:
          va = (a[currentSort.key] || '').toString().toLowerCase();
          vb = (b[currentSort.key] || '').toString().toLowerCase();
      }
      if (va < vb) return currentSort.dir === 'asc' ? -1 : 1;
      if (va > vb) return currentSort.dir === 'asc' ? 1 : -1;
      return 0;
    });
  }

  items = filtered;
  render();
}

// ─── Build Table Row ─────────────────────────────────────────────
function buildTableRow(item, i) {
  var tr = createEl('tr', {
    style: 'animation-delay: ' + (i * 0.03) + 's',
    onClick: function() { openSpecModal(item); }
  });

  // ID cell
  tr.appendChild(createEl('td', {}, [createEl('span', { className: 'feature-id', textContent: item.id })]));

  // Feature name cell
  var nameSpan = createEl('span', { className: 'feature-name' });
  if (item.pr) {
    var link = createEl('a', {
      href: 'https://github.com/visionvolve/leadgen-pipeline/pull/' + item.pr.replace('#', ''),
      target: '_blank',
      textContent: item.name
    });
    link.addEventListener('click', function(e) { e.stopPropagation(); });
    nameSpan.appendChild(link);
  } else {
    nameSpan.textContent = item.name;
  }
  tr.appendChild(createEl('td', {}, [nameSpan]));

  // Sprint cell
  tr.appendChild(createEl('td', {}, [
    createEl('span', { className: 'sprint-badge ' + (SPRINT_CLASS[item.sprint] || 'sprint-backlog'), textContent: item.sprint || 'Backlog' })
  ]));

  // Priority cell
  tr.appendChild(createEl('td', {}, [
    createEl('span', { className: 'badge ' + (PRIORITY_CLASS[item.priority] || ''), textContent: item.priority })
  ]));

  // Effort cell
  tr.appendChild(createEl('td', {}, [
    createEl('span', { className: 'effort ' + (EFFORT_CLASS[item.effort] || ''), textContent: item.effort })
  ]));

  // Status cell
  tr.appendChild(createEl('td', {}, [
    createEl('span', { className: 'badge ' + (STATUS_CLASS[item.status] || ''), textContent: item.status })
  ]));

  // PR cell
  var prTd = createEl('td', { className: 'hide-mobile' });
  if (item.pr) {
    var prLink = createEl('a', {
      className: 'pr-link',
      href: 'https://github.com/visionvolve/leadgen-pipeline/pull/' + item.pr.replace('#', ''),
      target: '_blank',
      textContent: item.pr
    });
    prLink.addEventListener('click', function(e) { e.stopPropagation(); });
    prTd.appendChild(prLink);
  } else {
    prTd.appendChild(createEl('span', { className: 'no-deps' }, [document.createTextNode('\u2014')]));
  }
  tr.appendChild(prTd);

  // Deps cell
  var depsTd = createEl('td', { className: 'hide-mobile' });
  if (item.deps.length > 0) {
    var depsList = createEl('div', { className: 'deps-list' });
    item.deps.forEach(function(d) {
      depsList.appendChild(createEl('span', { className: 'dep-tag', textContent: d }));
    });
    depsTd.appendChild(depsList);
  } else {
    depsTd.appendChild(createEl('span', { className: 'no-deps' }, [document.createTextNode('\u2014')]));
  }
  tr.appendChild(depsTd);

  return tr;
}

// ─── Render Table ────────────────────────────────────────────────
function renderTable() {
  var tbody = document.getElementById('tableBody');
  clearChildren(tbody);

  if (items.length === 0) {
    var emptyTd = createEl('td', { colspan: '8' }, [
      createEl('div', { className: 'empty-state', textContent: 'No items match the current filters.' })
    ]);
    tbody.appendChild(createEl('tr', {}, [emptyTd]));
    return;
  }

  // Group items by sprint for display (only when no sort active)
  var groupBySprint = !currentSort.key;

  if (groupBySprint) {
    var sprintGroups = {};
    SPRINT_ORDER.forEach(function(s) { sprintGroups[s] = []; });
    items.forEach(function(item) {
      var sp = item.sprint || 'Backlog';
      if (!sprintGroups[sp]) sprintGroups[sp] = [];
      sprintGroups[sp].push(item);
    });

    var rowIndex = 0;
    SPRINT_ORDER.forEach(function(sprint) {
      var group = sprintGroups[sprint];
      if (group.length === 0) return;

      var headerTr = createEl('tr', { className: 'sprint-group-header' });
      var headerTd = createEl('td', { colspan: '8' });
      var sprintBadge = createEl('span', {
        className: 'sprint-badge ' + (SPRINT_CLASS[sprint] || ''),
        style: 'margin-right:8px',
        textContent: sprint
      });
      headerTd.appendChild(sprintBadge);
      headerTd.appendChild(document.createTextNode(group.length + ' item' + (group.length !== 1 ? 's' : '')));
      headerTr.appendChild(headerTd);
      tbody.appendChild(headerTr);

      group.forEach(function(item) {
        tbody.appendChild(buildTableRow(item, rowIndex++));
      });
    });
    return;
  }

  items.forEach(function(item, i) {
    tbody.appendChild(buildTableRow(item, i));
  });
}

// ─── Render Kanban ───────────────────────────────────────────────
function renderKanban() {
  var container = document.getElementById('kanbanView');
  clearChildren(container);

  var statusGroups = {};
  STATUS_ORDER.forEach(function(s) { statusGroups[s] = []; });
  items.forEach(function(item) {
    if (statusGroups[item.status]) {
      statusGroups[item.status].push(item);
    } else {
      statusGroups['Idea'].push(item);
    }
  });

  var visibleStatuses = STATUS_ORDER.filter(function(s) {
    return statusGroups[s].length > 0 || ['Idea', "Spec'd", 'PR Open', 'Done'].indexOf(s) !== -1;
  });

  visibleStatuses.forEach(function(status) {
    var cards = statusGroups[status];
    var column = createEl('div', { className: 'kanban-column' });

    var headerLeft = createEl('span', {}, [
      createEl('span', { className: 'badge ' + (STATUS_CLASS[status] || ''), style: 'margin-right:6px', textContent: status })
    ]);
    var headerCount = createEl('span', { className: 'count', textContent: String(cards.length) });
    column.appendChild(createEl('div', { className: 'kanban-column-header' }, [headerLeft, headerCount]));

    var cardsEl = createEl('div', { className: 'kanban-cards' });

    if (cards.length === 0) {
      cardsEl.appendChild(createEl('div', {
        style: 'color:#D1D5DB;font-size:12px;text-align:center;padding:16px',
        textContent: 'No items'
      }));
    }

    cards.forEach(function(item, i) {
      var card = createEl('div', {
        className: 'kanban-card',
        style: 'animation-delay: ' + (i * 0.05) + 's',
        onClick: function() { openSpecModal(item); }
      });
      card.appendChild(createEl('div', { className: 'card-id', textContent: item.id }));
      card.appendChild(createEl('div', { className: 'card-name', textContent: item.name }));

      var meta = createEl('div', { className: 'card-meta' });
      meta.appendChild(createEl('span', {
        className: 'badge ' + (PRIORITY_CLASS[item.priority] || ''),
        style: 'font-size:10px;padding:1px 6px',
        textContent: item.priority.replace(' Have', '')
      }));
      meta.appendChild(createEl('span', {
        className: 'effort ' + (EFFORT_CLASS[item.effort] || ''),
        style: 'width:22px;height:18px;font-size:9px',
        textContent: item.effort
      }));
      meta.appendChild(createEl('span', {
        className: 'sprint-badge ' + (SPRINT_CLASS[item.sprint] || 'sprint-backlog'),
        style: 'font-size:9px;padding:1px 5px',
        textContent: SPRINT_LABELS[item.sprint] || 'BL'
      }));
      if (item.pr) {
        var kanbanPrLink = createEl('a', {
          className: 'pr-link',
          href: 'https://github.com/visionvolve/leadgen-pipeline/pull/' + item.pr.replace('#', ''),
          target: '_blank',
          style: 'font-size:10px',
          textContent: item.pr
        });
        kanbanPrLink.addEventListener('click', function(e) { e.stopPropagation(); });
        meta.appendChild(kanbanPrLink);
      }
      card.appendChild(meta);

      if (item.deps.length > 0) {
        var depsDiv = createEl('div', { className: 'card-deps' });
        item.deps.forEach(function(d) {
          depsDiv.appendChild(createEl('span', { className: 'dep-tag', textContent: d }));
        });
        card.appendChild(depsDiv);
      }

      cardsEl.appendChild(card);
    });

    column.appendChild(cardsEl);
    container.appendChild(column);
  });
}

// ─── Dependency Graph ────────────────────────────────────────────
function renderDepGraph() {
  var canvas = document.getElementById('depCanvas');
  var ctx = canvas.getContext('2d');
  var dpr = window.devicePixelRatio || 1;

  var rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = 400 * dpr;
  canvas.style.width = rect.width + 'px';
  canvas.style.height = '400px';
  ctx.scale(dpr, dpr);

  var W = rect.width;
  var H = 400;

  ctx.clearRect(0, 0, W, H);

  var depIds = {};
  var sourceIds = {};
  BACKLOG_DATA.forEach(function(item) {
    item.deps.forEach(function(d) { depIds[d] = true; sourceIds[item.id] = true; });
  });
  var relevantIds = {};
  Object.keys(depIds).forEach(function(k) { relevantIds[k] = true; });
  Object.keys(sourceIds).forEach(function(k) { relevantIds[k] = true; });
  var graphItems = BACKLOG_DATA.filter(function(item) { return relevantIds[item.id]; });

  if (graphItems.length === 0) {
    ctx.fillStyle = '#6B7280';
    ctx.font = '14px Work Sans';
    ctx.textAlign = 'center';
    ctx.fillText('No dependencies to display', W / 2, H / 2);
    return;
  }

  var idMap = {};
  BACKLOG_DATA.forEach(function(item) { idMap[item.id] = item; });

  var layers = [];
  var placed = {};

  var roots = graphItems.filter(function(item) {
    return item.deps.length === 0 || item.deps.every(function(d) { return !relevantIds[d]; });
  });

  if (roots.length > 0) {
    layers.push(roots.map(function(r) { return r.id; }));
    roots.forEach(function(r) { placed[r.id] = true; });
  }

  var safety = 0;
  var placedCount = Object.keys(placed).length;
  while (placedCount < graphItems.length && safety++ < 20) {
    var nextLayer = [];
    graphItems.forEach(function(item) {
      if (!placed[item.id] && item.deps.every(function(d) { return placed[d] || !relevantIds[d]; })) {
        nextLayer.push(item.id);
      }
    });
    if (nextLayer.length === 0) {
      graphItems.forEach(function(item) {
        if (!placed[item.id]) nextLayer.push(item.id);
      });
    }
    layers.push(nextLayer);
    nextLayer.forEach(function(id) { placed[id] = true; });
    placedCount = Object.keys(placed).length;
  }

  var nodePositions = {};
  var nodeW = 140;
  var nodeH = 36;
  var layerGap = 100;
  var totalWidth = layers.length * (nodeW + layerGap) - layerGap;
  var startX = Math.max(30, (W - totalWidth) / 2);

  layers.forEach(function(layer, li) {
    var x = startX + li * (nodeW + layerGap);
    var totalH = layer.length * (nodeH + 16) - 16;
    var startY = Math.max(20, (H - totalH) / 2);

    layer.forEach(function(id, ni) {
      nodePositions[id] = {
        x: x,
        y: startY + ni * (nodeH + 16),
        w: nodeW,
        h: nodeH
      };
    });
  });

  // Draw edges
  BACKLOG_DATA.forEach(function(item) {
    if (!nodePositions[item.id]) return;
    item.deps.forEach(function(depId) {
      if (!nodePositions[depId]) return;

      var from = nodePositions[depId];
      var to = nodePositions[item.id];

      var x1 = from.x + from.w;
      var y1 = from.y + from.h / 2;
      var x2 = to.x;
      var y2 = to.y + to.h / 2;

      ctx.beginPath();
      ctx.moveTo(x1, y1);
      var cx = (x1 + x2) / 2;
      ctx.bezierCurveTo(cx, y1, cx, y2, x2, y2);
      ctx.strokeStyle = '#C4B5FD';
      ctx.lineWidth = 2;
      ctx.stroke();

      var aSize = 6;
      ctx.beginPath();
      ctx.moveTo(x2, y2);
      ctx.lineTo(x2 - aSize * 1.5, y2 - aSize);
      ctx.lineTo(x2 - aSize * 1.5, y2 + aSize);
      ctx.closePath();
      ctx.fillStyle = '#C4B5FD';
      ctx.fill();
    });
  });

  // Draw nodes
  var priorityColors = { 'Must Have': '#DC2626', 'Should Have': '#D97706', 'Could Have': '#3B82F6' };

  Object.keys(nodePositions).forEach(function(id) {
    var pos = nodePositions[id];
    var item = idMap[id];
    if (!item) return;

    ctx.fillStyle = '#FFFFFF';
    ctx.strokeStyle = priorityColors[item.priority] || '#E5E7EB';
    ctx.lineWidth = 2;

    var r = 6;
    ctx.beginPath();
    ctx.moveTo(pos.x + r, pos.y);
    ctx.lineTo(pos.x + pos.w - r, pos.y);
    ctx.quadraticCurveTo(pos.x + pos.w, pos.y, pos.x + pos.w, pos.y + r);
    ctx.lineTo(pos.x + pos.w, pos.y + pos.h - r);
    ctx.quadraticCurveTo(pos.x + pos.w, pos.y + pos.h, pos.x + pos.w - r, pos.y + pos.h);
    ctx.lineTo(pos.x + r, pos.y + pos.h);
    ctx.quadraticCurveTo(pos.x, pos.y + pos.h, pos.x, pos.y + pos.h - r);
    ctx.lineTo(pos.x, pos.y + r);
    ctx.quadraticCurveTo(pos.x, pos.y, pos.x + r, pos.y);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = priorityColors[item.priority] || '#E5E7EB';
    ctx.beginPath();
    ctx.moveTo(pos.x + r, pos.y);
    ctx.lineTo(pos.x + 4, pos.y);
    ctx.lineTo(pos.x + 4, pos.y + pos.h);
    ctx.lineTo(pos.x + r, pos.y + pos.h);
    ctx.quadraticCurveTo(pos.x, pos.y + pos.h, pos.x, pos.y + pos.h - r);
    ctx.lineTo(pos.x, pos.y + r);
    ctx.quadraticCurveTo(pos.x, pos.y, pos.x + r, pos.y);
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = '#6B7280';
    ctx.font = '500 9px monospace';
    ctx.textAlign = 'left';
    ctx.fillText(item.id, pos.x + 10, pos.y + 13);

    ctx.fillStyle = '#404B5C';
    ctx.font = '500 11px Work Sans, sans-serif';
    var name = item.name;
    if (ctx.measureText(name).width > pos.w - 16) {
      while (ctx.measureText(name + '...').width > pos.w - 16 && name.length > 0) {
        name = name.slice(0, -1);
      }
      name += '...';
    }
    ctx.fillText(name, pos.x + 10, pos.y + 28);
  });
}

// ─── Render ──────────────────────────────────────────────────────
function render() {
  renderSprintSummary();
  renderStats(items);
  renderTable();
  renderKanban();

  if (document.getElementById('depGraphContainer').classList.contains('open')) {
    renderDepGraph();
  }
}

// ─── Event Handlers ──────────────────────────────────────────────

document.querySelectorAll('#priorityFilter .filter-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    document.querySelectorAll('#priorityFilter .filter-btn').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
    currentFilters.priority = btn.dataset.priority;
    applyFilters();
  });
});

document.querySelectorAll('#statusFilter .filter-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    document.querySelectorAll('#statusFilter .filter-btn').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
    currentFilters.status = btn.dataset.status;
    applyFilters();
  });
});

document.querySelectorAll('#effortFilter .filter-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    document.querySelectorAll('#effortFilter .filter-btn').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
    currentFilters.effort = btn.dataset.effort;
    applyFilters();
  });
});

document.querySelectorAll('#sprintFilter .filter-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    document.querySelectorAll('#sprintFilter .filter-btn').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
    currentFilters.sprint = btn.dataset.sprint;
    applyFilters();
  });
});

document.querySelectorAll('.view-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    document.querySelectorAll('.view-btn').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
    currentView = btn.dataset.view;

    document.getElementById('tableView').style.display = currentView === 'table' ? '' : 'none';
    var kanban = document.getElementById('kanbanView');
    if (currentView === 'kanban') {
      kanban.classList.add('active');
    } else {
      kanban.classList.remove('active');
    }
    render();
  });
});

document.querySelectorAll('.backlog-table th[data-sort]').forEach(function(th) {
  th.addEventListener('click', function() {
    var key = th.dataset.sort;
    if (currentSort.key === key) {
      currentSort.dir = currentSort.dir === 'asc' ? 'desc' : 'asc';
    } else {
      currentSort.key = key;
      currentSort.dir = 'asc';
    }

    document.querySelectorAll('.backlog-table th').forEach(function(h) {
      h.classList.remove('sorted');
      var icon = h.querySelector('.sort-icon');
      if (icon) icon.textContent = '\u25B2';
    });
    th.classList.add('sorted');
    var icon = th.querySelector('.sort-icon');
    if (icon) icon.textContent = currentSort.dir === 'asc' ? '\u25B2' : '\u25BC';

    applyFilters();
  });
});

document.getElementById('depGraphToggle').addEventListener('click', function() {
  var toggle = document.getElementById('depGraphToggle');
  var container = document.getElementById('depGraphContainer');
  toggle.classList.toggle('open');
  container.classList.toggle('open');

  if (container.classList.contains('open')) {
    setTimeout(renderDepGraph, 50);
  }
});

document.getElementById('specClose').addEventListener('click', closeSpecModal);
document.getElementById('specCloseBtn').addEventListener('click', closeSpecModal);
document.getElementById('specOverlay').addEventListener('click', function(e) {
  if (e.target === this) closeSpecModal();
});
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    if (document.getElementById('testOverlay').classList.contains('open')) {
      closeTestModal();
    } else if (document.getElementById('specOverlay').classList.contains('open')) {
      closeSpecModal();
    }
  }
});

document.getElementById('testClose').addEventListener('click', closeTestModal);
document.getElementById('testCloseBtn').addEventListener('click', closeTestModal);
document.getElementById('testOverlay').addEventListener('click', function(e) {
  if (e.target === this) closeTestModal();
});

document.getElementById('testCopy').addEventListener('click', function() {
  if (!currentTestSprint || !TEST_SCRIPTS[currentTestSprint]) return;
  var btn = this;
  var svgNode = btn.querySelector('svg');
  navigator.clipboard.writeText(TEST_SCRIPTS[currentTestSprint]).then(function() {
    btn.classList.add('copied');
    while (btn.lastChild !== svgNode) btn.removeChild(btn.lastChild);
    btn.appendChild(document.createTextNode(' Copied!'));
    setTimeout(function() {
      btn.classList.remove('copied');
      while (btn.lastChild !== svgNode) btn.removeChild(btn.lastChild);
      btn.appendChild(document.createTextNode(' Copy Markdown'));
    }, 2000);
  });
});

document.getElementById('specCopy').addEventListener('click', function() {
  if (!currentSpecItem) return;
  var text = currentSpecItem.spec || currentSpecItem.description || '';
  if (!text) return;
  var btn = this;
  var svgNode = btn.querySelector('svg');
  navigator.clipboard.writeText(text).then(function() {
    btn.classList.add('copied');
    while (btn.lastChild !== svgNode) btn.removeChild(btn.lastChild);
    btn.appendChild(document.createTextNode(' Copied!'));
    setTimeout(function() {
      btn.classList.remove('copied');
      while (btn.lastChild !== svgNode) btn.removeChild(btn.lastChild);
      btn.appendChild(document.createTextNode(' Copy Spec'));
    }, 2000);
  });
});

// ─── Auto-Refresh ────────────────────────────────────────────────
var lastUpdate = new Date();

function updateTimestamp() {
  var el = document.getElementById('lastUpdated');
  var diff = Math.floor((new Date() - lastUpdate) / 1000);
  if (diff < 10) el.textContent = 'Updated just now';
  else if (diff < 60) el.textContent = 'Updated ' + diff + 's ago';
  else el.textContent = 'Updated ' + Math.floor(diff / 60) + 'm ago';
}

setInterval(updateTimestamp, 5000);

// ─── Resize handler ──────────────────────────────────────────────
window.addEventListener('resize', function() {
  if (document.getElementById('depGraphContainer').classList.contains('open')) {
    renderDepGraph();
  }
});

// ─── Data Loading ────────────────────────────────────────────────
function showFileProtocolError() {
  var tbody = document.getElementById('tableBody');
  clearChildren(tbody);
  var msgDiv = createEl('div', {
    className: 'empty-state',
    style: 'padding:32px;line-height:1.7'
  });
  msgDiv.appendChild(document.createTextNode('Cannot load data over '));
  msgDiv.appendChild(createEl('code', { textContent: 'file://' }));
  msgDiv.appendChild(document.createTextNode(' protocol. Run a local server instead:'));
  msgDiv.appendChild(createEl('pre', { textContent: 'make backlog\n\n# or manually:\ncd docs/backlog && python3 -m http.server 8090' }));
  tbody.appendChild(createEl('tr', {}, [createEl('td', { colspan: '8' }, [msgDiv])]));
}

function normalizeItem(raw) {
  return {
    id: raw.id || '',
    name: raw.title || raw.name || '',
    priority: raw.priority || 'Could Have',
    effort: raw.effort || 'M',
    status: raw.status || 'Idea',
    sprint: raw.sprint || 'Backlog',
    deps: raw.depends_on || raw.deps || [],
    assignee: raw.assignee || '',
    pr: raw.pr || '',
    spec: raw.spec || '',
    description: raw.description || '',
    spec_file: raw.spec_file || '',
    theme: raw.theme || ''
  };
}

function loadData() {
  if (window.location.protocol === 'file:') {
    showFileProtocolError();
    return;
  }

  Promise.all([
    fetch('config.json').then(function(r) { return r.json(); }),
    fetch('sprints.json').then(function(r) { return r.json(); }),
    fetch('test-scripts.json').then(function(r) { return r.json(); }),
    fetch('docs-links.json').then(function(r) { return r.json(); })
  ]).then(function(results) {
    var config = results[0];
    SPRINT_DEFS = results[1];
    TEST_SCRIPTS = results[2];
    DOCS_LINKS = results[3];

    renderDocsBar();

    var itemIds = config.items || [];
    var fetches = itemIds.map(function(id) {
      return fetch('items/' + id + '.json')
        .then(function(r) {
          if (!r.ok) return null;
          return r.json();
        })
        .catch(function() { return null; });
    });

    return Promise.all(fetches);
  }).then(function(rawItems) {
    rawItems.forEach(function(raw) {
      if (raw) BACKLOG_DATA.push(normalizeItem(raw));
    });

    items = BACKLOG_DATA.slice();
    lastUpdate = new Date();
    updateTimestamp();
    applyFilters();
  }).catch(function(err) {
    console.error('Failed to load backlog data:', err);
    var tbody = document.getElementById('tableBody');
    clearChildren(tbody);
    var errTd = createEl('td', { colspan: '8' }, [
      createEl('div', { className: 'empty-state', textContent: 'Failed to load backlog data. Make sure you are serving this directory via HTTP.' })
    ]);
    tbody.appendChild(createEl('tr', {}, [errTd]));
  });
}

// ─── Initial Load ────────────────────────────────────────────────
loadData();
