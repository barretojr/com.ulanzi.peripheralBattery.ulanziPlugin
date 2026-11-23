# Peripheral Battery (Ulanzi D200H)

Botões do Ulanzi que mostram a bateria do **mouse Rapoo VT9 Pro** e do **fone MCHOSE V9 Pro**, com precisão de 1% e no tema do plugin Hardware Monitor.

## Como funciona
- `sidecar/battery_server.py` lê os dois dispositivos por HID (só Python padrão, sem instalar nada) e serve `http://127.0.0.1:8765/battery`.
  - **Rapoo** (`24AE:1601`): o dongle manda a bateria sozinho a cada ~3 s no canal `0xFF00` de 7 bytes; o último byte é a %.
  - **MCHOSE** (`291D:385D`): o script pergunta a cada 20 s no canal `0xFF90` (relatório `0x55`, `65 01 00…`); resposta `[0x55, 0x65, bateria, estado]` com estado 2 descarregando, 3 carregando, 4 cheio, `0x1a` dormindo.
- `plugin/app.js` desenha os botões e consulta o leitor a cada 5 s.

## Instalar
1. Copie esta pasta para `%APPDATA%\Ulanzi\UlanziDeck\Plugins\com.ulanzi.peripheralBattery.ulanziPlugin`.
2. Rode o leitor: `pythonw -I sidecar\battery_server.py`. Para iniciar com o Windows, crie um atalho para esse comando em `shell:startup`.
3. Reinicie o UlanziStudio e arraste os botões da categoria **Peripheral Battery**.

## Limites conhecidos
- O estado "carregando" do Rapoo (`byte 5 == 2`) é hipótese vista na escuta, não confirmada; o nível está certo.
- Outro modelo de mouse/fone pode ter outro VID/PID ou comando.
