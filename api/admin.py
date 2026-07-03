"""
api/admin.py — پنل ادمین Nazoo (Vercel Serverless، بدون هیچ dependency خارجی)

یه داشبورد تک‌فایلی که مستقیم از Redis می‌خونه:
  • لیست همه‌ی کاربرها + آخرین فعالیت
  • مشاهده‌ی کامل تاریخچه‌ی گفتگو (پیام کاربر + جواب AI) برای هر کاربر
  • مشاهده‌ی فکت‌های یادگرفته‌شده
  • پاک‌کردن تاریخچه / فکت‌ها / کل پروفایل هر کاربر

دسترسی با یه secret ساده محافظت میشه (ADMIN_SECRET در env vars).
"""

import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import kv_store as kv

ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")
BOT_NAME     = os.environ.get("BOT_NAME", "Nazoo")


# ── دسترسی به داده ────────────────────────────────────────────────────────────

def list_users() -> list:
    ids = kv.smembers("nazoo:users:index")
    users = []
    for uid in ids:
        meta    = kv.hgetall(f"nazoo:user:{uid}:meta")
        history = kv.get_json(f"nazoo:history:{uid}", [])
        facts   = kv.get_json(f"nazoo:facts:{uid}", [])
        users.append({
            "user_id":          uid,
            "first_name":       meta.get("first_name") or "؟",
            "username":         meta.get("username") or "",
            "total_messages":   kv.get_int(f"nazoo:msgcount:{uid}"),
            "recent_in_window": len(history) // 2,
            "facts_count":      len(facts),
            "last_seen":        meta.get("last_seen") or "",
            "joined_at":        meta.get("joined_at") or "",
        })
    users.sort(key=lambda u: u["last_seen"], reverse=True)
    return users


def get_user_detail(uid: str) -> dict:
    meta = kv.hgetall(f"nazoo:user:{uid}:meta")
    return {
        "meta":           meta,
        "history":        kv.get_json(f"nazoo:history:{uid}", []),
        "facts":          kv.get_json(f"nazoo:facts:{uid}", []),
        "total_messages": kv.get_int(f"nazoo:msgcount:{uid}"),
    }


def clear_history(uid: str):
    kv.delete(f"nazoo:history:{uid}")


def clear_facts(uid: str):
    kv.delete(f"nazoo:facts:{uid}")


def delete_user(uid: str):
    kv.delete(f"nazoo:history:{uid}", f"nazoo:facts:{uid}",
              f"nazoo:user:{uid}:meta", f"nazoo:msgcount:{uid}")
    kv.srem("nazoo:users:index", uid)


def get_stats() -> dict:
    ids = kv.smembers("nazoo:users:index")
    total_msgs = sum(kv.get_int(f"nazoo:msgcount:{uid}") for uid in ids)
    return {"total_users": len(ids), "total_messages": total_msgs}


