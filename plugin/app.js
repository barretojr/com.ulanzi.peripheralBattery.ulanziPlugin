// Botoes de bateria (Rapoo / MCHOSE) no tema do HardwareMonitor. Dados vem do leitor local (sidecar/battery_server.py).
const URL_BATTERY = 'http://127.0.0.1:8765/battery';
const KINDS = { rapoo: { label: 'RAPOO' }, mchose: { label: 'MCHOSE' } };
const ACTIONS = {}; // context -> kind
let data = null;    // ultima resposta do leitor; null = leitor fora do ar
let lastKey = {};

function levelColor(l) { return l <= 15 ? '#ff3b4d' : l <= 30 ? '#ff9f1c' : '#00ffcc'; }

function drawIcon(label, d) {
  const c = document.createElement('canvas'); c.width = c.height = 144;
  const x = c.getContext('2d');
  // fundo igual ao HardwareMonitor
  const g = x.createLinearGradient(0, 0, 144, 144);
  g.addColorStop(0, '#0f0f1a'); g.addColorStop(0.5, '#1a1a2e'); g.addColorStop(1, '#0a0a15');
  x.fillStyle = g; x.fillRect(0, 0, 144, 144);
  const rg = x.createRadialGradient(72, 50, 0, 72, 50, 80);
  rg.addColorStop(0, 'rgba(255,255,255,0.05)'); rg.addColorStop(1, 'rgba(255,255,255,0)');
  x.fillStyle = rg; x.fillRect(0, 0, 144, 144);

  x.textAlign = 'center'; x.font = 'bold 15px "Segoe UI", Arial, sans-serif';
  const off = !d; const color = off ? '#ff3b4d' : d.status === 'charging' ? '#00ffcc' : levelColor(d.level);
  x.fillStyle = off ? '#ff3b4d' : '#ff2bd6'; x.fillText(label, 72, 20);

  const cx = 72, cy = 80, r = 44;
  x.lineWidth = 8; x.lineCap = 'round';
  x.beginPath(); x.arc(cx, cy, r, 0, Math.PI * 2); x.strokeStyle = 'rgba(255,255,255,0.07)'; x.stroke();
  if (off) {
    x.fillStyle = color; x.font = 'bold 64px "Segoe UI", Arial, sans-serif'; x.fillText('!', cx, cy + 22);
    x.font = 'bold 12px "Segoe UI", Arial, sans-serif'; x.fillText(data === null ? 'SEM LEITOR' : 'DESLIGADO', cx, 138);
    return c.toDataURL('image/png');
  }
  const a0 = -Math.PI / 2, a1 = a0 + Math.max(0.02, d.level / 100) * Math.PI * 2;
  x.beginPath(); x.arc(cx, cy, r, a0, a1); x.strokeStyle = color + '4d'; x.lineWidth = 14; x.stroke(); // brilho
  x.beginPath(); x.arc(cx, cy, r, a0, a1); x.strokeStyle = color; x.lineWidth = 8; x.stroke();
  x.fillStyle = color; x.font = 'bold 40px "Segoe UI", Arial, sans-serif'; x.fillText(String(d.level), cx, cy + 14);
  x.font = 'bold 12px "Segoe UI", Arial, sans-serif'; x.fillStyle = '#8a8aa0';
  const sub = { charging: 'CARREGANDO', full: 'CHEIO', sleep: 'DORMINDO' }[d.status];
  x.fillText(sub || '%', cx, cy + 32);
  return c.toDataURL('image/png');
}

function render(context) {
  const kind = ACTIONS[context]; if (!kind) return;
  const d = data && data[kind]; // objeto, ou null/undefined = dispositivo desligado (ou leitor fora do ar se data===null)
  const key = d ? d.level + '|' + d.status : data ? 'off' : 'noserver';
  if (lastKey[context] === key) return;
  lastKey[context] = key;
  $UD.setBaseDataIcon(context, drawIcon(KINDS[kind].label, d || null), '');
}

async function poll() {
  try { data = await (await fetch(URL_BATTERY, { cache: 'no-store' })).json(); } catch (e) { data = null; }
  Object.keys(ACTIONS).forEach(render);
}

$UD.connect('com.ulanzi.peripheralBattery');
$UD.onAdd((jsn) => {
  ACTIONS[jsn.context] = (jsn.uuid || '').toLowerCase().includes('mchose') ? 'mchose' : 'rapoo';
  delete lastKey[jsn.context]; render(jsn.context);
});
$UD.onRun((jsn) => { delete lastKey[jsn.context]; poll(); }); // apertar o botao forca atualizar
$UD.onClear && $UD.onClear((jsn) => { (jsn.param || []).forEach(p => delete ACTIONS[p.context]); });
setInterval(poll, 5000); poll();
