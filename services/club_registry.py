"""Club registry with overwrite protection."""

import logging
import re
from difflib import SequenceMatcher
from models import db, Club, Athlete
from utils.normalizers import normalize_string, fix_latin_to_cyrillic

logger = logging.getLogger(__name__)

# Цифровые маркеры в названии (№1 / №2, СШОР 10 / СШОР 11) — разные школы, даже при
# SequenceMatcher ≥ 0.85. Без этого импорт молча склеивает клубы и переносит спортсменов.
_DIGIT_TOKEN_RE = re.compile(r'\d+')

# Типы спортивных школ как целые слова (длинные формы первыми).
# «СДЮСШОР» и «СДЮШОР» — варианты одной аббревиатуры; «СШОР» vs «СДЮШОР» — разные типы.
_ORG_TYPE_RE = re.compile(
    r'(?<![а-яё])(сдюсшор|сдюшор|сдющи|сшор|уор|дюсш|сш)(?![а-яё])',
    re.IGNORECASE,
)
_ORG_TYPE_ALIASES = {
    'сдюсшор': 'сдюшор',
}

# Кавычки/ёлочки из XML часто ломают prefix-remainder guard («Москвич» vs «Москвичка»).
_QUOTE_CHARS_RE = re.compile(r'[«»""„‟‹›\'`]+')

# Юридические/родовые слова — не отличительный бренд школы.
_STOP_TOKENS = frozenset({
    'гбу', 'мбу', 'маоу', 'мбоу', 'гаоу', 'гбоу', 'фгбу',
    'ооо', 'ано', 'ип', 'до', 'фсо', 'ффкк', 'ск', 'кфк',
    'клуб', 'школа', 'по', 'им', 'имени', 'г', 'гор', 'город',
    'мо', 'области', 'областной',
})

_TOKEN_RE = re.compile(r'[а-яёa-z0-9]+', re.IGNORECASE)