# ── HTML/CSS/JS داشبورد (استاتیک — بدون secret داخلش) ─────────────────────────

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>__BOT_NAME__ · پنل ادمین</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#12141a; --surface:#181b23; --surface-2:#20242e; --surface-3:#262b37;
    --border:#2a2f3b; --text:#eef0f4; --text-dim:#8a93a6; --text-faint:#5b6472;
    --user:#ff6f91; --ai:#8c7ae6; --danger:#f0526b; --danger-bg:#3a1c24;
    --success:#34d399; --warn:#fbbf6b;
    --radius:14px; --radius-sm:9px;
    --font-ui:'Vazirmatn',system-ui,sans-serif;
    --font-mono:'JetBrains Mono',ui-monospace,monospace;
  }
  *{box-sizing:border-box; margin:0; padding:0;}
  html,body{height:100%;}
  body{
    background:var(--bg); color:var(--text); font-family:var(--font-ui);
    -webkit-font-smoothing:antialiased; overflow:hidden;
  }
  @media (prefers-reduced-motion: reduce){ *{animation:none !important; transition:none !important;} }

  /* ---------- Login ---------- */
  #login-screen{
    position:fixed; inset:0; display:flex; align-items:center; justify-content:center;
    background:radial-gradient(circle at 30% 20%, #1c2130 0%, var(--bg) 60%);
  }
  .login-card{
    width:min(360px, 90vw); background:var(--surface); border:1px solid var(--border);
    border-radius:var(--radius); padding:32px 28px; text-align:center;
    box-shadow:0 20px 60px rgba(0,0,0,.4);
  }
  .login-emoji{font-size:40px; margin-bottom:6px; display:block;}
  .login-card h1{font-size:19px; font-weight:700; margin-bottom:4px;}
  .login-card p{color:var(--text-dim); font-size:13px; margin-bottom:20px;}
  .login-card input{
    width:100%; padding:12px 14px; border-radius:var(--radius-sm); border:1px solid var(--border);
    background:var(--surface-2); color:var(--text); font-family:var(--font-mono); font-size:14px;
    outline:none; transition:border-color .15s;
  }
  .login-card input:focus{border-color:var(--user);}
  .login-card button{
    width:100%; margin-top:12px; padding:12px; border:none; border-radius:var(--radius-sm);
    background:linear-gradient(135deg, var(--user), #ff9776); color:#1a0d12; font-weight:700;
    font-family:var(--font-ui); font-size:14px; cursor:pointer; transition:transform .1s, opacity .15s;
  }
  .login-card button:active{transform:scale(.98);}
  .login-card button:disabled{opacity:.5; cursor:default;}
  #login-error{color:var(--danger); font-size:12.5px; margin-top:10px; min-height:16px;}

  /* ---------- App shell ---------- */
  #app{display:none; height:100vh; flex-direction:column;}
  #app.visible{display:flex;}

  .topbar{
    display:flex; align-items:center; gap:14px; padding:12px 18px;
    background:var(--surface); border-bottom:1px solid var(--border); flex-shrink:0;
  }
  .topbar .brand{display:flex; align-items:center; gap:8px; font-weight:700; font-size:15px;}
  .topbar .brand .dot{width:8px; height:8px; border-radius:50%; background:var(--success); box-shadow:0 0 8px var(--success);}
  .pill{
    font-family:var(--font-mono); font-size:11.5px; color:var(--text-dim);
    background:var(--surface-2); border:1px solid var(--border); border-radius:20px;
    padding:4px 10px; white-space:nowrap;
  }
  .topbar .spacer{flex:1;}
  .icon-btn{
    background:var(--surface-2); border:1px solid var(--border); color:var(--text-dim);
    width:34px; height:34px; border-radius:var(--radius-sm); cursor:pointer;
    display:flex; align-items:center; justify-content:center; font-size:15px;
    transition:background .15s, color .15s;
  }
  .icon-btn:hover{background:var(--surface-3); color:var(--text);}

  .layout{flex:1; display:flex; overflow:hidden;}

  /* ---------- Sidebar ---------- */
  #sidebar{
    width:320px; flex-shrink:0; background:var(--surface); border-left:1px solid var(--border);
    display:flex; flex-direction:column;
  }
  .search-box{padding:12px; border-bottom:1px solid var(--border);}
  .search-box input{
    width:100%; padding:9px 12px; border-radius:var(--radius-sm); border:1px solid var(--border);
    background:var(--surface-2); color:var(--text); font-family:var(--font-ui); font-size:13px; outline:none;
  }
  .search-box input:focus{border-color:var(--user);}
  #user-list{flex:1; overflow-y:auto;}
  .user-row{
    display:flex; align-items:center; gap:10px; padding:12px 14px; cursor:pointer;
    border-bottom:1px solid var(--border); transition:background .12s;
  }
  .user-row:hover{background:var(--surface-2);}
  .user-row.active{background:var(--surface-3); border-right:3px solid var(--user);}
  .avatar{
    width:36px; height:36px; border-radius:50%; flex-shrink:0;
    background:linear-gradient(135deg, var(--ai), var(--user));
    display:flex; align-items:center; justify-content:center; font-weight:700; font-size:14px; color:#12141a;
  }
  .user-row .info{flex:1; min-width:0;}
  .user-row .name{font-size:13.5px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
  .user-row .sub{font-size:11.5px; color:var(--text-faint); font-family:var(--font-mono); margin-top:1px;}
  .status-dot{width:7px; height:7px; border-radius:50%; background:var(--text-faint); flex-shrink:0;}
  .status-dot.online{background:var(--success); box-shadow:0 0 6px var(--success); animation:pulse 2s infinite;}
  @keyframes pulse{0%,100%{opacity:1;} 50%{opacity:.4;}}
  #empty-users{padding:30px 16px; text-align:center; color:var(--text-faint); font-size:13px;}

  /* ---------- Main panel ---------- */
  #main{flex:1; display:flex; flex-direction:column; overflow:hidden;}
  #placeholder{
    flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center;
    color:var(--text-faint); gap:8px;
  }
  #placeholder .big{font-size:38px;}
  #placeholder .txt{font-size:13.5px;}

  #user-view{display:none; flex:1; flex-direction:column; overflow:hidden;}
  #user-view.visible{display:flex;}

  .user-header{
    display:flex; align-items:center; gap:12px; padding:14px 20px;
    border-bottom:1px solid var(--border); background:var(--surface); flex-shrink:0;
  }
  .user-header .avatar{width:42px; height:42px; font-size:16px;}
  .user-header .meta h2{font-size:15.5px; font-weight:700;}
  .user-header .meta .row{font-size:11.5px; color:var(--text-dim); font-family:var(--font-mono); margin-top:2px;}
  .user-header .actions{margin-right:auto; display:flex; gap:8px;}
  .btn{
    font-family:var(--font-ui); font-size:12.5px; font-weight:600; border-radius:var(--radius-sm);
    padding:8px 13px; cursor:pointer; border:1px solid var(--border); background:var(--surface-2);
    color:var(--text-dim); transition:background .15s, color .15s, border-color .15s;
  }
  .btn:hover{background:var(--surface-3); color:var(--text);}
  .btn.danger{color:var(--danger); border-color:#4a2530;}
  .btn.danger:hover{background:var(--danger-bg);}

  .facts-bar{
    padding:10px 20px; border-bottom:1px solid var(--border); background:var(--surface);
    display:flex; gap:8px; flex-wrap:wrap; flex-shrink:0;
  }
  .facts-bar .label{font-size:11px; color:var(--text-faint); font-family:var(--font-mono); align-self:center;}
  .fact-chip{
    font-size:11.5px; background:var(--surface-2); border:1px solid var(--border); color:var(--text-dim);
    padding:4px 10px; border-radius:20px;
  }

  #transcript{flex:1; overflow-y:auto; padding:20px; display:flex; flex-direction:column; gap:10px;}
  .bubble-row{display:flex; max-width:72%;}
  .bubble-row.user{align-self:flex-start; flex-direction:row;}
  .bubble-row.ai{align-self:flex-end; flex-direction:row-reverse;}
  .bubble{
    padding:10px 14px; border-radius:var(--radius); font-size:13.5px; line-height:1.6;
    animation:fadeIn .2s ease;
  }
  @keyframes fadeIn{from{opacity:0; transform:translateY(4px);} to{opacity:1; transform:none;}}
  .bubble-row.user .bubble{background:var(--surface-2); border:1px solid var(--border); border-top-right-radius:4px;}
  .bubble-row.ai .bubble{background:linear-gradient(135deg,#2a2440,#231e3a); border:1px solid #3a3260; border-top-left-radius:4px;}
  .bubble-meta{font-family:var(--font-mono); font-size:9.5px; color:var(--text-faint); margin-top:3px; padding:0 4px;}

  #empty-transcript{color:var(--text-faint); text-align:center; margin:auto; font-size:13px;}

  /* ---------- Mobile ---------- */
  @media (max-width: 820px){
    #sidebar{
      position:fixed; inset:0; width:100%; z-index:20;
      transform:translateX(0); transition:transform .2s ease;
    }
    #sidebar.hide-mobile{transform:translateX(105%);}
    #main{width:100%;}
    .back-btn{display:flex !important;}
    .bubble-row{max-width:88%;}
  }
  .back-btn{display:none;}
</style>
</head>
<body>

  <div id="login-screen">
    <div class="login-card">
      <span class="login-emoji">🦋</span>
      <h1>__BOT_NAME__ · پنل ادمین</h1>
      <p>برای ادامه، رمز ادمین رو وارد کن</p>
      <input id="secret-input" type="password" placeholder="ADMIN_SECRET" autocomplete="off" />
      <button id="login-btn" onclick="doLogin()">ورود</button>
      <div id="login-error"></div>
    </div>
  </div>

  <div id="app">
    <div class="topbar">
      <div class="brand"><span class="dot"></span> __BOT_NAME__ · ادمین</div>
      <span class="pill" id="stat-users">۰ کاربر</span>
      <span class="pill" id="stat-msgs">۰ پیام</span>
      <div class="spacer"></div>
      <button class="icon-btn" onclick="refreshAll()" title="بروزرسانی">↻</button>
      <button class="icon-btn" onclick="logout()" title="خروج">⏻</button>
    </div>

    <div class="layout">
      <div id="sidebar">
        <div class="search-box">
          <input id="search" placeholder="جستجوی کاربر…" oninput="renderUserList()" />
        </div>
        <div id="user-list"></div>
      </div>

      <div id="main">
        <div id="placeholder">
          <div class="big">🦋</div>
          <div class="txt">یه کاربر رو از لیست انتخاب کن</div>
        </div>

        <div id="user-view">
          <div class="user-header">
            <button class="icon-btn back-btn" onclick="closeUser()">→</button>
            <div class="avatar" id="uv-avatar">?</div>
            <div class="meta">
              <h2 id="uv-name">—</h2>
              <div class="row" id="uv-sub">—</div>
            </div>
            <div class="actions">
              <button class="btn" onclick="doAction('clear_history')">پاک‌کردن تاریخچه</button>
              <button class="btn" onclick="doAction('clear_facts')">فراموشی فکت‌ها</button>
              <button class="btn danger" onclick="doAction('delete_user')">حذف کامل کاربر</button>
            </div>
          </div>
          <div class="facts-bar" id="facts-bar" style="display:none;"></div>
          <div id="transcript"></div>
        </div>
      </div>
    </div>
  </div>

<script>
let SECRET = sessionStorage.getItem('nazoo_admin_secret') || '';
let USERS = [];
let CURRENT_UID = null;
let autoTimer = null;

function api(action, extra){
  extra = extra || {};
  return fetch(location.pathname, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(Object.assign({action:action, secret:SECRET}, extra))
  }).then(r => r.json());
}

async function doLogin(){
  const val = document.getElementById('secret-input').value.trim();
  const btn = document.getElementById('login-btn');
  const err = document.getElementById('login-error');
  if(!val){ err.textContent = 'رمز رو وارد کن.'; return; }
  SECRET = val;
  btn.disabled = true; btn.textContent = 'در حال بررسی…';
  const res = await api('login');
  btn.disabled = false; btn.textContent = 'ورود';
  if(res && res.ok){
    sessionStorage.setItem('nazoo_admin_secret', SECRET);
    document.getElementById('login-screen').style.display = 'none';
    document.getElementById('app').classList.add('visible');
    refreshAll();
    autoTimer = setInterval(refreshUsers, 25000);
  } else {
    err.textContent = 'رمز اشتباهه یا ADMIN_SECRET تنظیم نشده.';
  }
}

function logout(){
  sessionStorage.removeItem('nazoo_admin_secret');
  SECRET = ''; CURRENT_UID = null;
  if(autoTimer) clearInterval(autoTimer);
  document.getElementById('app').classList.remove('visible');
  document.getElementById('login-screen').style.display = 'flex';
  document.getElementById('secret-input').value = '';
}

async function refreshAll(){
  await Promise.all([refreshUsers(), refreshStats()]);
}

async function refreshStats(){
  const res = await api('stats');
  if(!res || !res.ok) return;
  document.getElementById('stat-users').textContent = res.total_users + ' کاربر';
  document.getElementById('stat-msgs').textContent  = res.total_messages + ' پیام';
}

async function refreshUsers(){
  const res = await api('list_users');
  if(!res || !res.ok){ if(res && res.error === 'unauthorized') logout(); return; }
  USERS = res.users || [];
  renderUserList();
}

function timeAgo(iso){
  if(!iso) return '—';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if(diff < 60) return 'همین الان';
  if(diff < 3600) return Math.floor(diff/60) + ' دقیقه پیش';
  if(diff < 86400) return Math.floor(diff/3600) + ' ساعت پیش';
  return Math.floor(diff/86400) + ' روز پیش';
}
function isOnline(iso){ if(!iso) return false; return (Date.now() - new Date(iso).getTime()) < 5*60*1000; }
function initial(name){ return (name || '؟').trim().charAt(0).toUpperCase(); }

function renderUserList(){
  const q = document.getElementById('search').value.trim().toLowerCase();
  const list = document.getElementById('user-list');
  const filtered = USERS.filter(u =>
    !q || (u.first_name||'').toLowerCase().includes(q) ||
    (u.username||'').toLowerCase().includes(q) || String(u.user_id).includes(q)
  );
  if(filtered.length === 0){
    list.innerHTML = '<div id="empty-users">کاربری پیدا نشد 🤷</div>';
    return;
  }
  list.innerHTML = filtered.map(u => `
    <div class="user-row ${u.user_id===CURRENT_UID?'active':''}" onclick="openUser('${u.user_id}')">
      <div class="avatar">${initial(u.first_name)}</div>
      <div class="info">
        <div class="name">${escapeHtml(u.first_name)} ${u.username ? '· @'+escapeHtml(u.username) : ''}</div>
        <div class="sub">id:${u.user_id} · ${u.total_messages} پیام · ${timeAgo(u.last_seen)}</div>
      </div>
      <div class="status-dot ${isOnline(u.last_seen)?'online':''}"></div>
    </div>
  `).join('');
}

async function openUser(uid){
  CURRENT_UID = uid;
  renderUserList();
  document.getElementById('placeholder').style.display = 'none';
  document.getElementById('user-view').classList.add('visible');
  document.getElementById('sidebar').classList.add('hide-mobile');

  const res = await api('get_user', {user_id: uid});
  if(!res || !res.ok) return;

  const meta = res.meta || {};
  document.getElementById('uv-avatar').textContent = initial(meta.first_name);
  document.getElementById('uv-name').textContent = meta.first_name || '؟';
  document.getElementById('uv-sub').textContent =
    `id:${uid} · ${meta.username ? '@'+meta.username : 'بدون یوزرنیم'} · ${res.total_messages} پیام کل`;

  const factsBar = document.getElementById('facts-bar');
  if(res.facts && res.facts.length){
    factsBar.style.display = 'flex';
    factsBar.innerHTML = '<span class="label">🧠 فکت‌ها:</span>' +
      res.facts.map(f => `<span class="fact-chip">${escapeHtml(f)}</span>`).join('');
  } else {
    factsBar.style.display = 'none';
  }

  const t = document.getElementById('transcript');
  if(!res.history || res.history.length === 0){
    t.innerHTML = '<div id="empty-transcript">هنوز پیامی رد و بدل نشده.</div>';
    return;
  }
  t.innerHTML = res.history.map(m => `
    <div class="bubble-row ${m.role==='user'?'user':'ai'}">
      <div>
        <div class="bubble" dir="auto">${escapeHtml(m.content)}</div>
      </div>
    </div>
  `).join('');
  t.scrollTop = t.scrollHeight;
}

function closeUser(){
  document.getElementById('sidebar').classList.remove('hide-mobile');
}

async function doAction(action){
  if(!CURRENT_UID) return;
  const labels = {clear_history:'تاریخچه پاک بشه؟', clear_facts:'فکت‌ها پاک بشن؟', delete_user:'کل پروفایل این کاربر حذف بشه؟ (غیرقابل بازگشت)'};
  if(!confirm(labels[action] || 'مطمئنی؟')) return;
  const res = await api(action, {user_id: CURRENT_UID});
  if(res && res.ok){
    if(action === 'delete_user'){
      CURRENT_UID = null;
      document.getElementById('user-view').classList.remove('visible');
      document.getElementById('placeholder').style.display = 'flex';
      refreshUsers();
    } else {
      openUser(CURRENT_UID);
    }
    refreshStats();
  }
}

function escapeHtml(s){
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

if(SECRET){
  document.getElementById('secret-input').value = SECRET;
  doLogin();
}
document.getElementById('secret-input').addEventListener('keydown', e => {
  if(e.key === 'Enter') doLogin();
});
</script>
</body>
</html>
"""


def _render_html() -> bytes:
    html = DASHBOARD_HTML.replace("__BOT_NAME__", BOT_NAME)
    return html.encode("utf-8")


# ── Vercel entrypoint ─────────────────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):

    def _json(self, code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        body = _render_html()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except Exception:
            payload = {}

        action = payload.get("action", "")
        secret = payload.get("secret", "")

        if not ADMIN_SECRET or not hmac.compare_digest(str(secret), ADMIN_SECRET):
            self._json(401, {"ok": False, "error": "unauthorized"})
            return

        try:
            if action == "login":
                data = {"ok": True}
            elif action == "stats":
                data = {"ok": True, **get_stats()}
            elif action == "list_users":
                data = {"ok": True, "users": list_users()}
            elif action == "get_user":
                uid = str(payload.get("user_id", ""))
                data = {"ok": True, **get_user_detail(uid)}
            elif action == "clear_history":
                clear_history(str(payload.get("user_id", "")))
                data = {"ok": True}
            elif action == "clear_facts":
                clear_facts(str(payload.get("user_id", "")))
                data = {"ok": True}
            elif action == "delete_user":
                delete_user(str(payload.get("user_id", "")))
                data = {"ok": True}
            else:
                data = {"ok": False, "error": "unknown action"}
        except Exception as e:
            data = {"ok": False, "error": str(e)}

        self._json(200, data)
