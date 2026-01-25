# Настройка Redis для Flask-Limiter

## Зачем нужен Redis?

Flask-Limiter по умолчанию использует **in-memory хранилище**, которое имеет ограничения:

### Проблемы in-memory хранилища:
- ❌ **Не синхронизируется между процессами** - каждый gunicorn worker имеет свою память
- ❌ **Сбрасывается при перезапуске** - счетчики rate limiting теряются
- ❌ **Не работает в кластере** - при нескольких серверах каждый считает отдельно
- ⚠️ **Может пропускать запросы** - если у вас 4 worker'а, каждый может обработать лимит независимо

### Преимущества Redis:
- ✅ **Единое хранилище** - все процессы/серверы используют один счетчик
- ✅ **Персистентность** - данные сохраняются между перезапусками
- ✅ **Масштабируемость** - работает в кластере из нескольких серверов
- ✅ **Точный rate limiting** - гарантирует соблюдение лимитов

## Установка Redis

### На Ubuntu/Debian:
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

### Проверка работы:
```bash
redis-cli ping
# Должен вернуть: PONG
```

## Настройка в проекте

### 1. Установка Python библиотеки

Уже добавлено в `requirements.txt`:
```
redis==5.0.1
```

Установка:
```bash
pip install -r requirements.txt
```

### 2. Настройка переменной окружения

Добавьте в `.env` файл или в переменные окружения системы:

```bash
# Для локального Redis
REDIS_URL=redis://localhost:6379/0

# Для Redis с паролем
REDIS_URL=redis://:password@localhost:6379/0

# Для Redis на удаленном сервере
REDIS_URL=redis://user:password@redis.example.com:6379/0

# Для Redis через Unix socket
REDIS_URL=unix:///var/run/redis/redis.sock?db=0
```

### 3. Код уже настроен

В `extensions.py` уже добавлена поддержка Redis:
- Если `REDIS_URL` указан → используется Redis
- Если `REDIS_URL` не указан → используется in-memory (для разработки)

## Настройка на production сервере

### 1. Установка Redis на сервере:
```bash
sudo apt install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

### 2. Настройка безопасности Redis (опционально):

Отредактируйте `/etc/redis/redis.conf`:
```conf
# Установить пароль
requirepass ваш_надежный_пароль

# Привязать только к localhost (если Redis на том же сервере)
bind 127.0.0.1

# Отключить опасные команды
rename-command FLUSHDB ""
rename-command FLUSHALL ""
```

Перезапустите Redis:
```bash
sudo systemctl restart redis-server
```

### 3. Добавьте переменную окружения:

В systemd service файле (`/etc/systemd/system/calc-figurebase.service`) или в `.env`:
```ini
[Service]
Environment="REDIS_URL=redis://:ваш_пароль@localhost:6379/0"
```

Или в `.env` файле проекта:
```bash
REDIS_URL=redis://:ваш_пароль@localhost:6379/0
```

### 4. Перезапустите приложение:
```bash
sudo systemctl restart calc-figurebase
```

## Проверка работы

### 1. Проверьте логи:
```bash
journalctl -u calc-figurebase -n 50 --no-pager
```

Предупреждение о in-memory хранилище должно исчезнуть.

### 2. Проверьте Redis:
```bash
redis-cli
> KEYS *
> GET limiter:*
```

Вы должны увидеть ключи, созданные Flask-Limiter.

## Мониторинг Redis

### Проверка использования памяти:
```bash
redis-cli INFO memory
```

### Мониторинг в реальном времени:
```bash
redis-cli MONITOR
```

### Очистка данных rate limiting (если нужно):
```bash
redis-cli FLUSHDB
```

⚠️ **Внимание**: Это очистит ВСЕ данные в текущей базе Redis!

## Альтернатива: Memcached

Если не хотите использовать Redis, можно использовать Memcached:

### Установка:
```bash
sudo apt install memcached
```

### В `.env`:
```bash
RATELIMIT_STORAGE_URL=memcached://localhost:11211
```

### В `extensions.py`:
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

storage_uri = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=storage_uri
)
```

## Рекомендации

1. **Для разработки**: Можно оставить in-memory (проще, не требует Redis)
2. **Для production**: Обязательно используйте Redis или Memcached
3. **Для кластера**: Только Redis/Memcached, иначе rate limiting не будет работать корректно

## Troubleshooting

### Redis не подключается:
1. Проверьте, что Redis запущен: `sudo systemctl status redis-server`
2. Проверьте URL: `redis-cli -u redis://localhost:6379/0 ping`
3. Проверьте логи приложения: `journalctl -u calc-figurebase -n 100`

### Ошибка "Connection refused":
- Убедитесь, что Redis слушает на правильном порту: `netstat -tlnp | grep 6379`
- Проверьте firewall: `sudo ufw status`

### Ошибка "Authentication required":
- Проверьте пароль в `REDIS_URL`
- Или временно отключите пароль в `/etc/redis/redis.conf`
