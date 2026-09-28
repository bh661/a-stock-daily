#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 A股选股 xlsx 转成一个自包含的 HTML 页面（用于 Cowork artifact 发布）。

用法:
    python3 build_report_site.py <xlsx路径> <输出html路径> [基准交易日YYYYMMDD] [版本标签]
    python3 build_report_site.py --empty <输出html路径> [提示文字]

设计要点:
  * 读 xlsx 的每个 sheet，连同单元格底色/字色/加粗一起搬到网页，保持和表格一致的视觉语言
  * 输出单文件 HTML，无外部依赖（artifact 沙箱只允许极少数 CDN，这里干脆不用）
  * 表格支持：搜索、点击表头排序、前两列冻结、表头吸顶
"""
import sys, json, html, datetime

def argb(c):
    """openpyxl 的颜色对象 -> #RRGGBB，拿不到或为白色/黑色时返回 None"""
    if c is None:
        return None
    v = getattr(c, 'rgb', None)
    if not isinstance(v, str) or len(v) < 6:
        return None
    v = v[-6:].upper()
    return '#' + v

def fmt(v, nf):
    if v is None:
        return ''
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.strftime('%Y-%m-%d')
    if isinstance(v, bool):
        return '✓' if v else ''
    if isinstance(v, (int, float)):
        nf = nf or ''
        if '#,##0.0' in nf:
            return f'{v:,.1f}'
        if '#,##0' in nf:
            return f'{v:,.0f}'
        if '0.000' in nf:
            return f'{v:.3f}'
        if '0.00' in nf:
            return f'{v:.2f}'
        if '0.0' in nf:
            return f'{v:.1f}'
        if isinstance(v, float) and v == int(v):
            return str(int(v))
        return str(v)
    return str(v)

def sheet_to_obj(ws):
    styles, sidx = [], {}

    def style_id(cell):
        bg = fc = None
        try:
            f = cell.fill
            if f is not None and f.patternType == 'solid':
                bg = argb(f.fgColor)
                if bg in ('#FFFFFF', '#000000'):
                    bg = None
        except Exception:
            pass
        try:
            fc = argb(cell.font.color) if cell.font and cell.font.color else None
            if fc == '#000000':
                fc = None
        except Exception:
            pass
        bold = bool(cell.font and cell.font.bold)
        try:
            align = cell.alignment.horizontal if cell.alignment else None
        except Exception:
            align = None
        key = (bg, fc, bold, align)
        if key == (None, None, False, None):
            return 0
        if key not in sidx:
            sidx[key] = len(styles) + 1
            styles.append({'bg': bg, 'fc': fc, 'b': bold, 'a': align})
        return sidx[key]

    rows_iter = ws.iter_rows()
    try:
        header_cells = next(rows_iter)
    except StopIteration:
        return {'name': ws.title, 'cols': [], 'rows': [], 'styles': [], 'widths': []}
    cols = [fmt(c.value, None) or '' for c in header_cells]
    ncol = len(cols)
    rows, cstyles = [], []
    for r in rows_iter:
        if all(c.value in (None, '') for c in r[:ncol]):
            continue
        vals, sids = [], []
        for c in r[:ncol]:
            vals.append(fmt(c.value, c.number_format))
            sids.append(style_id(c))
        while len(vals) < ncol:
            vals.append('')
            sids.append(0)
        rows.append(vals)
        cstyles.append(sids)
    widths = []
    for i in range(ncol):
        letter = ws.cell(row=1, column=i + 1).column_letter
        d = ws.column_dimensions.get(letter)
        widths.append(int((d.width or 12) * 7.5) if d and d.width else 90)
    return {'name': ws.title, 'cols': cols, 'rows': rows, 'cs': cstyles,
            'styles': styles, 'widths': widths}

