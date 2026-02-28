import json
import os
import re
import uuid
from datetime import timedelta
from typing import Any

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import Max, Q
from django.db.utils import DatabaseError
from django.http import HttpResponse, JsonResponse
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .events import maybe_publish_audit_event, maybe_publish_event
from .identity import require_any_role, require_role
from .metrics import DB_READINESS_ERRORS, metrics_response
from .models import (
    AccessRequest,
    AssetVersion,
    Classification,
    CollaborationDocument,
    CollaborationDocumentVersion,
    ConnectorRun,
    ConsentEvent,
    DataAsset,
    DataContract,
    DataShare,
    DataProduct,
    AgentRun,
    GlossaryTerm,
    GovernancePolicy,
    GovernancePolicyTransition,
    IngestionRequest,
    LineageEdge,
    MasterMergeCandidate,
    MasterRecord,
    NotebookExecution,
    NotebookSession,
    NotebookWorkspace,
    OrchestrationRun,
    OrchestrationWorkflow,
    PrivacyAction,
    PrivacyProfile,
    PrintJob,
    Project,
    ReferenceDataset,
    ReferenceDatasetVersion,
    ResidencyProfile,
    StewardshipItem,
    QualityCheckResult,
    QualityRule,
    RetentionHold,
    RetentionRule,
    RetentionRun,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowTask,
)
from .tasks import evaluate_quality_rule, execute_connector_run, execute_retention_run


def _tenant_schema(request) -> str:
    tenant = getattr(request, 'tenant', None)
    return tenant.schema_name if tenant else connection.schema_name


def health(request):
    return JsonResponse({'schema': connection.schema_name})


def probe_ok(request):
    return JsonResponse({'status': 'ok'})

def livez(request):
    return probe_ok(request)


def healthz(request):
    return probe_ok(request)


def readyz(request):
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except DatabaseError:
        DB_READINESS_ERRORS.inc()
        return JsonResponse({'status': 'not-ready'}, status=503)
    return JsonResponse({'status': 'ok'})


def metrics(request):
    body, content_type = metrics_response()
    return HttpResponse(body, content_type=content_type)


def _asset_to_dict(asset: DataAsset) -> dict[str, Any]:
    return {
        'id': str(asset.id),
        'qualified_name': asset.qualified_name,
        'display_name': asset.display_name,
        'asset_type': asset.asset_type,
        'description': None if asset.description == '' else asset.description,
        'owner': None if asset.owner == '' else asset.owner,
        'tags': asset.tags,
        'classifications': asset.classifications,
        'properties': asset.properties,
        'created_at': asset.created_at.isoformat(),
        'updated_at': asset.updated_at.isoformat(),
    }


def _asset_version_to_dict(version: AssetVersion) -> dict[str, Any]:
    return {
        'id': str(version.id),
        'asset_id': str(version.asset_id),
        'version_number': version.version_number,
        'change_summary': version.change_summary or None,
        'change_set': version.change_set,
        'status': version.status,
        'created_by': version.created_by or None,
        'created_at': version.created_at.isoformat(),
        'updated_at': version.updated_at.isoformat(),
    }


def _parse_json_body(request):
    try:
        body = request.body.decode('utf-8') if request.body else ''
        return json.loads(body or '{}')
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _parse_string_list(value: Any) -> list[str] | None:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return None
    return value


def _parse_uuid_string_list(value: Any) -> list[str] | None:
    parsed = _parse_string_list(value)
    if parsed is None:
        return None
    normalized = []
    for item in parsed:
        try:
            normalized.append(str(uuid.UUID(item)))
        except ValueError:
            return None
    return normalized


def _parse_orchestration_steps(value: Any) -> list[dict[str, Any]] | None:
    if value is None:
        return []
    if not isinstance(value, list):
        return None
    normalized = []
    known_step_ids = set()
    for raw_step in value:
        if not isinstance(raw_step, dict):
            return None
        step_id = (raw_step.get('step_id') or '').strip()
        ingestion_id = raw_step.get('ingestion_id')
        depends_on = raw_step.get('depends_on') or []
        if not step_id or not ingestion_id:
            return None
        if step_id in known_step_ids:
            return None
        if not isinstance(depends_on, list) or not all(
            isinstance(dep, str) and dep for dep in depends_on
        ):
            return None
        if any(dep not in known_step_ids for dep in depends_on):
            return None
        try:
            normalized_ingestion_id = str(uuid.UUID(str(ingestion_id)))
        except ValueError:
            return None
        known_step_ids.add(step_id)
        normalized.append(
            {
                'step_id': step_id,
                'ingestion_id': normalized_ingestion_id,
                'depends_on': depends_on,
            }
        )
    return normalized


CLASSIFICATION_SENSITIVITY = {
    Classification.Level.PUBLIC: 0,
    Classification.Level.INTERNAL: 1,
    Classification.Level.CONFIDENTIAL: 2,
    Classification.Level.RESTRICTED: 3,
}

AGENT_TOOL_ALLOWLIST = {
    'catalog.search',
    'asset.read',
    'contract.read',
    'quality.read',
    'lineage.read',
    'governance.read',
}


def _classification_max_sensitivity(values: list[str]) -> int:
    return max((CLASSIFICATION_SENSITIVITY.get(item, -1) for item in values), default=-1)


def _validate_classification_values(values: list[str]) -> list[str]:
    allowed = set(CLASSIFICATION_SENSITIVITY)
    return sorted({item for item in values if item not in allowed})


def _enforce_sensitivity_upgrade_role(
    request,
    *,
    existing_values: list[str],
    next_values: list[str],
):
    if _classification_max_sensitivity(next_values) <= _classification_max_sensitivity(
        existing_values
    ):
        return None
    return require_any_role(request, {'policy.admin', 'tenant.admin'})


def _ingestion_to_dict(ing: IngestionRequest) -> dict[str, Any]:
    return {
        'id': str(ing.id),
        'project_id': str(ing.project_id) if ing.project_id else None,
        'connector': ing.connector,
        'source': ing.source,
        'mode': ing.mode if ing.mode else None,
        'status': ing.status,
        'created_at': ing.created_at.isoformat(),
        'updated_at': ing.updated_at.isoformat(),
    }


def _edge_to_dict(edge: LineageEdge) -> dict[str, Any]:
    return {
        'id': str(edge.id),
        'from_asset_id': str(edge.from_asset_id),
        'to_asset_id': str(edge.to_asset_id),
        'edge_type': edge.edge_type,
        'properties': edge.properties,
        'created_at': edge.created_at.isoformat(),
        'updated_at': edge.updated_at.isoformat(),
    }


def _quality_rule_to_dict(rule: QualityRule) -> dict[str, Any]:
    return {
        'id': str(rule.id),
        'asset_id': str(rule.asset_id),
        'rule_type': rule.rule_type,
        'params': rule.params,
        'severity': rule.severity,
        'created_at': rule.created_at.isoformat(),
        'updated_at': rule.updated_at.isoformat(),
    }


def _quality_result_to_dict(result: QualityCheckResult) -> dict[str, Any]:
    return {
        'id': str(result.id),
        'rule_id': str(result.rule_id),
        'asset_id': str(result.rule.asset_id),
        'status': result.status,
        'details': result.details,
        'created_at': result.created_at.isoformat(),
    }


def _contract_to_dict(contract: DataContract) -> dict[str, Any]:
    return {
        'id': str(contract.id),
        'asset_id': str(contract.asset_id),
        'version': contract.version,
        'status': contract.status,
        'schema': contract.schema,
        'expectations': contract.expectations,
        'owners': contract.owners,
        'created_at': contract.created_at.isoformat(),
        'updated_at': contract.updated_at.isoformat(),
    }


def _retention_rule_to_dict(rule: RetentionRule) -> dict[str, Any]:
    return {
        'id': str(rule.id),
        'scope': rule.scope,
        'action': rule.action,
        'retention_period': rule.retention_period,
        'grace_period': rule.grace_period or None,
        'created_at': rule.created_at.isoformat(),
        'updated_at': rule.updated_at.isoformat(),
    }


def _retention_hold_to_dict(hold: RetentionHold) -> dict[str, Any]:
    return {
        'id': str(hold.id),
        'asset_id': str(hold.asset_id),
        'reason': hold.reason,
        'active': hold.active,
        'created_at': hold.created_at.isoformat(),
        'released_at': hold.released_at.isoformat() if hold.released_at else None,
    }


def _retention_run_to_dict(run: RetentionRun) -> dict[str, Any]:
    return {
        'id': str(run.id),
        'rule_id': str(run.rule_id),
        'mode': run.mode,
        'status': run.status,
        'summary': run.summary,
        'created_at': run.created_at.isoformat(),
        'completed_at': run.completed_at.isoformat() if run.completed_at else None,
    }


def _is_day_duration(value: str) -> bool:
    return bool(re.fullmatch(r'P\d+D', value or ''))


def _privacy_profile_to_dict(profile: PrivacyProfile) -> dict[str, Any]:
    return {
        'id': str(profile.id),
        'name': profile.name,
        'lawful_basis': profile.lawful_basis,
        'consent_required': profile.consent_required,
        'consent_state': profile.consent_state,
        'privacy_flags': profile.privacy_flags,
        'created_at': profile.created_at.isoformat(),
        'updated_at': profile.updated_at.isoformat(),
    }


def _consent_event_to_dict(event: ConsentEvent) -> dict[str, Any]:
    return {
        'id': str(event.id),
        'profile_id': str(event.profile_id),
        'consent_state': event.consent_state,
        'reason': event.reason,
        'created_at': event.created_at.isoformat(),
    }


def _privacy_action_to_dict(action: PrivacyAction) -> dict[str, Any]:
    return {
        'id': str(action.id),
        'profile_id': str(action.profile_id),
        'action_type': action.action_type,
        'status': action.status,
        'reason': action.reason or None,
        'actor_id': action.actor_id or None,
        'evidence': action.evidence,
        'requested_at': action.requested_at.isoformat(),
        'decided_at': action.decided_at.isoformat() if action.decided_at else None,
        'executed_at': action.executed_at.isoformat() if action.executed_at else None,
    }


def _agent_run_to_dict(agent_run: AgentRun) -> dict[str, Any]:
    return {
        'id': str(agent_run.id),
        'actor_id': agent_run.actor_id or None,
        'prompt': agent_run.prompt,
        'allowed_tools': agent_run.allowed_tools,
        'timeout_seconds': agent_run.timeout_seconds,
        'status': agent_run.status,
        'output': agent_run.output,
        'error_message': agent_run.error_message or None,
        'started_at': agent_run.started_at.isoformat() if agent_run.started_at else None,
        'finished_at': agent_run.finished_at.isoformat() if agent_run.finished_at else None,
        'created_at': agent_run.created_at.isoformat(),
        'updated_at': agent_run.updated_at.isoformat(),
    }


def _stewardship_item_to_dict(item: StewardshipItem) -> dict[str, Any]:
    return {
        'id': str(item.id),
        'item_type': item.item_type,
        'subject_ref': item.subject_ref,
        'severity': item.severity,
        'status': item.status,
        'assignee': item.assignee or None,
        'due_at': item.due_at.isoformat() if item.due_at else None,
        'resolution': item.resolution,
        'actor_id': item.actor_id or None,
        'created_at': item.created_at.isoformat(),
        'updated_at': item.updated_at.isoformat(),
        'resolved_at': item.resolved_at.isoformat() if item.resolved_at else None,
    }


def _residency_profile_to_dict(profile: ResidencyProfile) -> dict[str, Any]:
    return {
        'id': str(profile.id),
        'name': profile.name,
        'allowed_regions': profile.allowed_regions,
        'blocked_regions': profile.blocked_regions,
        'enforcement_mode': profile.enforcement_mode,
        'status': profile.status,
        'created_at': profile.created_at.isoformat(),
        'updated_at': profile.updated_at.isoformat(),
    }


def _access_request_to_dict(access_request: AccessRequest) -> dict[str, Any]:
    return {
        'id': str(access_request.id),
        'subject_ref': access_request.subject_ref,
        'requester': access_request.requester,
        'access_type': access_request.access_type,
        'justification': access_request.justification,
        'status': access_request.status,
        'approver': access_request.approver or None,
        'expires_at': access_request.expires_at.isoformat() if access_request.expires_at else None,
        'created_at': access_request.created_at.isoformat(),
        'updated_at': access_request.updated_at.isoformat(),
    }


def _reference_dataset_to_dict(dataset: ReferenceDataset) -> dict[str, Any]:
    active_version = dataset.versions.filter(status=ReferenceDatasetVersion.Status.ACTIVE).order_by('-version').first()
    return {
        'id': str(dataset.id),
        'name': dataset.name,
        'owner': dataset.owner or None,
        'domain': dataset.domain or None,
        'active_version': active_version.version if active_version else None,
        'created_at': dataset.created_at.isoformat(),
        'updated_at': dataset.updated_at.isoformat(),
    }


def _reference_dataset_version_to_dict(version: ReferenceDatasetVersion) -> dict[str, Any]:
    return {
        'id': str(version.id),
        'dataset_id': str(version.dataset_id),
        'version': version.version,
        'status': version.status,
        'values': version.values,
        'created_at': version.created_at.isoformat(),
        'updated_at': version.updated_at.isoformat(),
    }


def _master_record_to_dict(record: MasterRecord) -> dict[str, Any]:
    return {
        'id': str(record.id),
        'entity_type': record.entity_type,
        'master_id': str(record.master_id),
        'version': record.version,
        'attributes': record.attributes,
        'survivorship_policy': record.survivorship_policy,
        'confidence': record.confidence,
        'status': record.status,
        'created_at': record.created_at.isoformat(),
        'updated_at': record.updated_at.isoformat(),
    }


def _master_merge_candidate_to_dict(
    candidate: MasterMergeCandidate,
) -> dict[str, Any]:
    return {
        'id': str(candidate.id),
        'entity_type': candidate.entity_type,
        'target_master_id': str(candidate.target_master_id),
        'source_master_refs': candidate.source_master_refs,
        'proposed_attributes': candidate.proposed_attributes,
        'confidence': candidate.confidence,
        'status': candidate.status,
        'approved_by': candidate.approved_by or None,
        'created_at': candidate.created_at.isoformat(),
        'updated_at': candidate.updated_at.isoformat(),
    }


def _classification_to_dict(classification: Classification) -> dict[str, Any]:
    return {
        'id': str(classification.id),
        'name': classification.name,
        'level': classification.level,
        'description': classification.description,
        'tags': classification.tags,
        'status': classification.status,
        'created_at': classification.created_at.isoformat(),
        'updated_at': classification.updated_at.isoformat(),
    }


def _print_job_to_dict(print_job: PrintJob) -> dict[str, Any]:
    return {
        'id': str(print_job.id),
        'template_ref': print_job.template_ref,
        'payload': print_job.payload,
        'output_format': print_job.output_format,
        'destination': print_job.destination,
        'status': print_job.status,
        'retry_count': print_job.retry_count,
        'gateway_metadata': print_job.gateway_metadata,
        'error_message': print_job.error_message or None,
        'created_at': print_job.created_at.isoformat(),
        'updated_at': print_job.updated_at.isoformat(),
    }


def _collaboration_document_to_dict(
    document: CollaborationDocument,
) -> dict[str, Any]:
    latest_version = document.versions.order_by('-version').first()
    return {
        'id': str(document.id),
        'title': document.title,
        'object_key': document.object_key,
        'content_type': document.content_type or None,
        'owner': document.owner or None,
        'status': document.status,
        'latest_version': latest_version.version if latest_version else None,
        'created_at': document.created_at.isoformat(),
        'updated_at': document.updated_at.isoformat(),
    }


def _collaboration_version_to_dict(
    version: CollaborationDocumentVersion,
) -> dict[str, Any]:
    return {
        'id': str(version.id),
        'document_id': str(version.document_id),
        'version': version.version,
        'object_key': version.object_key,
        'summary': version.summary,
        'editor': version.editor or None,
        'created_at': version.created_at.isoformat(),
    }


def _notebook_workspace_to_dict(workspace: NotebookWorkspace) -> dict[str, Any]:
    return {
        'id': str(workspace.id),
        'name': workspace.name,
        'owner': workspace.owner or None,
        'image': workspace.image or None,
        'cpu_limit': workspace.cpu_limit or None,
        'memory_limit': workspace.memory_limit or None,
        'storage_mounts': workspace.storage_mounts,
        'status': workspace.status,
        'created_at': workspace.created_at.isoformat(),
        'updated_at': workspace.updated_at.isoformat(),
    }


def _notebook_session_to_dict(session: NotebookSession) -> dict[str, Any]:
    return {
        'id': str(session.id),
        'workspace_id': str(session.workspace_id),
        'user_id': session.user_id or None,
        'pod_name': session.pod_name or None,
        'status': session.status,
        'metadata': session.metadata,
        'started_at': session.started_at.isoformat(),
        'ended_at': session.ended_at.isoformat() if session.ended_at else None,
    }


def _notebook_execution_to_dict(execution: NotebookExecution) -> dict[str, Any]:
    return {
        'id': str(execution.id),
        'session_id': str(execution.session_id),
        'cell_ref': execution.cell_ref or None,
        'status': execution.status,
        'metadata': execution.metadata,
        'requested_at': execution.requested_at.isoformat(),
        'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
    }


def _connector_run_to_dict(run: ConnectorRun) -> dict[str, Any]:
    return {
        'id': str(run.id),
        'project_id': str(run.ingestion.project_id) if run.ingestion.project_id else None,
        'ingestion_id': str(run.ingestion_id),
        'execution_path': run.execution_path,
        'status': run.status,
        'retry_count': run.retry_count,
        'progress': run.progress,
        'error_message': run.error_message or None,
        'started_at': run.started_at.isoformat() if run.started_at else None,
        'finished_at': run.finished_at.isoformat() if run.finished_at else None,
        'created_at': run.created_at.isoformat(),
        'updated_at': run.updated_at.isoformat(),
    }


def _workflow_definition_to_dict(definition: WorkflowDefinition) -> dict[str, Any]:
    return {
        'id': str(definition.id),
        'name': definition.name,
        'description': definition.description,
        'domain_ref': definition.domain_ref,
        'created_at': definition.created_at.isoformat(),
        'updated_at': definition.updated_at.isoformat(),
    }


