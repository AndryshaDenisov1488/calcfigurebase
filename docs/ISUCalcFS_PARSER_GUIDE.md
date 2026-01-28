# ISUCalcFS XML Parser Guide
## Полная инструкция для парсинга данных участников

---

## 1. Ключевая классификация категорий

### 1.1 Атрибуты категории для определения типа

| Атрибут | Значения | Описание |
|---------|----------|----------|
| `CAT_GENDER` | `F` | Женщины/Девочки (одиночницы) |
| `CAT_GENDER` | `M` | Мужчины/Мальчики (одиночники) |
| `CAT_GENDER` | `T` | Смешанные (Пары + Танцы на льду) |
| `CAT_TYPE` | `S` | Одиночное катание (Singles) |
| `CAT_TYPE` | `D` | Танцы на льду (Ice Dance) |
| `CAT_TYPE` | `P` | Парное катание (Pairs) |

### 1.2 Комбинации для определения вида спорта

```
CAT_GENDER="F" + CAT_TYPE="S" → Одиночницы (девочки/женщины)
CAT_GENDER="M" + CAT_TYPE="S" → Одиночники (мальчики/мужчины)
CAT_GENDER="T" + CAT_TYPE="D" → Танцы на льду
CAT_GENDER="T" + CAT_TYPE="P" → Парное катание
```

**ВАЖНО:** `CAT_GENDER` относится к КАТЕГОРИИ, а не к индивидуальному спортсмену!

---

## 2. Структура данных участников

### 2.1 Иерархия элементов

```
<Category>
  └─ <Segments_List>
       └─ <Segment>
            └─ <Participants_List>
                 └─ <Participant>
                      ├─ <Person_Couple_Team>
                      │    └─ <Team_Members>        ← Только для пар/танцев!
                      │         ├─ <Person>         ← Партнёрша
                      │         └─ <Person>         ← Партнёр
                      │    └─ <Club/>               ← Клуб (у одиночников)
                      └─ <PlannedElements>          ← Запланированные элементы
```

### 2.2 Различие одиночников и пар

| Характеристика | Одиночники | Пары/Танцы |
|----------------|------------|------------|
| `PCT_TYPE` | `"PER"` | `"COU"` |
| `<Team_Members>` | Отсутствует | Присутствует с 2 Person |
| Данные партнёра | Нет | Есть (PCT_P* атрибуты) |
| `<Club>` | Внутри Person_Couple_Team | Внутри каждого Person |

---

## 3. Атрибуты Person_Couple_Team

### 3.1 Общие атрибуты (для всех типов)

| Атрибут | Описание | Пример |
|---------|----------|--------|
| `PCT_ID` | Уникальный идентификатор | `"2"`, `"147"` |
| `PCT_EXTDT` | Внешний идентификатор (из реестра спортсменов) | `"000000001415631"` |
| `PCT_TYPE` | Тип: `"PER"` (персона), `"COU"` (пара) | `"PER"` / `"COU"` |
| `PCT_STAT` | Статус | `"A"` (активен) |
| `PCT_CNAME` | Полное имя для отображения | `"Варвара БОГОМОЛОВА"` |
| `PCT_SNAME` | Короткий код (8 символов) | `"БОГОВАРВ"` |
| `PCT_PLNAME` | Полное официальное имя | `"Варвара Олеговна БОГОМОЛОВА"` |
| `PCT_GNAME` | Имя (Given name) | `"Варвара"` |
| `PCT_GNAMEI` | Инициал имени | `"В."` |
| `PCT_FNAME` | Фамилия (Family name) | `"Богомолова"` |
| `PCT_FNAMEC` | Фамилия (CAPS) | `"БОГОМОЛОВА"` |
| `PCT_BDAY` | Дата рождения (YYYYMMDD) | `"20150123"` |
| `PCT_GENDER` | Пол спортсмена | `"F"` / `"M"` |
| `PCT_CLBID` | ID клуба | `"1"` |
| `PCT_COANAM` | Имена тренеров | `"Софья Федченко"` |
| `PCT_COMENT` | Комментарий (разряд и т.д.) | `"2 СП"` |
| `PCT_SPMNAM` | Музыка короткой программы | `"Charlie Chaplin..."` |
| `PCT_FSMNAM` | Музыка произвольной программы | `"Ludovico Einaudi..."` |

### 3.2 Форматы имён

| Атрибут | Описание | Пример |
|---------|----------|--------|
| `PCT_TLNAME` | Полное имя для таблицы | `"Варвара БОГОМОЛОВА"` |
| `PCT_TSNAME` | Короткое имя для таблицы | `"ВарвараБОГОМОЛОВА"` |
| `PCT_S1NAME` | Короткое имя (вариант 1, до 28 симв.) | `"Варвара БОГОМОЛОВА"` |
| `PCT_S2NAME` | Короткое имя (вариант 2, до 22 симв.) | `"Варвара БОГОМОЛОВА"` |
| `PCT_S3NAME` | Короткое имя (вариант 3, до 19 симв.) | `"Варвара БОГОМОЛОВА"` |
| `PCT_S4NAME` | Короткое имя (вариант 4, до 16 симв.) | `"Варвара БОГОМОЛОВА"` |
| `PCT_WFNAME` | Web-версия фамилии | `"Варвара БОГОМОЛОВА"` |
| `PCT_WGNAME` | Web-версия имени | `"Варвара БОГОМОЛОВА"` |
| `PCT_RNAME` | Обратный формат | `"БОГОМОЛОВА Варвара"` |
| `PCT_INAME` | Формат с инициалом | `"БОГОМОЛОВА В."` |

### 3.3 Дополнительные атрибуты для ПАР и ТАНЦЕВ

| Атрибут | Описание | Пример |
|---------|----------|--------|
| `PCT_PCTID` | ID партнёрши (первый Person) | `"145"` |
| `PCT_PPCTID` | ID партнёра (второй Person) | `"146"` |
| `PCT_PGNAME` | Имя партнёра | `"Алексей"` |
| `PCT_PFNAMC` | Фамилия партнёра (CAPS) | `"ЕРЕМИН"` |
| `PCT_PBDAY` | Дата рождения партнёра | `"20100914"` |

