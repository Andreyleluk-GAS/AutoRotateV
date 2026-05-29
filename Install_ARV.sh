#!/bin/bash

# Цвета для красивого вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Начинаем установку 3X-UI Auto-Rotator...${NC}"

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Ошибка: Пожалуйста, запустите скрипт с правами root (sudo -i)${NC}"
  exit 1
fi

# Установка системных зависимостей
echo "Обновление списка пакетов и установка зависимостей..."
apt-get update -q
apt-get install -y python3 python3-pip python3-venv curl wget -q

# Подготовка директории
INSTALL_DIR="/opt/3x-ui-rotator"
echo "Создание рабочей директории в $INSTALL_DIR..."
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

# Скачивание Python-скрипта по ПРАВИЛЬНОЙ RAW-ссылке
GITHUB_RAW_URL="https://raw.githubusercontent.com/Andreyleluk-GAS/AutoRotateV/main/vpn_auto_rotator.py"

echo "Скачивание основного скрипта..."
wget -q -O vpn_auto_rotator.py $GITHUB_RAW_URL

if [ ! -f "vpn_auto_rotator.py" ] || [ ! -s "vpn_auto_rotator.py" ]; then
    echo -e "${RED}Ошибка: Не удалось скачать Python-скрипт. Убедись, что файл vpn_auto_rotator.py существует в репозитории.${NC}"
    exit 1
fi

# Создание виртуального окружения
echo "Настройка окружения Python..."
python3 -m venv venv
source venv/bin/activate
pip install flask requests > /dev/null 2>&1

# Создание системной службы (systemd)
echo "Создание службы systemd..."
cat <<EOF > /etc/systemd/system/3x-ui-rotator.service
[Unit]
Description=3X-UI Auto Rotator Panel & Worker
After=network.target

[Service]
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/vpn_auto_rotator.py
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=3x-ui-rotator

[Install]
WantedBy=multi-user.target
EOF

# Запуск службы
echo "Запуск фонового процесса..."
systemctl daemon-reload
systemctl enable 3x-ui-rotator.service
systemctl restart 3x-ui-rotator.service

# Получение IP адреса сервера
SERVER_IP=$(curl -s ifconfig.me)

echo -e "${GREEN}==================================================================${NC}"
echo -e "${GREEN} Установка успешно завершена! ${NC}"
echo -e " Панель авторотации работает в фоновом режиме."
echo -e " Управление службой: ${GREEN}systemctl status 3x-ui-rotator${NC}"
echo -e " Посмотреть логи: ${GREEN}journalctl -u 3x-ui-rotator -f${NC}"
echo -e " "
echo -e " Веб-интерфейс доступен по адресу:"
echo -e " http://${SERVER_IP}:5000"
echo -e "${GREEN}==================================================================${NC}"
