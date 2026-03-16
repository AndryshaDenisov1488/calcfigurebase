#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка списка ФИО против БД спортсменов с учётом опечаток.

Запуск (локально или на сервере, в активированном виртуальном окружении):

    python scripts/check_names_against_db.py
"""

import os
import sys

# Добавляем корень проекта в sys.path (как в других скриптах)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from app import app, db
from models import Athlete
from utils.normalizers import normalize_string, fix_latin_to_cyrillic, remove_duplication  # noqa: F401


RAW_NAMES = """
МЕЖЕНКОВА Вероника Александровна
ЛАБУТКИНА София Алексеевна
ДИДЕНКО Софья Константиновна
БАГДАСАРЯН Данела Викторовна
КОНОНОВА Элиза Максимовна
МАЗИТОВ Василь Искандерович
ЗОЛОНЕНКО Есения Андреевна
САНАРОВА Софья Евгеньевна
ПЕЛЬМЕНЕВА Алина Витальевна
БОРОДИНА Мирослава Богдановна
ПЕНЦЕНШТАДЛЕР Эдгар Сергеевна
КОНСТАНТИНОВА Кристина Андреевна
ЧУЧКАЛОВ Степан Сергеевич
ЛОНГУС Николь Сергеевна
ЯСЬКИНА Алиса Алексеевна
НАУМКИН Феликс Дмитриевич
ЛОРЕНСО Лаура Орландовна МАРТИНЕС
МЕРЗЛЯКОВА Анна Сергеевна
КОВАЛЕВИЧ Алексей Алексеевич ЭСПИНОСА
ЛЯНЕНКО Полина Евгеньевна
КРАХОТКО Яков Владимирович
ШУБИНА Екатерина Алексеевна
КРИВКО Евгения Андреевна
ЛЕБЕДЕВА Василиса БУРОН
ЛЕБЕДЕВА Василиса Кристиан Екатерина БУРОН
ШУМКОВА Софья Ивановна
ПРИЧАК Гордей Витальевич
ЧИЖОВА Ульяна Дмитриевна
ШЕСТАКОВА Василиса Юрьевна
СМЕЦКАЯ Мария Сергеевна
ЦЫПИШЕВА Екатерина Алексеевна
НАВАРРО Ангелина Энриевна МАЧУКА
ХРЕБТОВ Дмитрий Владимирович
МОЛЧАНОВА Александра Сергеевна
АНДРЕЕВ Даниил Константинович
ГВОЗДКОВ Егор Алексеевич
ЖЕГУЛИНА Ксения Андреевна
МАКСИМОВА Таисия Константиновна
МЕЛЬНИКОВ Владимир Жанович
КАПИТОНОВ Иван Дмитриевич
БЕЛКИНА Агния Ивановна
ЕРШОВ Кирилл Артёмович
ОСИПОВА Есения Валерьевна
ЯРУСОВА Ксения Дмитриевна
КРУПНОВА Елизавета Алексеевна
ЗАДОРОЖНЮК Матвей Артёмович
ПЕРЕЖИГИНА Александра Александровна
ПАВЛЕНКО Валерия Сергеевна
ДУБИНЕЦКАЯ Мария Вадимовна
АЛЕКСЕЕВА Алёна Александровна
КРАСНОПЕРОВА Елизавета Владимировна
СЕМЁНОВА Нина Александровна
ВОРОБЬЕВА Варвара Антоновна
МУРАТКАЛИЕВА Дарья Сергеевна
МУРАТКАЛИЕВА Дарья Сергеевна
БОГАТЫРЕНКО Дарья Олеговна
МАКАРОВА Каролина Алексеевна
КОЧКАРЕВА Диана Романовна
УТКИНА Полина Сергеевна
СЫЧЕВА Юлия Леонидовна
БУДАРИНА Наталия Вадимовна
ГОМОЗОВА Елизавета Андреевна
ГРОМОВА Кира Сергеевна
ВИНОГРАДОВА Таисия Сергеевна
ПРИХОДЬКО Виктория Михайловна
СИМОНОВА Полина Ильинична
БАРБАШЕВА Алиса Павловна
ЛИТВИНОВА Анна Евгеньевна
СЕМИНА Алиса Олеговна
ФЕДОТЕНКОВА Анна Федоровну
ТИНИН Лев Алексеевич
СНЯТКОВА Ульяна Андреевна
ГАЧИНА Софья Николаевна
ТРОШИНА Станислава Алексеевна
ДУРРУТИ Эмили РОМАГОСА
ВОЕВОДИНА Александра Леонидовна
НИКОЛАЕВ Никита Николаевич
НИКИФОРОВА Алиса Олеговна
МЕЛЬНИЧУК Георгий Денисович
РОЗАНОВА Мария Владимировна
МУКСУНОВА Эльвира Сергеевна
КАПУСТИНА Агния Алексеевна
ГОЛУБЕВА Анастасия Владимировна
ЗАЙЦЕВА Виктория Олеговна
ИВАНОВА Василиса Денисовна
БАБУШКИНА Майя Константиновна
КАЛИНИНА Анна Николаевна
МОЛОДЦОВА Арианна Руслановна
ОГАНИСЯН Кира Горовна
КАЗАКОВА Анна Андреевна
ДЕНИСКО Ульяна Дмитриевна
ПРОСВЕТОВА Маргарита Максимовна
АЛИШИХОВА Элени Багауддиновна
ДОВГАНЬ Дарья Андреевна
СЕДУН Алиса Алексеевна
МАЛЬКОВА Варвара Олеговна
""".strip()


def norm_component(s: str) -> str:
    """Нормализация одной части ФИО (общая)."""
    if not s:
        return ""
    s = fix_latin_to_cyrillic(s)
    s = normalize_string(s)
    s = s.replace("ё", "е").replace("Ё", "Е")
    return s.lower()


def normalize_first_name(name: str) -> str:
    """Нормализация имён с учётом Софья/София и похожих вариантов."""
    n = norm_component(name)
    # Софья / София → софя (убираем среднюю гласную)
    for suffix in ("ия", "ья"):
        if n.endswith(suffix):
            n = n[:-len(suffix)] + "я"
    return n


def patronymic_stem(pat: str) -> str:
    """Основа отчества без половых окончаний: Сергеевич/Сергеевна → сергеев."""
    p = norm_component(pat)
    if not p:
        return ""
    endings = (
        "ович",
        "евич",
        "ич",
        "овна",
        "евна",
        "ична",
        "инична",
        "овны",
        "евны",
        "ичны",
    )
    for e in endings:
        if p.endswith(e):
            return p[: -len(e)]
    return p


def parse_full_name(line: str):
    """
    Грубый парсер ФИО:
    первая часть — фамилия, последняя — отчество (если >=3 слов),
    всё между ними — имя (может быть составным).
    """
    raw = line.strip()
    if not raw:
        return None

    parts = raw.split()
    if len(parts) == 1:
        return {"raw": raw, "last": parts[0], "first": "", "pat": ""}

    if len(parts) == 2:
        last, first = parts
        return {"raw": raw, "last": last, "first": first, "pat": ""}

    last = parts[0]
    pat = parts[-1]
    first = " ".join(parts[1:-1])
    return {"raw": raw, "last": last, "first": first, "pat": pat}


def similarity_score(input_norm: str, db_norm: str) -> int:
    """
    Простая метрика похожести:
    полное совпадение → 2, общий префикс → 1, иначе 0.
    """
    if not input_norm or not db_norm:
        return 0
    if input_norm == db_norm:
        return 2
    if input_norm.startswith(db_norm) or db_norm.startswith(input_norm):
        return 1
    return 0


def check_one_name(parsed):
    raw = parsed["raw"]
    last_norm = norm_component(parsed["last"])
    first_norm = normalize_first_name(parsed["first"])
    pat_stem = patronymic_stem(parsed["pat"])

    if not last_norm:
        print(f"\n=== {raw} ===")
        print("  [!] Не удалось определить фамилию, пропуск")
        return

    print(f"\n=== {raw} ===")

    # Сначала ищем по исходной (ненормализованной) фамилии через ILIKE
    candidates = (
        db.session.query(Athlete)
        .filter(Athlete.last_name.isnot(None))
        .filter(Athlete.last_name.ilike(parsed["last"] + "%"))
        .all()
    )

    # Если ничего не нашли, делаем fallback по нормализованной фамилии
    if not candidates:
        all_athletes = db.session.query(Athlete).filter(Athlete.last_name.isnot(None)).all()
        candidates = [
            a for a in all_athletes if norm_component(a.last_name) == last_norm
        ]

    if not candidates:
        print("  Совпадений по фамилии не найдено.")
        return

    scored = []
    for a in candidates:
        db_first = a.first_name or ""
        db_last = a.last_name or ""
        db_pat = a.patronymic or ""

        db_first_norm = normalize_first_name(db_first)
        db_last_norm = norm_component(db_last)
        db_pat_stem = patronymic_stem(db_pat)

        # фамилия должна совпасть после нормализации
        if db_last_norm != last_norm:
            continue

        score = 0
        score += 2  # базовые баллы за совпадение фамилии
        score += similarity_score(first_norm, db_first_norm)
        score += similarity_score(pat_stem, db_pat_stem)

        scored.append((score, a, db_first, db_last, db_pat))

    if not scored:
        print("  Кандидаты по фамилии есть, но имя/отчество не совпали даже примерно.")
        return

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score = scored[0][0]

    # выводим только достаточно близкие совпадения
    for score, a, db_first, db_last, db_pat in scored:
        if score < max(2, best_score - 1):
            continue
        print(
            f"  score={score} → id={a.id}: "
            f"{db_last} {db_first} {db_pat or ''} "
            f"(gender={a.gender or '-'}, birth={a.birth_date or '-'})"
        )


def main():
    lines = [l for l in RAW_NAMES.splitlines() if l.strip()]
    parsed = [p for l in lines if (p := parse_full_name(l)) is not None]

    with app.app_context():
        for p in parsed:
            check_one_name(p)


if __name__ == "__main__":
    main()