**ВАЖНО:** В атрибутах уровня `<Person_Couple_Team>` для пар:
- `PCT_GNAME`, `PCT_FNAME`, `PCT_BDAY` — это данные **ПАРТНЁРШИ**
- `PCT_PGNAME`, `PCT_PFNAMC`, `PCT_PBDAY` — это данные **ПАРТНЁРА**

---

## 4. Структура Team_Members (только для пар/танцев)

### 4.1 Общий формат

```xml
<Team_Members>
    <Person PCT_ID="145" PCT_TYPE="PER" PCT_AFUNCT="CMP" PCT_GENDER="F" 
            PCT_GNAME="Амалия" PCT_FNAME="Ткалич" PCT_BDAY="20140320" ...>
        <Club/>
    </Person>
    <Person PCT_ID="146" PCT_TYPE="PER" PCT_AFUNCT="CMP" PCT_GENDER="F" 
            PCT_GNAME="Алексей" PCT_FNAME="Еремин" PCT_BDAY="20100914" .../>
</Team_Members>
```

### 4.2 Порядок партнёров

| Позиция | Описание | Ожидаемый пол |
|---------|----------|---------------|
| Первый `<Person>` | Партнёрша (lady) | Female |
| Второй `<Person>` | Партнёр (man) | Male |

### 4.3 Атрибуты Person в Team_Members

| Атрибут | Описание |
|---------|----------|
| `PCT_ID` | Уникальный ID спортсмена |
| `PCT_TYPE` | Всегда `"PER"` |
| `PCT_AFUNCT` | Функция: `"CMP"` = Competitor (спортсмен) |
| `PCT_STAT` | Статус: `"A"` = Active |
| `PCT_GENDER` | Пол (`"F"` / `"M"`) |
| `PCT_GNAME` | Имя |
| `PCT_FNAME` | Фамилия |
| `PCT_FNAMEC` | Фамилия (CAPS) |
| `PCT_BDAY` | Дата рождения |
| `PCT_CLBID` | ID клуба |
| `PCT_COMENT` | Комментарий (разряд) |
| ... | И другие стандартные атрибуты имён |

**ВНИМАНИЕ:** `PCT_GENDER="F"` у партнёра (мужчины) — это **БАГ в данных ISUCalcFS**, не используйте для определения пола!

---

## 5. Атрибуты Participant

| Атрибут | Описание | Пример |
|---------|----------|--------|
| `PAR_ID` | ID участия | `"127"` |
| `PCT_ID` | ID спортсмена/пары (ссылка) | `"147"` |
| `CAT_ID` | ID категории | `"6"` |
| `PAR_CLBID` | ID клуба | `"211"` |
| `PAR_STAT` | Статус участия | `"A"`, `"Q"`, `"R"` |
| `PAR_ENTNUM` | Номер заявки | `"3"` |
| `PAR_TPOINT` | Итоговые очки (* 100) | `"5943"` → 59.43 |
| `PAR_TPLACE` | Итоговое место | `"1"` |
| `PAR_INDEX` | Индекс в категории | `"1"` |
| `PAR_POINT1` | Очки после сегмента 1 | `"5943"` |
| `PAR_PLACE1` | Место после сегмента 1 | `"1"` |
| `PAR_INDEX1` | Индекс после сегмента 1 | `"1"` |
| `PAR_STAT1` | Статус в сегменте 1 | `"O"`, `"L"`, `"I"` |

### Статусы участия (PAR_STAT):
- `A` — Active (активен)
- `Q` — Qualified (квалифицирован)
- `R` — Reserved/Withdrawn (снят)

### Статусы в сегменте (PAR_STATn):
- `O` — Official (официальный результат)
- `L` — Loaded (загружен)
- `I` — Inactive (неактивен)
- `M` — Missing (пропущен)

---

## 6. PlannedElements (Запланированные элементы)

### 6.1 Формат атрибутов

```
PEL_1NAE01 — Название элемента 1 (сегмент 1)
PEL_1NWE01 — Код элемента 1 (сегмент 1)
PEL_1NLE01 — Полное название элемента 1 (сегмент 1)
PEL_2NAE01 — Название элемента 1 (сегмент 2)
...
```

### 6.2 Шаблон именования

```
PEL_{segment}NAE{element_num} — Аббревиатура элемента
PEL_{segment}NWE{element_num} — Код элемента  
PEL_{segment}NLE{element_num} — Полное название

segment: 1 = КП/Ритм-танец, 2 = ПП/Произвольный танец
element_num: 01-20
```

### 6.3 Пример для пары

```xml
<PlannedElements PEL_ID="133" PCT_ID="147" PEL_1CATYP="P"
    PEL_1NAE01="2Tw" PEL_1NWE01="2Tw" PEL_1NLE01="Double Twist Lift"
    PEL_1NAE02="2A" PEL_1NWE02="2A" PEL_1NLE02="Double Axel"
    PEL_1NAE03="2FTh" PEL_1NWE03="2FTh" PEL_1NLE03="Throw Double Flip"
    ...
/>
```

---

## 7. Алгоритм парсинга

### 7.1 Определение типа категории

```python
def get_category_type(category_elem):
    cat_gender = category_elem.get('CAT_GENDER', '')
    cat_type = category_elem.get('CAT_TYPE', '')
    
    if cat_type == 'S':
        if cat_gender == 'F':
            return 'WOMEN_SINGLES'
        elif cat_gender == 'M':
            return 'MEN_SINGLES'
    elif cat_type == 'D' and cat_gender == 'T':
        return 'ICE_DANCE'
    elif cat_type == 'P' and cat_gender == 'T':
        return 'PAIRS'
    
    return 'UNKNOWN'
```

### 7.2 Извлечение данных участника