def _workflow_run_to_dict(run: WorkflowRun) -> dict[str, Any]:
    return {
        'id': str(run.id),
        'definition_id': str(run.definition_id),
        'subject_ref': run.subject_ref,
        'status': run.status,
        'submitted_by': run.submitted_by or None,
        'reviewed_by': run.reviewed_by or None,
        'payload': run.payload,
        'created_at': run.created_at.isoformat(),
        'updated_at': run.updated_at.isoformat(),
    }


def _workflow_task_to_dict(task: WorkflowTask) -> dict[str, Any]:
    return {
        'id': str(task.id),
        'run_id': str(task.run_id),
        'task_type': task.task_type,
        'assignee': task.assignee or None,
        'status': task.status,
        'created_at': task.created_at.isoformat(),
        'completed_at': task.completed_at.isoformat() if task.completed_at else None,
    }


def _orchestration_workflow_to_dict(workflow: OrchestrationWorkflow) -> dict[str, Any]:
    return {
        'id': str(workflow.id),
        'project_id': str(workflow.project_id) if workflow.project_id else None,
        'name': workflow.name,
        'trigger_type': workflow.trigger_type,
        'trigger_value': workflow.trigger_value or None,
        'steps': workflow.steps,
        'status': workflow.status,
        'created_at': workflow.created_at.isoformat(),
        'updated_at': workflow.updated_at.isoformat(),
    }


def _orchestration_run_to_dict(run: OrchestrationRun) -> dict[str, Any]:
    return {
        'id': str(run.id),
        'project_id': str(run.project_id) if run.project_id else None,
        'workflow_id': str(run.workflow_id),
        'trigger_context': run.trigger_context,
        'status': run.status,
        'step_results': run.step_results,
        'error_message': run.error_message or None,
        'started_at': run.started_at.isoformat() if run.started_at else None,
        'finished_at': run.finished_at.isoformat() if run.finished_at else None,
        'created_at': run.created_at.isoformat(),
        'updated_at': run.updated_at.isoformat(),
    }


def _governance_policy_to_dict(policy: GovernancePolicy) -> dict[str, Any]:
    return {
        'id': str(policy.id),
        'name': policy.name,
        'version': policy.version,
        'status': policy.status,
        'rules': policy.rules,
        'reason': policy.reason or None,
        'actor_id': policy.actor_id or None,
        'rollback_target_id': str(policy.rollback_target_id) if policy.rollback_target_id else None,
        'created_at': policy.created_at.isoformat(),
        'updated_at': policy.updated_at.isoformat(),
    }


def _project_to_dict(project: Project) -> dict[str, Any]:
    return {
        'id': str(project.id),
        'name': project.name,
        'code': project.code or None,
        'institution_ref': project.institution_ref or None,
        'status': project.status,
        'sync_config': project.sync_config,
        'created_at': project.created_at.isoformat(),
        'updated_at': project.updated_at.isoformat(),
    }


def _glossary_term_to_dict(term: GlossaryTerm) -> dict[str, Any]:
    return {
        'id': str(term.id),
        'name': term.name,
        'definition': term.definition or None,
        'status': term.status,
        'owners': term.owners,
        'stewards': term.stewards,
        'related_asset_ids': term.related_asset_ids,
        'classifications': term.classifications,
        'created_at': term.created_at.isoformat(),
        'updated_at': term.updated_at.isoformat(),
    }


def _data_product_to_dict(product: DataProduct) -> dict[str, Any]:
    return {
        'id': str(product.id),
        'name': product.name,
        'domain': product.domain or None,
        'owner': product.owner or None,
        'asset_ids': product.asset_ids,
        'sla': product.sla,
        'status': product.status,
        'created_at': product.created_at.isoformat(),
        'updated_at': product.updated_at.isoformat(),
    }


def _data_share_to_dict(share: DataShare) -> dict[str, Any]:
    return {
        'id': str(share.id),
        'asset_id': str(share.asset_id),
        'consumer_ref': share.consumer_ref,
        'purpose': share.purpose or None,
        'constraints': share.constraints,
        'linked_access_request_ids': share.linked_access_request_ids,
        'status': share.status,
        'expires_at': share.expires_at.isoformat() if share.expires_at else None,
        'approved_by': share.approved_by or None,
        'created_at': share.created_at.isoformat(),
        'updated_at': share.updated_at.isoformat(),
    }


def _normalize_share_constraints(value: Any) -> dict[str, Any] | None:
    constraints = value or {}
    if not isinstance(constraints, dict):
        return None
    normalized = dict(constraints)
    masking_profile = normalized.get('masking_profile')
    if masking_profile is not None and not isinstance(masking_profile, str):
        return None
    row_filters = normalized.get('row_filters')
    if row_filters is not None:
        parsed = _parse_string_list(row_filters)
        if parsed is None:
            return None
        normalized['row_filters'] = parsed
    allowed_regions = normalized.get('allowed_regions')
    if allowed_regions is not None:
        parsed = _parse_string_list(allowed_regions)
        if parsed is None:
            return None
        normalized['allowed_regions'] = parsed
    return normalized


def _refresh_share_expiry(share: DataShare):
    if (
        share.expires_at
        and share.status in {
            DataShare.Status.DRAFT,
            DataShare.Status.APPROVED,
            DataShare.Status.ACTIVE,
        }
        and share.expires_at <= timezone.now()
    ):
        share.status = DataShare.Status.EXPIRED
        share.save(update_fields=['status', 'updated_at'])


def _parse_int_clamped(value: str | None, *, default: int, min_value: int, max_value: int) -> int | None:
    if value is None or value == '':
        return default
    try:
        parsed = int(value)
    except ValueError:
        return None
    return min(max(parsed, min_value), max_value)


@csrf_exempt
def search_assets(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'tenant.admin'})
    if forbidden:
        return forbidden

    query = (request.GET.get('q') or '').strip()
    if not query:
        return JsonResponse({'error': 'q is required'}, status=400)

    try:
        limit = int(request.GET.get('limit', '100'))
        offset = int(request.GET.get('offset', '0'))
    except ValueError:
        return JsonResponse({'error': 'limit/offset must be integers'}, status=400)
    limit = min(max(limit, 1), 500)
    offset = max(offset, 0)

    query_lower = query.lower()
    qs = DataAsset.objects.filter(
        Q(display_name__icontains=query)
        | Q(qualified_name__icontains=query)
        | Q(description__icontains=query)
        | Q(asset_type__iexact=query)
        | Q(owner__iexact=query)
        | Q(tags__contains=[query])
        | Q(tags__contains=[query_lower])
        | Q(classifications__contains=[query])
        | Q(classifications__contains=[query_lower])
    ).order_by('-updated_at', 'id')

    count = qs.count()
    results = [_asset_to_dict(a) for a in qs[offset : offset + limit]]
    return JsonResponse({'count': count, 'results': results})


