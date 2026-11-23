"""Le a bateria do mouse Rapoo VT9 Pro e do fone MCHOSE V9 Pro e serve em http://127.0.0.1:8765/battery.

Rapoo : o dongle (24AE:1601, canal 0xFF00 de 7 bytes) manda um pacote a cada ~3 s; ultimo byte = bateria %.
MCHOSE: pergunta a cada 20 s (mesmo pedido do app: relatorio 0x55 = 65 01 00..., canal 0xFF90);
        resposta [0x55, 0x65, bateria %, estado]  estado: 2 descarregando, 3 carregando, 4 cheio, 0x1a dormindo.
Somente Python padrao (ctypes), sem instalar nada.
"""
import ctypes, json, threading, time
from ctypes import wintypes as w
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8765
hid = ctypes.WinDLL('hid'); sa = ctypes.WinDLL('setupapi'); k32 = ctypes.WinDLL('kernel32', use_last_error=True)
class GUID(ctypes.Structure): _fields_ = [('a', w.DWORD), ('b', w.WORD), ('c', w.WORD), ('d', ctypes.c_ubyte * 8)]
class SPID(ctypes.Structure): _fields_ = [('cb', w.DWORD), ('g', GUID), ('f', w.DWORD), ('r', ctypes.c_void_p)]
class ATTR(ctypes.Structure): _fields_ = [('size', w.ULONG), ('vid', w.USHORT), ('pid', w.USHORT), ('ver', w.USHORT)]
class CAPS(ctypes.Structure): _fields_ = [('Usage', w.USHORT), ('UsagePage', w.USHORT), ('In', w.USHORT), ('Out', w.USHORT), ('Feat', w.USHORT), ('res', w.USHORT * 17), ('x', w.USHORT * 10)]
class OVL(ctypes.Structure): _fields_ = [('i', ctypes.c_void_p), ('ih', ctypes.c_void_p), ('off', w.DWORD), ('offh', w.DWORD), ('ev', ctypes.c_void_p)]
sa.SetupDiGetClassDevsW.restype = ctypes.c_void_p; k32.CreateFileW.restype = ctypes.c_void_p; k32.CreateEventW.restype = ctypes.c_void_p
VP = ctypes.c_void_p; INV = ctypes.c_void_p(-1).value

state = {'rapoo': None, 'mchose': None}  # {'level', 'status', 'ts'}

def find(vid, pid, want_in, want_out=None, up=None):
    """Caminho do canal HID pelo tamanho dos relatorios (e usage page, se dada)."""
    g = GUID(); hid.HidD_GetHidGuid(ctypes.byref(g))
    h = sa.SetupDiGetClassDevsW(ctypes.byref(g), None, None, 0x12); i = 0
    while True:
        d = SPID(); d.cb = ctypes.sizeof(SPID)
        if not sa.SetupDiEnumDeviceInterfaces(VP(h), None, ctypes.byref(g), i, ctypes.byref(d)): break
        i += 1
        n = w.DWORD(); sa.SetupDiGetDeviceInterfaceDetailW(VP(h), ctypes.byref(d), None, 0, ctypes.byref(n), None)
        buf = ctypes.create_string_buffer(n.value); ctypes.c_uint32.from_buffer(buf).value = 8
        if not sa.SetupDiGetDeviceInterfaceDetailW(VP(h), ctypes.byref(d), buf, n, None, None): continue
        path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
        hd = k32.CreateFileW(path, 0, 3, None, 3, 0, None)
        if hd in (None, INV): continue
        a = ATTR(); a.size = ctypes.sizeof(ATTR); found = None
        if hid.HidD_GetAttributes(VP(hd), ctypes.byref(a)) and (a.vid, a.pid) == (vid, pid):
            pp = VP(); hid.HidD_GetPreparsedData(VP(hd), ctypes.byref(pp)); c = CAPS(); hid.HidP_GetCaps(pp, ctypes.byref(c)); hid.HidD_FreePreparsedData(pp)
            if c.In == want_in and (want_out is None or c.Out == want_out) and (up is None or c.UsagePage == up): found = path
        k32.CloseHandle(VP(hd))
        if found: return found
    return None

def read_once(hd, size, timeout_ms, before=None):
    """Leitura de entrada com timeout; 'before' roda depois de armar a leitura (ex.: enviar pedido)."""
    ev = k32.CreateEventW(None, True, False, None); ro = OVL(); ro.ev = ev
    rb = (ctypes.c_ubyte * size)(); got = w.DWORD(0)
    k32.ReadFile(VP(hd), rb, size, ctypes.byref(got), ctypes.byref(ro))
    if before: before()
    if k32.WaitForSingleObject(VP(ev), timeout_ms) != 0:
        k32.CancelIo(VP(hd)); k32.CloseHandle(VP(ev)); return None
    k32.GetOverlappedResult(VP(hd), ctypes.byref(ro), ctypes.byref(got), False); k32.CloseHandle(VP(ev))
    return bytes(rb[:got.value])

def rapoo_loop():
    while True:
        path = find(0x24AE, 0x1601, 7, 7, 0xFF00)
        hd = k32.CreateFileW(path, 0x80000000, 3, None, 3, 0x40000000, None) if path else None
        if hd in (None, INV):
            time.sleep(5); continue
        while True:
            pkt = read_once(hd, 7, 15000)
            if pkt is None: state['rapoo'] = None; break          # sem pacote por 15 s: mouse desligado/fora
            if pkt[0] == 0xBB and len(pkt) == 7:
                # shortcut: byte de estado (pkt[5]==2 => carregando) e hipotese vista na escuta, nao confirmada
                state['rapoo'] = {'level': pkt[6], 'status': 'charging' if pkt[5] == 2 else 'discharge', 'ts': time.time()}
        k32.CloseHandle(VP(hd))

def mchose_poll():
    path = find(0x291D, 0x385D, 64, 64, 0xFF90)
    hd = k32.CreateFileW(path, 0xC0000000, 3, None, 3, 0x40000000, None) if path else None
    if hd in (None, INV): return None
    req = (ctypes.c_ubyte * 64)(); req[0] = 0x55; req[1] = 0x65; req[2] = 0x01
    def send():
        o = OVL(); o.ev = k32.CreateEventW(None, True, False, None); n = w.DWORD(0)
        if not k32.WriteFile(VP(hd), req, 64, ctypes.byref(n), ctypes.byref(o)) and ctypes.get_last_error() == 997:
            k32.WaitForSingleObject(VP(o.ev), 1000)
    r = read_once(hd, 64, 1500, send)
    k32.CloseHandle(VP(hd))
    if r and len(r) >= 4 and r[0] == 0x55 and r[1] == 0x65:
        st = {2: 'discharge', 3: 'charging', 4: 'full', 0x1A: 'sleep'}.get(r[3], 'discharge')
        return {'level': r[2], 'status': st, 'ts': time.time()}
    return None

def mchose_loop():
    while True:
        try: state['mchose'] = mchose_poll() or (state['mchose'] if state['mchose'] and time.time() - state['mchose']['ts'] < 90 else None)
        except Exception: pass
        time.sleep(20)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(state).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*'); self.send_header('Content-Length', str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass

if __name__ == '__main__':
    for f in (rapoo_loop, mchose_loop): threading.Thread(target=f, daemon=True).start()
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
