from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class PublicIdCounter(Base, TimestampMixin):
    __tablename__ = "public_id_counters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scope: Mapped[str] = mapped_column(String(24), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (UniqueConstraint("scope", "year", name="uq_public_id_scope_year"),)


class RoleName(enum.StrEnum):
    AM = "am"
    HEAD_OPS = "head_ops"
    CM = "cm"
    CC = "cc"
    CCS = "ccs"
    DN = "dn"
    MM = "mm"
    ADMIN = "admin"
    LEADERSHIP_VIEWER = "leadership_viewer"
    HEAD_SALES = "head_sales"
    CLIENT = "client"


class TeamName(enum.StrEnum):
    SALES = "sales"
    EDITORIAL = "editorial"
    MARKETING = "marketing"
    CLIENT_SERVICES = "client_services"


class SeniorityLevel(enum.StrEnum):
    STANDARD = "standard"
    MANAGER = "manager"
    LEADERSHIP = "leadership"


class AppAccessRole(enum.StrEnum):
    USER = "user"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class DealStatus(enum.StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    OPS_REVIEW = "ops_review"
    OPS_APPROVED = "ops_approved"
    READINESS_FAILED = "readiness_failed"
    READINESS_PASSED = "readiness_passed"
    CAMPAIGNS_GENERATED = "campaigns_generated"


class CampaignType(enum.StrEnum):
    DEMAND = "demand"
    AMPLIFY = "amplify"
    RESPONSE = "response"
    DISPLAY_ONLY = "display_only"


class PublicationName(enum.StrEnum):
    UC_TODAY = "uc_today"
    CX_TODAY = "cx_today"
    TECHTELLIGENCE = "techtelligence"


class DeliverableType(enum.StrEnum):
    KICKOFF_CALL = "kickoff_call"
    INTERVIEW_CALL = "interview_call"
    ARTICLE = "article"
    VIDEO = "video"
    CLIP = "clip"
    SHORT = "short"
    REPORT = "report"
    ENGAGEMENT_LIST = "engagement_list"
    LANDING_PAGE = "landing_page"
    EMAIL = "email"
    LEAD_TOTAL = "lead_total"
    DISPLAY_ASSET = "display_asset"


class DeliverableStatus(enum.StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    AWAITING_INTERNAL_REVIEW = "awaiting_internal_review"
    INTERNAL_REVIEW_COMPLETE = "internal_review_complete"
    AWAITING_CLIENT_REVIEW = "awaiting_client_review"
    CLIENT_CHANGES_REQUESTED = "client_changes_requested"
    APPROVED = "approved"
    READY_TO_PUBLISH = "ready_to_publish"
    SCHEDULED_OR_PUBLISHED = "scheduled_or_published"
    COMPLETE = "complete"


class WaitingOnType(enum.StrEnum):
    INTERNAL = "internal"
    CLIENT = "client"
    EXTERNAL = "external"
    DEPENDENCY = "dependency"


class WorkflowStepKind(enum.StrEnum):
    TASK = "task"
    CALL = "call"
    APPROVAL = "approval"


class GlobalHealth(enum.StrEnum):
    NOT_STARTED = "not_started"
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    OFF_TRACK = "off_track"


class GlobalStatus(enum.StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    BLOCKED_CLIENT = "blocked_client"
    BLOCKED_INTERNAL = "blocked_internal"
    BLOCKED_DEPENDENCY = "blocked_dependency"
    DONE = "done"
    CANCELLED = "cancelled"


class DeliverableStage(enum.StrEnum):
    PLANNING = "planning"
    PRODUCTION = "production"
    PROMOTION = "promotion"
    REPORTING = "reporting"


class RiskSeverity(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewWindowType(enum.StrEnum):
    INTERNAL_REVIEW = "internal_review"
    CLIENT_REVIEW = "client_review"
    AMENDS = "amends"


class ReviewWindowStatus(enum.StrEnum):
    OPEN = "open"
    COMPLETE = "complete"
    OVERDUE = "overdue"


class ReviewRoundEventType(enum.StrEnum):
    INTERNAL_ROUND_INCREMENTED = "internal_round_incremented"
    CLIENT_ROUND_INCREMENTED = "client_round_incremented"
    AMEND_ROUND_INCREMENTED = "amend_round_incremented"


class ApprovalStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_team: Mapped[TeamName] = mapped_column(Enum(TeamName), default=TeamName.CLIENT_SERVICES, nullable=False)
    seniority: Mapped[SeniorityLevel] = mapped_column(Enum(SeniorityLevel), default=SeniorityLevel.STANDARD, nullable=False)
    app_role: Mapped[AppAccessRole] = mapped_column(Enum(AppAccessRole), default=AppAccessRole.USER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[RoleName] = mapped_column(Enum(RoleName), unique=True, nullable=False)


class UserRoleAssignment(Base, TimestampMixin):
    __tablename__ = "user_role_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"), nullable=False)


class Client(Base, TimestampMixin):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_icp: Mapped[str | None] = mapped_column(Text)


class ClientContact(Base, TimestampMixin):
    __tablename__ = "client_contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))


class Deal(Base, TimestampMixin):
    __tablename__ = "deals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), nullable=False)
    am_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    brand_publication: Mapped[PublicationName] = mapped_column(Enum(PublicationName), nullable=False)
    status: Mapped[DealStatus] = mapped_column(Enum(DealStatus), default=DealStatus.DRAFT, nullable=False)
    sow_start_date: Mapped[date | None] = mapped_column(Date)
    sow_end_date: Mapped[date | None] = mapped_column(Date)
    icp: Mapped[str | None] = mapped_column(Text)
    campaign_objective: Mapped[str | None] = mapped_column(Text)
    messaging_positioning: Mapped[str | None] = mapped_column(Text)
    commercial_notes: Mapped[str | None] = mapped_column(Text)
    readiness_notes: Mapped[str | None] = mapped_column(Text)
    readiness_passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    assigned_cm_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    assigned_cc_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    assigned_ccs_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))


class DealProductLine(Base, TimestampMixin):
    __tablename__ = "deal_product_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    deal_id: Mapped[str] = mapped_column(ForeignKey("deals.id"), nullable=False)
    product_type: Mapped[CampaignType] = mapped_column(Enum(CampaignType), nullable=False)
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    options_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class DealAttachment(Base, TimestampMixin):
    __tablename__ = "deal_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    deal_id: Mapped[str] = mapped_column(ForeignKey("deals.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[PublicationName] = mapped_column(Enum(PublicationName), unique=True, nullable=False)


class TemplateVersion(Base, TimestampMixin):
    __tablename__ = "template_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    workflow_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (UniqueConstraint("name", "version", name="uq_template_name_version"),)


class OpsDefaultConfig(Base, TimestampMixin):
    __tablename__ = "ops_default_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    config_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    deal_id: Mapped[str] = mapped_column(ForeignKey("deals.id"), nullable=False)
    template_version_id: Mapped[str] = mapped_column(ForeignKey("template_versions.id"), nullable=False)
    campaign_type: Mapped[CampaignType] = mapped_column(Enum(CampaignType), nullable=False)
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="not_started", nullable=False)
    planned_start_date: Mapped[date | None] = mapped_column(Date)
    planned_end_date: Mapped[date | None] = mapped_column(Date)
    is_demand_sprint: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    demand_sprint_number: Mapped[int | None] = mapped_column(Integer)
    demand_track: Mapped[str | None] = mapped_column(String(32))


