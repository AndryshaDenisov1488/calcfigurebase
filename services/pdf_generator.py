"""PDF generator for detailed judging protocols."""

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from models import Performance, Element, ComponentScore


def _format_score(value, divide_100=False):
    if value is None:
        return ''
    try:
        if divide_100:
            return f"{int(value) / 100:.2f}"
        return f"{float(value):.2f}"
    except (ValueError, TypeError):
        return ''


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
