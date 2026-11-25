"""Web：药箱清单 + 一键检查 + 问模型。

检查全在本地算，点一下就出结果；「问建议」才调模型，所以会慢。
"""

from __future__ import annotations

import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import advice, check, drugs, store

PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>康记 · 家里那箱药</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0b0f14;color:#c9d1d9;font:15px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
header{padding:16px 24px;border-bottom:1px solid #21262d;display:flex;gap:12px;align-items:baseline}
h1{margin:0;font-size:18px;color:#7ee787}
.sub{color:#8b949e;font-size:13px}
main{display:grid;grid-template-columns:minmax(320px,420px) 1fr;min-height:calc(100vh - 60px)}
aside{border-right:1px solid #21262d;padding:16px}
section{padding:18px 24px}
input{width:100%;background:#161b22;color:#c9d1d9;border:1px solid #30363d;border-radius:8px;padding:7px 10px;margin-bottom:8px;font:14px inherit}
.row2{display:flex;gap:8px}
button{background:#238636;color:#fff;border:0;border-radius:6px;padding:8px 14px;font:14px inherit;cursor:pointer}
button.ghost{background:#21262d;color:#c9d1d9}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid #161b22}
th{color:#8b949e;font-weight:400}
.tag{font-size:12px;border-radius:10px;padding:1px 8px;background:#1c2f3d;color:#79c0ff}
.high{color:#ff7b72}.medium{color:#e3b341}.ok{color:#7ee787}
.card{border:1px solid #21262d;border-radius:8px;padding:12px;margin-bottom:10px}
.card b{font-weight:600}
.k{color:#8b949e;font-size:13px}
h2{font-size:15px;margin:20px 0 8px}
.warn{color:#e3b341}
</style></head><body>
<header><h1>康记</h1><span class="sub">家里那箱药，过期了没有、有没有重复、能不能一起吃</span></header>
<main>
<aside>
  <h2>加一盒</h2>
  <input id="name" placeholder="药名，商品名也行（泰诺林）">
  <div class="row2">
    <input id="qty" placeholder="数量" value="1">
    <input id="expire" placeholder="有效期 2027-06">
  </div>
  <input id="place" placeholder="放在哪（客厅抽屉）">
  <button id="add">记下</button>
  <h2>药箱</h2>
  <div id="list"></div>
</aside>
<section>
  <div style="display:flex;gap:8px;align-items:center;margin-bottom:14px">
    <button id="run" class="ghost">检查一遍</button>
    <button id="ask">问管理建议</button>
    <span class="k" id="status"></span>
  </div>
  <div id="out"><p class="k">左边加几盒药，然后点「检查一遍」。</p></div>
</section>
</main>
<script>
const $ = s => document.querySelector(s);
const esc = s => (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

async function loadList(){
  const r = await fetch('/api/meds');
  const items = (await r.json()).items;
  $('#list').innerHTML = items.length ? `<table><tr><th>数量</th><th>有效期</th><th>名字</th></tr>` +
    items.map(m=>`<tr><td>${m.qty}</td><td class="k">${esc(m.expire)||'没记'}</td><td>${esc(m.name)}</td></tr>`).join('') +
    `</table>` : '<p class="k">还是空的</p>';
}

function renderCheck(d){
  let html = `<h2>检查 · ${esc(d.as_of)} · <span class="${d.level}">${{high:'有硬问题',medium:'要留意',ok:'看着还行'}[d.level]}</span></h2>`;
  const block = (title, rows, fn) => rows.length ? `<h2>${title}</h2>` + rows.map(fn).join('') : '';
  html += block('过期了', d.expired, e => `<div class="card high"><b>${esc(e.name)}</b> <span class="k">${esc(e.generic)}</span><div class="k">过期 ${e.days_ago} 天（${esc(e.expire)}）</div></div>`);
  html += block('60 天内到期', d.expiring, e => `<div class="card medium"><b>${esc(e.name)}</b><div class="k">还剩 ${e.days_left} 天（${esc(e.expire)}）</div></div>`);
  html += block('同一成分出现在好几盒里', d.duplicates, x => `<div class="card"><b>${esc(x.ingredient)}</b><div class="k">${x.names.map(esc).join('、')} —— 一起吃等于加量</div></div>`);
  html += block('不宜同用', d.conflicts, c => `<div class="card ${c.level}"><b>${esc(c.a)} + ${esc(c.b)}</b><div class="k">${esc(c.why)}</div></div>`);
  html += block('已经用完了', d.low_stock, s => `<div class="card"><b>${esc(s.name)}</b> <span class="k">剩 ${s.qty}</span></div>`);
  if (d.unknown.length) html += `<p class="k">药库不认识：${d.unknown.map(esc).join('、')}（没参与检查）</p>`;
  $('#out').innerHTML = html;
}

$('#run').onclick = async () => {
  const r = await fetch('/api/check');
  const d = await r.json();
  if(d.error){ alert(d.error); return; }
  renderCheck(d);
};

$('#ask').onclick = async () => {
  $('#ask').disabled = true;
  $('#status').textContent = '模型在写…十几秒';
  const r = await fetch('/api/advice', {method:'POST'});
  const d = await r.json();
  $('#ask').disabled = false;
  $('#status').textContent = '';
  if(d.error){ alert(d.error); return; }
  let html = `<h2>管理建议</h2>` + (d.actions||[]).map(a =>
    `<div class="card"><b>${a.n}. ${esc(a.thing)}</b><div class="k">${esc(a.why)}</div>
     ${a.foreign && a.foreign.length ? `<div class="warn">⚠ 提到了药箱里没有的药：${a.foreign.map(esc).join('、')}</div>` : ''}</div>`).join('') +
    (d.summary ? `<p>${esc(d.summary)}</p>` : '');
  $('#out').innerHTML = html + $('#out').innerHTML;
};

$('#add').onclick = async () => {
  const name = $('#name').value.trim();
  if(!name) return alert('先写药名');
  const r = await fetch('/api/add', {method:'POST', body: JSON.stringify({
    name, qty: Number($('#qty').value) || 1, expire: $('#expire').value, place: $('#place').value
  })});
  const d = await r.json();
  if(d.error) return alert(d.error);
  $('#name').value = ''; $('#qty').value = '1'; $('#expire').value = ''; $('#place').value = '';
  loadList();
};
loadList();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    conn = None

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/meds":
            self._json({"items": store.list_meds(self.conn)})
            return
        if parsed.path == "/api/check":
            rows = store.list_meds(self.conn)
            qs = urllib.parse.parse_qs(parsed.query)
            today = check.parse_date((qs.get("today") or [""])[0])
            self._json(check.check(rows, today=today))
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            body = {}

        if parsed.path == "/api/add":
            name = (body.get("name") or "").strip()
            if not name:
                self._json({"error": "药名不能空"}, 400)
                return
            med = drugs.lookup(name)
            expire = check.parse_date(body.get("expire") or "")
            if (body.get("expire") or "").strip() and not expire:
                self._json({"error": "有效期格式看不懂"}, 400)
                return
            try:
                qty = float(body.get("qty") or 1)
            except (TypeError, ValueError):
                qty = 1.0
            mid = store.add_med(self.conn, name, med["name"] if med else "", qty,
                                expire.isoformat() if expire else "", body.get("place") or "")
            self._json({"id": mid, "generic": med["name"] if med else ""})
            return

        if parsed.path == "/api/advice":
            rows = store.list_meds(self.conn)
            if not rows:
                self._json({"error": "药箱是空的"}, 400)
                return
            result = check.check(rows)
            out = advice.advise(result, rows)
            if out["error"] and not out["actions"]:
                self._json({"error": out["error"]}, 502)
                return
            store.save_advice(self.conn, out["actions"], out["summary"], out["foreign"])
            self._json(out)
            return

        self._json({"error": "not found"}, 404)


def make_server(conn, host: str = "127.0.0.1", port: int = 8772) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"conn": conn})
    return ThreadingHTTPServer((host, port), handler)


def serve(conn, host: str = "127.0.0.1", port: int = 8772):
    httpd = make_server(conn, host, port)
    print(f"康记已起：http://{host}:{port}  （Ctrl+C 退出）")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n再见。")
    finally:
        httpd.server_close()
