// ── State ────────────────────────────────────────────────────────────────────
const state = {
  experiments: [],          // full list from /api/experiments
  active: null,             // currently viewed experiment (full data)
  activeSlug: null,
  // Global asset filter — persists across experiment switches.
  // null  = no filter (show all assets)
  // Set   = explicit selection; empty Set = show nothing
  selectedAssets: null,
  // Collapsed sections — persists across experiment/asset switches.
  // key = section id string, value = true (collapsed) / false (expanded)
  collapsed: {},
  // Table sort — col = data-col string, dir = 1 (asc) / -1 (desc)
  sort: { col: null, dir: 1 },
};

// ── Boot ─────────────────────────────────────────────────────────────────────
async function boot() {
  document.getElementById("refreshBtn").addEventListener("click", loadExperiments);
  document.getElementById("assetFilterChips").addEventListener("mouseleave", onChipsMouseLeave);
  initSortHeaders();
  // Initialise global asset filter with the full universe before loading experiments
  const uResp = await fetch("/api/universe");
  const universe = await uResp.json();
  buildAssetFilter(universe.all || []);
  await loadExperiments();
}

async function loadExperiments() {
  const resp = await fetch("/api/experiments");
  state.experiments = await resp.json();
  renderExpList(state.experiments);

  // Re-load active experiment if it still exists
  if (state.activeSlug) {
    const still = state.experiments.find(e => e.slug === state.activeSlug);
    if (still) loadExperiment(state.activeSlug);
  }
}

// ── Experiment list sorting ───────────────────────────────────────────────────

function initSortHeaders() {
  document.querySelectorAll("#expTable thead th[data-col]").forEach(th => {
    th.classList.add("sortable");
    th.addEventListener("click", () => {
      const col = th.dataset.col;
      state.sort.dir = state.sort.col === col ? state.sort.dir * -1 : 1;
      state.sort.col = col;
      renderExpList(state.experiments);
    });
  });
}

function sortKey(exp, col) {
  const m    = exp.metrics || {};
  const hm   = exp.historical_metrics || {};
  const meta = exp.metadata || {};
  const NEG  = -Infinity;
  switch (col) {
    case "slug":     return exp.slug || "";
    case "strategy": return meta.strategy_label || meta.strategy || "";
    case "assets":   return (meta.symbols || []).length;
    case "interval": return meta.interval || "";
    case "return":   return m.total_return_pct ?? NEG;
    case "bah":      return buyAndHoldReturn(exp.buy_and_hold) ?? NEG;
    case "ly":       return hm.total_return_pct ?? NEG;
    case "bah25":    return buyAndHoldReturn(exp.historical_buy_and_hold) ?? NEG;
    case "dd":       return m.max_drawdown_pct ?? NEG;
    case "fills":    return m.fills ?? NEG;
    case "status":   return ["promising","revised","in_progress","rejected"].indexOf(exp.status);
    default:         return "";
  }
}

function applySortIndicators() {
  document.querySelectorAll("#expTable thead th[data-col]").forEach(th => {
    const label = th.dataset.col === state.sort.col
      ? th.textContent.replace(/ [▲▼]$/, "") + (state.sort.dir === 1 ? " ▲" : " ▼")
      : th.textContent.replace(/ [▲▼]$/, "");
    th.textContent = label;
  });
}

// ── Experiment list ───────────────────────────────────────────────────────────

// Aggregate per-symbol metrics for a set of selected assets.
// Returns null when nothing is selected, or a stats object when 1+ symbols selected.
// `notTested` = true if none of the selected symbols appear in this experiment.
function aggregateSelected(exp, selectedAssets) {
  if (selectedAssets === null) return null;  // "all" — caller uses overall metrics
  if (selectedAssets.size === 0) return { empty: true };

  const ps_all = exp.per_symbol_metrics || {};
  const init_eq = (exp.metrics || {}).initial_equity || 100000;
  let total_pnl = 0, fills = 0, rt = 0, win_count = 0, gross_win = 0, gross_loss = 0;
  let found = 0;

  for (const sym of selectedAssets) {
    const ps = ps_all[sym];
    if (!ps) continue;
    found++;
    total_pnl += ps.total_pnl || 0;
    fills     += ps.fills      || 0;
    rt        += ps.round_trips || 0;
    win_count += ps.win_count  || 0;
    gross_win += ps.gross_win  || 0;
    gross_loss += ps.gross_loss || 0;
  }

  if (found === 0) return { notTested: true };

  return {
    ret:      Math.round(total_pnl / init_eq * 10000) / 100,
    fills,
    winRate:  rt ? Math.round(win_count / rt * 1000) / 10 : null,
    pf:       gross_loss > 0 ? Math.round(gross_win / gross_loss * 100) / 100 : null,
  };
}

