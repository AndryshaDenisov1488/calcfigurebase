# Подключение локального проекта к GitHub

## 🎯 Быстрый способ (рекомендуется)

### Если у вас уже есть локальная папка с проектом:

```powershell
# 1. Открыть PowerShell в папке проекта
cd "C:\Users\User\Documents\Разработки\ФФКМ\calc.figurebase.ru"

# 2. Инициализировать git (если еще не инициализирован)
git init

# 3. Добавить remote репозиторий
git remote add origin https://github.com/AndryshaDenisov1488/calcfigurebase.git

# 4. Получить изменения с GitHub
git fetch origin

# 5. Подключить к ветке main
git branch -M main
git pull origin main --allow-unrelated-histories
```

---

## 🔄 Альтернативный способ (клонирование)

Если хотите начать с чистого репозитория:

```powershell
# 1. Перейти в родительскую папку
cd "C:\Users\User\Documents\Разработки\ФФКМ"

# 2. Клонировать репозиторий
git clone https://github.com/AndryshaDenisov1488/calcfigurebase.git

# 3. Перейти в клонированную папку
cd calcfigurebase
```

---

## ⚠️ Если возникли конфликты

При выполнении `git pull` могут возникнуть конфликты, если локальные файлы отличаются от файлов на GitHub.

**Решение:**

1. Посмотреть конфликты:
   ```powershell
   git status
   ```

2. Разрешить конфликты вручную в файлах (отредактировать файлы с конфликтами)

3. После разрешения:
   ```powershell
   git add .
   git commit -m "Merge local and remote"
   git push
   ```

---

## 📋 Проверка подключения

```powershell
# Проверить remote
git remote -v

# Проверить статус
git status

# Посмотреть ветки
git branch -a
```

---

## 🔄 Регулярная работа

### Обновить с GitHub:
```powershell
git pull
```

### Отправить изменения на GitHub:
```powershell
git add .
git commit -m "Описание изменений"
git push
```

---

## 💡 Полезные команды

```powershell
# Посмотреть историю коммитов
git log --oneline -10

# Посмотреть изменения
git diff

# Отменить локальные изменения (ОСТОРОЖНО!)
git checkout -- .

# Посмотреть, какие файлы будут добавлены
git status
```