TPL = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>A股每日选股</title>
<style>
:root{color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:#f5f6f8;color:#15181d;
  font:14px/1.5 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",Arial,sans-serif}
header{background:#1F3864;color:#fff;padding:18px 22px}
header h1{margin:0 0 6px;font-size:20px;font-weight:600;letter-spacing:.5px}
.meta{font-size:13px;opacity:.88;display:flex;flex-wrap:wrap;gap:6px 18px}
.meta b{font-weight:600}
.tag{display:inline-block;background:rgba(255,255,255,.18);border-radius:10px;padding:1px 9px;font-size:12px}
a.dl{display:none;color:#fff;background:rgba(255,255,255,.2);border:1px solid rgba(255,255,255,.35);
  border-radius:7px;padding:3px 11px;text-decoration:none;font-size:12px}
a.dl:hover{background:rgba(255,255,255,.32)}
nav{display:flex;gap:2px;padding:0 14px;background:#fff;border-bottom:1px solid #dfe3e8;
  overflow-x:auto;position:sticky;top:0;z-index:30}
nav button{border:0;background:none;padding:12px 16px;font-size:14px;color:#5a6472;cursor:pointer;
  border-bottom:3px solid transparent;white-space:nowrap;font-family:inherit}
nav button.on{color:#1F3864;font-weight:600;border-bottom-color:#1F3864}
.bar{display:flex;align-items:center;gap:12px;padding:10px 16px;flex-wrap:wrap}
.bar input{flex:1;min-width:180px;max-width:360px;padding:7px 11px;border:1px solid #cfd5dd;
  border-radius:7px;font-size:13px;font-family:inherit;background:#fff}
.bar .n{font-size:12px;color:#6b7482}
.wrap{overflow:auto;background:#fff;border-top:1px solid #dfe3e8;
  max-height:calc(100vh - 185px)}
table{border-collapse:separate;border-spacing:0;font-size:13px}
th,td{border-right:1px solid #e3e6ea;border-bottom:1px solid #e3e6ea;padding:5px 8px;
  white-space:nowrap;background:#fff}
th{background:#1F3864;color:#fff;font-weight:600;position:sticky;top:0;z-index:10;
  cursor:pointer;text-align:center;white-space:normal;vertical-align:middle;padding:8px}
th:hover{background:#2c4b82}
th .ar{opacity:.55;font-size:10px;margin-left:3px}
td.f0,th.f0{position:sticky;left:0;z-index:9}
td.f1,th.f1{position:sticky;z-index:9}
th.f0,th.f1{z-index:20}
td.f0,td.f1{box-shadow:1px 0 0 #e3e6ea}
tbody tr:hover td{filter:brightness(.97)}
.num{text-align:right}
.ctr{text-align:center}
.empty{padding:60px 24px;text-align:center;color:#6b7482}
.empty h2{color:#15181d;font-size:17px;font-weight:600;margin:0 0 10px}
.note{padding:10px 16px;font-size:12px;color:#6b7482;background:#fff;border-top:1px solid #dfe3e8}
.desc td{white-space:pre-wrap;max-width:720px}
.desc td:first-child{white-space:normal;max-width:260px;font-weight:600}
@media(max-width:640px){.wrap{max-height:calc(100vh - 210px)}header h1{font-size:17px}}
</style>
</head>
<body>
<header>
  <h1>A股每日条件选股</h1>
  <div class="meta">
    <span>基准交易日 <b id="d"></b></span>
    <span>报表版本 <span class="tag" id="v"></span></span>
    <span>更新于 <b id="g"></b></span>
    <a class="dl" id="dl" href="latest.xlsx" download>⬇ 下载 xlsx</a>
  </div>
</header>
<nav id="nav"></nav>
<div id="body"></div>
<div class="note">数据来源：东方财富 / 同花顺 / 腾讯财经。本页为按既定规则的数据筛选结果，不构成投资建议。</div>
<script>
const R = __DATA__;
const el = (t,c)=>{const e=document.createElement(t); if(c) e.className=c; return e;};
document.getElementById('d').textContent = R.date || '—';
document.getElementById('v').textContent = R.version || '收盘快报';
document.getElementById('g').textContent = R.generated || '—';
if(R.xlsx) document.getElementById('dl').style.display = 'inline-block';

const body = document.getElementById('body'), nav = document.getElementById('nav');
if(!R.sheets || !R.sheets.length){
  const e = el('div','empty');
  e.innerHTML = '<h2>暂无数据</h2><p>'+(R.message||'等待下一个交易日收盘后的自动更新。')+'</p>';
  body.appendChild(e);
}else{
  const panes = R.sheets.map((s,i)=>{
    const b = el('button'); b.textContent = s.name; b.onclick = ()=>show(i);
    nav.appendChild(b);
    const p = el('div'); p.style.display='none'; p.appendChild(build(s)); body.appendChild(p);
    return p;
  });
  function show(i){
    panes.forEach((p,j)=>p.style.display = i===j?'':'none');
    [...nav.children].forEach((b,j)=>b.classList.toggle('on', i===j));
  }
  show(0);
}

function build(s){
  const box = el('div');
  const bar = el('div','bar');
  const inp = el('input'); inp.type='search'; inp.placeholder='搜索代码 / 名称 / 行业…';
  const cnt = el('span','n');
  bar.appendChild(inp); bar.appendChild(cnt); box.appendChild(bar);

  const wrap = el('div','wrap'), tb = el('table');
  const thead = el('thead'), htr = el('tr');
  const isDesc = /说明/.test(s.name);
  const frozen = isDesc ? 0 : 2;
  let left = 0;
  s.cols.forEach((c,i)=>{
    const th = el('th'); th.textContent = c;
    const w = Math.max(56, Math.min(s.widths[i]||90, 420));
    th.style.minWidth = w+'px'; th.style.width = w+'px';
    if(i<frozen){ th.className='f'+i; th.style.left = left+'px'; left += w; }
    th.onclick = ()=>sort(i, th);
    const ar = el('span','ar'); ar.textContent='⇅'; th.appendChild(ar);
    htr.appendChild(th);
  });
  thead.appendChild(htr); tb.appendChild(thead);
  const tbody = el('tbody'); if(isDesc) tbody.className='desc';
  tb.appendChild(tbody); wrap.appendChild(tb); box.appendChild(wrap);

  const numish = s.cols.map(c=>/%|额|价|MA|线|量|数|名次|市值|净|率|手|元/.test(c) && !/方向|时点|名称|板块|区间|报告期|股东|说明|代码|池/.test(c));
  let data = s.rows.map((r,i)=>({r, st:(s.cs&&s.cs[i])||[]}));
  let order = null, asc = true;

  function css(id){
    if(!id) return '';
    const st = s.styles[id-1]; if(!st) return '';
    let o = '';
    if(st.bg) o += 'background:'+st.bg+';';
    if(st.fc) o += 'color:'+st.fc+';';
    if(st.b) o += 'font-weight:700;';
    if(st.a==='center') o += 'text-align:center;';
    if(st.a==='right') o += 'text-align:right;';
    return o;
  }
  function render(){
    const q = inp.value.trim().toLowerCase();
    let rows = data;
    if(q) rows = rows.filter(o=>o.r.some(v=>String(v).toLowerCase().includes(q)));
    if(order!==null){
      const k = order;
      rows = rows.slice().sort((a,b)=>{
        const x=a.r[k]??'', y=b.r[k]??'';
        const nx=parseFloat(String(x).replace(/,/g,'')), ny=parseFloat(String(y).replace(/,/g,''));
        const bothNum = !isNaN(nx)&&!isNaN(ny)&&String(x).trim()!==''&&String(y).trim()!=='';
        let c = bothNum ? nx-ny : String(x).localeCompare(String(y),'zh-Hans-CN');
        return asc ? c : -c;
      });
    }
    tbody.textContent='';
    const frag = document.createDocumentFragment();
    rows.forEach(o=>{
      const tr = el('tr'); let l = 0;
      o.r.forEach((v,i)=>{
        const td = el('td');
        td.textContent = v;
        let cls = '';
        if(i<frozen){ cls='f'+i; const w=Math.max(56,Math.min(s.widths[i]||90,420)); td.style.left=l+'px'; l+=w; }
        if(numish[i]) cls += (cls?' ':'')+'num';
        if(v==='✓') cls += (cls?' ':'')+'ctr';
        if(cls) td.className = cls;
        const st = css(o.st[i]);
        if(st) td.style.cssText += st;
        tr.appendChild(td);
      });
      frag.appendChild(tr);
    });
    tbody.appendChild(frag);
    cnt.textContent = rows.length + ' / ' + data.length + ' 行';
  }
  function sort(i, th){
    if(order===i) asc = !asc; else { order = i; asc = true; }
    [...htr.children].forEach(h=>h.querySelector('.ar').textContent='⇅');
    th.querySelector('.ar').textContent = asc?'▲':'▼';
    render();
  }
  inp.oninput = render;
  render();
  return box;
}
</script>
</body>
</html>
"""

def build_html(payload):
    return TPL.replace('__DATA__', json.dumps(payload, ensure_ascii=False))

def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(1)
    want_xlsx = '--xlsx' in a
    a = [x for x in a if x != '--xlsx']
    if a[0] == '--empty':
        out = a[1]
        payload = {'date': '—', 'version': '待生成', 'generated': '—',
                   'message': a[2] if len(a) > 2 else '等待下一个交易日收盘后的自动更新。',
                   'sheets': []}
    else:
        import openpyxl
        xlsx, out = a[0], a[1]
        date = a[2] if len(a) > 2 else ''
        version = a[3] if len(a) > 3 else '收盘快报'
        wb = openpyxl.load_workbook(xlsx)
        sheets = [sheet_to_obj(wb[n]) for n in wb.sheetnames]
        if date and len(date) == 8:
            date = f'{date[:4]}-{date[4:6]}-{date[6:]}'
        gen = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M') + ' (北京)'
        payload = {'date': date or '—', 'version': version, 'generated': gen, 'sheets': sheets}
    payload['xlsx'] = want_xlsx
    with open(out, 'w', encoding='utf-8') as f:
        f.write(build_html(payload))
    print('wrote', out)

if __name__ == '__main__':
    main()