function renderExpList(experiments) {
  const tbody = document.getElementById("expBody");
  const count = document.getElementById("expCount");
  count.textContent = experiments.length ? `${experiments.length}` : "";

  if (experiments.length === 0) {
    tbody.innerHTML = '<tr><td colspan="12" class="empty-msg">No experiments yet. Run one with <code>run_experiment.py</code>.</td></tr>';
    return;
  }

  // Sort
  const sorted = state.sort.col
    ? [...experiments].sort((a, b) => {
        const ka = sortKey(a, state.sort.col);
        const kb = sortKey(b, state.sort.col);
        if (ka < kb) return -state.sort.dir;
        if (ka > kb) return  state.sort.dir;
        return 0;
      })
    : experiments;
  applySortIndicators();

  const isAll = state.selectedAssets === null;
  const dash  = "—";
  const na    = '<span class="dim">n/a</span>';

  tbody.innerHTML = "";
  for (const exp of sorted) {
    const m    = exp.metrics || {};
    const hm   = exp.historical_metrics || {};
    const hps  = exp.historical_per_symbol_metrics || {};
    const meta = exp.metadata || {};
    const assets = meta.symbols || [];
    const assetStr = assets.length <= 4 ? assets.join(", ")
                   : `${assets.slice(0, 3).join(", ")} +${assets.length - 3}`;

    let retCell, ddCell, fillsCell, lastYearCell;

    // B&H columns — filter-aware, reuse existing helper
    const bahVal   = buyAndHoldReturn(exp.buy_and_hold);
    const bah25Val = buyAndHoldReturn(exp.historical_buy_and_hold);
    const bahCell   = bahVal   != null ? `<span class="${colorCls(bahVal)}">${fmt(bahVal, "%", true)}</span>`   : dash;
    const bah25Cell = bah25Val != null ? `<span class="${colorCls(bah25Val)}">${fmt(bah25Val, "%", true)}</span>` : dash;

    // Helper: last-year cell for a given return value
    const lyCell = v => v != null ? `<span class="${colorCls(v)}">${fmt(v, "%", true)}</span>` : dash;

    if (isAll) {
      retCell      = `<span class="${colorCls(m.total_return_pct)}">${fmt(m.total_return_pct, "%", true)}</span>`;
      ddCell       = `<span class="${colorCls(m.max_drawdown_pct)}">${fmt(m.max_drawdown_pct, "%", true)}</span>`;
      fillsCell    = m.fills ?? dash;
      lastYearCell = lyCell(hm.total_return_pct);
    } else {
      const agg = aggregateSelected(exp, state.selectedAssets);
      if (agg.empty) {
        retCell = ddCell = fillsCell = lastYearCell = dash;
      } else if (agg.notTested) {
        retCell = ddCell = fillsCell = lastYearCell = na;
      } else if (state.selectedAssets.size === 1) {
        const sym = [...state.selectedAssets][0];
        const ps  = (exp.per_symbol_metrics || {})[sym];
        const hpsSym = hps[sym];
        if (ps) {
          retCell   = `<span class="${colorCls(ps.return_pct)}">${fmt(ps.return_pct, "%", true)}</span>`;
          ddCell    = ps.max_drawdown_pct != null ? `<span class="${colorCls(ps.max_drawdown_pct)}">${fmt(ps.max_drawdown_pct, "%", true)}</span>` : dash;
          fillsCell = ps.fills ?? dash;
        } else {
          retCell = ddCell = fillsCell = na;
        }
        // Use per-symbol historical return if available, else overall
        lastYearCell = hpsSym ? lyCell(hpsSym.return_pct) : lyCell(hm.total_return_pct);
      } else {
        retCell      = `<span class="${colorCls(agg.ret)}">${fmt(agg.ret, "%", true)}</span>`;
        ddCell       = dash;
        fillsCell    = agg.fills ?? dash;
        lastYearCell = lyCell(hm.total_return_pct);
      }
    }

    let rowCls = "exp-row";
    if (exp.slug === state.activeSlug) rowCls += " row-active";

    const tr = document.createElement("tr");
    tr.className = rowCls;
    tr.dataset.slug = exp.slug;
    tr.innerHTML = `
      <td class="row-indicator ${statusCls(exp.status)}"></td>
      <td class="col-mono col-slug">${exp.slug}</td>
      <td>${meta.strategy_label || meta.strategy || "—"}</td>
      <td class="col-assets" title="${assets.join(', ')}">${assetStr}</td>
      <td class="col-mono">${meta.interval || "—"}</td>
      <td>${retCell}</td>
      <td>${bahCell}</td>
      <td>${lastYearCell}</td>
      <td>${bah25Cell}</td>
      <td>${ddCell}</td>
      <td>${fillsCell}</td>
      <td><span class="status-pill ${statusCls(exp.status)}">${exp.status}</span></td>
    `;
    tr.addEventListener("click", () => loadExperiment(exp.slug));
    tbody.appendChild(tr);
  }
}

