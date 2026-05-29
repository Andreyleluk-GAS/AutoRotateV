import os
import json
import time
import threading
import requests
import urllib3
from urllib.parse import urlparse
from flask import Flask, request, render_template_string

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG_FILE = 'arv_config.json'

DEFAULT_CONFIG = {
    "panel_url": "https://like.dmtr.ru:12213/RBFAU7dIX2RqY7ecla",
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

def get_working_session(config):
    """Умная функция обхода защиты 3X-UI с подменой заголовков и маршрутов"""
    username = config.get('username', '').strip()
    password = config.get('password', '').strip()
    raw_url = config.get('panel_url', '').rstrip('/')
    
    if not raw_url:
        return None, None, None, "URL не указан"
        
    parsed = urlparse(raw_url)
    original_host = parsed.netloc
    port_str = f":{parsed.port}" if parsed.port else ""
    local_url = f"{parsed.scheme}://127.0.0.1{port_str}{parsed.path}"
    
    # Сначала пробуем внешний адрес, если блокирует - идем через локалхост с подменой Host
    urls_to_try = [
        {"url": raw_url, "host_header": None},
        {"url": local_url, "host_header": original_host}
    ]
    
    last_error = "Нет связи"
    for attempt in urls_to_try:
        url = attempt['url']
        try:
            login_url = f"{url}/login"
            payload = {"username": username, "password": password}
            
            # 100% имитация браузера и обход CSRF-защиты
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": f"{parsed.scheme}://{original_host}",
                "Referer": f"{raw_url}/"
            }
            if attempt['host_header']:
                headers["Host"] = attempt['host_header']
                
            session = requests.Session()
            res = session.post(login_url, data=payload, headers=headers, timeout=5, verify=False)
            
            if res.status_code == 200:
                try:
                    result = res.json()
                    if result.get('success', False):
                        return session, url, headers, "Успешно подключено к 3X-UI!"
                    else:
                        last_error = f"Ответ 3X-UI: {result.get('msg', 'Неверный логин/пароль')}"
                except:
                    return session, url, headers, "Подключено (Без JSON)"
            elif res.status_code == 404:
                last_error = f"Ошибка 404: Проверьте правильность WebBasePath"
            elif res.status_code == 403:
                last_error = f"Ошибка 403: Защита 3X-UI заблокировала вход ({'Внешний IP' if not attempt['host_header'] else 'Локальный IP'})"
            else:
                last_error = f"Ошибка HTTP {res.status_code}"
        except Exception as e:
            last_error = f"Сетевая ошибка: {str(e)[:30]}"
            
    return None, None, None, last_error

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
        .status-box { background-color: #e8f8f5; border-left: 5px solid #2ecc71; padding: 15px; border-radius: 6px; margin-bottom: 25px; font-size: 15px; line-height: 1.6; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 6px; font-weight: 600; font-size: 14px; color: #4a5568; }
        input[type="text"], input[type="number"], input[type="password"] { width: 100%; padding: 12px; border: 1px solid #cbd5e0; border-radius: 6px; box-sizing: border-box; font-size: 16px; transition: border-color 0.2s; }
        input:focus { border-color: #3498db; outline: none; }
        button { background-color: #3498db; color: white; padding: 14px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: 600; width: 100%; transition: background-color 0.2s; }
        button:hover { background-color: #2980b9; }
        button.edit-btn { background-color: #7f8c8d; width: auto; padding: 8px 15px; font-size: 14px; margin-top: 10px; }
        button.edit-btn:hover { background-color: #95a5a6; }
        button.delete { background-color: #e74c3c; padding: 8px 12px; font-size: 14px; width: auto; }
        button.delete:hover { background-color: #c0392b; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #e2e8f0; font-size: 15px; }
        th { background-color: #f8fafc; color: #4a5568; font-weight: 600; }
        .active-row { background-color: #ebf8ff; border-left: 3px solid #3498db; font-weight: bold; }
        .badge-success { color: #27ae60; font-weight: bold; background: #e8f8f5; padding: 2px 8px; border-radius: 4px; display: inline-block; }
        .badge-error { color: #c0392b; font-weight: bold; background: #fce4d6; padding: 2px 8px; border-radius: 4px; display: inline-block; }
        @media (min-width: 600px) { button { width: auto; } body { padding: 20px; } .container { padding: 30px; } }
    </style>
</head>
<body>
    <div class="container">
        <h1>Панель управления ARV Core</h1>
        
        <div class="status-box" style="{% if not api_connected %}border-left-color: #e74c3c;{% endif %}">
            <strong>Связь с ядром (API):</strong> 
            {% if api_connected %}
                <span class="badge-success">{{ api_msg }} ✓</span>
            {% else %}
                <span class="badge-error">{{ api_msg }} ✗</span>
            {% endif %}
            <br>
            <strong>Текущий статус службы:</strong> Мониторинг активен.<br>
            <strong>Текущая конфигурация:</strong> {{ active_pair.sni if active_pair else 'Не выбрана' }} : {{ active_pair.port if active_pair else '-' }}
        </div>

        <h2>1. Настройки доступа к ядру (API)</h2>
        {% if api_connected and not edit_mode %}
            <div style="background: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; border-left: 5px solid #3498db;">
                <p style="margin: 0 0 10px 0; color: #2c3e50;"><strong>Сервер:</strong> {{ config.panel_url }}</p>
                <p style="margin: 0 0 10px 0; color: #2c3e50;"><strong>ID потока:</strong> {{ config.inbound_id }} | <strong>Интервал:</strong> {{ config.check_interval_seconds }} сек.</p>
                <a href="/?edit=1"><button class="edit-btn">Изменить настройки</button></a>
            </div>
        {% else %}
            <form action="/save_settings" method="POST" style="background: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0;">
                <div class="form-group">
                    <label>Внешний URL панели (тот, что вы открываете в браузере):</label>
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
                    <label>ID потока:</label>
                    <input type="number" name="inbound_id" value="{{ config.inbound_id }}" required>
                </div>
                <div class="form-group">
                    <label>Интервал (сек):</label>
                    <input type="number" name="check_interval_seconds" value="{{ config.check_interval_seconds }}" required>
                </div>
                <button type="submit">Сохранить и подключиться</button>
            </form>
        {% endif %}

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

        <h2>3. Активный пул</h2>
        <div style="overflow-x: auto;">
            <table>
                <thead>
                    <tr><th>Хост (SNI)</th><th>Порт</th><th>Статус</th><th>Удалить</th></tr>
                </thead>
                <tbody>
                    {% for pair in config.pairs %}
                    <tr class="{% if pair.is_active %}active-row{% endif %}">
                        <td>{{ pair.sni }}</td><td>{{ pair.port }}</td>
                        <td>{{ 'АКТИВЕН' if pair.is_active else 'Ожидание' }}</td>
                        <td><a href="/delete/{{ loop.index0 }}"><button class="delete">×</button></a></td>
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
    _, _, _, api_msg = get_working_session(config)
    api_connected = "Успешно" in api_msg
    edit_mode = request.args.get('edit') == '1'
    return render_template_string(HTML_TEMPLATE, config=config, active_pair=active_pair, api_connected=api_connected, api_msg=api_msg, edit_mode=edit_mode)

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
    config['panel_url'] = request.form.get('panel_url', '').strip()
    config['username'] = request.form.get('username', '').strip()
    config['password'] = request.form.get('password', '').strip()
    config['inbound_id'] = int(request.form.get('inbound_id'))
    config['check_interval_seconds'] = int(request.form.get('check_interval_seconds'))
    save_config(config)
    return '<script>window.location.href="/";</script>'

def rotate_stream(config, next_pair):
    session, working_url, headers, _ = get_working_session(config)
    if not session:
        print("[ARV Worker] Ошибка авторизации в API")
        return False
        
    get_url = f"{working_url}/panel/api/inbounds/get/{config['inbound_id']}"
    
    # Пытаемся получить данные потока (сначала GET, резерв POST)
    res = session.get(get_url, headers=headers, timeout=5, verify=False)
    if res.status_code != 200:
        res = session.post(get_url, headers=headers, timeout=5, verify=False)
        
    if res.status_code != 200:
        return False
        
    stream_data = res.json()
    if not stream_data or not stream_data.get('success'):
        return False
        
    obj = stream_data['obj']
    
    try:
        stream_settings = json.loads(obj['streamSettings'])
        if 'realitySettings' in stream_settings:
            stream_settings['realitySettings']['serverNames'] = [next_pair['sni']]
            stream_settings['realitySettings']['dest'] = f"{next_pair['sni']}:443"
        obj['streamSettings'] = json.dumps(stream_settings)
    except Exception as e:
        print(f"[ARV Worker] Ошибка парсинга: {e}")
        return False

    obj['port'] = next_pair['port']
    
    update_url = f"{working_url}/panel/api/inbounds/update/{config['inbound_id']}"
    update_res = session.post(update_url, data=obj, headers=headers, timeout=5, verify=False)
    
    if update_res.status_code == 200 and update_res.json().get('success'):
        print(f"[ARV Worker] Переключено на {next_pair['sni']}:{next_pair['port']}")
        return True
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
            pass
            
        config = load_config()
        time.sleep(config.get('check_interval_seconds', 300))

if __name__ == '__main__':
    t = threading.Thread(target=rotation_worker, daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=int(os.environ.get('ARV_PORT', 5000)))