"""PDF generator for detailed judging protocols."""

import io
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from models import Performance, Element, ComponentScore
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def _format_score(value, divide_100=False):
    if value is None:
        return ''
    try:
        if divide_100:
            return f"{int(value) / 100:.2f}"
        return f"{float(value):.2f}"
    except (ValueError, TypeError):
        return ''


def _register_cyrillic_font():
    """Регистрирует шрифт с поддержкой кириллицы, если доступен в системе.

    Возвращает fontName (str), который можно использовать в стилях ReportLab.
    """
    candidates = [
        # Linux (обычно в контейнере/VM)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # Windows (для локальной генерации)
        r"C:\Windows\Fonts\arial.ttf",
    ]

    # Если уже зарегистрирован ранее (в рамках процесса) — просто используем.
    try:
        if "AppCyrillic" in pdfmetrics.getRegisteredFontNames():
            return "AppCyrillic"
    except Exception:
        pass

    for path in candidates:
        try:
            if path and os.path.exists(path):
                pdfmetrics.registerFont(TTFont("AppCyrillic", path))
                return "AppCyrillic"
        except Exception:
            # Если не получилось — просто пробуем следующий кандидат
            continue
    return "Helvetica"


def generate_first_timers_detail_pdf_bytes(report):
    """Генерирует PDF (bytes) для отчёта «Новички и повторяющиеся — детальный»."""
    font_name = _register_cyrillic_font()
    styles = getSampleStyleSheet()

    # Подправляем базовые стили под компактный вид
    title_style = styles["Title"].clone("TitleCyr")
    title_style.fontName = font_name
    title_style.fontSize = 14
    title_style.leading = 16

    h2_style = styles["Heading2"].clone("H2Cyr")
    h2_style.fontName = font_name
    h2_style.fontSize = 11
    h2_style.leading = 13
    h2_style.spaceBefore = 8
    h2_style.spaceAfter = 4

    h3_style = styles["Heading3"].clone("H3Cyr")
    h3_style.fontName = font_name
    h3_style.fontSize = 9
    h3_style.leading = 11
    h3_style.spaceBefore = 6
    h3_style.spaceAfter = 3

    normal_style = styles["Normal"].clone("NormalCyr")
    normal_style.fontName = font_name
    normal_style.fontSize = 8
    normal_style.leading = 10

    small_style = styles["Normal"].clone("SmallCyr")
    small_style.fontName = font_name
    small_style.fontSize = 7
    small_style.leading = 9

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=4 * mm,
        rightMargin=4 * mm,
        topMargin=4 * mm,
        bottomMargin=4 * mm,
        title="Новички и повторяющиеся — детальный отчёт",
    )

    story = []
    story.append(Paragraph("Новички и повторяющиеся — детальный отчёт", title_style))
    story.append(Paragraph(
        "По каждому турниру и разряду: повторяющиеся спортсмены, номер выступления в разряде и все предыдущие турниры.",
        normal_style
    ))
    story.append(Spacer(1, 6))

    events = (report or {}).get("events") or []
    if not events:
        story.append(Paragraph("Нет данных о турнирах.", normal_style))
        doc.build(story)
        return buffer.getvalue()

    # Ширина таблицы = doc.width (уже с учётом полей)
    table_width = doc.width
    col_widths = [
        table_width * 0.26,  # ФИО
        table_width * 0.18,  # Школа
        table_width * 0.08,  # N-й раз
        table_width * 0.48,  # Предыдущие
    ]

    for event in events:
        event_name = (event.get("event_name") or "—").strip()
        event_date = event.get("event_date_display") or "—"
        story.append(Paragraph(f"{event_name} — {event_date}", h2_style))

        rank_stats = event.get("rank_stats") or []
        ranks_with_repeaters = [r for r in rank_stats if (r.get("repeaters_detail") or [])]
        if not ranks_with_repeaters:
            story.append(Paragraph("Нет повторяющихся в этом турнире.", normal_style))
            story.append(Spacer(1, 4))
            continue

        for rank_stat in ranks_with_repeaters:
            rank_name = (rank_stat.get("rank") or "Без разряда").strip()
            repeaters = rank_stat.get("repeaters") or 0
            total_children = rank_stat.get("total_children") or 0
            story.append(Paragraph(f"Разряд: {rank_name} (повторяющихся: {repeaters} из {total_children})", h3_style))

            data = [["ФИО", "Школа", "Очередной раз", "Все предыдущие выступления (турнир — дата)"]]
            for r in (rank_stat.get("repeaters_detail") or []):
                athlete_name = (r.get("athlete_name") or "—").strip()
                athlete_school = (r.get("athlete_school") or "—").strip()
                appearance_number = r.get("appearance_number") or ((r.get("total_previous_count") or 0) + 1)
                appearance_text = f"{appearance_number}-й"

                prev_lines = []
                for prev in (r.get("previous_appearances") or []):
                    pn = (prev.get("event_name") or "—").strip()
                    pd = (prev.get("event_date") or "—").strip()
                    prev_lines.append(f"{pn} — {pd}")
                prev_html = "<br/>".join(prev_lines) if prev_lines else "—"

                data.append([
                    Paragraph(athlete_name, small_style),
                    Paragraph(athlete_school, small_style),
                    Paragraph(appearance_text, small_style),
                    Paragraph(prev_html, small_style),
                ])

            table = Table(data, colWidths=col_widths, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (2, 1), (2, -1), "CENTER"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
            ]))
            story.append(table)
            story.append(Spacer(1, 6))

    doc.build(story)
    return buffer.getvalue()


