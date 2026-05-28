#!/usr/bin/env python3
"""
build_eval_review.py — Generate a single-file HTML reviewer for eval_modules.py output.

Reads test-cases.jsonl + preds_modules_{name}_isolation.jsonl + preds_modules_{name}_cascade.jsonl
and emits a self-contained eval_review_{name}.html with both modes browseable.

Usage:
    uv run python tuning/rl/build_eval_review.py --checkpoint-name sft
    # Outputs: tuning/rl/eval_results/eval_review_sft.html

Open the HTML file directly in a browser — no server required.
"""

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
TEST_CASES_PATH = PROJECT_ROOT / "tuning" / "data" / "test-cases.jsonl"
EVAL_DIR = PROJECT_ROOT / "tuning" / "rl" / "eval_results"


def load_jsonl(path: Path) -> list:
    return [json.loads(l) for l in open(path) if l.strip()]


def build(checkpoint_name: str) -> Path:
    iso_path = EVAL_DIR / f"preds_modules_{checkpoint_name}_isolation.jsonl"
    cas_path = EVAL_DIR / f"preds_modules_{checkpoint_name}_cascade.jsonl"
    iso_summary = EVAL_DIR / f"summary_modules_{checkpoint_name}_isolation.json"
    cas_summary = EVAL_DIR / f"summary_modules_{checkpoint_name}_cascade.json"
    for p in [iso_path, cas_path, iso_summary, cas_summary]:
        assert p.exists(), f"Missing: {p}"

    test_cases = load_jsonl(TEST_CASES_PATH)
    isolation = load_jsonl(iso_path)
    cascade = load_jsonl(cas_path)
    iso_sum = json.loads(open(iso_summary).read())
    cas_sum = json.loads(open(cas_summary).read())

    # Index test-cases by test_id for input lookup
    cases_by_id = {c["test_id"]: c for c in test_cases}

    # Strip heavy fields from test_cases to keep HTML small
    def minimal_case(c: dict) -> dict:
        return {
            "test_id": c["test_id"],
            "category": c.get("category"),
            "persona": c.get("persona"),
            "profile": c.get("profile"),
            "user_message": c["user_message"],
            "form_state_before": c.get("form_state_before", {}),
            "conversation_history": c.get("conversation_history", []),
            "expected_action_types": c.get("expected_action_types", []),
            "expected_fields_set": c.get("expected_fields_set", []),
            "expected_output": c.get("expected_output", ""),
        }

    data = {
        "checkpoint_name": checkpoint_name,
        "cases": {tid: minimal_case(c) for tid, c in cases_by_id.items()},
        "isolation": isolation,
        "cascade": cascade,
        "iso_summary": iso_sum,
        "cas_summary": cas_sum,
    }

    out_path = EVAL_DIR / f"eval_review_{checkpoint_name}.html"
    html = HTML_TEMPLATE.replace(
        "__DATA_JSON__",
        json.dumps(data, ensure_ascii=False).replace("</", "<\\/"),
    )
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote: {out_path}")
    print(f"Size:  {out_path.stat().st_size / 1024:.0f} KB")
    print(f"Open:  file://{out_path}")
    return out_path


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Eval Review</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font: 13px -apple-system, system-ui, sans-serif; background: #f5f5f5; color: #222; }
  header { padding: 12px 18px; background: #1f2937; color: #fff; display: flex; align-items: center; gap: 18px; }
  header h1 { font-size: 16px; margin: 0; font-weight: 600; }
  header .tabs { display: flex; gap: 4px; }
  header .tab { padding: 6px 14px; background: #374151; color: #d1d5db; border: 0; border-radius: 4px; font-size: 13px; cursor: pointer; }
  header .tab.active { background: #3b82f6; color: #fff; }
  header .stats { margin-left: auto; font-size: 12px; color: #d1d5db; font-family: ui-monospace, Menlo, monospace; }

  .summary { padding: 10px 18px; background: #eef2ff; border-bottom: 1px solid #c7d2fe; font-size: 12px; font-family: ui-monospace, Menlo, monospace; white-space: pre; overflow-x: auto; }

  .main { display: grid; grid-template-columns: 440px 1fr; height: calc(100vh - 120px); }
  .list-panel { border-right: 1px solid #d1d5db; overflow-y: auto; background: #fff; }
  .filters { padding: 10px 12px; border-bottom: 1px solid #e5e7eb; position: sticky; top: 0; background: #fff; z-index: 2; }
  .filters input, .filters select { padding: 4px 8px; font-size: 12px; border: 1px solid #d1d5db; border-radius: 3px; margin: 2px; }
  .filters label { display: inline-flex; align-items: center; gap: 3px; margin: 2px 4px; font-size: 11px; color: #555; }

  .row { padding: 8px 12px; border-bottom: 1px solid #f0f0f0; cursor: pointer; display: grid; grid-template-columns: 38px 1fr auto; gap: 6px; align-items: center; }
  .row:hover { background: #eff6ff; }
  .row.selected { background: #dbeafe; border-left: 3px solid #3b82f6; padding-left: 9px; }
  .row .idx { font-family: ui-monospace, Menlo, monospace; font-size: 10px; color: #999; }
  .row .msg { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
  .row .badges { display: flex; gap: 3px; }
  .badge { display: inline-block; padding: 1px 5px; border-radius: 3px; font-size: 9px; font-weight: 600; text-transform: uppercase; }
  .badge.fmt-ok { background: #d1fae5; color: #065f46; }
  .badge.fmt-bad { background: #fee2e2; color: #991b1b; }
  .badge.cnt-ok { background: #dbeafe; color: #1e3a8a; }
  .badge.cnt-bad { background: #fef3c7; color: #92400e; }
  .badge.intent-ok { background: #d1fae5; color: #065f46; }
  .badge.intent-bad { background: #fee2e2; color: #991b1b; }
  .badge.module { background: #e5e7eb; color: #374151; }
  .badge.gather { background: #fde68a; color: #78350f; }
  .badge.clarify { background: #bae6fd; color: #0c4a6e; }
  .badge.converse { background: #ddd6fe; color: #5b21b6; }
  .badge.close { background: #fecaca; color: #7f1d1d; }
  .badge.review { background: #c7d2fe; color: #312e81; }
  .badge.small { font-size: 9px; padding: 1px 4px; }

  .detail-panel { overflow-y: auto; padding: 16px 22px; background: #fafafa; }
  .detail-panel h2 { font-size: 14px; margin: 0 0 4px; }
  .detail-panel h3 { font-size: 12px; margin: 16px 0 6px; color: #555; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }
  .detail-panel .meta { color: #666; font-size: 11px; margin-bottom: 6px; font-family: ui-monospace, Menlo, monospace; }

  .card { background: #fff; border: 1px solid #e5e7eb; border-radius: 5px; padding: 10px 12px; margin-bottom: 10px; }
  .card .title { font-size: 11px; font-weight: 600; text-transform: uppercase; color: #666; margin-bottom: 6px; letter-spacing: 0.5px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
  .card pre { margin: 0; padding: 8px; background: #f9fafb; border: 1px solid #f0f0f0; border-radius: 3px; font: 11px/1.5 ui-monospace, Menlo, monospace; white-space: pre-wrap; word-break: break-word; max-height: 400px; overflow-y: auto; }
  .card .raw-output { position: relative; }
  .card .raw-output .marker { color: #d946ef; font-weight: 700; }
  .card .raw-output .completed { color: #10b981; font-weight: 700; }

  details { margin-bottom: 8px; }
  details summary { cursor: pointer; font-size: 11px; color: #555; padding: 4px 0; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
  details[open] summary { margin-bottom: 6px; }

  .history-entry { padding: 6px 8px; margin-bottom: 4px; border-radius: 3px; font-size: 11px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
  .history-entry.user { background: #eff6ff; border-left: 3px solid #3b82f6; }
  .history-entry.assistant { background: #f3f4f6; border-left: 3px solid #6b7280; }
  .history-entry .role { font-size: 9px; font-weight: 700; text-transform: uppercase; color: #555; margin-bottom: 2px; }

  .metric-table { border-collapse: collapse; width: 100%; font-size: 11px; font-family: ui-monospace, Menlo, monospace; }
  .metric-table td { padding: 3px 8px; border-bottom: 1px solid #f0f0f0; }
  .metric-table td:first-child { color: #666; width: 200px; }
  .metric-table td.bool-true { color: #065f46; font-weight: 600; }
  .metric-table td.bool-false { color: #991b1b; font-weight: 600; }

  .empty { padding: 40px; text-align: center; color: #999; }
</style>
</head>
<body>
<header>
  <h1>Eval Review: <span id="ck-name"></span></h1>
  <div class="tabs">
    <button class="tab active" data-mode="isolation" onclick="switchMode('isolation')">Isolation (per-module, gold-gated)</button>
    <button class="tab" data-mode="cascade" onclick="switchMode('cascade')">Cascade (production, predicted-gated)</button>
  </div>
  <div class="stats" id="stats"></div>
</header>

<div class="summary" id="summary"></div>

<div class="main">
  <div class="list-panel">
    <div class="filters" id="filters"></div>
    <div id="list"></div>
  </div>
  <div class="detail-panel" id="detail">
    <div class="empty">Select a row on the left.</div>
  </div>
</div>

<script>
const DATA = __DATA_JSON__;
document.getElementById('ck-name').textContent = DATA.checkpoint_name;

let mode = 'isolation';
let selectedIdx = null;
const filterState = { module: '', gold: '', pred: '', fmt: '', cnt: '', q: '' };

// ─── Summary renderer ────────────────────────────────────────────────
function renderSummary() {
  const s = mode === 'isolation' ? DATA.iso_summary : DATA.cas_summary;
  let out = '';
  if (mode === 'isolation') {
    out += `[ISOLATION]  cases=${s.num_cases}  calls=${s.num_module_calls}  errors=${s.num_errors}  avg_latency=${s.avg_latency_s.toFixed(2)}s\n\n`;
    out += `  ${'Module'.padEnd(18)} ${'n'.padStart(4)}  ${'format_ok'.padStart(10)}  ${'content'.padStart(10)}  notes\n`;
    out += `  ${'─'.repeat(18)} ${'─'.repeat(4)}  ${'─'.repeat(10)}  ${'─'.repeat(10)}  ${'─'.repeat(60)}\n`;
    for (const m of ['intent_decider','text_responder','data_extractor','choice_builder','review_builder']) {
      const ms = s.per_module[m]; if (!ms) continue;
      const fmt = `${(ms.format_ok_rate*100).toFixed(1)}%`;
      let cnt = '', notes = '';
      if (m === 'intent_decider') { cnt = `${(ms.intent_accuracy*100).toFixed(1)}%`;
        const pg = ms.per_gold_intent_accuracy || {}; notes = Object.keys(pg).sort().map(k=>`${k}=${(pg[k]*100).toFixed(0)}%`).join(' '); }
      else if (m === 'text_responder') { cnt = `${(ms.content_ok_rate*100).toFixed(1)}%`; notes = `avg_len=${(ms.avg_response_length||0).toFixed(0)}`; }
      else if (m === 'data_extractor') { cnt = `${(ms.content_ok_rate*100).toFixed(1)}%`;
        notes = `loose_fmt=${(ms.format_ok_loose_rate*100).toFixed(1)}% pos_f1=${(ms.positive_f1*100).toFixed(1)}% neg_empty=${(ms.negative_empty_correct_rate*100).toFixed(1)}%`; }
      else if (m === 'choice_builder') { cnt = `${(ms.content_ok_rate*100).toFixed(1)}%`; notes = `avg_opts=${(ms.avg_options_count||0).toFixed(1)}`; }
      else if (m === 'review_builder') { cnt = `${(ms.content_ok_rate*100).toFixed(1)}%`; notes = `avg_content_len=${(ms.avg_content_length||0).toFixed(0)}`; }
      out += `  ${m.padEnd(18)} ${String(ms.n).padStart(4)}  ${fmt.padStart(10)}  ${cnt.padStart(10)}  ${notes}\n`;
    }
  } else {
    out += `[CASCADE]  turns=${s.num_turns}  errors=${s.num_errors}  avg_latency=${s.avg_latency_s.toFixed(2)}s\n`;
    out += `  Intent accuracy:        ${(s.intent_accuracy*100).toFixed(1)}%\n`;
    out += `  Intent format_ok:       ${(s.intent_format_ok_rate*100).toFixed(1)}%\n`;
    out += `  Turn format_ok (prod):  ${(s.turn_format_ok_rate*100).toFixed(1)}%\n`;
    out += `  Turn content_ok:        ${(s.turn_content_ok_rate*100).toFixed(1)}%\n\n`;
    out += `  Per-module (conditional on firing):\n`;
    for (const m of ['intent_decider','text_responder','data_extractor','choice_builder','review_builder']) {
      const ms = s.per_module_conditional[m]; if (!ms) continue;
      out += `  ${m.padEnd(18)} n=${String(ms.n_fired).padStart(4)}  fmt=${(ms.format_ok_rate*100).toFixed(1).padStart(5)}%  cnt=${(ms.content_ok_rate*100).toFixed(1).padStart(5)}%\n`;
    }
    out += `\n  Intent confusion (gold → predicted):\n`;
    for (const g of Object.keys(s.intent_confusion).sort()) {
      const c = s.intent_confusion[g];
      const total = Object.values(c).reduce((a,b)=>a+b,0);
      const pairs = Object.entries(c).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`${k}=${v}`).join(', ');
      out += `    ${g.padEnd(8)} (n=${total}): ${pairs}\n`;
    }
  }
  document.getElementById('summary').textContent = out;
}

// ─── Filters ─────────────────────────────────────────────────────────
function renderFilters() {
  const f = document.getElementById('filters');
  const intents = ['gather','clarify','close','converse','review'];
  if (mode === 'isolation') {
    const modules = ['intent_decider','text_responder','data_extractor','choice_builder','review_builder'];
    f.innerHTML = `
      <div>
        <input type="text" placeholder="search user_message…" id="f-q" oninput="setFilter('q', this.value)" value="${filterState.q}">
      </div>
      <div>
        <label>module <select id="f-module" onchange="setFilter('module', this.value)">
          <option value="">(all)</option>${modules.map(m=>`<option value="${m}">${m}</option>`).join('')}
        </select></label>
        <label>gold <select id="f-gold" onchange="setFilter('gold', this.value)">
          <option value="">(all)</option>${intents.map(i=>`<option value="${i}">${i}</option>`).join('')}
        </select></label>
        <label>format <select id="f-fmt" onchange="setFilter('fmt', this.value)">
          <option value="">(all)</option><option value="pass">pass</option><option value="fail">fail</option>
        </select></label>
        <label>content <select id="f-cnt" onchange="setFilter('cnt', this.value)">
          <option value="">(all)</option><option value="pass">pass</option><option value="fail">fail</option>
        </select></label>
      </div>`;
  } else {
    f.innerHTML = `
      <div>
        <input type="text" placeholder="search user_message…" id="f-q" oninput="setFilter('q', this.value)" value="${filterState.q}">
      </div>
      <div>
        <label>gold <select id="f-gold" onchange="setFilter('gold', this.value)">
          <option value="">(all)</option>${intents.map(i=>`<option value="${i}">${i}</option>`).join('')}
        </select></label>
        <label>predicted <select id="f-pred" onchange="setFilter('pred', this.value)">
          <option value="">(all)</option>${intents.map(i=>`<option value="${i}">${i}</option>`).join('')}
          <option value="INVALID">INVALID</option>
        </select></label>
        <label>turn format <select id="f-fmt" onchange="setFilter('fmt', this.value)">
          <option value="">(all)</option><option value="pass">pass</option><option value="fail">fail</option>
        </select></label>
        <label>turn content <select id="f-cnt" onchange="setFilter('cnt', this.value)">
          <option value="">(all)</option><option value="pass">pass</option><option value="fail">fail</option>
        </select></label>
      </div>`;
  }
  // Restore current values
  for (const k of ['module','gold','pred','fmt','cnt']) {
    const el = document.getElementById(`f-${k}`);
    if (el && filterState[k]) el.value = filterState[k];
  }
}

function setFilter(key, val) { filterState[key] = val; renderList(); }

// ─── List ────────────────────────────────────────────────────────────
function getRows() {
  if (mode === 'isolation') {
    return DATA.isolation.filter(r => {
      if (filterState.module && r.module !== filterState.module) return false;
      if (filterState.gold && r.gold_intent !== filterState.gold) return false;
      const fmt = r.metrics && r.metrics.format_ok;
      const cnt = r.metrics && (r.metrics.content_ok ?? r.metrics.intent_correct);
      if (filterState.fmt === 'pass' && !fmt) return false;
      if (filterState.fmt === 'fail' && fmt) return false;
      if (filterState.cnt === 'pass' && !cnt) return false;
      if (filterState.cnt === 'fail' && cnt) return false;
      if (filterState.q && !r.user_message.toLowerCase().includes(filterState.q.toLowerCase())) return false;
      return true;
    });
  } else {
    const VOCAB = new Set(['gather','converse','clarify','close','review']);
    return DATA.cascade.filter(r => {
      if (filterState.gold && r.gold_intent !== filterState.gold) return false;
      if (filterState.pred) {
        if (filterState.pred === 'INVALID') { if (VOCAB.has(r.predicted_intent)) return false; }
        else if (r.predicted_intent !== filterState.pred) return false;
      }
      if (filterState.fmt === 'pass' && !r.turn_format_ok) return false;
      if (filterState.fmt === 'fail' && r.turn_format_ok) return false;
      if (filterState.cnt === 'pass' && !r.turn_content_ok) return false;
      if (filterState.cnt === 'fail' && r.turn_content_ok) return false;
      if (filterState.q && !r.user_message.toLowerCase().includes(filterState.q.toLowerCase())) return false;
      return true;
    });
  }
}

function renderList() {
  const rows = getRows();
  document.getElementById('stats').textContent = `showing ${rows.length} rows`;
  const list = document.getElementById('list');
  if (rows.length === 0) { list.innerHTML = '<div class="empty">No matches.</div>'; return; }
  list.innerHTML = rows.slice(0, 2000).map((r, i) => {
    const orig = mode === 'isolation' ? DATA.isolation.indexOf(r) : DATA.cascade.indexOf(r);
    const selCls = orig === selectedIdx ? 'selected' : '';
    if (mode === 'isolation') {
      const m = r.metrics || {};
      const fmt = m.format_ok ? 'fmt-ok' : 'fmt-bad';
      const cntKey = 'content_ok' in m ? m.content_ok : m.intent_correct;
      const cnt = cntKey ? 'cnt-ok' : 'cnt-bad';
      const gold = r.gold_intent || '?';
      return `<div class="row ${selCls}" onclick="select(${orig})">
        <span class="idx">${String(r.case_idx).padStart(3,'0')}</span>
        <span class="msg">
          <span class="badge module">${r.module.replace('_','_​').substring(0,3)}</span>
          <span class="badge ${gold} small">${gold}</span>
          ${r.user_message}
        </span>
        <span class="badges"><span class="badge ${fmt}">F</span><span class="badge ${cnt}">C</span></span>
      </div>`;
    } else {
      const gold = r.gold_intent, pred = r.predicted_intent || '?';
      const fmt = r.turn_format_ok ? 'fmt-ok' : 'fmt-bad';
      const cnt = r.turn_content_ok ? 'cnt-ok' : 'cnt-bad';
      const iclass = r.intent_correct ? 'intent-ok' : 'intent-bad';
      return `<div class="row ${selCls}" onclick="select(${orig})">
        <span class="idx">${String(r.case_idx).padStart(3,'0')}</span>
        <span class="msg">
          <span class="badge ${gold} small">${gold}</span>
          <span class="badge ${iclass} small">→ ${pred||'—'}</span>
          ${r.user_message}
        </span>
        <span class="badges"><span class="badge ${fmt}">F</span><span class="badge ${cnt}">C</span></span>
      </div>`;
    }
  }).join('');
  if (rows.length > 2000) list.innerHTML += `<div class="empty">(showing first 2000 of ${rows.length})</div>`;
}

function select(origIdx) {
  selectedIdx = origIdx;
  renderList();
  renderDetail();
}

// ─── Detail ──────────────────────────────────────────────────────────
function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function highlightMarkers(raw) {
  if (!raw) return '';
  return escapeHtml(raw).replace(
    /\[\[\s*##\s*(\w+)\s*##\s*\]\]/g,
    (_, n) => n === 'completed'
      ? `<span class="completed">[[ ## ${n} ## ]]</span>`
      : `<span class="marker">[[ ## ${n} ## ]]</span>`
  );
}

function renderContextCard(testCase) {
  if (!testCase) return '';
  const state = testCase.form_state_before || {};
  const history = testCase.conversation_history || [];
  const stateHtml = Object.keys(state).length
    ? `<pre>${escapeHtml(JSON.stringify(state, null, 2))}</pre>`
    : '<div style="color:#999;font-size:11px;">(empty)</div>';
  const histHtml = history.length
    ? history.map(h => `<div class="history-entry ${h.role}"><div class="role">${h.role}</div>${escapeHtml(h.content)}</div>`).join('')
    : '<div style="color:#999;font-size:11px;">(no prior turns)</div>';
  return `
    <details>
      <summary>Filled fields (${Object.keys(state).length})</summary>
      ${stateHtml}
    </details>
    <details>
      <summary>Conversation history (${history.length} turns)</summary>
      ${histHtml}
    </details>`;
}

function renderMetrics(metrics) {
  if (!metrics) return '<div style="color:#999;">no metrics</div>';
  const rows = Object.entries(metrics)
    .filter(([k]) => !['pred_ids','pred_vals'].includes(k))
    .map(([k, v]) => {
      let tdClass = '', disp;
      if (typeof v === 'boolean') { tdClass = v ? 'bool-true' : 'bool-false'; disp = v ? '✓ true' : '✗ false'; }
      else if (typeof v === 'number') disp = Number.isInteger(v) ? v : v.toFixed(3);
      else disp = typeof v === 'object' ? JSON.stringify(v) : String(v);
      return `<tr><td>${k}</td><td class="${tdClass}">${escapeHtml(disp)}</td></tr>`;
    }).join('');
  return `<table class="metric-table">${rows}</table>`;
}

function renderModuleCard(moduleName, raw, metrics, intentInput) {
  const fmtOk = metrics && metrics.format_ok;
  const cntOk = metrics && ('content_ok' in metrics ? metrics.content_ok : metrics.intent_correct);
  const fmtBadge = `<span class="badge ${fmtOk ? 'fmt-ok' : 'fmt-bad'}">format ${fmtOk ? 'ok' : 'fail'}</span>`;
  const cntBadge = metrics ? `<span class="badge ${cntOk ? 'cnt-ok' : 'cnt-bad'}">content ${cntOk ? 'ok' : 'fail'}</span>` : '';
  const intentRow = intentInput ? `<div style="font-size:11px;color:#666;margin-bottom:6px;"><b>intent input:</b> <span class="badge ${intentInput} small">${intentInput}</span></div>` : '';
  return `
    <div class="card">
      <div class="title">${moduleName} ${fmtBadge} ${cntBadge}</div>
      ${intentRow}
      <div style="font-size:10px;color:#888;margin-bottom:4px;">raw_output:</div>
      <pre class="raw-output">${highlightMarkers(raw)}</pre>
      <details style="margin-top:6px;"><summary>metrics</summary>${renderMetrics(metrics)}</details>
    </div>`;
}

function renderDetail() {
  const d = document.getElementById('detail');
  if (selectedIdx == null) { d.innerHTML = '<div class="empty">Select a row on the left.</div>'; return; }
  const r = mode === 'isolation' ? DATA.isolation[selectedIdx] : DATA.cascade[selectedIdx];
  const tc = DATA.cases[r.test_id];
  const userMsg = tc ? tc.user_message : r.user_message;

  let html = `<h2>${escapeHtml(r.test_id)}</h2>`;
  html += `<div class="meta">category=${r.category || '?'} · persona=${tc?.persona || '?'} · profile=${tc?.profile || '?'} · case_idx=${r.case_idx}</div>`;

  if (mode === 'cascade') {
    const gcls = r.intent_correct ? 'intent-ok' : 'intent-bad';
    html += `<div style="margin-bottom:10px;">
      <span class="badge ${r.gold_intent} small">gold: ${r.gold_intent}</span>
      <span class="badge ${gcls} small">predicted: ${r.predicted_intent || '(invalid)'}</span>
      <span class="badge ${r.turn_format_ok?'fmt-ok':'fmt-bad'}">turn format ${r.turn_format_ok?'ok':'fail'}</span>
      <span class="badge ${r.turn_content_ok?'cnt-ok':'cnt-bad'}">turn content ${r.turn_content_ok?'ok':'fail'}</span>
      <span class="badge module small">fired: ${r.fired_modules.join(', ')}</span>
    </div>`;
  } else {
    html += `<div style="margin-bottom:10px;">
      <span class="badge module">module: ${r.module}</span>
      <span class="badge ${r.gold_intent} small">gold: ${r.gold_intent}</span>
    </div>`;
  }

  // Inputs collapsed by default; Model Output is always shown below.
  html += `<details class="inputs-block"><summary>Inputs (user_message, context, expected output)</summary>`;
  html += `<div class="card"><div class="title">user_message</div><pre>${escapeHtml(userMsg)}</pre></div>`;
  html += `<div class="card"><div class="title">context (form state + recent history)</div>${renderContextCard(tc)}</div>`;
  if (tc && tc.expected_output) {
    html += `<details><summary>Expected assistant output (full)</summary><div class="card"><pre>${escapeHtml(tc.expected_output)}</pre></div></details>`;
  }
  html += `</details>`;

  html += `<h3>Model Output</h3>`;
  if (mode === 'isolation') {
    // Single-module view; intent input only for text_responder
    const intentInput = r.module === 'text_responder' ? r.gold_intent : null;
    html += renderModuleCard(r.module, r.raw_output, r.metrics, intentInput);
  } else {
    // Multi-module turn view
    for (const m of ['intent_decider','text_responder','data_extractor','choice_builder','review_builder']) {
      const res = r.module_results[m];
      if (!res) continue;
      const intentInput = m === 'text_responder' ? r.predicted_intent : null;
      html += renderModuleCard(m, res.raw_output, res.metrics, intentInput);
    }
  }

  d.innerHTML = html;
  d.scrollTop = 0;
}

// ─── Mode switch ─────────────────────────────────────────────────────
function switchMode(m) {
  mode = m;
  selectedIdx = null;
  // Reset module filter (not applicable in cascade)
  if (m === 'cascade') filterState.module = '';
  for (const btn of document.querySelectorAll('.tab')) btn.classList.toggle('active', btn.dataset.mode === m);
  renderSummary();
  renderFilters();
  renderList();
  renderDetail();
}

// ─── Init ────────────────────────────────────────────────────────────
renderSummary();
renderFilters();
renderList();
</script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint-name", default="sft")
    args = parser.parse_args()
    build(args.checkpoint_name)


if __name__ == "__main__":
    main()
