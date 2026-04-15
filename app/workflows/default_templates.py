from __future__ import annotations

from app.models.domain import DeliverableType, RoleName
from app.core.config import settings
from app.workflows.csv_stage_steps import load_stage_steps_from_csv


AMENDS_RESERVE_STEP_NAME = "Amends reserve"
CSV_STAGE_STEPS = load_stage_steps_from_csv(settings.stage_steps_csv_path)


def _kickoff_steps(include_content_planning: bool) -> list[dict]:
    steps = [
        {
            "name": "Schedule kick-off",
            "owner_role": RoleName.CM.value,
            "duration_days": 2,
            "planned_hours": 1.5,
            "step_kind": "task",
        },
    ]
    if include_content_planning:
        steps.extend(
            [
                {
                    "name": "CC prep for KO/Planning",
                    "owner_role": RoleName.CC.value,
                    "duration_days": 1,
                    "planned_hours": 2.0,
                    "step_kind": "task",
                },
                {
                    "name": "Create content plan",
                    "owner_role": RoleName.CC.value,
                    "duration_days": 1,
                    "planned_hours": 2.0,
                    "health_critical": True,
                    "step_kind": "task",
                },
            ]
        )
    steps.append(
        {
            "name": "Run kick-off",
            "owner_role": RoleName.CM.value,
            "duration_days": 1,
            "planned_hours": 1.0,
            "step_kind": "call",
        }
    )
    return steps


def _interview_steps(include_content_work: bool) -> list[dict]:
    if include_content_work:
        return [
            {
                "name": "Book interview",
                "owner_role": RoleName.CM.value,
                "duration_days": 3,
                "planned_hours": 1.5,
                "step_kind": "task",
            },
            {
                "name": "Run interview",
                "owner_role": RoleName.CC.value,
                "duration_days": 1,
                "planned_hours": 1.5,
                "health_critical": True,
                "step_kind": "call",
            },
        ]
    return [
        {"name": "Book interview", "owner_role": RoleName.CM.value, "duration_days": 3, "planned_hours": 1.5, "step_kind": "task"},
        {
            "name": "Run interview",
            "owner_role": RoleName.CM.value,
            "duration_days": 1,
            "planned_hours": 1.0,
            "health_critical": True,
            "step_kind": "call",
        },
    ]


def _sprint_planning_steps() -> list[dict]:
    return [
        {"name": "Background research", "owner_role": RoleName.CC.value, "duration_days": 1, "planned_hours": 2.0, "step_kind": "task"},
        {"name": "Sprint briefing call", "owner_role": RoleName.CM.value, "duration_days": 1, "planned_hours": 1.0, "step_kind": "call"},
        {
            "name": "Create content plan",
            "owner_role": RoleName.CC.value,
            "duration_days": 1,
            "planned_hours": 2.0,
            "health_critical": True,
            "step_kind": "task",
        },
        {"name": "Interview call", "owner_role": RoleName.CC.value, "duration_days": 1, "planned_hours": 1.5, "health_critical": True, "step_kind": "call"},
    ]


def _article_steps() -> list[dict]:
    return [
        {"name": "Draft article", "owner_role": RoleName.CC.value, "duration_days": 3, "planned_hours": 4.0, "step_kind": "task"},
    ]


def _video_steps() -> list[dict]:
    return [
        {"name": "Video brief for design", "owner_role": RoleName.CC.value, "duration_days": 1, "planned_hours": 0.5, "step_kind": "task"},
        {"name": "Production", "owner_role": RoleName.CC.value, "duration_days": 4, "planned_hours": 6.0, "step_kind": "task"},
    ]


def _clip_or_short_steps(step_name: str) -> list[dict]:
    return [
        {"name": step_name, "owner_role": RoleName.CC.value, "duration_days": 2, "planned_hours": 1.5, "step_kind": "task"},
    ]


