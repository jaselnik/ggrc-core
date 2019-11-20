# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
This module provides all column handlers for objects in the ggrc module.

If you want to add column handler you should decide is it handler default
or custom for current model.
If this handler is default than you will add it into _COLUMN_HANDLERS dict in
subdict by key "DEFAULT_HANDLERS_KEY"
If this handler is custom for current model you shuld add it in COLUMN_HANDLERS
dict by key "Model.__name__"

You may add column handlers in your extensions.
To make this you should add "EXTENSION_HANDLERS_ATTR" in __init__.py in your
extenstion.
It should be callable or dict.
If you want to add default handler you should add it in you
extension_handlers_dict by key "DEFAULT_HANDLERS_KEY"
If it is custom handler for current model, you should add it in
your "EXTENSION_HANDLERS_ATTR" dict by key "Model.__name__"

If you want to get hendler for your model
call function model_column_handlers with you model class as argument.

Example:

It returns all dict like:
    {
        "column_1"; HandlerClass1,
        "column_2": HandlerClass2,
        ...
    }
Thich contain handler for your Model.
"""

from copy import deepcopy

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
from ggrc.extensions import get_extension_modules


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
    "verification_workflow": handlers.TextColumnHandler,
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


DEFAULT_HANDLERS_KEY = "default"
EXTENSION_HANDLERS_ATTR = "contributed_column_handlers"


_COLUMN_HANDLERS = {
    DEFAULT_HANDLERS_KEY: _DEFAULT_COLUMN_HANDLERS_DICT,
}


def get_extensions_column_handlers():
  """Search through all enabled modules for their contributed column handlers.

  Returns:
    result_handlers (dict): dict of all extension handlers
  """
  result_handlers = deepcopy(_COLUMN_HANDLERS)
  for extension_module in get_extension_modules():
    extension_handlers = getattr(
        extension_module, EXTENSION_HANDLERS_ATTR, None)
    if callable(extension_handlers):
      extension_handlers = extension_handlers()
    if isinstance(extension_handlers, dict):
      for key, value_dict in extension_handlers.iteritems():
        result_handlers[key] = result_handlers.get(key, {})
        result_handlers[key].update(value_dict)
  return result_handlers


COLUMN_HANDLERS = get_extensions_column_handlers()


def model_column_handlers(cls):
  """Generates handlers for model class

  Attributes:
      cls (model class): Model class for which you are looking for handlers

  Returns:
      result_handlers (dict): dict of all handlers for current model class
                              the keys are column names
                              the values are handler classes
  """
  result_handlers = COLUMN_HANDLERS[DEFAULT_HANDLERS_KEY].copy()
  result_handlers.update(COLUMN_HANDLERS.get(cls.__name__, {}))
  return result_handlers