function statusCls(status) {
  return { promising: "s-promising", rejected: "s-rejected", in_progress: "s-progress", revised: "s-revised" }[status] || "s-progress";
}

// ── Load and render a single experiment ───────────────────────────────────────
async function loadExperiment(slug) {
  state.activeSlug = slug;

  // Highlight the row
  document.querySelectorAll(".exp-row").forEach(r => r.classList.toggle("row-active", r.dataset.slug === slug));

  const resp = await fetch(`/api/experiments/${slug}`);
  const data = await resp.json();
  if (data.error) { alert(data.error); return; }

  state.active = data;
  // Global filter already set — chips are persistent, do not rebuild.
  renderExperiment(data);      // slug, status badge, rules
  applyAssetFilter();          // metrics / calendar / transactions with current filter
  document.getElementById("expView").classList.remove("hidden");
}

// ── Asset filter ──────────────────────────────────────────────────────────────

// _preHover: undefined = not hovering; any other value = saved selection before hover
let _preHover = undefined;

function onChipMouseEnter(sym) {
  if (_preHover === undefined) _preHover = state.selectedAssets;  // save on first enter
  state.selectedAssets = new Set([sym]);
  document.querySelectorAll("#assetFilterChips .asset-chip").forEach(c => {
    c.classList.toggle("active", c.dataset.sym === sym);
  });
  applyAssetFilter();
}

function onChipsMouseLeave() {
  if (_preHover === undefined) return;
  state.selectedAssets = _preHover;
  _preHover = undefined;
  document.querySelectorAll("#assetFilterChips .asset-chip").forEach(c => {
    c.classList.toggle("active", state.selectedAssets === null || state.selectedAssets.has(c.dataset.sym));
  });
  applyAssetFilter();
}

function buildAssetFilter(symbols) {
  const container = document.getElementById("assetFilterChips");
  container.innerHTML = "";
  for (const sym of symbols) {
    const active = state.selectedAssets === null || state.selectedAssets.has(sym);
    const btn = document.createElement("button");
    btn.className = "asset-chip" + (active ? " active" : "");
    btn.textContent = sym;
    btn.dataset.sym = sym;
    btn.addEventListener("click", () => toggleFilter(sym, btn));
    btn.addEventListener("mouseenter", () => onChipMouseEnter(sym));
    container.appendChild(btn);
  }
}