@csrf_exempt
def retention_rules(request):
    if request.method == 'GET':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        rules = RetentionRule.objects.order_by('-updated_at')
        return JsonResponse({'items': [_retention_rule_to_dict(r) for r in rules]})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        action = payload.get('action')
        retention_period = payload.get('retention_period')
        if action not in {RetentionRule.Action.ARCHIVE, RetentionRule.Action.DELETE}:
            return JsonResponse({'error': 'action must be archive or delete'}, status=400)
        if not _is_day_duration(retention_period):
            return JsonResponse({'error': 'retention_period must be ISO day duration (PnD)'}, status=400)
        grace_period = payload.get('grace_period') or ''
        if grace_period and not _is_day_duration(grace_period):
            return JsonResponse({'error': 'grace_period must be ISO day duration (PnD)'}, status=400)
        scope = payload.get('scope') or {}
        if not isinstance(scope, dict):
            return JsonResponse({'error': 'scope must be an object'}, status=400)

        rule = RetentionRule.objects.create(
            scope=scope,
            action=action,
            retention_period=retention_period,
            grace_period=grace_period,
        )
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='retention.rule.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.retention.rule.created',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_retention_rule_to_dict(rule),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='retention.rule.created',
            resource_type='retention_rule',
            resource_id=str(rule.id),
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_retention_rule_to_dict(rule),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_retention_rule_to_dict(rule), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def retention_holds(request):
    if request.method == 'GET':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        only_active = request.GET.get('active', 'true').lower() in {'1', 'true', 'yes'}
        qs = RetentionHold.objects.order_by('-created_at')
        if only_active:
            qs = qs.filter(active=True)
        return JsonResponse({'items': [_retention_hold_to_dict(h) for h in qs]})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        asset_id = payload.get('asset_id')
        if not asset_id:
            return JsonResponse({'error': 'asset_id is required'}, status=400)
        try:
            asset = DataAsset.objects.get(id=asset_id)
        except (ValidationError, DataAsset.DoesNotExist):
            return JsonResponse({'error': 'asset_not_found'}, status=404)
        hold = RetentionHold.objects.create(asset=asset, reason=(payload.get('reason') or ''))
        return JsonResponse(_retention_hold_to_dict(hold), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def retention_hold_release(request, hold_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        hold = RetentionHold.objects.get(id=hold_id)
    except (ValidationError, RetentionHold.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    hold.active = False
    hold.released_at = timezone.now()
    hold.save(update_fields=['active', 'released_at'])
    return JsonResponse(_retention_hold_to_dict(hold))


@csrf_exempt
def retention_runs(request):
    if request.method == 'GET':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        rule_id = request.GET.get('rule_id')
        runs = RetentionRun.objects.order_by('-created_at')
        if rule_id:
            runs = runs.filter(rule_id=rule_id)
        return JsonResponse({'items': [_retention_run_to_dict(r) for r in runs]})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        rule_id = payload.get('rule_id')
        mode = payload.get('mode') or RetentionRun.Mode.DRY_RUN
        if mode not in {RetentionRun.Mode.DRY_RUN, RetentionRun.Mode.EXECUTE}:
            return JsonResponse({'error': 'mode must be dry_run or execute'}, status=400)
        try:
            rule = RetentionRule.objects.get(id=rule_id)
        except (ValidationError, RetentionRule.DoesNotExist):
            return JsonResponse({'error': 'rule_not_found'}, status=404)
        run = RetentionRun.objects.create(rule=rule, mode=mode, status=RetentionRun.Status.STARTED)
        tenant_schema = _tenant_schema(request)
        result = execute_retention_run.apply(
            kwargs={
                'tenant_schema': tenant_schema,
                'run_id': str(run.id),
                'correlation_id': getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
                'user_id': request.headers.get('X-User-Id'),
                'request_id': request.headers.get('X-Request-Id') or request.headers.get('X-Request-ID'),
            }
        ).get(propagate=True)
        refreshed = RetentionRun.objects.get(id=run.id)
        return JsonResponse({'run': _retention_run_to_dict(refreshed), 'result': result}, status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def privacy_profiles(request):
    if request.method == 'GET':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        items = [_privacy_profile_to_dict(p) for p in PrivacyProfile.objects.order_by('-updated_at')]
        return JsonResponse({'items': items})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        name = payload.get('name')
        lawful_basis = payload.get('lawful_basis')
        if not name or not lawful_basis:
            return JsonResponse({'error': 'name and lawful_basis are required'}, status=400)
        if lawful_basis not in {
            PrivacyProfile.LawfulBasis.CONTRACT,
            PrivacyProfile.LawfulBasis.LEGAL_OBLIGATION,
            PrivacyProfile.LawfulBasis.CONSENT,
            PrivacyProfile.LawfulBasis.LEGITIMATE_INTEREST,
        }:
            return JsonResponse({'error': 'invalid_lawful_basis'}, status=400)
        consent_state = payload.get('consent_state') or ConsentEvent.ConsentState.UNKNOWN
        if consent_state not in {
            ConsentEvent.ConsentState.UNKNOWN,
            ConsentEvent.ConsentState.GRANTED,
            ConsentEvent.ConsentState.WITHDRAWN,
            ConsentEvent.ConsentState.EXPIRED,
        }:
            return JsonResponse({'error': 'invalid_consent_state'}, status=400)
        privacy_flags = payload.get('privacy_flags') or []
        if not isinstance(privacy_flags, list) or any(not isinstance(flag, str) for flag in privacy_flags):
            return JsonResponse({'error': 'privacy_flags must be an array of strings'}, status=400)

        profile = PrivacyProfile.objects.create(
            name=name,
            lawful_basis=lawful_basis,
            consent_required=bool(payload.get('consent_required', False)),
            consent_state=consent_state,
            privacy_flags=privacy_flags,
        )
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='privacy.profile.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.privacy.profile.created',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_privacy_profile_to_dict(profile),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='privacy.profile.created',
            resource_type='privacy_profile',
            resource_id=str(profile.id),
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_privacy_profile_to_dict(profile),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_privacy_profile_to_dict(profile), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def privacy_profile_detail(request, profile_id: str):
    try:
        profile = PrivacyProfile.objects.get(id=profile_id)
    except (ValidationError, PrivacyProfile.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)

    if request.method == 'GET':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        return JsonResponse(_privacy_profile_to_dict(profile))

    if request.method == 'PATCH':
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        if 'name' in payload:
            profile.name = payload['name']
        if 'lawful_basis' in payload:
            lawful_basis = payload['lawful_basis']
            if lawful_basis not in {
                PrivacyProfile.LawfulBasis.CONTRACT,
                PrivacyProfile.LawfulBasis.LEGAL_OBLIGATION,
                PrivacyProfile.LawfulBasis.CONSENT,
                PrivacyProfile.LawfulBasis.LEGITIMATE_INTEREST,
            }:
                return JsonResponse({'error': 'invalid_lawful_basis'}, status=400)
            profile.lawful_basis = lawful_basis
        if 'consent_required' in payload:
            profile.consent_required = bool(payload['consent_required'])
        if 'consent_state' in payload:
            consent_state = payload['consent_state']
            if consent_state not in {
                ConsentEvent.ConsentState.UNKNOWN,
                ConsentEvent.ConsentState.GRANTED,
                ConsentEvent.ConsentState.WITHDRAWN,
                ConsentEvent.ConsentState.EXPIRED,
            }:
                return JsonResponse({'error': 'invalid_consent_state'}, status=400)
            profile.consent_state = consent_state
        if 'privacy_flags' in payload:
            flags = payload['privacy_flags']
            if not isinstance(flags, list) or any(not isinstance(flag, str) for flag in flags):
                return JsonResponse({'error': 'privacy_flags must be an array of strings'}, status=400)
            profile.privacy_flags = flags
        profile.save()
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='privacy.profile.updated',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.privacy.profile.updated',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_privacy_profile_to_dict(profile),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='privacy.profile.updated',
            resource_type='privacy_profile',
            resource_id=str(profile.id),
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_privacy_profile_to_dict(profile),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_privacy_profile_to_dict(profile))

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def privacy_consent_events(request):
    if request.method == 'GET':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        profile_id = request.GET.get('profile_id')
        qs = ConsentEvent.objects.order_by('-created_at')
        if profile_id:
            qs = qs.filter(profile_id=profile_id)
        return JsonResponse({'items': [_consent_event_to_dict(e) for e in qs]})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        profile_id = payload.get('profile_id')
        consent_state = payload.get('consent_state')
        if not profile_id or not consent_state:
            return JsonResponse({'error': 'profile_id and consent_state are required'}, status=400)
        if consent_state not in {
            ConsentEvent.ConsentState.UNKNOWN,
            ConsentEvent.ConsentState.GRANTED,
            ConsentEvent.ConsentState.WITHDRAWN,
            ConsentEvent.ConsentState.EXPIRED,
        }:
            return JsonResponse({'error': 'invalid_consent_state'}, status=400)
        try:
            profile = PrivacyProfile.objects.get(id=profile_id)
        except (ValidationError, PrivacyProfile.DoesNotExist):
            return JsonResponse({'error': 'profile_not_found'}, status=404)

        event = ConsentEvent.objects.create(
            profile=profile,
            consent_state=consent_state,
            reason=payload.get('reason') or '',
        )
        profile.consent_state = consent_state
        profile.save(update_fields=['consent_state', 'updated_at'])
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='privacy.consent.changed',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.privacy.consent.changed',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data={'profile': _privacy_profile_to_dict(profile), 'consent_event': _consent_event_to_dict(event)},
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        if consent_state in {ConsentEvent.ConsentState.WITHDRAWN, ConsentEvent.ConsentState.EXPIRED}:
            action_types = ['policy.re_evaluate', 'retention.review', 'stewardship.triage']
            actions = [
                PrivacyAction.objects.create(
                    profile=profile,
                    action_type=action_type,
                    status=PrivacyAction.Status.REQUESTED,
                    reason=payload.get('reason') or '',
                    actor_id=(request.headers.get('X-User-Id') or ''),
                )
                for action_type in action_types
            ]
            maybe_publish_event(
                event_type='privacy.action.required',
                tenant_id=tenant_schema,
                routing_key=f'{tenant_schema}.privacy.action.required',
                correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
                user_id=request.headers.get('X-User-Id'),
                data={
                    'profile_id': str(profile.id),
                    'consent_state': consent_state,
                    'actions': action_types,
                    'action_ids': [str(action.id) for action in actions],
                },
                rabbitmq_url=os.environ.get('RABBITMQ_URL'),
            )
        return JsonResponse(_consent_event_to_dict(event), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def privacy_actions(request):
    if request.method == 'GET':
        forbidden = require_any_role(
            request, {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'}
        )
        if forbidden:
            return forbidden
        qs = PrivacyAction.objects.order_by('-requested_at')
        profile_id = request.GET.get('profile_id')
        if profile_id:
            qs = qs.filter(profile_id=profile_id)
        status_filter = request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        action_type = request.GET.get('action_type')
        if action_type:
            qs = qs.filter(action_type=action_type)
        return JsonResponse({'items': [_privacy_action_to_dict(item) for item in qs]})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        profile_id = payload.get('profile_id')
        action_type = (payload.get('action_type') or '').strip()
        if not profile_id or not action_type:
            return JsonResponse({'error': 'profile_id and action_type are required'}, status=400)
        try:
            profile = PrivacyProfile.objects.get(id=profile_id)
        except (ValidationError, PrivacyProfile.DoesNotExist):
            return JsonResponse({'error': 'profile_not_found'}, status=404)
        action = PrivacyAction.objects.create(
            profile=profile,
            action_type=action_type,
            status=PrivacyAction.Status.REQUESTED,
            reason=payload.get('reason') or '',
            actor_id=(request.headers.get('X-User-Id') or ''),
        )
        return JsonResponse(_privacy_action_to_dict(action), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def privacy_action_decision(request, action_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        action = PrivacyAction.objects.get(id=action_id)
    except (ValidationError, PrivacyAction.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    decision = payload.get('decision')
    if decision not in {'approve', 'reject'}:
        return JsonResponse({'error': 'invalid_decision'}, status=400)
    if action.status != PrivacyAction.Status.REQUESTED:
        return JsonResponse({'error': 'action_not_pending'}, status=400)
    action.status = (
        PrivacyAction.Status.APPROVED if decision == 'approve' else PrivacyAction.Status.REJECTED
    )
    action.reason = payload.get('reason') or action.reason
    action.actor_id = request.headers.get('X-User-Id') or action.actor_id
    action.decided_at = timezone.now()
    action.save(update_fields=['status', 'reason', 'actor_id', 'decided_at'])
    tenant_schema = _tenant_schema(request)
    event_type = f'privacy.action.{action.status}'
    payload_data = _privacy_action_to_dict(action)
    maybe_publish_event(
        event_type=event_type,
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.{event_type}',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=payload_data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action=event_type,
        resource_type='privacy_action',
        resource_id=str(action.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=payload_data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(payload_data)


@csrf_exempt
def privacy_action_execute(request, action_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        action = PrivacyAction.objects.get(id=action_id)
    except (ValidationError, PrivacyAction.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    if action.status != PrivacyAction.Status.APPROVED:
        return JsonResponse({'error': 'action_not_approved'}, status=400)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    evidence = payload.get('evidence') or {}
    if not isinstance(evidence, dict):
        return JsonResponse({'error': 'evidence must be an object'}, status=400)
    action.evidence = evidence
    action.actor_id = request.headers.get('X-User-Id') or action.actor_id
    action.status = PrivacyAction.Status.EXECUTED
    action.executed_at = timezone.now()
    action.save(update_fields=['evidence', 'actor_id', 'status', 'executed_at'])
    tenant_schema = _tenant_schema(request)
    payload_data = _privacy_action_to_dict(action)
    maybe_publish_event(
        event_type='privacy.action.executed',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.privacy.action.executed',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=payload_data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='privacy.action.executed',
        resource_type='privacy_action',
        resource_id=str(action.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=payload_data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(payload_data)


@csrf_exempt
def agent_runs(request):
    if request.method == 'GET':
        forbidden = require_any_role(
            request, {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'}
        )
        if forbidden:
            return forbidden
        qs = AgentRun.objects.order_by('-created_at')
        status_filter = request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return JsonResponse({'items': [_agent_run_to_dict(item) for item in qs]})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'catalog.editor', 'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        prompt = (payload.get('prompt') or '').strip()
        if not prompt:
            return JsonResponse({'error': 'prompt is required'}, status=400)
        allowed_tools = payload.get('allowed_tools', [])
        if not isinstance(allowed_tools, list) or not all(
            isinstance(item, str) and item for item in allowed_tools
        ):
            return JsonResponse({'error': 'allowed_tools must be a list of strings'}, status=400)
        invalid_tools = sorted(set(allowed_tools) - AGENT_TOOL_ALLOWLIST)
        if invalid_tools:
            return JsonResponse({'error': 'invalid_allowed_tools', 'details': invalid_tools}, status=400)
        timeout_seconds = payload.get('timeout_seconds', 60)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'timeout_seconds must be an integer'}, status=400)
        if timeout_seconds < 5 or timeout_seconds > 3600:
            return JsonResponse({'error': 'timeout_seconds out of range'}, status=400)
        now = timezone.now()
        status = AgentRun.Status.QUEUED
        started_at = None
        finished_at = None
        if payload.get('start_now'):
            status = AgentRun.Status.RUNNING
            started_at = now
        agent_run = AgentRun.objects.create(
            actor_id=(request.headers.get('X-User-Id') or ''),
            prompt=prompt,
            allowed_tools=sorted(set(allowed_tools)),
            timeout_seconds=timeout_seconds,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            output=payload.get('output') if isinstance(payload.get('output'), dict) else {},
        )
        tenant_schema = _tenant_schema(request)
        payload_data = _agent_run_to_dict(agent_run)
        maybe_publish_event(
            event_type='agent.run.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.agent.run.created',
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=payload_data,
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='agent.run.created',
            resource_type='agent_run',
            resource_id=str(agent_run.id),
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=payload_data,
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(payload_data, status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def agent_run_transition(request, run_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'catalog.editor', 'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        agent_run = AgentRun.objects.get(id=run_id)
    except (ValidationError, AgentRun.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    action = payload.get('action')
    now = timezone.now()
    if action == 'start':
        if agent_run.status != AgentRun.Status.QUEUED:
            return JsonResponse({'error': 'invalid_status_transition'}, status=400)
        agent_run.status = AgentRun.Status.RUNNING
        agent_run.started_at = now
        update_fields = ['status', 'started_at', 'updated_at']
    elif action == 'complete':
        if agent_run.status != AgentRun.Status.RUNNING:
            return JsonResponse({'error': 'invalid_status_transition'}, status=400)
        output = payload.get('output') or {}
        if not isinstance(output, dict):
            return JsonResponse({'error': 'output must be an object'}, status=400)
        agent_run.status = AgentRun.Status.COMPLETED
        agent_run.output = output
        agent_run.error_message = ''
        agent_run.finished_at = now
        update_fields = ['status', 'output', 'error_message', 'finished_at', 'updated_at']
    elif action == 'fail':
        if agent_run.status != AgentRun.Status.RUNNING:
            return JsonResponse({'error': 'invalid_status_transition'}, status=400)
        error_message = (payload.get('error_message') or '').strip()
        if not error_message:
            return JsonResponse({'error': 'error_message is required'}, status=400)
        agent_run.status = AgentRun.Status.FAILED
        agent_run.error_message = error_message
        agent_run.finished_at = now
        update_fields = ['status', 'error_message', 'finished_at', 'updated_at']
    elif action == 'cancel':
        if agent_run.status not in {AgentRun.Status.QUEUED, AgentRun.Status.RUNNING}:
            return JsonResponse({'error': 'invalid_status_transition'}, status=400)
        agent_run.status = AgentRun.Status.CANCELLED
        if not agent_run.started_at:
            agent_run.started_at = now
        agent_run.finished_at = now
        update_fields = ['status', 'started_at', 'finished_at', 'updated_at']
    elif action == 'materialize_timeouts':
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        if agent_run.status != AgentRun.Status.RUNNING or not agent_run.started_at:
            return JsonResponse({'error': 'invalid_status_transition'}, status=400)
        deadline = agent_run.started_at + timedelta(seconds=agent_run.timeout_seconds)
        if now < deadline:
            return JsonResponse({'error': 'run_not_timed_out'}, status=400)
        agent_run.status = AgentRun.Status.TIMED_OUT
        agent_run.error_message = 'execution timed out'
        agent_run.finished_at = now
        update_fields = ['status', 'error_message', 'finished_at', 'updated_at']
    else:
        return JsonResponse({'error': 'invalid_action'}, status=400)
    agent_run.save(update_fields=update_fields)
    tenant_schema = _tenant_schema(request)
    event_type = f'agent.run.{agent_run.status}'
    payload_data = _agent_run_to_dict(agent_run)
    maybe_publish_event(
        event_type=event_type,
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.{event_type}',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=payload_data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action=event_type,
        resource_type='agent_run',
        resource_id=str(agent_run.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=payload_data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(payload_data)


@csrf_exempt
def stewardship_items(request):
    if request.method == 'GET':
        forbidden = require_any_role(
            request, {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'}
        )
        if forbidden:
            return forbidden
        qs = StewardshipItem.objects.order_by('-created_at')
        status_filter = request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        severity_filter = request.GET.get('severity')
        if severity_filter:
            qs = qs.filter(severity=severity_filter)
        item_type_filter = request.GET.get('item_type')
        if item_type_filter:
            qs = qs.filter(item_type=item_type_filter)
        assignee_filter = request.GET.get('assignee')
        if assignee_filter:
            qs = qs.filter(assignee=assignee_filter)
        return JsonResponse({'items': [_stewardship_item_to_dict(item) for item in qs]})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'catalog.editor', 'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        item_type = payload.get('item_type')
        subject_ref = (payload.get('subject_ref') or '').strip()
        severity = payload.get('severity') or StewardshipItem.Severity.MEDIUM
        if item_type not in StewardshipItem.ItemType.values:
            return JsonResponse({'error': 'invalid_item_type'}, status=400)
        if severity not in StewardshipItem.Severity.values:
            return JsonResponse({'error': 'invalid_severity'}, status=400)
        if not subject_ref:
            return JsonResponse({'error': 'subject_ref is required'}, status=400)
        due_at = None
        due_at_value = payload.get('due_at')
        if due_at_value is not None:
            if not isinstance(due_at_value, str):
                return JsonResponse({'error': 'due_at must be an ISO datetime string'}, status=400)
            due_at = parse_datetime(due_at_value)
            if due_at is None:
                return JsonResponse({'error': 'invalid_due_at'}, status=400)
        item = StewardshipItem.objects.create(
            item_type=item_type,
            subject_ref=subject_ref,
            severity=severity,
            assignee=(payload.get('assignee') or ''),
            due_at=due_at,
            status=StewardshipItem.Status.OPEN,
            actor_id=(request.headers.get('X-User-Id') or ''),
        )
        tenant_schema = _tenant_schema(request)
        payload_data = _stewardship_item_to_dict(item)
        maybe_publish_event(
            event_type='stewardship.item.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.stewardship.item.created',
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=payload_data,
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='stewardship.item.created',
            resource_type='stewardship_item',
            resource_id=str(item.id),
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=payload_data,
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(payload_data, status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


def _stewardship_transition_allowed(item: StewardshipItem, action: str) -> bool:
    allowed = {
        StewardshipItem.Status.OPEN: {'start_review', 'block', 'resolve', 'dismiss'},
        StewardshipItem.Status.IN_REVIEW: {'block', 'resolve', 'dismiss'},
        StewardshipItem.Status.BLOCKED: {'start_review', 'resolve', 'dismiss'},
        StewardshipItem.Status.RESOLVED: {'reopen'},
        StewardshipItem.Status.DISMISSED: {'reopen'},
    }
    return action in allowed.get(item.status, set())


@csrf_exempt
def stewardship_item_transition(request, item_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        item = StewardshipItem.objects.get(id=item_id)
    except (ValidationError, StewardshipItem.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    action = payload.get('action')
    if action not in {'assign', 'start_review', 'block', 'resolve', 'dismiss', 'reopen'}:
        return JsonResponse({'error': 'invalid_action'}, status=400)

    update_fields = ['updated_at']
    if action == 'assign':
        assignee = (payload.get('assignee') or '').strip()
        if not assignee:
            return JsonResponse({'error': 'assignee is required'}, status=400)
        item.assignee = assignee
        item.actor_id = request.headers.get('X-User-Id') or item.actor_id
        update_fields.extend(['assignee', 'actor_id'])
        event_type = 'stewardship.item.assigned'
    else:
        if not _stewardship_transition_allowed(item, action):
            return JsonResponse({'error': 'invalid_transition'}, status=400)
        if action == 'start_review':
            item.status = StewardshipItem.Status.IN_REVIEW
            item.resolved_at = None
        elif action == 'block':
            item.status = StewardshipItem.Status.BLOCKED
            item.resolved_at = None
        elif action == 'resolve':
            resolution = payload.get('resolution') or {}
            if not isinstance(resolution, dict):
                return JsonResponse({'error': 'resolution must be an object'}, status=400)
            item.status = StewardshipItem.Status.RESOLVED
            item.resolution = resolution
            item.resolved_at = timezone.now()
            update_fields.append('resolution')
        elif action == 'dismiss':
            item.status = StewardshipItem.Status.DISMISSED
            item.resolved_at = timezone.now()
        else:
            item.status = StewardshipItem.Status.OPEN
            item.resolution = {}
            item.resolved_at = None
            update_fields.append('resolution')
        item.actor_id = request.headers.get('X-User-Id') or item.actor_id
        update_fields.extend(['status', 'resolved_at', 'actor_id'])
        event_type = (
            'stewardship.item.resolved'
            if item.status == StewardshipItem.Status.RESOLVED
            else 'stewardship.item.transitioned'
        )
    item.save(update_fields=update_fields)

    tenant_schema = _tenant_schema(request)
    payload_data = _stewardship_item_to_dict(item)
    maybe_publish_event(
        event_type=event_type,
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.{event_type}',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data={**payload_data, 'transition_action': action},
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action=event_type,
        resource_type='stewardship_item',
        resource_id=str(item.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data={**payload_data, 'transition_action': action},
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(payload_data)


@csrf_exempt
def residency_profiles(request):
    if request.method == 'GET':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        qs = ResidencyProfile.objects.order_by('-updated_at')
        return JsonResponse({'items': [_residency_profile_to_dict(p) for p in qs]})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        name = (payload.get('name') or '').strip()
        if not name:
            return JsonResponse({'error': 'name is required'}, status=400)

        allowed_regions = payload.get('allowed_regions')
        blocked_regions = payload.get('blocked_regions')
        if allowed_regions is None:
            allowed_regions = []
        if blocked_regions is None:
            blocked_regions = []
        if not isinstance(allowed_regions, list) or any(not isinstance(v, str) for v in allowed_regions):
            return JsonResponse({'error': 'allowed_regions must be a list of strings'}, status=400)
        if not isinstance(blocked_regions, list) or any(not isinstance(v, str) for v in blocked_regions):
            return JsonResponse({'error': 'blocked_regions must be a list of strings'}, status=400)

        enforcement_mode = payload.get('enforcement_mode', ResidencyProfile.EnforcementMode.ADVISORY)
        if enforcement_mode not in {ResidencyProfile.EnforcementMode.ADVISORY, ResidencyProfile.EnforcementMode.ENFORCED}:
            return JsonResponse({'error': 'invalid_enforcement_mode'}, status=400)

        profile = ResidencyProfile.objects.create(
            name=name,
            allowed_regions=allowed_regions,
            blocked_regions=blocked_regions,
            enforcement_mode=enforcement_mode,
            status=ResidencyProfile.Status.DRAFT,
        )
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='residency.profile.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.residency.profile.created',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_residency_profile_to_dict(profile),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='residency.profile.created',
            resource_type='residency_profile',
            resource_id=str(profile.id),
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_residency_profile_to_dict(profile),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_residency_profile_to_dict(profile), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def residency_profile_detail(request, profile_id: str):
    try:
        profile = ResidencyProfile.objects.get(id=profile_id)
    except (ValidationError, ResidencyProfile.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)

    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    return JsonResponse(_residency_profile_to_dict(profile))


@csrf_exempt
def residency_profile_activate(request, profile_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        profile = ResidencyProfile.objects.get(id=profile_id)
    except (ValidationError, ResidencyProfile.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    profile.status = ResidencyProfile.Status.ACTIVE
    profile.save(update_fields=['status', 'updated_at'])
    tenant_schema = _tenant_schema(request)
    maybe_publish_event(
        event_type='residency.profile.activated',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.residency.profile.activated',
        correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_residency_profile_to_dict(profile),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='residency.profile.activated',
        resource_type='residency_profile',
        resource_id=str(profile.id),
        correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_residency_profile_to_dict(profile),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(_residency_profile_to_dict(profile))


@csrf_exempt
def residency_profile_deprecate(request, profile_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        profile = ResidencyProfile.objects.get(id=profile_id)
    except (ValidationError, ResidencyProfile.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    profile.status = ResidencyProfile.Status.DEPRECATED
    profile.save(update_fields=['status', 'updated_at'])
    tenant_schema = _tenant_schema(request)
    maybe_publish_event(
        event_type='residency.profile.deprecated',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.residency.profile.deprecated',
        correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_residency_profile_to_dict(profile),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='residency.profile.deprecated',
        resource_type='residency_profile',
        resource_id=str(profile.id),
        correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_residency_profile_to_dict(profile),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(_residency_profile_to_dict(profile))


@csrf_exempt
def residency_check(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'catalog.editor', 'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    profile_id = payload.get('profile_id')
    target_region = payload.get('target_region')
    if not profile_id or not isinstance(target_region, str):
        return JsonResponse({'error': 'profile_id and target_region are required'}, status=400)
    try:
        profile = ResidencyProfile.objects.get(id=profile_id)
    except (ValidationError, ResidencyProfile.DoesNotExist):
        return JsonResponse({'error': 'profile_not_found'}, status=404)

    denied_by_block = target_region in set(profile.blocked_regions or [])
    denied_by_allow = bool(profile.allowed_regions) and target_region not in set(profile.allowed_regions)
    allowed = not (denied_by_block or denied_by_allow)
    denied_reason = ''
    if denied_by_block:
        denied_reason = 'blocked_region'
    elif denied_by_allow:
        denied_reason = 'outside_allowed_regions'
    enforced = profile.enforcement_mode == ResidencyProfile.EnforcementMode.ENFORCED
    response = {
        'profile_id': str(profile.id),
        'target_region': target_region,
        'allowed': allowed,
        'decision': 'allow' if allowed else 'deny',
        'enforced': enforced,
        'status': profile.status,
    }
    if denied_reason:
        response['reason'] = denied_reason
    if not allowed:
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='residency.violation.detected',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.residency.violation.detected',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=response,
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='residency.violation.detected',
            resource_type='residency_profile',
            resource_id=str(profile.id),
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=response,
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
    if not allowed and enforced:
        return JsonResponse(response, status=403)
    return JsonResponse(response)


@csrf_exempt
def access_requests(request):
    if request.method == 'GET':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        status_filter = request.GET.get('status')
        qs = AccessRequest.objects.order_by('-updated_at')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return JsonResponse({'items': [_access_request_to_dict(item) for item in qs]})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        subject_ref = (payload.get('subject_ref') or '').strip()
        requester = (payload.get('requester') or request.headers.get('X-User-Id') or '').strip()
        access_type = payload.get('access_type')
        if not subject_ref or not requester or not access_type:
            return JsonResponse({'error': 'subject_ref, requester, and access_type are required'}, status=400)
        if access_type not in {
            AccessRequest.AccessType.READ,
            AccessRequest.AccessType.WRITE,
            AccessRequest.AccessType.ADMIN,
            AccessRequest.AccessType.EXPORT,
        }:
            return JsonResponse({'error': 'invalid_access_type'}, status=400)
        access_request = AccessRequest.objects.create(
            subject_ref=subject_ref,
            requester=requester,
            access_type=access_type,
            justification=(payload.get('justification') or ''),
            status=AccessRequest.Status.SUBMITTED,
        )
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='access.request.submitted',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.access.request.submitted',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_access_request_to_dict(access_request),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='access.request.submitted',
            resource_type='access_request',
            resource_id=str(access_request.id),
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_access_request_to_dict(access_request),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_access_request_to_dict(access_request), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def access_request_decision(request, request_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        access_request = AccessRequest.objects.get(id=request_id)
    except (ValidationError, AccessRequest.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    status_value = payload.get('status')
    if status_value not in {
        AccessRequest.Status.IN_REVIEW,
        AccessRequest.Status.APPROVED,
        AccessRequest.Status.DENIED,
        AccessRequest.Status.REVOKED,
    }:
        return JsonResponse({'error': 'invalid_status'}, status=400)

    allowed_transitions = {
        AccessRequest.Status.SUBMITTED: {AccessRequest.Status.IN_REVIEW, AccessRequest.Status.APPROVED, AccessRequest.Status.DENIED},
        AccessRequest.Status.IN_REVIEW: {AccessRequest.Status.APPROVED, AccessRequest.Status.DENIED},
        AccessRequest.Status.APPROVED: {AccessRequest.Status.REVOKED},
    }
    if status_value not in allowed_transitions.get(access_request.status, set()):
        return JsonResponse({'error': 'invalid_transition'}, status=400)

    expires_at = access_request.expires_at
    if status_value == AccessRequest.Status.APPROVED and 'expires_at' in payload and payload.get('expires_at'):
        parsed = parse_datetime(str(payload.get('expires_at')))
        if not parsed:
            return JsonResponse({'error': 'invalid_expires_at'}, status=400)
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        expires_at = parsed

    access_request.status = status_value
    access_request.approver = (payload.get('approver') or request.headers.get('X-User-Id') or '').strip()
    access_request.expires_at = expires_at if status_value == AccessRequest.Status.APPROVED else access_request.expires_at
    access_request.save(update_fields=['status', 'approver', 'expires_at', 'updated_at'])
    tenant_schema = _tenant_schema(request)
    event_type = f'access.request.{status_value}'
    maybe_publish_event(
        event_type=event_type,
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.{event_type}',
        correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_access_request_to_dict(access_request),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action=event_type,
        resource_type='access_request',
        resource_id=str(access_request.id),
        correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_access_request_to_dict(access_request),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(_access_request_to_dict(access_request))


@csrf_exempt
def data_shares(request):
    if request.method == 'GET':
        forbidden = require_any_role(
            request,
            {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        qs = DataShare.objects.order_by('-updated_at')
        status_filter = request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        asset_id = request.GET.get('asset_id')
        if asset_id:
            qs = qs.filter(asset_id=asset_id)
        items = []
        for share in qs:
            _refresh_share_expiry(share)
            items.append(_data_share_to_dict(share))
        return JsonResponse({'items': items})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'catalog.editor', 'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        asset_id = payload.get('asset_id')
        consumer_ref = (payload.get('consumer_ref') or '').strip()
        if not asset_id or not consumer_ref:
            return JsonResponse({'error': 'asset_id and consumer_ref are required'}, status=400)
        try:
            asset = DataAsset.objects.get(id=asset_id)
        except (ValidationError, DataAsset.DoesNotExist):
            return JsonResponse({'error': 'asset_not_found'}, status=404)
        linked_access_request_ids = _parse_uuid_string_list(payload.get('linked_access_request_ids'))
        if linked_access_request_ids is None:
            return JsonResponse(
                {'error': 'linked_access_request_ids must be an array of UUID strings'},
                status=400,
            )
        constraints = _normalize_share_constraints(payload.get('constraints'))
        if constraints is None:
            return JsonResponse({'error': 'invalid_constraints'}, status=400)
        expires_at = None
        if payload.get('expires_at'):
            parsed = parse_datetime(str(payload.get('expires_at')))
            if not parsed:
                return JsonResponse({'error': 'invalid_expires_at'}, status=400)
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            expires_at = parsed
        share = DataShare.objects.create(
            asset=asset,
            consumer_ref=consumer_ref,
            purpose=(payload.get('purpose') or ''),
            constraints=constraints,
            linked_access_request_ids=linked_access_request_ids,
            status=DataShare.Status.DRAFT,
            expires_at=expires_at,
        )
        tenant_schema = _tenant_schema(request)
        data = _data_share_to_dict(share)
        maybe_publish_event(
            event_type='data_share.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.data_share.created',
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=data,
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='data_share.created',
            resource_type='data_share',
            resource_id=str(share.id),
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=data,
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(data, status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def data_share_detail(request, share_id: str):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(
        request,
        {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
    )
    if forbidden:
        return forbidden
    try:
        share = DataShare.objects.get(id=share_id)
    except (ValidationError, DataShare.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    _refresh_share_expiry(share)
    return JsonResponse(_data_share_to_dict(share))


@csrf_exempt
def data_share_transition(request, share_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        share = DataShare.objects.get(id=share_id)
    except (ValidationError, DataShare.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    _refresh_share_expiry(share)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    action = payload.get('action')
    if action not in {'approve', 'activate', 'revoke'}:
        return JsonResponse({'error': 'invalid_action'}, status=400)
    transitions = {
        DataShare.Status.DRAFT: {'approve'},
        DataShare.Status.APPROVED: {'activate', 'revoke'},
        DataShare.Status.ACTIVE: {'revoke'},
    }
    if action not in transitions.get(share.status, set()):
        return JsonResponse({'error': 'invalid_transition'}, status=400)
    if action == 'approve':
        share.status = DataShare.Status.APPROVED
        share.approved_by = (payload.get('approver') or request.headers.get('X-User-Id') or '').strip()
        event_type = 'data_share.approved'
    elif action == 'activate':
        share.status = DataShare.Status.ACTIVE
        event_type = 'data_share.activated'
    else:
        share.status = DataShare.Status.REVOKED
        event_type = 'data_share.revoked'
    share.save(update_fields=['status', 'approved_by', 'updated_at'])
    tenant_schema = _tenant_schema(request)
    data = _data_share_to_dict(share)
    maybe_publish_event(
        event_type=event_type,
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.{event_type}',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action=event_type,
        resource_type='data_share',
        resource_id=str(share.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(data)


@csrf_exempt
def reference_datasets(request):
    if request.method == 'GET':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        datasets = ReferenceDataset.objects.order_by('-updated_at')
        return JsonResponse({'items': [_reference_dataset_to_dict(item) for item in datasets]})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        name = (payload.get('name') or '').strip()
        if not name:
            return JsonResponse({'error': 'name is required'}, status=400)
        dataset = ReferenceDataset.objects.create(
            name=name,
            owner=(payload.get('owner') or ''),
            domain=(payload.get('domain') or ''),
        )
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='reference.dataset.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.reference.dataset.created',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_reference_dataset_to_dict(dataset),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='reference.dataset.created',
            resource_type='reference_dataset',
            resource_id=str(dataset.id),
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_reference_dataset_to_dict(dataset),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_reference_dataset_to_dict(dataset), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def reference_dataset_versions(request, dataset_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        dataset = ReferenceDataset.objects.get(id=dataset_id)
    except (ValidationError, ReferenceDataset.DoesNotExist):
        return JsonResponse({'error': 'dataset_not_found'}, status=404)

    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    values = payload.get('values')
    if values is None:
        values = []
    if not isinstance(values, list):
        return JsonResponse({'error': 'values must be a list'}, status=400)

    version = payload.get('version')
    if version is None:
        version = (ReferenceDatasetVersion.objects.filter(dataset_id=dataset_id).aggregate(max_v=Max('version')).get('max_v') or 0) + 1
    elif not isinstance(version, int) or version < 1:
        return JsonResponse({'error': 'version must be a positive integer'}, status=400)

    status_value = payload.get('status') or ReferenceDatasetVersion.Status.DRAFT
    if status_value not in {ReferenceDatasetVersion.Status.DRAFT, ReferenceDatasetVersion.Status.APPROVED}:
        return JsonResponse({'error': 'status must be draft or approved'}, status=400)

    created = ReferenceDatasetVersion.objects.create(
        dataset=dataset,
        version=version,
        status=status_value,
        values=values,
    )
    tenant_schema = _tenant_schema(request)
    maybe_publish_event(
        event_type='reference.version.created',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.reference.version.created',
        correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_reference_dataset_version_to_dict(created),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='reference.version.created',
        resource_type='reference_dataset_version',
        resource_id=str(created.id),
        correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_reference_dataset_version_to_dict(created),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(_reference_dataset_version_to_dict(created), status=201)


@csrf_exempt
def reference_dataset_activate(request, dataset_id: str, version: int):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        target = ReferenceDatasetVersion.objects.get(dataset_id=dataset_id, version=version)
    except (ValidationError, ReferenceDatasetVersion.DoesNotExist):
        return JsonResponse({'error': 'version_not_found'}, status=404)

    ReferenceDatasetVersion.objects.filter(dataset_id=dataset_id, status=ReferenceDatasetVersion.Status.ACTIVE).exclude(
        id=target.id
    ).update(status=ReferenceDatasetVersion.Status.DEPRECATED, updated_at=timezone.now())
    target.status = ReferenceDatasetVersion.Status.ACTIVE
    target.save(update_fields=['status', 'updated_at'])

    tenant_schema = _tenant_schema(request)
    maybe_publish_event(
        event_type='reference.version.activated',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.reference.version.activated',
        correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_reference_dataset_version_to_dict(target),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='reference.version.activated',
        resource_type='reference_dataset_version',
        resource_id=str(target.id),
        correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_reference_dataset_version_to_dict(target),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(_reference_dataset_version_to_dict(target))


@csrf_exempt
def reference_dataset_version_values(request, dataset_id: str, version: int):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        dataset_version = ReferenceDatasetVersion.objects.get(dataset_id=dataset_id, version=version)
    except (ValidationError, ReferenceDatasetVersion.DoesNotExist):
        return JsonResponse({'error': 'version_not_found'}, status=404)
    return JsonResponse(
        {
            'dataset_id': str(dataset_version.dataset_id),
            'version': dataset_version.version,
            'values': dataset_version.values,
        }
    )


@csrf_exempt
def master_records(request, entity_type: str):
    if request.method == 'GET':
        forbidden = require_any_role(
            request,
            {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        qs = MasterRecord.objects.filter(entity_type=entity_type).order_by(
            '-updated_at'
        )
        master_id = request.GET.get('master_id')
        if master_id:
            qs = qs.filter(master_id=master_id)
        return JsonResponse({'items': [_master_record_to_dict(item) for item in qs]})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        attributes = payload.get('attributes') or {}
        survivorship_policy = payload.get('survivorship_policy') or {}
        if not isinstance(attributes, dict):
            return JsonResponse({'error': 'attributes must be an object'}, status=400)
        if not isinstance(survivorship_policy, dict):
            return JsonResponse(
                {'error': 'survivorship_policy must be an object'},
                status=400,
            )
        confidence = payload.get('confidence')
        if confidence is not None and not isinstance(confidence, (int, float)):
            return JsonResponse({'error': 'confidence must be numeric'}, status=400)

        status_value = payload.get('status') or MasterRecord.Status.ACTIVE
        if status_value not in {
            MasterRecord.Status.DRAFT,
            MasterRecord.Status.ACTIVE,
            MasterRecord.Status.ARCHIVED,
        }:
            return JsonResponse({'error': 'invalid_status'}, status=400)

        raw_master_id = payload.get('master_id')
        tenant_schema = _tenant_schema(request)
        if raw_master_id:
            try:
                master_id = uuid.UUID(str(raw_master_id))
            except ValueError:
                return JsonResponse({'error': 'invalid_master_id'}, status=400)
            latest = (
                MasterRecord.objects.filter(
                    entity_type=entity_type,
                    master_id=master_id,
                )
                .order_by('-version')
                .first()
            )
            if latest is None:
                return JsonResponse({'error': 'master_not_found'}, status=404)
            if status_value == MasterRecord.Status.ACTIVE:
                MasterRecord.objects.filter(
                    entity_type=entity_type,
                    master_id=master_id,
                    status=MasterRecord.Status.ACTIVE,
                ).update(status=MasterRecord.Status.SUPERSEDED, updated_at=timezone.now())
            created = MasterRecord.objects.create(
                entity_type=entity_type,
                master_id=master_id,
                version=latest.version + 1,
                attributes=attributes,
                survivorship_policy=survivorship_policy,
                confidence=float(confidence) if confidence is not None else None,
                status=status_value,
            )
            event_type = 'master-data.record.updated'
        else:
            created = MasterRecord.objects.create(
                entity_type=entity_type,
                version=1,
                attributes=attributes,
                survivorship_policy=survivorship_policy,
                confidence=float(confidence) if confidence is not None else None,
                status=status_value,
            )
            event_type = 'master-data.record.created'

        maybe_publish_event(
            event_type=event_type,
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.{event_type}',
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_master_record_to_dict(created),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action=event_type,
            resource_type='master_record',
            resource_id=str(created.id),
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_master_record_to_dict(created),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_master_record_to_dict(created), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def master_record_detail(request, entity_type: str, master_id: str):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(
        request,
        {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
    )
    if forbidden:
        return forbidden

    qs = MasterRecord.objects.filter(entity_type=entity_type, master_id=master_id)
    version = request.GET.get('version')
    if version:
        try:
            parsed_version = int(version)
        except ValueError:
            return JsonResponse({'error': 'version must be an integer'}, status=400)
        record = qs.filter(version=parsed_version).first()
    else:
        record = qs.order_by('-version').first()
    if record is None:
        return JsonResponse({'error': 'not_found'}, status=404)
    return JsonResponse(_master_record_to_dict(record))


@csrf_exempt
def master_merge_candidates(request, entity_type: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    target_master_id = payload.get('target_master_id')
    proposed_attributes = payload.get('proposed_attributes') or {}
    source_master_refs = payload.get('source_master_refs') or []
    confidence = payload.get('confidence')
    if not target_master_id:
        return JsonResponse({'error': 'target_master_id is required'}, status=400)
    if not isinstance(proposed_attributes, dict):
        return JsonResponse(
            {'error': 'proposed_attributes must be an object'},
            status=400,
        )
    if not isinstance(source_master_refs, list):
        return JsonResponse(
            {'error': 'source_master_refs must be a list'},
            status=400,
        )
    if confidence is not None and not isinstance(confidence, (int, float)):
        return JsonResponse({'error': 'confidence must be numeric'}, status=400)
    try:
        parsed_target_master_id = uuid.UUID(str(target_master_id))
    except ValueError:
        return JsonResponse({'error': 'invalid_target_master_id'}, status=400)
    if not MasterRecord.objects.filter(
        entity_type=entity_type,
        master_id=parsed_target_master_id,
    ).exists():
        return JsonResponse({'error': 'target_master_not_found'}, status=404)
    candidate = MasterMergeCandidate.objects.create(
        entity_type=entity_type,
        target_master_id=parsed_target_master_id,
        source_master_refs=source_master_refs,
        proposed_attributes=proposed_attributes,
        confidence=float(confidence) if confidence is not None else None,
    )
    return JsonResponse(_master_merge_candidate_to_dict(candidate), status=201)


@csrf_exempt
def master_merge_candidate_approve(request, entity_type: str, candidate_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        candidate = MasterMergeCandidate.objects.get(
            id=candidate_id,
            entity_type=entity_type,
        )
    except (ValidationError, MasterMergeCandidate.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    if candidate.status != MasterMergeCandidate.Status.PENDING:
        return JsonResponse({'error': 'candidate_not_pending'}, status=400)
    latest = (
        MasterRecord.objects.filter(
            entity_type=entity_type,
            master_id=candidate.target_master_id,
        )
        .order_by('-version')
        .first()
    )
    if latest is None:
        return JsonResponse({'error': 'target_master_not_found'}, status=404)
    MasterRecord.objects.filter(
        entity_type=entity_type,
        master_id=candidate.target_master_id,
        status=MasterRecord.Status.ACTIVE,
    ).update(status=MasterRecord.Status.SUPERSEDED, updated_at=timezone.now())
    merged = MasterRecord.objects.create(
        entity_type=entity_type,
        master_id=candidate.target_master_id,
        version=latest.version + 1,
        attributes=candidate.proposed_attributes,
        survivorship_policy=latest.survivorship_policy,
        confidence=candidate.confidence,
        status=MasterRecord.Status.ACTIVE,
    )
    candidate.status = MasterMergeCandidate.Status.APPROVED
    candidate.approved_by = (
        request.headers.get('X-User-Id')
        or request.headers.get('X-User-ID')
        or ''
    )
    candidate.save(update_fields=['status', 'approved_by', 'updated_at'])
    tenant_schema = _tenant_schema(request)
    maybe_publish_event(
        event_type='master-data.record.merged',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.master-data.record.merged',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data={
            'candidate': _master_merge_candidate_to_dict(candidate),
            'record': _master_record_to_dict(merged),
        },
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='master-data.record.merged',
        resource_type='master_record',
        resource_id=str(merged.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data={
            'candidate': _master_merge_candidate_to_dict(candidate),
            'record': _master_record_to_dict(merged),
        },
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(
        {
            'candidate': _master_merge_candidate_to_dict(candidate),
            'record': _master_record_to_dict(merged),
        }
    )


@csrf_exempt
def classifications(request):
    if request.method == 'GET':
        forbidden = require_any_role(
            request,
            {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        qs = Classification.objects.order_by('-updated_at')
        status_filter = request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return JsonResponse({'items': [_classification_to_dict(item) for item in qs]})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        name = (payload.get('name') or '').strip()
        if not name:
            return JsonResponse({'error': 'name is required'}, status=400)
        level = payload.get('level')
        if level not in {
            Classification.Level.PUBLIC,
            Classification.Level.INTERNAL,
            Classification.Level.CONFIDENTIAL,
            Classification.Level.RESTRICTED,
        }:
            return JsonResponse({'error': 'invalid_level'}, status=400)
        tags = _parse_string_list(payload.get('tags'))
        if tags is None:
            return JsonResponse({'error': 'tags must be an array of strings'}, status=400)

        classification = Classification.objects.create(
            name=name,
            level=level,
            description=(payload.get('description') or ''),
            tags=tags,
            status=Classification.Status.DRAFT,
        )
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='classification.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.classification.created',
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_classification_to_dict(classification),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='classification.created',
            resource_type='classification',
            resource_id=str(classification.id),
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_classification_to_dict(classification),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_classification_to_dict(classification), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def classification_detail(request, classification_id: str):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(
        request,
        {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
    )
    if forbidden:
        return forbidden
    try:
        classification = Classification.objects.get(id=classification_id)
    except (ValidationError, Classification.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    return JsonResponse(_classification_to_dict(classification))


@csrf_exempt
def classification_activate(request, classification_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        classification = Classification.objects.get(id=classification_id)
    except (ValidationError, Classification.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    classification.status = Classification.Status.ACTIVE
    classification.save(update_fields=['status', 'updated_at'])
    tenant_schema = _tenant_schema(request)
    maybe_publish_event(
        event_type='classification.activated',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.classification.activated',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_classification_to_dict(classification),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='classification.activated',
        resource_type='classification',
        resource_id=str(classification.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_classification_to_dict(classification),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(_classification_to_dict(classification))


@csrf_exempt
def classification_deprecate(request, classification_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        classification = Classification.objects.get(id=classification_id)
    except (ValidationError, Classification.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    classification.status = Classification.Status.DEPRECATED
    classification.save(update_fields=['status', 'updated_at'])
    tenant_schema = _tenant_schema(request)
    maybe_publish_event(
        event_type='classification.deprecated',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.classification.deprecated',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_classification_to_dict(classification),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='classification.deprecated',
        resource_type='classification',
        resource_id=str(classification.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_classification_to_dict(classification),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(_classification_to_dict(classification))


@csrf_exempt
def asset_classifications(request, asset_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_role(request, 'catalog.editor')
    if forbidden:
        return forbidden
    try:
        asset = DataAsset.objects.get(id=asset_id)
    except (ValidationError, DataAsset.DoesNotExist):
        return JsonResponse({'error': 'asset_not_found'}, status=404)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    classifications_value = _parse_string_list(payload.get('classifications'))
    if classifications_value is None:
        return JsonResponse(
            {'error': 'classifications must be an array of strings'},
            status=400,
        )
    selected = classifications_value or []
    invalid = _validate_classification_values(selected)
    if invalid:
        return JsonResponse(
            {'error': 'unknown_classifications', 'items': invalid},
            status=400,
        )
    if selected:
        active_names = set(
            Classification.objects.filter(
                status=Classification.Status.ACTIVE,
                name__in=selected,
            ).values_list('name', flat=True)
        )
        missing = sorted(set(selected) - active_names)
        if missing:
            return JsonResponse(
                {
                    'error': 'inactive_or_unknown_classifications',
                    'items': missing,
                },
                status=400,
            )
    forbidden = _enforce_sensitivity_upgrade_role(
        request,
        existing_values=asset.classifications or [],
        next_values=selected,
    )
    if forbidden:
        return forbidden
    asset.classifications = selected
    asset.save(update_fields=['classifications', 'updated_at'])
    tenant_schema = _tenant_schema(request)
    maybe_publish_event(
        event_type='asset.classification.changed',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.asset.classification.changed',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_asset_to_dict(asset),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='asset.classification.changed',
        resource_type='asset',
        resource_id=str(asset.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_asset_to_dict(asset),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(_asset_to_dict(asset))


@csrf_exempt
def print_jobs(request):
    if request.method == 'GET':
        forbidden = require_any_role(
            request,
            {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        status_filter = request.GET.get('status')
        qs = PrintJob.objects.order_by('-created_at')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return JsonResponse({'items': [_print_job_to_dict(item) for item in qs]})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        template_ref = (payload.get('template_ref') or '').strip()
        destination = (payload.get('destination') or '').strip()
        output_format = payload.get('output_format')
        if not template_ref or not destination or not output_format:
            return JsonResponse(
                {'error': 'template_ref, destination, and output_format are required'},
                status=400,
            )
        if output_format not in {PrintJob.Format.ZPL, PrintJob.Format.PDF}:
            return JsonResponse({'error': 'invalid_output_format'}, status=400)
        print_payload = payload.get('payload') or {}
        if not isinstance(print_payload, dict):
            return JsonResponse({'error': 'payload must be an object'}, status=400)

        print_job = PrintJob.objects.create(
            template_ref=template_ref,
            payload=print_payload,
            output_format=output_format,
            destination=destination,
            status=PrintJob.Status.PENDING,
        )
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='print.requested',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.print.requested',
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_print_job_to_dict(print_job),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='print.requested',
            resource_type='print_job',
            resource_id=str(print_job.id),
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_print_job_to_dict(print_job),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_print_job_to_dict(print_job), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def print_job_detail(request, job_id: str):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(
        request,
        {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
    )
    if forbidden:
        return forbidden
    try:
        print_job = PrintJob.objects.get(id=job_id)
    except (ValidationError, PrintJob.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    return JsonResponse(_print_job_to_dict(print_job))


@csrf_exempt
def print_job_status(request, job_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        print_job = PrintJob.objects.get(id=job_id)
    except (ValidationError, PrintJob.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    status_value = payload.get('status')
    if status_value not in {
        PrintJob.Status.RETRYING,
        PrintJob.Status.COMPLETED,
        PrintJob.Status.FAILED,
    }:
        return JsonResponse({'error': 'invalid_status'}, status=400)
    retry_count = payload.get('retry_count')
    if retry_count is not None and not isinstance(retry_count, int):
        return JsonResponse({'error': 'retry_count must be an integer'}, status=400)
    gateway_metadata = payload.get('gateway_metadata')
    if gateway_metadata is not None and not isinstance(gateway_metadata, dict):
        return JsonResponse(
            {'error': 'gateway_metadata must be an object'},
            status=400,
        )
    error_message = payload.get('error_message')
    if error_message is not None and not isinstance(error_message, str):
        return JsonResponse({'error': 'error_message must be a string'}, status=400)

    print_job.status = status_value
    if retry_count is not None:
        print_job.retry_count = retry_count
    if gateway_metadata is not None:
        print_job.gateway_metadata = gateway_metadata
    if error_message is not None:
        print_job.error_message = error_message
    print_job.save(
        update_fields=[
            'status',
            'retry_count',
            'gateway_metadata',
            'error_message',
            'updated_at',
        ]
    )
    tenant_schema = _tenant_schema(request)
    maybe_publish_event(
        event_type=f'print.{status_value}',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.print.{status_value}',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_print_job_to_dict(print_job),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action=f'print.{status_value}',
        resource_type='print_job',
        resource_id=str(print_job.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_print_job_to_dict(print_job),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(_print_job_to_dict(print_job))


@csrf_exempt
def collaboration_documents(request):
    if request.method == 'GET':
        forbidden = require_any_role(
            request,
            {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        documents = CollaborationDocument.objects.order_by('-updated_at')
        return JsonResponse(
            {'items': [_collaboration_document_to_dict(item) for item in documents]}
        )

    if request.method == 'POST':
        forbidden = require_any_role(request, {'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        title = (payload.get('title') or '').strip()
        object_key = (payload.get('object_key') or '').strip()
        if not title or not object_key:
            return JsonResponse(
                {'error': 'title and object_key are required'},
                status=400,
            )
        content_type = payload.get('content_type') or ''
        owner = payload.get('owner') or request.headers.get('X-User-Id') or ''
        if content_type and not isinstance(content_type, str):
            return JsonResponse({'error': 'content_type must be a string'}, status=400)
        if owner and not isinstance(owner, str):
            return JsonResponse({'error': 'owner must be a string'}, status=400)

        document = CollaborationDocument.objects.create(
            title=title,
            object_key=object_key,
            content_type=content_type,
            owner=owner,
            status='active',
        )
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='collaboration.document.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.collaboration.document.created',
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_collaboration_document_to_dict(document),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='collaboration.document.created',
            resource_type='collaboration_document',
            resource_id=str(document.id),
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_collaboration_document_to_dict(document),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_collaboration_document_to_dict(document), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def collaboration_document_detail(request, document_id: str):
    if request.method == 'GET':
        forbidden = require_any_role(
            request,
            {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        try:
            document = CollaborationDocument.objects.get(id=document_id)
        except (ValidationError, CollaborationDocument.DoesNotExist):
            return JsonResponse({'error': 'not_found'}, status=404)
        return JsonResponse(_collaboration_document_to_dict(document))

    if request.method == 'PATCH':
        forbidden = require_any_role(request, {'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
        try:
            document = CollaborationDocument.objects.get(id=document_id)
        except (ValidationError, CollaborationDocument.DoesNotExist):
            return JsonResponse({'error': 'not_found'}, status=404)
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        if 'title' in payload:
            title = payload.get('title')
            if not isinstance(title, str) or not title.strip():
                return JsonResponse({'error': 'title must be a non-empty string'}, status=400)
            document.title = title.strip()
        if 'owner' in payload:
            owner = payload.get('owner')
            if owner is not None and not isinstance(owner, str):
                return JsonResponse({'error': 'owner must be a string'}, status=400)
            document.owner = owner or ''
        document.save(update_fields=['title', 'owner', 'updated_at'])
        return JsonResponse(_collaboration_document_to_dict(document))

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def collaboration_document_session(request, document_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(
        request,
        {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
    )
    if forbidden:
        return forbidden
    try:
        document = CollaborationDocument.objects.get(id=document_id)
    except (ValidationError, CollaborationDocument.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    mode = payload.get('mode') or 'edit'
    if mode not in {'view', 'edit'}:
        return JsonResponse({'error': 'mode must be view or edit'}, status=400)
    if mode == 'edit':
        forbidden_edit = require_any_role(request, {'catalog.editor', 'tenant.admin'})
        if forbidden_edit:
            return forbidden_edit

    tenant_schema = _tenant_schema(request)
    session_token = str(uuid.uuid4())
    event_type = (
        'collaboration.session.started'
        if mode == 'edit'
        else 'collaboration.session.viewed'
    )
    maybe_publish_event(
        event_type=event_type,
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.{event_type}',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data={
            'document': _collaboration_document_to_dict(document),
            'mode': mode,
            'session_token': session_token,
        },
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action=event_type,
        resource_type='collaboration_document',
        resource_id=str(document.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data={'mode': mode, 'session_token': session_token},
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(
        {
            'document_id': str(document.id),
            'mode': mode,
            'session_token': session_token,
        }
    )


@csrf_exempt
def collaboration_document_versions(request, document_id: str):
    if request.method == 'GET':
        forbidden = require_any_role(
            request,
            {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        versions = CollaborationDocumentVersion.objects.filter(
            document_id=document_id
        ).order_by('-version')
        return JsonResponse(
            {'items': [_collaboration_version_to_dict(item) for item in versions]}
        )

    if request.method == 'POST':
        forbidden = require_any_role(request, {'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
        try:
            document = CollaborationDocument.objects.get(id=document_id)
        except (ValidationError, CollaborationDocument.DoesNotExist):
            return JsonResponse({'error': 'not_found'}, status=404)
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        object_key = (payload.get('object_key') or '').strip()
        if not object_key:
            return JsonResponse({'error': 'object_key is required'}, status=400)
        latest_version = (
            CollaborationDocumentVersion.objects.filter(document_id=document_id)
            .order_by('-version')
            .first()
        )
        next_version = 1 if latest_version is None else latest_version.version + 1
        version = CollaborationDocumentVersion.objects.create(
            document=document,
            version=next_version,
            object_key=object_key,
            summary=(payload.get('summary') or ''),
            editor=(payload.get('editor') or request.headers.get('X-User-Id') or ''),
        )
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='collaboration.version.persisted',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.collaboration.version.persisted',
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data={
                'document': _collaboration_document_to_dict(document),
                'version': _collaboration_version_to_dict(version),
            },
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='collaboration.version.persisted',
            resource_type='collaboration_document',
            resource_id=str(document.id),
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_collaboration_version_to_dict(version),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_collaboration_version_to_dict(version), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def notebook_workspaces(request):
    if request.method == 'GET':
        forbidden = require_any_role(
            request,
            {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        workspaces = NotebookWorkspace.objects.order_by('-updated_at')
        return JsonResponse(
            {'items': [_notebook_workspace_to_dict(item) for item in workspaces]}
        )

    if request.method == 'POST':
        forbidden = require_any_role(request, {'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        name = (payload.get('name') or '').strip()
        if not name:
            return JsonResponse({'error': 'name is required'}, status=400)
        storage_mounts = payload.get('storage_mounts')
        if storage_mounts is None:
            storage_mounts = []
        if not isinstance(storage_mounts, list) or any(
            not isinstance(item, str) for item in storage_mounts
        ):
            return JsonResponse(
                {'error': 'storage_mounts must be an array of strings'},
                status=400,
            )
        workspace = NotebookWorkspace.objects.create(
            name=name,
            owner=(payload.get('owner') or request.headers.get('X-User-Id') or ''),
            image=(payload.get('image') or ''),
            cpu_limit=(payload.get('cpu_limit') or ''),
            memory_limit=(payload.get('memory_limit') or ''),
            storage_mounts=storage_mounts,
            status='active',
        )
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='notebook.workspace.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.notebook.workspace.created',
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_notebook_workspace_to_dict(workspace),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='notebook.workspace.created',
            resource_type='notebook_workspace',
            resource_id=str(workspace.id),
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_notebook_workspace_to_dict(workspace),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_notebook_workspace_to_dict(workspace), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def notebook_workspace_sessions(request, workspace_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'catalog.editor', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        workspace = NotebookWorkspace.objects.get(id=workspace_id)
    except (ValidationError, NotebookWorkspace.DoesNotExist):
        return JsonResponse({'error': 'workspace_not_found'}, status=404)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    metadata = payload.get('metadata') or {}
    if not isinstance(metadata, dict):
        return JsonResponse({'error': 'metadata must be an object'}, status=400)
    session = NotebookSession.objects.create(
        workspace=workspace,
        user_id=(payload.get('user_id') or request.headers.get('X-User-Id') or ''),
        pod_name=(payload.get('pod_name') or ''),
        metadata=metadata,
        status=NotebookSession.Status.STARTED,
    )
    tenant_schema = _tenant_schema(request)
    maybe_publish_event(
        event_type='notebook.session.started',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.notebook.session.started',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_notebook_session_to_dict(session),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='notebook.session.started',
        resource_type='notebook_session',
        resource_id=str(session.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_notebook_session_to_dict(session),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(_notebook_session_to_dict(session), status=201)


@csrf_exempt
def notebook_sessions(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(
        request,
        {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
    )
    if forbidden:
        return forbidden
    qs = NotebookSession.objects.order_by('-started_at')
    workspace_id = request.GET.get('workspace_id')
    if workspace_id:
        qs = qs.filter(workspace_id=workspace_id)
    status_filter = request.GET.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)
    return JsonResponse({'items': [_notebook_session_to_dict(item) for item in qs]})


@csrf_exempt
def notebook_session_terminate(request, session_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        session = NotebookSession.objects.get(id=session_id)
    except (ValidationError, NotebookSession.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    reason = payload.get('reason') or 'terminated'
    if reason not in {'terminated', 'resource_limit'}:
        return JsonResponse(
            {'error': 'reason must be terminated or resource_limit'},
            status=400,
        )
    session.status = (
        NotebookSession.Status.TERMINATED
        if reason == 'terminated'
        else NotebookSession.Status.RESOURCE_LIMITED
    )
    session.ended_at = timezone.now()
    metadata = session.metadata or {}
    metadata['termination_reason'] = reason
    session.metadata = metadata
    session.save(update_fields=['status', 'ended_at', 'metadata'])
    tenant_schema = _tenant_schema(request)
    event_type = (
        'notebook.session.terminated'
        if reason == 'terminated'
        else 'notebook.resource_limit.terminated'
    )
    maybe_publish_event(
        event_type=event_type,
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.{event_type}',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_notebook_session_to_dict(session),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action=event_type,
        resource_type='notebook_session',
        resource_id=str(session.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_notebook_session_to_dict(session),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(_notebook_session_to_dict(session))


@csrf_exempt
def notebook_session_executions(request, session_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'catalog.editor', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        session = NotebookSession.objects.get(id=session_id)
    except (ValidationError, NotebookSession.DoesNotExist):
        return JsonResponse({'error': 'session_not_found'}, status=404)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    metadata = payload.get('metadata') or {}
    if not isinstance(metadata, dict):
        return JsonResponse({'error': 'metadata must be an object'}, status=400)
    execution = NotebookExecution.objects.create(
        session=session,
        cell_ref=(payload.get('cell_ref') or ''),
        metadata=metadata,
        status=NotebookExecution.Status.REQUESTED,
    )
    tenant_schema = _tenant_schema(request)
    maybe_publish_event(
        event_type='notebook.execution.requested',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.notebook.execution.requested',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_notebook_execution_to_dict(execution),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='notebook.execution.requested',
        resource_type='notebook_execution',
        resource_id=str(execution.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_notebook_execution_to_dict(execution),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(_notebook_execution_to_dict(execution), status=201)


@csrf_exempt
def notebook_execution_complete(request, execution_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        execution = NotebookExecution.objects.get(id=execution_id)
    except (ValidationError, NotebookExecution.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    status_value = payload.get('status') or NotebookExecution.Status.COMPLETED
    if status_value not in {
        NotebookExecution.Status.COMPLETED,
        NotebookExecution.Status.FAILED,
    }:
        return JsonResponse(
            {'error': 'status must be completed or failed'},
            status=400,
        )
    metadata = payload.get('metadata')
    if metadata is not None and not isinstance(metadata, dict):
        return JsonResponse({'error': 'metadata must be an object'}, status=400)
    execution.status = status_value
    execution.completed_at = timezone.now()
    if metadata is not None:
        execution.metadata = metadata
    execution.save(update_fields=['status', 'completed_at', 'metadata'])
    tenant_schema = _tenant_schema(request)
    maybe_publish_event(
        event_type='notebook.execution.completed',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.notebook.execution.completed',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_notebook_execution_to_dict(execution),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='notebook.execution.completed',
        resource_type='notebook_execution',
        resource_id=str(execution.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_notebook_execution_to_dict(execution),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(_notebook_execution_to_dict(execution))


@csrf_exempt
def contracts(request):
    if request.method == 'GET':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
        asset_id = request.GET.get('asset_id')
        qs = DataContract.objects.order_by('-updated_at')
        if asset_id:
            qs = qs.filter(asset_id=asset_id)
        return JsonResponse({'items': [_contract_to_dict(c) for c in qs]})

    if request.method == 'POST':
        forbidden = require_role(request, 'catalog.editor')
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        asset_id = payload.get('asset_id')
        if not asset_id:
            return JsonResponse({'error': 'asset_id is required'}, status=400)
        try:
            asset = DataAsset.objects.get(id=asset_id)
        except (ValidationError, DataAsset.DoesNotExist):
            return JsonResponse({'error': 'asset_not_found'}, status=404)

        schema = payload.get('schema') or {}
        expectations = payload.get('expectations') or []
        owners = payload.get('owners') or []
        if not isinstance(schema, dict):
            return JsonResponse({'error': 'schema must be an object'}, status=400)
        if not isinstance(expectations, list):
            return JsonResponse({'error': 'expectations must be a list'}, status=400)
        if not isinstance(owners, list) or any(not isinstance(owner, str) for owner in owners):
            return JsonResponse({'error': 'owners must be a list of strings'}, status=400)

        version = payload.get('version')
        if version is None:
            version = (DataContract.objects.filter(asset_id=asset_id).aggregate(max_v=Max('version')).get('max_v') or 0) + 1
        elif not isinstance(version, int) or version < 1:
            return JsonResponse({'error': 'version must be a positive integer'}, status=400)

        contract = DataContract.objects.create(
            asset=asset,
            version=version,
            status=DataContract.Status.DRAFT,
            schema=schema,
            expectations=expectations,
            owners=owners,
        )
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='contract.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.contract.created',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_contract_to_dict(contract),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='contract.created',
            resource_type='data_contract',
            resource_id=str(contract.id),
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_contract_to_dict(contract),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_contract_to_dict(contract), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def contract_detail(request, contract_id: str):
    try:
        contract = DataContract.objects.get(id=contract_id)
    except (ValidationError, DataContract.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'tenant.admin'})
    if forbidden:
        return forbidden
    return JsonResponse(_contract_to_dict(contract))


@csrf_exempt
def asset_contracts(request, asset_id: str):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'tenant.admin'})
    if forbidden:
        return forbidden
    contracts_qs = DataContract.objects.filter(asset_id=asset_id).order_by('-version')
    return JsonResponse({'items': [_contract_to_dict(c) for c in contracts_qs]})


@csrf_exempt
def asset_versions(request, asset_id: str):
    if request.method == 'GET':
        forbidden = require_any_role(
            request, {'catalog.reader', 'catalog.editor', 'tenant.admin'}
        )
        if forbidden:
            return forbidden
        versions = AssetVersion.objects.filter(asset_id=asset_id).order_by('-version_number')
        return JsonResponse({'items': [_asset_version_to_dict(item) for item in versions]})

    if request.method == 'POST':
        forbidden = require_role(request, 'catalog.editor')
        if forbidden:
            return forbidden
        try:
            asset = DataAsset.objects.get(id=asset_id)
        except (ValidationError, DataAsset.DoesNotExist):
            return JsonResponse({'error': 'asset_not_found'}, status=404)
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        change_set = payload.get('change_set') or {}
        if not isinstance(change_set, dict):
            return JsonResponse({'error': 'change_set must be an object'}, status=400)
        latest_version = (
            AssetVersion.objects.filter(asset_id=asset_id).aggregate(max_v=Max('version_number')).get('max_v') or 0
        )
        version = AssetVersion.objects.create(
            asset=asset,
            version_number=latest_version + 1,
            change_summary=(payload.get('change_summary') or ''),
            change_set=change_set,
            status=AssetVersion.Status.DRAFT,
            created_by=(request.headers.get('X-User-Id') or ''),
        )
        tenant_schema = _tenant_schema(request)
        data = _asset_version_to_dict(version)
        maybe_publish_event(
            event_type='asset_version.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.asset_version.created',
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=data,
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='asset_version.created',
            resource_type='asset_version',
            resource_id=str(version.id),
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=data,
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(data, status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def asset_version_publish(request, asset_id: str, version_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        version = AssetVersion.objects.get(id=version_id, asset_id=asset_id)
    except (ValidationError, AssetVersion.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    if version.status != AssetVersion.Status.DRAFT:
        return JsonResponse({'error': 'only_draft_versions_can_be_published'}, status=400)

    change_set = version.change_set or {}
    ownership = change_set.get('ownership') or {}
    classifications = change_set.get('classifications')
    effective_owner = ownership.get('owner') if isinstance(ownership, dict) else None
    if not effective_owner:
        effective_owner = DataAsset.objects.filter(id=asset_id).values_list('owner', flat=True).first() or ''
    effective_classifications = (
        classifications
        if isinstance(classifications, list)
        else DataAsset.objects.filter(id=asset_id).values_list('classifications', flat=True).first() or []
    )
    if not effective_owner:
        return JsonResponse({'error': 'owner_required'}, status=400)
    parsed_classifications = _parse_string_list(effective_classifications)
    if parsed_classifications is None or not parsed_classifications:
        return JsonResponse({'error': 'classifications_required'}, status=400)
    invalid = _validate_classification_values(parsed_classifications)
    if invalid:
        return JsonResponse({'error': 'unknown_classifications', 'items': invalid}, status=400)

    schema_change = change_set.get('schema')
    active_contract = (
        DataContract.objects.filter(asset_id=asset_id, status=DataContract.Status.ACTIVE).order_by('-version').first()
    )
    if schema_change is not None and active_contract is not None and schema_change != active_contract.schema:
        return JsonResponse({'error': 'contract_incompatible_schema_change'}, status=400)

    AssetVersion.objects.filter(
        asset_id=asset_id,
        status=AssetVersion.Status.PUBLISHED,
    ).exclude(id=version.id).update(status=AssetVersion.Status.SUPERSEDED, updated_at=timezone.now())
    version.status = AssetVersion.Status.PUBLISHED
    version.save(update_fields=['status', 'updated_at'])
    tenant_schema = _tenant_schema(request)
    data = _asset_version_to_dict(version)
    maybe_publish_event(
        event_type='asset_version.published',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.asset_version.published',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='asset_version.published',
        resource_type='asset_version',
        resource_id=str(version.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_event(
        event_type='asset_version.superseded',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.asset_version.superseded',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data={'asset_id': asset_id, 'published_version_id': str(version.id)},
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(data)


@csrf_exempt
def contract_activate(request, contract_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        contract = DataContract.objects.get(id=contract_id)
    except (ValidationError, DataContract.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    DataContract.objects.filter(asset_id=contract.asset_id, status=DataContract.Status.ACTIVE).exclude(id=contract.id).update(
        status=DataContract.Status.DEPRECATED
    )
    contract.status = DataContract.Status.ACTIVE
    contract.save(update_fields=['status', 'updated_at'])
    tenant_schema = _tenant_schema(request)
    maybe_publish_event(
        event_type='contract.activated',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.contract.activated',
        correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_contract_to_dict(contract),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='contract.activated',
        resource_type='data_contract',
        resource_id=str(contract.id),
        correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_contract_to_dict(contract),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(_contract_to_dict(contract))


@csrf_exempt
def contract_deprecate(request, contract_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        contract = DataContract.objects.get(id=contract_id)
    except (ValidationError, DataContract.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    contract.status = DataContract.Status.DEPRECATED
    contract.save(update_fields=['status', 'updated_at'])
    tenant_schema = _tenant_schema(request)
    maybe_publish_event(
        event_type='contract.deprecated',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.contract.deprecated',
        correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_contract_to_dict(contract),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='contract.deprecated',
        resource_type='data_contract',
        resource_id=str(contract.id),
        correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_contract_to_dict(contract),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(_contract_to_dict(contract))


@csrf_exempt
def quality_rules(request):
    if request.method == 'GET':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
        asset_id = request.GET.get('asset_id')
        qs = QualityRule.objects.order_by('-updated_at')
        if asset_id:
            qs = qs.filter(asset_id=asset_id)
        items = [_quality_rule_to_dict(r) for r in qs]
        return JsonResponse({'items': items})

    if request.method == 'POST':
        forbidden = require_role(request, 'catalog.editor')
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        asset_id = payload.get('asset_id')
        rule_type = payload.get('rule_type')
        if not asset_id or not rule_type:
            return JsonResponse({'error': 'asset_id and rule_type are required'}, status=400)
        try:
            asset = DataAsset.objects.get(id=asset_id)
        except (ValidationError, DataAsset.DoesNotExist):
            return JsonResponse({'error': 'asset_not_found'}, status=404)
        params = payload.get('params') or {}
        if not isinstance(params, dict):
            return JsonResponse({'error': 'params must be an object'}, status=400)
        severity = payload.get('severity') or QualityRule.Severity.WARNING
        if severity not in {QualityRule.Severity.WARNING, QualityRule.Severity.ERROR}:
            return JsonResponse({'error': 'severity must be warning or error'}, status=400)

        rule = QualityRule.objects.create(asset=asset, rule_type=rule_type, params=params, severity=severity)
        return JsonResponse(_quality_rule_to_dict(rule), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def quality_rule_evaluate(request, rule_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_role(request, 'catalog.editor')
    if forbidden:
        return forbidden
    try:
        QualityRule.objects.get(id=rule_id)
    except (ValidationError, QualityRule.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)

    tenant_schema = _tenant_schema(request)
    result = evaluate_quality_rule.apply(
        kwargs={
            'tenant_schema': tenant_schema,
            'rule_id': rule_id,
            'correlation_id': getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            'user_id': request.headers.get('X-User-Id'),
            'request_id': request.headers.get('X-Request-Id') or request.headers.get('X-Request-ID'),
        }
    ).get(propagate=True)
    return JsonResponse(result)


@csrf_exempt
def quality_results(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'tenant.admin'})
    if forbidden:
        return forbidden
    rule_id = request.GET.get('rule_id')
    asset_id = request.GET.get('asset_id')
    try:
        limit = int(request.GET.get('limit', '100'))
        offset = int(request.GET.get('offset', '0'))
    except ValueError:
        return JsonResponse({'error': 'limit/offset must be integers'}, status=400)
    limit = min(max(limit, 1), 500)
    offset = max(offset, 0)

    qs = QualityCheckResult.objects.select_related('rule').order_by('-created_at')
    if rule_id:
        qs = qs.filter(rule_id=rule_id)
    if asset_id:
        qs = qs.filter(rule__asset_id=asset_id)
    items = [_quality_result_to_dict(r) for r in qs[offset : offset + limit]]
    return JsonResponse({'items': items})


@csrf_exempt
def data_products(request):
    if request.method == 'GET':
        forbidden = require_any_role(
            request,
            {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        qs = DataProduct.objects.order_by('-updated_at')
        status_filter = request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return JsonResponse({'items': [_data_product_to_dict(item) for item in qs]})

    if request.method == 'POST':
        forbidden = require_any_role(
            request,
            {'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        name = (payload.get('name') or '').strip()
        if not name:
            return JsonResponse({'error': 'name is required'}, status=400)
        if DataProduct.objects.filter(name=name).exists():
            return JsonResponse({'error': 'name_already_exists'}, status=409)

        asset_ids = _parse_uuid_string_list(payload.get('asset_ids'))
        if asset_ids is None:
            return JsonResponse({'error': 'asset_ids must be an array of UUID strings'}, status=400)
        existing_asset_ids = {
            str(asset_id) for asset_id in DataAsset.objects.filter(id__in=asset_ids).values_list('id', flat=True)
        }
        missing_asset_ids = sorted(set(asset_ids) - existing_asset_ids)
        if missing_asset_ids:
            return JsonResponse({'error': 'asset_not_found', 'asset_ids': missing_asset_ids}, status=400)

        sla = payload.get('sla') or {}
        if not isinstance(sla, dict):
            return JsonResponse({'error': 'sla must be an object'}, status=400)
        product = DataProduct.objects.create(
            name=name,
            domain=(payload.get('domain') or ''),
            owner=(payload.get('owner') or ''),
            asset_ids=asset_ids,
            sla=sla,
            status=DataProduct.Status.DRAFT,
        )
        tenant_schema = _tenant_schema(request)
        data = _data_product_to_dict(product)
        maybe_publish_event(
            event_type='data_product.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.data_product.created',
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=data,
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='data_product.created',
            resource_type='data_product',
            resource_id=str(product.id),
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=data,
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(data, status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def data_product_detail(request, product_id: str):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(
        request,
        {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
    )
    if forbidden:
        return forbidden
    try:
        product = DataProduct.objects.get(id=product_id)
    except (ValidationError, DataProduct.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    return JsonResponse(_data_product_to_dict(product))


@csrf_exempt
def data_product_activate(request, product_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        product = DataProduct.objects.get(id=product_id)
    except (ValidationError, DataProduct.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    if not product.owner:
        return JsonResponse({'error': 'owner_required'}, status=400)
    if not product.asset_ids:
        return JsonResponse({'error': 'asset_ids_required'}, status=400)

    missing_contracts = []
    for asset_id in product.asset_ids:
        has_active_contract = DataContract.objects.filter(
            asset_id=asset_id,
            status=DataContract.Status.ACTIVE,
        ).exists()
        if not has_active_contract:
            missing_contracts.append(asset_id)
    if missing_contracts:
        return JsonResponse(
            {'error': 'missing_active_contracts', 'asset_ids': missing_contracts},
            status=400,
        )
    product.status = DataProduct.Status.ACTIVE
    product.save(update_fields=['status', 'updated_at'])
    tenant_schema = _tenant_schema(request)
    data = _data_product_to_dict(product)
    maybe_publish_event(
        event_type='data_product.activated',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.data_product.activated',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='data_product.activated',
        resource_type='data_product',
        resource_id=str(product.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(data)


@csrf_exempt
def data_product_retire(request, product_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        product = DataProduct.objects.get(id=product_id)
    except (ValidationError, DataProduct.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    product.status = DataProduct.Status.RETIRED
    product.save(update_fields=['status', 'updated_at'])
    tenant_schema = _tenant_schema(request)
    data = _data_product_to_dict(product)
    maybe_publish_event(
        event_type='data_product.retired',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.data_product.retired',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='data_product.retired',
        resource_type='data_product',
        resource_id=str(product.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(data)


@csrf_exempt
def glossary_terms(request):
    if request.method == 'GET':
        forbidden = require_any_role(
            request,
            {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        qs = GlossaryTerm.objects.order_by('-updated_at')
        status_filter = request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return JsonResponse({'items': [_glossary_term_to_dict(item) for item in qs]})

    if request.method == 'POST':
        forbidden = require_any_role(
            request,
            {'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        name = (payload.get('name') or '').strip()
        if not name:
            return JsonResponse({'error': 'name is required'}, status=400)
        if GlossaryTerm.objects.filter(name=name).exists():
            return JsonResponse({'error': 'name_already_exists'}, status=409)
        owners = _parse_string_list(payload.get('owners'))
        if owners is None:
            return JsonResponse({'error': 'owners must be an array of strings'}, status=400)
        stewards = _parse_string_list(payload.get('stewards'))
        if stewards is None:
            return JsonResponse({'error': 'stewards must be an array of strings'}, status=400)
        classifications = _parse_string_list(payload.get('classifications'))
        if classifications is None:
            return JsonResponse(
                {'error': 'classifications must be an array of strings'},
                status=400,
            )
        invalid = _validate_classification_values(classifications)
        if invalid:
            return JsonResponse(
                {'error': 'unknown_classifications', 'items': invalid},
                status=400,
            )
        term = GlossaryTerm.objects.create(
            name=name,
            definition=(payload.get('definition') or ''),
            status=GlossaryTerm.Status.DRAFT,
            owners=owners,
            stewards=stewards,
            classifications=classifications,
            related_asset_ids=[],
        )
        tenant_schema = _tenant_schema(request)
        data = _glossary_term_to_dict(term)
        maybe_publish_event(
            event_type='glossary.term.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.glossary.term.created',
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=data,
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='glossary.term.created',
            resource_type='glossary_term',
            resource_id=str(term.id),
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=data,
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(data, status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def glossary_term_detail(request, term_id: str):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(
        request,
        {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
    )
    if forbidden:
        return forbidden
    try:
        term = GlossaryTerm.objects.get(id=term_id)
    except (ValidationError, GlossaryTerm.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    return JsonResponse(_glossary_term_to_dict(term))


@csrf_exempt
def glossary_term_approve(request, term_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        term = GlossaryTerm.objects.get(id=term_id)
    except (ValidationError, GlossaryTerm.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    if term.status == GlossaryTerm.Status.DEPRECATED:
        return JsonResponse({'error': 'term_deprecated'}, status=400)
    term.status = GlossaryTerm.Status.APPROVED
    term.save(update_fields=['status', 'updated_at'])
    tenant_schema = _tenant_schema(request)
    data = _glossary_term_to_dict(term)
    maybe_publish_event(
        event_type='glossary.term.approved',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.glossary.term.approved',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='glossary.term.approved',
        resource_type='glossary_term',
        resource_id=str(term.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(data)


@csrf_exempt
def glossary_term_deprecate(request, term_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        term = GlossaryTerm.objects.get(id=term_id)
    except (ValidationError, GlossaryTerm.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    term.status = GlossaryTerm.Status.DEPRECATED
    term.save(update_fields=['status', 'updated_at'])
    tenant_schema = _tenant_schema(request)
    data = _glossary_term_to_dict(term)
    maybe_publish_event(
        event_type='glossary.term.deprecated',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.glossary.term.deprecated',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='glossary.term.deprecated',
        resource_type='glossary_term',
        resource_id=str(term.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(data)


@csrf_exempt
def asset_glossary_term_link(request, asset_id: str, term_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_role(request, 'catalog.editor')
    if forbidden:
        return forbidden
    try:
        asset = DataAsset.objects.get(id=asset_id)
    except (ValidationError, DataAsset.DoesNotExist):
        return JsonResponse({'error': 'asset_not_found'}, status=404)
    try:
        term = GlossaryTerm.objects.get(id=term_id)
    except (ValidationError, GlossaryTerm.DoesNotExist):
        return JsonResponse({'error': 'term_not_found'}, status=404)
    if term.status != GlossaryTerm.Status.APPROVED:
        return JsonResponse({'error': 'term_not_approved'}, status=400)
    related_asset_ids = list(term.related_asset_ids or [])
    asset_ref = str(asset.id)
    if asset_ref not in related_asset_ids:
        related_asset_ids.append(asset_ref)
        term.related_asset_ids = related_asset_ids
        term.save(update_fields=['related_asset_ids', 'updated_at'])
    tenant_schema = _tenant_schema(request)
    data = _glossary_term_to_dict(term)
    maybe_publish_event(
        event_type='glossary.term.linked_to_asset',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.glossary.term.linked_to_asset',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data={'term': data, 'asset': _asset_to_dict(asset)},
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='glossary.term.linked_to_asset',
        resource_type='glossary_term',
        resource_id=str(term.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data={'term': data, 'asset': _asset_to_dict(asset)},
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(data)


@csrf_exempt
def governance_policies(request):
    if request.method == 'GET':
        forbidden = require_any_role(
            request,
            {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        qs = GovernancePolicy.objects.order_by('-updated_at')
        name = (request.GET.get('name') or '').strip()
        if name:
            qs = qs.filter(name=name)
        status_filter = request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return JsonResponse({'items': [_governance_policy_to_dict(item) for item in qs]})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        name = (payload.get('name') or '').strip()
        if not name:
            return JsonResponse({'error': 'name is required'}, status=400)
        rules = payload.get('rules') or {}
        if not isinstance(rules, dict):
            return JsonResponse({'error': 'rules must be an object'}, status=400)

        latest_version = (
            GovernancePolicy.objects.filter(name=name).aggregate(max_version=Max('version')).get('max_version') or 0
        )
        policy = GovernancePolicy.objects.create(
            name=name,
            version=latest_version + 1,
            status=GovernancePolicy.Status.DRAFT,
            rules=rules,
            reason=(payload.get('reason') or '').strip(),
            actor_id=request.headers.get('X-User-Id') or '',
        )
        return JsonResponse(_governance_policy_to_dict(policy), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def governance_policy_detail(request, policy_id: str):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(
        request,
        {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
    )
    if forbidden:
        return forbidden
    try:
        policy = GovernancePolicy.objects.get(id=policy_id)
    except (ValidationError, GovernancePolicy.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    return JsonResponse(_governance_policy_to_dict(policy))


def _governance_transition_allowed(policy: GovernancePolicy, action: str) -> bool:
    allowed = {
        GovernancePolicy.Status.DRAFT: {'submit_for_review'},
        GovernancePolicy.Status.IN_REVIEW: {'approve'},
        GovernancePolicy.Status.APPROVED: {'activate'},
        GovernancePolicy.Status.ACTIVE: {'rollback'},
    }
    return action in allowed.get(policy.status, set())


def _create_policy_transition(
    *,
    policy: GovernancePolicy,
    from_status: str,
    action: str,
    reason: str,
    actor_id: str,
):
    GovernancePolicyTransition.objects.create(
        policy=policy,
        from_status=from_status,
        to_status=policy.status,
        action=action,
        reason=reason,
        actor_id=actor_id,
    )


@csrf_exempt
def governance_policy_transition(request, policy_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    action = payload.get('action')
    if action not in {'submit_for_review', 'approve', 'activate', 'rollback'}:
        return JsonResponse({'error': 'invalid_action'}, status=400)
    try:
        policy = GovernancePolicy.objects.get(id=policy_id)
    except (ValidationError, GovernancePolicy.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    if not _governance_transition_allowed(policy, action):
        return JsonResponse({'error': 'invalid_transition'}, status=400)

    reason = (payload.get('reason') or '').strip()
    actor_id = request.headers.get('X-User-Id') or ''
    from_status = policy.status
    rollback_target = None
    if action == 'submit_for_review':
        policy.status = GovernancePolicy.Status.IN_REVIEW
        event_type = 'policy.submitted_for_review'
    elif action == 'approve':
        policy.status = GovernancePolicy.Status.APPROVED
        event_type = 'policy.approved'
    elif action == 'activate':
        policy.status = GovernancePolicy.Status.ACTIVE
        GovernancePolicy.objects.filter(
            name=policy.name,
            status=GovernancePolicy.Status.ACTIVE,
        ).exclude(id=policy.id).update(
            status=GovernancePolicy.Status.SUPERSEDED,
            updated_at=timezone.now(),
        )
        event_type = 'policy.activated'
    else:
        rollback_target = (
            GovernancePolicy.objects.filter(
                name=policy.name,
                status=GovernancePolicy.Status.SUPERSEDED,
            )
            .exclude(id=policy.id)
            .order_by('-version')
            .first()
        )
        if rollback_target is None:
            return JsonResponse({'error': 'rollback_target_not_found'}, status=400)
        policy.status = GovernancePolicy.Status.ROLLED_BACK
        rollback_target.status = GovernancePolicy.Status.ACTIVE
        rollback_target.reason = reason
        rollback_target.actor_id = actor_id
        rollback_target.save(update_fields=['status', 'reason', 'actor_id', 'updated_at'])
        _create_policy_transition(
            policy=rollback_target,
            from_status=GovernancePolicy.Status.SUPERSEDED,
            action='restore_from_rollback',
            reason=reason,
            actor_id=actor_id,
        )
        event_type = 'policy.rolled_back'

    policy.reason = reason
    policy.actor_id = actor_id
    policy.rollback_target = rollback_target
    policy.save(update_fields=['status', 'reason', 'actor_id', 'rollback_target', 'updated_at'])
    _create_policy_transition(
        policy=policy,
        from_status=from_status,
        action=action,
        reason=reason,
        actor_id=actor_id,
    )
    tenant_schema = _tenant_schema(request)
    payload = _governance_policy_to_dict(policy)
    maybe_publish_event(
        event_type=event_type,
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.{event_type}',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=payload,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action=event_type,
        resource_type='governance_policy',
        resource_id=str(policy.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=payload,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(payload)


@csrf_exempt
def workflow_definitions(request):
    if request.method == 'GET':
        forbidden = require_any_role(
            request,
            {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        definitions = WorkflowDefinition.objects.order_by('-updated_at')
        return JsonResponse(
            {'items': [_workflow_definition_to_dict(item) for item in definitions]}
        )

    if request.method == 'POST':
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        name = (payload.get('name') or '').strip()
        if not name:
            return JsonResponse({'error': 'name is required'}, status=400)
        definition = WorkflowDefinition.objects.create(
            name=name,
            description=(payload.get('description') or ''),
            domain_ref=(payload.get('domain_ref') or ''),
        )
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='workflow.definition.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.workflow.definition.created',
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_workflow_definition_to_dict(definition),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='workflow.definition.created',
            resource_type='workflow_definition',
            resource_id=str(definition.id),
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_workflow_definition_to_dict(definition),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_workflow_definition_to_dict(definition), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def workflow_definition_detail(request, definition_id: str):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(
        request,
        {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
    )
    if forbidden:
        return forbidden
    try:
        definition = WorkflowDefinition.objects.get(id=definition_id)
    except (ValidationError, WorkflowDefinition.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    return JsonResponse(_workflow_definition_to_dict(definition))


@csrf_exempt
def workflow_runs(request):
    if request.method == 'GET':
        forbidden = require_any_role(
            request,
            {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        qs = WorkflowRun.objects.order_by('-created_at')
        definition_id = request.GET.get('definition_id')
        if definition_id:
            qs = qs.filter(definition_id=definition_id)
        status_filter = request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return JsonResponse({'items': [_workflow_run_to_dict(item) for item in qs]})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        definition_id = payload.get('definition_id')
        if not definition_id:
            return JsonResponse({'error': 'definition_id is required'}, status=400)
        try:
            definition = WorkflowDefinition.objects.get(id=definition_id)
        except (ValidationError, WorkflowDefinition.DoesNotExist):
            return JsonResponse({'error': 'definition_not_found'}, status=404)
        run = WorkflowRun.objects.create(
            definition=definition,
            subject_ref=(payload.get('subject_ref') or ''),
            payload=payload.get('payload') or {},
            status=WorkflowRun.Status.DRAFT,
            submitted_by=request.headers.get('X-User-Id') or '',
        )
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='workflow.run.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.workflow.run.created',
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_workflow_run_to_dict(run),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='workflow.run.created',
            resource_type='workflow_run',
            resource_id=str(run.id),
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_workflow_run_to_dict(run),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_workflow_run_to_dict(run), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


def _workflow_transition_allowed(run: WorkflowRun, action: str) -> bool:
    allowed = {
        WorkflowRun.Status.DRAFT: {'submit'},
        WorkflowRun.Status.IN_REVIEW: {'approve', 'reject'},
        WorkflowRun.Status.APPROVED: {'activate', 'rollback'},
        WorkflowRun.Status.ACTIVE: {'supersede', 'rollback'},
    }
    return action in allowed.get(run.status, set())


@csrf_exempt
def workflow_run_transition(request, run_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    action = payload.get('action')
    if action not in {'submit', 'approve', 'reject', 'activate', 'supersede', 'rollback'}:
        return JsonResponse({'error': 'invalid_action'}, status=400)
    try:
        run = WorkflowRun.objects.get(id=run_id)
    except (ValidationError, WorkflowRun.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    if not _workflow_transition_allowed(run, action):
        return JsonResponse({'error': 'invalid_transition'}, status=400)

    if action == 'submit':
        forbidden = require_any_role(request, {'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
        run.status = WorkflowRun.Status.IN_REVIEW
        WorkflowTask.objects.create(
            run=run,
            task_type='review',
            assignee=(payload.get('assignee') or ''),
            status=WorkflowTask.Status.OPEN,
        )
    elif action in {'approve', 'reject'}:
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        run.status = (
            WorkflowRun.Status.APPROVED
            if action == 'approve'
            else WorkflowRun.Status.REJECTED
        )
        run.reviewed_by = request.headers.get('X-User-Id') or ''
        WorkflowTask.objects.filter(run=run, status=WorkflowTask.Status.OPEN).update(
            status=WorkflowTask.Status.COMPLETED,
            completed_at=timezone.now(),
        )
    elif action == 'activate':
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        run.status = WorkflowRun.Status.ACTIVE
    elif action == 'supersede':
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        run.status = WorkflowRun.Status.SUPERSEDED
    else:
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        run.status = WorkflowRun.Status.ROLLED_BACK

    run.save(update_fields=['status', 'reviewed_by', 'updated_at'])
    tenant_schema = _tenant_schema(request)
    event_type = f'workflow.run.{action}'
    maybe_publish_event(
        event_type=event_type,
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.{event_type}',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_workflow_run_to_dict(run),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action=event_type,
        resource_type='workflow_run',
        resource_id=str(run.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_workflow_run_to_dict(run),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(_workflow_run_to_dict(run))


@csrf_exempt
def workflow_run_tasks(request, run_id: str):
    if request.method != 'GET':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(
        request,
        {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
    )
    if forbidden:
        return forbidden
    tasks = WorkflowTask.objects.filter(run_id=run_id).order_by('-created_at')
    return JsonResponse({'items': [_workflow_task_to_dict(item) for item in tasks]})


@csrf_exempt
def projects(request):
    if request.method == 'GET':
        forbidden = require_any_role(
            request,
            {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        qs = Project.objects.order_by('-created_at')
        status_filter = request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return JsonResponse({'items': [_project_to_dict(item) for item in qs]})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'catalog.editor', 'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        name = (payload.get('name') or '').strip()
        if not name:
            return JsonResponse({'error': 'name is required'}, status=400)
        project = Project.objects.create(
            name=name,
            code=(payload.get('code') or '').strip(),
            institution_ref=(payload.get('institution_ref') or '').strip(),
            status=(payload.get('status') or 'active').strip() or 'active',
            sync_config=payload.get('sync_config')
            if isinstance(payload.get('sync_config'), dict)
            else {},
        )
        return JsonResponse(_project_to_dict(project), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def orchestration_workflows(request):
    if request.method == 'GET':
        forbidden = require_any_role(
            request,
            {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        qs = OrchestrationWorkflow.objects.order_by('-created_at')
        project_id = request.GET.get('project_id')
        if project_id:
            qs = qs.filter(project_id=project_id)
        status_filter = request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        trigger_type = request.GET.get('trigger_type')
        if trigger_type:
            qs = qs.filter(trigger_type=trigger_type)
        return JsonResponse(
            {'items': [_orchestration_workflow_to_dict(item) for item in qs]}
        )

    if request.method == 'POST':
        forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        name = (payload.get('name') or '').strip()
        if not name:
            return JsonResponse({'error': 'name is required'}, status=400)
        trigger_type = payload.get('trigger_type') or OrchestrationWorkflow.TriggerType.EVENT
        if trigger_type not in OrchestrationWorkflow.TriggerType.values:
            return JsonResponse({'error': 'invalid_trigger_type'}, status=400)
        project_id = payload.get('project_id')
        project = None
        if project_id:
            try:
                project = Project.objects.get(id=project_id)
            except (ValidationError, Project.DoesNotExist):
                return JsonResponse({'error': 'project_not_found'}, status=404)
        workflow_status = payload.get('status') or OrchestrationWorkflow.Status.ACTIVE
        if workflow_status not in OrchestrationWorkflow.Status.values:
            return JsonResponse({'error': 'invalid_status'}, status=400)
        steps = _parse_orchestration_steps(payload.get('steps'))
        if steps is None:
            return JsonResponse({'error': 'invalid_steps'}, status=400)
        for step in steps:
            try:
                ingestion = IngestionRequest.objects.get(id=step['ingestion_id'])
            except (ValidationError, IngestionRequest.DoesNotExist):
                return JsonResponse({'error': 'step_ingestion_not_found'}, status=404)
            if project and ingestion.project_id != project.id:
                return JsonResponse({'error': 'step_project_mismatch'}, status=400)
        workflow = OrchestrationWorkflow.objects.create(
            project=project,
            name=name,
            trigger_type=trigger_type,
            trigger_value=(payload.get('trigger_value') or '').strip(),
            steps=steps,
            status=workflow_status,
        )
        tenant_schema = _tenant_schema(request)
        payload_data = _orchestration_workflow_to_dict(workflow)
        maybe_publish_event(
            event_type='orchestration.workflow.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.orchestration.workflow.created',
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=payload_data,
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='orchestration.workflow.created',
            resource_type='orchestration_workflow',
            resource_id=str(workflow.id),
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=payload_data,
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(payload_data, status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def orchestration_runs(request):
    if request.method == 'GET':
        forbidden = require_any_role(
            request,
            {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        qs = OrchestrationRun.objects.order_by('-created_at')
        project_id = request.GET.get('project_id')
        if project_id:
            qs = qs.filter(project_id=project_id)
        workflow_id = request.GET.get('workflow_id')
        if workflow_id:
            qs = qs.filter(workflow_id=workflow_id)
        status_filter = request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return JsonResponse({'items': [_orchestration_run_to_dict(item) for item in qs]})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'catalog.editor', 'policy.admin', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        workflow_id = payload.get('workflow_id')
        if not workflow_id:
            return JsonResponse({'error': 'workflow_id is required'}, status=400)
        try:
            workflow = OrchestrationWorkflow.objects.get(id=workflow_id)
        except (ValidationError, OrchestrationWorkflow.DoesNotExist):
            return JsonResponse({'error': 'workflow_not_found'}, status=404)
        if workflow.status != OrchestrationWorkflow.Status.ACTIVE:
            return JsonResponse({'error': 'workflow_not_active'}, status=400)
        run = OrchestrationRun.objects.create(
            project=workflow.project,
            workflow=workflow,
            trigger_context=payload.get('trigger_context')
            if isinstance(payload.get('trigger_context'), dict)
            else {},
            status=OrchestrationRun.Status.QUEUED,
            step_results=[],
        )
        tenant_schema = _tenant_schema(request)
        payload_data = _orchestration_run_to_dict(run)
        maybe_publish_event(
            event_type='orchestration.run.queued',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.orchestration.run.queued',
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=payload_data,
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='orchestration.run.queued',
            resource_type='orchestration_run',
            resource_id=str(run.id),
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=payload_data,
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(payload_data, status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def orchestration_run_transition(request, run_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        run = OrchestrationRun.objects.select_related('workflow').get(id=run_id)
    except (ValidationError, OrchestrationRun.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'error': 'invalid_json'}, status=400)
    action = payload.get('action')
    if action not in {'start', 'cancel'}:
        return JsonResponse({'error': 'invalid_action'}, status=400)
    if action == 'cancel':
        if run.status in {
            OrchestrationRun.Status.SUCCEEDED,
            OrchestrationRun.Status.FAILED,
            OrchestrationRun.Status.CANCELLED,
        }:
            return JsonResponse({'error': 'run_not_cancellable'}, status=400)
        run.status = OrchestrationRun.Status.CANCELLED
        run.finished_at = timezone.now()
        run.error_message = 'cancelled by user'
        run.save(update_fields=['status', 'finished_at', 'error_message', 'updated_at'])
        event_type = 'orchestration.run.cancelled'
    else:
        if run.status != OrchestrationRun.Status.QUEUED:
            return JsonResponse({'error': 'invalid_transition'}, status=400)
        run.status = OrchestrationRun.Status.RUNNING
        run.started_at = timezone.now()
        run.save(update_fields=['status', 'started_at', 'updated_at'])
        event_type = 'orchestration.run.started'
        step_results: list[dict[str, Any]] = []
        tenant_schema = _tenant_schema(request)
        for step in run.workflow.steps:
            ingestion_id = step.get('ingestion_id')
            try:
                ingestion = IngestionRequest.objects.get(id=ingestion_id)
            except (ValidationError, IngestionRequest.DoesNotExist):
                run.status = OrchestrationRun.Status.FAILED
                run.error_message = f"ingestion_not_found:{ingestion_id}"
                run.finished_at = timezone.now()
                run.step_results = step_results
                run.save(
                    update_fields=[
                        'status',
                        'error_message',
                        'finished_at',
                        'step_results',
                        'updated_at',
                    ]
                )
                event_type = 'orchestration.run.failed'
                break
            connector_run = ConnectorRun.objects.create(
                ingestion=ingestion,
                execution_path=ConnectorRun.ExecutionPath.WORKER,
                status=ConnectorRun.Status.QUEUED,
                retry_count=0,
                progress={},
            )
            execute_connector_run.apply(
                kwargs={
                    'tenant_schema': tenant_schema,
                    'run_id': str(connector_run.id),
                    'correlation_id': getattr(request, 'correlation_id', None)
                    or request.headers.get('X-Correlation-Id'),
                    'user_id': request.headers.get('X-User-Id'),
                    'request_id': request.headers.get('X-Request-Id')
                    or request.headers.get('X-Request-ID'),
                }
            ).get(propagate=True)
            refreshed_connector_run = ConnectorRun.objects.get(id=connector_run.id)
            step_result = {
                'step_id': step.get('step_id'),
                'ingestion_id': str(ingestion.id),
                'connector_run_id': str(refreshed_connector_run.id),
                'status': refreshed_connector_run.status,
            }
            step_results.append(step_result)
            if refreshed_connector_run.status != ConnectorRun.Status.SUCCEEDED:
                run.status = OrchestrationRun.Status.FAILED
                run.error_message = (
                    refreshed_connector_run.error_message or 'connector_run_failed'
                )
                run.finished_at = timezone.now()
                run.step_results = step_results
                run.save(
                    update_fields=[
                        'status',
                        'error_message',
                        'finished_at',
                        'step_results',
                        'updated_at',
                    ]
                )
                event_type = 'orchestration.run.failed'
                break
        else:
            run.status = OrchestrationRun.Status.SUCCEEDED
            run.error_message = ''
            run.finished_at = timezone.now()
            run.step_results = step_results
            run.save(
                update_fields=[
                    'status',
                    'error_message',
                    'finished_at',
                    'step_results',
                    'updated_at',
                ]
            )
            event_type = 'orchestration.run.succeeded'

    tenant_schema = _tenant_schema(request)
    payload_data = _orchestration_run_to_dict(run)
    maybe_publish_event(
        event_type=event_type,
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.{event_type}',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=payload_data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action=event_type,
        resource_type='orchestration_run',
        resource_id=str(run.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=payload_data,
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(payload_data)


@csrf_exempt
def connector_runs(request):
    if request.method == 'GET':
        forbidden = require_any_role(
            request,
            {'catalog.reader', 'catalog.editor', 'policy.admin', 'tenant.admin'},
        )
        if forbidden:
            return forbidden
        qs = ConnectorRun.objects.select_related('ingestion').order_by('-created_at')
        ingestion_id = request.GET.get('ingestion_id')
        if ingestion_id:
            qs = qs.filter(ingestion_id=ingestion_id)
        project_id = request.GET.get('project_id')
        if project_id:
            qs = qs.filter(ingestion__project_id=project_id)
        status_filter = request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return JsonResponse({'items': [_connector_run_to_dict(item) for item in qs]})

    if request.method == 'POST':
        forbidden = require_any_role(request, {'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        ingestion_id = payload.get('ingestion_id')
        if not ingestion_id:
            return JsonResponse({'error': 'ingestion_id is required'}, status=400)
        try:
            ingestion = IngestionRequest.objects.get(id=ingestion_id)
        except (ValidationError, IngestionRequest.DoesNotExist):
            return JsonResponse({'error': 'ingestion_not_found'}, status=404)

        execution_path = (
            payload.get('execution_path') or ConnectorRun.ExecutionPath.WORKER
        )
        if execution_path not in {
            ConnectorRun.ExecutionPath.WORKER,
            ConnectorRun.ExecutionPath.JOB,
        }:
            return JsonResponse({'error': 'invalid_execution_path'}, status=400)

        run = ConnectorRun.objects.create(
            ingestion=ingestion,
            execution_path=execution_path,
            status=ConnectorRun.Status.QUEUED,
            retry_count=int(payload.get('retry_count') or 0),
            progress={},
        )
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='connector.run.queued',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.connector.run.queued',
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_connector_run_to_dict(run),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='connector.run.queued',
            resource_type='connector_run',
            resource_id=str(run.id),
            correlation_id=getattr(request, 'correlation_id', None)
            or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_connector_run_to_dict(run),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        result = execute_connector_run.apply(
            kwargs={
                'tenant_schema': tenant_schema,
                'run_id': str(run.id),
                'correlation_id': getattr(request, 'correlation_id', None)
                or request.headers.get('X-Correlation-Id'),
                'user_id': request.headers.get('X-User-Id'),
                'request_id': request.headers.get('X-Request-Id')
                or request.headers.get('X-Request-ID'),
            }
        ).get(propagate=True)
        refreshed = ConnectorRun.objects.get(id=run.id)
        return JsonResponse(
            {'run': _connector_run_to_dict(refreshed), 'result': result},
            status=201,
        )

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def connector_run_cancel(request, run_id: str):
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    forbidden = require_any_role(request, {'policy.admin', 'tenant.admin'})
    if forbidden:
        return forbidden
    try:
        run = ConnectorRun.objects.select_related('ingestion').get(id=run_id)
    except (ValidationError, ConnectorRun.DoesNotExist):
        return JsonResponse({'error': 'not_found'}, status=404)
    if run.status in {
        ConnectorRun.Status.SUCCEEDED,
        ConnectorRun.Status.FAILED,
        ConnectorRun.Status.CANCELLED,
    }:
        return JsonResponse({'error': 'run_not_cancellable'}, status=400)
    run.status = ConnectorRun.Status.CANCELLED
    run.finished_at = timezone.now()
    run.error_message = 'cancelled by user'
    run.save(update_fields=['status', 'finished_at', 'error_message', 'updated_at'])
    run.ingestion.status = IngestionRequest.Status.FAILED
    run.ingestion.save(update_fields=['status', 'updated_at'])
    tenant_schema = _tenant_schema(request)
    maybe_publish_event(
        event_type='connector.run.cancelled',
        tenant_id=tenant_schema,
        routing_key=f'{tenant_schema}.connector.run.cancelled',
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_connector_run_to_dict(run),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    maybe_publish_audit_event(
        tenant_id=tenant_schema,
        action='connector.run.cancelled',
        resource_type='connector_run',
        resource_id=str(run.id),
        correlation_id=getattr(request, 'correlation_id', None)
        or request.headers.get('X-Correlation-Id'),
        user_id=request.headers.get('X-User-Id'),
        data=_connector_run_to_dict(run),
        rabbitmq_url=os.environ.get('RABBITMQ_URL'),
    )
    return JsonResponse(_connector_run_to_dict(run))


@csrf_exempt
def ingestions(request):
    """Create tenant-scoped ingestion requests."""
    if request.method == 'GET':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
        qs = IngestionRequest.objects.order_by('-created_at')
        project_id = request.GET.get('project_id')
        if project_id:
            qs = qs.filter(project_id=project_id)
        return JsonResponse({'items': [_ingestion_to_dict(item) for item in qs]})

    if request.method == 'POST':
        forbidden = require_role(request, 'catalog.editor')
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)

        connector = payload.get('connector')
        source = payload.get('source')
        project_id = payload.get('project_id')
        if not connector:
            return JsonResponse({'error': 'connector is required'}, status=400)
        if source is None or not isinstance(source, dict):
            return JsonResponse({'error': 'source must be an object'}, status=400)
        project = None
        if project_id:
            try:
                project = Project.objects.get(id=project_id)
            except (ValidationError, Project.DoesNotExist):
                return JsonResponse({'error': 'project_not_found'}, status=404)

        ing = IngestionRequest.objects.create(
            project=project,
            connector=connector,
            source=source,
            mode=payload.get('mode') or '',
        )
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='ingestion.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.ingestion.created',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_ingestion_to_dict(ing),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='ingestion.created',
            resource_type='ingestion',
            resource_id=str(ing.id),
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_ingestion_to_dict(ing),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_ingestion_to_dict(ing), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def ingestion_detail(request, ingestion_id: str):
    try:
        ing = IngestionRequest.objects.get(id=ingestion_id)
    except IngestionRequest.DoesNotExist:
        return JsonResponse({'error': 'not_found'}, status=404)

    if request.method == 'GET':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
        data = _ingestion_to_dict(ing)
        latest_run = ing.connector_runs.order_by('-created_at').first()
        if latest_run:
            data['execution'] = {
                'state': latest_run.status,
                'started_at': latest_run.started_at.isoformat() if latest_run.started_at else None,
                'finished_at': latest_run.finished_at.isoformat() if latest_run.finished_at else None,
                'retry_count': latest_run.retry_count,
                'progress': latest_run.progress,
            }
        return JsonResponse(data)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def assets(request):
    """List/create tenant-scoped DataAssets.

    GET supports simple offset pagination via ?limit= (default 100, max 500) and ?offset= (default 0).
    """
    if request.method == 'GET':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
        try:
            limit = int(request.GET.get('limit', '100'))
            offset = int(request.GET.get('offset', '0'))
        except ValueError:
            return JsonResponse({'error': 'limit/offset must be integers'}, status=400)
        limit = min(max(limit, 1), 500)
        offset = max(offset, 0)

        qs = DataAsset.objects.order_by('created_at')[offset : offset + limit]
        items = [_asset_to_dict(a) for a in qs]
        return JsonResponse({'items': items})

    if request.method == 'POST':
        forbidden = require_role(request, 'catalog.editor')
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)

        qualified_name = payload.get('qualified_name')
        asset_type = payload.get('asset_type')
        description = payload.get('description')
        owner = payload.get('owner')
        if not qualified_name or not asset_type:
            return JsonResponse({'error': 'qualified_name and asset_type are required'}, status=400)
        if description is not None and not isinstance(description, str):
            return JsonResponse({'error': 'description must be a string'}, status=400)
        if owner is not None and not isinstance(owner, str):
            return JsonResponse({'error': 'owner must be a string'}, status=400)
        tags = _parse_string_list(payload.get('tags'))
        if tags is None:
            return JsonResponse({'error': 'tags must be an array of strings'}, status=400)
        classifications = _parse_string_list(payload.get('classifications'))
        if classifications is None:
            return JsonResponse({'error': 'classifications must be an array of strings'}, status=400)
        invalid = _validate_classification_values(classifications)
        if invalid:
            return JsonResponse(
                {'error': 'unknown_classifications', 'items': invalid},
                status=400,
            )

        asset = DataAsset.objects.create(
            qualified_name=qualified_name,
            display_name=payload.get('display_name') or qualified_name,
            asset_type=asset_type,
            description='' if description is None else description,
            owner='' if owner is None else owner,
            tags=tags,
            classifications=classifications,
            properties=payload.get('properties') or {},
        )
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='asset.created',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.catalog.asset.created',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_asset_to_dict(asset),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='asset.created',
            resource_type='asset',
            resource_id=str(asset.id),
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_asset_to_dict(asset),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_asset_to_dict(asset), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def asset_detail(request, asset_id: str):
    try:
        asset = DataAsset.objects.get(id=asset_id)
    except DataAsset.DoesNotExist:
        return JsonResponse({'error': 'not_found'}, status=404)

    if request.method == 'GET':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
        return JsonResponse(_asset_to_dict(asset))

    if request.method == 'PUT':
        forbidden = require_role(request, 'catalog.editor')
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)

        if 'asset_type' in payload and payload['asset_type'] != asset.asset_type:
            return JsonResponse({'error': 'asset_type is immutable'}, status=400)

        if 'display_name' in payload:
            if payload['display_name'] is None:
                return JsonResponse({'error': 'display_name cannot be null'}, status=400)
            asset.display_name = payload['display_name']
        if 'description' in payload:
            if payload['description'] is not None and not isinstance(payload['description'], str):
                return JsonResponse({'error': 'description must be a string'}, status=400)
            asset.description = '' if payload['description'] is None else payload['description']
        if 'owner' in payload:
            if payload['owner'] is not None and not isinstance(payload['owner'], str):
                return JsonResponse({'error': 'owner must be a string'}, status=400)
            asset.owner = '' if payload['owner'] is None else payload['owner']
        if 'tags' in payload:
            tags = _parse_string_list(payload['tags'])
            if tags is None:
                return JsonResponse({'error': 'tags must be an array of strings'}, status=400)
            asset.tags = tags
        if 'classifications' in payload:
            classifications = _parse_string_list(payload['classifications'])
            if classifications is None:
                return JsonResponse({'error': 'classifications must be an array of strings'}, status=400)
            invalid = _validate_classification_values(classifications)
            if invalid:
                return JsonResponse(
                    {'error': 'unknown_classifications', 'items': invalid},
                    status=400,
                )
            forbidden = _enforce_sensitivity_upgrade_role(
                request,
                existing_values=asset.classifications or [],
                next_values=classifications,
            )
            if forbidden:
                return forbidden
            asset.classifications = classifications
        if 'properties' in payload:
            props = payload['properties']
            if props is None:
                asset.properties = {}
            else:
                if not isinstance(props, dict):
                    return JsonResponse({'error': 'properties must be an object'}, status=400)
                merged = dict(asset.properties)
                for k, v in props.items():
                    if v is None:
                        merged.pop(k, None)
                    else:
                        merged[k] = v
                asset.properties = merged
        asset.save()
        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='asset.updated',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.catalog.asset.updated',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_asset_to_dict(asset),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='asset.updated',
            resource_type='asset',
            resource_id=str(asset.id),
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data=_asset_to_dict(asset),
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse(_asset_to_dict(asset))

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def lineage_edges(request):
    """Tenant-scoped lineage edge upsert/query."""
    if request.method == 'POST':
        forbidden = require_role(request, 'catalog.editor')
        if forbidden:
            return forbidden
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)
        items = payload.get('items')
        if not isinstance(items, list):
            return JsonResponse({'error': 'items must be a list'}, status=400)

        required_ids: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                return JsonResponse({'error': 'items must be objects'}, status=400)
            from_id = item.get('from_asset_id')
            to_id = item.get('to_asset_id')
            edge_type = item.get('edge_type')
            if not from_id or not to_id or not edge_type:
                return JsonResponse({'error': 'from_asset_id, to_asset_id, and edge_type are required'}, status=400)
            try:
                uuid.UUID(from_id)
                uuid.UUID(to_id)
            except ValueError:
                return JsonResponse({'error': 'from_asset_id and to_asset_id must be UUIDs'}, status=400)
            required_ids.add(from_id)
            required_ids.add(to_id)

        existing = {str(a.id) for a in DataAsset.objects.filter(id__in=list(required_ids))}
        if required_ids - existing:
            return JsonResponse({'error': 'asset_not_found'}, status=404)

        out: list[dict[str, Any]] = []
        for item in items:
            edge, _ = LineageEdge.objects.update_or_create(
                from_asset_id=item['from_asset_id'],
                to_asset_id=item['to_asset_id'],
                edge_type=item['edge_type'],
                defaults={'properties': item.get('properties') or {}},
            )
            out.append(_edge_to_dict(edge))

        tenant_schema = _tenant_schema(request)
        maybe_publish_event(
            event_type='lineage.edge.upserted',
            tenant_id=tenant_schema,
            routing_key=f'{tenant_schema}.lineage.edge.upserted',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data={'items': out},
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        maybe_publish_audit_event(
            tenant_id=tenant_schema,
            action='lineage.edge.upserted',
            resource_type='lineage_edge',
            correlation_id=getattr(request, 'correlation_id', None) or request.headers.get('X-Correlation-Id'),
            user_id=request.headers.get('X-User-Id'),
            data={'items': out},
            rabbitmq_url=os.environ.get('RABBITMQ_URL'),
        )
        return JsonResponse({'items': out})

    if request.method == 'GET':
        forbidden = require_any_role(request, {'catalog.reader', 'catalog.editor', 'tenant.admin'})
        if forbidden:
            return forbidden
        asset_id = request.GET.get('asset_id')
        if not asset_id:
            return JsonResponse({'error': 'asset_id is required'}, status=400)
        try:
            uuid.UUID(asset_id)
        except ValueError:
            return JsonResponse({'error': 'asset_id must be a UUID'}, status=400)
        try:
            DataAsset.objects.get(id=asset_id)
        except (ValidationError, DataAsset.DoesNotExist):
            return JsonResponse({'error': 'not_found'}, status=404)

        direction = request.GET.get('direction', 'downstream')
        if direction not in {'upstream', 'downstream'}:
            return JsonResponse({'error': 'direction must be upstream or downstream'}, status=400)

        depth = _parse_int_clamped(request.GET.get('depth'), default=1, min_value=1, max_value=5)
        if depth is None:
            return JsonResponse({'error': 'depth must be an integer'}, status=400)

        current = {asset_id}
        visited_assets = {asset_id}
        edges: dict[str, LineageEdge] = {}
        for _ in range(depth):
            if not current:
                break
            if direction == 'upstream':
                qs = LineageEdge.objects.filter(to_asset_id__in=list(current))
                next_assets = {str(e.from_asset_id) for e in qs}
            else:
                qs = LineageEdge.objects.filter(from_asset_id__in=list(current))
                next_assets = {str(e.to_asset_id) for e in qs}
            for e in qs:
                edges[str(e.id)] = e
            current = next_assets - visited_assets
            visited_assets |= current

        edge_items = [_edge_to_dict(e) for e in edges.values()]
        assets = [_asset_to_dict(a) for a in DataAsset.objects.filter(id__in=list(visited_assets))]
        return JsonResponse({'edges': edge_items, 'assets': assets})

    return JsonResponse({'error': 'method_not_allowed'}, status=405)
