# Быстрое развертывание на сервере

## 🚀 Быстрая инструкция

### На ЛОКАЛЬНОЙ машине (Windows PowerShell):

```powershell
cd "C:\Users\User\Documents\Разработки\ФФКМ\calc.figurebase.ru"
git add .
git commit -m "Улучшения: CSRF, обработка ошибок БД, пагинация, health check, security headers"
git push origin main
```

### На СЕРВЕРЕ (Linux):

```bash
# 1. Переходим в проект
cd /var/www/calc.figurebase.ru

# 2. Сохраняем .env
cp .env .env.backup

# 3. Получаем изменения
git pull origin main

# 4. Обновляем зависимости
source venv/bin/activate  # если используется venv
pip3 install -r requirements.txt

# 5. Добавляем новые переменные в .env (если их нет)
# Откройте .env и добавьте:
# WTF_CSRF_ENABLED=True
# WTF_CSRF_TIME_LIMIT=3600
# FLASK_HOST=127.0.0.1
# FLASK_PORT=5001

# 6. Перезапускаем (выберите нужный вариант):
# Вариант A: systemd
sudo systemctl restart calc.figurebase.ru

# Вариант B: supervisor
sudo supervisorctl restart calc.figurebase.ru

# Вариант C: Apache
sudo systemctl restart apache2

# Вариант D: Если запущено вручную - найдите и перезапустите процесс
ps aux | grep python | grep app.py
# Убейте процесс и запустите заново

# 7. Проверяем
curl http://localhost:5001/api/health
```

---

## 📋 Сначала получите информацию о сервере

Выполните на сервере:

```bash
# Скачайте скрипт или выполните команды вручную
cd /var/www/calc.figurebase.ru
bash SERVER_INFO_COMMANDS.sh > server_info.txt
cat server_info.txt
```

Или выполните команды из `SERVER_DIAGNOSTICS.md` вручную.

Пришлите результаты, и я дам точные команды для вашего случая!

