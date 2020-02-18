# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module with common validators for Relationship."""

from ggrc import login
from ggrc.models import exceptions


def _check_relation_types_group(type1, type2, group1, group2):
  """Checks if 2 types belong to 2 groups

  Args:
    type1: name of model 1
    type2: name of model 2
    group1: Collection of model names which belong to group 1
    group1: Collection of model names which belong to group 2
  Return:
    True if types belong to different groups, else False
  """

  if (type1 in group1 and type2 in group2) or (type2 in group1 and
                                               type1 in group2):
    return True

  return False


def validate_relation_by_type(source_type, destination_type):
  """Checks if a mapping is allowed between given types.

  Args:
    source_type: name of source model in relationship
    destination_type: name of destination model in relationship
  """
  if login.is_external_app_user():
    # external users can map and unmap scoping objects
    return

  from ggrc.models import all_models
  scoping_models_names = all_models.get_scope_model_names()

  # Check Regulation and Standard
  if _check_relation_types_group(
      source_type,
      destination_type,
      scoping_models_names,
      ("Regulation", "Standard"),
  ):
    raise exceptions.ValidationError(
        u"You do not have the necessary permissions to map and unmap "
        u"scoping objects to directives in this application. Please "
        u"contact your administrator if you have any questions.")

  # Check Control
  control_external_only_mappings = set(scoping_models_names)
  control_external_only_mappings.update(("Regulation", "Standard", "Risk"))
  if _check_relation_types_group(
      source_type,
      destination_type,
      control_external_only_mappings,
      ("Control", ),
  ):
    raise exceptions.ValidationError(
        u"You do not have the necessary permissions to map and unmap "
        u"controls to scoping objects, standards and regulations in this "
        u"application. Please contact your administrator "
        u"if you have any questions.")

  # Check Risk
  risk_external_only_mappings = set(scoping_models_names)
  risk_external_only_mappings.update(("Regulation", "Standard", "Control"))
  if _check_relation_types_group(
      source_type,
      destination_type,
      risk_external_only_mappings,
      ("Risk", ),
  ):
    raise exceptions.ValidationError(
        u"You do not have the necessary permissions to map and unmap "
        u"risks to scoping objects, controls, standards "
        u"and regulations in this application."
        u"Please contact your administrator if you have any questions.")

  # Check Scope Objects
  scope_external_only_mappings = set(scoping_models_names)
  scope_external_only_mappings.update(
      ("Regulation", "Standard", "Control", "Risk")
  )
  if _check_relation_types_group(
      source_type,
      destination_type,
      scope_external_only_mappings,
      set(scoping_models_names),
  ):
    raise exceptions.ValidationError(
        u"You do not have the necessary permissions to map and unmap "
        u"scoping objects to scoping objects, risks, controls, standards "
        u"and regulations in this application."
        u"Please contact your administrator if you have any questions.")
