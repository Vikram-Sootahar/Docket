"""CV builder: fixed interview questions and PDF generation (no AI calls in this file)."""

from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

QUESTIONS = [
    {"key": "name", "prompt": "What is your full name?"},
    {"key": "contact", "prompt": "Your contact details: email, phone, city, and links (GitHub/LinkedIn)."},
    {"key": "education", "prompt": "Your education: degree, university, dates, CGPA or highlights."},
    {"key": "skills", "prompt": "Your key skills (separate with commas)."},
    {"key": "experience", "prompt": "Work, internship or volunteering: role, organization, dates, what you did. (Type 'skip' if none)"},
    {"key": "projects", "prompt": "Your best projects: name and one line about each. (Type 'skip' if none)"},
    {"key": "certifications", "prompt": "Certifications or awards. (Type 'skip' if none)"},
]


def _txt(value) -> str:
    return escape(str(value).strip())


def _as_list(value) -> list:
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [v for v in value if v]
    return [value]


def build_cv_pdf(cv: dict, output_path: str) -> dict:
    """Build a polished, professional one-column CV PDF from a structured dict."""
    try:
        base = getSampleStyleSheet()
        dark = colors.HexColor("#16324F")
        accent = colors.HexColor("#2E6E9E")
        grey = colors.HexColor("#5A5A5A")
        light_grey = colors.HexColor("#8A8A8A")
        pill_bg = colors.HexColor("#EAF1F8")

        name_style = ParagraphStyle(
            "CVName", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=25, leading=28, textColor=dark, spaceAfter=3, alignment=0,
        )
        contact_style = ParagraphStyle(
            "CVContact", parent=base["Normal"], fontSize=9.5,
            leading=13, textColor=grey, alignment=0,
        )
        heading_style = ParagraphStyle(
            "CVHeading", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=11.5, leading=14, spaceBefore=14, spaceAfter=5,
            textColor=dark, letterSpacing=1.2,
        )
        body = ParagraphStyle(
            "CVBody", parent=base["Normal"], fontSize=10, leading=15,
            textColor=colors.HexColor("#222222"), alignment=4,
        )
        bold_line = ParagraphStyle(
            "CVBold", parent=body, fontName="Helvetica-Bold", fontSize=10.5,
            leading=13, spaceBefore=6, textColor=dark, alignment=0,
        )
        org_style = ParagraphStyle(
            "CVOrg", parent=body, fontName="Helvetica-Oblique", fontSize=9.5,
            leading=12, textColor=accent, alignment=0,
        )
        small = ParagraphStyle(
            "CVSmall", parent=body, fontSize=8.5, leading=11,
            textColor=light_grey, alignment=0,
        )
        bullet = ParagraphStyle(
            "CVBullet", parent=body, fontSize=9.8, leading=14,
            leftIndent=16, bulletIndent=4, spaceAfter=2, alignment=4,
        )

        story = []

        def heading(title):
            story.append(Paragraph(title.upper(), heading_style))
            story.append(HRFlowable(width="100%", thickness=1.1, color=accent, spaceAfter=6))

        story.append(Paragraph(_txt(cv.get("name") or "Your Name"), name_style))
        story.append(HRFlowable(width="100%", thickness=2.2, color=dark, spaceBefore=2, spaceAfter=8))

        contact = cv.get("contact") or {}
        if isinstance(contact, dict):
            parts = [contact.get("email"), contact.get("phone"), contact.get("location")]
            parts += _as_list(contact.get("links"))
        else:
            parts = _as_list(contact)
        parts = [str(p).strip() for p in parts if p]
        if parts:
            story.append(Paragraph(_txt("   \u2022   ".join(parts)), contact_style))

        if cv.get("summary"):
            heading("Summary")
            story.append(Paragraph(_txt(cv["summary"]), body))

        education = _as_list(cv.get("education"))
        if education:
            heading("Education")
            for e in education:
                if isinstance(e, dict):
                    line = ", ".join(str(x) for x in [e.get("degree"), e.get("institution")] if x)
                    row_cells = [Paragraph(_txt(line), bold_line)]
                    if e.get("dates"):
                        row_cells = [Paragraph(_txt(line), bold_line), Paragraph(_txt(e["dates"]), small)]
                        t = Table([row_cells], colWidths=[4.6 * inch, 1.4 * inch])
                        t.setStyle(TableStyle([
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                            ("TOPPADDING", (0, 0), (-1, -1), 0),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                        ]))
                        story.append(t)
                    else:
                        story.append(Paragraph(_txt(line), bold_line))
                    for d in _as_list(e.get("details")):
                        story.append(Paragraph(_txt(d), bullet, bulletText="\u2022"))
                else:
                    story.append(Paragraph(_txt(e), body))
                story.append(Spacer(1, 5))

        skills = _as_list(cv.get("skills"))
        if skills:
            heading("Skills")
            cell_style = ParagraphStyle(
                "CVSkillPill", parent=body, fontSize=9, leading=12,
                textColor=dark, alignment=1,
            )
            cells = [Paragraph(_txt(s), cell_style) for s in skills]
            rows, row, per_row = [], [], 4
            for i, c in enumerate(cells):
                row.append(c)
                if len(row) == per_row or i == len(cells) - 1:
                    while len(row) < per_row:
                        row.append("")
                    rows.append(row)
                    row = []
            col_width = 6.0 * inch / per_row
            t = Table(rows, colWidths=[col_width] * per_row, rowHeights=20)
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BACKGROUND", (0, 0), (-1, -1), pill_bg),
                ("BOX", (0, 0), (-1, -1), 0, colors.white),
                ("INNERGRID", (0, 0), (-1, -1), 4, colors.white),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(t)

        experience = _as_list(cv.get("experience"))
        if experience:
            heading("Experience")
            for x in experience:
                if isinstance(x, dict):
                    title_line = _txt(x.get("title") or "")
                    org_line = _txt(x.get("organization") or "")
                    header_cells = [Paragraph(title_line, bold_line)]
                    if x.get("dates"):
                        t = Table(
                            [[Paragraph(title_line, bold_line), Paragraph(_txt(x["dates"]), small)]],
                            colWidths=[4.6 * inch, 1.4 * inch],
                        )
                        t.setStyle(TableStyle([
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                            ("TOPPADDING", (0, 0), (-1, -1), 0),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                        ]))
                        story.append(t)
                    else:
                        story.append(Paragraph(title_line, bold_line))
                    if org_line:
                        story.append(Paragraph(org_line, org_style))
                    for b in _as_list(x.get("bullets")):
                        story.append(Paragraph(_txt(b), bullet, bulletText="\u2022"))
                else:
                    story.append(Paragraph(_txt(x), body))
                story.append(Spacer(1, 6))

        projects = _as_list(cv.get("projects"))
        if projects:
            heading("Projects")
            for p in projects:
                if isinstance(p, dict):
                    story.append(Paragraph(_txt(p.get("name") or "Project"), bold_line))
                    for b in _as_list(p.get("bullets") or p.get("description")):
                        story.append(Paragraph(_txt(b), bullet, bulletText="\u2022"))
                else:
                    story.append(Paragraph(_txt(p), body))
                story.append(Spacer(1, 6))

        certs = _as_list(cv.get("certifications"))
        if certs:
            heading("Certifications")
            for c in certs:
                story.append(Paragraph(_txt(c), bullet, bulletText="\u2022"))

        doc = SimpleDocTemplate(
            output_path, pagesize=letter,
            leftMargin=60, rightMargin=60, topMargin=54, bottomMargin=54,
            title="CV", author=str(cv.get("name") or ""),
        )
        doc.build(story)
        return {"success": True, "path": output_path}
    except Exception as e:
        return {"success": False, "error": str(e)}


def cv_to_text(cv: dict) -> str:
    """Flatten a structured CV into plain text (used for search and matching)."""
    lines = ["Curriculum Vitae (CV) / Resume"]

    def walk(value):
        if isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, (list, tuple)):
            for v in value:
                walk(v)
        elif value:
            lines.append(str(value))

    walk(cv)
    return "\n".join(lines)