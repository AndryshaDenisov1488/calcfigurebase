# Полная расшифровка XML формата ISUCalcFS
## Экспортный формат данных соревнований по фигурному катанию ISU

**Формат файла:** XML  
**Кодировка:** UTF-8  
**Источник:** ISUCalcFS 3.7.6  
**Соответствие:** Правила ISU сезона 2021-2022

---

## 1. ОБЩАЯ СТРУКТУРА XML

### 1.1 Иерархия элементов

```
<ISUCalcFS>                           ← Корневой элемент
  └─ <Event>                          ← Соревнование
       └─ <Categories_List>           ← Список категорий
            └─ <Category>             ← Категория (возрастная группа)
                 └─ <Segments_List>   ← Список сегментов программы
                      └─ <Segment>    ← Сегмент (КП, ПП, РТ)
                           ├─ <TimeSchedule/>     ← Расписание
                           ├─ <Judges_List>       ← Список судей
                           │    └─ <Person/>
                           ├─ <Participants_List> ← Список участников
                           │    └─ <Participant>
                           │         ├─ <Person_Couple_Team>
                           │         │    └─ <Club/>
                           │         └─ <PlannedElements/>
                           └─ <Performance_List>  ← Результаты выступлений
                                └─ <Performance/> ← Детали выступления
```

### 1.2 Принцип хранения данных

- **Все данные хранятся в атрибутах** элементов, а не в текстовом содержимом
- **Числовые баллы умножены на 100** (5439 = 54.39 балла)
- **GOE судей кодируется числами:** 0=-5, 1=-3, 2=-2, 3=-1, 4=0, 5=+1, 6=+2, 7=+3, 8=+4, 9=пусто, 10=+5, 11=-5, 12=-4, 13=+4, 14=+5, 15=-1
- **Даты в формате:** YYYYMMDD (20260119)
- **Статусы одной буквой:** A=Active, Q=Qualified, R=Retired, O=OK, I=Incomplete

---

## 2. ЭЛЕМЕНТ EVENT (Соревнование)

Корневой элемент данных соревнования.

### 2.1 Атрибуты Event

| Атрибут | Тип | Описание | Пример |
|---------|-----|----------|--------|
| `EVT_ID` | N | Уникальный ID соревнования | 1 |
| `EVT_EXTDT` | N | Внешний ID | 14182 |
| `EVT_NAME` | C | Название соревнования | Первенство Москвы |
| `EVT_LNAME` | C | Полное название | Первенство Москвы |
| `EVT_PLACE` | C | Место проведения | г.Москва, СРЦ Навка Арена |
| `EVT_BEGDAT` | D | Дата начала (YYYYMMDD) | 20260119 |
| `EVT_ENDDAT` | D | Дата окончания | 20260123 |
| `EVT_REPPID` | N | ID представителя | 144 |
| `EVT_PLANG` | C | Язык протоколов (E/R) | E |
| `EVT_TYPE` | C | Тип соревнования | T (Tournament) |
| `EVT_CMPTYP` | C | Тип: L=Local, I=International | L |
| `EVT_STAT` | C | Статус: A=Active | A |
| `EVT_CALCTM` | C | Режим расчёта времени | B |

---

## 3. ЭЛЕМЕНТ CATEGORY (Категория)

Определяет возрастную группу и дисциплину.

### 3.1 Атрибуты Category

| Атрибут | Тип | Описание | Пример |
|---------|-----|----------|--------|
| `CAT_ID` | N | Уникальный ID категории | 1 |
| `CAT_EXTDT` | N | Внешний ID | 160203 |
| `EVT_ID` | N | Ссылка на соревнование | 1 |
| `CAT_NAME` | C | Название категории | Девочки, младшая группа |
| `CAT_TVNAME` | C | Название для ТВ | Девочки, младшая группа |
| `CAT_NENT` | N | Количество заявленных | 54 |
| `CAT_NPAR` | N | Количество стартующих | 54 |
| `CAT_LSCPID` | N | ID последнего сегмента | 17 |
| `CAT_LEVEL` | C | Уровень | m=мастер, 1/2/3=юниоры |
| `CAT_GENDER` | C | Пол | F=женский, M=мужской, T=смешанный |
| `CAT_TYPE` | C | Тип дисциплины | S=Singles, D=Dance, P=Pairs |
| `CAT_STAT` | C | Статус | A=Active |
| `CAT_SCPID1-6` | N | ID сегментов программы (1-6) | 15, 16, 17 |
| `CAT_SCPSN1-6` | C | Короткие названия сегментов | КП, ЭЛ, ПП |

