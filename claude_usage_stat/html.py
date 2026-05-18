"""生成自包含、可交互的 HTML 仪表盘(无外部依赖,可离线打开)。"""
import json
import os

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Code 用量统计</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: -apple-system, "PingFang SC", "Segoe UI", sans-serif;
    background:#0f1115; color:#e6e8eb; font-size:14px; }
  .wrap { max-width:1180px; margin:0 auto; padding:28px 22px 60px; }
  h1 { font-size:21px; margin:0 0 4px; }
  .sub { color:#8b929e; font-size:12.5px; margin-bottom:22px; }
  .controls { display:flex; flex-wrap:wrap; gap:10px; align-items:center;
    background:#171a21; border:1px solid #252a34; border-radius:10px; padding:12px 14px; margin-bottom:20px; }
  .controls label { color:#8b929e; font-size:12px; }
  input[type=date] { background:#0f1115; color:#e6e8eb; border:1px solid #2d333f;
    border-radius:6px; padding:5px 8px; font-size:13px; }
  .btn { background:#222630; color:#cfd3da; border:1px solid #2d333f; border-radius:6px;
    padding:5px 11px; font-size:12.5px; cursor:pointer; }
  .btn:hover { background:#2b303c; }
  .btn.active { background:#3b6fe0; border-color:#3b6fe0; color:#fff; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(155px,1fr)); gap:12px; margin-bottom:24px; }
  .card { background:#171a21; border:1px solid #252a34; border-radius:10px; padding:14px 16px; }
  .card .k { color:#8b929e; font-size:11.5px; text-transform:uppercase; letter-spacing:.04em; }
  .card .v { font-size:23px; font-weight:600; margin-top:5px; }
  .card .v small { font-size:13px; color:#8b929e; font-weight:400; }
  .panel { background:#171a21; border:1px solid #252a34; border-radius:10px; padding:16px 18px; margin-bottom:20px; }
  .panel h2 { font-size:14px; margin:0 0 14px; color:#cfd3da; }
  .chart { display:flex; align-items:flex-end; gap:3px; height:180px; overflow-x:auto; padding-bottom:4px; }
  .bar { flex:1 0 14px; min-width:9px; background:#3b6fe0; border-radius:3px 3px 0 0;
    position:relative; transition:background .12s; }
  .bar:hover { background:#5b8bff; }
  .bar .tip { display:none; position:absolute; bottom:100%; left:50%; transform:translateX(-50%);
    background:#000; border:1px solid #2d333f; border-radius:6px; padding:6px 9px; font-size:11.5px;
    white-space:nowrap; z-index:5; margin-bottom:5px; }
  .bar:hover .tip { display:block; }
  .axis { display:flex; gap:3px; margin-top:5px; }
  .axis span { flex:1 0 14px; min-width:9px; text-align:center; font-size:9px; color:#5c6370;
    overflow:hidden; white-space:nowrap; }
  table { width:100%; border-collapse:collapse; }
  th, td { text-align:left; padding:8px 10px; border-bottom:1px solid #232833; font-size:13px; }
  th { color:#8b929e; font-size:11px; text-transform:uppercase; letter-spacing:.04em; cursor:pointer; }
  th:hover { color:#cfd3da; }
  td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
  tr:hover td { background:#1c2028; }
  .mini { height:6px; background:#222630; border-radius:3px; overflow:hidden; margin-top:3px; }
  .mini > i { display:block; height:100%; background:#3b6fe0; }
  .ttl { color:#e6e8eb; }
  .dim { color:#8b929e; font-size:11.5px; }
  .pill { display:inline-block; background:#222630; border-radius:4px; padding:1px 6px;
    font-size:11px; color:#9aa2af; margin-left:6px; }
  .breakdown { display:flex; height:26px; border-radius:6px; overflow:hidden; margin-bottom:8px; }
  .breakdown > div { display:flex; align-items:center; justify-content:center; font-size:11px; }
  .lg { display:flex; flex-wrap:wrap; gap:14px; font-size:12px; color:#8b929e; }
  .lg i { display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:5px; vertical-align:middle; }
  .empty { color:#8b929e; padding:18px; text-align:center; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Claude Code 用量统计</h1>
  <div class="sub" id="meta"></div>

  <div class="controls">
    <label>从</label><input type="date" id="from">
    <label>到</label><input type="date" id="to">
    <button class="btn" data-range="1">今天</button>
    <button class="btn" data-range="7">近 7 天</button>
    <button class="btn" data-range="30">近 30 天</button>
    <button class="btn" data-range="all">全部</button>
  </div>

  <div class="cards" id="cards"></div>

  <div class="panel">
    <h2>Token 构成</h2>
    <div class="breakdown" id="bd"></div>
    <div class="lg">
      <span><i style="background:#3b6fe0"></i>输入</span>
      <span><i style="background:#e0913b"></i>输出</span>
      <span><i style="background:#3ba55c"></i>缓存读</span>
      <span><i style="background:#8b5cf6"></i>缓存写</span>
    </div>
  </div>

  <div class="panel">
    <h2>每日用量(柱高=总 token,悬停看明细)</h2>
    <div class="chart" id="chart"></div>
    <div class="axis" id="axis"></div>
  </div>

  <div class="panel">
    <h2>消耗最多的项目</h2>
    <table id="projTable"><thead><tr>
      <th>项目</th><th class="num">Token</th><th class="num">花费(估)</th>
      <th class="num">Session 数</th><th class="num">占比</th>
    </tr></thead><tbody></tbody></table>
  </div>

  <div class="panel">
    <h2>消耗最多的 Session</h2>
    <table id="sessTable"><thead><tr>
      <th>Session</th><th>项目</th><th class="num">Token</th><th class="num">花费(估)</th>
    </tr></thead><tbody></tbody></table>
  </div>
</div>

<script>
const DAILY = __DAILY__;
const SESSIONS = __SESSIONS__;

function fmt(n){
  if(n>=1e9) return (n/1e9).toFixed(2)+'B';
  if(n>=1e6) return (n/1e6).toFixed(2)+'M';
  if(n>=1e3) return (n/1e3).toFixed(1)+'k';
  return String(n);
}
function usd(n){ return '$'+n.toFixed(n<10?2:0); }

const allDates = DAILY.map(r=>r.d).sort();
const minD = allDates[0], maxD = allDates[allDates.length-1];

const fromEl = document.getElementById('from');
const toEl = document.getElementById('to');
fromEl.min = toEl.min = minD; fromEl.max = toEl.max = maxD;

let sortProj = {k:'tok', dir:-1};
let sortSess = {k:'tok', dir:-1};

function setRange(days){
  if(days==='all'){ fromEl.value=minD; toEl.value=maxD; }
  else {
    const start = new Date(maxD);
    start.setDate(start.getDate()-(days-1));
    toEl.value = maxD;
    fromEl.value = start.toISOString().slice(0,10);
  }
  render();
}

function render(){
  const f = fromEl.value, t = toEl.value;
  const rows = DAILY.filter(r => r.d>=f && r.d<=t);

  let I=0,O=0,CR=0,CW=0,COST=0;
  const byDay = {}, byProj = {}, bySess = {};
  for(const r of rows){
    I+=r.i; O+=r.o; CR+=r.cr; CW+=r.cw; COST+=r.cost;
    const tok = r.i+r.o+r.cr+r.cw;
    if(!byDay[r.d]) byDay[r.d]={tok:0,cost:0};
    byDay[r.d].tok+=tok; byDay[r.d].cost+=r.cost;
    const proj = (SESSIONS[r.sid]||{}).proj || '(未知)';
    if(!byProj[proj]) byProj[proj]={tok:0,cost:0,sids:new Set()};
    byProj[proj].tok+=tok; byProj[proj].cost+=r.cost; byProj[proj].sids.add(r.sid);
    if(!bySess[r.sid]) bySess[r.sid]={tok:0,cost:0};
    bySess[r.sid].tok+=tok; bySess[r.sid].cost+=r.cost;
  }
  const TOTAL = I+O+CR+CW;
  const nDays = Object.keys(byDay).length || 1;

  document.getElementById('cards').innerHTML = [
    ['总 Token', fmt(TOTAL)],
    ['花费(估)', usd(COST)],
    ['活跃天数', nDays+' <small>天</small>'],
    ['日均 Token', fmt(Math.round(TOTAL/nDays))],
    ['项目数', Object.keys(byProj).length],
    ['Session 数', Object.keys(bySess).length],
  ].map(([k,v])=>`<div class="card"><div class="k">${k}</div><div class="v">${v}</div></div>`).join('');

  const seg=[['#3b6fe0',I,'输入'],['#e0913b',O,'输出'],['#3ba55c',CR,'缓存读'],['#8b5cf6',CW,'缓存写']];
  document.getElementById('bd').innerHTML = TOTAL? seg.map(([c,v])=>{
    const p=v/TOTAL*100;
    return `<div style="background:${c};width:${p}%" title="${fmt(v)} (${p.toFixed(1)}%)">${p>7?p.toFixed(0)+'%':''}</div>`;
  }).join('') : '<div class="empty">该区间无数据</div>';

  const days = Object.keys(byDay).sort();
  const maxTok = Math.max(1,...days.map(d=>byDay[d].tok));
  document.getElementById('chart').innerHTML = days.length? days.map(d=>{
    const o=byDay[d]; const h=Math.max(2,o.tok/maxTok*170);
    return `<div class="bar" style="height:${h}px"><div class="tip">${d}<br>${fmt(o.tok)} tok · ${usd(o.cost)}</div></div>`;
  }).join('') : '<div class="empty">该区间无数据</div>';
  document.getElementById('axis').innerHTML = days.map((d,i)=>{
    const lbl = (days.length<=14 || i%Math.ceil(days.length/14)===0) ? d.slice(5) : '';
    return `<span>${lbl}</span>`;
  }).join('');

  let projArr = Object.entries(byProj).map(([name,o])=>({
    name, tok:o.tok, cost:o.cost, sess:o.sids.size}));
  projArr.sort((a,b)=> sortProj.dir*((a[sortProj.k]>b[sortProj.k])?1:(a[sortProj.k]<b[sortProj.k])?-1:0));
  const projMax = Math.max(1,...projArr.map(p=>p.tok));
  document.querySelector('#projTable tbody').innerHTML = projArr.length? projArr.map(p=>`
    <tr><td><span class="ttl">${esc(p.name)}</span>
      <div class="mini"><i style="width:${p.tok/projMax*100}%"></i></div></td>
    <td class="num">${fmt(p.tok)}</td><td class="num">${usd(p.cost)}</td>
    <td class="num">${p.sess}</td><td class="num">${(p.tok/TOTAL*100).toFixed(1)}%</td></tr>`).join('')
    : '<tr><td colspan="5" class="empty">该区间无数据</td></tr>';

  let sessArr = Object.entries(bySess).map(([sid,o])=>{
    const s = SESSIONS[sid]||{};
    return {sid, tok:o.tok, cost:o.cost, title:s.title||'(无标题)', proj:s.proj||'(未知)', branch:s.branch||''};
  });
  sessArr.sort((a,b)=> sortSess.dir*((a[sortSess.k]>b[sortSess.k])?1:(a[sortSess.k]<b[sortSess.k])?-1:0));
  document.querySelector('#sessTable tbody').innerHTML = sessArr.slice(0,40).map(s=>`
    <tr><td><span class="ttl">${esc(s.title)}</span>
      <div class="dim">${s.sid.slice(0,8)}${s.branch?' · '+esc(s.branch):''}</div></td>
    <td>${esc(s.proj)}</td>
    <td class="num">${fmt(s.tok)}</td><td class="num">${usd(s.cost)}</td></tr>`).join('')
    || '<tr><td colspan="4" class="empty">该区间无数据</td></tr>';

  document.getElementById('meta').textContent =
    `数据范围 ${minD} ~ ${maxD} · 共 ${Object.keys(SESSIONS).length} 个 session · `+
    `花费为按官方 API 标准价的等价估算,非订阅实际计费`;
}
function esc(s){ return (s+'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

document.querySelectorAll('[data-range]').forEach(b=>{
  b.onclick=()=>{ document.querySelectorAll('[data-range]').forEach(x=>x.classList.remove('active'));
    b.classList.add('active'); setRange(b.dataset.range==='all'?'all':+b.dataset.range); };
});
fromEl.onchange=toEl.onchange=()=>{ document.querySelectorAll('[data-range]').forEach(x=>x.classList.remove('active')); render(); };

document.querySelectorAll('#projTable th').forEach((th,i)=>{
  const keys=['name','tok','cost','sess','tok'];
  th.onclick=()=>{ const k=keys[i]; sortProj.dir = (sortProj.k===k)? -sortProj.dir : -1; sortProj.k=k; render(); };
});
document.querySelectorAll('#sessTable th').forEach((th,i)=>{
  const keys=['title','proj','tok','cost'];
  th.onclick=()=>{ const k=keys[i]; sortSess.dir = (sortSess.k===k)? -sortSess.dir : -1; sortSess.k=k; render(); };
});

fromEl.value=minD; toEl.value=maxD;
document.querySelector('[data-range="all"]').classList.add('active');
render();
</script>
</body>
</html>
"""


def generate(sessions: dict, daily: list, out_path: str) -> str:
    """把数据嵌入 HTML 模板并写盘,返回绝对路径。"""
    html_out = (
        HTML_TEMPLATE
        .replace("__DAILY__", json.dumps(daily, ensure_ascii=False))
        .replace("__SESSIONS__", json.dumps(sessions, ensure_ascii=False))
    )
    out_path = os.path.abspath(os.path.expanduser(out_path))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html_out)
    return out_path
