# Диагностика сервера перед обновлением

## 📋 Команды для получения информации о сервере

Выполните эти команды на сервере и пришлите результаты:

### 1. Проверка запущенного Flask приложения

```bash
# Проверяем какие процессы Python запущены
ps aux | grep python
ps aux | grep flask
ps aux | grep gunicorn
ps aux | grep uwsgi

# Проверяем какие порты заняты
netstat -tulpn | grep python
netstat -tulpn | grep :500
netstat -tulpn | grep :8000
ss -tulpn | grep python
ss -tulpn | grep :500
ss -tulpn | grep :8000

# Проверяем конфигурацию WSGI (если используется)
cat /var/www/calc.figurebase.ru/wsgi.py
cat /etc/httpd/conf.d/calc.figurebase.ru.conf 2>/dev/null
cat /etc/nginx/sites-enabled/calc.figurebase.ru 2>/dev/null
cat /etc/apache2/sites-enabled/calc.figurebase.ru.conf 2>/dev/null
```

### 2. Проверка конфигурации проекта

```bash
# Переходим в директорию проекта
cd /var/www/calc.figurebase.ru

# Проверяем текущую конфигурацию
cat .env | grep -E "(FLASK_PORT|DATABASE_URL|FLASK_HOST)" || echo "Переменные не найдены в .env"

# Проверяем какой Python используется
which python3
python3 --version

# Проверяем структуру проекта
ls -la
ls -la routes/
ls -la api/
ls -la utils/
ls -la config/
```

### 3. Проверка базы данных

```bash
# Проверяем подключение к PostgreSQL
psql --version
psql -U postgres -c "\l" | grep figure

# Проверяем текущую БД в .env
cd /var/www/calc.figurebase.ru
cat .env | grep DATABASE_URL
```

### 4. Проверка Git статуса

```bash
cd /var/www/calc.figurebase.ru
git status
git remote -v
git branch
git log --oneline -5
```

### 5. Проверка зависимостей

```bash
cd /var/www/calc.figurebase.ru
pip3 list | grep -E "(Flask|WTF|psycopg)"
```

---

## 📤 Отправьте результаты

Пришлите вывод этих команд, особенно:
- ✅ На каком порту запущен проект
- ✅ Какой веб-сервер используется (Apache/Nginx)
- ✅ Текущая конфигурация .env
- ✅ Статус Git репозитория

