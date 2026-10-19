#!/usr/bin/env python3
"""A Whale's Heart — Bridge v0.12"""
import json, os, socket, struct, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

HTTP_PORT = 8080
OSC_IN    = 57121
SC_PORT   = 57120
SC_HOST   = '127.0.0.1'
ROOT      = os.path.dirname(os.path.abspath(__file__))
DEBUG     = True   # set False to silence per-beat bridge logs

state = {'sc_ready': False, 'playing': False}
lock  = threading.Lock()
_last_gate_ms = [0.0]  # list for closure mutability

def _p4(n): return n + (4 - n % 4) % 4
def _es(s):
    b = (s + '\x00').encode('ascii')
    return b.ljust(_p4(len(b)), b'\x00')
def _ef(f): return struct.pack('>f', float(f))
def _ei(i): return struct.pack('>i', int(i))

def osc(addr, *args):
    tags, data = ',', b''
    for a in args:
        if   isinstance(a, float): tags += 'f'; data += _ef(a)
        elif isinstance(a, int):   tags += 'i'; data += _ei(a)
        else:                      tags += 's'; data += _es(str(a))
    return _es(addr) + _es(tags) + data

def send_osc(addr, *args):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(osc(addr, *args), (SC_HOST, SC_PORT))
    s.close()

def osc_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', OSC_IN)); s.settimeout(1)
    print(f'  OSC  :{OSC_IN}')
    while True:
        try:
            data, _ = s.recvfrom(1024)
            i = data.index(b'\x00')
            addr = data[:i].decode('ascii', errors='ignore')
            if addr == '/whale/ready':
                with lock: state['sc_ready'] = True
                print('  ✓  SuperCollider ready')
        except socket.timeout: continue
        except Exception as e: print(f'  OSC error: {e}')

class H(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def _json(self, d, c=200):
        b = json.dumps(d).encode()
        try:
            self.send_response(c)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(b))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b)
        except (BrokenPipeError, ConnectionResetError): pass

    def do_OPTIONS(self):
        try:
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin',  '*')
            self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError): pass

    def do_GET(self):
        p = urlparse(self.path).path
        try:
            if p == '/api/state':
                with lock: self._json(dict(state))
            elif p in ('/', '/prototype.html'):
                f = os.path.join(ROOT, 'html', 'prototype.html')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                with open(f, 'rb') as fh: self.wfile.write(fh.read())
            else:
                self.send_response(404); self.end_headers()
        except (BrokenPipeError, ConnectionResetError): pass

    def do_POST(self):
        p   = urlparse(self.path).path
        n   = int(self.headers.get('Content-Length', 0))
        bod = json.loads(self.rfile.read(n)) if n else {}
        try:
            if p == '/api/play':
                send_osc('/whale/play')
                with lock: state['playing'] = True
                self._json({'ok': True})

            elif p == '/api/pause':
                send_osc('/whale/pause')
                with lock: state['playing'] = False
                self._json({'ok': True})

            elif p == '/api/stop':
                # End-of-track: silence ocean + current beat
                send_osc('/whale/stop')
                with lock: state['playing'] = False
                self._json({'ok': True})

            elif p == '/api/setmode':
                # Speaker mode switch — body: {"mode": "stereo" | "quad"}
                mode = str(bod.get('mode', 'stereo'))
                if mode not in ('stereo', 'quad'):
                    mode = 'stereo'
                send_osc('/whale/setmode', mode)
                if DEBUG:
                    print(f'  [BRIDGE setmode] mode={mode}')
                self._json({'ok': True, 'mode': mode})

            elif p == '/api/gate':
                # Depth inflection event — fire heartbeat in SC immediately
                # spatX/spatY ∈ [-1,1]: west/south = -1, east/north = +1
                if DEBUG:
                    import time
                    now_ms = time.monotonic() * 1000.0
                    dt     = now_ms - _last_gate_ms[0] if _last_gate_ms[0] else 0
                    _last_gate_ms[0] = now_ms
                    print(f'  [BRIDGE gate] dt={dt:.0f}ms  depth={bod.get("depth",0):.1f}m  bpm={bod.get("bpm",0):.1f}')
                send_osc('/whale/gate',
                    float(bod.get('amplitude', 0.5)),
                    float(bod.get('rate',      1.0)),
                    str(  bod.get('type',      'surface')),
                    float(bod.get('depth',     0.0)),
                    float(bod.get('bpm',       20.0)),
                    float(bod.get('spatX',     0.0)),
                    float(bod.get('spatY',     0.0)))
                self._json({'ok': True})

            else:
                self.send_response(404); self.end_headers()
        except (BrokenPipeError, ConnectionResetError): pass

if __name__ == '__main__':
    threading.Thread(target=osc_server, daemon=True).start()
    srv = HTTPServer(('', HTTP_PORT), H)
    print(f'  HTTP http://localhost:{HTTP_PORT}')
    try: srv.serve_forever()
    except KeyboardInterrupt: print('\nBridge stopped.')
