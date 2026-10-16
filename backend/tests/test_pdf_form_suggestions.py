from io import BytesIO

from reportlab.pdfgen import canvas

from app.services.pdf_form_suggestion_service import suggest_pdf_questions


def test_pdf_questions_are_suggestions_from_text_not_published():
    buffer = BytesIO()
    page = canvas.Canvas(buffer)
    page.drawString(60, 770, "Encuesta de visita")
    page.drawString(60, 740, "Nombre completo:")
    page.drawString(60, 710, "Correo electronico:")
    page.drawString(60, 680, "Fecha de visita:")
    page.save()

    result = suggest_pdf_questions(buffer.getvalue())

    assert result["page_count"] == 1
    assert [item["type"] for item in result["questions"]] == ["TEXT", "EMAIL", "DATE"]
