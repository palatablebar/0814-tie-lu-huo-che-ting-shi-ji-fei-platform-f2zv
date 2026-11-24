import {element, pretty} from './client.js';

const labels = {READY:'通过', MISMATCH:'差异待复核', PENDING:'待复核', APPROVED:'已签发', HELD:'已暂缓',
  ACCEPTED:'采信', REJECTED:'隔离', BLANK_LINE:'空白行', HEADER_REPLAY:'重复表头',
  INVALID_STAY:'停时段无效', EXPECTED_ONE_STAY:'停时记录缺失'};
const headers = ['业务分组', '输入行', '计算值', '参考值', '判定', '组签批'];
const ledgerHeaders = ['源行', '记录键', '业务组', '处置', '原因码', '归属'];
const dispositionLabels = {
  ACCEPTED:'采信', REJECTED:'隔离', BLANK_LINE:'空白行', HEADER_REPLAY:'重复表头'
};

export function badge(status) {
  return element('span', labels[status] || status, {class:'badge', 'data-result':status, title: status});
}

function decisionOf(batch, caseId) {
  return batch?.group_decisions?.find(item => item.case_id === caseId) || null;
}

export function renderGate(report) {
  const banner = document.querySelector('#gate-banner');
  const gate = report.signoff?.gate;
  if (!gate) { banner.hidden = true; return; }
  banner.hidden = false;
  banner.dataset.open = String(gate.open);
  if (gate.open) {
    banner.textContent = `签批闸门开放：台账 ${gate.ledger_lines}/${gate.input_lines} 行守恒，可按组签批`;
  } else {
    const reason = gate.reasons.map(code => labels[code] || code).join('、');
    banner.textContent = `整批等待补齐：${reason}（不可归属条目 ${gate.unattributed.length} 条）`;
  }
}

export function snapshot(report, selected, stage, batch = null) {
  const stats = report.intake;
  document.querySelector('[data-metric="input"]').textContent = stats.input;
  document.querySelector('[data-metric="accepted"]').textContent = stats.accepted;
  document.querySelector('[data-metric="isolated"]').textContent = stats.rejected;
  document.querySelector('[data-metric="cases"]').textContent = report.cases?.length ?? '—';
  renderGate(report);
  const table = document.querySelector('#rows');
  table.replaceChildren();
  const head = element('tr');
  const body = table.createTBody();
  if (stage === 'intake') {
    head.append(...ledgerHeaders.map(title => element('th', title, {scope:'col'})));
    for (const item of report.signoff?.ledger || []) {
      const tr = body.insertRow();
      const attribution = item.disposition === 'REJECTED'
        ? (item.attributable === true ? `归属 ${item.group}`
           : item.attributable === false ? '无法归属' : '待分组')
        : '—';
      tr.append(...[item.line, item.record ?? '—', item.case ?? '—',
        dispositionLabels[item.disposition] || item.disposition,
        item.reason, attribution].map(value => element('td', String(value))));
    }
  } else {
    head.append(...headers.map(title => element('th', title, {scope:'col'})));
    for (const row of report.cases || []) {
      const tr = body.insertRow();
      const button = element('button',row.case,{type:'button','data-case':row.case,'aria-pressed':String(row.case===selected)});
      tr.insertCell().append(button);
      [row.records.length, row.measure?.value ?? '—', row.measure?.expected ?? '—'].forEach(value=>tr.insertCell().textContent=value);
      tr.insertCell().append(badge(row.status));
      const decision = decisionOf(batch, row.case);
      tr.insertCell().append(decision ? badge(decision.status) : element('span','待裁定',{class:'badge','data-result':'PENDING'}));
    }
  }
  table.createTHead().append(head);
  const picked = report.cases?.find(row=>row.case===selected);
  document.querySelector('#detail-title').textContent = picked ? `分组 ${picked.case}` : '采信摘要';
  const shown = picked ? picked.measure?.evidence ?? picked.prep?.details ?? {原因:picked.status} : stats.reasons;
  document.querySelector('#detail').textContent = pretty(shown);
  document.querySelector('#counts').textContent = report.balance ? `行数 ${report.balance.accounted}/${report.balance.input} · ${report.balance.ready} 组通过` : `采信 ${stats.accepted} 行 · 隔离 ${stats.rejected} 行`;
  renderDecisionForm(report, selected, batch);
}

function renderDecisionForm(report, selected, batch) {
  const form = document.querySelector('#decision');
  const group = report.signoff?.groups.find(item => item.case === selected);
  if (!group || !batch) { form.hidden = true; return; }
  const decision = decisionOf(batch, selected);
  const gateOpen = report.signoff.gate.open;
  form.hidden = false;
  const meta = document.querySelector('#decision-meta');
  if (decision) {
    meta.textContent = `已${decision.status === 'APPROVED' ? '签发' : '暂缓'} · r${decision.revision} · 采用 ${decision.scope.record_count} 条记录`;
  } else if (!gateOpen) {
    meta.textContent = `闸门关闭：${report.signoff.gate.reasons.join('、')}，暂不能裁定`;
  } else if (!group.eligible) {
    meta.textContent = `不能签发：${group.block_reasons.map(code => labels[code] || code).join('、')}；可填写暂缓意见`;
  } else {
    meta.textContent = `可签发：采用 ${group.scope.record_count} 条采信记录，异常 ${group.exceptions.length} 条`;
  }
  const finalized = Boolean(decision) || batch.status === 'APPROVED' || !gateOpen;
  form.elements.note.value = decision?.note || '';
  for (const button of form.querySelectorAll('button')) {
    button.disabled = finalized || (button.value === 'APPROVED' && !group.eligible);
  }
}

export function history(items, active) {
  const target = document.querySelector('#history');
  target.replaceChildren();
  for (const run of items) {
    const button = element('button', run.id.slice(0,10), {'data-run':run.id,'aria-pressed':String(run.id===active),type:'button'});
    const item = element('li');
    item.append(button, badge(run.status));
    target.append(item);
  }
  if (!items.length) target.append(element('li','尚无执行批次'));
}
