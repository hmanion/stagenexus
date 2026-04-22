from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_runtime_schema(engine: Engine) -> None:
    """
    Transitional compatibility shim for pre-Alembic databases.

    This function remains intentionally for migration-window safety while environments
    are upgraded onto formal Alembic revisions. New schema evolution should be authored
    via Alembic migrations, not by extending this runtime patch path.
    """
    additions = {
        "users": [
            ("primary_team", "VARCHAR(32) NOT NULL DEFAULT 'CLIENT_SERVICES'"),
            ("editorial_subteam", "VARCHAR(8)"),
            ("seniority", "VARCHAR(16) NOT NULL DEFAULT 'STANDARD'"),
            ("app_role", "VARCHAR(16) NOT NULL DEFAULT 'USER'"),
        ],
        "campaigns": [
            ("is_demand_sprint", "BOOLEAN NOT NULL DEFAULT 0"),
            ("demand_sprint_number", "INTEGER"),
            ("demand_track", "VARCHAR(32)"),
            ("planned_start_date", "DATE"),
            ("planned_end_date", "DATE"),
            ("status_source", "VARCHAR(16) NOT NULL DEFAULT 'derived'"),
            ("status_overridden_by_user_id", "VARCHAR(36)"),
            ("status_overridden_at", "DATETIME"),
        ],
        "deliverables": [
            ("campaign_id", "VARCHAR(36)"),
            ("default_owner_role", "VARCHAR(11)"),
            ("stage", "VARCHAR(16) NOT NULL DEFAULT 'planning'"),
            ("operational_stage_status", "VARCHAR(16) NOT NULL DEFAULT 'planning'"),
            ("sequence_number", "INTEGER NOT NULL DEFAULT 1"),
            ("current_start", "DATE"),
            ("internal_review_rounds", "INTEGER NOT NULL DEFAULT 0"),
            ("client_review_rounds", "INTEGER NOT NULL DEFAULT 0"),
            ("amend_rounds", "INTEGER NOT NULL DEFAULT 0"),
        ],
        "milestones": [
            ("campaign_id", "VARCHAR(36)"),
            ("stage_id", "VARCHAR(36)"),
            ("owner_user_id", "VARCHAR(36)"),
            ("due_date", "DATE"),
            ("completion_date", "DATE"),
            ("sla_health", "VARCHAR(16) NOT NULL DEFAULT 'not_due'"),
            ("sla_health_manual_override", "BOOLEAN NOT NULL DEFAULT 0"),
            ("sla_health_overridden_by_user_id", "VARCHAR(36)"),
            ("sla_health_overridden_at", "DATETIME"),
            ("offset_days_from_campaign_start", "INTEGER"),
        ],
        "product_modules": [
            ("campaign_id", "VARCHAR(36)"),
        ],
        "workflow_steps": [
            ("campaign_id", "VARCHAR(36)"),
            ("stage_id", "VARCHAR(36)"),
            ("linked_deliverable_id", "VARCHAR(36)"),
            ("planned_hours_baseline", "REAL NOT NULL DEFAULT 0"),
            ("earliest_start_date", "DATE"),
            ("planned_work_date", "DATE"),
            ("completion_date", "DATE"),
            ("sprint_id", "VARCHAR(36)"),
            ("stage_name", "VARCHAR(32)"),
            ("step_kind", "VARCHAR(16) NOT NULL DEFAULT 'task'"),
            ("normalized_status", "VARCHAR(24) NOT NULL DEFAULT 'not_started'"),
            ("normalized_health", "VARCHAR(24) NOT NULL DEFAULT 'not_started'"),
        ],
        "stages": [
            ("status_source", "VARCHAR(16) NOT NULL DEFAULT 'derived'"),
            ("status_overridden_by_user_id", "VARCHAR(36)"),
            ("status_overridden_at", "DATETIME"),
        ],
        "capacity_ledger": [
            ("active_planned_hours", "REAL NOT NULL DEFAULT 0"),
            ("forecast_planned_hours", "REAL NOT NULL DEFAULT 0"),
        ],
    }

    with engine.begin() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        _ensure_stages_table(conn)
        for table_name, columns in additions.items():
            if table_name not in tables:
                continue
            existing = {col["name"] for col in inspector.get_columns(table_name)}
            for column_name, type_sql in columns:
                if column_name in existing:
                    continue
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {type_sql}"))

        if engine.dialect.name == "sqlite":
            _ensure_deliverables_sqlite_campaign_shape(conn)
            _ensure_milestones_sqlite_campaign_shape(conn)
            _ensure_product_modules_sqlite_campaign_shape(conn)
            if "workflow_steps" in tables:
                _ensure_workflow_steps_sqlite_parent_shape(conn)
        _backfill_campaign_direct_fields(conn)
        _backfill_stage_hierarchy(conn)
        _backfill_user_identity_fields(conn)
        _normalize_user_identity_enum_storage(conn)
        _backfill_deliverable_owner_defaults(conn)
        _backfill_milestone_canonical_fields(conn)
        _backfill_step_planned_fields(conn)
        _backfill_deliverable_sequence_and_operational_status(conn)
        _ensure_new_indexes(conn)
        _ensure_review_window_tables(conn)
        _ensure_workflow_step_efforts_table(conn)