```python
def extract_participant_data(participant_elem, category_type):
    pct_elem = participant_elem.find('Person_Couple_Team')
    result = {
        'participant_id': participant_elem.get('PAR_ID'),
        'person_id': pct_elem.get('PCT_ID'),
        'status': participant_elem.get('PAR_STAT'),
        'entry_number': participant_elem.get('PAR_ENTNUM'),
        'total_score': int(participant_elem.get('PAR_TPOINT', 0)) / 100,
        'place': participant_elem.get('PAR_TPLACE'),
        'category_type': category_type,
        'club_id': pct_elem.get('PCT_CLBID'),
        'coaches': pct_elem.get('PCT_COANAM', ''),
        'comment': pct_elem.get('PCT_COMENT', ''),
        'music_sp': pct_elem.get('PCT_SPMNAM', ''),
        'music_fp': pct_elem.get('PCT_FSMNAM', ''),
    }
    
    pct_type = pct_elem.get('PCT_TYPE')
    
    if pct_type == 'PER':  # Одиночник
        result['type'] = 'SINGLE'
        result['athlete'] = extract_person_data(pct_elem)
    
    elif pct_type == 'COU':  # Пара/Танцы
        result['type'] = 'COUPLE'
        team_members = pct_elem.find('Team_Members')
        
        if team_members is not None:
            persons = team_members.findall('Person')
            if len(persons) >= 2:
                result['lady'] = extract_person_data(persons[0])
                result['man'] = extract_person_data(persons[1])
        else:
            # Резервный метод: из атрибутов Person_Couple_Team
            result['lady'] = {
                'id': pct_elem.get('PCT_PCTID'),
                'given_name': pct_elem.get('PCT_GNAME'),
                'family_name': pct_elem.get('PCT_FNAME'),
                'birth_date': format_date(pct_elem.get('PCT_BDAY', '')),
            }
            result['man'] = {
                'id': pct_elem.get('PCT_PPCTID'),
                'given_name': pct_elem.get('PCT_PGNAME'),
                'family_name': pct_elem.get('PCT_PFNAMC'),
                'birth_date': format_date(pct_elem.get('PCT_PBDAY', '')),
            }
    
    return result


def extract_person_data(person_elem):
    """Извлекает данные одного спортсмена"""
    bday = person_elem.get('PCT_BDAY', '')
    
    return {
        'id': person_elem.get('PCT_ID'),
        'external_id': person_elem.get('PCT_EXTDT', ''),
        'given_name': person_elem.get('PCT_GNAME', ''),
        'family_name': person_elem.get('PCT_FNAME', ''),
        'family_name_caps': person_elem.get('PCT_FNAMEC', ''),
        'full_name': person_elem.get('PCT_CNAME', ''),
        'official_name': person_elem.get('PCT_PLNAME', ''),
        'birth_date': format_date(bday),
        'birth_year': bday[:4] if len(bday) >= 4 else '',
        'club_id': person_elem.get('PCT_CLBID', ''),
        'comment': person_elem.get('PCT_COMENT', ''),  # Разряд
    }


def format_date(date_str):
    """Конвертирует YYYYMMDD в YYYY-MM-DD"""
    if len(date_str) == 8:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return date_str
```

### 7.3 Полный цикл парсинга

```python
import xml.etree.ElementTree as ET

def parse_competition_xml(filepath):
    tree = ET.parse(filepath)
    root = tree.getroot()
    
    competition = {
        'event': {},
        'categories': [],
        'participants': [],
        'athletes': []  # Плоский список всех спортсменов
    }
    
    # Данные соревнования
    event = root.find('Event')
    if event is not None:
        competition['event'] = {
            'id': event.get('EVT_ID'),
            'name': event.get('EVT_NAME'),
            'location': event.get('EVT_CTNM'),
            'start_date': format_date(event.get('EVT_STDT', '')),
            'end_date': format_date(event.get('EVT_ENDT', '')),
        }
    
    # Категории и участники
    for category in root.findall('.//Category'):
        cat_id = category.get('CAT_ID')
        cat_type = get_category_type(category)
        
        cat_data = {
            'id': cat_id,
            'name': category.get('CAT_NAME'),
            'type': cat_type,
            'gender': category.get('CAT_GENDER'),
            'discipline': category.get('CAT_TYPE'),
            'level': category.get('CAT_LEVEL'),
            'entries': int(category.get('CAT_NENT', 0)),
            'participants': []
        }
        
        # Участники категории
        for participant in category.findall('.//Participant'):
            part_data = extract_participant_data(participant, cat_type)
            part_data['category_id'] = cat_id
            part_data['category_name'] = cat_data['name']
            
            cat_data['participants'].append(part_data)
            competition['participants'].append(part_data)
            
            # Добавляем в плоский список спортсменов
            if part_data.get('type') == 'SINGLE':
                athlete = part_data['athlete'].copy()
                athlete['category_type'] = cat_type
                athlete['category_id'] = cat_id
                competition['athletes'].append(athlete)
            elif part_data.get('type') == 'COUPLE':
                if 'lady' in part_data:
                    lady = part_data['lady'].copy()
                    lady['category_type'] = cat_type
                    lady['category_id'] = cat_id
                    lady['role'] = 'LADY'
                    competition['athletes'].append(lady)
                if 'man' in part_data:
                    man = part_data['man'].copy()
                    man['category_type'] = cat_type
                    man['category_id'] = cat_id
                    man['role'] = 'MAN'
                    competition['athletes'].append(man)
        
        competition['categories'].append(cat_data)
    
    return competition
```

---

## 8. Примеры реальных данных

### 8.1 Одиночница (Девочка)

```xml
<Category CAT_ID="1" CAT_GENDER="F" CAT_TYPE="S" 
          CAT_NAME="Девочки, младшая группа">
  ...
  <Participant PAR_ID="3" PCT_ID="6" CAT_ID="1" PAR_TPOINT="5943" PAR_TPLACE="1">
    <Person_Couple_Team PCT_ID="6" PCT_TYPE="PER" PCT_AFUNCT="CMP"
        PCT_CNAME="Софья ВАГИНА"
        PCT_GNAME="Софья" PCT_FNAME="Вагина"
        PCT_BDAY="20160407" PCT_GENDER="F"
        PCT_COANAM="Евгений Плющенко"
        PCT_COMENT="2 СП">
      <Club PCT_ID="5" PCT_CNAME="ООО Академия фигурного катания..."/>
    </Person_Couple_Team>
    <PlannedElements PEL_1NAE01="3F" PEL_1NAE02="2A" .../>
  </Participant>
</Category>
```