function toggleFilter(sym, btn) {
  // Use the pre-hover locked state (not the hover-modified one) to decide toggle.
  // Without this, hovering already sets selectedAssets = Set([sym]), so a click
  // would immediately see onlyThis=true and toggle back to null.
  const locked = _preHover !== undefined ? _preHover : state.selectedAssets;
  const onlyThis = locked instanceof Set && locked.size === 1 && locked.has(sym);
  if (onlyThis) {
    state.selectedAssets = null;  // back to all
  } else {
    state.selectedAssets = new Set([sym]);
  }
  _preHover = undefined;  // commit click as new baseline so mouseleave won't undo it
  // Sync chip active states
  document.querySelectorAll("#assetFilterChips .asset-chip").forEach(c => {
    c.classList.toggle("active", state.selectedAssets === null || state.selectedAssets.has(c.dataset.sym));
  });
  applyAssetFilter();
}

function filterAll() {
  state.selectedAssets = null;  // null = show everything
  document.querySelectorAll("#assetFilterChips .asset-chip").forEach(c => c.classList.add("active"));
  applyAssetFilter();
}

function filterNone() {
  state.selectedAssets = new Set();  // empty set = show nothing
  document.querySelectorAll("#assetFilterChips .asset-chip").forEach(c => c.classList.remove("active"));
  applyAssetFilter();
}

function applyAssetFilter() {
  renderExpList(state.experiments);
  if (!state.active) return;
  const txns = state.active.transactions || [];
  renderMetrics(...computeFilteredMetrics(txns, state.active.metadata));
  renderTransactions(txns);
  renderCalendar(state.active.calendar || []);
  renderHistorical(state.active.historical || null);
}

// ── Compute metrics from filtered transactions ────────────────────────────────
// When all assets selected: return stored metrics unchanged (includes equity-curve Sharpe/DD).
// When a subset: recompute from transactions (Sharpe and DD shown as "—", can't derive without equity curve).
function computeFilteredMetrics(txns, meta) {
  // null = all assets selected (no filter)
  const isAll = state.selectedAssets === null;

  if (isAll) {
    return [state.active.metrics, state.active.extended_metrics, meta, false];
  }

  const filtered = txns.filter(t => state.selectedAssets.has(t.asset));
  const exits = filtered.filter(t => t.pnl != null);
  const totalPnl = exits.reduce((s, t) => s + t.pnl, 0);
  const wins = exits.filter(t => t.pnl > 0);
  const losses = exits.filter(t => t.pnl <= 0);
  const grossWin = wins.reduce((s, t) => s + t.pnl, 0);
  const grossLoss = Math.abs(losses.reduce((s, t) => s + t.pnl, 0));

  // Derive number of months from the stored monthly/total return ratio
  const storedM = state.active.metrics || {};
  const nMonths = (storedM.total_return_pct && storedM.monthly_return_pct)
    ? Math.abs(storedM.total_return_pct / storedM.monthly_return_pct)
    : 3;

  const initEquity = storedM.initial_equity ?? 100000;
  const returnPct = (totalPnl / initEquity) * 100;

  let maxCons = 0, streak = 0;
  for (const t of exits) { streak = t.pnl <= 0 ? streak + 1 : 0; maxCons = Math.max(maxCons, streak); }

  const m = {
    initial_equity: initEquity,
    final_equity: Math.round((initEquity + totalPnl) * 100) / 100,
    total_return_pct: Math.round(returnPct * 100) / 100,
    monthly_return_pct: Math.round((returnPct / nMonths) * 100) / 100,
    sharpe_ratio: null,       // needs equity curve — not computable per-asset
    max_drawdown_pct: null,   // same
    fills: filtered.length,
  };
  const x = {
    round_trips: exits.length,
    win_rate_pct: exits.length ? Math.round(wins.length / exits.length * 1000) / 10 : null,
    profit_factor: grossLoss > 0 ? Math.round(grossWin / grossLoss * 100) / 100 : null,
    expectancy: exits.length ? Math.round(totalPnl / exits.length * 100) / 100 : null,
    max_consecutive_losses: maxCons,
  };
  return [m, x, meta, true];  // true = partial (subset of assets)
}

// ── Render full experiment ────────────────────────────────────────────────────
function renderExperiment(data) {
  document.getElementById("expSlug").textContent = data.slug || "";
  const badge = document.getElementById("expStatusBadge");
  badge.textContent = data.status || "";
  badge.className = `status-badge ${statusCls(data.status)}`;
  renderRules(data.rules || []);
  // Metrics / calendar / transactions are rendered by applyAssetFilter()
}