DEFAULT_TEMPLATES = {
    "demand": {
        "version": 8,
        "review_stall_threshold_days": {"internal": 2, "client": 3},
        "review_windows_working_days": {"internal": 2, "client": 5, "amends": 2},
        "review_windows_working_days_by_deliverable": {},
        # Compatibility defaults from TDtimeline milestone structure, adapted to 4-day week planning.
        "milestone_defaults": [
            {"name": "kickoff", "offset_working_days": 0},
            {"name": "content_plan", "offset_working_days": 4},
            {"name": "interview", "offset_working_days": 8},
            {"name": "writing_complete", "offset_working_days": 16},
            {"name": "internal_review_complete", "offset_working_days": 18},
            {"name": "client_review_complete", "offset_working_days": 23},
            {"name": "publishing", "offset_working_days": 24},
            {"name": "promoting_complete", "offset_working_days": 38},
            {"name": "reporting", "offset_working_days": 46},
        ],
        "steps_by_deliverable": {
            DeliverableType.ARTICLE.value: _article_steps(),
            DeliverableType.VIDEO.value: _video_steps(),
            DeliverableType.CLIP.value: _clip_or_short_steps("Produce clip"),
            DeliverableType.SHORT.value: _clip_or_short_steps("Produce host-led short"),
            DeliverableType.REPORT.value: [
                {"name": "Collect metrics", "owner_role": RoleName.CM.value, "duration_days": 2, "planned_hours": 2.0},
                {"name": "Draft report", "owner_role": RoleName.CM.value, "duration_days": 1, "planned_hours": 2.0},
                {"name": "Internal review", "owner_role": RoleName.HEAD_OPS.value, "duration_days": 1, "planned_hours": 1.0},
            ],
            DeliverableType.ENGAGEMENT_LIST.value: [
                {"name": "Compile engagement list", "owner_role": RoleName.CM.value, "duration_days": 2, "planned_hours": 1.5},
                {"name": "Internal review", "owner_role": RoleName.HEAD_OPS.value, "duration_days": 1, "planned_hours": 0.5},
            ],
            DeliverableType.LEAD_TOTAL.value: [
                {"name": "Confirm final lead total", "owner_role": RoleName.CM.value, "duration_days": 1, "planned_hours": 0.5},
            ],
        },
        "steps_by_sprint_phase": {
            "planning": _sprint_planning_steps(),
        },
        "csv_stage_steps": CSV_STAGE_STEPS,
    },
    "amplify": {
        "version": 8,
        "review_stall_threshold_days": {"internal": 2, "client": 3},
        "review_windows_working_days": {"internal": 2, "client": 5, "amends": 2},
        "review_windows_working_days_by_deliverable": {},
        "milestone_defaults": [
            {"name": "kickoff", "offset_working_days": 0},
            {"name": "interview", "offset_working_days": 4},
            {"name": "publishing", "offset_working_days": 16},
            {"name": "reporting", "offset_working_days": 24},
        ],
        "steps_by_deliverable": {
            DeliverableType.ARTICLE.value: _article_steps(),
            DeliverableType.VIDEO.value: _video_steps(),
            DeliverableType.CLIP.value: _clip_or_short_steps("Produce clip"),
            DeliverableType.SHORT.value: _clip_or_short_steps("Produce host-led short"),
            DeliverableType.REPORT.value: [
                {"name": "Collect metrics", "owner_role": RoleName.CM.value, "duration_days": 2, "planned_hours": 2.0, "step_kind": "task"},
                {"name": "Draft report", "owner_role": RoleName.CM.value, "duration_days": 1, "planned_hours": 2.0, "step_kind": "task"},
                {"name": "Internal review", "owner_role": RoleName.HEAD_OPS.value, "duration_days": 1, "planned_hours": 1.0, "step_kind": "approval"},
            ],
            DeliverableType.ENGAGEMENT_LIST.value: [
                {"name": "Compile engagement list", "owner_role": RoleName.CM.value, "duration_days": 2, "planned_hours": 1.5, "step_kind": "task"},
                {"name": "Internal review", "owner_role": RoleName.HEAD_OPS.value, "duration_days": 1, "planned_hours": 0.5, "step_kind": "approval"},
            ],
        },
        "steps_by_sprint_phase": {
            "planning": _sprint_planning_steps(),
        },
        "csv_stage_steps": CSV_STAGE_STEPS,
    },
    "response": {
        "version": 8,
        "review_stall_threshold_days": {"internal": 2, "client": 3},
        "review_windows_working_days": {"internal": 2, "client": 5, "amends": 2},
        "review_windows_working_days_by_deliverable": {},
        "milestone_defaults": [
            {"name": "kickoff", "offset_working_days": 0},
            {"name": "publishing", "offset_working_days": 12},
            {"name": "reporting", "offset_working_days": 20},
        ],
        "steps_by_deliverable": {
            DeliverableType.LANDING_PAGE.value: [
                {"name": "Build landing page", "owner_role": RoleName.CM.value, "duration_days": 3, "planned_hours": 3.0, "step_kind": "task"},
                {"name": "Client review", "owner_role": RoleName.AM.value, "duration_days": 2, "planned_hours": 1.0, "step_kind": "approval"},
            ],
            DeliverableType.EMAIL.value: [
                {"name": "Draft email", "owner_role": RoleName.CM.value, "duration_days": 2, "planned_hours": 2.0, "step_kind": "task"},
                {"name": "Client review", "owner_role": RoleName.AM.value, "duration_days": 2, "planned_hours": 1.0, "step_kind": "approval"},
            ],
            DeliverableType.VIDEO.value: _video_steps(),
            DeliverableType.LEAD_TOTAL.value: [
                {"name": "Confirm final lead total", "owner_role": RoleName.CM.value, "duration_days": 1, "planned_hours": 0.5, "step_kind": "task"},
            ],
        },
        "steps_by_sprint_phase": {
            "planning": _sprint_planning_steps(),
        },
        "csv_stage_steps": CSV_STAGE_STEPS,
    },
}
