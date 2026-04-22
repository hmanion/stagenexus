from __future__ import annotations

import unittest

from app.models.domain import (
    CampaignAssignment,
    Client,
    ClientContact,
    Deliverable,
    DeliverableStatus,
    DeliverableType,
    Publication,
    PublicationName,
    Review,
    RoleName,
    User,
    UserRoleAssignment,
)
from app.semantic.schemaorg import schema_org_type, to_schema_org_payload


class SchemaOrgHookTests(unittest.TestCase):
    def test_person_mappings(self) -> None:
        user = User(id="u1", email="u@example.com", full_name="User One")
        contact = ClientContact(id="cc1", client_id="c1", name="Contact One", email="c@example.com")
        self.assertEqual(schema_org_type(user), "Person")
        self.assertEqual(schema_org_type(contact), "Person")
        self.assertEqual(to_schema_org_payload(user)["@type"], "Person")
        self.assertEqual(to_schema_org_payload(contact)["@type"], "Person")

    def test_organization_mappings(self) -> None:
        client = Client(id="c1", name="Client One")
        publication = Publication(id="p1", name=PublicationName.UC_TODAY)
        self.assertEqual(schema_org_type(client), "Organization")
        self.assertEqual(schema_org_type(publication), "Organization")
        self.assertEqual(to_schema_org_payload(client)["name"], "Client One")
        self.assertEqual(to_schema_org_payload(publication)["name"], "uc_today")

    def test_deliverable_subtype_mappings(self) -> None:
        article = Deliverable(
            id="d1",
            display_id="DEL-1",
            publication_id="p1",
            deliverable_type=DeliverableType.ARTICLE,
            status=DeliverableStatus.PLANNED,
            title="Article One",
        )
        video = Deliverable(
            id="d2",
            display_id="DEL-2",
            publication_id="p1",
            deliverable_type=DeliverableType.VIDEO,
            status=DeliverableStatus.PLANNED,
            title="Video One",
        )
        report = Deliverable(
            id="d3",
            display_id="DEL-3",
            publication_id="p1",
            deliverable_type=DeliverableType.REPORT,
            status=DeliverableStatus.PLANNED,
            title="Report One",
        )

        self.assertEqual(schema_org_type(article), "Article")
        self.assertEqual(schema_org_type(video), "VideoObject")
        self.assertEqual(schema_org_type(report), "Report")

    def test_review_mapping(self) -> None:
        review = Review(
            id="r1",
            display_id="REV-1",
            deliverable_id="d1",
            review_type="internal",
            status="approved",
            comments="Looks good",
        )
        payload = to_schema_org_payload(review)
        self.assertEqual(payload["@type"], "Review")
        self.assertEqual(payload["itemReviewed"]["identifier"], "d1")

    def test_role_assignment_mapping(self) -> None:
        campaign_assignment = CampaignAssignment(
            id="ca1",
            campaign_id="camp1",
            role_name=RoleName.CM,
            user_id="u1",
        )
        user_assignment = UserRoleAssignment(id="ura1", user_id="u1", role_id="role1")

        campaign_payload = to_schema_org_payload(campaign_assignment)
        user_payload = to_schema_org_payload(user_assignment)
        self.assertEqual(schema_org_type(campaign_assignment), "OrganizationRole")
        self.assertEqual(schema_org_type(user_assignment), "OrganizationRole")
        self.assertEqual(campaign_payload["roleName"], "cm")
        self.assertEqual(user_payload["roleName"], "role1")


if __name__ == "__main__":
    unittest.main()