class CampaignAssignment(Base, TimestampMixin):
    __tablename__ = "campaign_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    role_name: Mapped[RoleName] = mapped_column(Enum(RoleName), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)


class Sprint(Base, TimestampMixin):
    __tablename__ = "sprints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    sprint_number: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_start: Mapped[date | None] = mapped_column(Date)
    baseline_due: Mapped[date | None] = mapped_column(Date)
    current_start: Mapped[date | None] = mapped_column(Date)
    current_due: Mapped[date | None] = mapped_column(Date)


class ProductModule(Base, TimestampMixin):
    __tablename__ = "product_modules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"))
    sprint_id: Mapped[str | None] = mapped_column(ForeignKey("sprints.id"))
    module_name: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Deliverable(Base, TimestampMixin):
    __tablename__ = "deliverables"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"))
    sprint_id: Mapped[str | None] = mapped_column(ForeignKey("sprints.id"))
    publication_id: Mapped[str] = mapped_column(ForeignKey("publications.id"), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    default_owner_role: Mapped[str | None] = mapped_column(String(11))
    deliverable_type: Mapped[DeliverableType] = mapped_column(Enum(DeliverableType), nullable=False)
    status: Mapped[DeliverableStatus] = mapped_column(Enum(DeliverableStatus), default=DeliverableStatus.PLANNED, nullable=False)
    stage: Mapped[DeliverableStage] = mapped_column(
        Enum(DeliverableStage, values_callable=lambda enum_cls: [e.value for e in enum_cls], native_enum=False),
        default=DeliverableStage.PLANNING,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    current_start: Mapped[date | None] = mapped_column(Date)
    baseline_due: Mapped[date | None] = mapped_column(Date)
    current_due: Mapped[date | None] = mapped_column(Date)
    actual_done: Mapped[datetime | None] = mapped_column(DateTime)
    internal_review_stall_threshold_days: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    client_review_stall_threshold_days: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    awaiting_internal_review_since: Mapped[datetime | None] = mapped_column(DateTime)
    awaiting_client_review_since: Mapped[datetime | None] = mapped_column(DateTime)
    client_changes_requested_at: Mapped[datetime | None] = mapped_column(DateTime)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    scheduled_or_published_at: Mapped[datetime | None] = mapped_column(DateTime)
    ready_to_publish_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    ready_to_publish_at: Mapped[datetime | None] = mapped_column(DateTime)
    internal_review_rounds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    client_review_rounds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    amend_rounds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class WorkflowStep(Base, TimestampMixin):
    __tablename__ = "workflow_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"))
    stage_id: Mapped[str] = mapped_column(ForeignKey("stages.id"), nullable=False)
    linked_deliverable_id: Mapped[str | None] = mapped_column(ForeignKey("deliverables.id"))
    # Compatibility alias during migration window: legacy column still used by older code paths.
    deliverable_id: Mapped[str | None] = mapped_column(ForeignKey("deliverables.id"))
    sprint_id: Mapped[str | None] = mapped_column(ForeignKey("sprints.id"))
    stage_name: Mapped[str | None] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    step_kind: Mapped[WorkflowStepKind] = mapped_column(
        Enum(
            WorkflowStepKind,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            native_enum=False,
        ),
        default=WorkflowStepKind.TASK,
        nullable=False,
    )
    normalized_status: Mapped[GlobalStatus] = mapped_column(
        Enum(GlobalStatus, values_callable=lambda enum_cls: [e.value for e in enum_cls], native_enum=False),
        default=GlobalStatus.NOT_STARTED,
        nullable=False,
    )
    normalized_health: Mapped[GlobalHealth] = mapped_column(
        Enum(GlobalHealth, values_callable=lambda enum_cls: [e.value for e in enum_cls], native_enum=False),
        default=GlobalHealth.NOT_STARTED,
        nullable=False,
    )
    owner_role: Mapped[RoleName] = mapped_column(Enum(RoleName), nullable=False)
    planned_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    planned_hours_baseline: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    baseline_start: Mapped[date | None] = mapped_column(Date)
    baseline_due: Mapped[date | None] = mapped_column(Date)
    current_start: Mapped[date | None] = mapped_column(Date)
    current_due: Mapped[date | None] = mapped_column(Date)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime)
    actual_done: Mapped[datetime | None] = mapped_column(DateTime)
    waiting_on_type: Mapped[WaitingOnType | None] = mapped_column(Enum(WaitingOnType))
    waiting_on_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    waiting_since: Mapped[datetime | None] = mapped_column(DateTime)
    blocker_reason: Mapped[str | None] = mapped_column(Text)
    stuck_threshold_days: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    next_owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    __table_args__ = (
        CheckConstraint(
            "(stage_id IS NOT NULL)",
            name="ck_workflow_step_single_parent",
        ),
    )


