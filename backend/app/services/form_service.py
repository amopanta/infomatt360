from sqlalchemy.orm import Session

from app.models.forms import Form, FormField
from app.schemas.forms import FormCreate, FormFieldRead, FormRead


def _field_to_read(field: FormField) -> FormFieldRead:
    return FormFieldRead(
        id=field.id,
        name=field.name,
        label=field.label,
        field_type=field.field_type,
        required=field.required == "true",
        layout_row=field.layout_row,
        layout_col=field.layout_col,
        options_json=field.options_json,
        rules_json=field.rules_json,
    )


def _form_to_read(db: Session, form: Form) -> FormRead:
    fields = db.query(FormField).filter(FormField.form_id == form.id).order_by(FormField.layout_row, FormField.layout_col).all()
    return FormRead(
        id=form.id,
        project_id=form.project_id,
        name=form.name,
        description=form.description,
        status=form.status,
        current_version=form.current_version,
        fields=[_field_to_read(field) for field in fields],
    )


class FormService:
    def create_form(self, db: Session, payload: FormCreate) -> FormRead:
        form = Form(project_id=payload.project_id, name=payload.name, description=payload.description)
        db.add(form)
        db.commit()
        db.refresh(form)

        for field_payload in payload.fields:
            field = FormField(
                form_id=form.id,
                name=field_payload.name,
                label=field_payload.label,
                field_type=field_payload.field_type,
                required="true" if field_payload.required else "false",
                layout_row=field_payload.layout_row,
                layout_col=field_payload.layout_col,
                options_json=field_payload.options_json,
                rules_json=field_payload.rules_json,
            )
            db.add(field)
        db.commit()
        return _form_to_read(db, form)

    def list_forms(self, db: Session, project_id: str) -> list[FormRead]:
        forms = db.query(Form).filter(Form.project_id == project_id).order_by(Form.created_at.desc()).all()
        return [_form_to_read(db, form) for form in forms]


form_service = FormService()
