import {element} from './client.js';

function zone(target, className, text) {
  const box = element('div', undefined, {class:className});
  if (text) box.append(element('span',text));
  target.append(box);
  return box;
}

function fill(layer, value, max, label) {
  const mark = zone(layer, 'mark-piece', label);
  mark.style.setProperty('--part', `${Math.max(0,Math.min(100,100*value/Math.max(1,max)))}%`);
  return mark;
}

export function visualize(report, selected) {
  const target = document.querySelector('#visual');
  const row = report.cases?.find(item=>item.case===selected && item.measure);
  target.replaceChildren();
  if (!row) { target.append(element('p','该分组暂无计算值')); return; }
  const {evidence:e, value, expected, unit} = row.measure;
  render(target, e, value, expected, unit);
}

function render(target,e,value,expected,unit) {
  const stages=zone(target,'freight-tiers');
  for(const [i,fee] of [1,3,5].entries()) {
    const mins=e[`tier_${i+1}_min`];
    const card=zone(stages,'freight-rate',`档 ${i+1} · ${fee} 分/分钟`);
    card.append(element('strong',`${mins} min`));
  }
  zone(target,'freight-charge',`停时费用 ${value} 分`);
}