// ── Rules ─────────────────────────────────────────────────────────────────────
function renderRules(rules) {
  const list = document.getElementById("rulesList");
  list.innerHTML = "";
  for (const rule of rules) {
    const li = document.createElement("li");
    li.textContent = rule;
    list.appendChild(li);
  }
}

// ── Metrics ───────────────────────────────────────────────────────────────────
function renderMetrics(m, x, meta, partial) {
  const grid = document.getElementById("metricsGrid");
  grid.innerHTML = "";

  // When partial (asset subset), Sharpe and DD can't be derived from transactions alone
  const sharpeVal  = m.sharpe_ratio  != null ? m.sharpe_ratio.toFixed(2) : "—";
  const ddVal      = m.max_drawdown_pct != null ? fmt(m.max_drawdown_pct, "%", true) : "—";
  const sharpeCls  = m.sharpe_ratio  != null ? colorCls(m.sharpe_ratio) : "dim";
  const ddCls      = m.max_drawdown_pct != null ? colorCls(m.max_drawdown_pct) : "dim";

  const bah = buyAndHoldReturn(meta?.buy_and_hold);
  const cards = [
    { label: "Total Return",   value: fmt(m.total_return_pct, "%", true),    cls: colorCls(m.total_return_pct) },
    { label: "Monthly Return", value: fmt(m.monthly_return_pct, "%", true),  cls: colorCls(m.monthly_return_pct) },
    { label: "Buy & Hold",     value: bah != null ? fmt(bah, "%", true) : "—", cls: colorCls(bah) },
    { label: "Sharpe",         value: sharpeVal,  cls: sharpeCls },
    { label: "Max Drawdown",   value: ddVal,      cls: ddCls },
    { label: "Fills",          value: m.fills ?? "—",  cls: "" },
    { label: "Round Trips",    value: x?.round_trips ?? "—", cls: "" },
    { label: "Win Rate",       value: x?.win_rate_pct != null ? x.win_rate_pct + "%" : "—",
                               cls: colorCls(x?.win_rate_pct != null ? x.win_rate_pct - 50 : null) },
    { label: "Profit Factor",  value: x?.profit_factor?.toFixed(2) ?? "—",
                               cls: colorCls(x?.profit_factor != null ? x.profit_factor - 1 : null) },
    { label: "Expectancy",     value: x?.expectancy != null ? "$" + x.expectancy.toFixed(2) : "—",
                               cls: colorCls(x?.expectancy) },
    { label: "Final Equity",   value: "$" + (m.final_equity ?? 0).toLocaleString(), cls: "" },
    { label: "Leverage",       value: (meta?.leverage ?? 1) + "×", cls: "" },
    { label: "Interval",       value: meta?.interval ?? "—", cls: "" },
  ];

  for (const c of cards) {
    const div = document.createElement("div");
    div.className = "metric-card";
    div.innerHTML = `<div class="metric-label">${c.label}</div><div class="metric-value ${c.cls}">${c.value}</div>`;
    grid.appendChild(div);
  }

  // Show a subtle note when showing partial (per-asset) metrics
  document.querySelector(".metrics-note")?.remove();
  if (partial) {
    const note = document.createElement("div");
    note.className = "metrics-note";
    note.textContent = "Showing realized PnL for selected assets. Sharpe and Max DD require full run.";
    grid.after(note);
  }
}

