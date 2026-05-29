import os
import json
import time
import threading
import requests
from flask import Flask, request, render_template_string

# Конфигурационный файл
CONFIG_FILE = 'arv_config.json'

DEFAULT_CONFIG = {
    "panel_url": "http://127.0.0.1:12213/RBFAU7dIX2RqY7ecla",
    "username": "admin",
    "password": "password",
    "inbound_id": 1,
    "check_interval_seconds": 300,
    "pairs": [
        {"sni": "www.microsoft.com", "port": 44343, "is_active": False}
    ]
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
        return DEFAULT_CONFIG
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ARV Core Control</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f6f9; margin: 0; padding: 10px; color: #333; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
        h1 { color: #2c3e50; font-size: 24px; border-bottom: 2px solid #ecf0f1; padding-bottom: 10px; margin-top: 0; }
        h2 { color: #34495e; font-size: 20px; margin-top: 25px; margin-bottom: 15px; }
        .status-box { background-color: #e8f8f5; border-left: 5px solid #2ecc71; padding: 15px; border-radius: 6px; margin-bottom: 25px; font-size: 15px; line-height: 1.5; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 6px; font-weight: 600; font-size: 14px; color: #4a5568; }
        input[type="text"], input[type="number"], input[type="password"] { width: 100%; padding: 12px; border: 1px solid #cbd5e0; border-radius: 6px; box-sizing: border-box; font-size: 16px; transition: border-color 0.2s; }
        input:focus { border-color: #3498db; outline: none; }
        button { background-color: #3498db; color: white; padding: 14px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: 600; width: 100%; transition: background-color 0.2s; }
        button:hover { background-color: #2980b9; }
        button.delete { background-color: #e74c3c; padding: 8px 12px; font-size: 14px; width: auto; }
        button.delete:hover { background-color: #c0392b; }
        .table-responsive { overflow-x: auto; -webkit-overflow-scrolling: touch; margin-top: 10px; border-radius: 6px; }
        table { width: 100%; border-collapse: collapse; min-width: 400px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #e2e8f0; font-size: 15px; }
        th { background-color: #f8fafc; color: #4a5568; font-weight: 600; }
        .active-row { background-color: #ebf8ff; border-left: 3px solid #3498db; font-weight: bold; }
        
        /* Медиа-запрос для мелких экранов */
        @media (min-width: 600px) {
            button { width: auto; }
            body { padding: 20px; }
            .container { padding: 30px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Панель управления ARV Core</h1>
        
        <div class="status-box">
            <strong>Текущий статус службы:</strong> Мониторинг активен.<br>
            <strong>Текущая конфигурация:</strong> {{ active_pair.sni if active_pair else 'Не выбрана' }} : {{ active_pair.port if active_pair else '-' }}
        </div>

        <h2>1. Настройки доступа к ядру (API)</h2>
        <form action="/save_settings" method="POST" style="background: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0;">
            <div class="form-group">
                <label>API URL (включая WebBasePath):</label>
                <input type="text" name="panel_url" value="{{ config.panel_url }}" required>
            </div>
            <div class="form-group">
                <label>Логин:</label>
                <input type="text" name="username" value="{{ config.username }}" required>
            </div>
            <div class="form-group">
                <label>Пароль:</label>
                <input type="password" name="password" value="{{ config.password }}" required>
            </div>
            <div class="form-group">
                <label>Идентификатор потока (ID):</label>
                <input type="number" name="inbound_id" value="{{ config.inbound_id }}" required>
            </div>
            <div class="form-group">
                <label>Интервал проверки (сек):</label>
                <input type="number" name="check_interval_seconds" value="{{ config.check_interval_seconds }}" required>
            </div>
            <button type="submit">Сохранить настройки API</button>
        </form>

        <h2>2. Добавление в пул ротации</h2>
        <form action="/add" method="POST">
            <div class="form-group">
                <label>Хост (SNI):</label>
                <input type="text" name="sni" placeholder="например, www.apple.com" required>
            </div>
            <div class="form-group">
                <label>Порт:</label>
                <input type="number" name="port" placeholder="например, 44343" required>
            </div>
            <button type="submit" style="background-color: #2ecc71;">Добавить комбинацию</button>
        </form>

        <h2>3. Активный пул комбинаций</h2>
        <div class="table-responsive">
            <table>
                <thead>
                    <tr>
                        <th>Хост (SNI)</th>
                        <th>Порт</th>
                        <th>Статус</th>
                        <th>Удалить</th>
                    </tr>
                </thead>
                <tbody>
                    {% for pair in config.pairs %}
                    <tr class="{% if pair.is_active %}active-row{% endif %}">
                        <td>{{ pair.sni }}</td>
                        <td>{{ pair.port }}</td>
                        <td>{{ 'АКТИВЕН' if pair.is_active else 'Ожидание' }}</td>
                        <td>
                            <a href="/delete/{{ loop.index0 }}"><button class="delete">×</button></a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    config = load_config()
    active_pair = next((p for p in config['pairs'] if p.get('is_active')), None)
    return render_template_string(HTML_TEMPLATE, config=config, active_pair=active_pair)

@app.route('/add', methods=['POST'])
def add_pair():
    config = load_config()
    sni = request.form.get('sni')
    port = int(request.form.get('port'))
    config['pairs'].append({"sni": sni, "port": port, "is_active": False})
    save_config(config)
    return '<script>window.location.href="/";</script>'

@app.route('/delete/<int:index>')
def delete_pair(index):
    config = load_config()
    if 0 <= index < len(config['pairs']):
        config['pairs'].pop(index)
        save_config(config)
    return '<script>window.location.href="/";</script>'

@app.route('/save_settings', methods=['POST'])
def save_settings():
    config = load_config()
    config['panel_url'] = request.form.get('panel_url')
    config['username'] = request.form.get('username')
    config['password'] = request.form.get('password')
    config['inbound_id'] = int(request.form.get('inbound_id'))
    config['check_interval_seconds'] = int(request.form.get('check_interval_seconds'))
    save_config(config)
    return '<script>window.location.href="/";</script>'

# Логика фонового воркера ротации
def core_api_request(config, active_session, endpoint, data=None):
    url = f"{config['panel_url'].rstrip('/')}{endpoint}"
    try:
        if data:
            res = active_session.post(url, data=data, timeout=10)
        else:
            res = active_session.post(url, timeout=10)
        return res.json()
    except Exception as e:
        print(f"[Ошибка API]: {e}")
        return None

def login_to_core(config, session):
    login_url = f"{config['panel_url'].rstrip('/')}/login"
    data = {"username": config['username'], "password": config['password']}
    try:
        res = session.post(login_url, data=data, timeout=10)
        return res.status_code == 200
    except:
        return False

def rotate_stream(config, next_pair):
    session = requests.Session()
    if not login_to_core(config, session):
        print("[ARV Worker] Ошибка авторизации в API ядра")
        return False
    
    # Получаем текущие настройки потока
    get_url = f"/panel/api/inbounds/get/{config['inbound_id']}"
    stream_data = core_api_request(config, session, get_url)
    if not stream_data or not stream_data.get('success'):
        print("[ARV Worker] Не удалось получить данные потока")
        return False
    
    obj = stream_data['obj']
    
    try:
        stream_settings = json.loads(obj['streamSettings'])
        if 'realitySettings' in stream_settings:
            stream_settings['realitySettings']['serverNames'] = [next_pair['sni']]
            stream_settings['realitySettings']['dest'] = f"{next_pair['sni']}:443"
        obj['streamSettings'] = json.dumps(stream_settings)
    except Exception as e:
        print(f"[ARV Worker] Ошибка разбора конфигурации: {e}")
        return False

    obj['port'] = next_pair['port']
    
    update_url = f"/panel/api/inbounds/update/{config['inbound_id']}"
    update_res = core_api_request(config, session, update_url, data=obj)
    
    if update_res and update_res.get('success'):
        print(f"[ARV Worker] Успешное переключение на конфигурацию {next_pair['sni']}:{next_pair['port']}")
        return True
    else:
        print("[ARV Worker] Не удалось обновить поток через API")
        return False

def check_connection_health(port):
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(('127.0.0.1', port))
        s.close()
        return True
    except:
        return False

def rotation_worker():
    while True:
        try:
            config = load_config()
            pairs = config.get('pairs', [])
            if not pairs:
                time.sleep(10)
                continue
                
            active_pair = next((p for p in pairs if p.get('is_active')), None)
            
            if not active_pair:
                pairs[0]['is_active'] = True
                save_config(config)
                rotate_stream(config, pairs[0])
                active_pair = pairs[0]

            is_healthy = check_connection_health(active_pair['port'])
            
            if not is_healthy:
                print(f"[ARV Worker] Обнаружена недоступность порта {active_pair['port']}. Инициализация ротации...")
                curr_idx = pairs.index(active_pair)
                pairs[curr_idx]['is_active'] = False
                
                next_idx = (curr_idx + 1) % len(pairs)
                pairs[next_idx]['is_active'] = True
                
                save_config(config)
                rotate_stream(config, pairs[next_idx])
                
        except Exception as e:
            print(f"[ARV Worker Критическая ошибка]: {e}")
            
        config = load_config()
        time.sleep(config.get('check_interval_seconds', 300))

if __name__ == '__main__':
    t = threading.Thread(target=rotation_worker, daemon=True)
    t.start()
    
    panel_port = int(os.environ.get('ARV_PORT', 5000))
    app.run(host='0.0.0.0', port=panel_port)