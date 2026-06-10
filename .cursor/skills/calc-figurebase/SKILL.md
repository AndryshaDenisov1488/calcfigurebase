---
name: calc-figurebase
description: >-
  ULTRA-документация Турнирный калькулятор Figurebase (calc.figurebase.ru). Путь: /var/www/calc.figurebase.ru.
  reference.md содержит ПОЛНЫЙ исходный код всех файлов, API, модели, схемы БД.
  При ЛЮБОЙ задаче — читать reference.md ПЕРВЫМ. Не сканировать проект. Сервер: ffkm-server.
---

# Турнирный калькулятор Figurebase — Ultra Skill

## ОБЯЗАТЕЛЬНО ПЕРВЫМ ДЕЛОМ

1. **[reference.md](reference.md)** — исчерпывающая документация (до 3.5MB):
   - Часть I: Executive Summary
   - Часть IV: Все API маршруты
   - Часть V: Все классы и модели
   - Часть VII: Схема БД
   - Часть XII: Пофайловый анализ (каждый файл)
   - **Часть XIII: ПОЛНЫЙ исходный код всех файлов**
2. **[README.md](../../README.md)** — обзор для человека
3. Сервер: `/root/.cursor/skills/ffkm-server/SKILL.md`

## Карточка

| | |
|--|--|
| Путь | `/var/www/calc.figurebase.ru` |
| URL | https://calc.figurebase.ru |
| Порт | 7000 (Gunicorn) |
| БД | SQLite instance/, опционально PostgreSQL |
| Systemd | `calc-figurebase` |

## Команды

```bash
systemctl restart calc-figurebase
journalctl -u calc-figurebase -f
```

## Навигация по reference.md

| Часть | Содержание |
|-------|------------|
| I | Резюме, статистика, архитектура |
| II | Зависимости Python/JS |
| III | Каталог всех файлов |
| IV | API маршруты (полный реестр) |
| V | Классы и модели |
| VI | Переменные окружения |
| VII | Схема БД |
| VIII–IX | Systemd, Nginx |
| X | Git |
| XI | Операции, деплой |
| XII | Пофайловый анализ |
| **XIII** | **Полный исходный код** |
| XIV | README, ТЗ, приложения |