def generate_performance_pdf(performance_id, output_path):
    """Generate a detailed PDF protocol for a single performance."""
    performance = Performance.query.get(performance_id)
    if not performance:
        raise ValueError(f"Performance {performance_id} not found")

    participant = performance.participant
    athlete = participant.athlete
    segment = performance.segment
    category = segment.category
    event = category.event

    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )
    styles = getSampleStyleSheet()
    story = []

    title = f"{event.name} — {category.name}"
    subtitle = f"{segment.name} — Детализация судейских оценок"
    athlete_line = f"{athlete.full_name} | Старт № {performance.index or '-'}"
    score_line = f"TES: {_format_score(performance.tes_total, True)} | PCS: {_format_score(performance.pcs_total, True)} | Total: {_format_score(performance.points)}"

    story.append(Paragraph(title, styles['Title']))
    story.append(Paragraph(subtitle, styles['Heading2']))
    story.append(Paragraph(athlete_line, styles['Normal']))
    story.append(Paragraph(score_line, styles['Normal']))
    story.append(Spacer(1, 6))

    # Elements table
    elements = Element.query.filter_by(performance_id=performance.id).order_by(Element.order_num.asc()).all()
    element_headers = ['#', 'Element', 'Info', 'BV', 'GOE', 'PNL', 'RES', 'Flag'] + [f'J{j:02d}' for j in range(1, 16)]
    element_rows = [element_headers]
    for elem in elements:
        judge_scores = elem.judge_scores or {}
        total_score = None
        if elem.result is not None:
            total_score = elem.result
        elif elem.base_value is not None or elem.goe_result is not None:
            total_score = (elem.base_value or 0) + (elem.goe_result or 0)
        flag_value = ''
        if judge_scores.get('confirmed'):
            flag_value = str(judge_scores.get('confirmed'))
        if judge_scores.get('time_code'):
            flag_value = f"{flag_value} {judge_scores.get('time_code')}".strip()
        row = [
            elem.order_num or '',
            elem.executed_code or elem.planned_code or '',
            elem.info_code or '',
            _format_score(elem.base_value, True),
            _format_score(elem.goe_result, True),
            _format_score(elem.penalty, True),
            _format_score(total_score, True),
            flag_value,
        ]
        for j in range(1, 16):
            key = f'J{j:02d}'
            value = judge_scores.get(key)
            row.append('' if value is None else str(value))
        element_rows.append(row)

    element_table = Table(element_rows, repeatRows=1)
    element_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
    ]))
    story.append(Paragraph("Выполненные элементы", styles['Heading3']))
    story.append(element_table)
    story.append(Spacer(1, 6))

    # Components table
    components = ComponentScore.query.filter_by(performance_id=performance.id).all()
    component_headers = ['Component', 'Score'] + [f'J{j:02d}' for j in range(1, 16)]
    component_rows = [component_headers]
    for comp in components:
        row = [
            comp.component_type or '',
            _format_score(comp.result, True),
        ]
        for j in range(1, 16):
            key = f'J{j:02d}'
            value = comp.judge_scores.get(key) if comp.judge_scores else None
            row.append('' if value is None else str(value))
        component_rows.append(row)

    component_table = Table(component_rows, repeatRows=1)
    component_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
    ]))
    story.append(Paragraph("Компоненты программы", styles['Heading3']))
    story.append(component_table)

    doc.build(story)
