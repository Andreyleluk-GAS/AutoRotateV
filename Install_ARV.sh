#!/bin/bash

# Цвета для красивого вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Начинаем установку ядра ARV (AutoRotateV)...${NC}"

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
INSTALL_DIR="/opt/arv-core"
echo "Создание рабочей директории в $INSTALL_DIR..."
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

# Скачивание Python-скрипта по RAW-ссылке
GITHUB_RAW_URL="https://raw.githubusercontent.com/Andreyleluk-GAS/AutoRotateV/main/arv_main.py"

echo "Скачивание основного скрипта..."
wget -q -O arv_main.py $GITHUB_RAW_URL

if [ ! -f "arv_main.py" ] || [ ! -s "arv_main.py" ]; then
    echo -e "${RED}Ошибка: Не удалось скачать Python-скрипт. Убедись, что файл arv_main.py существует в репозитории.${NC}"
    exit 1
fi

# Создание виртуального окружения
echo "Настройка окружения Python..."
python3 -m venv venv
source venv/bin/activate
pip install flask requests > /dev/null 2>&1

# Создание системной службы (systemd)
echo "Создание службы systemd..."
cat <<EOF > /etc/systemd/system/arv-core.service
[Unit]
Description=ARV Core Background Worker
After=network.target

[Service]
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/arv_main.py
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=arv-core

[Install]
WantedBy=multi-user.target
EOF

# Запуск службы
echo "Запуск фонового процесса..."
systemctl daemon-reload
systemctl enable arv-core.service
systemctl restart arv-core.service

# Получение IP адреса сервера
SERVER_IP=$(curl -s ifconfig.me)

echo -e "${GREEN}==================================================================${NC}"
echo -e "${GREEN} Установка ARV успешно завершена! ${NC}"
echo -e " Ядро системы работает в фоновом режиме."
echo -e " Управление службой: ${GREEN}systemctl status arv-core${NC}"
echo -e " Посмотреть логи: ${GREEN}journalctl -u arv-core -f${NC}"
echo -e " "
echo -e " Веб-интерфейс доступен по адресу:"
echo -e " http://${SERVER_IP}:5000"
echo -e "${GREEN}==================================================================${NC}"