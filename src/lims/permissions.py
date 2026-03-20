from __future__ import annotations

from django.http import JsonResponse

from core.identity import request_roles, roles_enforced


PERMISSION_DEFINITIONS = {
    'lims.dashboard.view': {
        'description': 'View the tenant LIMS shell, launchpad, and dashboard summaries.',
        'guardian_codename': 'view_lims_dashboard',
        'object_type': 'service',
    },
    'lims.reference.view': {
        'description': 'View lab, study, site, and other reference records.',
        'guardian_codename': 'view_reference_record',
        'object_type': 'reference_record',
    },
    'lims.reference.manage': {
        'description': 'Create, update, and retire reference records used by LIMS workflows.',
        'guardian_codename': 'manage_reference_record',
        'object_type': 'reference_record',
    },
    'lims.metadata.view': {
        'description': 'View metadata vocabularies, field definitions, schemas, and validation results.',
        'guardian_codename': 'view_metadata_schema',
        'object_type': 'metadata_schema',
    },
    'lims.metadata.manage': {
        'description': 'Create, publish, and bind configurable metadata schemas for LIMS forms and workflow steps.',
        'guardian_codename': 'manage_metadata_schema',
        'object_type': 'metadata_schema',
    },
    'lims.workflow_config.view': {
        'description': 'View workflow templates, version history, and step-schema bindings.',
        'guardian_codename': 'view_workflow_template',
        'object_type': 'workflow_template',
    },
    'lims.workflow_config.manage': {
        'description': 'Create, version, validate, and publish workflow templates for LIMS operations.',
        'guardian_codename': 'manage_workflow_template',
        'object_type': 'workflow_template',
    },
    'lims.workflow_task.view': {
        'description': 'View workflow task state, assignee, and task-form metadata.',
        'guardian_codename': 'view_workflow_task',
        'object_type': 'workflow_task',
    },
    'lims.workflow_task.execute': {
        'description': 'Complete operator task actions on assigned workflow work items.',
        'guardian_codename': 'execute_workflow_task',
        'object_type': 'workflow_task',
    },
    'lims.workflow_task.assign': {
        'description': 'Assign or reassign workflow tasks for operational balancing.',
        'guardian_codename': 'assign_workflow_task',
        'object_type': 'workflow_task',
    },
    'lims.workflow_task.approve': {
        'description': 'Approve or reject QA/manager checkpoints on workflow tasks.',
        'guardian_codename': 'approve_workflow_task',
        'object_type': 'workflow_task',
    },
    'lims.artifact.view': {
        'description': 'View sensitive biospecimen, QC, and derived workflow artifacts.',
        'guardian_codename': 'view_sensitive_artifact',
        'object_type': 'sensitive_artifact',
    },
    'lims.artifact.manage': {
        'description': 'Approve, correct, or retire sensitive LIMS artifacts.',
        'guardian_codename': 'manage_sensitive_artifact',
        'object_type': 'sensitive_artifact',
    },
}

ROLE_BUNDLES = {
    'lims.operator': {
        'description': 'Bench/operator role for day-to-day task execution.',
        'permissions': {
            'lims.dashboard.view',
            'lims.metadata.view',
            'lims.reference.view',
            'lims.workflow_config.view',
            'lims.workflow_task.view',
            'lims.workflow_task.execute',
            'lims.artifact.view',
        },
    },
    'lims.manager': {
        'description': 'Operational manager role for coordination and reference-data stewardship.',
        'permissions': {
            'lims.dashboard.view',
            'lims.metadata.view',
            'lims.metadata.manage',
            'lims.reference.view',
            'lims.reference.manage',
            'lims.workflow_config.view',
            'lims.workflow_config.manage',
            'lims.workflow_task.view',
            'lims.workflow_task.execute',
            'lims.workflow_task.assign',
            'lims.artifact.view',
        },
    },
    'lims.qa': {
        'description': 'Quality and compliance role for approvals, reviews, and sensitive artifacts.',
        'permissions': {
            'lims.dashboard.view',
            'lims.metadata.view',
            'lims.reference.view',
            'lims.workflow_config.view',
            'lims.workflow_task.view',
            'lims.workflow_task.approve',
            'lims.artifact.view',
            'lims.artifact.manage',
        },
    },
    'lims.admin': {
        'description': 'Tenant-local LIMS administrator role with full module permissions.',
        'permissions': set(PERMISSION_DEFINITIONS.keys()),
    },
}