def _ensure_workflow_steps_sqlite_parent_shape(conn) -> None:
    """
    SQLite cannot ALTER a NOT NULL FK in place.
    Rebuild workflow_steps to make deliverable_id nullable and support sprint-owned steps.
    """
    info = conn.execute(text("PRAGMA table_info(workflow_steps)")).mappings().all()
    if not info:
        return
    col_map = {str(row["name"]): row for row in info}
    deliverable_notnull = int(col_map.get("deliverable_id", {}).get("notnull", 0)) == 1
    has_step_kind = "step_kind" in col_map
    has_sprint_id = "sprint_id" in col_map
    has_campaign_id = "campaign_id" in col_map
    has_stage_id = "stage_id" in col_map
    has_linked_deliverable_id = "linked_deliverable_id" in col_map
    if not has_step_kind or not has_sprint_id:
        return
    if not deliverable_notnull and has_stage_id and has_linked_deliverable_id:
        return

    conn.execute(text("PRAGMA foreign_keys=OFF"))
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS workflow_steps_new (
                id VARCHAR(36) PRIMARY KEY,
                display_id VARCHAR(32) NOT NULL UNIQUE,
                campaign_id VARCHAR(36),
                stage_id VARCHAR(36),
                linked_deliverable_id VARCHAR(36),
                deliverable_id VARCHAR(36),
                sprint_id VARCHAR(36),
                stage_name VARCHAR(32),
                name VARCHAR(120) NOT NULL,
                step_kind VARCHAR(16) NOT NULL DEFAULT 'task',
                normalized_status VARCHAR(24) NOT NULL DEFAULT 'not_started',
                normalized_health VARCHAR(24) NOT NULL DEFAULT 'not_started',
                owner_role VARCHAR(11) NOT NULL,
                planned_hours REAL NOT NULL DEFAULT 0,
                planned_hours_baseline REAL NOT NULL DEFAULT 0,
                earliest_start_date DATE,
                planned_work_date DATE,
                completion_date DATE,
                baseline_start DATE,
                baseline_due DATE,
                current_start DATE,
                current_due DATE,
                actual_start DATETIME,
                actual_done DATETIME,
                waiting_on_type VARCHAR(10),
                waiting_on_user_id VARCHAR(36),
                waiting_since DATETIME,
                blocker_reason TEXT,
                stuck_threshold_days INTEGER NOT NULL DEFAULT 2,
                next_owner_user_id VARCHAR(36),
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                CONSTRAINT ck_workflow_step_single_parent CHECK (
                    (stage_id IS NOT NULL)
                ),
                FOREIGN KEY(campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY(stage_id) REFERENCES stages(id),
                FOREIGN KEY(linked_deliverable_id) REFERENCES deliverables(id),
                FOREIGN KEY(deliverable_id) REFERENCES deliverables(id),
                FOREIGN KEY(sprint_id) REFERENCES sprints(id),
                FOREIGN KEY(waiting_on_user_id) REFERENCES users(id),
                FOREIGN KEY(next_owner_user_id) REFERENCES users(id)
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO workflow_steps_new (
                id, display_id, campaign_id, stage_id, linked_deliverable_id, deliverable_id, sprint_id, stage_name, name, step_kind, normalized_status, normalized_health, owner_role, planned_hours,
                planned_hours_baseline, earliest_start_date, planned_work_date, completion_date, baseline_start, baseline_due, current_start, current_due,
                actual_start, actual_done, waiting_on_type, waiting_on_user_id, waiting_since,
                blocker_reason, stuck_threshold_days, next_owner_user_id, created_at, updated_at
            )
            SELECT
                ws.id,
                ws.display_id,
                ws.campaign_id,
                ws.stage_id,
                COALESCE(ws.linked_deliverable_id, ws.deliverable_id),
                ws.deliverable_id,
                ws.sprint_id,
                ws.stage_name,
                ws.name,
                COALESCE(ws.step_kind, 'task'),
                COALESCE(ws.normalized_status, CASE
                    WHEN ws.actual_done IS NOT NULL THEN 'done'
                    WHEN ws.waiting_on_type IS NOT NULL THEN
                        CASE ws.waiting_on_type
                            WHEN 'client' THEN 'blocked_client'
                            WHEN 'internal' THEN 'blocked_internal'
                            WHEN 'dependency' THEN 'blocked_dependency'
                            ELSE 'on_hold'
                        END
                    WHEN ws.actual_start IS NOT NULL THEN 'in_progress'
                    ELSE 'not_started'
                END),
                COALESCE(ws.normalized_health, 'not_started'),
                ws.owner_role,
                COALESCE(ws.planned_hours, 0),
                COALESCE(ws.planned_hours_baseline, ws.planned_hours, 0),
                COALESCE(ws.earliest_start_date, ws.current_start, ws.baseline_start),
                COALESCE(ws.planned_work_date, ws.current_start, ws.baseline_start),
                COALESCE(ws.completion_date, DATE(ws.actual_done)),
                ws.baseline_start,
                ws.baseline_due,
                ws.current_start,
                ws.current_due,
                ws.actual_start,
                ws.actual_done,
                ws.waiting_on_type,
                ws.waiting_on_user_id,
                ws.waiting_since,
                ws.blocker_reason,
                COALESCE(ws.stuck_threshold_days, 2),
                ws.next_owner_user_id,
                ws.created_at,
                ws.updated_at
            FROM workflow_steps ws
            """
        )
    )
    conn.execute(text("DROP TABLE workflow_steps"))
    conn.execute(text("ALTER TABLE workflow_steps_new RENAME TO workflow_steps"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_workflow_steps_deliverable_id ON workflow_steps(deliverable_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_workflow_steps_linked_deliverable_id ON workflow_steps(linked_deliverable_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_workflow_steps_stage_id ON workflow_steps(stage_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_workflow_steps_campaign_id ON workflow_steps(campaign_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_workflow_steps_sprint_id ON workflow_steps(sprint_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_workflow_steps_next_owner_user_id ON workflow_steps(next_owner_user_id)"))
    conn.execute(text("PRAGMA foreign_keys=ON"))


def _ensure_stages_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS stages (
                id VARCHAR(36) PRIMARY KEY,
                display_id VARCHAR(32) NOT NULL UNIQUE,
                campaign_id VARCHAR(36) NOT NULL,
                name VARCHAR(32) NOT NULL,
                status VARCHAR(24) NOT NULL DEFAULT 'not_started',
                status_source VARCHAR(16) NOT NULL DEFAULT 'derived',
                status_overridden_by_user_id VARCHAR(36),
                status_overridden_at DATETIME,
                health VARCHAR(24) NOT NULL DEFAULT 'not_started',
                baseline_start DATE,
                baseline_due DATE,
                current_start DATE,
                current_due DATE,
                actual_done DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                CONSTRAINT uq_stage_campaign_name UNIQUE (campaign_id, name),
                FOREIGN KEY(campaign_id) REFERENCES campaigns(id)
            )
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_stages_campaign_id ON stages(campaign_id)"))


def _ensure_deliverables_sqlite_campaign_shape(conn) -> None:
    info = conn.execute(text("PRAGMA table_info(deliverables)")).mappings().all()
    if not info:
        return
    col_map = {str(row["name"]): row for row in info}
    has_campaign_id = "campaign_id" in col_map
    sprint_notnull = int(col_map.get("sprint_id", {}).get("notnull", 0)) == 1
    if has_campaign_id and not sprint_notnull:
        return

    conn.execute(text("PRAGMA foreign_keys=OFF"))
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS deliverables_new (
                id VARCHAR(36) PRIMARY KEY,
                display_id VARCHAR(32) NOT NULL UNIQUE,
                campaign_id VARCHAR(36),
                sprint_id VARCHAR(36),
                publication_id VARCHAR(36) NOT NULL,
                owner_user_id VARCHAR(36),
                default_owner_role VARCHAR(11),
                deliverable_type VARCHAR(15) NOT NULL,
                status VARCHAR(24) NOT NULL,
                stage VARCHAR(16) NOT NULL DEFAULT 'planning',
                operational_stage_status VARCHAR(16) NOT NULL DEFAULT 'planning',
                sequence_number INTEGER NOT NULL DEFAULT 1,
                title VARCHAR(255) NOT NULL,
                current_start DATE,
                baseline_due DATE,
                current_due DATE,
                actual_done DATETIME,
                internal_review_stall_threshold_days INTEGER NOT NULL DEFAULT 2,
                client_review_stall_threshold_days INTEGER NOT NULL DEFAULT 3,
                awaiting_internal_review_since DATETIME,
                awaiting_client_review_since DATETIME,
                client_changes_requested_at DATETIME,
                approved_at DATETIME,
                scheduled_or_published_at DATETIME,
                ready_to_publish_by_user_id VARCHAR(36),
                ready_to_publish_at DATETIME,
                internal_review_rounds INTEGER NOT NULL DEFAULT 0,
                client_review_rounds INTEGER NOT NULL DEFAULT 0,
                amend_rounds INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY(sprint_id) REFERENCES sprints(id),
                FOREIGN KEY(publication_id) REFERENCES publications(id),
                FOREIGN KEY(owner_user_id) REFERENCES users(id),
                FOREIGN KEY(ready_to_publish_by_user_id) REFERENCES users(id)
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO deliverables_new (
                id, display_id, campaign_id, sprint_id, publication_id, owner_user_id, default_owner_role, deliverable_type, status, stage, operational_stage_status, sequence_number, title,
                current_start, baseline_due, current_due, actual_done, internal_review_stall_threshold_days, client_review_stall_threshold_days,
                awaiting_internal_review_since, awaiting_client_review_since, client_changes_requested_at, approved_at,
                scheduled_or_published_at, ready_to_publish_by_user_id, ready_to_publish_at,
                internal_review_rounds, client_review_rounds, amend_rounds, created_at, updated_at
            )
            SELECT
                d.id, d.display_id, d.campaign_id, d.sprint_id, d.publication_id, d.owner_user_id, d.default_owner_role, d.deliverable_type, d.status,
                COALESCE(d.stage, CASE
                    WHEN d.deliverable_type IN ('report','engagement_list','lead_total') THEN 'reporting'
                    WHEN d.deliverable_type IN ('display_asset') THEN 'promotion'
                    ELSE 'production'
                END),
                COALESCE(d.operational_stage_status, d.stage, 'planning'),
                COALESCE(d.sequence_number, 1),
                d.title,
                d.current_start, d.baseline_due, d.current_due, d.actual_done, d.internal_review_stall_threshold_days, d.client_review_stall_threshold_days,
                d.awaiting_internal_review_since, d.awaiting_client_review_since, d.client_changes_requested_at, d.approved_at,
                d.scheduled_or_published_at, d.ready_to_publish_by_user_id, d.ready_to_publish_at,
                COALESCE(d.internal_review_rounds, 0), COALESCE(d.client_review_rounds, 0), COALESCE(d.amend_rounds, 0),
                d.created_at, d.updated_at
            FROM deliverables d
            """
        )
    )
    conn.execute(text("DROP TABLE deliverables"))
    conn.execute(text("ALTER TABLE deliverables_new RENAME TO deliverables"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_deliverables_campaign_id ON deliverables(campaign_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_deliverables_sprint_id ON deliverables(sprint_id)"))
    conn.execute(text("PRAGMA foreign_keys=ON"))


def _ensure_milestones_sqlite_campaign_shape(conn) -> None:
    info = conn.execute(text("PRAGMA table_info(milestones)")).mappings().all()
    if not info:
        return
    col_map = {str(row["name"]): row for row in info}
    has_campaign_id = "campaign_id" in col_map
    sprint_notnull = int(col_map.get("sprint_id", {}).get("notnull", 0)) == 1
    if has_campaign_id and not sprint_notnull:
        return

    conn.execute(text("PRAGMA foreign_keys=OFF"))
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS milestones_new (
                id VARCHAR(36) PRIMARY KEY,
                display_id VARCHAR(32) NOT NULL UNIQUE,
                campaign_id VARCHAR(36),
                sprint_id VARCHAR(36),
                stage_id VARCHAR(36),
                owner_user_id VARCHAR(36),
                name VARCHAR(120) NOT NULL,
                due_date DATE,
                completion_date DATE,
                sla_health VARCHAR(16) NOT NULL DEFAULT 'not_due',
                sla_health_manual_override BOOLEAN NOT NULL DEFAULT 0,
                sla_health_overridden_by_user_id VARCHAR(36),
                sla_health_overridden_at DATETIME,
                offset_days_from_campaign_start INTEGER,
                baseline_date DATE,
                current_target_date DATE,
                achieved_at DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY(sprint_id) REFERENCES sprints(id),
                FOREIGN KEY(stage_id) REFERENCES stages(id),
                FOREIGN KEY(owner_user_id) REFERENCES users(id),
                FOREIGN KEY(sla_health_overridden_by_user_id) REFERENCES users(id)
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO milestones_new (
                id, display_id, campaign_id, sprint_id, stage_id, owner_user_id, name, due_date, completion_date, sla_health,
                sla_health_manual_override, sla_health_overridden_by_user_id, sla_health_overridden_at, offset_days_from_campaign_start,
                baseline_date, current_target_date, achieved_at, created_at, updated_at
            )
            SELECT
                m.id, m.display_id, m.campaign_id, m.sprint_id, m.stage_id, m.owner_user_id, m.name,
                COALESCE(m.due_date, m.current_target_date, m.baseline_date),
                COALESCE(m.completion_date, DATE(m.achieved_at)),
                COALESCE(m.sla_health, 'not_due'),
                COALESCE(m.sla_health_manual_override, 0),
                m.sla_health_overridden_by_user_id,
                m.sla_health_overridden_at,
                m.offset_days_from_campaign_start,
                m.baseline_date, m.current_target_date, m.achieved_at, m.created_at, m.updated_at
            FROM milestones m
            """
        )
    )
    conn.execute(text("DROP TABLE milestones"))
    conn.execute(text("ALTER TABLE milestones_new RENAME TO milestones"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_milestones_campaign_id ON milestones(campaign_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_milestones_sprint_id ON milestones(sprint_id)"))
    conn.execute(text("PRAGMA foreign_keys=ON"))


def _ensure_product_modules_sqlite_campaign_shape(conn) -> None:
    info = conn.execute(text("PRAGMA table_info(product_modules)")).mappings().all()
    if not info:
        return
    col_map = {str(row["name"]): row for row in info}
    has_campaign_id = "campaign_id" in col_map
    sprint_notnull = int(col_map.get("sprint_id", {}).get("notnull", 0)) == 1
    if has_campaign_id and not sprint_notnull:
        return

    conn.execute(text("PRAGMA foreign_keys=OFF"))
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS product_modules_new (
                id VARCHAR(36) PRIMARY KEY,
                campaign_id VARCHAR(36),
                sprint_id VARCHAR(36),
                module_name VARCHAR(32) NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY(sprint_id) REFERENCES sprints(id)
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO product_modules_new (id, campaign_id, sprint_id, module_name, enabled, created_at, updated_at)
            SELECT pm.id, pm.campaign_id, pm.sprint_id, pm.module_name, pm.enabled, pm.created_at, pm.updated_at
            FROM product_modules pm
            """
        )
    )
    conn.execute(text("DROP TABLE product_modules"))
    conn.execute(text("ALTER TABLE product_modules_new RENAME TO product_modules"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_product_modules_campaign_id ON product_modules(campaign_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_product_modules_sprint_id ON product_modules(sprint_id)"))
    conn.execute(text("PRAGMA foreign_keys=ON"))


def _ensure_review_window_tables(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS review_windows (
                id VARCHAR(36) PRIMARY KEY,
                display_id VARCHAR(32) NOT NULL UNIQUE,
                deliverable_id VARCHAR(36) NOT NULL,
                window_type VARCHAR(32) NOT NULL,
                window_start DATE NOT NULL,
                window_due DATE NOT NULL,
                completed_at DATETIME,
                status VARCHAR(16) NOT NULL DEFAULT 'open',
                round_number INTEGER NOT NULL DEFAULT 1,
                created_by_user_id VARCHAR(36),
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(deliverable_id) REFERENCES deliverables(id),
                FOREIGN KEY(created_by_user_id) REFERENCES users(id)
            )
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_review_windows_deliverable ON review_windows(deliverable_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_review_windows_status_due ON review_windows(status, window_due)"))
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS review_round_events (
                id VARCHAR(36) PRIMARY KEY,
                display_id VARCHAR(32) NOT NULL UNIQUE,
                deliverable_id VARCHAR(36) NOT NULL,
                event_type VARCHAR(64) NOT NULL,
                round_number INTEGER NOT NULL DEFAULT 1,
                event_at DATETIME NOT NULL,
                actor_user_id VARCHAR(36),
                note TEXT,
                source VARCHAR(16) NOT NULL DEFAULT 'auto',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(deliverable_id) REFERENCES deliverables(id),
                FOREIGN KEY(actor_user_id) REFERENCES users(id)
            )
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_review_round_events_deliverable ON review_round_events(deliverable_id)"))


def _ensure_workflow_step_efforts_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS workflow_step_efforts (
                id VARCHAR(36) PRIMARY KEY,
                display_id VARCHAR(32) NOT NULL UNIQUE,
                workflow_step_id VARCHAR(36) NOT NULL,
                role_name VARCHAR(17) NOT NULL,
                hours REAL NOT NULL DEFAULT 0,
                assigned_user_id VARCHAR(36),
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(workflow_step_id) REFERENCES workflow_steps(id),
                FOREIGN KEY(assigned_user_id) REFERENCES users(id),
                CONSTRAINT uq_workflow_step_effort_role UNIQUE (workflow_step_id, role_name)
            )
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_workflow_step_efforts_step ON workflow_step_efforts(workflow_step_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_workflow_step_efforts_user ON workflow_step_efforts(assigned_user_id)"))


def _backfill_campaign_direct_fields(conn) -> None:
    conn.execute(
        text(
            """
            UPDATE deliverables
            SET campaign_id = (
              SELECT s.campaign_id FROM sprints s WHERE s.id = deliverables.sprint_id
            )
            WHERE campaign_id IS NULL AND sprint_id IS NOT NULL
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE milestones
            SET campaign_id = (
              SELECT s.campaign_id FROM sprints s WHERE s.id = milestones.sprint_id
            )
            WHERE campaign_id IS NULL AND sprint_id IS NOT NULL
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE product_modules
            SET campaign_id = (
              SELECT s.campaign_id FROM sprints s WHERE s.id = product_modules.sprint_id
            )
            WHERE campaign_id IS NULL AND sprint_id IS NOT NULL
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE workflow_steps
            SET campaign_id = (
              SELECT s.campaign_id FROM sprints s WHERE s.id = workflow_steps.sprint_id
            )
            WHERE campaign_id IS NULL AND sprint_id IS NOT NULL
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE campaigns
            SET planned_start_date = (
              SELECT MIN(COALESCE(m.current_target_date, m.baseline_date))
              FROM milestones m
              WHERE m.campaign_id = campaigns.id
            )
            WHERE planned_start_date IS NULL
            """
        )
    )


def _backfill_user_identity_fields(conn) -> None:
    # Team backfill.
    conn.execute(
        text(
            """
            UPDATE users
            SET primary_team = CASE
              WHEN EXISTS (
                SELECT 1
                FROM user_role_assignments ura
                JOIN roles r ON r.id = ura.role_id
                WHERE ura.user_id = users.id AND r.name IN ('am','head_sales')
              ) THEN 'SALES'
              WHEN EXISTS (
                SELECT 1
                FROM user_role_assignments ura
                JOIN roles r ON r.id = ura.role_id
                WHERE ura.user_id = users.id AND r.name IN ('cc','ccs')
              ) THEN 'EDITORIAL'
              WHEN EXISTS (
                SELECT 1
                FROM user_role_assignments ura
                JOIN roles r ON r.id = ura.role_id
                WHERE ura.user_id = users.id AND r.name IN ('dn','mm')
              ) THEN 'MARKETING'
              WHEN EXISTS (
                SELECT 1
                FROM user_role_assignments ura
                JOIN roles r ON r.id = ura.role_id
                WHERE ura.user_id = users.id AND r.name IN ('cm','head_ops')
              ) THEN 'CLIENT_SERVICES'
              ELSE COALESCE(primary_team, 'CLIENT_SERVICES')
            END
            """
        )
    )
    # Seniority backfill.
    conn.execute(
        text(
            """
            UPDATE users
            SET seniority = CASE
              WHEN EXISTS (
                SELECT 1
                FROM user_role_assignments ura
                JOIN roles r ON r.id = ura.role_id
                WHERE ura.user_id = users.id AND r.name IN ('admin','leadership_viewer')
              ) THEN 'LEADERSHIP'
              WHEN EXISTS (
                SELECT 1
                FROM user_role_assignments ura
                JOIN roles r ON r.id = ura.role_id
                WHERE ura.user_id = users.id AND r.name IN ('head_ops','head_sales')
              ) THEN 'MANAGER'
              ELSE COALESCE(seniority, 'STANDARD')
            END
            """
        )
    )
    # App-role backfill.
    conn.execute(
        text(
            """
            UPDATE users
            SET app_role = CASE
              WHEN EXISTS (
                SELECT 1
                FROM user_role_assignments ura
                JOIN roles r ON r.id = ura.role_id
                WHERE ura.user_id = users.id AND LOWER(CAST(r.name AS TEXT)) IN ('admin', 'head_ops')
              ) THEN 'SUPERADMIN'
              ELSE COALESCE(app_role, 'USER')
            END
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE campaigns
            SET status = CASE
              WHEN LOWER(COALESCE(status, '')) IN ('draft','planned','not_started') THEN 'not_started'
              WHEN LOWER(COALESCE(status, '')) IN ('active','live','in_progress') THEN 'in_progress'
              WHEN LOWER(COALESCE(status, '')) IN ('on_hold') THEN 'on_hold'
              WHEN LOWER(COALESCE(status, '')) IN ('blocked_client') THEN 'blocked_client'
              WHEN LOWER(COALESCE(status, '')) IN ('blocked_internal') THEN 'blocked_internal'
              WHEN LOWER(COALESCE(status, '')) IN ('blocked_dependency') THEN 'blocked_dependency'
              WHEN LOWER(COALESCE(status, '')) IN ('complete','completed','done') THEN 'done'
              WHEN LOWER(COALESCE(status, '')) IN ('cancelled','canceled') THEN 'cancelled'
              ELSE 'not_started'
            END
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE campaigns
            SET planned_end_date = (
              SELECT MAX(COALESCE(m.current_target_date, m.baseline_date))
              FROM milestones m
              WHERE m.campaign_id = campaigns.id
            )
            WHERE planned_end_date IS NULL
            """
        )
    )


def _backfill_stage_hierarchy(conn) -> None:
    # Ensure baseline stage objects exist per campaign.
    canonical = ("planning", "production", "promotion")
    for stage_name in canonical:
        conn.execute(
            text(
                """
                INSERT INTO stages (id, display_id, campaign_id, name, status, health, created_at, updated_at)
                SELECT lower(hex(randomblob(16))),
                       ('STG-' || upper(substr(hex(randomblob(8)), 1, 8))),
                       c.id,
                       :stage_name,
                       'not_started',
                       'not_started',
                       CURRENT_TIMESTAMP,
                       CURRENT_TIMESTAMP
                FROM campaigns c
                WHERE NOT EXISTS (
                    SELECT 1 FROM stages s
                    WHERE s.campaign_id = c.id AND lower(s.name) = :stage_name
                )
                """
            ),
            {"stage_name": stage_name},
        )

    # Reporting stage is conditional: only when a campaign has reporting deliverables
    # or reporting-linked workflow steps.
    conn.execute(
        text(
            """
            INSERT INTO stages (id, display_id, campaign_id, name, status, health, created_at, updated_at)
            SELECT lower(hex(randomblob(16))),
                   ('STG-' || upper(substr(hex(randomblob(8)), 1, 8))),
                   c.id,
                   'reporting',
                   'not_started',
                   'not_started',
                   CURRENT_TIMESTAMP,
                   CURRENT_TIMESTAMP
            FROM campaigns c
            WHERE NOT EXISTS (
                SELECT 1 FROM stages s
                WHERE s.campaign_id = c.id AND lower(s.name) = 'reporting'
            )
              AND (
                  EXISTS (
                    SELECT 1
                    FROM deliverables d
                    WHERE d.campaign_id = c.id
                      AND lower(CAST(d.deliverable_type AS TEXT)) IN ('report','engagement_list','lead_total')
                  )
                  OR EXISTS (
                    SELECT 1
                    FROM workflow_steps ws
                    LEFT JOIN deliverables d ON d.id = COALESCE(ws.linked_deliverable_id, ws.deliverable_id)
                    WHERE ws.campaign_id = c.id
                      AND (
                        lower(COALESCE(ws.stage_name, '')) = 'reporting'
                        OR lower(COALESCE(CAST(d.deliverable_type AS TEXT), '')) IN ('report','engagement_list','lead_total')
                      )
                  )
              )
            """
        )
    )

    # Preserve existing deliverable linkage as a non-parent association.
    conn.execute(
        text(
            """
            UPDATE workflow_steps
            SET linked_deliverable_id = COALESCE(linked_deliverable_id, deliverable_id)
            WHERE linked_deliverable_id IS NULL
            """
        )
    )
    # Full cleanup: deliverable linkage lives only in linked_deliverable_id.
    conn.execute(
        text(
            """
            UPDATE workflow_steps
            SET deliverable_id = NULL
            WHERE deliverable_id IS NOT NULL
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE workflow_steps
            SET sprint_id = NULL
            WHERE sprint_id IS NOT NULL
            """
        )
    )

    # Derive stage name for steps when missing.
    conn.execute(
        text(
            """
            UPDATE workflow_steps
            SET stage_name = COALESCE(
                NULLIF(lower(stage_name), ''),
                (
                    SELECT lower(COALESCE(CAST(d.stage AS TEXT), 'production'))
                    FROM deliverables d
                    WHERE d.id = COALESCE(workflow_steps.linked_deliverable_id, workflow_steps.deliverable_id)
                ),
                CASE
                  WHEN lower(name) LIKE '%kick-off%' OR lower(name) LIKE '%briefing%' OR lower(name) LIKE '%interview%' OR lower(name) LIKE '%content plan%' THEN 'planning'
                  WHEN lower(name) LIKE '%report%' OR lower(name) LIKE '%engagement list%' OR lower(name) LIKE '%lead total%' THEN 'reporting'
                  WHEN lower(name) LIKE '%publish%' OR lower(name) LIKE '%promot%' OR lower(name) LIKE '%distribution%' THEN 'promotion'
                  ELSE 'production'
                END
            )
            WHERE stage_name IS NULL OR trim(stage_name) = ''
            """
        )
    )

    # Map every step to a stage object.
    conn.execute(
        text(
            """
            UPDATE workflow_steps
            SET stage_id = (
                SELECT s.id
                FROM stages s
                WHERE s.campaign_id = workflow_steps.campaign_id
                  AND lower(s.name) = lower(COALESCE(workflow_steps.stage_name, 'production'))
                LIMIT 1
            )
            WHERE stage_id IS NULL
              AND campaign_id IS NOT NULL
            """
        )
    )

    # Stage windows/status from child steps.
    conn.execute(
        text(
            """
            UPDATE stages
            SET baseline_start = (
                    SELECT MIN(ws.baseline_start)
                    FROM workflow_steps ws
                    WHERE ws.stage_id = stages.id
                ),
                baseline_due = (
                    SELECT MAX(ws.baseline_due)
                    FROM workflow_steps ws
                    WHERE ws.stage_id = stages.id
                ),
                current_start = (
                    SELECT MIN(ws.current_start)
                    FROM workflow_steps ws
                    WHERE ws.stage_id = stages.id
                ),
                current_due = (
                    SELECT MAX(ws.current_due)
                    FROM workflow_steps ws
                    WHERE ws.stage_id = stages.id
                ),
                actual_done = (
                    SELECT CASE
                        WHEN COUNT(*) > 0 AND COUNT(*) = SUM(CASE WHEN ws.actual_done IS NOT NULL THEN 1 ELSE 0 END)
                        THEN MAX(ws.actual_done)
                        ELSE NULL
                    END
                    FROM workflow_steps ws
                    WHERE ws.stage_id = stages.id
                ),
                status = (
                    SELECT CASE
                        WHEN COUNT(*) = 0 THEN 'not_started'
                        WHEN SUM(CASE WHEN lower(CAST(ws.normalized_status AS TEXT)) IN ('cancelled') THEN 1 ELSE 0 END) = COUNT(*) THEN 'cancelled'
                        WHEN SUM(CASE WHEN lower(CAST(ws.normalized_status AS TEXT)) IN ('done') THEN 1 ELSE 0 END) = COUNT(*) THEN 'done'
                        WHEN SUM(CASE WHEN lower(CAST(ws.normalized_status AS TEXT)) IN ('blocked_client') THEN 1 ELSE 0 END) > 0 THEN 'blocked_client'
                        WHEN SUM(CASE WHEN lower(CAST(ws.normalized_status AS TEXT)) IN ('blocked_internal') THEN 1 ELSE 0 END) > 0 THEN 'blocked_internal'
                        WHEN SUM(CASE WHEN lower(CAST(ws.normalized_status AS TEXT)) IN ('blocked_dependency') THEN 1 ELSE 0 END) > 0 THEN 'blocked_dependency'
                        WHEN SUM(CASE WHEN lower(CAST(ws.normalized_status AS TEXT)) IN ('in_progress') THEN 1 ELSE 0 END) > 0 THEN 'in_progress'
                        ELSE 'not_started'
                    END
                    FROM workflow_steps ws
                    WHERE ws.stage_id = stages.id
                ),
                health = (
                    SELECT CASE
                        WHEN COUNT(*) = 0 THEN 'not_started'
                        WHEN SUM(CASE WHEN lower(CAST(ws.normalized_health AS TEXT)) = 'off_track' THEN 1 ELSE 0 END) > 0 THEN 'off_track'
                        WHEN SUM(CASE WHEN lower(CAST(ws.normalized_health AS TEXT)) = 'at_risk' THEN 1 ELSE 0 END) > 0 THEN 'at_risk'
                        WHEN SUM(CASE WHEN lower(CAST(ws.normalized_health AS TEXT)) = 'on_track' THEN 1 ELSE 0 END) > 0 THEN 'on_track'
                        ELSE 'not_started'
                    END
                    FROM workflow_steps ws
                    WHERE ws.stage_id = stages.id
                ),
                updated_at = CURRENT_TIMESTAMP
            """
        )
    )

    # Delete empty reporting stages when campaign has no reporting work.
    conn.execute(
        text(
            """
            DELETE FROM stages
            WHERE lower(name) = 'reporting'
              AND NOT EXISTS (
                SELECT 1 FROM workflow_steps ws
                WHERE ws.stage_id = stages.id
              )
              AND NOT EXISTS (
                SELECT 1
                FROM deliverables d
                WHERE d.campaign_id = stages.campaign_id
                  AND lower(CAST(d.deliverable_type AS TEXT)) IN ('report','engagement_list','lead_total')
              )
            """
        )
    )


def _normalize_user_identity_enum_storage(conn) -> None:
    """
    Normalize identity enum columns to Enum-name storage expected by SQLAlchemy.
    Existing data may contain lowercase enum values from earlier backfills/defaults.
    """
    conn.execute(
        text(
            """
            UPDATE users
            SET primary_team = CASE LOWER(TRIM(primary_team))
              WHEN 'sales' THEN 'SALES'
              WHEN 'editorial' THEN 'EDITORIAL'
              WHEN 'marketing' THEN 'MARKETING'
              WHEN 'client_services' THEN 'CLIENT_SERVICES'
              ELSE primary_team
            END
            WHERE primary_team IS NOT NULL
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE users
            SET editorial_subteam = CASE LOWER(TRIM(COALESCE(editorial_subteam, '')))
              WHEN 'cx' THEN 'cx'
              WHEN 'uc' THEN 'uc'
              ELSE NULL
            END
            """
        )
    )


def _backfill_deliverable_owner_defaults(conn) -> None:
    """
    Apply default owner policy to existing deliverables:
    - Article/Video -> campaign CC
    - Report -> campaign CM
    """
    conn.execute(
        text(
            """
            UPDATE deliverables
            SET default_owner_role = CASE
              WHEN LOWER(CAST(deliverable_type AS TEXT)) IN ('article', 'video') THEN 'cc'
              WHEN LOWER(CAST(deliverable_type AS TEXT)) = 'report' THEN 'cm'
              ELSE default_owner_role
            END
            WHERE campaign_id IS NOT NULL
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE deliverables
            SET owner_user_id = (
              SELECT ca.user_id
              FROM campaign_assignments ca
              WHERE ca.campaign_id = deliverables.campaign_id
                AND LOWER(CAST(ca.role_name AS TEXT)) = 'cc'
              LIMIT 1
            )
            WHERE LOWER(CAST(deliverable_type AS TEXT)) IN ('article', 'video')
              AND campaign_id IS NOT NULL
              AND EXISTS (
                SELECT 1
                FROM campaign_assignments ca2
                WHERE ca2.campaign_id = deliverables.campaign_id
                  AND LOWER(CAST(ca2.role_name AS TEXT)) = 'cc'
              )
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE deliverables
            SET owner_user_id = (
              SELECT ca.user_id
              FROM campaign_assignments ca
              WHERE ca.campaign_id = deliverables.campaign_id
                AND LOWER(CAST(ca.role_name AS TEXT)) = 'cm'
              LIMIT 1
            )
            WHERE LOWER(CAST(deliverable_type AS TEXT)) = 'report'
              AND campaign_id IS NOT NULL
              AND EXISTS (
                SELECT 1
                FROM campaign_assignments ca2
                WHERE ca2.campaign_id = deliverables.campaign_id
                  AND LOWER(CAST(ca2.role_name AS TEXT)) = 'cm'
              )
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE users
            SET seniority = CASE LOWER(TRIM(seniority))
              WHEN 'standard' THEN 'STANDARD'
              WHEN 'manager' THEN 'MANAGER'
              WHEN 'leadership' THEN 'LEADERSHIP'
              ELSE seniority
            END
            WHERE seniority IS NOT NULL
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE users
            SET app_role = CASE LOWER(TRIM(app_role))
              WHEN 'user' THEN 'USER'
              WHEN 'admin' THEN 'ADMIN'
              WHEN 'superadmin' THEN 'SUPERADMIN'
              ELSE app_role
            END
            WHERE app_role IS NOT NULL
            """
        )
    )


def _backfill_milestone_canonical_fields(conn) -> None:
    conn.execute(
        text(
            """
            UPDATE milestones
            SET due_date = COALESCE(due_date, current_target_date, baseline_date)
            WHERE due_date IS NULL
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE milestones
            SET completion_date = COALESCE(completion_date, DATE(achieved_at))
            WHERE completion_date IS NULL AND achieved_at IS NOT NULL
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE milestones
            SET offset_days_from_campaign_start = (
              CASE
                WHEN c.planned_start_date IS NULL OR milestones.due_date IS NULL THEN NULL
                ELSE CAST(julianday(milestones.due_date) - julianday(c.planned_start_date) AS INTEGER)
              END
            )
            FROM campaigns c
            WHERE c.id = milestones.campaign_id
              AND offset_days_from_campaign_start IS NULL
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE milestones
            SET sla_health = CASE
              WHEN completion_date IS NOT NULL AND due_date IS NOT NULL AND completion_date <= due_date THEN 'met'
              WHEN completion_date IS NOT NULL AND due_date IS NOT NULL AND completion_date > due_date THEN 'missed'
              WHEN completion_date IS NULL AND due_date IS NOT NULL AND due_date < DATE('now') THEN 'missed'
              ELSE 'not_due'
            END
            WHERE COALESCE(sla_health_manual_override, 0) = 0
            """
        )
    )


def _backfill_step_planned_fields(conn) -> None:
    conn.execute(
        text(
            """
            UPDATE workflow_steps
            SET earliest_start_date = COALESCE(earliest_start_date, current_start, baseline_start)
            WHERE earliest_start_date IS NULL
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE workflow_steps
            SET planned_work_date = COALESCE(planned_work_date, current_start, baseline_start)
            WHERE planned_work_date IS NULL
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE workflow_steps
            SET completion_date = COALESCE(completion_date, DATE(actual_done))
            WHERE completion_date IS NULL AND actual_done IS NOT NULL
            """
        )
    )


def _backfill_deliverable_sequence_and_operational_status(conn) -> None:
    conn.execute(
        text(
            """
            WITH ranked AS (
              SELECT d.id,
                     ROW_NUMBER() OVER (
                       PARTITION BY d.campaign_id, LOWER(CAST(d.deliverable_type AS TEXT))
                       ORDER BY d.created_at, d.id
                     ) AS seq
              FROM deliverables d
            )
            UPDATE deliverables
            SET sequence_number = (
              SELECT ranked.seq FROM ranked WHERE ranked.id = deliverables.id
            )
            WHERE sequence_number IS NULL OR sequence_number < 1
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE deliverables
            SET operational_stage_status = COALESCE(operational_stage_status, stage, 'planning')
            WHERE operational_stage_status IS NULL
            """
        )
    )


def _ensure_new_indexes(conn) -> None:
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_workflow_steps_planned_work_date ON workflow_steps(planned_work_date)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_workflow_steps_earliest_start_date ON workflow_steps(earliest_start_date)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_milestones_stage_id ON milestones(stage_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_milestones_due_date ON milestones(due_date)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_deliverables_campaign_type_seq ON deliverables(campaign_id, deliverable_type, sequence_number)"))


def assert_runtime_integrity(engine: Engine) -> None:
    with engine.connect() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        if "workflow_steps" in tables:
            null_stage_steps = int(
                conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM workflow_steps
                        WHERE stage_id IS NULL
                        """
                    )
                ).scalar()
                or 0
            )
            if null_stage_steps:
                raise RuntimeError(
                    f"Integrity check failed: {null_stage_steps} workflow_steps rows have null stage_id."
                )
        if "sow_change_requests" not in tables:
            return

        malformed_count = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM sow_change_requests
                    WHERE campaign_id IS NULL OR LENGTH(campaign_id) != 36
                    """
                )
            ).scalar()
            or 0
        )
        if malformed_count:
            raise RuntimeError(
                f"Integrity check failed: {malformed_count} sow_change_requests rows have malformed campaign_id values."
            )

        orphan_count = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM sow_change_requests scr
                    LEFT JOIN campaigns c ON c.id = scr.campaign_id
                    WHERE c.id IS NULL
                    """
                )
            ).scalar()
            or 0
        )
        if orphan_count:
            raise RuntimeError(
                f"Integrity check failed: {orphan_count} sow_change_requests rows reference missing campaigns."
            )