### 3.2 Значения CAT_LEVEL
| Код | Описание |
|-----|----------|
| `m` | Мастера (взрослые) |
| `1` | 1 юношеский разряд |
| `2` | 2 юношеский разряд |
| `3` | 3 юношеский разряд |

### 3.3 Значения CAT_TYPE
| Код | Описание |
|-----|----------|
| `S` | Singles (одиночное катание) |
| `D` | Dance (танцы на льду) |
| `P` | Pairs (парное катание) |

---

## 4. ЭЛЕМЕНТ SEGMENT (Сегмент программы)

Определяет часть соревнования (КП, ПП, Ритм-танец).

### 4.1 Основные атрибуты Segment

| Атрибут | Тип | Описание | Пример |
|---------|-----|----------|--------|
| `SCP_ID` | N | Уникальный ID сегмента | 15 |
| `SCP_NAME` | C | Название | Короткая программа |
| `SCP_TVNAME` | C | Название для ТВ | Короткая программа |
| `SCP_SNAM` | C | Короткое название | КП |
| `SCP_TYPE` | C | Тип: S=Short, F=Free, R=Rhythm | S |
| `CAT_ID` | N | Ссылка на категорию | 1 |
| `SCP_FACTOR` | N | Коэффициент (×100) | 100 |
| `SCP_STAT` | C | Статус: B=Before, D=During, A=After | B |
| `SCP_START` | N | Начальный номер | 1 |
| `SCP_STNUMC` | N | Текущий стартовый номер | 54 |
| `SCP_STNUML` | N | Последний стартовый номер | 54 |
| `SCP_STNUMN` | N | Следующий стартовый номер | 54 |

### 4.2 Атрибуты судейской панели

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `SCP_JID01-15` | N | ID судей 1-15 |
| `SCP_JID16-21` | N | ID техпанели (TS, TC, AS) |
| `SCP_JWDR01-15` | C | Флаги отстранения судей |

### 4.3 Атрибуты критериев (компонентов программы)

| Атрибут | Тип | Описание | Пример |
|---------|-----|----------|--------|
| `SCP_CRIT01` | C | Название компонента 1 | Композиция |
| `SCP_CRIT03` | C | Название компонента 2 | Представление |
| `SCP_CRIT05` | C | Название компонента 3 | Мастерство катания |
| `SCP_CRFR01-05` | N | Факторы компонентов (×100) | 133 |
| `SCP_CRSH01-05` | C | Короткие коды | CO, PR, SK |
| `SCP_CRFRGN` | N | Общий фактор генерации | 10 |

### 4.4 Атрибуты вычетов (Deductions)

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `SCP_DEDU01-17` | C | Названия типов вычетов |
| `SCP_DEFR01-17` | N | Значения вычетов (×100) |
| `SCP_DEED01-17` | C | Коды типов |
| `SCP_DEVC01-17` | C | Категории вычетов |

**Типы вычетов:**
- Costume/Prop violation
- Time violation
- Illegal element/movement
- Falls
- Interruption in excess
- Interruption of the program
- Costume failure
- Late start

### 4.5 Атрибуты разминки

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `SCP_WUG01-09` | N | Размеры разминочных групп |
| `SCP_WBG_ID` | N | ID конфигурации разминки |

---

## 5. ЭЛЕМЕНТ PERSON (Персона)

Универсальный элемент для судей, участников, официальных лиц.

### 5.1 Атрибуты Person

