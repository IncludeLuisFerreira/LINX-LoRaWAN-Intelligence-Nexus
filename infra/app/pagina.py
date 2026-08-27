from datetime import datetime
from flask import Flask, request, render_template_string
from zoneinfo import ZoneInfo
import json
import paho.mqtt.client as mqtt
import threading

app = Flask(__name__)

historico_pacotes = []
total_pacotes = 0
MQTT_TOPIC = "application/+/device/+/event/up"

TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Monitor LoRaWAN - Luminosidade</title>
    <meta http-equiv="refresh" content="10">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0d1117; color: #c9d1d9; padding: 30px; }
        h1 { color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 12px; margin-bottom: 24px; font-size: 1.5rem; }
        .stats { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
        .stat-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 14px 20px; flex: 1; min-width: 140px; }
        .stat-card .label { font-size: 0.75rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; }
        .stat-card .value { font-size: 1.5rem; font-weight: 600; color: #f0f6fc; margin-top: 4px; }
        .empty { color: #8b949e; text-align: center; padding: 60px 20px; border: 2px dashed #30363d; border-radius: 8px; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 18px 22px; margin-bottom: 16px; display: flex; flex-wrap: wrap; gap: 16px 32px; }
        .card:hover { border-color: #58a6ff; }
        .card .field { min-width: 120px; }
        .card .field .label { font-size: 0.7rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.4px; }
        .card .field .value { font-size: 1.05rem; font-weight: 500; margin-top: 2px; }
        .card .field .value.luminosity { color: #d2a8ff; font-size: 1.3rem; }
        .card .field .value.battery { color: #7ee787; }
        .card .field .value.timestamp { color: #79c0ff; }
        .card .field .value.rssi { color: #ffa657; }
        .card .field .value.snr { color: #ff7b72; }
        .badge { display: inline-block; background: #21262d; padding: 2px 8px; border-radius: 12px; font-size: 0.7rem; color: #8b949e; margin-left: 8px; }
        footer { margin-top: 32px; text-align: center; color: #484f58; font-size: 0.8rem; }
    </style>
</head>
<body>
    <h1>Monitor de Luminosidade — LoRaWAN</h1>

    <div class="stats">
        <div class="stat-card">
            <div class="label">Total de pacotes</div>
            <div class="value">{{ total }}</div>
        </div>
        <div class="stat-card">
            <div class="label">Última medição</div>
            <div class="value" style="font-size:0.9rem">{{ ultima_medicao }}</div>
        </div>
    </div>

    {% if not pacotes %}
        <div class="empty">Aguardando primeiro uplink do dispositivo...</div>
    {% endif %}

    {% for pkt in pacotes %}
        {% set obj = pkt.get('object', {}) %}
        {% set rx = pkt.get('rxInfo', [{}])[0] %}
        {% set ts = pkt.get('nsTime') or pkt.get('time', '') %}
        <div class="card">
            <div class="field">
                <div class="label">Dispositivo</div>
                <div class="value">{{ pkt.get('deviceInfo', {}).get('deviceName', 'N/A') }}</div>
            </div>
            <div class="field">
                <div class="label">Data / Hora</div>
                <div class="value timestamp">{{ ts | format_ts }}</div>
            </div>
            <div class="field">
                <div class="label">Luminosidade (LDR)</div>
                <div class="value luminosity">{{ obj.get('ldr_value', '---') }}</div>
            </div>
            <div class="field">
                <div class="label">Bateria</div>
                <div class="value battery">{{ obj.get('volt_bateria', '---') }} V</div>
            </div>
            <div class="field">
                <div class="label">FCnt</div>
                <div class="value">{{ pkt.get('fCnt', '---') }}</div>
            </div>
            <div class="field">
                <div class="label">RSSI</div>
                <div class="value rssi">{{ rx.get('rssi', '---') }} dBm</div>
            </div>
            <div class="field">
                <div class="label">SNR</div>
                <div class="value snr">{{ rx.get('snr', '---') }} dB</div>
            </div>
            <div class="badge">FPort {{ pkt.get('fPort', '?') }}</div>
        </div>
    {% endfor %}
    <footer>Atualiza automática a cada 10s · infrastructure</footer>
</body>
</html>
"""

@app.template_filter('format_ts')
def format_timestamp(ts):
    if not ts:
        return '---'
    try:
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        tz = ZoneInfo('America/Sao_Paulo')
        dt_local = dt.astimezone(tz)
        return dt_local.strftime('%d/%m/%Y %H:%M:%S')
    except Exception:
        return str(ts)

@app.route('/', methods=['GET'])
def index():
    ultima = ''
    if historico_pacotes:
        ts_ultimo = historico_pacotes[0].get('nsTime') or historico_pacotes[0].get('time', '')
        ultima = format_timestamp(ts_ultimo) if ts_ultimo else ''
    return render_template_string(TEMPLATE, pacotes=historico_pacotes, ultima_medicao=ultima, total=total_pacotes)

def on_connect(client, userdata, flags, reason_code, properties):
    print(f"[MQTT] Conectado ao Mosquitto (rc={reason_code})", flush=True)
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    global total_pacotes
    try:
        dados = json.loads(msg.payload)
        total_pacotes += 1
        print(f"[MQTT] Uplink #{total_pacotes} — FCnt: {dados.get('fCnt')}, tópico: {msg.topic}", flush=True)
        historico_pacotes.insert(0, dados)
        if len(historico_pacotes) > 100:
            historico_pacotes.pop()
    except Exception as e:
        print(f"[MQTT] Erro: {e}", flush=True)

def start_mqtt():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect("mosquitto", 1883, 60)
        client.loop_start()
        print("[MQTT] Thread iniciada", flush=True)
    except Exception as e:
        print(f"[MQTT] Erro ao iniciar: {e}", flush=True)

if __name__ == '__main__':
    threading.Thread(target=start_mqtt, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
