"""
PM-first report templates. Each template is a JSON spec the planner uses
as priors (entities to look for, output shape, suggested charts).
"""

from __future__ import annotations

from typing import Any


TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "onboarding-dropoff",
        "name": "Onboarding drop-off",
        "tagline": "Where new users fall off between sign-up and activation",
        "icon": "funnel",
        "params": [
            {"id": "date_range", "label": "Date range", "type": "date_range", "default": "30d"},
            {"id": "segment", "label": "Segment (optional)", "type": "text", "placeholder": "country, plan, ..."},
            {"id": "activation_event", "label": "Activation event", "type": "text", "placeholder": "first_action / first_value"},
        ],
        "intent": (
            "Find where new users drop off between sign-up and activation. "
            "Look for a users/accounts table and an events/activity table. "
            "Build a step funnel (sign-up -> key events -> activation), compute step-wise "
            "conversion and time-to-step, and segment by major dimensions if available."
        ),
        "synthesis_hint": (
            "Lead with the biggest step where users are lost, give absolute numbers, "
            "compare against prior period when possible, and propose 3-5 concrete actions."
        ),
        "suggested_charts": ["funnel", "bar"],
    },
    {
        "id": "activation-funnel",
        "name": "Activation funnel",
        "tagline": "Step-by-step funnel for any sequence of events",
        "icon": "steps",
        "params": [
            {"id": "date_range", "label": "Date range", "type": "date_range", "default": "30d"},
            {"id": "steps", "label": "Step events (comma-separated, ordered)", "type": "text", "placeholder": "sign_up, verify_email, first_project, invite_member"},
        ],
        "intent": (
            "Build a generic ordered-event funnel with stepwise conversion percentages, "
            "median time between steps, and counts by step."
        ),
        "synthesis_hint": (
            "Highlight the worst-performing transition and quantify the loss; "
            "suggest A/B tests targeting that transition."
        ),
        "suggested_charts": ["funnel", "line"],
    },
    {
        "id": "retention-cohorts",
        "name": "Retention cohorts",
        "tagline": "Weekly/monthly retention by signup cohort",
        "icon": "grid",
        "params": [
            {"id": "granularity", "label": "Cohort granularity", "type": "select", "options": ["weekly", "monthly"], "default": "weekly"},
            {"id": "horizon", "label": "Horizon (periods)", "type": "number", "default": 12},
            {"id": "return_event", "label": "Return event (optional)", "type": "text", "placeholder": "session, login, ..."},
        ],
        "intent": (
            "Compute classic cohort retention: bucket users by signup cohort, then "
            "measure the % of each cohort active in each subsequent period. "
            "Default 'active' = any event for the user in that period."
        ),
        "synthesis_hint": (
            "Identify cohorts with above/below average curves, call out the period-1 cliff, "
            "and propose retention experiments."
        ),
        "suggested_charts": ["heatmap", "line"],
    },
    {
        "id": "feature-adoption",
        "name": "Feature adoption",
        "tagline": "Adoption curve and reach for a feature since launch",
        "icon": "spark",
        "params": [
            {"id": "feature_event", "label": "Feature event", "type": "text", "placeholder": "feature_x_used"},
            {"id": "date_range", "label": "Date range", "type": "date_range", "default": "90d"},
        ],
        "intent": (
            "Quantify feature adoption: unique users per day/week, share of MAU, "
            "time-to-first-use after sign-up, repeat usage rate."
        ),
        "synthesis_hint": (
            "Compare against total active base, call out plateaus, and propose growth levers."
        ),
        "suggested_charts": ["line", "bar"],
    },
    {
        "id": "revenue-churn",
        "name": "Revenue & churn",
        "tagline": "MRR, churn, and expansion when subscriptions exist",
        "icon": "currency",
        "params": [
            {"id": "date_range", "label": "Date range", "type": "date_range", "default": "90d"},
        ],
        "intent": (
            "Look for subscriptions / payments / invoices tables. Compute MRR by month, "
            "gross churn rate, expansion MRR, and net revenue retention if data permits."
        ),
        "synthesis_hint": (
            "Lead with NRR if computable, else MRR trend; call out churn spikes and "
            "expansion concentration."
        ),
        "suggested_charts": ["line", "bar"],
    },
    {
        "id": "ad-hoc",
        "name": "Ad-hoc analysis",
        "tagline": "Open prompt — describe the question you want answered",
        "icon": "sparkle",
        "params": [],
        "intent": "Decompose the PM's natural-language question into 2-5 sub-queries.",
        "synthesis_hint": "Be direct: numbers first, then findings, then 3-5 actions.",
        "suggested_charts": ["auto"],
    },
]


def get_template(template_id: str) -> dict[str, Any] | None:
    for t in TEMPLATES:
        if t["id"] == template_id:
            return t
    return None


def list_templates_public() -> list[dict[str, Any]]:
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "tagline": t["tagline"],
            "icon": t["icon"],
            "params": t["params"],
        }
        for t in TEMPLATES
    ]
