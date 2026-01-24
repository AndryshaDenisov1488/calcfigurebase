"""String normalization utilities."""

import re
import html


def normalize_string(value):
    """Normalize string: trim, replace tabs, collapse whitespace."""
    if value is None:
        return ''
    if not isinstance(value, str):
        value = str(value)
    value = html.unescape(value)
    value = value.replace('\t', ' ')
    value = re.sub(r'\s+', ' ', value)
    return value.strip()


def remove_duplication(text):
    """Удаляет дублирование слов в тексте (например, 'Софья Софья' -> 'Софья')."""
    if not text or not isinstance(text, str):
        return text
    words = text.split()
    if len(words) < 2:
        return text
    # Удаляем последовательные дубликаты
    result = []
    prev_word = None
    for word in words:
        if word != prev_word:
            result.append(word)
            prev_word = word
    return ' '.join(result)


def fix_latin_to_cyrillic(text):
    """
    Заменяет латинские буквы, которые выглядят как русские, на русские.
    Это нужно для правильного распознавания разрядов, когда в XML используются
    латинские буквы вместо русских (например, '3 Юнoшеский' вместо '3 Юношеский').
    
    Заменяет:
    - o -> о (латинская o на русскую о)
    - e -> е (латинская e на русскую е)
    - c -> с (латинская c на русскую с)
    - p -> р (латинская p на русскую р)
    - a -> а (латинская a на русскую а)
    - y -> у (латинская y на русскую у)
    - x -> х (латинская x на русскую х)
    - O -> О (латинская O на русскую О)
    - E -> Е (латинская E на русскую Е)
    - C -> С (латинская C на русскую С)
    - P -> Р (латинская P на русскую Р)
    - A -> А (латинская A на русскую А)
    - Y -> У (латинская Y на русскую У)
    - X -> Х (латинская X на русскую Х)
    """
    if not text or not isinstance(text, str):
        return text
    
    # Маппинг латинских букв на русские (визуально похожие)
    latin_to_cyrillic = {
        'o': 'о',  # латинская o -> русская о
        'e': 'е',  # латинская e -> русская е
        'c': 'с',  # латинская c -> русская с
        'p': 'р',  # латинская p -> русская р
        'a': 'а',  # латинская a -> русская а
        'y': 'у',  # латинская y -> русская у
        'x': 'х',  # латинская x -> русская х
        'O': 'О',  # латинская O -> русская О
        'E': 'Е',  # латинская E -> русская Е
        'C': 'С',  # латинская C -> русская С
        'P': 'Р',  # латинская P -> русская Р
        'A': 'А',  # латинская A -> русская А
        'Y': 'У',  # латинская Y -> русская У
        'X': 'Х',  # латинская X -> русская Х
    }
    
    result = []
    for char in text:
        if char in latin_to_cyrillic:
            result.append(latin_to_cyrillic[char])
        else:
            result.append(char)
    
    return ''.join(result)
