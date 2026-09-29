"""CV builder: fixed interview questions and PDF generation (no AI calls in this file)."""

from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

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
    """Build a clean one-column CV PDF from a structured dict."""
    try:
        base = getSampleStyleSheet()
        dark = colors.HexColor("#1F3A5F")
        grey = colors.HexColor("#555555")

        name_style = ParagraphStyle("CVName", parent=base["Title"], fontSize=22, leading=26, spaceAfter=2)
        contact_style = ParagraphStyle("CVContact", parent=base["Normal"], fontSize=9.5, alignment=1, textColor=grey)
        heading_style = ParagraphStyle("CVHeading", parent=base["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=1, textColor=dark)
        body = ParagraphStyle("CVBody", parent=base["Normal"], fontSize=10, leading=13)
        bold_line = ParagraphStyle("CVBold", parent=body, fontName="Helvetica-Bold")
        small = ParagraphStyle("CVSmall", parent=body, fontSize=9, textColor=grey)
        bullet = ParagraphStyle("CVBullet", parent=body, leftIndent=14, bulletIndent=3)

        story = []

        def heading(title):
            story.append(Paragraph(title.upper(), heading_style))
            story.append(HRFlowable(width="100%", thickness=0.6, color=dark, spaceAfter=4))

        story.append(Paragraph(_txt(cv.get("name") or "Your Name"), name_style))

        contact = cv.get("contact") or {}
        if isinstance(contact, dict):
            parts = [contact.get("email"), contact.get("phone"), contact.get("location")]
            parts += _as_list(contact.get("links"))
        else:
            parts = _as_list(contact)
        parts = [str(p).strip() for p in parts if p]
        if parts:
            story.append(Paragraph(_txt("  |  ".join(parts)), contact_style))

        if cv.get("summary"):
            heading("Summary")
            story.append(Paragraph(_txt(cv["summary"]), body))

        education = _as_list(cv.get("education"))
        if education:
            heading("Education")
            for e in education:
                if isinstance(e, dict):
                    line = ", ".join(str(x) for x in [e.get("degree"), e.get("institution")] if x)
                    story.append(Paragraph(_txt(line), bold_line))
                    if e.get("dates"):
                        story.append(Paragraph(_txt(e["dates"]), small))
                    for d in _as_list(e.get("details")):
                        story.append(Paragraph(_txt(d), bullet, bulletText="•"))
                else:
                    story.append(Paragraph(_txt(e), body))
                story.append(Spacer(1, 4))

        skills = _as_list(cv.get("skills"))
        if skills:
            heading("Skills")
            story.append(Paragraph(_txt(", ".join(str(s) for s in skills)), body))

        experience = _as_list(cv.get("experience"))
        if experience:
            heading("Experience")
            for x in experience:
                if isinstance(x, dict):
                    line = " - ".join(str(v) for v in [x.get("title"), x.get("organization")] if v)
                    story.append(Paragraph(_txt(line), bold_line))
                    if x.get("dates"):
                        story.append(Paragraph(_txt(x["dates"]), small))
                    for b in _as_list(x.get("bullets")):
                        story.append(Paragraph(_txt(b), bullet, bulletText="•"))
                else:
                    story.append(Paragraph(_txt(x), body))
                story.append(Spacer(1, 4))

        projects = _as_list(cv.get("projects"))
        if projects:
            heading("Projects")
            for p in projects:
                if isinstance(p, dict):
                    story.append(Paragraph(_txt(p.get("name") or "Project"), bold_line))
                    for b in _as_list(p.get("bullets") or p.get("description")):
                        story.append(Paragraph(_txt(b), bullet, bulletText="•"))
                else:
                    story.append(Paragraph(_txt(p), body))
                story.append(Spacer(1, 4))

        certs = _as_list(cv.get("certifications"))
        if certs:
            heading("Certifications")
            for c in certs:
                story.append(Paragraph(_txt(c), bullet, bulletText="•"))

        doc = SimpleDocTemplate(
            output_path, pagesize=letter,
            leftMargin=54, rightMargin=54, topMargin=48, bottomMargin=48,
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