from __future__ import annotations

from typing import Any

from app.models.domain import (
    CampaignAssignment,
    Client,
    ClientContact,
    Deliverable,
    DeliverableType,
    Publication,
    Review,
    User,
    UserRoleAssignment,
)


def schema_org_type(entity: Any) -> str | None:
    if isinstance(entity, (User, ClientContact)):
        return "Person"
    if isinstance(entity, (Client, Publication)):
        return "Organization"
    if isinstance(entity, Deliverable):
        return _deliverable_schema_type(entity.deliverable_type)
    if isinstance(entity, Review):
        return "Review"
    if isinstance(entity, (CampaignAssignment, UserRoleAssignment)):
        return "OrganizationRole"
    return None


def to_schema_org_payload(entity: Any) -> dict[str, Any]:
    schema_type = schema_org_type(entity)
    if schema_type is None:
        return {}

    payload: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": schema_type,
    }

    if isinstance(entity, User):
        payload["identifier"] = entity.id
        payload["name"] = entity.full_name
        payload["email"] = entity.email
        return payload

    if isinstance(entity, ClientContact):
        payload["identifier"] = entity.id
        payload["name"] = entity.name
        payload["email"] = entity.email
        if entity.title:
            payload["jobTitle"] = entity.title
        payload["worksFor"] = {"@type": "Organization", "identifier": entity.client_id}
        return payload

    if isinstance(entity, Client):
        payload["identifier"] = entity.id
        payload["name"] = entity.name
        return payload

    if isinstance(entity, Publication):
        payload["identifier"] = entity.id
        payload["name"] = entity.name.value
        return payload

    if isinstance(entity, Deliverable):
        payload["identifier"] = entity.id
        payload["name"] = entity.title
        payload["creativeWorkStatus"] = entity.status.value
        payload["isPartOf"] = {"@type": "CreativeWork", "identifier": entity.campaign_id}
        if entity.publication_id:
            payload["publisher"] = {"@type": "Organization", "identifier": entity.publication_id}
        return payload

    if isinstance(entity, Review):
        payload["identifier"] = entity.id
        payload["reviewBody"] = entity.comments or ""
        payload["itemReviewed"] = {"@type": "CreativeWork", "identifier": entity.deliverable_id}
        if entity.reviewer_user_id:
            payload["author"] = {"@type": "Person", "identifier": entity.reviewer_user_id}
        if entity.status:
            payload["reviewRating"] = {"@type": "Rating", "description": entity.status}
        return payload

    if isinstance(entity, CampaignAssignment):
        payload["identifier"] = entity.id
        payload["roleName"] = entity.role_name.value
        payload["member"] = {"@type": "Person", "identifier": entity.user_id}
        payload["memberOf"] = {"@type": "Organization", "identifier": entity.campaign_id}
        return payload

    if isinstance(entity, UserRoleAssignment):
        payload["identifier"] = entity.id
        payload["member"] = {"@type": "Person", "identifier": entity.user_id}
        payload["roleName"] = entity.role_id
        return payload

    return payload


def _deliverable_schema_type(deliverable_type: DeliverableType) -> str:
    if deliverable_type == DeliverableType.ARTICLE:
        return "Article"
    if deliverable_type == DeliverableType.VIDEO:
        return "VideoObject"
    if deliverable_type in {DeliverableType.CLIP, DeliverableType.SHORT}:
        return "MediaObject"
    if deliverable_type == DeliverableType.REPORT:
        return "Report"
    return "CreativeWork"