**Результат парсинга:**
```json
{
  "participant_id": "3",
  "type": "SINGLE",
  "category_type": "WOMEN_SINGLES",
  "total_score": 59.43,
  "place": "1",
  "athlete": {
    "id": "6",
    "given_name": "Софья",
    "family_name": "Вагина",
    "birth_date": "2016-04-07",
    "birth_year": "2016"
  }
}
```

### 8.2 Танцевальная пара

```xml
<Category CAT_ID="5" CAT_GENDER="T" CAT_TYPE="D"
          CAT_NAME="Танцы на льду, 1 Спортивный разряд">
  ...
  <Participant PAR_ID="131" PCT_ID="190" CAT_ID="5">
    <Person_Couple_Team PCT_ID="190" PCT_TYPE="COU"
        PCT_CNAME="Анастасия ТВЕРДОХЛЕБОВА / Илья ПАВЛИНОВ"
        PCT_GNAME="Анастасия" PCT_FNAME="ТВЕРДОХЛЕБОВА"
        PCT_BDAY="20100206"
        PCT_PCTID="188" PCT_PPCTID="189"
        PCT_PGNAME="Илья" PCT_PFNAMC="ПАВЛИНОВ"
        PCT_PBDAY="20091229">
      <Team_Members>
        <Person PCT_ID="188" PCT_TYPE="PER" PCT_AFUNCT="CMP"
            PCT_GNAME="Анастасия" PCT_FNAME="Твердохлебова"
            PCT_BDAY="20100206" PCT_GENDER="F">
          <Club/>
        </Person>
        <Person PCT_ID="189" PCT_TYPE="PER" PCT_AFUNCT="CMP"
            PCT_GNAME="Илья" PCT_FNAME="Павлинов"
            PCT_BDAY="20091229" PCT_GENDER="F">
        </Person>
      </Team_Members>
    </Person_Couple_Team>
    <PlannedElements PEL_2CATYP="D" PEL_2NAE01="ChSp" .../>
  </Participant>
</Category>
```

**Результат парсинга:**
```json
{
  "participant_id": "131",
  "type": "COUPLE",
  "category_type": "ICE_DANCE",
  "lady": {
    "id": "188",
    "given_name": "Анастасия",
    "family_name": "Твердохлебова",
    "birth_date": "2010-02-06",
    "birth_year": "2010"
  },
  "man": {
    "id": "189",
    "given_name": "Илья",
    "family_name": "Павлинов",
    "birth_date": "2009-12-29",
    "birth_year": "2009"
  }
}
```

### 8.3 Спортивная пара

```xml
<Category CAT_ID="6" CAT_GENDER="T" CAT_TYPE="P"
          CAT_NAME="Парное катание, 1 Спортивный разряд">
  ...
  <Participant PAR_ID="127" PCT_ID="147" CAT_ID="6">
    <Person_Couple_Team PCT_ID="147" PCT_TYPE="COU"
        PCT_CNAME="Амалия ТКАЛИЧ / Алексей ЕРЕМИН"
        PCT_GNAME="Амалия" PCT_FNAME="ТКАЛИЧ"
        PCT_BDAY="20140320"
        PCT_PCTID="145" PCT_PPCTID="146"
        PCT_PGNAME="Алексей" PCT_PFNAMC="ЕРЕМИН"
        PCT_PBDAY="20100914">
      <Team_Members>
        <Person PCT_ID="145" PCT_GNAME="Амалия" PCT_FNAME="Ткалич"
                PCT_BDAY="20140320" PCT_GENDER="F"/>
        <Person PCT_ID="146" PCT_GNAME="Алексей" PCT_FNAME="Еремин"
                PCT_BDAY="20100914" PCT_GENDER="F"/>
      </Team_Members>
    </Person_Couple_Team>
  </Participant>
</Category>
```

---

## 9. Особенности и подводные камни

### 9.1 Некорректный PCT_GENDER у мужчин

**ПРОБЛЕМА:** В данных ISUCalcFS поле `PCT_GENDER` у мужчин в парах/танцах часто содержит `"F"` вместо `"M"`.

**РЕШЕНИЕ:** НЕ ИСПОЛЬЗОВАТЬ `PCT_GENDER` для определения пола в парах/танцах! Определять пол по:
1. Позиции в `<Team_Members>` (первый = партнёрша, второй = партнёр)
2. По `CAT_GENDER` категории для одиночников

### 9.2 Разные источники данных партнёров

Для пар данные партнёров доступны в двух местах:
1. **Предпочтительно:** `<Team_Members>` → полные данные каждого
2. **Резерв:** атрибуты PCT_PCTID, PCT_PGNAME, PCT_PFNAMC, PCT_PBDAY в `<Person_Couple_Team>`

### 9.3 Форматы дат

- Все даты в формате `YYYYMMDD` (8 символов)
- Для вывода конвертировать в `YYYY-MM-DD`
- Для расчёта возраста использовать только год: `bday[:4]`

### 9.4 Очки умножены на 100

Все числовые оценки хранятся умноженными на 100:
- `PAR_TPOINT="5943"` → 59.43 балла
- Делить на 100 при выводе

### 9.5 Комментарии/Разряды

Спортивный разряд хранится в `PCT_COMENT`:
- `"2 СП"` — 2-й спортивный разряд
- `"1 СП"` — 1-й спортивный разряд
- `"КМС"` — кандидат в мастера спорта
- И т.д.

### 9.6 КРИТИЧНО: Лишние пробелы и Tab символы в строках

**ПРОБЛЕМА 1: Пробелы в начале имён**