LEGACY_ROLE_BUNDLES = {
    'catalog.reader': {
        'description': 'Legacy platform read role mapped into the LIMS read surface.',
        'permissions': {
            'lims.dashboard.view',
            'lims.metadata.view',
            'lims.reference.view',
            'lims.workflow_config.view',
            'lims.workflow_task.view',
            'lims.artifact.view',
        },
    },
    'catalog.editor': {
        'description': 'Legacy platform editor role mapped into LIMS operational edits.',
        'permissions': {
            'lims.dashboard.view',
            'lims.metadata.view',
            'lims.metadata.manage',
            'lims.reference.view',
            'lims.reference.manage',
            'lims.workflow_config.view',
            'lims.workflow_config.manage',
            'lims.workflow_task.view',
            'lims.workflow_task.execute',
            'lims.artifact.view',
        },
    },
    'policy.admin': {
        'description': 'Legacy governance admin role mapped into QA-style approvals.',
        'permissions': {
            'lims.dashboard.view',
            'lims.metadata.view',
            'lims.reference.view',
            'lims.workflow_config.view',
            'lims.workflow_task.view',
            'lims.workflow_task.approve',
            'lims.artifact.view',
            'lims.artifact.manage',
        },
    },
    'tenant.admin': {
        'description': 'Legacy tenant admin role mapped to full LIMS administration.',
        'permissions': set(PERMISSION_DEFINITIONS.keys()),
    },
}

VIEWFLOW_TASK_ACTION_PERMISSIONS = {
    'view': 'lims.workflow_task.view',
    'execute': 'lims.workflow_task.execute',
    'assign': 'lims.workflow_task.assign',
    'approve': 'lims.workflow_task.approve',
}


def guardian_permission_name(permission_key: str) -> str:
    definition = PERMISSION_DEFINITIONS[permission_key]
    return f"lims.{definition['guardian_codename']}"


def permissions_for_roles(roles: set[str]) -> set[str]:
    grants: set[str] = set()
    for role in roles:
        bundle = ROLE_BUNDLES.get(role) or LEGACY_ROLE_BUNDLES.get(role)
        if bundle:
            grants.update(bundle['permissions'])
    return grants


def has_lims_permission(roles: set[str], permission_key: str) -> bool:
    return permission_key in permissions_for_roles(roles)


def require_lims_permission(request, permission_key: str):
    if not roles_enforced():
        return None
    if has_lims_permission(request_roles(request), permission_key):
        return None
    return JsonResponse({'error': 'forbidden'}, status=403)


def viewflow_task_permission_name(action: str) -> str:
    permission_key = VIEWFLOW_TASK_ACTION_PERMISSIONS[action]
    return guardian_permission_name(permission_key)


def permission_summary_for_roles(roles: set[str]) -> dict[str, object]:
    effective_permissions = permissions_for_roles(roles)
    return {
        'request_roles': sorted(roles),
        'effective_permissions': sorted(effective_permissions),
        'role_bundles': [
            {
                'role': role,
                'description': bundle['description'],
                'permissions': sorted(bundle['permissions']),
            }
            for role, bundle in sorted(ROLE_BUNDLES.items())
        ],
        'legacy_role_compatibility': [
            {
                'role': role,
                'description': bundle['description'],
                'permissions': sorted(bundle['permissions']),
            }
            for role, bundle in sorted(LEGACY_ROLE_BUNDLES.items())
        ],
        'object_permissions': [
            {
                'permission': key,
                'guardian_name': guardian_permission_name(key),
                'object_type': definition['object_type'],
                'description': definition['description'],
            }
            for key, definition in sorted(PERMISSION_DEFINITIONS.items())
        ],
        'viewflow_task_permissions': {
            action: viewflow_task_permission_name(action)
            for action in sorted(VIEWFLOW_TASK_ACTION_PERMISSIONS)
        },
    }
