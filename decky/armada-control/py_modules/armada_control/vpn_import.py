import http.server
import json
import socket
import threading
from urllib.parse import parse_qs, urlparse

from .privileged import call

IMPORT_PORT = 8799

_server = None
_thread = None
_state = {"received": False, "last_profile": ""}


def _lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


_PAGE = """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Import VPN config</title><style>
body{font-family:sans-serif;background:#14171c;color:#e8e8e8;margin:0;padding:24px;max-width:760px}
h2{font-weight:500}code{color:#8ab4f8}
textarea{width:100%;height:280px;box-sizing:border-box;font-family:monospace;font-size:13px;background:#0f1216;color:#dfe;border:1px solid #333;border-radius:8px;padding:10px}
button{margin-top:14px;padding:12px 22px;font-size:16px;border:0;border-radius:8px;color:#fff;cursor:pointer}
.b1{background:#2677d8}.b2{background:#1d9e75;margin-left:10px}
.msg{margin-top:14px;font-size:15px}.ok{color:#5dcaa5}.err{color:#e24b4a}
</style></head><body>
<h2>Import VPN config</h2>
<p>Paste a <code>vless://</code> link <b>or</b> a full sing-box <code>config.json</code>, then choose a profile:</p>
<textarea id="c" placeholder="vless://uuid@host:443?type=grpc&security=reality&sni=...&pbk=...&sid=...   (or a full config.json)"></textarea>
<div>
  <button class="b1" onclick="save('1')">Save to Profile 1</button>
  <button class="b2" onclick="save('2')">Save to Profile 2</button>
</div>
<div id="m" class="msg"></div>
<script>
async function save(p){var m=document.getElementById('m');m.className='msg';m.textContent='Saving to Profile '+p+'...';
try{var r=await fetch('/import?profile='+p,{method:'POST',headers:{'Content-Type':'text/plain'},body:document.getElementById('c').value});
var j=await r.json();if(j.ok){m.className='msg ok';m.textContent='Saved to Profile '+j.profile+(j.active?' (VPN restarted)':'')+'. Paste another to save to the other profile, or close this page.';}
else{m.className='msg err';m.textContent='Error: '+(j.error||'failed');}}catch(e){m.className='msg err';m.textContent='Error: '+e;}}
</script></body></html>"""


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if urlparse(self.path).path == "/import":
            self._send(200, _PAGE)
        else:
            self._send(404, "not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/import":
            self._send(404, "not found")
            return
        try:
            profile = (parse_qs(parsed.query).get("profile") or ["1"])[0]
            if profile not in ("1", "2"):
                raise ValueError("choose Profile 1 or 2")
            length = int(self.headers.get("Content-Length", 0))
            text = self.rfile.read(length).decode("utf-8")
            result = call("import_vpn_config", profile=profile, text=text)
            _state["received"] = True
            _state["last_profile"] = result.get("profile", profile)
            self._send(200, json.dumps({"ok": True, "profile": result.get("profile"), "active": result.get("active")}), "application/json")
        except Exception as exc:
            self._send(200, json.dumps({"ok": False, "error": str(exc)[:300]}), "application/json")


def start(profile="1"):
    global _server, _thread
    stop()
    _state["received"] = False
    _state["last_profile"] = ""
    _server = http.server.ThreadingHTTPServer(("0.0.0.0", IMPORT_PORT), _Handler)
    _thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _thread.start()
    return {"url": "http://%s:%d/import" % (_lan_ip(), IMPORT_PORT), "port": IMPORT_PORT}


def stop():
    global _server, _thread
    if _server is not None:
        try:
            _server.shutdown()
            _server.server_close()
        except Exception:
            pass
    _server = None
    _thread = None
    return {"ok": True}


def status():
    return {"running": _server is not None, "received": _state["received"], "profile": _state.get("last_profile", "")}