```xml
<!-- ПЛОХО: лишний пробел в начале! -->
<Person PCT_CNAME=" Татьяна ФЕДОРОВА" PCT_PLNAME=" Татьяна ФЕДОРОВА"/>
```

**ПРОБЛЕМА 2: Tab символы в названиях клубов**

```xml
<!-- ПЛОХО: Tab в конце названия! -->
<Club PCT_CNAME="ГБУ ДО Московская академия фигурного катания на коньках	"/>
<!--                                                                    ↑ TAB -->
```

**ПРОБЛЕМА 3: Двойные пробелы в именах**

```xml
<Person PCT_CNAME=" Руслана  КАРЕВА"/>  <!-- ДВА пробела между именем и фамилией -->
```

**РЕШЕНИЕ:** Обязательно применять `.strip()` и нормализацию пробелов:

```python
import re

def normalize_string(value):
    """Нормализует строку: убирает лишние пробелы и tabs"""
    if not value:
        return ''
    # Заменяем tabs на пробелы
    value = value.replace('\t', ' ')
    # Убираем множественные пробелы
    value = re.sub(r'\s+', ' ', value)
    # Убираем пробелы по краям
    return value.strip()
```

### 9.7 PCT_GENDER="F" у мужчин-судей

**ПРОБЛЕМА:** Поле `PCT_GENDER` у судей-МУЖЧИН также содержит `"F"`!

```xml
<Person PCT_ID="165" PCT_CNAME=" Сергей ЖЕРНОВ" PCT_GENDER="F"/>  <!-- МУЖЧИНА! -->
<Person PCT_ID="158" PCT_CNAME=" Антон СОЛОВЬЕВ" PCT_GENDER="F"/> <!-- МУЖЧИНА! -->
<Person PCT_ID="160" PCT_CNAME=" Иван ВЕДЕРОВ" PCT_GENDER="F"/>   <!-- МУЖЧИНА! -->
```

**ВЫВОД:** `PCT_GENDER` ненадёжен ВЕЗДЕ — и у спортсменов, и у судей!

### 9.8 Дублирование записей судей

**ПРОБЛЕМА:** Один судья может встречаться ДВАЖДЫ в одном `<Judges_List>`:

```xml
<Judges_List>
  <Person PCT_ID="157" PCT_CNAME=" Татьяна ФЕДОРОВА"/>
  <Person PCT_ID="162" .../>
  ...
  <Person PCT_ID="157" PCT_CNAME=" Татьяна ФЕДОРОВА"/>  <!-- ДУБЛИКАТ! -->
  <Person PCT_ID="158" .../>
</Judges_List>
```

**РЕШЕНИЕ:** При парсинге судей использовать `dict` или `set` по `PCT_ID` для дедупликации.

### 9.9 Статусы участников и выступлений

**PAR_STAT (статус участника в категории):**

| Значение | Описание |
|----------|----------|
| `A` | Active — активен, участвует |
| `Q` | Qualified — квалифицирован |
| `R` | Retired/Withdrawn — снялся |

**PAR_STATn / PRF_STAT (статус в сегменте):**

| Значение | Описание |
|----------|----------|
| `O` | OK — выступление состоялось |
| `L` | Live — идёт/ожидается |
| `M` | Missing — отсутствует в сегменте |
| `I` | Incomplete — не завершено/снялся |

**ВАЖНО:** Участник с `PAR_STAT="R"` не имеет очков (`PAR_TPOINT`, `PAR_TPLACE` отсутствуют)!

### 9.10 Оценки судей: правильная формула декодирования

**В Performance оценки судей (PRF_E01J01 и т.д.) имеют полную шкалу от -5 до +5:**

| Код | GOE | Формула | Описание |
|-----|-----|---------|----------|
| `0` | **-5** | -5 | Очень плохое исполнение |
| `1` | **-3** | code - 4 | Ниже среднего |
| `2` | **-2** | code - 4 | Немного ниже среднего |
| `3` | **-1** | code - 4 | Чуть ниже среднего |
| `4` | **0** | code - 4 | Среднее (базовая стоимость) |
| `5` | **+1** | code - 4 | Чуть выше среднего |
| `6` | **+2** | code - 4 | Немного выше среднего |
| `7` | **+3** | code - 4 | Хорошее исполнение |
| `8` | **+4** | +4 | Отличное исполнение |
| `9` | **None** | None | Не используется |
| `10` | **+5** | +5 | Превосходное исполнение |
| `11` | **-5** | code - 16 | Альтернативное кодирование -5 |
| `12` | **-4** | code - 16 | Альтернативное кодирование -4 |
| `13` | **+4** | code - 9 | Альтернативное кодирование +4 |
| `14` | **+5** | code - 9 | Альтернативное кодирование +5 |
| `15` | **-1** | code - 16 | Альтернативное кодирование -1 |

**Примеры:**
- `PRF_E01J01="14"` → GOE = 14 - 9 = **+5**
- `PRF_E06J01="4"` → GOE = 4 - 4 = **0**
- `PRF_E10J01="12"` → GOE = 12 - 16 = **-4**
- `PRF_E01J01="11"` → GOE = 11 - 16 = **-5**

### 9.11 HTML entities в названиях элементов

**ПРОБЛЕМА:** Специальные символы экранируются как HTML entities:

```xml
<!-- < экранируется как &lt; -->
<Performance PRF_INAE01="3Lz&lt;+2T"/>  <!-- означает 3Lz<+2T (недокрут) -->

<!-- > экранируется как &gt; -->
<!-- & экранируется как &amp; -->
```

**РЕШЕНИЕ:** При парсинге XML используйте стандартные библиотеки — они автоматически декодируют entities.

### 9.12 Регистр в названиях элементов

**ПРОБЛЕМА:** Запланированные элементы могут иметь разный регистр:

```xml
<Performance PRF_PNAE01="2a" PRF_PNWE01="2A"/>  <!-- маленькая vs БОЛЬШАЯ -->
<Performance PRF_PNAE02="3s+2t" PRF_PNWE02="3S+2T"/>
```

