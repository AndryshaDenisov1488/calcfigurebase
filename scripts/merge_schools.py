#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Объединение школ (клубов): перенос всех спортсменов из одной школы в другую.

Используйте, когда в базе одна и та же школа записана под разными названиями
(например «ЦСКА» и «ФАУ МО РФ ЦСКА») — объединяете в одну запись.

Запуск из корня проекта:
  python scripts/merge_schools.py list                    # список клубов с числом спортсменов
  python scripts/merge_schools.py list --search "ЦСКА"    # поиск по названию
  python scripts/merge_schools.py merge 1 7               # школа 7 → в школу 1 (оставляем 1)
  python scripts/merge_schools.py merge --into 1 --from 7 # то же
  python scripts/merge_schools.py merge 1 7 --yes        # без подтверждения
  python scripts/merge_schools.py merge 1 7 --no-delete    # не удалять пустую школу 7 после переноса
  python scripts/merge_schools.py merge 27 10 78 100 75 68  # все перечисленные школы → в 27
  python scripts/merge_schools.py delete 86                 # удалить пустую школу (0 спортсменов)
  python scripts/merge_schools.py show 86                   # проверить школу по БД (ID или --search)
  python scripts/merge_schools.py unassign 1595 --yes       # снять спортсмена с клуба (чтобы удалить пустую школу)
  python scripts/merge_schools.py delete-athlete 1595 --yes # удалить спортсмена из БД полностью