// ── Calendar with hover ───────────────────────────────────────────────────────
function renderCalendar(calData, containerId = "calendarView") {
  const view = document.getElementById(containerId);
  view.innerHTML = "";

  // Filter calendar data to selected assets
  const filtered = calData.map(day => {
    if (!day.has_trades) return day;
    const trades = (day.trades || []).filter(t =>
      state.selectedAssets === null || state.selectedAssets.has(t.asset));
    const pnl = trades.reduce((s, t) => s + (t.pnl ?? 0), 0);
    const assets = [...new Set(trades.map(t => t.asset))];
    return { ...day, trades, trade_count: trades.length, pnl: Math.round(pnl * 100) / 100,
             assets, has_trades: trades.length > 0 };
  });

  const months = {};
  for (const d of filtered) {
    const month = d.date.slice(0, 7);
    if (!months[month]) months[month] = [];
    months[month].push(d);
  }

  const DAY_LABELS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];

  const initEq = state.active?.metrics?.initial_equity || 100000;

  for (const [month, days] of Object.entries(months).sort()) {
    const [year, mon] = month.split("-").map(Number);
    const monthDiv = document.createElement("div");
    monthDiv.className = "cal-month";

    const monthPnl = days.reduce((s, d) => s + (d.pnl || 0), 0);
    const monthPct = monthPnl / initEq * 100;
    const pctStr   = (monthPct >= 0 ? "+" : "") + monthPct.toFixed(2) + "%";
    const pctCls   = monthPct > 0 ? "pos" : monthPct < 0 ? "neg" : "dim";
    const monthName = new Date(year, mon - 1, 1).toLocaleString("default", { month: "long", year: "numeric" });

    const label = document.createElement("div");
    label.className = "cal-month-label";
    label.innerHTML = `<span>${monthName}</span><span class="cal-month-pct ${pctCls}">${pctStr}</span>`;
    monthDiv.appendChild(label);

    const header = document.createElement("div");
    header.className = "cal-week-header";
    for (const dl of DAY_LABELS) {
      const span = document.createElement("div");
      span.className = "cal-day-label";
      span.textContent = dl;
      header.appendChild(span);
    }
    monthDiv.appendChild(header);

    const dayMap = {};
    for (const d of days) dayMap[d.date.slice(8, 10)] = d;

    const firstDow = new Date(year, mon - 1, 1).getDay();
    const startOffset = (firstDow + 6) % 7;
    const daysInMonth = new Date(year, mon, 0).getDate();

    let week = document.createElement("div");
    week.className = "cal-week";

    for (let i = 0; i < startOffset; i++) {
      week.appendChild(emptyCell());
    }

    for (let d = 1; d <= daysInMonth; d++) {
      const dd = String(d).padStart(2, "0");
      const info = dayMap[dd];
      const cell = document.createElement("div");

      if (info) {
        let cls = "cal-day market-day";
        if (info.has_trades) {
          cls += info.pnl > 0 ? " has-trades pnl-pos" : info.pnl < 0 ? " has-trades pnl-neg" : " has-trades";
          // Hover listeners
          cell.addEventListener("mouseenter", e => showTooltip(e, info));
          cell.addEventListener("mousemove", e => moveTooltip(e));
          cell.addEventListener("mouseleave", hideTooltip);
        }
        cell.className = cls;
      } else {
        cell.className = "cal-day empty";
      }

      const num = document.createElement("span");
      num.className = "cal-day-num";
      num.textContent = d;
      cell.appendChild(num);
      week.appendChild(cell);

      const dow = (startOffset + d - 1) % 7;
      if (dow === 6 || d === daysInMonth) {
        if (d === daysInMonth) {
          for (let i = 0; i < 6 - dow; i++) week.appendChild(emptyCell());
        }
        monthDiv.appendChild(week);
        week = document.createElement("div");
        week.className = "cal-week";
      }
    }
    view.appendChild(monthDiv);
  }
}

function emptyCell() {
  const c = document.createElement("div");
  c.className = "cal-day empty";
  return c;
}