**РЕШЕНИЕ:** Приводить к единому регистру при сравнении: `.upper()` или `.lower()`

### 9.13 PCT_COANAM — разные значения для судей и спортсменов

**Для спортсменов:** содержит имена тренеров
```xml
<Person_Couple_Team PCT_COANAM="Евгений Плющенко"/>
```

**Для судей:** содержит регион/категорию
```xml
<Person PCT_AFUNCT="JDG" PCT_COANAM="Москва, ВК"/>  <!-- Регион + категория -->
<Person PCT_AFUNCT="JDG" PCT_COANAM="Москва, 1К"/>
```

---

## 10. КРИТИЧНО: Школы/Клубы — Причины перезаписи данных

### 10.1 Три разных источника клуба

В XML данные о клубе хранятся в **ТРЁХ РАЗНЫХ МЕСТАХ**, и они могут отличаться!

| Уровень | Атрибут/Элемент | Описание | Пример |
|---------|-----------------|----------|--------|
| `<Participant>` | `PAR_CLBID` | ID клуба участия | `PAR_CLBID="205"` |
| `<Person_Couple_Team>` | `PCT_CLBID` | ID клуба спортсмена/пары | `PCT_CLBID="205"` |
| `<Person_Couple_Team>` | `<Club>` | Вложенный элемент с данными | `<Club PCT_ID="1" .../>` |

### 10.2 Проблема: Клуб участия ≠ Клуб спортсмена

**Пример из реальных данных (танцевальная пара):**

```xml
<Participant PAR_ID="131" PAR_CLBID="205">              <!-- Клуб УЧАСТИЯ = 205 -->
  <Person_Couple_Team PCT_ID="190" PCT_CLBID="205">     <!-- Клуб ПАРЫ = 205 -->
    <Team_Members>
      <Person PCT_ID="188" PCT_CLBID="3">              <!-- Клуб ПАРТНЁРШИ = 3 (!) -->
        <Club/>                                         <!-- ПУСТОЙ элемент! -->
      </Person>
      <Person PCT_ID="189">                            <!-- У ПАРТНЁРА НЕТ PCT_CLBID! -->
      </Person>
    </Team_Members>
  </Person_Couple_Team>
</Participant>
```

**Что здесь происходит:**
- Пара выступает за клуб 205 (`PAR_CLBID`)
- Партнёрша записана в клуб 3 (`PCT_CLBID` в Person)
- Партнёр **НЕ ИМЕЕТ** клуба!
- Элемент `<Club/>` пустой — нет данных!

### 10.3 Проблема: Пустой элемент `<Club/>`

**КРИТИЧНО:** В парах/танцах элемент `<Club>` внутри `<Person>` часто **ПУСТОЙ**!

```xml
<!-- ОДИНОЧНИК — Club заполнен -->
<Person_Couple_Team PCT_ID="2" PCT_CLBID="1">
  <Club PCT_ID="1" PCT_CNAME="ООО Триумф" PCT_EXTDT="000000000000001" .../>
</Person_Couple_Team>

<!-- ПАРА — Club пустой! -->
<Person PCT_ID="188" PCT_CLBID="3">
  <Club/>  <!-- НЕТ ДАННЫХ! -->
</Person>
```

**Последствия:** Если парсер извлекает название клуба из вложенного `<Club>`, для пар получит пустую строку!

### 10.4 ГЛАВНАЯ ПРОБЛЕМА: Перезапись клуба у одиночников

**Сценарий:** Парсите несколько XML файлов или один файл с разными сегментами.

**ТИПИЧНАЯ ОШИБКА — перезапись без проверки:**

```python
# НЕПРАВИЛЬНО!
athletes = {}
for participant in all_participants:
    pct = participant.find('Person_Couple_Team')
    athlete_id = pct.get('PCT_ID')
    club_elem = pct.find('Club')
    
    # ПЕРЕЗАПИСЫВАЕМ каждый раз!
    athletes[athlete_id] = {
        'name': pct.get('PCT_CNAME'),
        'club_name': club_elem.get('PCT_CNAME', '') if club_elem else ''
    }
```

**Что происходит:**
1. В первом сегменте: спортсмен ID=2 с клубом "ООО Триумф"
2. Во втором сегменте: тот же спортсмен ID=2, но с пустым `<Club/>`
3. **РЕЗУЛЬТАТ:** Клуб перезаписан пустой строкой!

**ПРАВИЛЬНЫЙ подход — МЕРЖИТЬ данные:**

```python
def merge_athlete_data(existing, new_data):
    """Мержит данные спортсмена, не перезаписывая полезные данные пустыми"""
    if existing is None:
        return new_data
    
    result = existing.copy()
    for key, new_value in new_data.items():
        old_value = result.get(key)
        
        # НЕ перезаписываем если новое значение пустое, а старое — нет
        if new_value and (not old_value or len(str(new_value)) > len(str(old_value))):
            result[key] = new_value
    
    return result
```

### 10.5 Проблема: Перезапись справочника клубов

**ТИПИЧНАЯ ОШИБКА в парсере:**

```python
# НЕПРАВИЛЬНО - перезаписывает данные!
clubs = {}
for participant in all_participants:
    club_elem = participant.find('.//Club')
    if club_elem is not None:
        club_id = club_elem.get('PCT_ID')
        if club_id:
            clubs[club_id] = {
                'id': club_id,
                'name': club_elem.get('PCT_CNAME', ''),  # Может быть пустым!
            }
```

**Что происходит:**
1. Парсим одиночницу с клубом 3 → `clubs["3"] = {name: "ГБУ ДО..."}`
2. Парсим пару, у партнёрши `PCT_CLBID="3"` но `<Club/>` пустой
3. Перезаписываем → `clubs["3"] = {name: ""}` ← **ДАННЫЕ ПОТЕРЯНЫ!**

### 10.6 Партнёр без клуба — ЭТО НОРМАЛЬНО!

В парах/танцах у **ПАРТНЁРА** (второй Person) часто:
- Отсутствует атрибут `PCT_CLBID`
- Нет вложенного `<Club>`

