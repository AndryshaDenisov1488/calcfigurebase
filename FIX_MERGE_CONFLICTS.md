# Исправление конфликтов слияния в шаблонах

## Проблема
Многие шаблоны имеют конфликты слияния Git (маркеры `<<<<<<<`, `=======`, `>>>>>>>`), что вызывает ошибки при рендеринге.

## Решение
Нужно исправить все файлы с конфликтами. Я уже исправил:
- ✅ `templates/500.html`
- ✅ `templates/404.html`
- ✅ `templates/index.html`
- ✅ `templates/base.html`

## Остальные файлы с конфликтами:
- `templates/club_detail.html`
- `templates/club_free_analysis.html`
- `templates/free_participation.html`
- `templates/free_participation_analysis.html`
- `templates/admin_free_participation.html`
- `templates/admin_login.html`
- `templates/upload.html`
- `templates/normalize_categories.html`
- `templates/event_detail.html`
- `templates/clubs.html`
- `templates/analytics.html`
- `templates/admin_tools.html`
- `templates/admin_export_google_sheets.html`

## Быстрое решение на сервере:

```bash
cd /var/www/calc.figurebase.ru

# Используем версию из HEAD (локальную) для всех конфликтов
git checkout --ours templates/*.html

# Или используем версию из удаленного репозитория
git checkout --theirs templates/*.html

# Затем исправим url_for вручную или через скрипт
```

## Или исправим все через Git:

```bash
# На сервере
cd /var/www/calc.figurebase.ru

# Принимаем все изменения из удаленного репозитория
git merge -X theirs origin/main

# Или откатываемся и делаем заново
git reset --hard origin/main
```