| Атрибут | Тип | Описание | Пример |
|---------|-----|----------|--------|
| `PCT_ID` | N | Уникальный ID | 2 |
| `PCT_EXTDT` | C | Внешний ID | 000000001415631 |
| `PCT_TYPE` | C | Тип: PER=Person, CLU=Club, TEA=Team | PER |
| `PCT_AFUNCT` | C | Функция: CMP=Competitor, JDG=Judge | CMP |
| `PCT_STAT` | C | Статус | A |
| `PCT_CNAME` | C | Полное имя | Варвара БОГОМОЛОВА |
| `PCT_SNAME` | C | Короткий код | БОГОВАРВ |
| `PCT_PLNAME` | C | Имя для протоколов | Варвара Олеговна БОГОМОЛОВА |
| `PCT_GNAME` | C | Имя | Варвара |
| `PCT_GNAMEI` | C | Инициал имени | В. |
| `PCT_FNAME` | C | Фамилия | Богомолова |
| `PCT_FNAMEC` | C | Фамилия заглавными | БОГОМОЛОВА |
| `PCT_GENDER` | C | Пол | F/M |
| `PCT_TITLE` | C | Титул | Ms./Mr. |
| `PCT_BDAY` | D | Дата рождения | 20150123 |
| `PCT_CLBID` | N | ID клуба | 1 |
| `PCT_COANAM` | C | Тренер | Софья Федченко |
| `PCT_SPMNAM` | C | Музыка КП | Charlie Chaplin, His Morning... |
| `PCT_FSMNAM` | C | Музыка ПП | Ludovico Einaudi - Experience... |
| `PCT_COMENT` | C | Комментарий (разряд) | 2 СП |
| `PCT_RNAME` | C | Имя в обратном порядке | БОГОМОЛОВА Варвара |
| `PCT_INAME` | C | Имя с инициалом | БОГОМОЛОВА В. |
| `PCT_COMPOF` | C | Флаг участия | a |

### 5.2 Варианты имён для разных контекстов

| Атрибут | Использование |
|---------|---------------|
| `PCT_PSNAME` | Печатные протоколы - короткое |
| `PCT_TLNAME` | ТВ-графика - длинное |
| `PCT_TSNAME` | ТВ-графика - короткое |
| `PCT_S1NAME` | Формат 1 |
| `PCT_S2NAME` | Формат 2 |
| `PCT_S3NAME` | Формат 3 |
| `PCT_S4NAME` | Формат 4 |
| `PCT_WFNAME` | Web - фамилия |
| `PCT_WGNAME` | Web - имя |

---

## 6. ЭЛЕМЕНТ PARTICIPANT (Участник категории)

Связывает участника с категорией и хранит результаты.

### 6.1 Атрибуты Participant

| Атрибут | Тип | Описание | Пример |
|---------|-----|----------|--------|
| `PAR_ID` | N | Уникальный ID записи | 1 |
| `PCT_ID` | N | Ссылка на персону | 2 |
| `CAT_ID` | N | Ссылка на категорию | 1 |
| `PAR_CLBID` | N | ID клуба | 1 |
| `PAR_STAT` | C | Статус участника | A/Q/R/W |
| `PAR_ENTNUM` | N | Номер заявки | 1 |
| `PAR_TPOINT` | N | Итоговые баллы (×100) | 4246 |
| `PAR_TPLACE` | N | Итоговое место | 30 |
| `PAR_INDEX` | N | Индекс в списке | 30 |
| `PAR_ODRYTM` | N | Ритм-танец порядок | 0 |

### 6.2 Атрибуты результатов по сегментам

Для каждого сегмента 1-6:

| Атрибут | Описание |
|---------|----------|
| `PAR_POINT1-6` | Баллы за сегмент (×100) |
| `PAR_PLACE1-6` | Место в сегменте |
| `PAR_INDEX1-6` | Индекс в сегменте |
| `PAR_STAT1-6` | Статус: O=OK, M=Missing, L=Last, I=Incomplete |
| `PAR_IPLAC1-6` | Промежуточное место |
| `PAR_IINDX1-6` | Промежуточный индекс |

### 6.3 Значения PAR_STAT

| Код | Описание |
|-----|----------|
| `A` | Active (активный) |
| `Q` | Qualified (квалифицировался) |
| `R` | Retired (снялся) |
| `W` | Withdrawn (отозван) |

---

## 7. ЭЛЕМЕНТ PLANNEDELEMENTS (Запланированные элементы)

Элементы, заявленные участником для программы.

### 7.1 Атрибуты PlannedElements