**Это НЕ ошибка!** Если у партнёра нет клуба — значит он **ТАКОЙ ЖЕ как у партнёрши**. Данные не дублируются намеренно.

**Правило:** Если `PCT_CLBID` отсутствует у партнёра → брать клуб партнёрши.

### 10.7 ПРАВИЛЬНЫЙ алгоритм работы с клубами

```python
class ClubRegistry:
    """Справочник клубов с защитой от перезаписи"""
    
    def __init__(self):
        self.clubs = {}  # id -> {id, name, external_id, ...}
    
    def register_club(self, club_elem):
        """Регистрирует клуб ТОЛЬКО если есть данные"""
        if club_elem is None:
            return None
        
        club_id = club_elem.get('PCT_ID')
        if not club_id:
            return None
        
        club_name = club_elem.get('PCT_CNAME', '').strip()
        
        # НЕ перезаписываем если новые данные пустые!
        if club_id in self.clubs:
            if not club_name:  # Новые данные пустые
                return self.clubs[club_id]  # Возвращаем старые
        
        # Регистрируем только если есть название
        if club_name:
            self.clubs[club_id] = {
                'id': club_id,
                'name': club_name,
                'external_id': club_elem.get('PCT_EXTDT', ''),
            }
        
        return self.clubs.get(club_id)
    
    def get_club_name(self, club_id):
        """Получает название клуба по ID"""
        if club_id and club_id in self.clubs:
            return self.clubs[club_id].get('name', '')
        return ''


def extract_athlete_club(person_elem, club_registry):
    """Правильное извлечение клуба спортсмена"""
    
    # 1. Пробуем вложенный <Club>
    club_elem = person_elem.find('Club')
    if club_elem is not None:
        # Проверяем что не пустой
        if club_elem.get('PCT_ID'):
            club_registry.register_club(club_elem)
    
    # 2. Берём ID из атрибута PCT_CLBID
    club_id = person_elem.get('PCT_CLBID', '')
    
    # 3. Получаем название из справочника
    club_name = club_registry.get_club_name(club_id)
    
    return {
        'club_id': club_id,
        'club_name': club_name,
    }
```

### 10.8 Приоритеты получения клуба для разных типов

**Для одиночников:**
1. `PCT_CLBID` из `<Person_Couple_Team>`
2. `<Club>` внутри `<Person_Couple_Team>` — обычно заполнен

**Для партнёров в парах/танцах:**
1. `PCT_CLBID` из `<Person>` в `<Team_Members>` — может отсутствовать!
2. `<Club>` внутри `<Person>` — обычно **ПУСТОЙ**!
3. **Fallback:** `PAR_CLBID` из `<Participant>` — клуб пары

### 10.9 Рекомендации

| Что делать | Почему |
|------------|--------|
| Создать глобальный справочник клубов | Данные о клубах дублируются, лучше собрать один раз |
| НЕ перезаписывать если данные пустые | `<Club/>` у пар затрёт нормальные данные |
| Сначала парсить одиночников | У них полные данные клубов |
| Для пар использовать `PAR_CLBID` | Это клуб выступления, он всегда заполнен |
| Хранить `club_id` отдельно от `club_name` | Название можно получить из справочника |

### 10.10 Проверочный список для клубов

- [ ] Справочник клубов заполняется из одиночников (у них полные данные)
- [ ] При парсинге пар НЕ перезаписывать клубы пустыми значениями
- [ ] Проверять наличие `PCT_CLBID` — у партнёров может отсутствовать
- [ ] Проверять что `<Club>` не пустой перед извлечением
- [ ] Для участия пары использовать `PAR_CLBID` как fallback
- [ ] Хранить связь: `athlete_id` → `club_id` → справочник клубов

---

## 11. Дедупликация и идентификация спортсменов

### 11.1 Проблема: Разные ID в разных файлах

**КРИТИЧНО:** `PCT_ID` — это ID **внутри одного соревнования**, а не глобальный!

```xml
<!-- Файл competition1.xml -->
<Person_Couple_Team PCT_ID="2" PCT_EXTDT="000000001415631" PCT_CNAME="Варвара БОГОМОЛОВА"/>

<!-- Файл competition2.xml — тот же спортсмен, другой ID! -->
<Person_Couple_Team PCT_ID="15" PCT_EXTDT="000000001415631" PCT_CNAME="Варвара БОГОМОЛОВА"/>
```

### 11.2 Ключи для дедупликации

**По приоритету:**

| Ключ | Надёжность | Пример | Описание |
|------|------------|--------|----------|
| `PCT_EXTDT` | **Высокая** | `000000001415631` | Внешний ID из базы данных |
| `PCT_CNAME` + `PCT_BDAY` | Средняя | `"Варвара БОГОМОЛОВА"` + `"20150123"` | Имя + дата рождения |
| `PCT_GNAME` + `PCT_FNAME` + `PCT_BDAY` | Средняя | Отдельные поля | Более устойчиво к формату |

### 11.3 Формат PCT_EXTDT

```
000000001415631
│         │
│         └── Уникальный номер спортсмена
└────────────── Ведущие нули (padding)
```

**ВАЖНО:** `PCT_EXTDT` может отсутствовать! Всегда проверяйте наличие.

### 11.4 Алгоритм дедупликации

```python
def get_athlete_key(person_elem):
    """Генерирует уникальный ключ для спортсмена"""
    
    # Приоритет 1: PCT_EXTDT
    ext_id = person_elem.get('PCT_EXTDT', '').strip()
    if ext_id and ext_id != '0' * len(ext_id):  # Не все нули
        return f"ext:{ext_id}"
    
    # Приоритет 2: Имя + Фамилия + ДР
    gname = normalize_string(person_elem.get('PCT_GNAME', ''))
    fname = normalize_string(person_elem.get('PCT_FNAME', ''))
    bday = person_elem.get('PCT_BDAY', '')
    
    if gname and fname and bday:
        return f"name:{gname.lower()}:{fname.lower()}:{bday}"
    
    # Fallback: PCT_ID (только в пределах файла!)
    return f"local:{person_elem.get('PCT_ID', '')}"
```

