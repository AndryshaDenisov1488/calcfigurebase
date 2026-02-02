#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обновление ролей судей (role_code) в БД по правилу порядка в сегменте.
Проходит по JudgePanel в базе, без XML.

Правило: полевых судей может быть от 3 до 7 (и больше).
- Последний в сегменте (order_num == размер бригады) всегда = ОВД (DO).
- При 10 участниках: 7=TC, 8=TS, 9=ATS, 10=DO.

Обновляются только записи с role_code в ('JDG','J', None), остальные не трогаем.
Запуск из корня: python scripts/update_judge_roles_from_db.py [--dry-run]
"""

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app_factory import create_app
from extensions import db
from models import JudgePanel, Segment


# При 10 участниках в бригаде (стандарт ISU)
ORDER_TO_ROLE_10 = {
    7: 'TC',   # Технический контролер
    8: 'TS',   # Технический специалист
    9: 'ATS',  # Помощник технического специалиста
    10: 'DO',  # Оператор ввода данных
}


def role_for_order(order_num, total_in_segment):
    """Роль по порядковому номеру и размеру бригады.
    Последний в сегменте (3–7 или больше) = ОВД (DO). При 10 участниках: 7=TC, 8=TS, 9=ATS, 10=DO."""
    if order_num is None or total_in_segment is None:
        return None
    # Последний по счёту в сегменте всегда ОВД (при 3, 4, 5, 6, 7 полевых судьях и т.д.)
    if order_num == total_in_segment:
        return 'DO'
    # При 10 участниках — фиксированные роли для 7, 8, 9
    if total_in_segment >= 10 and order_num in ORDER_TO_ROLE_10:
        return ORDER_TO_ROLE_10[order_num]
    return None


def main():
    dry_run = '--dry-run' in sys.argv
    app = create_app()
    with app.app_context():
        # Все сегменты с их id
        segments = Segment.query.all()
        segment_ids = {s.id for s in segments}

        # По каждому сегменту: панели с order_num, считаем макс order_num = размер бригады
        from sqlalchemy import func
        panel_counts = (
            db.session.query(JudgePanel.segment_id, func.max(JudgePanel.order_num).label('max_order'))
            .filter(JudgePanel.segment_id.in_(segment_ids))
            .group_by(JudgePanel.segment_id)
        )
        segment_total = {row.segment_id: row.max_order for row in panel_counts}

        # Обновляем только панели с ролью JDG/J/None и подходящим order_num
        to_update = []
        panels = JudgePanel.query.filter(
            JudgePanel.segment_id.in_(segment_ids),
            db.or_(
                JudgePanel.role_code.in_(['JDG', 'J', '']),
                JudgePanel.role_code.is_(None),
            ),
        ).all()

        for p in panels:
            total = segment_total.get(p.segment_id)
            new_role = role_for_order(p.order_num, total)
            if new_role and (p.role_code or '') != new_role:
                to_update.append((p, new_role))

        print("=" * 60)
        print("ОБНОВЛЕНИЕ РОЛЕЙ СУДЕЙ В БД (по порядку в сегменте)")
        print("=" * 60)
        print(f"Сегментов в БД: {len(segment_ids)}")
        print(f"Панелей с ролью JDG/J/пусто: {len(panels)}")
        print(f"Будет обновлено записей: {len(to_update)}")
        if dry_run:
            print("\n[DRY-RUN] Изменения не сохраняются.")
            for p, new_role in to_update[:20]:
                print(f"  segment_id={p.segment_id} judge_id={p.judge_id} order_num={p.order_num} -> role_code={new_role}")
            if len(to_update) > 20:
                print(f"  ... и ещё {len(to_update) - 20}")
        else:
            for p, new_role in to_update:
                p.role_code = new_role
            db.session.commit()
            print("\nГотово. role_code обновлён.")
        print("=" * 60)


if __name__ == "__main__":
    main()
