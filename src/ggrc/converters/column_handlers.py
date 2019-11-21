# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
This module provides all column handlers for objects in the ggrc module.

If you want to add column handler you should decide is it handler default
or custom for current model.
If this handler is default than you will add it into
_DEFAULT_COLUMN_HANDLERS_DICT dict.
If this handler is custom for current model you should place it in model
class in _SPECIFIC_HANDLERS_ATTR method

If you want to get handler for your model
call function aggregate_column_handlers with you model class as argument.

Example:

It returns all dict like:
    {
        "column_1"; HandlerClass1,
        "column_2": HandlerClass2,
        ...
    }
Which contain handler for your Model.
"""

from ggrc.converters.handlers import assessment_template
from ggrc.converters.handlers import boolean
from ggrc.converters.handlers import comments
from ggrc.converters.handlers import default_people
from ggrc.converters.handlers import handlers
from ggrc.converters.handlers import list_handlers
from ggrc.converters.handlers import template
from ggrc.converters.handlers import document
from ggrc.converters.handlers import evidence
from ggrc.converters.handlers import custom_attribute
from ggrc.converters.handlers import acl
from ggrc.converters.handlers import issue_tracker

from ggrc.converters.handlers.snapshot_instance_column_handler import (
    SnapshotInstanceColumnHandler
)

_DEFAULT_COLUMN_HANDLERS_DICT = {
    "archived": boolean.CheckboxColumnHandler,
    "assertions": handlers.JsonListColumnHandler,
    "assessment_template": assessment_template.AssessmentTemplateColumnHandler,
    "assignee": handlers.UserColumnHandler,
    "audit": handlers.AuditColumnHandler,
    "categories": handlers.JsonListColumnHandler,
    "comments": comments.CommentColumnHandler,
    "company": handlers.TextColumnHandler,
    "contact": handlers.UserColumnHandler,
    "created_at": handlers.ExportOnlyDateColumnHandler,
    "default_assignees": default_people.DefaultPersonColumnHandler,
    "default_verifier": default_people.DefaultPersonColumnHandler,
    "delete": handlers.DeleteColumnHandler,
    "description": handlers.TextColumnHandler,
    "design": handlers.ConclusionColumnHandler,
    "documents": handlers.DocumentsColumnHandler,
    "documents_file": document.DocumentFileHandler,
    "documents_reference_url": document.DocumentReferenceUrlHandler,
    "due_date": handlers.DateColumnHandler,
    "email": handlers.EmailColumnHandler,
    "end_date": handlers.DateColumnHandler,
    "evidences_file": evidence.EvidenceFileHandler,
    "evidences_url": evidence.EvidenceUrlHandler,
    "finished_date": handlers.NullableDateColumnHandler,
    "fraud_related": boolean.CheckboxColumnHandler,
    "is_enabled": boolean.CheckboxColumnHandler,
    "is_verification_needed": boolean.StrictBooleanColumnHandler,
    "issue_tracker": handlers.ExportOnlyIssueTrackerColumnHandler,
    "key_control": boolean.KeyControlColumnHandler,
    "kind": handlers.OptionColumnHandler,
    "labels": handlers.LabelsHandler,
    "last_assessment_date": handlers.DateColumnHandler,
    "last_comment": handlers.ExportOnlyColumnHandler,
    "last_deprecated_date": handlers.DateColumnHandler,
    "link": handlers.TextColumnHandler,
    "means": handlers.OptionColumnHandler,
    "modified_by": handlers.DirecPersonMappingColumnHandler,
    "created_by": handlers.ExportOnlyPersonColumnHandler,
    "name": handlers.TextColumnHandler,
    "network_zone": handlers.OptionColumnHandler,
    "notes": handlers.TextColumnHandler,
    "operationally": handlers.ConclusionColumnHandler,
    "procedure_description": handlers.TextColumnHandler,
    "review_status": handlers.ReviewableColumnHandler,
    "reviewers": handlers.ReviewersColumnHandler,
    "readonly": boolean.AdminCheckboxColumnHandler,
    "program": handlers.ProgramColumnHandler,
    "ra_counsel": handlers.UserColumnHandler,
    "ra_manager": handlers.UserColumnHandler,
    "recipients": list_handlers.ValueListHandler,
    "report_end_date": handlers.DateColumnHandler,
    "report_start_date": handlers.DateColumnHandler,
    "secondary_contact": handlers.UserColumnHandler,
    "send_by_default": boolean.CheckboxColumnHandler,
    "slug": handlers.ColumnHandler,
    "start_date": handlers.DateColumnHandler,
    "status": handlers.StatusColumnHandler,
    "template_custom_attributes": template.TemplateCaColumnHandler,
    "template_object_type": template.TemplateObjectColumnHandler,
    "test_plan": handlers.TextColumnHandler,
    "test_plan_procedure": boolean.CheckboxColumnHandler,
    "title": handlers.TextColumnHandler,
    "updated_at": handlers.ExportOnlyDateColumnHandler,
    "verified_date": handlers.NullableDateColumnHandler,
    "verify_frequency": handlers.OptionColumnHandler,
    "risk_type": handlers.TextColumnHandler,
    "threat_source": handlers.TextColumnHandler,
    "threat_event": handlers.TextColumnHandler,
    "vulnerability": handlers.TextColumnHandler,

    # External app attributes
    "last_submitted_at": handlers.ExportOnlyDateColumnHandler,
    "last_submitted_by": handlers.ExportOnlyPersonColumnHandler,
    "last_verified_at": handlers.ExportOnlyDateColumnHandler,
    "last_verified_by": handlers.ExportOnlyPersonColumnHandler,

    # IssueTracker fields
    "component_id": issue_tracker.IssueTrackerAddsColumnHandler,
    "hotlist_id": issue_tracker.IssueTrackerAddsColumnHandler,
    "issue_priority": issue_tracker.IssueTrackerWithValidStates,
    "issue_severity": issue_tracker.IssueTrackerWithValidStates,
    "issue_title": issue_tracker.IssueTrackerTitleColumnHandler,
    "issue_type": issue_tracker.IssueTrackerWithValidStates,
    "enabled": issue_tracker.IssueTrackerEnabledHandler,
    "people_sync_enabled": issue_tracker.PeopleSyncEnabledHandler,

    # Mapping column handlers
    "__mapping__:person": handlers.PersonMappingColumnHandler,
    "__unmapping__:person": handlers.PersonUnmappingColumnHandler,
    "directive": handlers.RequirementDirectiveColumnHandler,

    # Prefix column handlers:
    # If a column handler does not match any full key, the key will be split on
    # ":" and the prefix will be used in the handler search. This is used to
    # group many handler keys for the same handler into a more concise list.
    "__mapping__": handlers.MappingColumnHandler,
    "__unmapping__": handlers.MappingColumnHandler,
    "__custom__": custom_attribute.CustomAttributeColumnHandler,
    "__object_custom__": custom_attribute.ObjectCaColumnHandler,
    "__snapshot_mapping__": SnapshotInstanceColumnHandler,
    "__acl__": acl.AccessControlRoleColumnHandler,

    "custom_attribute_definition": comments.LCACommentColumnHandler,
}


_SPECIFIC_HANDLERS_ATTR = "specific_column_handlers"


def aggregate_column_handlers(cls):
  """Generates handlers for model class

  Attributes:
      cls (model class): Model class for which you are looking for handlers

  Returns:
      result_handlers (dict): dict of all handlers for current model class
                              the keys are column names
                              the values are handler classes
  """
  result_handlers = _DEFAULT_COLUMN_HANDLERS_DICT.copy()
  handlers = getattr(cls, _SPECIFIC_HANDLERS_ATTR, None)
  if handlers:
    result_handlers.update(handlers())
  return result_handlers