"""

import os
import shutil
import sys
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app_factory import create_app
from extensions import db
from models import Club, Athlete, CoachAssignment


def get_db_path(app):
    """Путь к файлу SQLite из конфига приложения."""
    uri = app.config.get('SQLALCHEMY_DATABASE_URI', '') or ''
    if uri.startswith('sqlite:///'):
        path = uri.replace('sqlite:///', '', 1)
        if not os.path.isabs(path):
            path = os.path.join(project_root, path)
        return path
    return None


def create_backup(app):
    """Создаёт бэкап базы в каталоге backups/ в корне проекта."""
    db_path = get_db_path(app)
    if not db_path or not os.path.exists(db_path):
        return None
    backup_dir = os.path.join(project_root, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name = f'before_merge_schools_{timestamp}.db'
    backup_path = os.path.join(backup_dir, name)
    try:
        shutil.copy2(db_path, backup_path)
        return name
    except Exception:
        return None


def cmd_list(app, search=None, limit=50):
    """Вывести список клубов с количеством спортсменов."""
    with app.app_context():
        q = db.session.query(Club.id, Club.name, db.func.count(Athlete.id).label('cnt')).outerjoin(
            Athlete, Club.id == Athlete.club_id
        ).group_by(Club.id, Club.name).order_by(db.text('cnt DESC'))
        if search:
            pattern = f'%{search}%'
            q = q.filter(db.func.lower(Club.name).like(db.func.lower(pattern)))
        rows = q.limit(limit).all()
        print("ID   | Спортсменов | Название")
        print("-" * 80)
        for club_id, name, cnt in rows:
            print(f"{club_id:4d} | {cnt:11d} | {name or '(без названия)'}")
        return 0


def cmd_show(app, club_id=None, search=None):
    """Проверить школу по БД: данные клуба и список спортсменов с club_id = этот клуб."""
    with app.app_context():
        if club_id is not None:
            clubs = [db.session.get(Club, club_id)]
            if not clubs[0]:
                print(f"Клуб с ID {club_id} не найден.", file=sys.stderr)
                return 1
        elif search:
            pattern = f'%{search}%'
            clubs = Club.query.filter(db.func.lower(Club.name).like(db.func.lower(pattern))).order_by(Club.id).all()
            if not clubs:
                print(f"Клубы по запросу «{search}» не найдены.", file=sys.stderr)
                return 1
        else:
            print("Укажите ID школы или --search \"название\"", file=sys.stderr)
            return 1

        for club in clubs:
            athletes = Athlete.query.filter_by(club_id=club.id).order_by(Athlete.last_name, Athlete.first_name).all()
            print("=" * 70)
            print("КЛУБ В БД")
            print("=" * 70)
            print(f"  id:          {club.id}")
            print(f"  name:        {club.name!r}")
            print(f"  short_name:  {club.short_name!r}")
            print(f"  external_id: {club.external_id!r}")
            print(f"  country:     {club.country!r}")
            print(f"  city:        {club.city!r}")
            print(f"  спортсменов: {len(athletes)}")
            print()
            if athletes:
                print("  Спортсмены (athlete_id, full_name):")
                for a in athletes:
                    print(f"    {a.id:5d}  {a.full_name}")
            else:
                print("  Спортсмены: нет записей в athlete с club_id =", club.id)
            print("=" * 70)
        return 0


def cmd_merge(app, keep_id, remove_id, yes=False, no_delete=False):
    """Объединить клуб remove_id в keep_id: все спортсмены из remove_id получают club_id = keep_id."""
    with app.app_context():
        keep = db.session.get(Club, keep_id)
        remove = db.session.get(Club, remove_id)
        if not keep:
            print(f"Клуб с ID {keep_id} не найден.", file=sys.stderr)
            return 1
        if not remove:
            print(f"Клуб с ID {remove_id} не найден.", file=sys.stderr)
            return 1
        if keep_id == remove_id:
            print("Нельзя объединить клуб сам с собой.", file=sys.stderr)
            return 1

        keep_count = Athlete.query.filter_by(club_id=keep_id).count()
        remove_count = Athlete.query.filter_by(club_id=remove_id).count()

        print("=" * 70)
        print("ОБЪЕДИНЕНИЕ ШКОЛ")
        print("=" * 70)
        print(f"  ОСТАВЛЯЕМ (все переходят сюда): ID {keep_id} — «{keep.name}»")
        print(f"    Спортсменов: {keep_count}")
        print(f"  ПЕРЕНОСИМ ИЗ (будет пустая, можно удалить): ID {remove_id} — «{remove.name}»")
        print(f"    Спортсменов: {remove_count}")
        print(f"  ИТОГО в «{keep.name}» после объединения: {keep_count + remove_count}")
        print("=" * 70)

        if not yes:
            answer = input("Выполнить? (yes/NO): ").strip().lower()
            if answer != 'yes':
                print("Отменено.")
                return 0

        backup_name = create_backup(app)
        if not backup_name:
            print("Внимание: бэкап недоступен (не SQLite или нет прав на запись).", file=sys.stderr)
            if not yes:
                answer = input("Продолжить без бэкапа? (yes/NO): ").strip().lower()
                if answer != 'yes':
                    print("Отменено.")
                    return 1
            backup_name = "(не создан)"

        try:
            if remove_count > 0:
                Athlete.query.filter_by(club_id=remove_id).update({'club_id': keep_id})
            if not no_delete:
                db.session.delete(remove)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Ошибка: {e}", file=sys.stderr)
            return 1

        final = Athlete.query.filter_by(club_id=keep_id).count()
        print("Готово.")
        print(f"  Перенесено спортсменов: {remove_count}")
        print(f"  В «{keep.name}» теперь: {final}")
        if not no_delete:
            print(f"  Клуб «{remove.name}» (ID {remove_id}) удалён.")
        if backup_name and backup_name != "(не создан)":
            print(f"  Бэкап: backups/{backup_name}")
        return 0


def cmd_merge_many(app, keep_id, remove_ids, yes=False, no_delete=False):
    """Объединить несколько клубов remove_ids в один keep_id за один запуск."""
    with app.app_context():
        keep = db.session.get(Club, keep_id)
        if not keep:
            print(f"Клуб с ID {keep_id} не найден.", file=sys.stderr)
            return 1

        remove_ids = [r for r in remove_ids if r != keep_id]
        if not remove_ids:
            print("Нет школ для переноса (или все совпадают с целевой).", file=sys.stderr)
            return 1

        clubs = []
        total_remove = 0
        for rid in remove_ids:
            c = db.session.get(Club, rid)
            if not c:
                print(f"Клуб с ID {rid} не найден — пропуск.", file=sys.stderr)
                continue
            cnt = Athlete.query.filter_by(club_id=rid).count()
            clubs.append((rid, c, cnt))
            total_remove += cnt

        if not clubs:
            print("Нет найденных клубов для переноса.", file=sys.stderr)
            return 1

        keep_count = Athlete.query.filter_by(club_id=keep_id).count()

        print("=" * 70)
        print("ОБЪЕДИНЕНИЕ НЕСКОЛЬКИХ ШКОЛ В ОДНУ")
        print("=" * 70)
        print(f"  ОСТАВЛЯЕМ: ID {keep_id} — «{keep.name}»")
        print(f"    Спортсменов сейчас: {keep_count}")
        print()
        print("  ПЕРЕНОСИМ ИЗ:")
        for rid, c, cnt in clubs:
            print(f"    ID {rid} — «{c.name}» ({cnt} спортсменов)")
        print(f"  ИТОГО перенесётся: {total_remove}")
        print(f"  В «{keep.name}» после объединения: {keep_count + total_remove}")
        print("=" * 70)

        if not yes:
            answer = input("Выполнить? (yes/NO): ").strip().lower()
            if answer != 'yes':
                print("Отменено.")
                return 0

        backup_name = create_backup(app)
        if not backup_name:
            print("Внимание: бэкап недоступен (не SQLite или нет прав на запись).", file=sys.stderr)
            if not yes:
                answer = input("Продолжить без бэкапа? (yes/NO): ").strip().lower()
                if answer != 'yes':
                    print("Отменено.")
                    return 1
            backup_name = "(не создан)"

        try:
            for rid, c, cnt in clubs:
                if cnt > 0:
                    Athlete.query.filter_by(club_id=rid).update({'club_id': keep_id})
                if not no_delete:
                    db.session.delete(c)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Ошибка: {e}", file=sys.stderr)
            return 1

        final = Athlete.query.filter_by(club_id=keep_id).count()
        print("Готово.")
        print(f"  Перенесено спортсменов: {total_remove}")
        print(f"  В «{keep.name}» теперь: {final}")
        if not no_delete:
            print(f"  Удалено клубов: {len(clubs)}")
        if backup_name and backup_name != "(не создан)":
            print(f"  Бэкап: backups/{backup_name}")
        return 0


def cmd_unassign(app, athlete_id, yes=False):
    """Снять спортсмена с клуба (club_id = NULL). Удобно, если у спортсмена нет выступлений и клуб нужно удалить."""
    with app.app_context():
        athlete = db.session.get(Athlete, athlete_id)
        if not athlete:
            print(f"Спортсмен с ID {athlete_id} не найден.", file=sys.stderr)
            return 1
        club = db.session.get(Club, athlete.club_id) if athlete.club_id else None
        print(f"Спортсмен: ID {athlete_id} — {athlete.full_name}")
        print(f"  Сейчас в клубе: {club.name if club else '(нет)'} (ID {athlete.club_id})")
        if not athlete.club_id:
            print("Уже без клуба. Ничего менять не нужно.")
            return 0
        if not yes:
            answer = input("Снять с клуба (club_id = NULL)? (yes/NO): ").strip().lower()
            if answer != 'yes':
                print("Отменено.")
                return 0
        try:
            athlete.club_id = None
            db.session.commit()
            print(f"Готово. У спортсмена {athlete_id} теперь club_id = NULL.")
            if club:
                left = Athlete.query.filter_by(club_id=club.id).count()
                print(f"В клубе «{club.name}» (ID {club.id}) осталось спортсменов: {left}")
            return 0
        except Exception as e:
            db.session.rollback()
            print(f"Ошибка: {e}", file=sys.stderr)
            return 1


def cmd_delete_athlete(app, athlete_id, yes=False):
    """Удалить спортсмена из базы (и все его участия, назначения тренеров и т.д.)."""
    with app.app_context():
        athlete = db.session.get(Athlete, athlete_id)
        if not athlete:
            print(f"Спортсмен с ID {athlete_id} не найден.", file=sys.stderr)
            return 1
        from models import Participant
        participations = Participant.query.filter_by(athlete_id=athlete_id).count()
        club = db.session.get(Club, athlete.club_id) if athlete.club_id else None
        print(f"Спортсмен: ID {athlete_id} — {athlete.full_name}")
        print(f"  Клуб: {club.name if club else '(нет)'} (ID {athlete.club_id})")
        print(f"  Участий в турнирах: {participations}")
        if not yes:
            answer = input("Удалить спортсмена из БД полностью? (yes/NO): ").strip().lower()
            if answer != 'yes':
                print("Отменено.")
                return 0
        try:
            CoachAssignment.query.filter_by(athlete_id=athlete_id).delete()
            db.session.delete(athlete)
            db.session.commit()
            print(f"Спортсмен ID {athlete_id} удалён из базы.")
            if club:
                left = Athlete.query.filter_by(club_id=club.id).count()
                print(f"В клубе «{club.name}» (ID {club.id}) осталось спортсменов: {left}")
            return 0
        except Exception as e:
            db.session.rollback()
            print(f"Ошибка: {e}", file=sys.stderr)
            return 1


def cmd_delete(app, club_id, yes=False):
    """Удалить школу из базы. Разрешено только если в ней 0 спортсменов."""
    with app.app_context():
        club = db.session.get(Club, club_id)
        if not club:
            print(f"Клуб с ID {club_id} не найден.", file=sys.stderr)
            return 1
        cnt = Athlete.query.filter_by(club_id=club_id).count()
        if cnt > 0:
            print(f"Удалить нельзя: в школе «{club.name}» (ID {club_id}) {cnt} спортсменов.", file=sys.stderr)
            print("Сначала объедините её с другой: merge <ID_оставляем>", club_id, file=sys.stderr)
            return 1
        print(f"Школа: ID {club_id} — «{club.name}» (спортсменов: 0)")
        if not yes:
            answer = input("Удалить? (yes/NO): ").strip().lower()
            if answer != 'yes':
                print("Отменено.")
                return 0
        try:
            db.session.delete(club)
            db.session.commit()
            print(f"Школа ID {club_id} удалена.")
            return 0
        except Exception as e:
            db.session.rollback()
            print(f"Ошибка: {e}", file=sys.stderr)
            return 1


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Объединение школ (клубов): перенос спортсменов из одной школы в другую.'
    )
    sub = parser.add_subparsers(dest='command', help='list | show | merge | unassign | delete | delete-athlete')

    # list
    plist = sub.add_parser('list', help='Список клубов с числом спортсменов')
    plist.add_argument('--search', '-s', help='Поиск по названию (подстрока)')
    plist.add_argument('--limit', '-n', type=int, default=80, help='Максимум строк (по умолчанию 80)')

    # merge
    pmerge = sub.add_parser('merge', help='Объединить школу(и) в одну. Один ID = оставляем, остальные = переносим.')
    pmerge.add_argument('keep_id', nargs='?', type=int, help='ID школы, которую оставляем')
    pmerge.add_argument('remove_ids', nargs='*', type=int, help='ID школ, из которых переносим (можно несколько)')
    pmerge.add_argument('--into', type=int, metavar='ID', help='ID школы, которую оставляем (вместо первого аргумента)')
    pmerge.add_argument('--from', dest='from_id', type=int, metavar='ID', help='ID школы, из которой переносим (вместо списка)')
    pmerge.add_argument('--yes', '-y', action='store_true', help='Не спрашивать подтверждение')
    pmerge.add_argument('--no-delete', action='store_true', help='Не удалять пустые школы после переноса')

    # show (проверка по БД)
    pshow = sub.add_parser('show', help='Проверить школу по БД: данные клуба и спортсмены')
    pshow.add_argument('club_id', nargs='?', type=int, help='ID школы')
    pshow.add_argument('--search', '-s', help='Поиск по названию (показать все совпадения)')

    # unassign (снять спортсмена с клуба)
    punassign = sub.add_parser('unassign', help='Снять спортсмена с клуба (club_id = NULL)')
    punassign.add_argument('athlete_id', type=int, help='ID спортсмена')
    punassign.add_argument('--yes', '-y', action='store_true', help='Не спрашивать подтверждение')

    # delete (школу)
    pdelete = sub.add_parser('delete', help='Удалить пустую школу (0 спортсменов)')
    pdelete.add_argument('club_id', type=int, help='ID школы для удаления')
    pdelete.add_argument('--yes', '-y', action='store_true', help='Не спрашивать подтверждение')

    # delete-athlete (спортсмена)
    pdelath = sub.add_parser('delete-athlete', help='Удалить спортсмена из БД полностью')
    pdelath.add_argument('athlete_id', type=int, help='ID спортсмена')
    pdelath.add_argument('--yes', '-y', action='store_true', help='Не спрашивать подтверждение')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    app = create_app()

    if args.command == 'list':
        return cmd_list(app, search=getattr(args, 'search', None), limit=args.limit)

    if args.command == 'show':
        club_id = getattr(args, 'club_id', None)
        search = getattr(args, 'search', None)
        if club_id is None and not search:
            print("Укажите ID школы или --search \"название\"", file=sys.stderr)
            return 1
        return cmd_show(app, club_id=club_id, search=search)

    if args.command == 'merge':
        keep_id = args.into if getattr(args, 'into', None) is not None else args.keep_id
        from_id = getattr(args, 'from_id', None)
        if from_id is not None:
            remove_ids = [from_id]
        else:
            remove_ids = list(args.remove_ids or [])
        if keep_id is None:
            print("Укажите школу, которую оставляем: merge <ID_оставляем> [ID1 ID2 ...] или --into ID --from ID", file=sys.stderr)
            return 1
        if len(remove_ids) == 0:
            print("Укажите хотя бы одну школу для переноса: merge <ID_оставляем> <ID1> [ID2 ...] или --from ID", file=sys.stderr)
            return 1
        if len(remove_ids) == 1:
            return cmd_merge(app, keep_id, remove_ids[0], yes=args.yes, no_delete=args.no_delete)
        return cmd_merge_many(app, keep_id, remove_ids, yes=args.yes, no_delete=args.no_delete)

    if args.command == 'unassign':
        return cmd_unassign(app, args.athlete_id, yes=args.yes)

    if args.command == 'delete':
        return cmd_delete(app, args.club_id, yes=args.yes)

    if args.command == 'delete-athlete':
        return cmd_delete_athlete(app, args.athlete_id, yes=args.yes)

    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
