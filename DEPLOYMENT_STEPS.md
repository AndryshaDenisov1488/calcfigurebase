# Пошаговое развертывание обновлений на сервере

## 🔄 Шаг 1: Коммит и Push изменений (на локальной машине)

Выполните на **локальной машине** (Windows):

```powershell
# Переходим в директорию проекта
cd "C:\Users\User\Documents\Разработки\ФФКМ\calc.figurebase.ru"

# Проверяем статус
git status

# Добавляем все изменения
git add .

# Коммитим изменения
git commit -m "Добавлены улучшения: CSRF защита, обработка ошибок БД, пагинация, health check, security headers, connection pooling для PostgreSQL"

# Пушим на GitHub
git push origin main
```

Если будет ошибка, используйте:
```powershell
git push origin main --force-with-lease
```

---

## 📥 Шаг 2: Pull изменений на сервере

Выполните на **сервере** (Linux):

```bash
# Переходим в директорию проекта
cd /var/www/calc.figurebase.ru

# Сохраняем текущий .env (ВАЖНО!)
cp .env .env.backup

# Проверяем статус Git
git status

# Получаем последние изменения
git fetch origin

# Смотрим что изменилось
git log HEAD..origin/main --oneline

# Делаем pull
git pull origin main
```

Если будут конфликты:
```bash
# Если есть конфликты в .env, оставляем свой
git checkout --ours .env
git add .env
git commit -m "Сохраняем локальный .env"
```

---

## 🔧 Шаг 3: Обновление зависимостей на сервере

```bash
cd /var/www/calc.figurebase.ru

# Активируем виртуальное окружение (если используется)
source venv/bin/activate  # или: source env/bin/activate

# Обновляем зависимости
pip3 install -r requirements.txt --upgrade

# Проверяем что установлено
pip3 list | grep -E "(Flask-WTF|WTForms|psycopg)"
```

---

## ⚙️ Шаг 4: Обновление конфигурации .env

```bash
cd /var/www/calc.figurebase.ru

# Проверяем текущий .env
cat .env

# Добавляем новые переменные (если их нет)
# Откройте .env в редакторе и добавьте:

# CSRF Protection
WTF_CSRF_ENABLED=True
WTF_CSRF_TIME_LIMIT=3600

# Host и Port (если нужно изменить)
FLASK_HOST=127.0.0.1
FLASK_PORT=5001

# Connection Pooling для PostgreSQL (если используется PostgreSQL)
DB_POOL_SIZE=10
DB_POOL_RECYCLE=3600
DB_POOL_PRE_PING=True
DB_MAX_OVERFLOW=20
```

---

## 🗄️ Шаг 5: Миграция базы данных (если нужно)

### Если используете SQLite и хотите перейти на PostgreSQL:

```bash
cd /var/www/calc.figurebase.ru

# 1. Создайте бэкап SQLite
cp instance/figure_skating.db backups/before_migration_$(date +%Y%m%d_%H%M%S).db

# 2. Создайте PostgreSQL базу (если еще не создана)
sudo -u postgres psql -c "CREATE DATABASE figure_skating;"
sudo -u postgres psql -c "CREATE USER figure_user WITH PASSWORD 'your_secure_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE figure_skating TO figure_user;"

# 3. Обновите .env
# Измените DATABASE_URL на:
# DATABASE_URL=postgresql://figure_user:your_secure_password@localhost/figure_skating

# 4. Создайте структуру таблиц в PostgreSQL
source venv/bin/activate  # если используется venv
flask db upgrade

# 5. Запустите миграцию данных
python3 scripts/migrate_sqlite_to_postgresql.py
```

### Если уже используете PostgreSQL:

```bash
# Просто обновите структуру БД
cd /var/www/calc.figurebase.ru
source venv/bin/activate  # если используется venv
flask db upgrade
```

---

## 🔄 Шаг 6: Перезапуск приложения

### Вариант A: Если используется systemd service

```bash
# Проверяем статус
sudo systemctl status calc.figurebase.ru
# или
sudo systemctl status gunicorn
# или
sudo systemctl status uwsgi

# Перезапускаем
sudo systemctl restart calc.figurebase.ru
# или
sudo systemctl restart gunicorn
# или
sudo systemctl restart uwsgi

# Проверяем логи
sudo journalctl -u calc.figurebase.ru -f
# или
sudo journalctl -u gunicorn -f
```

### Вариант B: Если используется supervisor

```bash
sudo supervisorctl restart calc.figurebase.ru
sudo supervisorctl status calc.figurebase.ru
```

### Вариант C: Если запущено вручную

```bash
# Находим процесс
ps aux | grep python | grep app.py

# Убиваем процесс (замените PID на реальный)
kill -HUP <PID>

# Или если используете gunicorn
pkill -HUP gunicorn
```

### Вариант D: Если используется Apache/Nginx + mod_wsgi

```bash
# Перезапускаем Apache
sudo systemctl restart apache2
# или
sudo systemctl restart httpd

# Перезапускаем Nginx (если используется)
sudo systemctl restart nginx

# Проверяем логи
sudo tail -f /var/log/apache2/error.log
# или
sudo tail -f /var/log/httpd/error_log
```

---

## ✅ Шаг 7: Проверка работоспособности

```bash
# Проверяем health check endpoint
curl http://localhost:5001/api/health
# или
curl http://calc.figurebase.ru/api/health

# Проверяем логи на ошибки
tail -f /var/www/calc.figurebase.ru/logs/app.log

# Проверяем что приложение запущено
ps aux | grep python | grep -v grep
```

---

## 🆘 Если что-то пошло не так

### Откат изменений:

```bash
cd /var/www/calc.figurebase.ru

# Откатываемся к предыдущему коммиту
git log --oneline -5
git reset --hard <предыдущий_commit_hash>

# Восстанавливаем .env
cp .env.backup .env

# Перезапускаем приложение
sudo systemctl restart <service_name>
```

### Проверка ошибок:

```bash
# Логи приложения
tail -50 /var/www/calc.figurebase.ru/logs/app.log

# Логи веб-сервера
sudo tail -50 /var/log/apache2/error.log
# или
sudo tail -50 /var/log/nginx/error.log

# Логи systemd
sudo journalctl -u <service_name> -n 50
```

---

## 📝 Чеклист развертывания

- [ ] Коммит и push на локальной машине
- [ ] Pull на сервере
- [ ] Обновление зависимостей (pip install -r requirements.txt)
- [ ] Обновление .env (добавлены новые переменные)
- [ ] Миграция БД (если нужно)
- [ ] Перезапуск приложения
- [ ] Проверка health check endpoint
- [ ] Проверка логов на ошибки
- [ ] Тестирование основных функций