class ClubRegistry:
    """Cache/registry for clubs to prevent overwrite by empty values."""

    def __init__(self):
        self._cache_by_name = {}

    def _should_update(self, old_value, new_value):
        if not new_value:
            return False
        if not old_value:
            return True
        return len(str(new_value)) > len(str(old_value))

    @staticmethod
    def _normalize_for_similarity(name: str) -> str:
        """Нормализация имени для сравнения: латиница→кириллица, кавычки, ё→е."""
        if not name:
            return ''
        text = normalize_string(fix_latin_to_cyrillic(name)).lower()
        text = _QUOTE_CHARS_RE.sub(' ', text)
        text = text.replace('ё', 'е')
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    @staticmethod
    def _digit_tokens(normalized_name: str) -> tuple:
        """Кортеж числовых токенов в порядке появления (после нормализации имени)."""
        if not normalized_name:
            return ()
        return tuple(_DIGIT_TOKEN_RE.findall(normalized_name))

    @staticmethod
    def _org_type_tokens(normalized_name: str) -> frozenset:
        """Множество типов школы в названии (сш / сшор / сдюшор / уор …)."""
        if not normalized_name:
            return frozenset()
        tokens = []
        for raw in _ORG_TYPE_RE.findall(normalized_name.lower()):
            tokens.append(_ORG_TYPE_ALIASES.get(raw, raw))
        return frozenset(tokens)

    @classmethod
    def _core_name_tokens(cls, normalized_name: str) -> frozenset:
        """Отличительные токены бренда (без юр.формы и типа школы)."""
        if not normalized_name:
            return frozenset()
        org_types = cls._org_type_tokens(normalized_name)
        core = set()
        for raw in _TOKEN_RE.findall(normalized_name.lower()):
            token = raw.replace('ё', 'е')
            if token.isdigit():
                continue
            if token in _STOP_TOKENS:
                continue
            if token in org_types or _ORG_TYPE_ALIASES.get(token, token) in org_types:
                continue
            if token in _ORG_TYPE_ALIASES or token in {
                'сдюсшор', 'сдюшор', 'сдющи', 'сшор', 'уор', 'дюсш', 'сш',
            }:
                continue
            core.add(token)
        return frozenset(core)

    def _calculate_similarity(self, name1, name2):
        """Вычисляет схожесть двух названий клубов (0.0 - 1.0)
        
        Учитывает:
        - Точное совпадение (после нормализации)
        - Различие цифровых маркеров (№1 vs №2 → не объединять)
        - Различие типа школы (СШОР vs СДЮШОР/СДЮСШОР → не объединять)
        - Различие брендовых токенов («Москвич» vs «Москвичка» → не объединять)
        - Вхождение одного названия в другое
        - Схожесть по SequenceMatcher
        """
        if not name1 or not name2:
            return 0.0
        
        # Нормализуем оба названия (кавычки снимаем — иначе prefix-guard не срабатывает)
        norm1 = self._normalize_for_similarity(name1)
        norm2 = self._normalize_for_similarity(name2)
        
        # Точное совпадение
        if norm1 == norm2:
            return 1.0

        # Разные номера в названии → разные клубы (СШОР №1 Москва / СШОР №2 Москва ≈ 0.93)
        if self._digit_tokens(norm1) != self._digit_tokens(norm2):
            return 0.0

        # Разный тип школы → разные организации (ГБУ ДО СШОР / ГБУ ДО СДЮСШОР ≈ 0.88)
        types1 = self._org_type_tokens(norm1)
        types2 = self._org_type_tokens(norm2)
        if types1 and types2 and types1 != types2:
            return 0.0

        # Разный бренд/имя школы → разные клубы
        # («Москвич»/«Москвичка» ≈ 0.93; «Айс»/«Аист» ≈ 0.86; «Звезда»/«Звездочка» ≈ 0.90)
        core1 = self._core_name_tokens(norm1)
        core2 = self._core_name_tokens(norm2)
        if core1 and core2 and core1 != core2:
            return 0.0
        
        # Проверка на вхождение одного названия в другое
        # Если короткое название содержится в длинном и составляет ≥90% длины, это очень похоже
        # Порог 90% предотвращает объединение "Академия спорта" и "Академия спорта Стрижи"
        if norm1 in norm2 or norm2 in norm1:
            shorter_name = norm1 if len(norm1) < len(norm2) else norm2
            longer_name = norm2 if len(norm1) < len(norm2) else norm1
            shorter = len(shorter_name)
            longer = len(longer_name)
            
            # Дополнительная проверка: если есть отличающиеся слова, это разные школы
            # Например: "ООО Академия спорта" vs "ООО Академия спорта Стрижи"
            # Остаток: "Стрижи" - это целое слово, значит разные школы
            if longer_name.startswith(shorter_name):
                remainder = longer_name[len(shorter_name):].strip()
                # Если остаток содержит хотя бы одно слово (не пустой и не только пробелы)
                if remainder and len(remainder.split()) >= 1:
                    # Это разные школы - есть дополнительные слова
                    return 0.70  # Низкая схожесть - не объединять
            
            if longer > 0 and shorter / longer >= 0.90 and shorter >= 10:
                return 0.95  # Очень высокая схожесть
        
        # Используем SequenceMatcher для вычисления общей схожести
        similarity_ratio = SequenceMatcher(None, norm1, norm2).ratio()
        return similarity_ratio

    def register(self, club_data):
        """Register or update club from parsed data."""
        if not club_data:
            return None

        # Применяем fix_latin_to_cyrillic для исправления визуально похожих символов
        raw_name = club_data.get('name', '')
        name = normalize_string(fix_latin_to_cyrillic(raw_name))
        short_name = normalize_string(fix_latin_to_cyrillic(club_data.get('short_name', '')))
        country = normalize_string(club_data.get('country', ''))
        city = normalize_string(club_data.get('city', ''))

        if not name:
            return None

        # Проверяем кеш по имени
        if name in self._cache_by_name:
            club = self._cache_by_name[name]
        else:
            club = None

        # Ищем по нормализованному имени - сравниваем нормализованные версии
        # Это предотвращает создание дубликатов из-за различий в пробелах/табуляциях
        # Также применяем fix_latin_to_cyrillic для существующих клубов
        # И используем fuzzy matching для похожих названий
        if not club:
            all_clubs = Club.query.all()
            best_match = None
            best_similarity = 0.85  # Порог схожести для автоматического объединения (85%)
            
            for existing_club in all_clubs:
                if not existing_club.name:
                    continue
                
                # Сначала проверяем точное совпадение
                normalized_existing = normalize_string(fix_latin_to_cyrillic(existing_club.name))
                if normalized_existing == name:
                    club = existing_club
                    break
                
                # Если точного совпадения нет, проверяем схожесть
                similarity = self._calculate_similarity(existing_club.name, raw_name)
                if similarity >= best_similarity:
                    if not best_match or similarity > best_match[1]:
                        best_match = (existing_club, similarity)
            
            # Если нашли достаточно похожий клуб, используем его
            if not club and best_match:
                club = best_match[0]
                similarity_score = best_match[1]
                logger.info(
                    f"Автоматическое объединение похожих клубов: "
                    f"'{raw_name}' объединен с '{club.name}' "
                    f"(схожесть: {similarity_score:.1%})"
                )

        if not club:
            club = Club(
                name=name,
                short_name=short_name or None,
                country=country or None,
                city=city or None,
            )
            db.session.add(club)
        else:
            if self._should_update(club.name, name):
                club.name = name
            if self._should_update(club.short_name, short_name):
                club.short_name = short_name
            if self._should_update(club.country, country):
                club.country = country
            if self._should_update(club.city, city):
                club.city = city

        self._cache_by_name[name] = club
        return club
    
    def merge_all_duplicates(self):
        """Объединяет все дубликаты клубов в базе данных (вызывается после регистрации всех клубов)"""
        all_clubs = Club.query.all()
        processed_clubs = set()
        similarity_threshold = 0.85  # Порог схожести 85%
        merged_count = 0
        
        for i, club1 in enumerate(all_clubs):
            if not club1.name or club1.id in processed_clubs:
                continue
            
            similar_clubs = [club1]
            
            for club2 in all_clubs[i+1:]:
                if not club2.name or club2.id in processed_clubs:
                    continue
                
                similarity = self._calculate_similarity(club1.name, club2.name)
                if similarity >= similarity_threshold:
                    similar_clubs.append(club2)
                    processed_clubs.add(club2.id)
            
            # Если нашли похожие клубы, объединяем их
            if len(similar_clubs) > 1:
                keep_club, remove_clubs = self._merge_club_group(similar_clubs)
                
                for remove_club in remove_clubs:
                    try:
                        # Подсчитываем спортсменов
                        remove_athletes = Athlete.query.filter_by(club_id=remove_club.id).count()
                        
                        # Переносим спортсменов
                        Athlete.query.filter_by(club_id=remove_club.id).update({
                            'club_id': keep_club.id
                        })
                        
                        # Обновляем данные клуба, если нужно
                        if not keep_club.country and remove_club.country:
                            keep_club.country = remove_club.country
                        if not keep_club.city and remove_club.city:
                            keep_club.city = remove_club.city
                        if not keep_club.short_name and remove_club.short_name:
                            keep_club.short_name = remove_club.short_name
                        
                        # Обновляем кеш, если удаляемый клуб был в кеше
                        for cached_name, cached_club in list(self._cache_by_name.items()):
                            if cached_club.id == remove_club.id:
                                self._cache_by_name[cached_name] = keep_club
                        
                        # Удаляем дубликат
                        db.session.delete(remove_club)
                        db.session.flush()
                        
                        merged_count += 1
                        
                        logger.info(
                            f"Автоматическое объединение дубликатов клубов: "
                            f"'{remove_club.name}' объединен с '{keep_club.name}' "
                            f"(перенесено спортсменов: {remove_athletes})"
                        )
                        
                    except Exception as e:
                        logger.error(f"Ошибка при объединении клубов '{remove_club.name}' и '{keep_club.name}': {e}")
                        db.session.rollback()
                        continue
                
                processed_clubs.add(club1.id)
        
        if merged_count > 0:
            logger.info(f"Автоматически объединено {merged_count} дубликатов клубов")
        
        return merged_count
    
    def _merge_club_group(self, clubs):
        """Объединяет группу клубов в один - выбирает клуб для сохранения"""
        if not clubs or len(clubs) < 2:
            return None, []
        
        # Выбираем клуб для сохранения: тот, у которого больше спортсменов
        # Если одинаково - выбираем тот, у которого более длинное название
        clubs_with_counts = []
        for club in clubs:
            athlete_count = Athlete.query.filter_by(club_id=club.id).count()
            clubs_with_counts.append((club, athlete_count))
        
        # Сортируем: больше спортсменов -> более длинное название
        clubs_with_counts.sort(
            key=lambda x: (
                -x[1],  # Больше спортсменов
                -len(x[0].name or '')  # Более длинное название
            )
        )
        
        keep_club = clubs_with_counts[0][0]
        remove_clubs = [club for club, _ in clubs_with_counts[1:]]
        
        return keep_club, remove_clubs
