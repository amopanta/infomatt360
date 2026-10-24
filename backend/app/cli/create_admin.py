"""Crea o recupera una cuenta de administrador desde el servidor (docs/147).

Sirve cuando el sistema ya está instalado (el asistente de primer arranque
responde 409) y nadie puede entrar: por ejemplo, el responsable no tiene
cuenta o el correo para recuperar la contraseña aún no está configurado.

La contraseña se pide por teclado sin mostrarla y nunca va en la línea de
comandos ni en el historial. Si el correo ya existe, se le pone la
contraseña nueva y se reactiva; en ambos casos queda como administrador de
todos los proyectos activos (o de los indicados con --project). Cada uso
queda en la auditoría.

Uso en producción (desde /opt/infomatt360):
    docker compose -f docker-compose.production.example.yml --env-file .env.production \\
        exec backend-1 python -m app.cli.create_admin --email persona@ejemplo.com --name "Nombre Apellido"
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys

from sqlalchemy.orm import Session

from app.core.permissions import ALL_PERMISSIONS
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.assignment import UserProjectAssignment
from app.models.audit import AuditLog
from app.models.identity import Project, Role, User

ADMIN_ROLE_NAME = "Administrador"
MIN_LENGTH = 10


def password_problem(password: str) -> str | None:
    if len(password) < MIN_LENGTH:
        return f"Debe tener al menos {MIN_LENGTH} caracteres."
    if not any(ch.isalpha() for ch in password) or not any(ch.isdigit() for ch in password):
        return "Debe combinar letras y números."
    return None


def admin_role(db: Session) -> Role:
    """El rol «Administrador» del asistente, con todo el catálogo. Si no
    existe se crea; si existe se completa con permisos agregados después."""
    role = db.query(Role).filter(Role.name == ADMIN_ROLE_NAME).first()
    if role is None:
        role = Role(name=ADMIN_ROLE_NAME, description="Rol con todos los permisos del catálogo")
        db.add(role)
    current = {item for item in (role.permissions or "").split(",") if item}
    role.permissions = ",".join(sorted(current | set(ALL_PERMISSIONS)))
    db.flush()
    return role


def create_or_recover(db: Session, email: str, full_name: str, document_id: str | None, password: str, project_ids: list[str] | None) -> dict:
    email = email.strip().lower()
    projects_query = db.query(Project).filter(Project.status == "active")
    if project_ids:
        projects_query = projects_query.filter(Project.id.in_(project_ids))
    projects = projects_query.all()
    if not projects:
        raise SystemExit("No hay proyectos activos con esos identificadores.")
    role = admin_role(db)
    user = db.query(User).filter(User.email == email).first()
    created = user is None
    if user is None:
        user = User(email=email, full_name=full_name, document_id=document_id, status="active")
        db.add(user)
    elif full_name:
        user.full_name = full_name
    user.password_hash = hash_password(password)
    user.status = "active"
    user.must_change_password = False
    db.flush()
    assigned = []
    for project in projects:
        row = db.query(UserProjectAssignment).filter(UserProjectAssignment.user_id == user.id, UserProjectAssignment.project_id == project.id).first()
        if row is None:
            db.add(UserProjectAssignment(user_id=user.id, project_id=project.id, role_id=role.id, status="active"))
        else:
            row.role_id, row.status = role.id, "active"
        assigned.append(project.name)
    db.add(AuditLog(user_id=user.id, module="identity", action="admin_created_cli" if created else "admin_recovered_cli",
                    entity_type="user", entity_id=user.id, after_json=json.dumps({"email": email, "projects": assigned}, ensure_ascii=False)))
    db.commit()
    return {"created": created, "email": email, "projects": assigned}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Crea o recupera una cuenta de administrador.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="", help="Nombre completo (obligatorio si la cuenta es nueva)")
    parser.add_argument("--document", default=None, help="Número de documento (opcional)")
    parser.add_argument("--project", action="append", help="Id de proyecto; se puede repetir. Por defecto, todos los activos.")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        exists = db.query(User).filter(User.email == args.email.strip().lower()).first() is not None
    if not exists and len(args.name.strip()) < 3:
        sys.exit("Para una cuenta nueva indica el nombre completo con --name.")

    password = getpass.getpass("Contraseña nueva (no se muestra): ")
    problem = password_problem(password)
    if problem:
        sys.exit(problem)
    if getpass.getpass("Repite la contraseña: ") != password:
        sys.exit("Las contraseñas no coinciden. No se cambió nada.")

    with SessionLocal() as db:
        result = create_or_recover(db, args.email, args.name.strip(), args.document, password, args.project)
    action = "Cuenta creada" if result["created"] else "Cuenta recuperada (contraseña nueva y activa)"
    print(f"{action}: {result['email']}")
    print("Administrador en: " + ", ".join(result["projects"]))


if __name__ == "__main__":
    main()
