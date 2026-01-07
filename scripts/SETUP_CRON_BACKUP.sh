#!/bin/bash
# Скрипт для быстрой настройки автоматического бэкапа
# Запустите на сервере: bash SETUP_CRON_BACKUP.sh

echo "═══════════════════════════════════════════════════════════"
echo " НАСТРОЙКА АВТОМАТИЧЕСКОГО БЭКАПА ДЛЯ calc.figurebase.ru"
echo "═══════════════════════════════════════════════════════════"

# Путь к проекту
PROJECT_PATH="/var/www/calc.figurebase.ru"

echo ""
echo "1️⃣  Проверка наличия файлов..."
if [ ! -f "$PROJECT_PATH/backup_database.py" ]; then
    echo "❌ Файл backup_database.py не найден!"
    echo "Загрузите его на сервер в: $PROJECT_PATH/"
    exit 1
fi
echo "✅ backup_database.py найден"

echo ""
echo "2️⃣  Установка прав доступа..."
chmod +x "$PROJECT_PATH/backup_database.py"
echo "✅ Права установлены"

echo ""
echo "3️⃣  Создание папки для бэкапов..."
mkdir -p "$PROJECT_PATH/backups"
chmod 755 "$PROJECT_PATH/backups"
echo "✅ Папка создана"

echo ""
echo "4️⃣  Тестовый запуск..."
cd "$PROJECT_PATH"
./venv/bin/python backup_database.py --auto

if [ $? -eq 0 ]; then
    echo "✅ Тестовый бэкап успешно создан!"
else
    echo "❌ Ошибка при создании бэкапа!"
    echo "Проверьте логи: cat $PROJECT_PATH/backups/backup.log"
    exit 1
fi

echo ""
echo "5️⃣  Проверка текущего crontab..."
CRON_LINE="0 1 * * * cd $PROJECT_PATH && $PROJECT_PATH/venv/bin/python backup_database.py --auto >> $PROJECT_PATH/backups/backup.log 2>&1"

if crontab -l 2>/dev/null | grep -q "calc.figurebase.ru.*backup_database.py"; then
    echo "⚠️  Задача уже существует в crontab!"
    echo "Текущая задача:"
    crontab -l | grep "calc.figurebase.ru.*backup_database.py"
    echo ""
    read -p "Заменить на новую? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Операция отменена"
        exit 0
    fi
    # Удаляем старую задачу
    crontab -l | grep -v "calc.figurebase.ru.*backup_database.py" | crontab -
fi

echo ""
echo "6️⃣  Добавление задачи в crontab..."
(crontab -l 2>/dev/null; echo "# Бэкап БД calc.figurebase.ru (каждый день в 04:00 МСК)"; echo "$CRON_LINE") | crontab -

if [ $? -eq 0 ]; then
    echo "✅ Задача добавлена в crontab!"
else
    echo "❌ Ошибка добавления задачи в crontab!"
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "✅ НАСТРОЙКА ЗАВЕРШЕНА УСПЕШНО!"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "📊 Текущая конфигурация:"
echo "   Время: 04:00 МСК (01:00 UTC) каждый день"
echo "   Хранение: 7 дней"
echo "   Логи: $PROJECT_PATH/backups/backup.log"
echo ""
echo "📝 Текущий crontab:"
crontab -l | grep -A1 "calc.figurebase.ru"
echo ""
echo "🔍 Для просмотра логов:"
echo "   tail -f $PROJECT_PATH/backups/backup.log"
echo ""


