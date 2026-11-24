"""Reviewed C1 route/lifetime inventory. Not a runtime middleware yet.

Match actual registered route templates, not untrusted URL prefixes. No
unclassified route may silently become lightweight when integration lands.
Integrity status may stream a bounded source digest, but not materialize a frame;
verify that property and concurrent polling cost before wiring. Metadata/control
classification is not an authentication exemption.
"""
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class RoutePlan:
    endpoint: str
    lifetime: str
    operation: str | None


ROUTES = MappingProxyType({
    ("GET", "/api/health"): RoutePlan("health", "metadata", None),
    ("GET", "/api/projects"): RoutePlan("projects", "metadata", None),
    ("POST", "/api/projects"): RoutePlan("create_project", "upload", "data"),
    ("GET", "/api/projects/manage"): RoutePlan("manage_projects", "metadata", None),
    ("PUT", "/api/projects/{project_id}/lifecycle"): RoutePlan("change_project_lifecycle", "control", None),
    ("GET", "/api/projects/{project_id}/deletion-impact"): RoutePlan("get_project_deletion_impact", "metadata", None),
    ("GET", "/api/projects/{project_id}"): RoutePlan("get_project", "metadata", None),
    ("GET", "/api/projects/{project_id}/preparation"): RoutePlan("prepare", "request", "data"),
    ("POST", "/api/projects/{project_id}/experiments"): RoutePlan("new_experiment", "training_handoff", "training"),
    ("GET", "/api/experiments/{experiment_id}"): RoutePlan("get_experiment", "integrity_status", None),
    ("POST", "/api/experiments/{experiment_id}/cancel"): RoutePlan("cancel_training", "control", None),
    ("POST", "/api/experiments/{experiment_id}/select"): RoutePlan("choose_model", "request", "model_load"),
    ("POST", "/api/experiments/{experiment_id}/predict"): RoutePlan("predict", "request", "model_load"),
    ("GET", "/api/projects/{project_id}/quality"): RoutePlan("get_quality", "request", "data"),
    ("GET", "/api/projects/{project_id}/quality/investigate"): RoutePlan("investigate_quality_finding", "request", "data"),
    ("GET", "/api/projects/{project_id}/quality/preview"): RoutePlan("get_quality_preview", "request", "data"),
    ("POST", "/api/projects/{project_id}/quality/export"): RoutePlan("export_cleaned_dataset", "stream", "export"),
    ("GET", "/api/projects/{project_id}/quality/history"): RoutePlan("get_quality_history", "request", "data"),
    ("POST", "/api/projects/{project_id}/quality/proposals"): RoutePlan("preview_quality_change", "request", "data"),
    ("POST", "/api/projects/{project_id}/quality/commit"): RoutePlan("commit_quality_change", "request", "data"),
    ("POST", "/api/projects/{project_id}/quality/autopilot"): RoutePlan("run_quality_autopilot", "request", "data"),
    ("POST", "/api/projects/{project_id}/quality/decisions"): RoutePlan("decide_quality", "request", "data"),
    ("POST", "/api/projects/{project_id}/quality/undo"): RoutePlan("undo_quality", "request", "data"),
    ("POST", "/api/projects/{project_id}/quality/restore"): RoutePlan("restore_quality", "request", "data"),
    ("GET", "/api/projects/{project_id}/columns/overview"): RoutePlan("column_investigation_overview", "request", "data"),
    ("GET", "/api/projects/{project_id}/target-opportunities"): RoutePlan("target_opportunity_overview", "request", "data"),
    ("GET", "/api/projects/{project_id}/target-opportunities/inspect"): RoutePlan("inspect_manual_target_opportunity", "request", "data"),
    ("POST", "/api/projects/{project_id}/target-business-context"): RoutePlan("save_target_business_context", "request", "data"),
    ("POST", "/api/projects/{project_id}/semantic-business-context"): RoutePlan("save_semantic_business_context", "request", "data"),
    ("GET", "/api/projects/{project_id}/semantics"): RoutePlan("semantic_overview", "request", "data"),
    ("GET", "/api/projects/{project_id}/semantic-reviews"): RoutePlan("list_human_semantic_reviews", "request", "data"),
    ("POST", "/api/projects/{project_id}/semantic-reviews"): RoutePlan("save_human_semantic_review", "request", "data"),
    ("GET", "/api/projects/{project_id}/columns/detail"): RoutePlan("column_investigation_detail", "request", "data"),
    ("GET", "/api/projects/{project_id}/explore/overview"): RoutePlan("explore_overview", "request", "data"),
    ("GET", "/api/projects/{project_id}/explore/chart"): RoutePlan("explore_chart", "request", "data"),
    ("GET", "/api/projects/{project_id}/explore/correlation"): RoutePlan("explore_correlation", "request", "data"),
    ("GET", "/api/projects/{project_id}/explore/filter-options"): RoutePlan("explore_filter_options", "request", "data"),
    ("POST", "/api/projects/{project_id}/explore/workbench"): RoutePlan("explore_workbench", "request", "data"),
    ("POST", "/api/projects/{project_id}/explore/inspect"): RoutePlan("explore_inspect", "request", "data"),
    ("GET", "/api/projects/{project_id}/explore/saved"): RoutePlan("list_saved_explore_analyses", "request", "data"),
    ("GET", "/api/projects/{project_id}/explore/saved/{snapshot_id}"): RoutePlan("read_saved_explore_analysis", "request", "data"),
    ("POST", "/api/projects/{project_id}/explore/saved"): RoutePlan("save_explore_analysis", "request", "data"),
    ("GET", "/api/projects/{project_id}/explore/insights"): RoutePlan("explore_insights", "request", "data"),
    ("GET", "/api/projects/{project_id}/features"): RoutePlan("feature_recommendations", "request", "data"),
    ("POST", "/api/projects/{project_id}/assistant"): RoutePlan("ask_assistant", "request", "data"),
    ("GET", "/api/resource/status"): RoutePlan("resource_status", "control", None),
    ("GET", "/api/resource/preflight"): RoutePlan("resource_preflight", "control", None),
    ("PUT", "/api/resource/policy"): RoutePlan("update_resource_policy", "control", None),
    ("GET", "/api/ai/settings"): RoutePlan("ai_settings", "control", None),
    ("PUT", "/api/ai/settings"): RoutePlan("save_ai_settings", "control", None),
    ("PUT", "/api/ai/key"): RoutePlan("save_ai_key", "control", None),
    ("POST", "/api/projects/{project_id}/ai/insight"): RoutePlan("ai_insight", "staged_inference", "data"),
    ("GET", "/api/ai/local/status"): RoutePlan("local_ai_status", "control", None),
    ("POST", "/api/ai/verify-connected"): RoutePlan("verify_ai_providers", "control", None),
    ("POST", "/api/ai/test/{provider}"): RoutePlan("test_ai_provider", "control", None),
    ("GET", "/api/projects/{project_id}/live-profile"): RoutePlan("live_profile", "request", "data"),
    ("GET", "/api/projects/{project_id}/investigations"): RoutePlan("list_canvas_investigations", "integrity_status", None),
    ("POST", "/api/projects/{project_id}/investigations"): RoutePlan("create_canvas_investigation", "request", "data"),
    ("GET", "/api/investigations/{investigation_id}"): RoutePlan("get_canvas_investigation", "request", "data"),
    ("POST", "/api/investigations/{investigation_id}/runs"): RoutePlan("run_canvas_tool", "request", "data"),
    ("GET", "/api/investigations/{investigation_id}/autonomy"): RoutePlan("get_autonomous_run", "integrity_status", None),
    ("POST", "/api/investigations/{investigation_id}/autonomy/start"): RoutePlan("start_autonomous_run", "autonomy_handoff", "data"),
    ("POST", "/api/investigations/{investigation_id}/autonomy/resume"): RoutePlan("resume_autonomous_run", "autonomy_handoff", "data"),
    ("POST", "/api/investigations/{investigation_id}/autonomy/cancel"): RoutePlan("cancel_autonomous_run", "control", None),
    ("POST", "/api/projects/{project_id}/investigate"): RoutePlan("investigate_project", "request", "data"),
    ("GET", "/api/projects/{project_id}/quality/missingness"): RoutePlan("quality_missingness", "request", "data"),
    ("POST", "/api/projects/{project_id}/quality/impute"): RoutePlan("quality_impute", "request", "data"),
    ("GET", "/api/projects/{project_id}/explore/recommended"): RoutePlan("recommended_exploration", "request", "data"),
    ("GET", "/api/projects/{project_id}/report-evidence"): RoutePlan("list_available_report_evidence", "request", "report"),
    ("GET", "/api/projects/{project_id}/report-evidence/{evidence_id}/preview"): RoutePlan("preview_verified_report_evidence", "request", "report"),
    ("POST", "/api/projects/{project_id}/report-quality"): RoutePlan("capture_quality_report_evidence", "request", "report"),
    ("GET", "/api/projects/{project_id}/reports"): RoutePlan("list_saved_reports", "metadata", None),
    ("POST", "/api/projects/{project_id}/reports"): RoutePlan("create_saved_report", "request", "report"),
    ("GET", "/api/reports/{report_id}"): RoutePlan("read_saved_report", "request", "report"),
    ("POST", "/api/reports/{report_id}/revisions"): RoutePlan("revise_saved_report", "request", "report"),
    ("GET", "/api/reports/{report_id}/export/{format}"): RoutePlan("export_saved_report", "request", "report"),
})