// ── Tooltip ───────────────────────────────────────────────────────────────────
function showTooltip(e, day) {
  const tip = document.getElementById("tooltip");
  const pnlStr = day.pnl >= 0 ? `+$${day.pnl.toFixed(2)}` : `-$${Math.abs(day.pnl).toFixed(2)}`;
  const pnlCls = day.pnl > 0 ? "tp-pos" : day.pnl < 0 ? "tp-neg" : "";
  const assetsStr = (day.assets || []).join(", ") || "—";

  let tradesHtml = "";
  const trades = day.trades || [];
  if (trades.length) {
    tradesHtml = `<div class="tip-trades">`;
    for (const t of trades) {
      const sideLower = t.side.toLowerCase();
      let sideCls = sideLower.includes("buy") && !sideLower.includes("cover") ? "tp-buy"
                  : sideLower.includes("sell") && !sideLower.includes("short") ? "tp-sell"
                  : "tp-short";
      const pnl = t.pnl != null ? ` <span class="${t.pnl >= 0 ? 'tp-pos' : 'tp-neg'}">${t.pnl >= 0 ? "+" : ""}$${t.pnl.toFixed(2)}</span>` : "";
      const timeStr = t.time ? `<span class="dim"> ${t.time}</span>` : "";
      const levTag = t.leverage != null && t.leverage !== 1 ? ` <span class="pos">${t.leverage}×</span>` : "";
      tradesHtml += `<div class="tip-trade"><span class="${sideCls}">${t.asset} ${t.side}</span>${timeStr}${levTag} ×${t.size} @$${t.price.toFixed(2)}${pnl}</div>`;
    }
    tradesHtml += `</div>`;
  }

  tip.innerHTML = `
    <div class="tip-date">${day.date}</div>
    <div class="tip-row"><span class="tip-label">PnL</span><span class="${pnlCls}">${pnlStr}</span></div>
    <div class="tip-row"><span class="tip-label">Assets</span><span>${assetsStr}</span></div>
    <div class="tip-row"><span class="tip-label">Trades</span><span>${day.trade_count}</span></div>
    ${tradesHtml}
  `;
  tip.classList.remove("hidden");
  moveTooltip(e);
}

function moveTooltip(e) {
  const tip = document.getElementById("tooltip");
  const margin = 12;
  let x = e.clientX + margin;
  let y = e.clientY + margin;
  // Keep within viewport
  const tw = tip.offsetWidth, th = tip.offsetHeight;
  if (x + tw > window.innerWidth - 8) x = e.clientX - tw - margin;
  if (y + th > window.innerHeight - 8) y = e.clientY - th - margin;
  tip.style.left = x + "px";
  tip.style.top  = y + "px";
}

function hideTooltip() {
  document.getElementById("tooltip").classList.add("hidden");
}

