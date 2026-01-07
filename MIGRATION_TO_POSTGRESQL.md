# Миграция SQLite → PostgreSQL

## ✅ Да, миграция возможна!

Ваша база данных SQLite может быть полностью мигрирована в PostgreSQL без потери данных.

## 📋 Подготовка

### 1. Установка PostgreSQL

**На Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**На Windows:**
- Скачайте установщик с https://www.postgresql.org/download/windows/
- Установите PostgreSQL

**На macOS:**
```bash
brew install postgresql
brew services start postgresql
```

### 2. Создание базы данных

```bash
# Войдите в PostgreSQL
sudo -u postgres psql

# Создайте базу данных и пользователя
CREATE DATABASE figure_skating;
CREATE USER figure_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE figure_skating TO figure_user;
\q
```

### 3. Обновление .env

Добавьте в `.env`:
```bash
# PostgreSQL URL
DATABASE_URL=postgresql://figure_user:your_secure_password@localhost/figure_skating

# Путь к SQLite БД для миграции
SQLITE_DB_PATH=instance/figure_skating.db
```

## 🚀 Миграция данных

### Вариант 1: Автоматическая миграция (рекомендуется)

Используйте скрипт `scripts/migrate_sqlite_to_postgresql.py`:

```bash
# 1. Сделайте бэкап SQLite БД
cp instance/figure_skating.db backups/before_migration_$(date +%Y%m%d_%H%M%S).db

# 2. Убедитесь, что DATABASE_URL указывает на PostgreSQL
# 3. Запустите миграцию
python scripts/migrate_sqlite_to_postgresql.py
```

Скрипт:
- ✅ Копирует все данные из SQLite в PostgreSQL
- ✅ Сохраняет все связи и foreign keys
- ✅ Обновляет sequences для auto-increment
- ✅ Обрабатывает ошибки и конфликты

### Вариант 2: Использование Flask-Migrate

```bash
# 1. Обновите DATABASE_URL на PostgreSQL
# 2. Создайте структуру таблиц
flask db upgrade

# 3. Используйте скрипт миграции для копирования данных
python scripts/migrate_sqlite_to_postgresql.py
```

### Вариант 3: Ручная миграция через pgloader

```bash
# Установите pgloader
sudo apt install pgloader  # Linux
brew install pgloader      # macOS

# Мигрируйте данные
pgloader sqlite:///path/to/figure_skating.db postgresql://user:pass@localhost/figure_skating
```

## ⚠️ Важные замечания

### 1. Бэкап перед миграцией

**ОБЯЗАТЕЛЬНО** сделайте бэкап SQLite БД:
```bash
cp instance/figure_skating.db backups/before_migration_$(date +%Y%m%d_%H%M%S).db
```

### 2. Проверка данных

После миграции проверьте:
```python
# В Python shell
from app import app, db
from models import Event, Athlete, Participant

with app.app_context():
    print(f"Событий: {Event.query.count()}")
    print(f"Спортсменов: {Athlete.query.count()}")
    print(f"Участий: {Participant.query.count()}")
```

### 3. Тестирование

Протестируйте приложение с PostgreSQL:
```bash
# Запустите приложение
python app.py

# Проверьте основные функции:
# - Просмотр событий
# - Просмотр спортсменов
# - Загрузка нового XML файла
```

## 🔧 Настройка для продакшена

После миграции обновите настройки connection pooling в `.env`:

```bash
# Connection Pooling для PostgreSQL
DB_POOL_SIZE=20          # Размер пула соединений
DB_POOL_RECYCLE=3600     # Переподключение каждые 3600 секунд
DB_POOL_PRE_PING=True    # Проверка соединений перед использованием
DB_MAX_OVERFLOW=40       # Максимальное количество дополнительных соединений
```

## 📊 Преимущества PostgreSQL

После миграции вы получите:

1. ✅ **Лучшая производительность** - особенно для больших объемов данных
2. ✅ **Параллельные запросы** - несколько пользователей одновременно
3. ✅ **Расширенные возможности** - полнотекстовый поиск, JSON операции
4. ✅ **Надежность** - ACID транзакции, репликация
5. ✅ **Масштабируемость** - готовность к росту данных

## 🆘 Решение проблем

### Ошибка подключения к PostgreSQL

```bash
# Проверьте, что PostgreSQL запущен
sudo systemctl status postgresql  # Linux
brew services list                # macOS

# Проверьте права доступа
sudo -u postgres psql -c "SELECT 1"
```

### Ошибка миграции данных

1. Проверьте логи скрипта миграции
2. Убедитесь, что структура таблиц совпадает
3. Проверьте foreign keys и constraints

### Откат миграции

Если что-то пошло не так:
```bash
# Вернитесь к SQLite
DATABASE_URL=sqlite:///instance/figure_skating.db

# Восстановите из бэкапа
cp backups/before_migration_*.db instance/figure_skating.db
```

## 📝 Чеклист миграции

- [ ] Создан бэкап SQLite БД
- [ ] Установлен PostgreSQL
- [ ] Создана база данных и пользователь
- [ ] Обновлен DATABASE_URL в .env
- [ ] Запущена миграция данных
- [ ] Проверено количество записей
- [ ] Протестировано приложение
- [ ] Обновлены настройки connection pooling
- [ ] Обновлен wsgi.py для продакшена (если нужно)

## 🎉 Готово!

После успешной миграции ваше приложение будет работать с PostgreSQL и готово к продакшену!

