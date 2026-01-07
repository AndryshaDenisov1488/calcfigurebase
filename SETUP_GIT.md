# Настройка Git на сервере

## 📋 Инструкция по подключению проекта к GitHub

### Шаг 1: Инициализация Git репозитория

Если git еще не инициализирован в папке проекта:

```bash
# Перейти в папку проекта на сервере
cd /var/www/calc.figurebase.ru

# Инициализировать git репозиторий
git init
```

### Шаг 2: Добавить remote репозиторий

```bash
# Добавить удаленный репозиторий GitHub
git remote add origin https://github.com/AndryshaDenisov1488/calcfigurebase.git

# Проверить, что remote добавлен
git remote -v
```

### Шаг 3: Настроить .gitignore (если еще не настроен)

Убедитесь, что файл `.gitignore` существует и содержит нужные исключения:
- `instance/` (база данных)
- `venv/` (виртуальное окружение)
- `*.db` (файлы баз данных)
- `google_credentials.json` (секретные данные)
- и т.д.

### Шаг 4: Первый коммит и отправка на GitHub

```bash
# Добавить все файлы (кроме тех, что в .gitignore)
git add .

# Создать первый коммит
git commit -m "Initial commit"

# Установить ветку main (если нужно)
git branch -M main

# Отправить на GitHub
git push -u origin main
```

**Важно:** При первом push может потребоваться авторизация:
- Либо использовать Personal Access Token вместо пароля
- Либо настроить SSH ключи

---

## 🔐 Настройка авторизации для GitHub

### Вариант 1: Personal Access Token (рекомендуется)

1. Создайте токен на GitHub:
   - Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Создайте токен с правами `repo`

2. При push используйте токен вместо пароля:
   ```bash
   # Git попросит ввести логин и пароль
   # Логин: ваш_username
   # Пароль: ваш_personal_access_token
   ```

### Вариант 2: SSH ключи

```bash
# 1. Сгенерировать SSH ключ (если еще нет)
ssh-keygen -t ed25519 -C "your_email@example.com"

# 2. Показать публичный ключ
cat ~/.ssh/id_ed25519.pub

# 3. Добавить ключ на GitHub:
# Settings → SSH and GPG keys → New SSH key

# 4. Изменить remote на SSH URL
git remote set-url origin git@github.com:AndryshaDenisov1488/calcfigurebase.git
```

---

## 🔄 После настройки: регулярная синхронизация

### Отправка изменений с сервера на GitHub:
```bash
cd /var/www/calc.figurebase.ru
git add .
git commit -m "Описание изменений"
git push
```

### Обновление с GitHub на сервер:
```bash
cd /var/www/calc.figurebase.ru
git pull
```

---

## ⚠️ Важные замечания

1. **НЕ коммитьте чувствительные данные:**
   - `google_credentials.json` (уже в .gitignore)
   - `.env` файлы с паролями
   - Файлы баз данных `*.db`

2. **Проверьте .gitignore перед первым коммитом:**
   ```bash
   git status
   # Убедитесь, что базы данных и секреты не попадут в коммит
   ```

3. **Если репозиторий на GitHub пустой**, первый push должен пройти без проблем.

4. **Если на GitHub уже есть файлы**, может потребоваться:
   ```bash
   git pull origin main --allow-unrelated-histories
   # Разрешить конфликты, если есть
   git push
   ```

---

## 🛠️ Полезные команды для проверки

```bash
# Проверить статус
git status

# Проверить remote
git remote -v

# Посмотреть историю
git log --oneline -5

# Проверить, какие файлы будут добавлены
git status --short
```

---

## 📝 Быстрая команда для первого раза

```bash
cd /var/www/calc.figurebase.ru
git init
git remote add origin https://github.com/AndryshaDenisov1488/calcfigurebase.git
git add .
git commit -m "Initial commit"
git branch -M main
git push -u origin main
```

