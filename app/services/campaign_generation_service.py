from __future__ import annotations

from datetime import date, timedelta
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import (
    Campaign,
    CampaignAssignment,
    CampaignType,
    Client,
    Deal,
    DealProductLine,
    Deliverable,
    DeliverableStage,
    DeliverableStatus,
    DeliverableType,
    Milestone,
    ProductModule,
    Publication,
    TemplateVersion,
    WorkflowStep,
    WorkflowStepEffort,
    WorkflowStepDependency,
    Role,
    RoleName,
    WorkflowStepKind,
    User,
    UserRoleAssignment,
    WaitingOnType,
    PublicationName,
)
from app.services.calendar_service import build_default_working_calendar
from app.services.id_service import PublicIdService
from app.services.ops_defaults_service import OpsDefaultsService
from app.services.stage_integrity_service import REPORTING_DELIVERABLE_TYPES, StageIntegrityService
from app.services.timeline_service import TimelineService
from app.services.workflow_engine_service import WorkflowEngineService
from app.workflows.default_templates import DEFAULT_TEMPLATES


class CampaignGenerationService:
    STEP_OWNER_PRIORITY = {
        RoleName.CM: 0,
        RoleName.CC: 1,
        RoleName.AM: 2,
        RoleName.DN: 3,
        RoleName.MM: 4,
        RoleName.CCS: 5,
    }

    def __init__(self, db: Session):
        self.db = db
        self.timeline = TimelineService(build_default_working_calendar())
        self.public_ids = PublicIdService(db)
        self.ops_defaults = OpsDefaultsService(db).get()
        self.stage_integrity = StageIntegrityService(db)

    def generate_for_deal(self, deal: Deal) -> list[Campaign]:
        lines = self.db.scalars(select(DealProductLine).where(DealProductLine.deal_id == deal.id)).all()
        if not lines:
            raise ValueError("Cannot generate campaigns without deal product lines")

        publication = self.db.scalar(select(Publication).where(Publication.name == deal.brand_publication))
        if publication is None:
            raise ValueError("Missing publication seed data")

        generated: list[Campaign] = []
        client_name = self._client_name_from_deal(deal)
        for line in lines:
            template = self._get_or_create_template(line.product_type.value)
            brand_code, yy = self._brand_year_from_deal(deal)
            product_code = self._campaign_product_code(deal, line)
            sow_start = deal.sow_start_date or date.today()

            if line.product_type == CampaignType.DEMAND:
                mode = ((line.options_json or {}).get("demand_module_mode") or "create_reach_capture").strip().lower()
                for i in range(1, 5):
                    sprint_start = sow_start + timedelta(days=(i - 1) * 90)
                    sprint_end = sprint_start + timedelta(days=89)
                    cr_campaign = self._create_campaign_record(
                        deal=deal,
                        template=template,
                        brand_code=brand_code,
                        yy=yy,
                        product_code=product_code,
                        tier=line.tier,
                        campaign_type=line.product_type,
                        title=self._campaign_title(
                            client_name=client_name,
                            deal=deal,
                            campaign_type=line.product_type,
                            tier=line.tier,
                            demand_track="create_reach",
                            demand_sprint_number=i,
                        ),
                        planned_start_date=sprint_start,
                        planned_end_date=sprint_end,
                        is_demand_sprint=True,
                        demand_sprint_number=i,
                        demand_track="create_reach",
                    )
                    generated.append(cr_campaign)
                    self._create_campaign_assignments(cr_campaign, deal)
                    for module in ["create", "reach"]:
                        self.db.add(ProductModule(campaign_id=cr_campaign.id, module_name=module, enabled=True))
                    self._create_milestones(cr_campaign, template, sprint_start)
                    deliverables = self._resolve_deliverables(line=line, include_lead_total=False)
                    created_deliverables: list[Deliverable] = []
                    for d in deliverables:
                        created_deliverables.append(self._create_deliverable_with_steps(
                            deal=deal,
                            campaign=cr_campaign,
                            publication_id=publication.id,
                            deliverable_type=d,
                            sprint_number=i,
                            template=template,
                            campaign_start=sprint_start,
                            lead_target=None,
                        ))
                    self._create_csv_stage_steps_for_campaign(
                        campaign=cr_campaign,
                        line=line,
                        template=template,
                        deliverables=created_deliverables,
                    )
                    self.stage_integrity.reconcile_campaign(cr_campaign.id)
                    self._stagger_publish_steps_for_campaign(cr_campaign.id)

                if mode == "create_reach_capture":
                    cap_campaign = self._create_campaign_record(
                        deal=deal,
                        template=template,
                        brand_code=brand_code,
                        yy=yy,
                        product_code=product_code,
                        tier=line.tier,
                        campaign_type=line.product_type,
                        title=self._campaign_title(
                            client_name=client_name,
                            deal=deal,
                            campaign_type=line.product_type,
                            tier=line.tier,
                            demand_track="capture",
                            demand_sprint_number=None,
                        ),
                        planned_start_date=sow_start,
                        planned_end_date=deal.sow_end_date or (sow_start + timedelta(days=364)),
                        is_demand_sprint=False,
                        demand_sprint_number=None,
                        demand_track="capture",
                    )
                    generated.append(cap_campaign)
                    self._create_campaign_assignments(cap_campaign, deal)
                    self.db.add(ProductModule(campaign_id=cap_campaign.id, module_name="capture", enabled=True))
                    self._create_milestones(cap_campaign, template, sow_start)
                    lead_target = self._response_target_leads_for_line(line)
                    created = self._create_deliverable_with_steps(
                        deal=deal,
                        campaign=cap_campaign,
                        publication_id=publication.id,
                        deliverable_type=DeliverableType.LEAD_TOTAL,
                        sprint_number=None,
                        template=template,
                        campaign_start=sow_start,
                        lead_target=lead_target,
                    )
                    self._create_csv_stage_steps_for_campaign(
                        campaign=cap_campaign,
                        line=line,
                        template=template,
                        deliverables=[created],
                    )
                    self.stage_integrity.reconcile_campaign(cap_campaign.id)
                    self._stagger_publish_steps_for_campaign(cap_campaign.id)
                continue

            campaign = self._create_campaign_record(
                deal=deal,
                template=template,
                brand_code=brand_code,
                yy=yy,
                product_code=product_code,
                tier=line.tier,
                campaign_type=line.product_type,
                title=self._campaign_title(
                    client_name=client_name,
                    deal=deal,
                    campaign_type=line.product_type,
                    tier=line.tier,
                    demand_track=None,
                    demand_sprint_number=None,
                ),
                planned_start_date=sow_start,
                planned_end_date=sow_start + timedelta(days=89),
                is_demand_sprint=False,
                demand_sprint_number=None,
                demand_track=None,
            )
            generated.append(campaign)
            self._create_campaign_assignments(campaign, deal)
            for module in self._resolve_modules(line):
                self.db.add(ProductModule(campaign_id=campaign.id, module_name=module, enabled=True))
            self._create_milestones(campaign, template, sow_start)
            deliverables = self._resolve_deliverables(line=line, include_lead_total=True)
            created_deliverables: list[Deliverable] = []
            for d in deliverables:
                lead_target = self._response_target_leads_for_line(line) if d == DeliverableType.LEAD_TOTAL else None
                created_deliverables.append(self._create_deliverable_with_steps(
                    deal=deal,
                    campaign=campaign,
                    publication_id=publication.id,
                    deliverable_type=d,
                    sprint_number=None,
                    template=template,
                    campaign_start=sow_start,
                    lead_target=lead_target,
                ))
            self._create_csv_stage_steps_for_campaign(
                campaign=campaign,
                line=line,
                template=template,
                deliverables=created_deliverables,
            )
            self.stage_integrity.reconcile_campaign(campaign.id)
            self._stagger_publish_steps_for_campaign(campaign.id)

        return generated

    @staticmethod
    def _is_publish_step_name(name: str | None) -> bool:
        value = str(name or "").strip().lower()
        return bool(value and "publish" in value)

    def _stagger_publish_steps_for_campaign(self, campaign_id: str, *, include_completed: bool = False) -> int:
        campaign = self.db.get(Campaign, campaign_id)
        if not campaign:
            return 0
        steps = self.db.scalars(
            select(WorkflowStep).where(
                WorkflowStep.campaign_id == campaign_id,
                WorkflowStep.linked_deliverable_id.is_not(None),
            )
        ).all()
        if not steps:
            return 0
        deliverable_ids = sorted({s.linked_deliverable_id for s in steps if s.linked_deliverable_id})
        deliverables = (
            {
                d.id: d
                for d in self.db.scalars(select(Deliverable).where(Deliverable.id.in_(deliverable_ids))).all()
            }
            if deliverable_ids
            else {}
        )
        eligible: list[WorkflowStep] = []
        for step in steps:
            if not include_completed and step.actual_done is not None:
                continue
            if not self._is_publish_step_name(step.name):
                continue
            deliverable = deliverables.get(step.linked_deliverable_id or "")
            if not deliverable:
                continue
            if deliverable.deliverable_type not in {DeliverableType.ARTICLE, DeliverableType.VIDEO}:
                continue
            eligible.append(step)
        if len(eligible) <= 1:
            return 0

        anchor_candidates = [
            s.current_start or s.baseline_start
            for s in eligible
            if (s.current_start or s.baseline_start)
        ]
        anchor = min(anchor_candidates) if anchor_candidates else (
            campaign.planned_start_date or date.today()
        )
        calendar = self.timeline.calendar
        dependency_rows = self.db.scalars(
            select(WorkflowStepDependency).where(
                WorkflowStepDependency.successor_step_id.in_([s.id for s in eligible])
            )
        ).all()
        predecessor_ids = sorted({d.predecessor_step_id for d in dependency_rows})
        predecessors = (
            {
                s.id: s
                for s in self.db.scalars(select(WorkflowStep).where(WorkflowStep.id.in_(predecessor_ids))).all()
            }
            if predecessor_ids
            else {}
        )
        deps_by_successor: dict[str, list[WorkflowStep]] = {}
        for dep in dependency_rows:
            predecessor = predecessors.get(dep.predecessor_step_id)
            if not predecessor:
                continue
            deps_by_successor.setdefault(dep.successor_step_id, []).append(predecessor)

        def _step_sort_key(step: WorkflowStep) -> tuple:
            deliverable = deliverables.get(step.linked_deliverable_id or "")
            dtype_rank = 0
            if deliverable and deliverable.deliverable_type == DeliverableType.VIDEO:
                dtype_rank = 1
            start = step.current_start or step.baseline_start or anchor
            return (start, dtype_rank, step.created_at, step.id)

        staggered_count = 0
        engine = WorkflowEngineService(self.db)
        for idx, step in enumerate(sorted(eligible, key=_step_sort_key)):
            target_start = calendar.next_working_day_on_or_after(anchor + timedelta(days=(7 * idx)))
            predecessors_for_step = deps_by_successor.get(step.id, [])
            if predecessors_for_step:
                predecessor_due = max(
                    (
                        p.current_due
                        or p.baseline_due
                        or p.current_start
                        or p.baseline_start
                        for p in predecessors_for_step
                    ),
                    default=target_start,
                )
                target_start = calendar.next_working_day_on_or_after(max(target_start, predecessor_due))

            duration = 1
            if step.current_start and step.current_due:
                duration = max(self.timeline.working_days_between(step.current_start, step.current_due), 1)
            elif step.baseline_start and step.baseline_due:
                duration = max(self.timeline.working_days_between(step.baseline_start, step.baseline_due), 1)
            target_due = calendar.next_working_day_on_or_after(
                calendar.add_working_days(target_start, duration)
            )
            if (
                step.current_start == target_start
                and step.current_due == target_due
                and step.baseline_start == target_start
                and step.baseline_due == target_due
            ):
                continue
            step.baseline_start = target_start
            step.current_start = target_start
            step.baseline_due = target_due
            step.current_due = target_due
            engine._recalculate_successor_chain(step)
            staggered_count += 1
        return staggered_count

    def _publication_suffix(self, publication: PublicationName | str | None) -> str:
        value = str(publication or "").strip().lower()
        if value == PublicationName.UC_TODAY.value:
            return "UC"
        if value == PublicationName.CX_TODAY.value:
            return "CX"
        if value == PublicationName.TECHTELLIGENCE.value:
            return "TT"
        return "PUB"

    def _campaign_type_label(self, campaign_type: CampaignType, demand_track: str | None = None) -> str:
        if campaign_type == CampaignType.DEMAND:
            if str(demand_track or "").strip().lower() == "capture":
                return "Demand Capture"
            return "Demand"
        if campaign_type == CampaignType.AMPLIFY:
            return "Amplify"
        if campaign_type == CampaignType.RESPONSE:
            return "Response"
        return "Display"

    def _campaign_title(
        self,
        client_name: str,
        deal: Deal,
        campaign_type: CampaignType,
        tier: str,
        demand_track: str | None,
        demand_sprint_number: int | None,
    ) -> str:
        client = (client_name or "Client").strip()
        publication_code = self._publication_suffix(deal.brand_publication)
        kind = self._campaign_type_label(campaign_type, demand_track=demand_track)
        title = f"{client} - {kind} {tier.title()} - {publication_code}"
        if campaign_type == CampaignType.DEMAND and demand_track != "capture" and demand_sprint_number:
            title = f"{client} - {kind} {tier.title()} S{demand_sprint_number} - {publication_code}"
        return title

    def _client_name_from_deal(self, deal: Deal) -> str:
        client = self.db.get(Client, deal.client_id)
        full = (client.name if client and client.name else "Client").strip()
        first_word = full.split()[0] if full else "Client"
        return first_word

    def _create_campaign_record(
        self,
        deal: Deal,
        template: TemplateVersion,
        brand_code: str,
        yy: int,
        product_code: str,
        tier: str,
        campaign_type: CampaignType,
        title: str,
        planned_start_date: date,
        planned_end_date: date,
        is_demand_sprint: bool,
        demand_sprint_number: int | None,
        demand_track: str | None,
    ) -> Campaign:
        campaign = Campaign(
            display_id=self.public_ids.next_campaign_id(Campaign, brand_code=brand_code, yy=yy, product_code=product_code),
            deal_id=deal.id,
            template_version_id=template.id,
            campaign_type=campaign_type,
            tier=tier,
            title=title,
            status="not_started",
            planned_start_date=planned_start_date,
            planned_end_date=planned_end_date,
            is_demand_sprint=is_demand_sprint,
            demand_sprint_number=demand_sprint_number,
            demand_track=demand_track,
        )
        self.db.add(campaign)
        self.db.flush()
        return campaign

    def _brand_year_from_deal(self, deal: Deal) -> tuple[str, int]:
        match = re.match(r"^([A-Z]{4})-(\d{2})-\d{3}$", deal.display_id or "")
        if match:
            return match.group(1), int(match.group(2))
        return "DEAL", date.today().year % 100

    def _level_code(self, level: str | None, fallback_tier: str | None = None) -> str:
        value = (level or fallback_tier or "").strip().lower()
        if value.startswith("b"):
            return "B"
        if value.startswith("s"):
            return "S"
        if value.startswith("g"):
            return "G"
        return "B"

    def _campaign_product_code(self, deal: Deal, line: DealProductLine) -> str:
        first = self._product_family_code(deal, line.product_type)
        second = self._level_code(line.tier)
        opts = line.options_json or {}

        if line.product_type == CampaignType.DEMAND:
            mode = (opts.get("demand_module_mode") or "create_reach_capture").strip().lower()
            reach = self._level_code(opts.get("reach_level"), fallback_tier=line.tier)
            capture = self._level_code(opts.get("capture_level"), fallback_tier=line.tier)
            if mode == "create_only":
                tail = "XX"
            elif mode == "create_reach":
                tail = f"{reach}X"
            else:
                tail = f"{reach}{capture}"
            return f"{first}{second}{tail}"

        if line.product_type == CampaignType.RESPONSE:
            raw = opts.get("lead_volume")
            if raw is None:
                raise ValueError("Response campaigns require lead_volume in deal product line")
            leads = int(raw)
            if leads <= 0:
                raise ValueError("lead_volume must be positive for Response campaigns")
            return f"{first}{second}{str(leads)[0]}M"

        # Amplify and Display use XX by default.
        return f"{first}{second}XX"

    def _product_family_code(self, deal: Deal, campaign_type: CampaignType) -> str:
        if deal.brand_publication == PublicationName.TECHTELLIGENCE:
            return "T"
        if campaign_type == CampaignType.DEMAND:
            return "D"
        if campaign_type == CampaignType.RESPONSE:
            return "R"
        if campaign_type == CampaignType.AMPLIFY:
            return "A"
        return "B"

    def _get_or_create_template(self, name: str) -> TemplateVersion:
        template_payload = DEFAULT_TEMPLATES.get(name, {"version": 1, "steps_by_deliverable": {}})
        existing = self.db.scalar(
            select(TemplateVersion).where(TemplateVersion.name == name).order_by(TemplateVersion.version.desc())
        )
        if existing and existing.version >= int(template_payload.get("version", 1)):
            return existing

        created = TemplateVersion(
            display_id=self.public_ids.next_id(TemplateVersion, "TPL"),
            name=name,
            version=int(template_payload.get("version", 1)),
            workflow_json=template_payload,
        )
        self.db.add(created)
        self.db.flush()
        return created

    def _resolve_modules(self, line: DealProductLine) -> list[str]:
        campaign_type = line.product_type
        if campaign_type == CampaignType.DEMAND:
            mode = ((line.options_json or {}).get("demand_module_mode") or "create_reach_capture").strip().lower()
            if mode == "create_only":
                return ["create"]
            if mode == "create_reach":
                return ["create", "reach"]
            return ["create", "reach", "capture"]
        if campaign_type == CampaignType.AMPLIFY:
            return ["create", "reach"]
        if campaign_type == CampaignType.RESPONSE:
            return ["capture"]
        return ["reach"]

    def _resolve_deliverables(self, line: DealProductLine, include_lead_total: bool) -> list[DeliverableType]:
        base: list[DeliverableType] = []
        campaign_type = line.product_type
        tier = line.tier

        if campaign_type == CampaignType.DEMAND:
            base.extend([DeliverableType.ARTICLE, DeliverableType.ARTICLE, DeliverableType.VIDEO, DeliverableType.REPORT])
            if tier.lower() in {"silver", "gold"}:
                base.append(DeliverableType.ENGAGEMENT_LIST)
            if include_lead_total:
                base.append(DeliverableType.LEAD_TOTAL)
        elif campaign_type == CampaignType.AMPLIFY:
            base.extend([
                DeliverableType.ARTICLE,
                DeliverableType.VIDEO,
                DeliverableType.ARTICLE,
                DeliverableType.CLIP,
                DeliverableType.CLIP,
                DeliverableType.SHORT,
                DeliverableType.SHORT,
                DeliverableType.REPORT,
            ])
        elif campaign_type == CampaignType.RESPONSE:
            base.extend([DeliverableType.LANDING_PAGE, DeliverableType.EMAIL, DeliverableType.VIDEO, DeliverableType.LEAD_TOTAL])
        return base

    @staticmethod
    def _response_target_leads_for_line(line: DealProductLine) -> int | None:
        raw = (line.options_json or {}).get("lead_volume")
        if raw is None:
            return None
        try:
            leads = int(raw)
            return leads if leads > 0 else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _deliverable_title(deliverable_type: DeliverableType, sprint_number: int | None, lead_target: int | None = None) -> str:
        if deliverable_type == DeliverableType.LEAD_TOTAL:
            if lead_target:
                return f"Total leads ({lead_target}) due by campaign end"
            return "Total leads due by campaign end"
        if sprint_number:
            return f"{deliverable_type.value.replace('_', ' ').title()} (Sprint {sprint_number})"
        return f"{deliverable_type.value.replace('_', ' ').title()}"

    def _deliverable_due_date(self, deal: Deal, deliverable_type: DeliverableType, sprint_start: date) -> date | None:
        milestones = {name: target for name, target in self._tdtimeline_default_milestones(sprint_start)}
        if deliverable_type == DeliverableType.LEAD_TOTAL:
            if deal.sow_end_date:
                return self.timeline.calendar.next_working_day_on_or_after(deal.sow_end_date)
            fallback = milestones.get("reporting") or (sprint_start + timedelta(days=89))
            return self.timeline.calendar.next_working_day_on_or_after(fallback)

        milestone_map = {
            DeliverableType.KICKOFF_CALL: "kickoff",
            DeliverableType.INTERVIEW_CALL: "interview",
            DeliverableType.ARTICLE: "publishing",
            DeliverableType.VIDEO: "publishing",
            DeliverableType.CLIP: "publishing",
            DeliverableType.SHORT: "publishing",
            DeliverableType.REPORT: "reporting",
            DeliverableType.ENGAGEMENT_LIST: "reporting",
            DeliverableType.LANDING_PAGE: "publishing",
            DeliverableType.EMAIL: "publishing",
            DeliverableType.DISPLAY_ASSET: "promoting",
        }
        anchor = milestones.get(milestone_map.get(deliverable_type, "publishing")) or sprint_start
        return self.timeline.calendar.next_working_day_on_or_after(anchor)

    def _review_thresholds_for_deliverable(self, template: TemplateVersion, deliverable_type: DeliverableType) -> tuple[int, int]:
        config = template.workflow_json or {}
        defaults = (config.get("review_stall_threshold_days") or {})
        by_type = (config.get("review_stall_threshold_days_by_deliverable") or {}).get(deliverable_type.value, {})
        internal = int(by_type.get("internal", defaults.get("internal", 2)))
        client = int(by_type.get("client", defaults.get("client", 3)))
        return max(internal, 1), max(client, 1)

    def _create_milestones(self, campaign: Campaign, template: TemplateVersion, campaign_start: date | None) -> None:
        anchor_start = campaign_start or date.today()
        for name, target in self._tdtimeline_default_milestones(anchor_start):
            self.db.add(
                Milestone(
                    display_id=self.public_ids.next_id(Milestone, "MS"),
                    campaign_id=campaign.id,
                    name=name,
                    baseline_date=target,
                    current_target_date=target,
                )
            )

    def _tdtimeline_default_milestones(self, sprint_start: date) -> list[tuple[str, date]]:
        """
        TDTimeline defaults:
        - KO-week anchored content plan/interview windows.
        - Creation/promotion/reporting phase windows on calendar-day cadence.
        - Writing/review/publish handoffs on working-day cadence.
        """
        timeline_defaults = self.ops_defaults.get("timeline_defaults", {})
        interview_weeks_after_ko = int(timeline_defaults.get("interview_weeks_after_ko", 2))
        writing_days = int(timeline_defaults.get("writing_working_days", 8))
        internal_review_days = int(timeline_defaults.get("internal_review_working_days", 2))
        client_review_days = int(timeline_defaults.get("client_review_working_days", 5))
        publish_after_client_days = int(timeline_defaults.get("publish_after_client_review_working_days", 1))
        promotion_duration_days = int(timeline_defaults.get("promotion_duration_calendar_days", 44))
        reporting_duration_days = int(timeline_defaults.get("reporting_duration_calendar_days", 14))

        ko = self._tdtimeline_working_day_on_or_after(sprint_start)
        week_1_start = self._next_monday_after_ko_week(ko)
        week_1_end = week_1_start + timedelta(days=6)
        interview_week_end = week_1_start + timedelta(days=max((7 * interview_weeks_after_ko) - 1, 0))

        content_plan = self._tdtimeline_working_day_on_or_after(week_1_end)
        interview_anchor = interview_week_end if interview_week_end > content_plan else (content_plan + timedelta(days=1))
        interview = self._tdtimeline_working_day_on_or_after(interview_anchor)
        writing = self._tdtimeline_add_working_days(interview, writing_days)
        internal_review = self._tdtimeline_add_working_days(writing, internal_review_days)
        client_review = self._tdtimeline_add_working_days(internal_review, client_review_days)
        publishing = self._tdtimeline_add_working_days(client_review, publish_after_client_days)

        production_end = ko + timedelta(days=29)
        promotion_start = production_end + timedelta(days=1)
        promotion_end = promotion_start + timedelta(days=promotion_duration_days)
        reporting_start = promotion_end + timedelta(days=1)
        reporting_end = reporting_start + timedelta(days=reporting_duration_days)

        promoting = self._tdtimeline_working_day_on_or_after(promotion_end)
        reporting = self._tdtimeline_working_day_on_or_after(reporting_end)

        return [
            ("kickoff", ko),
            ("content_plan", content_plan),
            ("interview", interview),
            ("writing", writing),
            ("internal_review", internal_review),
            ("client_review", client_review),
            ("publishing", publishing),
            ("promoting", promoting),
            ("reporting", reporting),
        ]

    def _next_monday_after_ko_week(self, ko_date: date) -> date:
        week_start = self._week_start_monday(ko_date)
        return week_start + timedelta(days=7)

    @staticmethod
    def _week_start_monday(d: date) -> date:
        return d - timedelta(days=d.weekday())

    def _tdtimeline_working_day_on_or_after(self, d: date) -> date:
        current = d
        while not self._is_tdtimeline_working_day(current):
            current += timedelta(days=1)
        return current

    def _tdtimeline_add_working_days(self, start: date, days: int) -> date:
        if days < 0:
            raise ValueError("days must be >= 0")
        current = start
        remaining = days
        while remaining > 0:
            current += timedelta(days=1)
            if self._is_tdtimeline_working_day(current):
                remaining -= 1
        return current

    def _is_tdtimeline_working_day(self, d: date) -> bool:
        # Align with TDTimeline planner assumptions:
        # - configured working week and UK holidays
        # - Christmas shutdown: Dec 27-31 as non-working
        if not self.timeline.calendar.is_working_day(d):
            return False
        if d.month == 12 and 27 <= d.day <= 31:
            return False
        return True

    def _create_steps_from_definitions(self, deliverable: Deliverable, steps: list[dict]) -> None:
        planned_start = self._planned_start_anchor_for_deliverable(deliverable)
        required_stage_names = {
            str((step.get("stage") or deliverable.stage.value or "production")).strip().lower()
            for step in steps
        }
        stage_map = (
            self.stage_integrity.stage_ids_for_campaign(deliverable.campaign_id, required_stage_names)
            if deliverable.campaign_id
            else {}
        )
        previous_step_id: str | None = None
        for idx, step in enumerate(steps):
            _, due = self.timeline.plan_step_window(planned_start, step.get("duration_days", 1))
            planned_hours = self._resolve_planned_hours(step)
            owner_role = self._enforced_owner_role(step_name=str(step.get("name") or ""), default_role=RoleName(step["owner_role"]))
            owner_user_id = self._find_assigned_user_for_role(deliverable.campaign_id, owner_role)
            step_kind = WorkflowStepKind(str(step.get("step_kind") or "task"))
            stage_key = (step.get("stage") or deliverable.stage.value or "production").strip().lower()
            workflow_step = WorkflowStep(
                display_id=self.public_ids.next_id(WorkflowStep, "STEP"),
                campaign_id=deliverable.campaign_id,
                stage_id=stage_map.get(stage_key),
                linked_deliverable_id=deliverable.id,
                deliverable_id=None,
                stage_name=stage_key,
                name=step["name"],
                step_kind=step_kind,
                owner_role=owner_role,
                planned_hours=planned_hours,
                planned_hours_baseline=planned_hours,
                baseline_start=planned_start,
                baseline_due=due,
                current_start=planned_start,
                current_due=due,
                stuck_threshold_days=2 if idx < 2 else 3,
                next_owner_user_id=owner_user_id,
                waiting_on_type=None if idx == 0 else WaitingOnType.DEPENDENCY,
            )
            self.db.add(workflow_step)
            self.db.flush()
            self.db.add(
                WorkflowStepEffort(
                    display_id=self.public_ids.next_id(WorkflowStepEffort, "EFF"),
                    workflow_step_id=workflow_step.id,
                    role_name=owner_role,
                    hours=planned_hours,
                    assigned_user_id=owner_user_id,
                )
            )

            if previous_step_id:
                self.db.add(
                    WorkflowStepDependency(
                        display_id=self.public_ids.next_id(WorkflowStepDependency, "DEP"),
                        predecessor_step_id=previous_step_id,
                        successor_step_id=workflow_step.id,
                        dependency_type="finish_to_start",
                    )
                )
            previous_step_id = workflow_step.id
            planned_start = due

    def _create_campaign_steps_from_definitions(self, campaign: Campaign, sprint_number: int | None, steps: list[dict]) -> None:
        if not steps:
            return
        planned_start = self._planned_start_anchor_for_campaign(campaign)
        stage_map = self.stage_integrity.stage_ids_for_campaign(
            campaign.id,
            {
                str(step.get("stage") or "planning").strip().lower()
                for step in steps
            },
        )
        previous_step_id: str | None = None
        for idx, step in enumerate(steps):
            _, due = self.timeline.plan_step_window(planned_start, int(step.get("duration_days", 1)))
            name = str(step.get("name") or "").strip()
            if name.lower() == "sprint briefing call" and sprint_number == 1:
                name = "Kick-off call"
            owner_role = self._enforced_owner_role(step_name=name, default_role=RoleName(str(step["owner_role"])))
            owner_user_id = self._find_assigned_user_for_role(campaign.id, owner_role)
            step_kind = WorkflowStepKind(str(step.get("step_kind") or "task"))
            planned_hours = self._resolve_planned_hours(step)
            stage_key = str(step.get("stage") or "planning").strip().lower()
            workflow_step = WorkflowStep(
                display_id=self.public_ids.next_id(WorkflowStep, "STEP"),
                campaign_id=campaign.id,
                stage_id=stage_map.get(stage_key),
                linked_deliverable_id=None,
                deliverable_id=None,
                stage_name=stage_key,
                name=name,
                step_kind=step_kind,
                owner_role=owner_role,
                planned_hours=planned_hours,
                planned_hours_baseline=planned_hours,
                baseline_start=planned_start,
                baseline_due=due,
                current_start=planned_start,
                current_due=due,
                stuck_threshold_days=2 if idx < 2 else 3,
                next_owner_user_id=owner_user_id,
                waiting_on_type=None if idx == 0 else WaitingOnType.DEPENDENCY,
            )
            self.db.add(workflow_step)
            self.db.flush()
            self.db.add(
                WorkflowStepEffort(
                    display_id=self.public_ids.next_id(WorkflowStepEffort, "EFF"),
                    workflow_step_id=workflow_step.id,
                    role_name=owner_role,
                    hours=planned_hours,
                    assigned_user_id=owner_user_id,
                )
            )
            if previous_step_id:
                self.db.add(
                    WorkflowStepDependency(
                        display_id=self.public_ids.next_id(WorkflowStepDependency, "DEP"),
                        predecessor_step_id=previous_step_id,
                        successor_step_id=workflow_step.id,
                        dependency_type="finish_to_start",
                    )
                )
            previous_step_id = workflow_step.id
            planned_start = due

    @staticmethod
    def _enforced_owner_role(step_name: str, default_role: RoleName) -> RoleName:
        name = str(step_name or "").strip().lower()
        forced_cc_names = {
            "create content plan",
            "interview call",
            "run interview",
            "video brief for design",
            "production",
        }
        if name in forced_cc_names:
            return RoleName.CC
        return default_role

    def _planned_start_anchor_for_campaign(self, campaign: Campaign) -> date:
        milestones = self.db.scalars(select(Milestone).where(Milestone.campaign_id == campaign.id)).all()
        kickoff = next((m for m in milestones if m.name == "kickoff"), None)
        if kickoff:
            target = kickoff.current_target_date or kickoff.baseline_date
            if target:
                return target
        return date.today()

    def _planned_start_anchor_for_deliverable(self, deliverable: Deliverable) -> date:
        campaign = self.db.get(Campaign, deliverable.campaign_id) if deliverable.campaign_id else None
        if not campaign:
            return date.today()

        milestone_dates: dict[str, date] = {}
        milestones = self.db.scalars(select(Milestone).where(Milestone.campaign_id == campaign.id)).all()
        for m in milestones:
            target = m.current_target_date or m.baseline_date
            if target:
                milestone_dates[m.name] = target

        anchor_name = self._anchor_milestone_name_for_deliverable_type(deliverable.deliverable_type)
        return milestone_dates.get(anchor_name) or date.today()

    @staticmethod
    def _anchor_milestone_name_for_deliverable_type(deliverable_type: DeliverableType) -> str:
        if deliverable_type == DeliverableType.KICKOFF_CALL:
            return "kickoff"
        if deliverable_type == DeliverableType.INTERVIEW_CALL:
            return "interview"
        if deliverable_type in {
            DeliverableType.ARTICLE,
            DeliverableType.VIDEO,
            DeliverableType.CLIP,
            DeliverableType.SHORT,
        }:
            return "content_plan"
        if deliverable_type in {
            DeliverableType.REPORT,
            DeliverableType.ENGAGEMENT_LIST,
            DeliverableType.LEAD_TOTAL,
        }:
            return "reporting"
        if deliverable_type in {DeliverableType.LANDING_PAGE, DeliverableType.EMAIL, DeliverableType.DISPLAY_ASSET}:
            return "publishing"
        return "kickoff"

    def _resolve_planned_hours(self, step: dict) -> float:
        name = str(step.get("name", "")).strip().lower()
        owner_role = str(step.get("owner_role", "")).strip().lower()
        defaults = (self.ops_defaults.get("content_workload_hours") or {})

        if name == "cc prep for ko/planning":
            return float(defaults.get("ko_prep_hours", step.get("planned_hours", 0.0)))
        if name == "background research":
            return float(defaults.get("ko_prep_hours", step.get("planned_hours", 0.0)))
        if name == "create content plan":
            return float(defaults.get("content_plan_hours", step.get("planned_hours", 0.0)))
        if name == "run interview" and owner_role == RoleName.CC.value:
            return float(defaults.get("interview_hours", step.get("planned_hours", 0.0)))
        if name == "interview call":
            return float(defaults.get("interview_hours", step.get("planned_hours", 0.0)))
        if name == "draft article":
            return float(defaults.get("article_drafting_hours", step.get("planned_hours", 0.0)))
        if name == "video brief for design":
            return float(defaults.get("video_brief_hours", step.get("planned_hours", 0.0)))
        if name == "amends reserve":
            return float(defaults.get("amends_reserve_hours", step.get("planned_hours", 0.0)))
        return float(step.get("planned_hours", 0.0))

    def _resolve_sprint_step_definitions(self, template: TemplateVersion, deliverables: list[DeliverableType]) -> list[dict]:
        steps_by_sprint = (template.workflow_json or {}).get("steps_by_sprint_phase", {})
        if "planning" in steps_by_sprint:
            return list(steps_by_sprint.get("planning", []))
        # Backward compatibility with legacy templates.
        steps_by_sprint_legacy = (template.workflow_json or {}).get("steps_by_sprint", {})
        content_types = {
            DeliverableType.ARTICLE,
            DeliverableType.VIDEO,
            DeliverableType.CLIP,
            DeliverableType.SHORT,
        }
        has_content = any(d in content_types for d in deliverables)
        key = "content" if has_content else "non_content"
        return list(steps_by_sprint_legacy.get(key, []))

    def _create_campaign_assignments(self, campaign: Campaign, deal: Deal) -> None:
        default_cc_user_id = self._default_role_user_id(RoleName.CC)
        default_dn_user_id = self._default_role_user_id(RoleName.DN)
        default_mm_user_id = self._default_role_user_id(RoleName.MM)
        assignments: list[tuple[RoleName, str | None]] = [
            (RoleName.AM, deal.am_user_id),
            (RoleName.CM, deal.assigned_cm_user_id),
            # Test default: always assign a CC to generated campaigns.
            (RoleName.CC, deal.assigned_cc_user_id or default_cc_user_id),
            (RoleName.CCS, deal.assigned_ccs_user_id),
            (RoleName.DN, default_dn_user_id),
            (RoleName.MM, default_mm_user_id),
        ]
        for role_name, user_id in assignments:
            if user_id:
                self.db.add(CampaignAssignment(campaign_id=campaign.id, role_name=role_name, user_id=user_id))

    def _default_role_user_id(self, role_name: RoleName) -> str | None:
        role = self.db.scalar(select(Role).where(Role.name == role_name))
        if role:
            assigned = self.db.scalar(select(UserRoleAssignment).where(UserRoleAssignment.role_id == role.id))
            if assigned:
                return assigned.user_id
        email_prefix = role_name.value
        user = self.db.scalar(select(User).where(User.email.like(f"{email_prefix}@%")))
        return user.id if user else None

    def _find_assigned_user_for_role(self, campaign_id: str | None, role_name: RoleName) -> str | None:
        if not campaign_id:
            return None
        assignment = self.db.scalar(
            select(CampaignAssignment).where(
                CampaignAssignment.campaign_id == campaign_id,
                CampaignAssignment.role_name == role_name,
            )
        )
        return assignment.user_id if assignment else None

    def _create_deliverable_with_steps(
        self,
        deal: Deal,
        campaign: Campaign,
        publication_id: str,
        deliverable_type: DeliverableType,
        sprint_number: int | None,
        template: TemplateVersion,
        campaign_start: date,
        lead_target: int | None,
    ) -> Deliverable:
        internal_threshold, client_threshold = self._review_thresholds_for_deliverable(template, deliverable_type)
        default_owner_role = self._default_owner_role_for_deliverable(deliverable_type)
        owner_user_id = self._default_owner_user_for_deliverable(campaign.id, deliverable_type)
        deliverable = Deliverable(
            display_id=self.public_ids.next_id(Deliverable, "DEL"),
            campaign_id=campaign.id,
            publication_id=publication_id,
            owner_user_id=owner_user_id,
            default_owner_role=default_owner_role.value if default_owner_role else None,
            deliverable_type=deliverable_type,
            stage=self._deliverable_stage_for_type(deliverable_type),
            title=self._deliverable_title(deliverable_type, sprint_number, lead_target),
            status=DeliverableStatus.PLANNED,
            current_start=campaign_start,
            baseline_due=self._deliverable_due_date(deal, deliverable_type, campaign_start),
            current_due=self._deliverable_due_date(deal, deliverable_type, campaign_start),
            internal_review_stall_threshold_days=internal_threshold,
            client_review_stall_threshold_days=client_threshold,
        )
        self.db.add(deliverable)
        self.db.flush()
        deliverable_steps = list(
            (template.workflow_json.get("steps_by_deliverable", {}) or {}).get(deliverable.deliverable_type.value, [])
        )
        csv_steps = list((template.workflow_json or {}).get("csv_stage_steps") or [])
        if not csv_steps:
            self._create_steps_from_definitions(deliverable, deliverable_steps)
        return deliverable

    @staticmethod
    def _default_owner_role_for_deliverable(deliverable_type: DeliverableType) -> RoleName | None:
        if deliverable_type in {DeliverableType.ARTICLE, DeliverableType.VIDEO}:
            return RoleName.CC
        if deliverable_type == DeliverableType.REPORT:
            return RoleName.CM
        return None

    def _default_owner_user_for_deliverable(self, campaign_id: str, deliverable_type: DeliverableType) -> str | None:
        role = self._default_owner_role_for_deliverable(deliverable_type)
        if role:
            return self._find_assigned_user_for_role(campaign_id, role)
        return None

    @staticmethod
    def _deliverable_stage_for_type(deliverable_type: DeliverableType) -> DeliverableStage:
        if deliverable_type in {DeliverableType.REPORT, DeliverableType.ENGAGEMENT_LIST, DeliverableType.LEAD_TOTAL}:
            return DeliverableStage.REPORTING
        if deliverable_type in {DeliverableType.DISPLAY_ASSET}:
            return DeliverableStage.PROMOTION
        if deliverable_type in {DeliverableType.KICKOFF_CALL, DeliverableType.INTERVIEW_CALL}:
            return DeliverableStage.PLANNING
        return DeliverableStage.PRODUCTION

    def _create_csv_stage_steps_for_campaign(
        self,
        campaign: Campaign,
        line: DealProductLine,
        template: TemplateVersion,
        deliverables: list[Deliverable],
    ) -> None:
        rows = list((template.workflow_json or {}).get("csv_stage_steps") or [])
        if not rows:
            return

        editorial_types = {
            DeliverableType.ARTICLE,
            DeliverableType.VIDEO,
            DeliverableType.CLIP,
            DeliverableType.SHORT,
        }
        editorial_deliverables = [d for d in deliverables if d.deliverable_type in editorial_types]
        milestones = self.db.scalars(select(Milestone).where(Milestone.campaign_id == campaign.id)).all()
        milestone_map = {
            m.name: (m.current_target_date or m.baseline_date)
            for m in milestones
            if (m.current_target_date or m.baseline_date)
        }

        stage_anchor = {
            "planning": milestone_map.get("kickoff") or date.today(),
            "production": milestone_map.get("content_plan") or milestone_map.get("kickoff") or date.today(),
            "promotion": milestone_map.get("publishing") or milestone_map.get("content_plan") or date.today(),
            "reporting": milestone_map.get("reporting") or milestone_map.get("publishing") or date.today(),
        }
        has_reporting_deliverables = any(d.deliverable_type in REPORTING_DELIVERABLE_TYPES for d in deliverables)
        required_stage_names = {
            str(row.get("stage") or "production").strip().lower()
            for row in rows
            if self._csv_row_applies_to_campaign(row, campaign, line)
        }
        if not has_reporting_deliverables:
            required_stage_names.discard("reporting")
        stage_map = self.stage_integrity.stage_ids_for_campaign(campaign.id, required_stage_names)

        created_by_base: dict[str, list[tuple[WorkflowStep, Deliverable | None]]] = {}

        for row in rows:
            if not self._csv_row_applies_to_campaign(row, campaign, line):
                continue
            frequency = str(row.get("frequency") or "per_campaign")
            step_name_base = str(row.get("step_name") or "").strip()
            if not step_name_base:
                continue
            stage = str(row.get("stage") or "production").strip().lower()
            if stage == "reporting" and not has_reporting_deliverables:
                continue
            step_kind = WorkflowStepKind(str(row.get("step_kind") or "task"))
            hours_by_role = {
                str(k): float(v)
                for k, v in (row.get("hours_by_role") or {}).items()
                if float(v or 0) > 0
            }
            if not hours_by_role:
                continue

            targets: list[tuple[Deliverable | None, str]] = []
            if frequency == "per_content_piece":
                for d in editorial_deliverables:
                    if not self._csv_row_applies_to_deliverable(row, d):
                        continue
                    targets.append((d, f"{step_name_base} · {d.title}"))
            else:
                targets.append((None, step_name_base))

            for target_deliverable, step_name in targets:
                owner_role, owner_role_overridden = self._owner_role_for_csv_step(
                    campaign=campaign,
                    step_name_base=step_name_base,
                    hours_by_role=hours_by_role,
                )
                owner_user_id = self._find_assigned_user_for_role(campaign.id, owner_role)
                owner_from_allocations = (
                    None if owner_role_overridden else self._owner_user_from_role_hours(campaign.id, hours_by_role)
                )
                planned_start = stage_anchor.get(stage) or date.today()

                dep_steps: list[WorkflowStep] = []
                for dep_name in (row.get("dependencies") or []):
                    for dep_step, dep_deliverable in created_by_base.get(str(dep_name).strip(), []):
                        if target_deliverable and dep_deliverable and dep_deliverable.id != target_deliverable.id:
                            continue
                        dep_steps.append(dep_step)
                if dep_steps:
                    latest_due = max((s.current_due for s in dep_steps if s.current_due), default=planned_start)
                    planned_start = latest_due or planned_start

                duration_days = self._duration_days_for_csv_step(step_name_base, step_kind)
                _, due = self.timeline.plan_step_window(planned_start, duration_days)
                planned_hours_total = float(sum(hours_by_role.values()))
                workflow_step = WorkflowStep(
                    display_id=self.public_ids.next_id(WorkflowStep, "STEP"),
                    campaign_id=campaign.id,
                    stage_id=stage_map.get(stage),
                    linked_deliverable_id=target_deliverable.id if target_deliverable else None,
                    deliverable_id=None,
                    stage_name=stage,
                    name=step_name,
                    step_kind=step_kind,
                    owner_role=owner_role,
                    planned_hours=planned_hours_total,
                    planned_hours_baseline=planned_hours_total,
                    baseline_start=planned_start,
                    baseline_due=due,
                    current_start=planned_start,
                    current_due=due,
                    stuck_threshold_days=3 if stage in {"production", "reporting"} else 2,
                    next_owner_user_id=owner_from_allocations or owner_user_id,
                    waiting_on_type=WaitingOnType.DEPENDENCY if dep_steps else None,
                )
                self.db.add(workflow_step)
                self.db.flush()

                for role_key, hours in hours_by_role.items():
                    try:
                        role_name = RoleName(role_key)
                    except ValueError:
                        continue
                    assigned_user = self._find_assigned_user_for_role(campaign.id, role_name)
                    self.db.add(
                        WorkflowStepEffort(
                            display_id=self.public_ids.next_id(WorkflowStepEffort, "EFF"),
                            workflow_step_id=workflow_step.id,
                            role_name=role_name,
                            hours=hours,
                            assigned_user_id=assigned_user,
                        )
                    )

                for predecessor in dep_steps:
                    self.db.add(
                        WorkflowStepDependency(
                            display_id=self.public_ids.next_id(WorkflowStepDependency, "DEP"),
                            predecessor_step_id=predecessor.id,
                            successor_step_id=workflow_step.id,
                            dependency_type="finish_to_start",
                        )
                    )

                created_by_base.setdefault(step_name_base, []).append((workflow_step, target_deliverable))

    def _owner_role_for_csv_step(
        self,
        campaign: Campaign,
        step_name_base: str,
        hours_by_role: dict[str, float],
    ) -> tuple[RoleName, bool]:
        step_name = str(step_name_base or "").strip().lower()
        if step_name == "ko/planning call":
            if campaign.campaign_type in {CampaignType.AMPLIFY, CampaignType.RESPONSE}:
                return RoleName.AM, True
            if campaign.campaign_type == CampaignType.DEMAND:
                if int(campaign.demand_sprint_number or 0) == 1:
                    return RoleName.AM, True
                if int(campaign.demand_sprint_number or 0) in {2, 3, 4}:
                    return RoleName.CC, True
        if step_name in {"content plan internal review", "content internal review"}:
            return RoleName.CC, True
        if step_name == "report internal review":
            return RoleName.AM, True
        return self._owner_role_from_hours(hours_by_role), False

    @classmethod
    def _owner_role_from_hours(cls, hours_by_role: dict[str, float]) -> RoleName:
        ranking = []
        for key, val in hours_by_role.items():
            try:
                role = RoleName(key)
            except ValueError:
                continue
            ranking.append((float(val), -cls.STEP_OWNER_PRIORITY.get(role, 99), role))
        if not ranking:
            return RoleName.CM
        ranking.sort(reverse=True)
        return ranking[0][2]

    def _owner_user_from_role_hours(self, campaign_id: str, hours_by_role: dict[str, float]) -> str | None:
        assigned_hours_by_user: dict[str, float] = {}
        for role_key, hours in (hours_by_role or {}).items():
            try:
                role = RoleName(role_key)
            except ValueError:
                continue
            user_id = self._find_assigned_user_for_role(campaign_id, role)
            hrs = float(hours or 0.0)
            if not user_id or hrs <= 0:
                continue
            assigned_hours_by_user[user_id] = assigned_hours_by_user.get(user_id, 0.0) + hrs
        if not assigned_hours_by_user:
            return None
        if len(assigned_hours_by_user) == 1:
            return next(iter(assigned_hours_by_user.keys()))
        ranked = sorted(assigned_hours_by_user.items(), key=lambda item: (-item[1], item[0]))
        return ranked[0][0]

    def _duration_days_for_csv_step(self, step_name: str, step_kind: WorkflowStepKind) -> int:
        timeline_defaults = self.ops_defaults.get("timeline_defaults", {})
        low = step_name.strip().lower()
        if "draft article" in low:
            return max(1, int(timeline_defaults.get("writing_working_days", 8)))
        if step_kind == WorkflowStepKind.APPROVAL:
            if "client" in low:
                return max(1, int(timeline_defaults.get("client_review_working_days", 5)))
            return max(1, int(timeline_defaults.get("internal_review_working_days", 2)))
        if step_kind == WorkflowStepKind.CALL:
            return 1
        return 1

    def _csv_row_applies_to_campaign(self, row: dict, campaign: Campaign, line: DealProductLine) -> bool:
        applicability = row.get("applicability_by_product") or {}
        tier = str(campaign.tier or line.tier or "").strip().lower()
        if campaign.campaign_type == CampaignType.DEMAND:
            if campaign.demand_track == "capture":
                tiers = applicability.get("demand_capture") or []
                return tier in tiers
            options = line.options_json or {}
            mode = str(options.get("demand_module_mode") or "").strip().lower()
            include_create = mode in {"", "create_only", "create_reach", "create_reach_capture"}
            include_reach = mode in {"create_reach", "create_reach_capture"}

            create_tiers = applicability.get("demand_create") or []
            reach_tiers = applicability.get("demand_reach") or []
            applies_create = include_create and (tier in create_tiers)
            applies_reach = include_reach and (tier in reach_tiers)
            return applies_create or applies_reach
        if campaign.campaign_type == CampaignType.RESPONSE:
            return tier in (applicability.get("response") or [])
        if campaign.campaign_type == CampaignType.AMPLIFY:
            return tier in (applicability.get("amplify") or [])
        if campaign.campaign_type == CampaignType.DISPLAY_ONLY:
            return tier in (applicability.get("display") or [])
        return False

    @staticmethod
    def _csv_row_applies_to_deliverable(row: dict, deliverable: Deliverable) -> bool:
        """
        Guardrail for per-content-piece expansion.
        Some CSV rows (for example "Draft Article") are editorial-only but should
        still apply only to article deliverables.
        """
        step_name = str(row.get("step_name") or "").strip().lower()
        if "draft article" in step_name and deliverable.deliverable_type != DeliverableType.ARTICLE:
            return False
        return True