| Атрибут | Тип | Описание | Пример |
|---------|-----|----------|--------|
| `PEL_ID` | N | Уникальный ID | 1 |
| `PCT_ID` | N | Ссылка на участника | 2 |
| `PEL_1CATYP` | C | Тип категории для программы 1 | S |
| `PEL_1NAE01-20` | C | Короткие названия элементов | 3S |
| `PEL_1NWE01-20` | C | Нормализованные названия | 3S |
| `PEL_1NLE01-20` | C | Полные названия | Triple Salchow |
| `PEL_2NAE01-20` | C | Элементы программы 2 | |
| `PEL_1PBEST` | N | Личный рекорд программы 1 | |

**Примеры элементов:**
- `3S` - Triple Salchow (тройной сальхов)
- `2Lz+2Lo` - Double Lutz + Double Loop (комбинация)
- `LSp` - Layback Spin (заклон)
- `CCoSp` - Change Foot Combination Spin
- `StSq` - Step Sequence (дорожка шагов)
- `2A` - Double Axel (двойной аксель)

---

## 8. ЭЛЕМЕНТ PERFORMANCE (Результат выступления)

**Самый важный элемент** — содержит полные детали выступления спортсмена.

### 8.1 Основные атрибуты Performance

| Атрибут | Тип | Описание | Пример |
|---------|-----|----------|--------|
| `PRF_ID` | N | Уникальный ID | 431 |
| `PAR_ID` | N | Ссылка на участника | 1 |
| `SCP_ID` | N | Ссылка на сегмент | 15 |
| `PRF_STNUM` | N | Стартовый номер | 44 |
| `PRF_STGNUM` | N | Номер разминочной группы | 8 |
| `PRF_PLACE` | N | Место в сегменте | 30 |
| `PRF_INDEX` | N | Индекс | 30 |
| `PRF_POINTS` | N | **Общий балл (×100)** | 4246 = 42.46 |
| `PRF_STAT` | C | Статус: O=OK, I=Incomplete, L=Last | O |
| `PRF_LOCK` | N | Заблокировано | 1 |
| `PRF_QUALIF` | N | Квалификационный порог | 32 |

### 8.2 Атрибуты технического балла (TES)

| Атрибут | Тип | Описание | Пример |
|---------|-----|----------|--------|
| `PRF_M1TOT` | N | Сумма TES (×100) | 2129 = 21.29 |
| `PRF_M1RES` | N | Итог TES | 2129 |
| `PRF_PTOSKA` | N | Целевой технический балл | 1140 |

### 8.3 Атрибуты компонентов (PCS)

| Атрибут | Тип | Описание | Пример |
|---------|-----|----------|--------|
| `PRF_M2TOT` | N | Сумма PCS (×100) | 2117 = 21.17 |
| `PRF_M2RES` | N | Итог PCS | 2117 |

### 8.4 Атрибуты квалификации

| Атрибут | Описание |
|---------|----------|
| `PRF_PNEED1` | Баллы до 1 места |
| `PRF_PNEED2` | Баллы до 2 места |
| `PRF_PNEED3` | Баллы до 3 места |

### 8.5 Атрибуты элементов (E01-E20)

Для каждого элемента 01-20:

| Атрибут | Описание | Пример |
|---------|----------|--------|
| `PRF_PNAE01` | Планируемый элемент | 3S |
| `PRF_PNWE01` | Нормализованное название | 3S |
| `PRF_INAE01` | Исполненный элемент (от техпанели) | 3Sq |
| `PRF_XNAE01` | Итоговый элемент | 3Sq |
| `PRF_XCFE01` | Флаг подтверждения | X |
| `PRF_XTCE01` | Временная метка | 0.31 |
| `PRF_XBVE01` | **Базовая стоимость (×100)** | 430 = 4.30 |
| `PRF_E01J01-15` | **GOE от судей 1-15** (коды 0-15) | 14,14,14,14,14,9... |
| `PRF_E01PNL` | Бонус/штраф элемента (×100) | 118 |
| `PRF_E01RES` | **Итоговый балл элемента (×100)** | 401 = 4.01 |
| `PRF_E01HLF` | Половина программы: 1=первая, 2=вторая | 1 или 2 |
| `PRF_E01WBP` | Бонус за вторую половину (1=да, 0=нет) | 1 |

### 8.6 Декодирование GOE судей

**Правильная система кодирования GOE для оценок судей (проверено на реальных данных):**

