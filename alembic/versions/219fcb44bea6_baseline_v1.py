"""baseline_v1

Revision ID: 219fcb44bea6
Revises: 
Create Date: 2026-04-22 12:07:56.393445

Canonical schema objects:
- Deal -> Campaign -> Stage -> WorkflowStep hierarchy
- Campaign children: Deliverable, ProductModule, Milestone
- Identity/access, client/commercial, review, risk/performance/capacity/audit tables

Transitional compatibility baggage kept intentionally:
- sprints table (legacy identity shape retained during migration window)
- sprint_id compatibility columns on deliverables/workflow_steps/milestones/product_modules
- workflow_steps.deliverable_id compatibility alias to linked_deliverable_id

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '219fcb44bea6'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('clients',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('default_icp', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ops_default_configs',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('config_key', sa.String(length=64), nullable=False),
    sa.Column('config_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('config_key')
    )
    op.create_table('public_id_counters',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('scope', sa.String(length=24), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('last_value', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('scope', 'year', name='uq_public_id_scope_year')
    )
    op.create_table('publications',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.Enum('UC_TODAY', 'CX_TODAY', 'TECHTELLIGENCE', name='publicationname'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('roles',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.Enum('AM', 'HEAD_OPS', 'CM', 'CC', 'CCS', 'DN', 'MM', 'ADMIN', 'LEADERSHIP_VIEWER', 'HEAD_SALES', 'CLIENT', name='rolename'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('template_versions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('workflow_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id'),
    sa.UniqueConstraint('name', 'version', name='uq_template_name_version')
    )
    op.create_table('users',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=False),
    sa.Column('primary_team', sa.Enum('SALES', 'EDITORIAL', 'MARKETING', 'CLIENT_SERVICES', name='teamname'), nullable=False),
    sa.Column('editorial_subteam', sa.Enum('cx', 'uc', name='editorialsubteam', native_enum=False), nullable=True),
    sa.Column('seniority', sa.Enum('STANDARD', 'MANAGER', 'LEADERSHIP', name='senioritylevel'), nullable=False),
    sa.Column('app_role', sa.Enum('USER', 'ADMIN', 'SUPERADMIN', name='appaccessrole'), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('activity_log',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('actor_user_id', sa.String(length=36), nullable=True),
    sa.Column('entity_type', sa.String(length=64), nullable=False),
    sa.Column('entity_id', sa.String(length=36), nullable=False),
    sa.Column('action', sa.String(length=120), nullable=False),
    sa.Column('meta_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('capacity_ledger',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('role_name', sa.Enum('AM', 'HEAD_OPS', 'CM', 'CC', 'CCS', 'DN', 'MM', 'ADMIN', 'LEADERSHIP_VIEWER', 'HEAD_SALES', 'CLIENT', name='rolename'), nullable=False),
    sa.Column('week_start', sa.Date(), nullable=False),
    sa.Column('capacity_hours', sa.Float(), nullable=False),
    sa.Column('planned_hours', sa.Float(), nullable=False),
    sa.Column('active_planned_hours', sa.Float(), nullable=False),
    sa.Column('forecast_planned_hours', sa.Float(), nullable=False),
    sa.Column('override_approved', sa.Boolean(), nullable=False),
    sa.Column('override_reason', sa.Text(), nullable=True),
    sa.Column('override_approved_by_user_id', sa.String(length=36), nullable=True),
    sa.Column('override_requested', sa.Boolean(), nullable=False),
    sa.Column('override_requested_by_user_id', sa.String(length=36), nullable=True),
    sa.Column('override_requested_at', sa.DateTime(), nullable=True),
    sa.Column('override_decided_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['override_approved_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['override_requested_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id'),
    sa.UniqueConstraint('user_id', 'role_name', 'week_start', name='uq_capacity_user_role_week')
    )
    op.create_table('client_contacts',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('client_id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('comments',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('entity_type', sa.String(length=64), nullable=False),
    sa.Column('entity_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('deals',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('client_id', sa.String(length=36), nullable=False),
    sa.Column('am_user_id', sa.String(length=36), nullable=False),
    sa.Column('brand_publication', sa.Enum('UC_TODAY', 'CX_TODAY', 'TECHTELLIGENCE', name='publicationname'), nullable=False),
    sa.Column('status', sa.Enum('DRAFT', 'SUBMITTED', 'OPS_REVIEW', 'OPS_APPROVED', 'READINESS_FAILED', 'READINESS_PASSED', 'CAMPAIGNS_GENERATED', name='dealstatus'), nullable=False),
    sa.Column('sow_start_date', sa.Date(), nullable=True),
    sa.Column('sow_end_date', sa.Date(), nullable=True),
    sa.Column('icp', sa.Text(), nullable=True),
    sa.Column('campaign_objective', sa.Text(), nullable=True),
    sa.Column('messaging_positioning', sa.Text(), nullable=True),
    sa.Column('commercial_notes', sa.Text(), nullable=True),
    sa.Column('readiness_notes', sa.Text(), nullable=True),
    sa.Column('readiness_passed', sa.Boolean(), nullable=False),
    sa.Column('assigned_cm_user_id', sa.String(length=36), nullable=True),
    sa.Column('assigned_cc_user_id', sa.String(length=36), nullable=True),
    sa.Column('assigned_ccs_user_id', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['am_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['assigned_cc_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['assigned_ccs_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['assigned_cm_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('escalations',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('risk_type', sa.String(length=16), nullable=False),
    sa.Column('risk_id', sa.String(length=36), nullable=False),
    sa.Column('escalated_to_user_id', sa.String(length=36), nullable=True),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['escalated_to_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('notes',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('entity_type', sa.String(length=64), nullable=False),
    sa.Column('entity_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('user_role_assignments',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('role_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('campaigns',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('deal_id', sa.String(length=36), nullable=False),
    sa.Column('template_version_id', sa.String(length=36), nullable=False),
    sa.Column('campaign_type', sa.Enum('DEMAND', 'AMPLIFY', 'RESPONSE', 'DISPLAY_ONLY', name='campaigntype'), nullable=False),
    sa.Column('tier', sa.String(length=32), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=64), nullable=False),
    sa.Column('status_source', sa.Enum('derived', 'manual', name='statussource', native_enum=False), nullable=False),
    sa.Column('status_overridden_by_user_id', sa.String(length=36), nullable=True),
    sa.Column('status_overridden_at', sa.DateTime(), nullable=True),
    sa.Column('planned_start_date', sa.Date(), nullable=True),
    sa.Column('planned_end_date', sa.Date(), nullable=True),
    sa.Column('is_demand_sprint', sa.Boolean(), nullable=False),
    sa.Column('demand_sprint_number', sa.Integer(), nullable=True),
    sa.Column('demand_track', sa.String(length=32), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['deal_id'], ['deals.id'], ),
    sa.ForeignKeyConstraint(['status_overridden_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['template_version_id'], ['template_versions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('deal_attachments',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('deal_id', sa.String(length=36), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('storage_key', sa.String(length=500), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['deal_id'], ['deals.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('deal_product_lines',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('deal_id', sa.String(length=36), nullable=False),
    sa.Column('product_type', sa.Enum('DEMAND', 'AMPLIFY', 'RESPONSE', 'DISPLAY_ONLY', name='campaigntype'), nullable=False),
    sa.Column('tier', sa.String(length=32), nullable=False),
    sa.Column('options_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['deal_id'], ['deals.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('benchmark_targets',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=False),
    sa.Column('metric_name', sa.String(length=64), nullable=False),
    sa.Column('target_value', sa.Float(), nullable=False),
    sa.Column('period_scope', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('campaign_assignments',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=False),
    sa.Column('role_name', sa.Enum('AM', 'HEAD_OPS', 'CM', 'CC', 'CCS', 'DN', 'MM', 'ADMIN', 'LEADERSHIP_VIEWER', 'HEAD_SALES', 'CLIENT', name='rolename'), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('risks_manual',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=False),
    sa.Column('raised_by_user_id', sa.String(length=36), nullable=False),
    sa.Column('severity', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='riskseverity'), nullable=False),
    sa.Column('details', sa.Text(), nullable=False),
    sa.Column('mitigation_owner_user_id', sa.String(length=36), nullable=True),
    sa.Column('mitigation_due', sa.Date(), nullable=True),
    sa.Column('is_open', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['mitigation_owner_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['raised_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('risks_system',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=False),
    sa.Column('risk_code', sa.String(length=64), nullable=False),
    sa.Column('severity', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='riskseverity'), nullable=False),
    sa.Column('details', sa.Text(), nullable=False),
    sa.Column('is_open', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('sow_change_requests',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=False),
    sa.Column('requested_by_user_id', sa.String(length=36), nullable=False),
    sa.Column('impact_scope_json', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('activated_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['requested_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('sprints',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=False),
    sa.Column('sprint_number', sa.Integer(), nullable=False),
    sa.Column('baseline_start', sa.Date(), nullable=True),
    sa.Column('baseline_due', sa.Date(), nullable=True),
    sa.Column('current_start', sa.Date(), nullable=True),
    sa.Column('current_due', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('stages',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=32), nullable=False),
    sa.Column('status', sa.Enum('not_started', 'in_progress', 'on_hold', 'blocked_client', 'blocked_internal', 'blocked_dependency', 'done', 'cancelled', name='globalstatus', native_enum=False), nullable=False),
    sa.Column('status_source', sa.Enum('derived', 'manual', name='statussource', native_enum=False), nullable=False),
    sa.Column('status_overridden_by_user_id', sa.String(length=36), nullable=True),
    sa.Column('status_overridden_at', sa.DateTime(), nullable=True),
    sa.Column('health', sa.Enum('not_started', 'on_track', 'at_risk', 'off_track', name='globalhealth', native_enum=False), nullable=False),
    sa.Column('baseline_start', sa.Date(), nullable=True),
    sa.Column('baseline_due', sa.Date(), nullable=True),
    sa.Column('current_start', sa.Date(), nullable=True),
    sa.Column('current_due', sa.Date(), nullable=True),
    sa.Column('actual_done', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['status_overridden_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('campaign_id', 'name', name='uq_stage_campaign_name'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('deliverables',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=True),
    sa.Column('sprint_id', sa.String(length=36), nullable=True),
    sa.Column('publication_id', sa.String(length=36), nullable=False),
    sa.Column('owner_user_id', sa.String(length=36), nullable=True),
    sa.Column('default_owner_role', sa.String(length=11), nullable=True),
    sa.Column('deliverable_type', sa.Enum('KICKOFF_CALL', 'INTERVIEW_CALL', 'ARTICLE', 'VIDEO', 'CLIP', 'SHORT', 'REPORT', 'ENGAGEMENT_LIST', 'LANDING_PAGE', 'EMAIL', 'LEAD_TOTAL', 'DISPLAY_ASSET', name='deliverabletype'), nullable=False),
    sa.Column('status', sa.Enum('PLANNED', 'IN_PROGRESS', 'AWAITING_INTERNAL_REVIEW', 'INTERNAL_REVIEW_COMPLETE', 'AWAITING_CLIENT_REVIEW', 'CLIENT_CHANGES_REQUESTED', 'APPROVED', 'READY_TO_PUBLISH', 'SCHEDULED_OR_PUBLISHED', 'COMPLETE', name='deliverablestatus'), nullable=False),
    sa.Column('stage', sa.Enum('planning', 'production', 'promotion', 'reporting', name='deliverablestage', native_enum=False), nullable=False),
    sa.Column('operational_stage_status', sa.Enum('planning', 'production', 'promotion', 'reporting', name='deliverablestage', native_enum=False), nullable=False),
    sa.Column('sequence_number', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('current_start', sa.Date(), nullable=True),
    sa.Column('baseline_due', sa.Date(), nullable=True),
    sa.Column('current_due', sa.Date(), nullable=True),
    sa.Column('actual_done', sa.DateTime(), nullable=True),
    sa.Column('internal_review_stall_threshold_days', sa.Integer(), nullable=False),
    sa.Column('client_review_stall_threshold_days', sa.Integer(), nullable=False),
    sa.Column('awaiting_internal_review_since', sa.DateTime(), nullable=True),
    sa.Column('awaiting_client_review_since', sa.DateTime(), nullable=True),
    sa.Column('client_changes_requested_at', sa.DateTime(), nullable=True),
    sa.Column('approved_at', sa.DateTime(), nullable=True),
    sa.Column('scheduled_or_published_at', sa.DateTime(), nullable=True),
    sa.Column('ready_to_publish_by_user_id', sa.String(length=36), nullable=True),
    sa.Column('ready_to_publish_at', sa.DateTime(), nullable=True),
    sa.Column('internal_review_rounds', sa.Integer(), nullable=False),
    sa.Column('client_review_rounds', sa.Integer(), nullable=False),
    sa.Column('amend_rounds', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['publication_id'], ['publications.id'], ),
    sa.ForeignKeyConstraint(['ready_to_publish_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['sprint_id'], ['sprints.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('milestones',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=True),
    sa.Column('sprint_id', sa.String(length=36), nullable=True),
    sa.Column('stage_id', sa.String(length=36), nullable=True),
    sa.Column('owner_user_id', sa.String(length=36), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('completion_date', sa.Date(), nullable=True),
    sa.Column('sla_health', sa.Enum('met', 'missed', 'not_due', name='milestoneslahealth', native_enum=False), nullable=False),
    sa.Column('sla_health_manual_override', sa.Boolean(), nullable=False),
    sa.Column('sla_health_overridden_by_user_id', sa.String(length=36), nullable=True),
    sa.Column('sla_health_overridden_at', sa.DateTime(), nullable=True),
    sa.Column('offset_days_from_campaign_start', sa.Integer(), nullable=True),
    sa.Column('baseline_date', sa.Date(), nullable=True),
    sa.Column('current_target_date', sa.Date(), nullable=True),
    sa.Column('achieved_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['sla_health_overridden_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['sprint_id'], ['sprints.id'], ),
    sa.ForeignKeyConstraint(['stage_id'], ['stages.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('performance_results',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('benchmark_target_id', sa.String(length=36), nullable=False),
    sa.Column('measured_value', sa.Float(), nullable=False),
    sa.Column('measured_at', sa.DateTime(), nullable=False),
    sa.Column('source', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['benchmark_target_id'], ['benchmark_targets.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('product_modules',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=True),
    sa.Column('sprint_id', sa.String(length=36), nullable=True),
    sa.Column('module_name', sa.String(length=32), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['sprint_id'], ['sprints.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('sow_change_approvals',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('sow_change_request_id', sa.String(length=36), nullable=False),
    sa.Column('approver_role', sa.Enum('AM', 'HEAD_OPS', 'CM', 'CC', 'CCS', 'DN', 'MM', 'ADMIN', 'LEADERSHIP_VIEWER', 'HEAD_SALES', 'CLIENT', name='rolename'), nullable=False),
    sa.Column('approver_user_id', sa.String(length=36), nullable=True),
    sa.Column('status', sa.Enum('PENDING', 'APPROVED', 'REJECTED', name='approvalstatus'), nullable=False),
    sa.Column('decided_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['approver_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['sow_change_request_id'], ['sow_change_requests.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('review_round_events',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('deliverable_id', sa.String(length=36), nullable=False),
    sa.Column('event_type', sa.Enum('internal_round_incremented', 'client_round_incremented', 'amend_round_incremented', name='reviewroundeventtype', native_enum=False), nullable=False),
    sa.Column('round_number', sa.Integer(), nullable=False),
    sa.Column('event_at', sa.DateTime(), nullable=False),
    sa.Column('actor_user_id', sa.String(length=36), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deliverable_id'], ['deliverables.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('review_windows',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('deliverable_id', sa.String(length=36), nullable=False),
    sa.Column('window_type', sa.Enum('internal_review', 'client_review', 'amends', name='reviewwindowtype', native_enum=False), nullable=False),
    sa.Column('window_start', sa.Date(), nullable=False),
    sa.Column('window_due', sa.Date(), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('status', sa.Enum('open', 'complete', 'overdue', name='reviewwindowstatus', native_enum=False), nullable=False),
    sa.Column('round_number', sa.Integer(), nullable=False),
    sa.Column('created_by_user_id', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['deliverable_id'], ['deliverables.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('reviews',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('deliverable_id', sa.String(length=36), nullable=False),
    sa.Column('review_type', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('reviewer_user_id', sa.String(length=36), nullable=True),
    sa.Column('comments', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['deliverable_id'], ['deliverables.id'], ),
    sa.ForeignKeyConstraint(['reviewer_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('workflow_steps',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=True),
    sa.Column('stage_id', sa.String(length=36), nullable=False),
    sa.Column('linked_deliverable_id', sa.String(length=36), nullable=True),
    sa.Column('deliverable_id', sa.String(length=36), nullable=True),
    sa.Column('sprint_id', sa.String(length=36), nullable=True),
    sa.Column('stage_name', sa.String(length=32), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('step_kind', sa.Enum('task', 'call', 'approval', name='workflowstepkind', native_enum=False), nullable=False),
    sa.Column('normalized_status', sa.Enum('not_started', 'in_progress', 'on_hold', 'blocked_client', 'blocked_internal', 'blocked_dependency', 'done', 'cancelled', name='globalstatus', native_enum=False), nullable=False),
    sa.Column('normalized_health', sa.Enum('not_started', 'on_track', 'at_risk', 'off_track', name='globalhealth', native_enum=False), nullable=False),
    sa.Column('owner_role', sa.Enum('AM', 'HEAD_OPS', 'CM', 'CC', 'CCS', 'DN', 'MM', 'ADMIN', 'LEADERSHIP_VIEWER', 'HEAD_SALES', 'CLIENT', name='rolename'), nullable=False),
    sa.Column('planned_hours', sa.Float(), nullable=False),
    sa.Column('planned_hours_baseline', sa.Float(), nullable=False),
    sa.Column('earliest_start_date', sa.Date(), nullable=True),
    sa.Column('planned_work_date', sa.Date(), nullable=True),
    sa.Column('baseline_start', sa.Date(), nullable=True),
    sa.Column('baseline_due', sa.Date(), nullable=True),
    sa.Column('current_start', sa.Date(), nullable=True),
    sa.Column('current_due', sa.Date(), nullable=True),
    sa.Column('actual_start', sa.DateTime(), nullable=True),
    sa.Column('actual_done', sa.DateTime(), nullable=True),
    sa.Column('waiting_on_type', sa.Enum('INTERNAL', 'CLIENT', 'EXTERNAL', 'DEPENDENCY', name='waitingontype'), nullable=True),
    sa.Column('waiting_on_user_id', sa.String(length=36), nullable=True),
    sa.Column('waiting_since', sa.DateTime(), nullable=True),
    sa.Column('blocker_reason', sa.Text(), nullable=True),
    sa.Column('stuck_threshold_days', sa.Integer(), nullable=False),
    sa.Column('next_owner_user_id', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint('(stage_id IS NOT NULL)', name='ck_workflow_step_single_parent'),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ),
    sa.ForeignKeyConstraint(['deliverable_id'], ['deliverables.id'], ),
    sa.ForeignKeyConstraint(['linked_deliverable_id'], ['deliverables.id'], ),
    sa.ForeignKeyConstraint(['next_owner_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['sprint_id'], ['sprints.id'], ),
    sa.ForeignKeyConstraint(['stage_id'], ['stages.id'], ),
    sa.ForeignKeyConstraint(['waiting_on_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id')
    )
    op.create_table('workflow_step_dependencies',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('predecessor_step_id', sa.String(length=36), nullable=False),
    sa.Column('successor_step_id', sa.String(length=36), nullable=False),
    sa.Column('dependency_type', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['predecessor_step_id'], ['workflow_steps.id'], ),
    sa.ForeignKeyConstraint(['successor_step_id'], ['workflow_steps.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id'),
    sa.UniqueConstraint('predecessor_step_id', 'successor_step_id', name='uq_workflow_step_dependency')
    )
    op.create_table('workflow_step_efforts',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('display_id', sa.String(length=32), nullable=False),
    sa.Column('workflow_step_id', sa.String(length=36), nullable=False),
    sa.Column('role_name', sa.Enum('AM', 'HEAD_OPS', 'CM', 'CC', 'CCS', 'DN', 'MM', 'ADMIN', 'LEADERSHIP_VIEWER', 'HEAD_SALES', 'CLIENT', name='rolename'), nullable=False),
    sa.Column('hours', sa.Float(), nullable=False),
    sa.Column('assigned_user_id', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['assigned_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['workflow_step_id'], ['workflow_steps.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('display_id'),
    sa.UniqueConstraint('workflow_step_id', 'role_name', name='uq_workflow_step_effort_role')
    )
    op.create_index('ix_stages_campaign_id', 'stages', ['campaign_id'], unique=False)
    op.create_index('ix_deliverables_campaign_id', 'deliverables', ['campaign_id'], unique=False)
    op.create_index('ix_deliverables_sprint_id', 'deliverables', ['sprint_id'], unique=False)
    op.create_index('ix_deliverables_campaign_type_seq', 'deliverables', ['campaign_id', 'deliverable_type', 'sequence_number'], unique=False)
    op.create_index('ix_milestones_campaign_id', 'milestones', ['campaign_id'], unique=False)
    op.create_index('ix_milestones_sprint_id', 'milestones', ['sprint_id'], unique=False)
    op.create_index('ix_milestones_stage_id', 'milestones', ['stage_id'], unique=False)
    op.create_index('ix_milestones_due_date', 'milestones', ['due_date'], unique=False)
    op.create_index('ix_product_modules_campaign_id', 'product_modules', ['campaign_id'], unique=False)
    op.create_index('ix_product_modules_sprint_id', 'product_modules', ['sprint_id'], unique=False)
    op.create_index('ix_review_windows_deliverable', 'review_windows', ['deliverable_id'], unique=False)
    op.create_index('ix_review_windows_status_due', 'review_windows', ['status', 'window_due'], unique=False)
    op.create_index('ix_review_round_events_deliverable', 'review_round_events', ['deliverable_id'], unique=False)
    op.create_index('ix_workflow_steps_deliverable_id', 'workflow_steps', ['deliverable_id'], unique=False)
    op.create_index('ix_workflow_steps_linked_deliverable_id', 'workflow_steps', ['linked_deliverable_id'], unique=False)
    op.create_index('ix_workflow_steps_stage_id', 'workflow_steps', ['stage_id'], unique=False)
    op.create_index('ix_workflow_steps_campaign_id', 'workflow_steps', ['campaign_id'], unique=False)
    op.create_index('ix_workflow_steps_sprint_id', 'workflow_steps', ['sprint_id'], unique=False)
    op.create_index('ix_workflow_steps_next_owner_user_id', 'workflow_steps', ['next_owner_user_id'], unique=False)
    op.create_index('ix_workflow_steps_planned_work_date', 'workflow_steps', ['planned_work_date'], unique=False)
    op.create_index('ix_workflow_steps_earliest_start_date', 'workflow_steps', ['earliest_start_date'], unique=False)
    op.create_index('ix_workflow_step_efforts_step', 'workflow_step_efforts', ['workflow_step_id'], unique=False)
    op.create_index('ix_workflow_step_efforts_user', 'workflow_step_efforts', ['assigned_user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_workflow_step_efforts_user', table_name='workflow_step_efforts')
    op.drop_index('ix_workflow_step_efforts_step', table_name='workflow_step_efforts')
    op.drop_index('ix_workflow_steps_earliest_start_date', table_name='workflow_steps')
    op.drop_index('ix_workflow_steps_planned_work_date', table_name='workflow_steps')
    op.drop_index('ix_workflow_steps_next_owner_user_id', table_name='workflow_steps')
    op.drop_index('ix_workflow_steps_sprint_id', table_name='workflow_steps')
    op.drop_index('ix_workflow_steps_campaign_id', table_name='workflow_steps')
    op.drop_index('ix_workflow_steps_stage_id', table_name='workflow_steps')
    op.drop_index('ix_workflow_steps_linked_deliverable_id', table_name='workflow_steps')
    op.drop_index('ix_workflow_steps_deliverable_id', table_name='workflow_steps')
    op.drop_index('ix_review_round_events_deliverable', table_name='review_round_events')
    op.drop_index('ix_review_windows_status_due', table_name='review_windows')
    op.drop_index('ix_review_windows_deliverable', table_name='review_windows')
    op.drop_index('ix_product_modules_sprint_id', table_name='product_modules')
    op.drop_index('ix_product_modules_campaign_id', table_name='product_modules')
    op.drop_index('ix_milestones_due_date', table_name='milestones')
    op.drop_index('ix_milestones_stage_id', table_name='milestones')
    op.drop_index('ix_milestones_sprint_id', table_name='milestones')
    op.drop_index('ix_milestones_campaign_id', table_name='milestones')
    op.drop_index('ix_deliverables_campaign_type_seq', table_name='deliverables')
    op.drop_index('ix_deliverables_sprint_id', table_name='deliverables')
    op.drop_index('ix_deliverables_campaign_id', table_name='deliverables')
    op.drop_index('ix_stages_campaign_id', table_name='stages')
    op.drop_table('workflow_step_efforts')
    op.drop_table('workflow_step_dependencies')
    op.drop_table('workflow_steps')
    op.drop_table('reviews')
    op.drop_table('review_windows')
    op.drop_table('review_round_events')
    op.drop_table('sow_change_approvals')
    op.drop_table('product_modules')
    op.drop_table('performance_results')
    op.drop_table('milestones')
    op.drop_table('deliverables')
    op.drop_table('stages')
    op.drop_table('sprints')
    op.drop_table('sow_change_requests')
    op.drop_table('risks_system')
    op.drop_table('risks_manual')
    op.drop_table('campaign_assignments')
    op.drop_table('benchmark_targets')
    op.drop_table('deal_product_lines')
    op.drop_table('deal_attachments')
    op.drop_table('campaigns')
    op.drop_table('user_role_assignments')
    op.drop_table('notes')
    op.drop_table('escalations')
    op.drop_table('deals')
    op.drop_table('comments')
    op.drop_table('client_contacts')
    op.drop_table('capacity_ledger')
    op.drop_table('activity_log')
    op.drop_table('users')
    op.drop_table('template_versions')
    op.drop_table('roles')
    op.drop_table('publications')
    op.drop_table('public_id_counters')
    op.drop_table('ops_default_configs')
    op.drop_table('clients')
