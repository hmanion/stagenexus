from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import (
    Publication,
    PublicationName,
    Role,
    RoleName,
    TemplateVersion,
    User,
    UserRoleAssignment,
)
from app.services.id_service import PublicIdService
from app.workflows.default_templates import DEFAULT_TEMPLATES


DEFAULT_USERS = [
    ("am@todaydigital.local", "John Smith", RoleName.AM),
    ("ops@todaydigital.local", "Jane Doe", RoleName.HEAD_OPS),
    ("cm@todaydigital.local", "Alex Carter", RoleName.CM),
    ("cc@todaydigital.local", "Priya Patel", RoleName.CC),
    ("dn@todaydigital.local", "Jordan Lee", RoleName.DN),
    ("mm@todaydigital.local", "Sam Rivera", RoleName.MM),
    ("sales@todaydigital.local", "Morgan Clark", RoleName.HEAD_SALES),
]


def seed_bootstrap(db: Session) -> None:
    public_ids = PublicIdService(db)
    for role_name in RoleName:
        if not db.scalar(select(Role).where(Role.name == role_name)):
            db.add(Role(name=role_name))

    for publication_name in PublicationName:
        if not db.scalar(select(Publication).where(Publication.name == publication_name)):
            db.add(Publication(name=publication_name))

    for email, full_name, role_name in DEFAULT_USERS:
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(email=email, full_name=full_name)
            db.add(user)
            db.flush()
        elif user.full_name != full_name:
            user.full_name = full_name

        role = db.scalar(select(Role).where(Role.name == role_name))
        if role and not db.scalar(
            select(UserRoleAssignment).where(
                UserRoleAssignment.user_id == user.id,
                UserRoleAssignment.role_id == role.id,
            )
        ):
            db.add(UserRoleAssignment(user_id=user.id, role_id=role.id))

    for template_name, payload in DEFAULT_TEMPLATES.items():
        exists = db.scalar(select(TemplateVersion).where(TemplateVersion.name == template_name, TemplateVersion.version == payload["version"]))
        if not exists:
            db.add(
                TemplateVersion(
                    display_id=public_ids.next_id(TemplateVersion, "TPL"),
                    name=template_name,
                    version=payload["version"],
                    workflow_json=payload,
                    is_active=True,
                )
            )

    db.commit()