Оценки судей имеют полную шкалу от **-5 до +5**.

| Код | GOE | Описание | Формула |
|-----|-----|----------|---------|
| `0` | **-5** | Очень плохое исполнение | -5 |
| `1` | **-3** | Ниже среднего | code - 4 |
| `2` | **-2** | Немного ниже среднего | code - 4 |
| `3` | **-1** | Чуть ниже среднего | code - 4 |
| `4` | **0** | Среднее (базовая стоимость) | code - 4 |
| `5` | **+1** | Чуть выше среднего | code - 4 |
| `6` | **+2** | Немного выше среднего | code - 4 |
| `7` | **+3** | Хорошее исполнение | code - 4 |
| `8` | **+4** | Отличное исполнение | +4 |
| `9` | **None** | Не используется / Пусто | None |
| `10` | **+5** | Превосходное исполнение | +5 |
| `11` | **-5** | Альтернативное кодирование -5 | code - 16 |
| `12` | **-4** | Альтернативное кодирование -4 | code - 16 |
| `13` | **+4** | Альтернативное кодирование +4 | code - 9 |
| `14` | **+5** | Альтернативное кодирование +5 | code - 9 |
| `15` | **-1** | Альтернативное кодирование -1 | code - 16 |

**Функция декодирования:**
```python
def decode_judge_score_xml(code):
    """Декодирование GOE оценки судьи из XML формата ISUCalcFS"""
    if code is None:
        return None
    code = str(code).strip()
    if not code:
        return None
    try:
        code_int = int(code)
    except ValueError:
        return None
    
    # Код 9 - не используется
    if code_int == 9:
        return None
    
    # Код 0: -5
    if code_int == 0:
        return -5
    
    # Коды 1-7: code - 4
    if 1 <= code_int <= 7:
        return code_int - 4  # 1→-3, 2→-2, 3→-1, 4→0, 5→+1, 6→+2, 7→+3
    
    # Код 8: +4
    if code_int == 8:
        return 4
    
    # Код 10: +5
    if code_int == 10:
        return 5
    
    # Коды 11-12: code - 16 (отрицательные значения)
    if 11 <= code_int <= 12:
        return code_int - 16  # 11→-5, 12→-4
    
    # Коды 13-14: code - 9 (положительные значения +4 и +5)
    if 13 <= code_int <= 14:
        return code_int - 9  # 13→+4, 14→+5
    
    # Код 15: code - 16
    if code_int == 15:
        return 15 - 16  # 15→-1
    
    return None
```

**Примеры из реальных XML:**
- `PRF_E01J01="14"` → GOE = +5 (14 - 9 = 5)
- `PRF_E02J01="13"` → GOE = +4 (13 - 9 = 4)
- `PRF_E06J01="4"` → GOE = 0 (4 - 4 = 0)
- `PRF_E10J01="12"` → GOE = -4 (12 - 16 = -4)
- `PRF_E01J01="11"` → GOE = -5 (11 - 16 = -5)

### 8.7 Бонус за вторую половину программы

Элементы, выполненные во второй половине программы, получают бонус **10%** к базовой стоимости.
Это относится только к **прыжковым элементам** (jumps).

**Атрибуты:**
- `PRF_E{idx}HLF` - Половина программы: `1` = первая половина, `2` = вторая половина
- `PRF_E{idx}WBP` - Бонус за вторую половину: `1` = бонус применен, `0` = нет бонуса

**Пример:**
```xml
<Performance 
    PRF_E08HLF="2"      <!-- Элемент 8 выполнен во второй половине -->
    PRF_E08WBP="1"      <!-- Бонус применен -->
    PRF_XBVE08="539"    <!-- Базовая стоимость: 5.39 -->
/>
```

В протоколе такой элемент отображается как: **5.39 x** (базовая стоимость уже увеличена на 10%)

**Важно:** Бонус применяется только к прыжковым элементам. Для спиралей, шагов и других элементов бонус не применяется, даже если они выполнены во второй половине.

### 8.8 Атрибуты компонентов программы (C01-C05)

Для каждого компонента 01-05:

| Атрибут | Описание |
|---------|----------|
| `PRF_C01J01-15` | Оценки судей за компонент 1 (Композиция) |
| `PRF_C02J01-15` | Оценки судей за компонент 2 |
| `PRF_C03J01-15` | Оценки судей за компонент 3 (Представление) |
| `PRF_C05J01-15` | Оценки судей за компонент 5 (Мастерство катания) |
| `PRF_C01RES` | Итоговый балл компонента 1 |

**Компоненты программы:**
1. **CO** - Composition (Композиция)
2. **TR** - Transitions (Связки) — если есть
3. **PR** - Presentation/Performance (Представление)
4. **IN** - Interpretation (Интерпретация) — если есть
5. **SK** - Skating Skills (Мастерство катания)

### 8.8 Атрибуты вычетов (Deductions)

| Атрибут | Описание |
|---------|----------|
| `PRF_DED01-17` | Значения вычетов |
| `PRF_DEDTOT` | Общая сумма вычетов |

### 8.9 Символы в названиях элементов

| Символ | Значение |
|--------|----------|
| `<` | Недокрут (underrotated) |
| `<<` | Сильный недокрут (downgraded) |
| `!` | Неясное ребро (unclear edge) |
| `e` | Неправильное ребро (wrong edge) |
| `q` | Четверть недокрута |
| `*` | Невалидный элемент |
| `+COMBO` | Комбинация не выполнена |
| `+SEQ` | Секвенция |
| `+REP` | Повтор |

---

## 9. ЭЛЕМЕНТ TIMESCHEDULE (Расписание)

### 9.1 Атрибуты TimeSchedule

| Атрибут | Описание | Формат |
|---------|----------|--------|
| `TIM_RESURF` | Время заливки льда | HH:MM:SS |
| `TIM_BEGTIM` | Время начала | HH:MM:SS |
| `TIM_ENDTIM` | Время окончания | HH:MM:SS |
| `TIM_WARMUP` | Время разминки | HH:MM:SS |
| `TIM_PERFOR` | Время выступлений | HH:MM:SS |
| `TIM_LSTWGR` | Последняя разминочная группа | HH:MM:SS |
| `TIM_JUDFST` | Первое судейство | HH:MM:SS |
| `TIM_JUDLST` | Последнее судейство | HH:MM:SS |
| `TIM_PREPVC` | Подготовка к церемонии | HH:MM:SS |
| `TIM_VC` | Церемония | HH:MM:SS |
| `TIM_INTROD` | Представление | HH:MM:SS |

---

## 10. ЭЛЕМЕНТ CLUB (Клуб)

### 10.1 Атрибуты Club

| Атрибут | Тип | Описание | Пример |
|---------|-----|----------|--------|
| `PCT_ID` | N | Уникальный ID | 1 |
| `PCT_EXTDT` | C | Внешний ID | 000000000000001 |
| `PCT_TYPE` | C | Тип: CLU | CLU |
| `PCT_STAT` | C | Статус | A |
| `PCT_CNAME` | C | Полное название | ООО Триумф |
| `PCT_SNAME` | C | Короткое название | ООО ТРИУ |
| `PCT_PLNAME` | C | Для протоколов | ООО Триумф |

---

## 11. СООТВЕТСТВИЕ XML ↔ DBF

| XML элемент | DBF таблица | Описание |
|-------------|-------------|----------|
| `<Event>` | EVT.DBF | Соревнование |
| `<Category>` | CAT.DBF | Категории |
| `<Segment>` | SCP.DBF | Сегменты программы |
| `<Person>` | PCT.DBF | Персоны/клубы |
| `<Participant>` | PAR.DBF | Участники категории |
| `<Performance>` | PRF.DBF | Результаты выступлений |
| `<PlannedElements>` | PEL.DBF | Запланированные элементы |
| `<TimeSchedule>` | TIM.DBF | Расписание |
| `<Judges_List>` | JPS.DBF | Судейские панели |

---

## 12. ФОРМУЛЫ РАСЧЁТА БАЛЛОВ

### 12.1 Общий балл сегмента (TSS)

```
TSS = TES + PCS - Deductions

Где:
- TES = PRF_M1RES / 100
- PCS = PRF_M2RES / 100
- Deductions = PRF_DEDTOT / 100
```

### 12.2 Технический балл (TES)

