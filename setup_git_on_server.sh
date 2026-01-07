#!/bin/bash
# Скрипт для настройки Git на сервере
# Запустите: bash setup_git_on_server.sh

echo "═══════════════════════════════════════════════════════════"
echo " НАСТРОЙКА GIT ДЛЯ calc.figurebase.ru"
echo "═══════════════════════════════════════════════════════════"

# Путь к проекту
PROJECT_PATH="/var/www/calc.figurebase.ru"
GITHUB_REPO="https://github.com/AndryshaDenisov1488/calcfigurebase.git"

echo ""
echo "1️⃣  Переход в директорию проекта..."
cd "$PROJECT_PATH" || {
    echo "❌ Ошибка: не удалось перейти в $PROJECT_PATH"
    exit 1
}
echo "✅ Текущая директория: $(pwd)"

echo ""
echo "2️⃣  Проверка наличия .git..."
if [ -d ".git" ]; then
    echo "⚠️  Git уже инициализирован"
    read -p "Продолжить? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
else
    echo "Инициализация git репозитория..."
    git init
    if [ $? -eq 0 ]; then
        echo "✅ Git инициализирован"
    else
        echo "❌ Ошибка при инициализации git"
        exit 1
    fi
fi

echo ""
echo "3️⃣  Проверка remote репозитория..."
if git remote | grep -q "origin"; then
    echo "⚠️  Remote 'origin' уже существует"
    CURRENT_URL=$(git remote get-url origin)
    echo "Текущий URL: $CURRENT_URL"
    read -p "Изменить на $GITHUB_REPO? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git remote set-url origin "$GITHUB_REPO"
        echo "✅ URL обновлен"
    fi
else
    echo "Добавление remote репозитория..."
    git remote add origin "$GITHUB_REPO"
    if [ $? -eq 0 ]; then
        echo "✅ Remote добавлен"
    else
        echo "❌ Ошибка при добавлении remote"
        exit 1
    fi
fi

echo ""
echo "4️⃣  Проверка .gitignore..."
if [ -f ".gitignore" ]; then
    echo "✅ .gitignore найден"
else
    echo "⚠️  .gitignore не найден! Рекомендуется создать его перед коммитом"
fi

echo ""
echo "5️⃣  Проверка статуса..."
git status --short

echo ""
echo "6️⃣  Готово к коммиту и push!"
echo ""
echo "Следующие команды для выполнения:"
echo "  git add ."
echo "  git commit -m 'Initial commit'"
echo "  git branch -M main"
echo "  git push -u origin main"
echo ""
read -p "Выполнить эти команды сейчас? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Добавление файлов..."
    git add .
    
    echo ""
    echo "Создание коммита..."
    git commit -m "Initial commit from server"
    
    echo ""
    echo "Установка ветки main..."
    git branch -M main
    
    echo ""
    echo "Отправка на GitHub..."
    echo "⚠️  Может потребоваться авторизация (логин и Personal Access Token)"
    git push -u origin main
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ Успешно отправлено на GitHub!"
    else
        echo ""
        echo "❌ Ошибка при отправке. Проверьте:"
        echo "   - Авторизацию (Personal Access Token)"
        echo "   - Права доступа к репозиторию"
        echo "   - URL репозитория"
    fi
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo " Настройка завершена!"
echo "═══════════════════════════════════════════════════════════"