// ── Transactions table ────────────────────────────────────────────────────────
function renderTransactions(txns) {
  const tbody = document.getElementById("txnBody");
  tbody.innerHTML = "";

  const filtered = txns
    .filter(t => state.selectedAssets === null || state.selectedAssets.has(t.asset))
    .slice()
    .reverse();

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-msg">No transactions for selected assets.</td></tr>';
    return;
  }

  for (const t of filtered) {
    const sideLower = t.side.toLowerCase();
    let sideCls = sideLower.includes("buy") && !sideLower.includes("cover") ? "buy"
                : sideLower.includes("sell") && !sideLower.includes("short") ? "sell"
                : "short";
    let pnlCls = "pnl-zero", pnlStr = "—";
    if (t.pnl != null) {
      pnlStr = (t.pnl >= 0 ? "+" : "") + "$" + t.pnl.toFixed(2);
      pnlCls = t.pnl > 0 ? "pnl-pos" : t.pnl < 0 ? "pnl-neg" : "pnl-zero";
    }
    const levStr = t.leverage != null && t.leverage !== 1 ? `${t.leverage}×` : "1×";
    const levCls = t.leverage != null && t.leverage !== 1 ? "pos" : "dim";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${t.date}</td>
      <td class="col-mono dim">${t.time || "—"}</td>
      <td>${t.asset}</td>
      <td class="${sideCls}">${t.side}</td>
      <td class="${levCls}">${levStr}</td>
      <td>${t.size}</td>
      <td>$${t.price.toFixed(2)}</td>
      <td class="${pnlCls}">${pnlStr}</td>
    `;
    tbody.appendChild(tr);
  }
}

// ── Historical (2025) section ─────────────────────────────────────────────────
function renderHistorical(hist) {
  const view = document.getElementById("historicalView");
  if (!hist || !hist.metrics) { view.classList.add("hidden"); return; }
  view.classList.remove("hidden");

  // Update window label
  document.querySelector(".hist-window").textContent = hist.window || "";

  // Determine metrics to show — per-symbol when one asset selected
  const isAll = state.selectedAssets === null;
  let m = hist.metrics || {};
  let x = hist.extended_metrics || {};
  let partial = false;

  if (!isAll && state.selectedAssets.size === 1) {
    const sym = [...state.selectedAssets][0];
    const ps = (hist.per_symbol_metrics || {})[sym];
    if (ps) {
      m = {
        total_return_pct:  ps.return_pct,
        monthly_return_pct: ps.monthly_return_pct,
        sharpe_ratio:      ps.sharpe_ratio,
        max_drawdown_pct:  ps.max_drawdown_pct,
        fills:             ps.fills,
        initial_equity:    (hist.metrics || {}).initial_equity,
        final_equity:      null,
      };
      x = {
        round_trips:    ps.round_trips,
        win_rate_pct:   ps.win_rate_pct,
        profit_factor:  ps.profit_factor,
        expectancy:     ps.expectancy,
      };
      partial = true;
    } else {
      // Symbol not tested in this run — show overall
    }
  }

  // Render metrics into historicalMetrics grid
  const grid = document.getElementById("historicalMetrics");
  grid.innerHTML = "";
  const sharpeVal = m.sharpe_ratio  != null ? m.sharpe_ratio.toFixed(2) : "—";
  const ddVal     = m.max_drawdown_pct != null ? fmt(m.max_drawdown_pct, "%", true) : "—";
  const histBah   = buyAndHoldReturn(hist.buy_and_hold);
  const cards = [
    { label: "Total Return",   value: fmt(m.total_return_pct, "%", true),   cls: colorCls(m.total_return_pct) },
    { label: "Monthly Return", value: fmt(m.monthly_return_pct, "%", true), cls: colorCls(m.monthly_return_pct) },
    { label: "Buy & Hold",     value: histBah != null ? fmt(histBah, "%", true) : "—", cls: colorCls(histBah) },
    { label: "Sharpe",         value: sharpeVal,  cls: colorCls(m.sharpe_ratio) },
    { label: "Max Drawdown",   value: ddVal,      cls: colorCls(m.max_drawdown_pct) },
    { label: "Fills",          value: m.fills ?? "—", cls: "" },
    { label: "Round Trips",    value: x.round_trips ?? "—", cls: "" },
    { label: "Win Rate",       value: x.win_rate_pct != null ? x.win_rate_pct + "%" : "—",
                               cls: colorCls(x.win_rate_pct != null ? x.win_rate_pct - 50 : null) },
    { label: "Profit Factor",  value: x.profit_factor?.toFixed(2) ?? "—",
                               cls: colorCls(x.profit_factor != null ? x.profit_factor - 1 : null) },
    { label: "Expectancy",     value: x.expectancy != null ? "$" + x.expectancy.toFixed(2) : "—",
                               cls: colorCls(x.expectancy) },
  ];
  for (const c of cards) {
    const div = document.createElement("div");
    div.className = "metric-card";
    div.innerHTML = `<div class="metric-label">${c.label}</div><div class="metric-value ${c.cls}">${c.value}</div>`;
    grid.appendChild(div);
  }

  // Calendar — filter by selected assets the same way as primary
  renderCalendar(hist.calendar || [], "historicalCalendar");
}

// ── Collapsible sections ──────────────────────────────────────────────────────
function toggleSection(id) {
  state.collapsed[id] = !state.collapsed[id];
  const panel = document.getElementById("sec-" + id);
  if (panel) panel.classList.toggle("collapsed", !!state.collapsed[id]);
}

// ── Buy & hold helper ─────────────────────────────────────────────────────────
// Returns equal-weighted avg B&H return for the currently selected assets,
// or null if data isn't available.
function buyAndHoldReturn(bah) {
  if (!bah || Object.keys(bah).length === 0) return null;
  const syms = state.selectedAssets === null
    ? Object.keys(bah)
    : [...state.selectedAssets].filter(s => s in bah);
  if (syms.length === 0) return null;
  return Math.round(syms.reduce((s, sym) => s + bah[sym], 0) / syms.length * 100) / 100;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(v, suffix = "", sign = false) {
  if (v == null) return "—";
  const s = sign && v > 0 ? "+" : "";
  return `${s}${Number(v).toFixed(2)}${suffix}`;
}

function colorCls(v) {
  if (v == null) return "";
  return v > 0 ? "pos" : v < 0 ? "neg" : "";
}

// ── Init ──────────────────────────────────────────────────────────────────────
boot();