class Stage(Base, TimestampMixin):
    __tablename__ = "stages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[GlobalStatus] = mapped_column(
        Enum(GlobalStatus, values_callable=lambda enum_cls: [e.value for e in enum_cls], native_enum=False),
        default=GlobalStatus.NOT_STARTED,
        nullable=False,
    )
    health: Mapped[GlobalHealth] = mapped_column(
        Enum(GlobalHealth, values_callable=lambda enum_cls: [e.value for e in enum_cls], native_enum=False),
        default=GlobalHealth.NOT_STARTED,
        nullable=False,
    )
    baseline_start: Mapped[date | None] = mapped_column(Date)
    baseline_due: Mapped[date | None] = mapped_column(Date)
    current_start: Mapped[date | None] = mapped_column(Date)
    current_due: Mapped[date | None] = mapped_column(Date)
    actual_done: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        UniqueConstraint("campaign_id", "name", name="uq_stage_campaign_name"),
    )


class WorkflowStepDependency(Base, TimestampMixin):
    __tablename__ = "workflow_step_dependencies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    predecessor_step_id: Mapped[str] = mapped_column(ForeignKey("workflow_steps.id"), nullable=False)
    successor_step_id: Mapped[str] = mapped_column(ForeignKey("workflow_steps.id"), nullable=False)
    dependency_type: Mapped[str] = mapped_column(String(32), default="finish_to_start", nullable=False)

    __table_args__ = (
        UniqueConstraint("predecessor_step_id", "successor_step_id", name="uq_workflow_step_dependency"),
    )


