# Инструкция по пересозданию базы данных на сервере

## Когда это нужно

Пересоздание БД необходимо после исправления формулы декодирования оценок судей, чтобы все данные были сохранены в правильном формате (коды 0-15 вместо декодированных значений).

## ⚠️ ВАЖНО: Резервное копирование

**ПЕРЕД УДАЛЕНИЕМ БД ОБЯЗАТЕЛЬНО СОЗДАЙТЕ РЕЗЕРВНУЮ КОПИЮ!**

## Шаги для пересоздания БД на сервере

### 1. Подключение к серверу

```bash
ssh root@xkvlorcrjx
# или используйте ваш способ подключения
```

### 2. Переход в директорию проекта

```bash
cd /var/www/calc.figurebase.ru
```

### 3. Активация виртуального окружения

```bash
source .venv/bin/activate
```

### 4. Остановка приложения

```bash
# Остановите Gunicorn/приложение
sudo systemctl stop calc-figurebase
# или
sudo supervisorctl stop calc-figurebase
# или найдите процесс и остановите его
ps aux | grep gunicorn
kill <PID>
```

### 5. Резервное копирование текущей БД

```bash
# Определите путь к БД
# Проверьте переменную DATABASE_URL в .env
cat .env | grep DATABASE_URL

# На сервере БД обычно находится в /var/www/calc.figurebase.ru/instance/figure_skating.db
# Создайте резервную копию:
cp instance/figure_skating.db instance/figure_skating.db.backup.$(date +%Y%m%d_%H%M%S)

# Или если БД в корне проекта:
# cp figure_skating.db figure_skating.db.backup.$(date +%Y%m%d_%H%M%S)

# Если используется PostgreSQL, создайте дамп:
# pg_dump -U username -d database_name > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 6. Удаление старой БД

**Для SQLite:**
```bash
# На сервере БД обычно находится в instance/figure_skating.db
# Удалите файл БД:
rm instance/figure_skating.db

# Или если БД в корне проекта:
# rm figure_skating.db

# Также удалите файлы миграций (опционально, если хотите начать с чистого листа)
# rm -rf migrations/versions/*
```

**Для PostgreSQL:**
```bash
# Подключитесь к PostgreSQL
psql -U username -d postgres

# Удалите базу данных
DROP DATABASE database_name;

# Создайте новую пустую базу
CREATE DATABASE database_name;
\q
```

### 7. Создание новой БД

```bash
# Убедитесь, что вы в виртуальном окружении
source .venv/bin/activate

# Создайте новую БД используя db.create_all() (миграция init пустая, поэтому используем db.create_all())
python -c "from app_factory import create_app; from extensions import db; app = create_app(); app.app_context().push(); db.create_all(); print('БД создана успешно')"

# Или используйте скрипт (рекомендуется):
python scripts/create_database.py

# Примечание: Миграция init (814525e701e1) пустая, поэтому flask db upgrade не создаст таблицы.
# После db.create_all() можно сразу запускать сервис - миграция не нужна.
```

### 8. Запуск приложения

```bash
# Запустите приложение
sudo systemctl start calc-figurebase

# Проверьте статус
sudo systemctl status calc-figurebase

# Проверьте логи (если нужно)
journalctl -u calc-figurebase -f
```

### 9. Импорт XML файлов

```bash
# Найдите XML файлы для импорта
# Обычно они находятся в папке uploads/ или в другом месте
ls -la uploads/

# Импортируйте XML файлы через админ-панель:
# 1. Зайдите на сайт: https://calc.figurebase.ru/admin
# 2. Войдите в админ-панель
# 3. Перейдите в раздел "Импорт XML"
# 4. Загрузите все XML файлы по очереди

# Или через скрипт (если есть):
# python scripts/reimport_event_from_xml.py path/to/file.xml
```

**Важно:** После импорта каждого XML файла проверьте, что оценки судей отображаются правильно в распечатках.

### 10. Проверка данных

```bash
# Проверьте, что данные импортированы правильно
# Зайдите на сайт и проверьте:
# - Список спортсменов
# - Результаты турниров
# - Распечатки (проверьте оценки судей - должны быть от -5 до +5)
```

## Проверка после пересоздания

### Проверка оценок судей

После импорта проверьте несколько распечаток и убедитесь, что:
1. Оценки судей (J1, J2, J3) отображаются в диапазоне от -5 до +5
2. Код 11 декодируется как -5
3. Код 14 декодируется как +5
4. Код 4 декодируется как 0

### SQL запрос для проверки (SQLite)

```bash
# Выполните SQL запрос для проверки
sqlite3 instance/figure_skating.db "
SELECT 
    e.id,
    e.order_num,
    e.executed_code,
    json_extract(e.judge_scores, '$.J01') as j01_code,
    json_extract(e.judge_scores, '$.J02') as j02_code,
    json_extract(e.judge_scores, '$.J03') as j03_code
FROM element e
WHERE e.judge_scores IS NOT NULL
LIMIT 10;
"
```

Ожидаемый результат: `j01_code`, `j02_code`, `j03_code` должны быть числами от 0 до 15 (или NULL для кода 9).

## Откат (если что-то пошло не так)

Если после пересоздания что-то пошло не так:

```bash
# Остановите приложение
sudo systemctl stop calc-figurebase

# Восстановите резервную копию
# На сервере БД обычно находится в instance/figure_skating.db
cp instance/figure_skating.db.backup.YYYYMMDD_HHMMSS instance/figure_skating.db

# Или если БД в корне проекта:
# cp figure_skating.db.backup.YYYYMMDD_HHMMSS figure_skating.db

# Запустите приложение
sudo systemctl start calc-figurebase
```

## Дополнительные команды

### Просмотр логов

```bash
# Логи приложения
tail -f logs/app.log

# Логи Gunicorn
journalctl -u calc-figurebase -f
# или
sudo supervisorctl tail -f calc-figurebase
```

### Проверка структуры БД

```bash
# Для SQLite (на сервере БД обычно в instance/)
sqlite3 instance/figure_skating.db ".tables"
sqlite3 instance/figure_skating.db ".schema element"

# Или если БД в корне проекта:
# sqlite3 figure_skating.db ".tables"
# sqlite3 figure_skating.db ".schema element"

# Для PostgreSQL
psql -U username -d database_name -c "\dt"
psql -U username -d database_name -c "\d element"
```

## Примечания

- **Время выполнения**: Импорт всех XML файлов может занять время в зависимости от количества данных
- **Доступность сайта**: Сайт будет недоступен во время пересоздания БД
- **Резервные копии**: Храните резервные копии в безопасном месте
- **Тестирование**: После импорта проверьте несколько распечаток вручную
