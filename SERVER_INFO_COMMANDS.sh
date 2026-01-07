#!/bin/bash
# Скрипт для сбора информации о сервере
# Выполните на сервере и пришлите результаты

echo "=========================================="
echo "ИНФОРМАЦИЯ О СЕРВЕРЕ И ПРОЕКТЕ"
echo "=========================================="
echo ""

echo "1. ПРОЦЕССЫ PYTHON/FLASK:"
echo "------------------------"
ps aux | grep -E "(python|flask|gunicorn|uwsgi)" | grep -v grep
echo ""

echo "2. ЗАНЯТЫЕ ПОРТЫ:"
echo "----------------"
echo "Python процессы:"
netstat -tulpn 2>/dev/null | grep python || ss -tulpn | grep python
echo ""
echo "Порты 5000-5010:"
netstat -tulpn 2>/dev/null | grep -E ":(500[0-9]|5010)" || ss -tulpn | grep -E ":(500[0-9]|5010)"
echo ""

echo "3. КОНФИГУРАЦИЯ ПРОЕКТА:"
echo "-----------------------"
cd /var/www/calc.figurebase.ru 2>/dev/null || cd ~/calc.figurebase.ru 2>/dev/null || echo "Директория проекта не найдена!"
if [ -d "/var/www/calc.figurebase.ru" ] || [ -d "~/calc.figurebase.ru" ]; then
    echo "Текущая директория: $(pwd)"
    echo ""
    echo "FLASK_PORT и DATABASE_URL из .env:"
    grep -E "(FLASK_PORT|DATABASE_URL|FLASK_HOST)" .env 2>/dev/null || echo ".env не найден или переменные отсутствуют"
    echo ""
    echo "Структура проекта:"
    ls -la | head -20
    echo ""
    echo "Git статус:"
    git status 2>/dev/null || echo "Не Git репозиторий"
    echo ""
    echo "Git remote:"
    git remote -v 2>/dev/null
    echo ""
    echo "Последние коммиты:"
    git log --oneline -5 2>/dev/null
fi
echo ""

echo "4. ВЕБ-СЕРВЕР:"
echo "-------------"
echo "Apache:"
systemctl status apache2 2>/dev/null | head -5 || systemctl status httpd 2>/dev/null | head -5 || echo "Apache не найден"
echo ""
echo "Nginx:"
systemctl status nginx 2>/dev/null | head -5 || echo "Nginx не найден"
echo ""

echo "5. SYSTEMD СЕРВИСЫ:"
echo "---------------------"
systemctl list-units --type=service | grep -E "(calc|figure|gunicorn|uwsgi|flask)" || echo "Сервисы не найдены"
echo ""

echo "6. SUPERVISOR:"
echo "-------------"
supervisorctl status 2>/dev/null | grep -E "(calc|figure)" || echo "Supervisor не используется или процессы не найдены"
echo ""

echo "7. POSTGRESQL:"
echo "-------------"
psql --version 2>/dev/null || echo "PostgreSQL не установлен"
echo ""
echo "Базы данных:"
sudo -u postgres psql -c "\l" 2>/dev/null | grep figure || echo "База figure_skating не найдена"
echo ""

echo "8. ЗАВИСИМОСТИ:"
echo "-------------"
if [ -d "/var/www/calc.figurebase.ru" ]; then
    cd /var/www/calc.figurebase.ru
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    fi
    pip3 list 2>/dev/null | grep -E "(Flask|WTF|psycopg)" || echo "Зависимости не найдены"
fi
echo ""

echo "9. WSGI КОНФИГУРАЦИЯ:"
echo "--------------------"
if [ -f "/var/www/calc.figurebase.ru/wsgi.py" ]; then
    cat /var/www/calc.figurebase.ru/wsgi.py
elif [ -f "~/calc.figurebase.ru/wsgi.py" ]; then
    cat ~/calc.figurebase.ru/wsgi.py
else
    echo "wsgi.py не найден"
fi
echo ""

echo "10. ЛОГИ (последние 10 строк):"
echo "------------------------------"
if [ -f "/var/www/calc.figurebase.ru/logs/app.log" ]; then
    tail -10 /var/www/calc.figurebase.ru/logs/app.log
elif [ -f "~/calc.figurebase.ru/logs/app.log" ]; then
    tail -10 ~/calc.figurebase.ru/logs/app.log
else
    echo "Логи не найдены"
fi
echo ""

echo "=========================================="
echo "СБОР ИНФОРМАЦИИ ЗАВЕРШЕН"
echo "=========================================="