```
TES = Σ (PRF_ExxRES) / 100

Для каждого элемента:
Element_Score = Base_Value + GOE_Value
             = (PRF_XBVExx + PRF_ExxPNL) / 100
```

### 12.3 Компоненты программы (PCS)

```
PCS = Σ (Component_Score × Factor)

Для каждого компонента:
Component_Score = Trimmed_Mean(Judge_Scores) × Factor
```

### 12.4 Итоговый балл соревнования

```
Total = Σ (Segment_Scores)
      = PAR_POINT1 + PAR_POINT2 + ... 
      = PAR_TPOINT / 100
```

---

## 13. ПРИМЕРЫ КОДА НА PYTHON

### 13.1 Чтение XML файла

```python
import xml.etree.ElementTree as ET

def read_isucalcfs_xml(filepath):
    """Чтение XML файла ISUCalcFS"""
    tree = ET.parse(filepath)
    root = tree.getroot()
    
    # Получить данные соревнования
    event = root.find('Event')
    competition = {
        'name': event.get('EVT_NAME'),
        'place': event.get('EVT_PLACE'),
        'start_date': event.get('EVT_BEGDAT'),
        'end_date': event.get('EVT_ENDDAT')
    }
    
    return root, competition

# Использование
root, comp = read_isucalcfs_xml('pm.XML')
print(f"Соревнование: {comp['name']}")
print(f"Место: {comp['place']}")
```

### 13.2 Получение результатов категории

```python
def get_category_results(root, cat_id):
    """Получить результаты всех участников категории"""
    results = []
    
    # Найти категорию
    for cat in root.findall('.//Category'):
        if cat.get('CAT_ID') == str(cat_id):
            # Найти всех участников
            for par in cat.findall('.//Participant'):
                person = par.find('Person_Couple_Team')
                if person is not None:
                    results.append({
                        'place': int(par.get('PAR_TPLACE', 0)),
                        'name': person.get('PCT_CNAME', '').strip(),
                        'total_score': int(par.get('PAR_TPOINT', 0)) / 100,
                        'club': person.find('Club').get('PCT_CNAME') if person.find('Club') is not None else '',
                        'status': par.get('PAR_STAT')
                    })
    
    return sorted(results, key=lambda x: x['place'] if x['place'] > 0 else 999)

# Использование
results = get_category_results(root, 1)
for r in results[:10]:
    print(f"{r['place']}. {r['name']} - {r['total_score']:.2f}")
```

### 13.3 Получение деталей выступления

```python
def get_performance_details(root, prf_id):
    """Получить детали выступления по ID"""
    
    for prf in root.findall('.//Performance'):
        if prf.get('PRF_ID') == str(prf_id):
            # Основные данные
            details = {
                'start_num': int(prf.get('PRF_STNUM', 0)),
                'place': int(prf.get('PRF_PLACE', 0)),
                'total': int(prf.get('PRF_POINTS', 0)) / 100,
                'tes': int(prf.get('PRF_M1RES', 0)) / 100,
                'pcs': int(prf.get('PRF_M2RES', 0)) / 100,
                'elements': []
            }
            
            # Элементы
            for i in range(1, 21):
                elem_name = prf.get(f'PRF_XNAE{i:02d}')
                if elem_name and elem_name.strip():
                    base_value = int(prf.get(f'PRF_XBVE{i:02d}', 0)) / 100
                    result = int(prf.get(f'PRF_E{i:02d}RES', 0)) / 100
                    
                    # GOE судей
                    goe_codes = []
                    for j in range(1, 16):
                        code = prf.get(f'PRF_E{i:02d}J{j:02d}')
                        if code and code != '9':
                            goe_codes.append(int(code))
                    
                    details['elements'].append({
                        'name': elem_name.strip(),
                        'base_value': base_value,
                        'score': result,
                        'goe_codes': goe_codes
                    })
            
            return details
    
    return None

# Использование
perf = get_performance_details(root, 433)
print(f"Место: {perf['place']}, Баллы: {perf['total']:.2f}")
print(f"TES: {perf['tes']:.2f}, PCS: {perf['pcs']:.2f}")
print("\nЭлементы:")
for e in perf['elements']:
    print(f"  {e['name']}: BV={e['base_value']:.2f}, Score={e['score']:.2f}")
```

