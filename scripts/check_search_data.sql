-- Скрипт для проверки данных поиска в базе
-- Запуск: sqlite3 figure_skating.db < scripts/check_search_data.sql
-- Или для PostgreSQL: psql -d database_name -f scripts/check_search_data.sql

-- Проверяем, есть ли спортсмены с "иван" в разных полях
SELECT '=== Поиск "иван" в first_name ===' as check_type;
SELECT id, first_name, last_name, patronymic, full_name_xml 
FROM athlete 
WHERE LOWER(first_name) LIKE '%иван%' 
LIMIT 10;

SELECT '=== Поиск "иван" в last_name ===' as check_type;
SELECT id, first_name, last_name, patronymic, full_name_xml 
FROM athlete 
WHERE LOWER(last_name) LIKE '%иван%' 
LIMIT 10;

SELECT '=== Поиск "иван" в full_name_xml ===' as check_type;
SELECT id, first_name, last_name, patronymic, full_name_xml 
FROM athlete 
WHERE LOWER(full_name_xml) LIKE '%иван%' 
LIMIT 10;

SELECT '=== Поиск "иван" в patronymic ===' as check_type;
SELECT id, first_name, last_name, patronymic, full_name_xml 
FROM athlete 
WHERE LOWER(patronymic) LIKE '%иван%' 
LIMIT 10;

-- Проверяем, что находится для "ив"
SELECT '=== Поиск "ив" в first_name ===' as check_type;
SELECT id, first_name, last_name, patronymic, full_name_xml 
FROM athlete 
WHERE LOWER(first_name) LIKE '%ив%' 
LIMIT 10;

SELECT '=== Поиск "ив" в last_name ===' as check_type;
SELECT id, first_name, last_name, patronymic, full_name_xml 
FROM athlete 
WHERE LOWER(last_name) LIKE '%ив%' 
LIMIT 10;

-- Проверяем примеры из логов
SELECT '=== Проверка ID=1281 (Оливия АНТОНОВА) ===' as check_type;
SELECT id, first_name, last_name, patronymic, full_name_xml,
       LOWER(first_name) as first_name_lower,
       LOWER(last_name) as last_name_lower,
       LOWER(COALESCE(patronymic, '')) as patronymic_lower,
       LOWER(COALESCE(full_name_xml, '')) as full_name_xml_lower
FROM athlete 
WHERE id = 1281;

SELECT '=== Проверка ID=1322 (Оливия ДЖОРДЖАШВИЛИ) ===' as check_type;
SELECT id, first_name, last_name, patronymic, full_name_xml,
       LOWER(first_name) as first_name_lower,
       LOWER(last_name) as last_name_lower,
       LOWER(COALESCE(patronymic, '')) as patronymic_lower,
       LOWER(COALESCE(full_name_xml, '')) as full_name_xml_lower
FROM athlete 
WHERE id = 1322;

-- Проверяем, есть ли вообще спортсмены с "иван"
SELECT '=== Общая статистика ===' as check_type;
SELECT 
    COUNT(*) FILTER (WHERE LOWER(first_name) LIKE '%иван%') as first_name_count,
    COUNT(*) FILTER (WHERE LOWER(last_name) LIKE '%иван%') as last_name_count,
    COUNT(*) FILTER (WHERE LOWER(COALESCE(full_name_xml, '')) LIKE '%иван%') as full_name_xml_count,
    COUNT(*) FILTER (WHERE LOWER(COALESCE(patronymic, '')) LIKE '%иван%') as patronymic_count
FROM athlete;