class WorkflowStepEffort(Base, TimestampMixin):
    __tablename__ = "workflow_step_efforts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    workflow_step_id: Mapped[str] = mapped_column(ForeignKey("workflow_steps.id"), nullable=False)
    role_name: Mapped[RoleName] = mapped_column(Enum(RoleName), nullable=False)
    hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    assigned_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    __table_args__ = (
        UniqueConstraint("workflow_step_id", "role_name", name="uq_workflow_step_effort_role"),
    )


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    deliverable_id: Mapped[str] = mapped_column(ForeignKey("deliverables.id"), nullable=False)
    review_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewer_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    comments: Mapped[str | None] = mapped_column(Text)


class ReviewWindow(Base, TimestampMixin):
    __tablename__ = "review_windows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    deliverable_id: Mapped[str] = mapped_column(ForeignKey("deliverables.id"), nullable=False)
    window_type: Mapped[ReviewWindowType] = mapped_column(
        Enum(ReviewWindowType, values_callable=lambda enum_cls: [e.value for e in enum_cls], native_enum=False),
        nullable=False,
    )
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_due: Mapped[date] = mapped_column(Date, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[ReviewWindowStatus] = mapped_column(
        Enum(ReviewWindowStatus, values_callable=lambda enum_cls: [e.value for e in enum_cls], native_enum=False),
        default=ReviewWindowStatus.OPEN,
        nullable=False,
    )
    round_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))


class ReviewRoundEvent(Base, TimestampMixin):
    __tablename__ = "review_round_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    deliverable_id: Mapped[str] = mapped_column(ForeignKey("deliverables.id"), nullable=False)
    event_type: Mapped[ReviewRoundEventType] = mapped_column(
        Enum(ReviewRoundEventType, values_callable=lambda enum_cls: [e.value for e in enum_cls], native_enum=False),
        nullable=False,
    )
    round_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    event_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), default="auto", nullable=False)


class Milestone(Base, TimestampMixin):
    __tablename__ = "milestones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"))
    sprint_id: Mapped[str | None] = mapped_column(ForeignKey("sprints.id"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    baseline_date: Mapped[date | None] = mapped_column(Date)
    current_target_date: Mapped[date | None] = mapped_column(Date)
    achieved_at: Mapped[datetime | None] = mapped_column(DateTime)


class SystemRisk(Base, TimestampMixin):
    __tablename__ = "risks_system"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    risk_code: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[RiskSeverity] = mapped_column(Enum(RiskSeverity), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ManualRisk(Base, TimestampMixin):
    __tablename__ = "risks_manual"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    raised_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    severity: Mapped[RiskSeverity] = mapped_column(Enum(RiskSeverity), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    mitigation_owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    mitigation_due: Mapped[date | None] = mapped_column(Date)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Escalation(Base, TimestampMixin):
    __tablename__ = "escalations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    risk_type: Mapped[str] = mapped_column(String(16), nullable=False)
    risk_id: Mapped[str] = mapped_column(String(36), nullable=False)
    escalated_to_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


class BenchmarkTarget(Base, TimestampMixin):
    __tablename__ = "benchmark_targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    target_value: Mapped[float] = mapped_column(Float, nullable=False)
    period_scope: Mapped[str] = mapped_column(String(32), nullable=False)


class PerformanceResult(Base, TimestampMixin):
    __tablename__ = "performance_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    benchmark_target_id: Mapped[str] = mapped_column(ForeignKey("benchmark_targets.id"), nullable=False)
    measured_value: Mapped[float] = mapped_column(Float, nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)


class CapacityLedger(Base, TimestampMixin):
    __tablename__ = "capacity_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    role_name: Mapped[RoleName] = mapped_column(Enum(RoleName), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    capacity_hours: Mapped[float] = mapped_column(Float, nullable=False)
    planned_hours: Mapped[float] = mapped_column(Float, nullable=False)
    active_planned_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    forecast_planned_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    override_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    override_reason: Mapped[str | None] = mapped_column(Text)
    override_approved_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    override_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    override_requested_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    override_requested_at: Mapped[datetime | None] = mapped_column(DateTime)
    override_decided_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (UniqueConstraint("user_id", "role_name", "week_start", name="uq_capacity_user_role_week"),)


class SowChangeRequest(Base, TimestampMixin):
    __tablename__ = "sow_change_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    requested_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    impact_scope_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime)


class SowChangeApproval(Base, TimestampMixin):
    __tablename__ = "sow_change_approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    sow_change_request_id: Mapped[str] = mapped_column(ForeignKey("sow_change_requests.id"), nullable=False)
    approver_role: Mapped[RoleName] = mapped_column(Enum(RoleName), nullable=False)
    approver_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)


class ActivityLog(Base, TimestampMixin):
    __tablename__ = "activity_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Comment(Base, TimestampMixin):
    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)


class Note(Base, TimestampMixin):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