### 13.4 Экспорт в JSON

```python
import json

def export_competition_to_json(root, output_file):
    """Экспорт данных соревнования в JSON"""
    event = root.find('Event')
    
    data = {
        'competition': {
            'name': event.get('EVT_NAME'),
            'place': event.get('EVT_PLACE'),
            'dates': f"{event.get('EVT_BEGDAT')} - {event.get('EVT_ENDDAT')}"
        },
        'categories': []
    }
    
    for cat in root.findall('.//Category'):
        cat_data = {
            'id': cat.get('CAT_ID'),
            'name': cat.get('CAT_NAME'),
            'type': cat.get('CAT_TYPE'),
            'participants': []
        }
        
        for par in cat.findall('.//Participant'):
            person = par.find('Person_Couple_Team')
            if person is not None:
                cat_data['participants'].append({
                    'place': par.get('PAR_TPLACE'),
                    'name': person.get('PCT_CNAME'),
                    'score': int(par.get('PAR_TPOINT', 0)) / 100
                })
        
        data['categories'].append(cat_data)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Использование
export_competition_to_json(root, 'competition_export.json')
```

---

## 14. ОСОБЕННОСТИ ФОРМАТА

### 14.1 Кодировка и символы

- XML файл в кодировке UTF-8
- Специальные символы экранированы: `&lt;` = `<`, `&amp;` = `&`
- Кириллица поддерживается нативно

### 14.2 Отличия от DBF

| Аспект | DBF | XML |
|--------|-----|-----|
| Структура | Таблицы отдельно | Всё в одном файле |
| Связи | Через ID | Вложенность элементов |
| Размер | Много мелких файлов | Один большой файл |
| GOE кодирование | 5-15 | 1-13 |
| Пустые значения | Null/пробел | Отсутствие атрибута |

### 14.3 Ограничения

- XML файл может быть очень большим (2+ МБ)
- Не содержит справочник элементов ELM
- Не содержит исторические данные BST
- Не содержит конфигурацию CFG

### 14.4 Соответствие XML ↔ DBF (ключевые таблицы)

| XML элемент | Основные атрибуты | Аналог DBF |
|------------|-------------------|------------|
| `<Event>` | EVT_* | **EVT.DBF** |
| `<Category>` | CAT_* | **CAT.DBF** |
| `<Segment>` | SCP_* | **SCP.DBF** |
| `<Person_Couple_Team>` | PCT_* | **PCT.DBF** |
| `<Club>` | PCT_* (тип клуба) | **PCT.DBF** |
| `<Participant>` | PAR_* | **PAR.DBF** |
| `<Performance>` | PRF_* | **PRF.DBF** |
| `<PlannedElements>` | PEL_* | **PEL.DBF** |
| `<Judges_List>` / `<Person>` | PCT_* (судьи/офиц.) | **PCT.DBF** + **JPS/JDG** |

#### Ключевые связи (как в DBF, но через вложенность)
- `Category.CAT_ID` → `Segment.CAT_ID`
- `Participant.CAT_ID` → `Category.CAT_ID`
- `Participant.PCT_ID` → `Person_Couple_Team.PCT_ID`
- `Performance.PAR_ID` → `Participant.PAR_ID`
- `Performance.SCP_ID` → `Segment.SCP_ID`
- `Person_Couple_Team.PCT_CLBID` → `<Club PCT_ID=...>`

#### Типы персон (PCT_TYPE)
- `PER` — одиночник
- `COU` — пара/танцы (в XML чаще одна запись на пару)
- Судьи/официальные лица также приходят как `Person` внутри `Judges_List`

---

## 15. ЗАКЛЮЧЕНИЕ

XML формат ISUCalcFS представляет собой полный экспорт данных соревнования в едином файле. Формат содержит:

1. **Информацию о соревновании** - название, место, даты
2. **Категории участников** - возрастные группы и дисциплины
3. **Сегменты программы** - КП, ПП, ритм-танец
4. **Данные участников** - имена, клубы, тренеры, музыка
5. **Результаты выступлений** - полная детализация оценок
6. **Судейские оценки** - GOE за каждый элемент от каждого судьи

**Дата документации:** Январь 2026  
**Анализ выполнен на основе:** pm.XML соревнования "Первенство Москвы"
