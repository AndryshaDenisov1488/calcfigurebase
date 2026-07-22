# Турнирный калькулятор Figurebase

<p align="center">
  <strong>Импорт, хранение, аналитика и визуализация данных соревнований по фигурному катанию в формате ISUCalcFS 3.7.6</strong>
</p>

<p align="center">
  <a href="https://calc.figurebase.ru">calc.figurebase.ru</a> ·
  <a href=".cursor/skills/calc-figurebase/reference.md">Полная документация (Ultra)</a> ·
  <a href=".cursor/skills/calc-figurebase/SKILL.md">AI Skill</a>
</p>

---

## Содержание

1. [О проекте](#о-проекте)
2. [Ключевые возможности](#ключевые-возможности)
3. [Архитектура](#архитектура)
4. [Технологический стек](#технологический-стек)
5. [Структура репозитория](#структура-репозитория)
6. [API](#api)
7. [База данных](#база-данных)
8. [Установка и разработка](#установка-и-разработка)
9. [Деплой на production](#деплой-на-production)
10. [Конфигурация (.env)](#конфигурация-env)
11. [Мониторинг и логи](#мониторинг-и-логи)
12. [Бэкапы](#бэкапы)
13. [Безопасность](#безопасность)
14. [Интеграции](#интеграции)
15. [Документация](#документация)

---

## О проекте

**Турнирный калькулятор Figurebase** — Импорт, хранение, аналитика и визуализация данных соревнований по фигурному катанию в формате ISUCalcFS 3.7.6.

Система является частью экосистемы **Figurebase** и развёрнута на production-сервере:

| | |
|--|--|
| Сервер | xkvlorcrjx (45.12.237.105, Beget VPS) |
| ОС | Ubuntu 22.04.5 LTS |
| URL | https://calc.figurebase.ru |
| Backend | 127.0.0.1:7000 (Gunicorn) |
| БД | SQLite instance/, опционально PostgreSQL |
| Systemd | calc-figurebase |
| Unix user | www-data |
| Интеграции | figurebase.ru (отдельный продукт) |

### Расположение на сервере

| Параметр | Значение |
|----------|----------|
| Путь | `/var/www/calc.figurebase.ru` |
| Домен | `calc.figurebase.ru` |
| Порт backend | `7000 (Gunicorn)` |
| Systemd | `calc-figurebase` |
| Пользователь | `www-data` |
| БД | `SQLite instance/, опционально PostgreSQL` |

---

## Ключевые возможности

![1770031819275](image/README/1770031819275.png)![1770031821059](image/README/1770031821059.png)![1770031826110](image/README/1770031826110.png)![1770031827248](image/README/1770031827248.png)![1770031831029](image/README/1770031831029.png)![1770031831241](image/README/1770031831241.png)![1770031831737](image/README/1770031831737.png)# Система управления турнирами по фигурному катанию

Веб-приложение для импорта, хранения и отображения данных соревнований по фигурному катанию на основе формата ISUCalcFS.

## 📋 Содержание

- [Описание](#описание)
- [Возможности](#возможности)
- [Технологии](#технологии)
- [Установка](#установка)
- [Конфигурация](#конфигурация)
- [Использование](#использование)
- [Архитектура базы данных](#архитектура-базы-данных)
- [Импорт данных](#импорт-данных)
- [Администрирование](#администрирование)
- [Разработка](#разработка)

---

## Архитектура

## 1.1 Описание продукта

**Турнирный калькулятор Figurebase** — Импорт, хранение, аналитика и визуализация данных соревнований по фигурному катанию в формате ISUCalcFS 3.7.6.

Система является частью экосистемы **Figurebase** и развёрнута на production-сервере:

| | |
|--|--|
| Сервер | xkvlorcrjx (45.12.237.105, Beget VPS) |
| ОС | Ubuntu 22.04.5 LTS |
| URL | https://calc.figurebase.ru |
| Backend | 127.0.0.1:7000 (Gunicorn) |
| БД | SQLite instance/, опционально PostgreSQL |
| Systemd | calc-figurebase |
| Unix user | www-data |
| Интеграции | figurebase.ru (отдельный продукт) |

## 1.2

```
Интернет → nginx (443) → 127.0.0.1:7000 (Gunicorn) → systemd (calc-figurebase)
```

---

## Технологический стек

ЗАВИСИМОСТИ И СТЕК

## 2.1 Python зависимости

```
Flask
Flask-CORS
Flask-Limiter
Flask-Migrate
Flask-SQLAlchemy
Flask-WTF
SQLAlchemy
Werkzeug
alembic
google-auth
google-auth-httplib2
google-auth-oauthlib
gspread
gunicorn
openpyxl
python-dotenv
redis
reportlab
```

## 2.2 JavaScript зависимости

```json
{}
```

---

---

## Структура репозитория

```
.
./reports
./backups
./migrations
./migrations/__pycache__
./migrations/versions
./migrations/versions/__pycache__
./docs
./docs/image
./docs/image/XML_IMPORT_FULL_GUIDE
./docs/image/README
./.cursor
./.cursor/skills
./.cursor/skills/calc-figurebase
./.venv
./__pycache__
./routes
./routes/__pycache__
./utils
./utils/__pycache__
./uploads
./uploads/xml_archive
./instance
./scripts
./scripts/__pycache__
./services
./services/__pycache__
./logs
./templates
./parsers
./parsers/__pycache__
./static
./static/css
./static/js
```

Полный каталог: [reference.md § Часть III](.cursor/skills/calc-figurebase/reference.md)

---

## API

И МАРШРУТЫ (ПОЛНЫЙ РЕЕСТР)

Всего: **32** endpoints

```
ROUTE /favicon.ico  ← `app_factory.py`
ROUTE /  ← `scripts/appBU.py`
ROUTE /upload  ← `scripts/appBU.py`
ROUTE /analyze-xml  ← `scripts/appBU.py`
ROUTE /normalize-categories  ← `scripts/appBU.py`
ROUTE /upload-to-database  ← `scripts/appBU.py`
ROUTE /athletes  ← `scripts/appBU.py`
ROUTE /athlete/<int:athlete_id>  ← `scripts/appBU.py`
ROUTE /api/athlete/<int:athlete_id>/results-chart  ← `scripts/appBU.py`
ROUTE /events  ← `scripts/appBU.py`
ROUTE /categories  ← `scripts/appBU.py`
ROUTE /event/<int:event_id>  ← `scripts/appBU.py`
ROUTE /api/event/<int:event_id>/export  ← `scripts/appBU.py`
ROUTE /analytics  ← `scripts/appBU.py`
ROUTE /free-participation  ← `scripts/appBU.py`
ROUTE /club-free-analysis  ← `scripts/appBU.py`
ROUTE /api/statistics  ← `scripts/appBU.py`
ROUTE /api/analytics/top-athletes  ← `scripts/appBU.py`
ROUTE /api/analytics/club-statistics  ← `scripts/appBU.py`
ROUTE /api/analytics/category-statistics  ← `scripts/appBU.py`
ROUTE /api/analytics/free-participation  ← `scripts/appBU.py`
ROUTE /api/analytics/club-free-participation  ← `scripts/appBU.py`
ROUTE /api/athletes  ← `scripts/appBU.py`
ROUTE /api/category/<int:category_id>  ← `scripts/appBU.py`
ROUTE /clubs  ← `scripts/appBU.py`
ROUTE /api/clubs  ← `scripts/appBU.py`
ROUTE /club/<int:club_id>  ← `scripts/appBU.py`
ROUTE /admin/login  ← `scripts/appBU.py`
ROUTE /admin/logout  ← `scripts/appBU.py`
ROUTE /free-participation-analysis  ← `scripts/appBU.py`
ROUTE /api/analytics/free-participation-analysis  ← `scripts/appBU.py`
ROUTE /admin/free-participation  ← `scripts/appBU.py`
```

---

---

## База данных

SQLite instance/, опционально PostgreSQL

Схема: [reference.md Часть VII](.cursor/skills/calc-figurebase/reference.md)

---

## Установка и разработка

### Требования

- Python 3.10+ / Node.js 18+ (см. проект)
- SQLite / PostgreSQL (см. конфиг)
- nginx (production)

### Локальный запуск

```bash
git clone <repo>
cd calc.figurebase.ru
cp .env.example .env   # настроить (плейсхолдеры только)
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# или: cd backend && pip install -r requirements.txt
# Frontend: cd frontend && npm ci && npm run dev
```

---

## Деплой на production

ОПЕРАЦИИ

## Деплой
```bash
cd /var/www/calc.figurebase.ru
git pull
# pip install / npm ci / build / migrate
systemctl restart calc-figurebase
```

## Диагностика
```bash
systemctl status calc-figurebase
journalctl -u calc-figurebase -n 200 --no-pager
curl -s http://127.0.0.1:<port>/health
```

## Бэкапы
- Cron 04:00: `/usr/local/sbin/ffkm-project-backups.sh`
- Лог: `/var/log/ffkm-project-backups.log`

---

### ТЗ сервера

# ТЗ: размещение на сервере — Figure Skating Tournament Management (calc.figurebase.ru)

## Назначение
По имени сервиса **`calc-figurebase.service`** — веб-приложение управления турнирами фигурного катания (Flask/Gunicorn, длительные операции, таймаут Gunicorn **600** с).

## Путь на сервере
`/var/www/calc.figurebase.ru`

## Systemd
- **`calc-figurebase.service`**:  
  `gunicorn --timeout 600 --bind 127.0.0.1:7000 --workers 4 app:app`  
  Виртуальное окружение: `.venv/bin/gunicorn`.

## Сеть и домены
- **HTTPS:** `calc.figurebase.ru`.
- Nginx: прокси на `127.0.0.1:7000`, статика `/static/` из каталога проекта.

## Данные
- БД и файлы приложения — внутри `/var/www/calc.figurebase.ru` (конкретика в коде/`config` проекта).

## Связь с figurebase.ru
**Разные проекты:** `figurebase.ru` — ISUCalcFS (бот + `web_app.py`), этот каталог — только турнирный calc на поддомене.


---

## Конфигурация (.env)

Переменные — в `.env.example` (только плейсхолдеры). **Никогда не коммитить `.env` и JSON ключей сервисного аккаунта.**

На production: `chmod 600 .env`

### Google Sheets credentials

Экспорт/синхронизация читает путь к SA JSON из окружения:

| Переменная | Назначение |
|------------|------------|
| `GOOGLE_CREDENTIALS_PATH` | Абсолютный путь к файлу ключа **вне** git working tree / mount secret store |

Пример (плейсхолдер):

```bash
# Linux/macOS
export GOOGLE_CREDENTIALS_PATH=/secure/path/outside/repo/sa.json

# Windows PowerShell
$env:GOOGLE_CREDENTIALS_PATH="D:\secrets\calc\figurebase-sa.json"
```

Правила:

- Не класть `google_credentials.json` (и аналоги `*-credentials.json` / `service-account*.json`) в корень репозитория или `scripts/`.
- Не коммитить и не печатать содержимое SA JSON.
- Если `GOOGLE_CREDENTIALS_PATH` не задан, код исторически ищет `google_credentials.json` рядом с модулем — это **legacy fallback** для локального ops; предпочтителен только env/path вне дерева.
- Проверка отсутствия файла в дереве: `python -m unittest test_no_google_credentials.py`

Полный список прочих переменных: [reference.md Часть VI](.cursor/skills/calc-figurebase/reference.md)

---

## Мониторинг и логи

```bash
journalctl -u calc-figurebase -f
systemctl status calc-figurebase
```

Prometheus exporters на сервере: node_exporter, nginx_exporter, postgres_exporter.

---

## Бэкапы

- **Расписание:** ежедневно 04:00 MSK
- **Скрипт:** `/usr/local/sbin/ffkm-project-backups.sh`
- **Лог:** `/var/log/ffkm-project-backups.log`
- **Ротация:** 7 дней

---

## Безопасность

- Backend слушает только `127.0.0.1`
- SSL через Let's Encrypt (certbot)
- UFW + Fail2ban на сервере
- `.env` права 600
- nginx блокирует `/.env`, `/.git`
- Google SA JSON: только через `GOOGLE_CREDENTIALS_PATH` вне репозитория; шаблоны в `.gitignore` (`google_credentials.json`, `*-credentials.json`, `service-account*.json`)
- Аудит: `/root/server_audit_report_2026-06-10.docx`

---

## Интеграции

- figurebase.ru (отдельный продукт)
- Google Sheets: credentials только env/path (`GOOGLE_CREDENTIALS_PATH`); см. [Конфигурация (.env)](#конфигурация-env)

---

## Документация

| Документ | Описание | Размер |
|----------|----------|--------|
| [reference.md](.cursor/skills/calc-figurebase/reference.md) | Исчерпывающая техдокументация | ~2115K символов |
| [SKILL.md](.cursor/skills/calc-figurebase/SKILL.md) | Навигация для AI-агента | — |
| [ТЗ-сервер.md](ТЗ-сервер.md) | ТЗ размещения | — |
| [ffkm-server](/root/.cursor/skills/ffkm-server/) | Документация всего сервера | — |

---


---

## Детальный анализ файлов (выдержка)

### Файл: `README.md`

| Свойство | Значение |
|----------|----------|
| Строк | 222 |
| Размер | 7,518 байт |

### Файл: `add_coach_column.py`

| Свойство | Значение |
|----------|----------|
| Строк | 81 |
| Размер | 3,400 байт |
| Функции | 1 |

**Функции верхнего уровня:**

- `add_coach_column()` L12

### Файл: `app.py`

| Свойство | Значение |
|----------|----------|
| Строк | 11 |
| Размер | 240 байт |

### Файл: `app_factory.py`

| Свойство | Значение |
|----------|----------|
| Строк | 98 |
| Размер | 3,640 байт |
| Маршруты | 1 |
| Функции | 1 |

**Функции верхнего уровня:**

- `create_app()` L16

**Маршруты:**
```
ROUTE /favicon.ico
```


### Файл: `birth_date_0101.txt`

| Свойство | Значение |
|----------|----------|
| Строк | 62 |
| Размер | 4,490 байт |

### Файл: `config.py`

| Свойство | Значение |
|----------|----------|
| Строк | 71 |
| Размер | 2,681 байт |
| Функции | 3 |

**Функции верхнего уровня:**

- `_resolve_sqlite_database_uri(uri)` L15
- `_parse_api_keys()` L27
- `get_config()` L32

### Файл: `detailed_parser.py`

| Свойство | Значение |
|----------|----------|
| Строк | 8 |
| Размер | 255 байт |

### Файл: `docs/DATABASE_RECREATION.md`

| Свойство | Значение |
|----------|----------|
| Строк | 276 |
| Размер | 9,633 байт |

### Файл: `docs/GOE_DECODING.md`

| Свойство | Значение |
|----------|----------|
| Строк | 193 |
| Размер | 9,401 байт |

### Файл: `docs/ISUCalcFS_DATABASE_GUIDE.md`

| Свойство | Значение |
|----------|----------|
| Строк | 607 |
| Размер | 24,539 байт |

### Файл: `docs/ISUCalcFS_PARSER_GUIDE.md`

| Свойство | Значение |
|----------|----------|
| Строк | 1145 |
| Размер | 49,538 байт |

### Файл: `docs/ISUCalcFS_XML_GUIDE.md`

| Свойство | Значение |
|----------|----------|
| Строк | 819 |
| Размер | 34,421 байт |

### Файл: `docs/README.md`

| Свойство | Значение |
|----------|----------|
| Строк | 649 |
| Размер | 22,601 байт |

### Файл: `docs/REDIS_SETUP.md`

| Свойство | Значение |
|----------|----------|
| Строк | 203 |
| Размер | 6,373 байт |

### Файл: `docs/SECURITY_DEPLOY.md`

| Свойство | Значение |
|----------|----------|
| Строк | 55 |
| Размер | 4,151 байт |

### Файл: `docs/XML_IMPORT_FULL_GUIDE.md`

| Свойство | Значение |
|----------|----------|
| Строк | 380 |
| Размер | 31,317 байт |

### Файл: `event_rank_constants.py`

| Свойство | Значение |
|----------|----------|
| Строк | 29 |
| Размер | 1,061 байт |

### Файл: `extensions.py`

| Свойство | Значение |
|----------|----------|
| Строк | 54 |
| Размер | 1,431 байт |
| Функции | 1 |

**Функции верхнего уровня:**

- `init_cors(app)` L35

### Файл: `fio_duplicates_ye_yo.txt`

| Свойство | Значение |
|----------|----------|
| Строк | 12 |
| Размер | 714 байт |

### Файл: `fio_same_name_different_dob.txt`

| Свойство | Значение |
|----------|----------|
| Строк | 48 |
| Размер | 2,786 байт |

### Файл: `google_credentials.json` (не в репозитории)

| Свойство | Значение |
|----------|----------|
| Статус | Запрещён в working tree (SEC-SEC-011); путь только через `GOOGLE_CREDENTIALS_PATH` |
| Примечание | Содержимое ключа не документируется и не коммитится |

### Файл: `google_sheets_sync.py`

| Свойство | Значение |
|----------|----------|
| Строк | 4199 |
| Размер | 209,214 байт |
| Функции | 17 |

**Функции верхнего уровня:**

- `_is_free_for_reports(pct_ppname, exclude_free_from_reports, participant_exclude_free_from_reports)` L24
- `get_google_sheets_client()` L47
- `_install_gspread_retry(client, max_retries, base_delay)` L75
- `safe_api_call(func)` L117
- `_empty_event_rank_stats_row(rank, tournaments_count)` L155
- `_finalize_event_rank_stats_table(stats)` L168
- `_is_ms_kms_normalized_category(normalized_name)` L197
- `get_event_rank_statistics_data()` L204
- `get_athletes_data()` L303
- `get_schools_analysis_data()` L468
- `get_general_statistics_data()` L620
- `get_participations_statistics_data()` L728
- `get_summary_statistics_data()` L822
- `get_weekly_unique_athletes_growth()` L999
- `get_events_first_timers_report_data(rank_contains, free_only)` L1094
- `get_free_participation_exceedance_data()` L1425
- `export_to_google_sheets(spreadsheet_id)` L1487

### Файл: `id.txt`

| Свойство | Значение |
|----------|----------|
| Строк | 1 |
| Размер | 44 байт |

### Файл: `instance/google_export_state.json`

| Свойство | Значение |
|----------|----------|
| Строк | 1 |
| Размер | 892 байт |

### Файл: `migrations/alembic.ini`

| Свойство | Значение |
|----------|----------|
| Строк | 51 |
| Размер | 857 байт |

### Файл: `migrations/env.py`

| Свойство | Значение |
|----------|----------|
| Строк | 127 |
| Размер | 3,911 байт |
| Функции | 5 |

**Функции верхнего уровня:**

- `get_engine()` L21
- `get_engine_url()` L30
- `get_metadata()` L51
- `run_migrations_offline()` L57
- `run_migrations_online()` L78

### Файл: `models.py`

| Свойство | Значение |
|----------|----------|
| Строк | 332 |
| Размер | 16,527 байт |
| Классы | 15 |

**Классы:**

- `Event` (строка 11)
  - Docstring: Модель события/турнира
- `Category` (строка 40)
  - Docstring: Модель категории соревнований
- `Segment` (строка 63)
  - Docstring: Модель сегмента программы
- `Club` (строка 77)
  - Docstring: Модель клуба/организации
- `Athlete` (строка 93)
  - Docstring: Модель спортсмена
  - `full_name(self)` L110
  - `short_name(self)` L127
- `Participant` (строка 146)
  - Docstring: Модель участника турнира
- `Performance` (строка 176)
  - Docstring: Модель выступления в сегменте
- `Element` (строка 209)
  - Docstring: Модель выполненного элемента выступления
- `ComponentScore` (строка 224)
  - Docstring: Модель оценок компонентов программы
- `Judge` (строка 235)
  - Docstring: Модель судьи
- `JudgePanel` (строка 252)
  - Docstring: Связь судьи с сегментом (судейская бригада)
- `Coach` (строка 268)
  - Docstring: Модель тренера
- `CoachAssignment` (строка 282)
  - Docstring: Модель назначения тренера спортсмену (отслеживание переходов)
- `SiteReaderLoginLog` (строка 303)
  - Docstring: Успешные входы через /site-access (пароль «доступ судьи» / SITE_READ_PASSWORD).
- `JudgeHelperFreeAudit` (строка 314)
  - Docstring: Журнал использования страницы помощника судьям (бесплатные участия).

### Файл: `my_duplicates.txt`

| Свойство | Значение |
|----------|----------|
| Строк | 330 |
| Размер | 21,586 байт |

### Файл: `my_list.txt`

| Свойство | Значение |
|----------|----------|
| Строк | 62 |
| Размер | 4,490 байт |

### Файл: `parsers/__init__.py`

| Свойство | Значение |
|----------|----------|
| Строк | 2 |
| Размер | 23 байт |

### Файл: `parsers/isu_calcfs_parser.py`

| Свойство | Значение |
|----------|----------|
| Строк | 572 |
| Размер | 26,568 байт |
| Классы | 1 |
| Функции | 2 |

**Классы:**

- `ISUCalcFSParser` (строка 14)
  - Docstring: Парсер для XML файлов ISUCalcFS
  - `__init__(self, xml_file_path)` L17
  - `_decode_goe_xml(code)` L30
  - `_decode_judge_score_xml(code)` L74
  - `parse(self)` L153
  - `_parse_events(self, root)` L177
  - `_parse_categories(self, root)` L203
  - `_parse_segments(self, root)` L225
  - `_wug_to_role_code(wug)` L251
  - `_parse_judges(self, root)` L269
  - `_parse_persons(self, root)` L309
  - `_parse_clubs(self, root)` L357
  - `_parse_participants(self, root)` L381
  - `_parse_performances(self, root)` L409
  - `_parse_date(self, date_str)` L541
  - `get_athletes_with_results(self)` L550

**Функции верхнего уровня:**

- `parse_date(date_str)` L554
- `parse_date_to_string(date_str)` L563

### Файл: `reports/otchet_bd_20260607_130413.txt`

| Свойство | Значение |
|----------|----------|
| Строк | 105 |
| Размер | 6,791 байт |

### Файл: `requirements.txt`

| Свойство | Значение |
|----------|----------|
| Строк | 18 |
| Размер | 339 байт |

### Файл: `routes/__init__.py`

| Свойство | Значение |
|----------|----------|
| Строк | 2 |
| Размер | 24 байт |

### Файл: `routes/admin.py`

| Свойство | Значение |
|----------|----------|
| Строк | 1183 |
| Размер | 57,387 байт |
| Функции | 22 |

**Функции верхнего уровня:**

- `_parse_normalize_category_form(request)` L37
- `_safe_parse_birth_conflict_resolutions(raw)` L49
- `check_import_birth_conflicts()` L80
- `_export_state_path(app_obj)` L122
- `_read_export_state(app_obj)` L128
- `_write_export_state(app_obj, state)` L161
- `_start_google_export_background(app_obj)` L169
- `upload_file()` L215
- `analyze_xml()` L343
- `normalize_categories()` L479
- `admin_judge_helper_audit()` L663
- `admin_site_reader_login_log()` L675
- `upload_to_database()` L708
- `admin_login()` L785
- `admin_logout()` L807
- `admin_export_google_sheets()` L815
- `admin_export_google_sheets_status()` L895
- `admin_event_rank_update()` L911
- `_event_ranks_list_details_by_id(event_ids)` L945
- `admin_event_ranks()` L1010
- `admin_free_participation()` L1055
- `participant_free_report_toggle()` L1158

### Файл: `routes/analytics.py`

| Свойство | Значение |
|----------|----------|
| Строк | 469 |
| Размер | 21,067 байт |
| Функции | 21 |

**Функции верхнего уровня:**

- `_normalize_words(s)` L26
- `_is_year(s)` L33
- `_is_rank(s)` L39
- `_is_city_or_school(s)` L45
- `_looks_like_fio(s)` L58
- `_parse_pasted_list(text)` L75
- `_check_names_against_db(names)` L102
- `_enrich_matches(raw_matches)` L162
- `_get_participation_counts()` L209
- `_check_names_against_db_free(names)` L230
- `analytics()` L270
- `free_participation()` L275
- `club_free_analysis()` L280
- `school_segment_event_ranks()` L286
- `school_segment_report_pdf()` L312
- `free_participation_analysis()` L345
- `judge_helper_free()` L351
- `first_timers_detail()` L402
- `first_timers_detail_1_sport()` L416
- `first_timers_detail_free()` L427
- `first_timers_detail_pdf()` L437

### Файл: `routes/api.py`

| Свойство | Значение |
|----------|----------|
| Строк | 1494 |
| Размер | 75,657 байт |
| Функции | 18 |

**Функции верхнего уровня:**

- `_require_api_auth()` L30
- `api_health()` L39
- `api_athlete_results_chart(athlete_id)` L45
- `api_events()` L75
- `export_event_results(event_id)` L94
- `api_statistics()` L137
- `api_top_athletes()` L191
- `api_club_statistics()` L292
- `api_category_statistics()` L323
- `api_free_participation()` L372
- `api_club_free_participation()` L519
- `api_athletes()` L597
- `api_category_details(category_id)` L809
- `api_clubs()` L852
- `api_free_participation_analysis()` L882
- `api_free_participation_analysis_ranks()` L1053
- `api_coaches()` L1072
- `api_participant_performance_details(participant_id)` L1122

### Файл: `routes/errors.py`

| Свойство | Значение |
|----------|----------|
| Строк | 127 |
| Размер | 5,269 байт |
| Функции | 2 |

**Функции верхнего уровня:**

- `_wants_json_error()` L13
- `register_error_handlers(app)` L20

### Файл: `routes/public.py`

| Свойство | Значение |
|----------|----------|
| Строк | 594 |
| Размер | 25,549 байт |
| Функции | 15 |

**Функции верхнего уровня:**

- `_normalize_search_text(value)` L21
- `index()` L29
- `athletes()` L35
- `athlete_detail(athlete_id)` L46
- `events()` L74
- `categories()` L184
- `best_results()` L214
- `get_judge_role_name(role_code, panel_group, order_num)` L233
- `event_detail(event_id)` L324
- `coaches()` L456
- `coach_detail(coach_id)` L461
- `clubs()` L514
- `club_detail(club_id)` L520
- `site_access()` L546
- `site_reader_logout()` L590

### Файл: `scripts/1617022026ustinov.py`

| Свойство | Значение |
|----------|----------|
| Строк | 128 |
| Размер | 3,510 байт |
| Функции | 6 |

**Функции верхнего уровня:**

- `normalize_words(s)` L28
- `list_entry_to_key(s)` L37
- `athlete_name_words(name)` L44
- `load_names(path)` L48
- `find_athletes_by_two_words(athletes_data, list_key)` L57
- `main()` L65

### Файл: `scripts/1617022026ustinov.txt`

| Свойство | Значение |
|----------|----------|
| Строк | 45 |
| Размер | 1,352 байт |

### Файл: `scripts/1820022026lakernik.py`

| Свойство | Значение |
|----------|----------|
| Строк | 128 |
| Размер | 3,515 байт |
| Функции | 6 |

**Функции верхнего уровня:**

- `normalize_words(s)` L28
- `list_entry_to_key(s)` L37
- `athlete_name_words(name)` L44
- `load_names(path)` L48
- `find_athletes_by_two_words(athletes_data, list_key)` L57
- `main()` L65

### Файл: `scripts/1820022026lakernik.txt`

| Свойство | Значение |
|----------|----------|
| Строк | 13 |
| Размер | 372 байт |

### Файл: `scripts/SETUP_CRON_BACKUP.sh`

| Свойство | Значение |
|----------|----------|
| Строк | 93 |
| Размер | 3,813 байт |

### Файл: `scripts/add_coach_tables.py`

| Свойство | Значение |
|----------|----------|
| Строк | 53 |
| Размер | 1,860 байт |
| Функции | 1 |

**Функции верхнего уровня:**

- `add_coach_tables()` L20

### Файл: `scripts/add_event_exclude_free_flag.py`

| Свойство | Значение |
|----------|----------|
| Строк | 51 |
| Размер | 1,577 байт |
| Функции | 1 |

**Функции верхнего уровня:**

- `main()` L20

### Файл: `scripts/add_event_rank_column.py`

| Свойство | Значение |
|----------|----------|
| Строк | 49 |
| Размер | 1,276 байт |
| Функции | 1 |

**Функции верхнего уровня:**

- `main()` L20

### Файл: `scripts/add_participant_exclude_free_flag.py`

| Свойство | Значение |
|----------|----------|
| Строк | 49 |
| Размер | 1,476 байт |
| Функции | 1 |

**Функции верхнего уровня:**

- `main()` L20

### Файл: `scripts/analyze_clubs.py`

| Свойство | Значение |
|----------|----------|
| Строк | 111 |
| Размер | 3,184 байт |
| Функции | 4 |

**Функции верхнего уровня:**

- `lev(a, b)` L24
- `dice_chars(a, b)` L39
- `lev_ratio(a, b)` L47
- `main()` L54

### Файл: `scripts/appBU.py`

| Свойство | Значение |
|----------|----------|
| Строк | 2086 |
| Размер | 93,296 байт |
| Маршруты | 31 |
| Функции | 43 |

**Функции верхнего уровня:**

- `format_season(date_obj)` L32
- `admin_required(f)` L89
- `not_found_error(error)` L119
- `internal_error(error)` L124
- `too_large(error)` L130
- `index()` L137
- `upload_file()` L145
- `analyze_xml()` L205
- `normalize_categories()` L268
- `upload_to_database()` L330
- `athletes()` L365
- `athlete_detail(athlete_id)` L379
- `api_athlete_results_chart(athlete_id)` L397
- `events()` L436
- `categories()` L483
- `event_detail(event_id)` L507
- `export_event_results(event_id)` L520
- `analytics()` L569
- `free_participation()` L574
- `club_free_analysis()` L579
- `api_statistics()` L584
- `get_rank_weight(rank_name)` L605
- `api_top_athletes()` L628
- `api_club_statistics()` L735
- `analyze_categories_from_xml(parser)` L956
- `normalize_category_name(category_name, gender)` L978
- `api_category_statistics()` L1011
- `api_free_participation()` L1067
- `api_club_free_participation()` L1162
- `api_athletes()` L1222

**Маршруты:**
```
ROUTE /
ROUTE /upload
ROUTE /analyze-xml
ROUTE /normalize-categories
ROUTE /upload-to-database
ROUTE /athletes
ROUTE /athlete/<int:athlete_id>
ROUTE /api/athlete/<int:athlete_id>/results-chart
ROUTE /events
ROUTE /categories
ROUTE /event/<int:event_id>
ROUTE /api/event/<int:event_id>/export
ROUTE /analytics
ROUTE /free-participation
ROUTE /club-free-analysis
ROUTE /api/statistics
ROUTE /api/analytics/top-athletes
ROUTE /api/analytics/club-statistics
ROUTE /api/analytics/category-statistics
ROUTE /api/analytics/free-participation
ROUTE /api/analytics/club-free-participation
ROUTE /api/athletes
ROUTE /api/category/<int:category_id>
ROUTE /clubs
ROUTE /api/clubs
ROUTE /club/<int:club_id>
ROUTE /admin/login
ROUTE /admin/logout
ROUTE /free-participation-analysis
ROUTE /api/analytics/free-participation-analysis
ROUTE /admin/free-participation
```


### Файл: `scripts/assign_default_club.py`

| Свойство | Значение |
|----------|----------|
| Строк | 134 |
| Размер | 6,505 байт |
| Функции | 2 |

**Функции верхнего уровня:**

- `assign_default_club()` L18
- `main()` L121

### Файл: `scripts/athlete_names_list.txt`

| Свойство | Значение |
|----------|----------|
| Строк | 76 |
| Размер | 2,294 байт |

### Файл: `scripts/backup_database.py`

| Свойство | Значение |
|----------|----------|
| Строк | 282 |
| Размер | 11,384 байт |
| Функции | 5 |

**Функции верхнего уровня:**

- `setup_logging(log_file)` L14
- `cleanup_old_backups(backup_dir, days_to_keep)` L28
- `backup_database(auto_mode)` L67
- `restore_database(backup_filename)` L167
- `main()` L210

### Файл: `scripts/check_athletes_from_org_list.py`

| Свойство | Значение |
|----------|----------|
| Строк | 139 |
| Размер | 5,456 байт |
| Функции | 4 |

**Функции верхнего уровня:**

- `normalize_fio_key(s)` L37
- `extract_fio_from_org_list(path)` L47
- `build_athlete_index(app)` L73
- `main()` L85

### Файл: `scripts/check_athletes_in_db.py`

| Свойство | Значение |
|----------|----------|
| Строк | 141 |
| Размер | 5,011 байт |
| Функции | 6 |

**Функции верхнего уровня:**

- `normalize_words(s)` L31
- `list_entry_to_key(s)` L41
- `athlete_name_words(name)` L50
- `load_names(path)` L55
- `find_athletes_by_two_words(athletes_data, list_key)` L65
- `main()` L74

### Файл: `scripts/check_athletes_without_starts.py`

| Свойство | Значение |
|----------|----------|
| Строк | 104 |
| Размер | 3,847 байт |
| Функции | 2 |

**Функции верхнего уровня:**

- `check_athletes_without_starts()` L27
- `main()` L90

### Файл: `scripts/check_club_duplicates_by_words.py`

| Свойство | Значение |
|----------|----------|
| Строк | 193 |
| Размер | 8,107 байт |
| Функции | 6 |

**Функции верхнего уровня:**

- `normalize_word(w)` L30
- `words_from_name(name, exclude_stop)` L40
- `build_word_sets(clubs)` L61
- `find_groups_by_common_words(clubs_with_words, min_common_words)` L70
- `athlete_count_for_club(session, club_id)` L132
- `main()` L137

### Файл: `scripts/check_clubs_zero_athletes.py`

| Свойство | Значение |
|----------|----------|
| Строк | 94 |
| Размер | 3,036 байт |
| Функции | 2 |

**Функции верхнего уровня:**

- `check_clubs_zero_athletes()` L20
- `main()` L80

### Файл: `scripts/check_duplicates_smart.py`

| Свойство | Значение |
|----------|----------|
| Строк | 143 |
| Размер | 6,159 байт |
| Функции | 2 |

**Функции верхнего уровня:**

- `similarity(a, b)` L13
- `check_duplicates()` L21

### Файл: `scripts/check_fio_against_db.py`

| Свойство | Значение |
|----------|----------|
| Строк | 143 |
| Размер | 5,127 байт |
| Функции | 5 |

**Функции верхнего уровня:**

- `normalize_fio_key(s)` L32
- `build_db_index(app)` L43
- `check_one_fio(fio, index)` L65
- `load_fio_lines(path)` L73
- `main()` L83

### Файл: `scripts/check_mafkk_schools.py`

| Свойство | Значение |
|----------|----------|
| Строк | 96 |
| Размер | 4,006 байт |
| Функции | 1 |

**Функции верхнего уровня:**

- `check_mafkk_schools()` L18

### Файл: `scripts/check_missing_clubs.py`

| Свойство | Значение |
|----------|----------|
| Строк | 120 |
| Размер | 5,021 байт |
| Функции | 3 |

**Функции верхнего уровня:**

- `check_missing_clubs()` L17
- `check_club_statistics()` L77
- `main()` L102

### Файл: `scripts/check_names_against_db.py`

| Свойство | Значение |
|----------|----------|
| Строк | 288 |
| Размер | 11,037 байт |
| Функции | 7 |

**Функции верхнего уровня:**

- `norm_component(s)` L124
- `normalize_first_name(name)` L134
- `patronymic_stem(pat)` L144
- `parse_full_name(line)` L167
- `similarity_score(input_norm, db_norm)` L191
- `check_one_name(parsed)` L205
- `main()` L276

### Файл: `scripts/check_paid_1sport_girls.py`

| Свойство | Значение |
|----------|----------|
| Строк | 204 |
| Размер | 9,277 байт |
| Функции | 2 |

**Функции верхнего уровня:**

- `check_paid_1sport_girls()` L24
- `main()` L190

### Файл: `scripts/check_pair_results.py`

| Свойство | Значение |
|----------|----------|
| Строк | 141 |
| Размер | 6,883 байт |

### Файл: `scripts/check_participants_zero_points.py`

| Свойство | Значение |
|----------|----------|
| Строк | 155 |
| Размер | 6,430 байт |
| Функции | 2 |

**Функции верхнего уровня:**

- `check_participants_zero_points()` L24
- `main()` L141

### Файл: `scripts/check_remaining.py`

| Свойство | Значение |
|----------|----------|
| Строк | 35 |
| Размер | 1,224 байт |

### Файл: `scripts/check_remaining_pairs.py`

| Свойство | Значение |
|----------|----------|
| Строк | 73 |
| Размер | 2,498 байт |

### Файл: `scripts/check_search_data.sql`

| Свойство | Значение |
|----------|----------|
| Строк | 70 |
| Размер | 2,965 байт |

### Файл: `scripts/check_search_direct.py`

| Свойство | Значение |
|----------|----------|
| Строк | 160 |
| Размер | 6,930 байт |

### Файл: `scripts/check_similar_club_names.py`

| Свойство | Значение |
|----------|----------|
| Строк | 374 |
| Размер | 17,875 байт |
| Функции | 6 |

**Функции верхнего уровня:**

- `expand_abbreviations(text)` L36
- `normalize_club_name(name)` L53
- `extract_key_words(name)` L69
- `similarity(name1, name2)` L86
- `check_similar_club_names()` L170
- `main()` L360

### Файл: `scripts/check_specific.py`

| Свойство | Значение |
|----------|----------|
| Строк | 68 |
| Размер | 2,630 байт |
| Функции | 1 |

**Функции верхнего уровня:**

- `similarity(a, b)` L11

### Файл: `scripts/check_withdrawn_athletes.py`

| Свойство | Значение |
|----------|----------|
| Строк | 215 |
| Размер | 9,116 байт |
| Функции | 2 |

**Функции верхнего уровня:**

- `check_withdrawn_athletes()` L29
- `main()` L202

### Файл: `scripts/clear_and_reload.py`

| Свойство | Значение |
|----------|----------|
| Строк | 79 |
| Размер | 3,239 байт |
| Функции | 2 |

**Функции верхнего уровня:**

- `clear_database()` L10
- `check_database_status()` L42

### Файл: `scripts/create_database.py`

| Свойство | Значение |
|----------|----------|
| Строк | 57 |
| Размер | 1,910 байт |
| Функции | 1 |

**Функции верхнего уровня:**

- `create_database()` L19

### Файл: `scripts/delete_athletes_and_club.py`

| Свойство | Значение |
|----------|----------|
| Строк | 121 |
| Размер | 4,630 байт |
| Функции | 2 |

**Функции верхнего уровня:**

- `create_backup()` L28
- `main()` L55

### Файл: `scripts/delete_clubs_zero_athletes.py`

| Свойство | Значение |
|----------|----------|
| Строк | 172 |
| Размер | 5,606 байт |
| Функции | 3 |

**Функции верхнего уровня:**

- `create_backup()` L22
- `delete_clubs_zero_athletes()` L45
- `main()` L155

### Файл: `scripts/delete_event_by_id.py`

| Свойство | Значение |
|----------|----------|
| Строк | 87 |
| Размер | 3,983 байт |
| Функции | 1 |

**Функции верхнего уровня:**

- `delete_event_by_id(event_id, backup)` L21

### Файл: `scripts/delete_event_by_name.py`

| Свойство | Значение |
|----------|----------|
| Строк | 148 |
| Размер | 5,546 байт |
| Функции | 2 |

**Функции верхнего уровня:**

- `create_backup()` L13
- `delete_event_by_name(event_name)` L27

### Файл: `scripts/delete_participants_null_points.py`

| Свойство | Значение |
|----------|----------|
| Строк | 192 |
| Размер | 7,331 байт |
| Функции | 3 |

**Функции верхнего уровня:**

- `create_backup()` L24
- `delete_null_points_participants()` L39
- `main()` L178

### Файл: `scripts/detailed_parser.py`

| Свойство | Значение |
|----------|----------|
| Строк | 257 |
| Размер | 11,789 байт |
| Классы | 1 |
| Функции | 2 |

**Классы:**

- `ISUCalcFSParser` (строка 13)
  - Docstring: Парсер для XML файлов ISUCalcFS
  - `__init__(self, xml_file_path)` L16
  - `parse(self)` L26
  - `_parse_events(self, root)` L47
  - `_parse_categories(self, root)` L74
  - `_parse_segments(self, root)` L89
  - `_parse_persons(self, root)` L103
  - `_parse_clubs(self, root)` L151
  - `_parse_participants(self, root)` L187
  - `_parse_performances(self, root)` L212
  - `_parse_date(self, date_str)` L227
  - `get_athletes_with_results(self)` L236

**Функции верхнего уровня:**

- `parse_date(date_str)` L240
- `parse_date_to_string(date_str)` L249

### Файл: `scripts/detailed_parserBU datemin.py`

| Свойство | Значение |
|----------|----------|
| Строк | 232 |
| Размер | 10,488 байт |
| Классы | 1 |
| Функции | 2 |

**Классы:**

- `ISUCalcFSParser` (строка 13)
  - Docstring: Парсер для XML файлов ISUCalcFS
  - `__init__(self, xml_file_path)` L16
  - `parse(self)` L26
  - `_parse_events(self, root)` L47
  - `_parse_categories(self, root)` L67
  - `_parse_segments(self, root)` L82
  - `_parse_persons(self, root)` L96
  - `_parse_clubs(self, root)` L142
  - `_parse_participants(self, root)` L162
  - `_parse_performances(self, root)` L187
  - `_parse_date(self, date_str)` L202
  - `get_athletes_with_results(self)` L211

**Функции верхнего уровня:**

- `parse_date(date_str)` L215
- `parse_date_to_string(date_str)` L224

### Файл: `scripts/exact_duplicates.py`

| Свойство | Значение |
|----------|----------|
| Строк | 250 |
| Размер | 11,607 байт |
| Функции | 3 |

**Функции верхнего уровня:**

- `similarity(a, b)` L12
- `normalize_name(name)` L18
- `find_exact_duplicates()` L25

### Файл: `scripts/export_schools_athletes.py`

| Свойство | Значение |
|----------|----------|
| Строк | 140 |
| Размер | 5,373 байт |
| Функции | 2 |

**Функции верхнего уровня:**

- `export_schools_athletes(output_format)` L22
- `main()` L124

### Файл: `scripts/final_duplicates.py`

| Свойство | Значение |
|----------|----------|
| Строк | 160 |
| Размер | 7,029 байт |
| Функции | 1 |

**Функции верхнего уровня:**

- `find_all_duplicates()` L12

### Файл: `scripts/fio_list.txt`

| Свойство | Значение |
|----------|----------|
| Ст
---

## Статистика проекта

| Метрика | Значение |
|---------|----------|
| Файлов проанализировано | 196 |
| Директорий | 13 |
| HTTP маршрутов (оценка) | 32 |
| Python классов | 21 |
| Строк в reference | ~2,032,682 |
| Исходников включено полностью | 196 |

<p align="center"><i>Документация Ultra v2.0 · 2026-06-10</i></p>
