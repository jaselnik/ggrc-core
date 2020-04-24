# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Collects all permissions for Global Creator role."""

# pylint: disable=invalid-name

scope = "System"
description = """
  This role grants a user basic object creation and editing permission.
  """

owner_base = [
    "Option",
    "CustomAttributeDefinition",
    "CustomAttributeValue",
    "NotificationConfig",
]
owner_read = owner_base + [
    "AccessControlList",
    "AccessControlRole",
    "BackgroundTask",
    {
        "type": "Relationship",
        "terms": {
            "property_name": "source,destination",
            "action": "read"
        },
        "condition": "relationship",
    },
    {
        "type": "Proposal",
        "condition": "is_allowed_based_on",
        "terms": {
            "property_name": "instance",
            "action": "read",
        },
    },
    "Role",
    "Comment",
    "UserRole",
    "Context",
    "Person",
    "Label",
    "ObjectLabel",
]

owner_delete = owner_base + [
    {
        "type": "Relationship",
        "terms": {
            "property_name": "source,destination",
            "action": "update"
        },
        "condition": "relationship",
    },
    {
        "type": "Comment",
        "terms": {
            "property_name": "modified_by",
            "value": "$current_user"
        },
        "condition": "is"
    },
    {
        "type": "Proposal",
        "condition": "is_allowed_based_on",
        "terms": {
            "property_name": "instance",
            "action": "update",
        },
    },
]

owner_update = owner_delete + [
    "PersonProfile",
]

permissions = {
    "read": owner_read,
    "create": [
        "AccountBalance",
        {
            "type": "Audit",
            "condition": "is_allowed_based_on",
            "terms": {
                "property_name": "program",
                "action": "update",
            },
        },
        {
            "type": "Snapshot",
            "condition": "is_allowed_based_on",
            "terms": {
                "property_name": "parent",
                "action": "update",
            },
        },
        "AssessmentTemplate",
        "BackgroundTask",
        {
            "type": "TaskGroup",
            "condition": "is_workflow_admin",
            "terms": {},
        },
        {
            "type": "TaskGroupTask",
            "condition": "is_workflow_admin",
            "terms": {},
        },
        {
            "type": "Cycle",
            "condition": "is_workflow_admin",
            "terms": {},
        },
        {
            "type": "CycleTaskGroup",
            "condition": "is_workflow_admin",
            "terms": {},
        },
        {
            "type": "CycleTaskGroupObjectTask",
            "condition": "is_workflow_admin",
            "terms": {},
        },
        {
            "type": "TaskGroupObject",
            "condition": "is_workflow_admin",
            "terms": {},
        },
        "Control",
        "Comment",
        {
            "type": "Assessment",
            "condition": "is_auditor",
            "terms": {},
        },
        "Issue",
        "DataAsset",
        "AccessGroup",
        "Directive",
        "Contract",
        "Policy",
        "Regulation",
        "Standard",
        "Document",
        "Evidence",
        "Facility",
        "Market",
        "Objective",
        "ObjectPerson",
        "Option",
        "OrgGroup",
        "Risk",
        "Threat",
        "Vendor",
        "PopulationSample",
        "Product",
        {
            "type": "Proposal",
            "condition": "is_allowed_based_on",
            "terms": {
                "property_name": "instance",
                "action": "read",
            },
        },
        "Project",
        {
            "type": "Relationship",
            "terms": {
                "property_name": "source,destination",
                "action": "update"
            },
            "condition": "relationship",
        },
        "Requirement",
        "System",
        "KeyReport",
        "Process",
        "Metric",
        "ProductGroup",
        "Program",
        "TechnologyEnvironment",
        "Context",
        "Review"
    ],
    "update": owner_update,
    "delete": owner_delete + [
        {
            "type": "CycleTaskGroup",
            "condition": "is_workflow_admin",
            "terms": {},
        },
    ],
}