### 11.5 Мерж данных при повторном появлении

При парсинге нескольких файлов спортсмен может встретиться многократно. **НЕ ПЕРЕЗАПИСЫВАТЬ!**

```python
def update_athlete_record(existing, new_data):
    """Обновляет запись, сохраняя непустые значения"""
    
    if existing is None:
        return new_data.copy()
    
    updated = existing.copy()
    
    for field in ['club_id', 'club_name', 'coach', 'rank']:
        new_val = new_data.get(field)
        old_val = updated.get(field)
        
        # Обновляем только если:
        # 1. Старое значение пустое
        # 2. Новое значение более полное (длиннее)
        if new_val:
            if not old_val:
                updated[field] = new_val
            elif len(str(new_val)) > len(str(old_val)):
                updated[field] = new_val
    
    # Добавляем участие в список
    if 'participations' not in updated:
        updated['participations'] = []
    updated['participations'].append(new_data.get('participation'))
    
    return updated
```

---

## 12. Сводная таблица атрибутов по типам

### Одиночники (PCT_TYPE="PER")

| Что извлекать | Откуда |
|---------------|--------|
| ID спортсмена | `PCT_ID` |
| Имя | `PCT_GNAME` |
| Фамилия | `PCT_FNAME` |
| Дата рождения | `PCT_BDAY` |
| Пол | `CAT_GENDER` категории |
| Клуб ID | `PCT_CLBID` |
| Клуб название | вложенный `<Club PCT_CNAME="..."/>` |
| Разряд | `PCT_COMENT` |
| Тренеры | `PCT_COANAM` |

### Пары и Танцы (PCT_TYPE="COU")

| Что извлекать | Откуда |
|---------------|--------|
| ID пары | `PCT_ID` в Person_Couple_Team |
| Клуб пары | `PAR_CLBID` в Participant |
| **Партнёрша:** | |
| - ID | первый Person `PCT_ID` или `PCT_PCTID` |
| - Имя | первый Person `PCT_GNAME` или `PCT_GNAME` |
| - Фамилия | первый Person `PCT_FNAME` или `PCT_FNAME` |
| - Дата рождения | первый Person `PCT_BDAY` или `PCT_BDAY` |
| - Клуб | первый Person `PCT_CLBID` (может быть!) |
| **Партнёр:** | |
| - ID | второй Person `PCT_ID` или `PCT_PPCTID` |
| - Имя | второй Person `PCT_GNAME` или `PCT_PGNAME` |
| - Фамилия | второй Person `PCT_FNAME` или `PCT_PFNAMC` |
| - Дата рождения | второй Person `PCT_BDAY` или `PCT_PBDAY` |
| - Клуб | второй Person `PCT_CLBID` (обычно НЕТ!) |
| Тренеры | `PCT_COANAM` |

---

## 13. Чек-лист для разработки парсера

### Базовый парсинг
- [ ] Определение типа категории по `CAT_GENDER` + `CAT_TYPE`
- [ ] Разделение одиночников (`PCT_TYPE="PER"`) и пар (`PCT_TYPE="COU"`)
- [ ] Извлечение данных из `<Team_Members>` для пар
- [ ] Резервное извлечение из атрибутов PCT_P* если Team_Members отсутствует
- [ ] Не использовать `PCT_GENDER` для пола в парах (часто некорректен)
- [ ] Конвертация дат из YYYYMMDD
- [ ] Деление очков на 100
- [ ] Извлечение разряда из `PCT_COMENT`

### Клубы/Школы (КРИТИЧНО!)
- [ ] Создать глобальный справочник клубов `{club_id: club_data}`
- [ ] Сначала парсить одиночников — у них полные данные клубов
- [ ] НЕ перезаписывать клуб если новые данные пустые (`<Club/>`)
- [ ] Проверять `PCT_CLBID` у партнёров — может отсутствовать!
- [ ] Использовать `PAR_CLBID` как fallback для пар
- [ ] Хранить только `club_id` у спортсмена, название брать из справочника

### Объединение данных
- [ ] Объединение данных из нескольких XML файлов
- [ ] Дедупликация спортсменов по `PCT_ID` или `PCT_EXTDT`
- [ ] Отслеживание участий одного спортсмена в разных соревнованиях
- [ ] Мерж данных при повторном появлении спортсмена (не перезаписывать!)

---

## 14. Краткая памятка: Источники данных о клубе

```
┌─────────────────────────────────────────────────────────────────┐
│                        ОДИНОЧНИКИ                               │
├─────────────────────────────────────────────────────────────────┤
│  <Participant PAR_CLBID="1">                                    │
│    <Person_Couple_Team PCT_CLBID="1">      ← ID клуба           │
│      <Club PCT_ID="1" PCT_CNAME="ООО.."/> ← Полные данные ✓    │
│    </Person_Couple_Team>                                        │
│  </Participant>                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     ПАРЫ / ТАНЦЫ                                │
├─────────────────────────────────────────────────────────────────┤
│  <Participant PAR_CLBID="205">              ← Клуб ПАРЫ ✓      │
│    <Person_Couple_Team PCT_CLBID="205">     ← Клуб пары        │
│      <Team_Members>                                             │
│        <Person PCT_CLBID="3">               ← Клуб партнёрши?  │
│          <Club/>                            ← ПУСТОЙ! ✗        │
│        </Person>                                                │
│        <Person>                             ← НЕТ PCT_CLBID! ✗ │
│        </Person>                                                │
│      </Team_Members>                                            │
│    </Person_Couple_Team>                                        │
│  </Participant>                                                 │
└─────────────────────────────────────────────────────────────────┘

ПРАВИЛО: Для пар брать PAR_CLBID, для одиночников — PCT_CLBID + <Club>
```

---

*Документ версия 2.0 | Обновлён: секции о клубах/школах, подводные камни (пробелы, tabs, статусы, судьи), дедупликация спортсменов*
