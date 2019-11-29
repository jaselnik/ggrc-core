# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""A module containing the implementation of the assessment template entity."""

from collections import OrderedDict

from sqlalchemy import orm
from sqlalchemy.orm import validates
from werkzeug.exceptions import Forbidden

from ggrc import (
    db,
    login,
    settings,
)

from ggrc.access_control.roleable import Roleable
from ggrc.builder import simple_property
from ggrc.models import audit
from ggrc.models import mixins
from ggrc.models import relationship
from ggrc.models.mixins import audit_relationship
from ggrc.models.mixins import base
from ggrc.models.mixins import clonable
from ggrc.models.mixins import issue_tracker
from ggrc.models.exceptions import ValidationError
from ggrc.models.reflection import AttributeInfo
from ggrc.models import reflection
from ggrc.models.types import JsonType
from ggrc.services import signals
from ggrc.fulltext.mixin import Indexed
from ggrc.rbac.permissions import permissions_for
from ggrc.integrations import constants


# pylint: disable=too-few-public-methods
class VerificationWorkflow(object):
  """
    Container with available verification_workflow
    column values.
  """
  STANDARD = "STANDARD"
  SOX302 = "SOX302"
  MLV = "MLV"

  ALL = (STANDARD, SOX302, MLV)


class AssessmentTemplate(
    audit_relationship.AuditRelationship,
    relationship.Relatable,
    mixins.Titled,
    mixins.CustomAttributable,
    Roleable,
    issue_tracker.IssueTrackedWithConfig,
    base.ContextRBAC,
    mixins.Slugged,
    mixins.Stateful,
    clonable.MultiClonable,
    Indexed,
    db.Model,
):

  """A class representing the assessment template entity.

  An Assessment Template is a template that allows users for easier creation of
  multiple Assessments that are somewhat similar to each other, avoiding the
  need to repeatedly define the same set of properties for every new Assessment
  object.
  """
  __tablename__ = "assessment_templates"
  _mandatory_default_people = ("assignees",)

  PER_OBJECT_CUSTOM_ATTRIBUTABLE = True

  RELATED_TYPE = 'assessment'

  # the type of the Default Assessment Type
  template_object_type = db.Column(db.String, nullable=True)

  # whether to use the control test plan as a procedure
  test_plan_procedure = db.Column(db.Boolean, nullable=False, default=False)

  # procedure description
  procedure_description = db.Column(db.Text, nullable=False, default=u"")

  # the people that should be assigned by default to each assessment created
  # within the releated audit
  default_people = db.Column(JsonType, nullable=False)

  # parent audit
  audit_id = db.Column(db.Integer, db.ForeignKey('audits.id'), nullable=False)

  verification_workflow = db.Column(
      db.String,
      nullable=False,
      default=VerificationWorkflow.STANDARD,
  )

  review_levels_count = db.Column(
      db.Integer,
  )

  # labels to show to the user in the UI for various default people values
  DEFAULT_PEOPLE_LABELS = OrderedDict([
      ("Admin", "Object Admins"),
      ("Audit Lead", "Audit Captain"),
      ("Auditors", "Auditors"),
      ("Principal Assignees", "Principal Assignees"),
      ("Secondary Assignees", "Secondary Assignees"),
      ("Primary Contacts", "Primary Contacts"),
      ("Secondary Contacts", "Secondary Contacts"),
      ("Control Operators", "Control Operators"),
      ("Control Owners", "Control Owners"),
      ("Risk Owners", "Risk Owners"),
      ("Other Contacts", "Other Contacts"),
  ])

  # labels to show as hint all Assessment Types except of Control and Risk
  _DEFAULT_PEOPLE_LABELS_ACTUAL = OrderedDict([
      ("Admin", "Object Admins"),
      ("Audit Lead", "Audit Captain"),
      ("Auditors", "Auditors"),
      ("Principal Assignees", "Principal Assignees"),
      ("Secondary Assignees", "Secondary Assignees"),
      ("Primary Contacts", "Primary Contacts"),
      ("Secondary Contacts", "Secondary Contacts"),
  ])

  # labels to show as hint in Default Assignees/Verifiers for Control
  _DEFAULT_PEOPLE_LABELS_CONTROL = OrderedDict([
      ("Admin", "Object Admins"),
      ("Audit Lead", "Audit Captain"),
      ("Auditors", "Auditors"),
      ("Principal Assignees", "Principal Assignees"),
      ("Secondary Assignees", "Secondary Assignees"),
      ("Control Operators", "Control Operators"),
      ("Control Owners", "Control Owners"),
      ("Other Contacts", "Other Contacts"),
  ])

  # labels to show as hint in Default Assignees/Verifiers for Risk
  _DEFAULT_PEOPLE_LABELS_RISK = OrderedDict([
      ("Admin", "Object Admins"),
      ("Audit Lead", "Audit Captain"),
      ("Auditors", "Auditors"),
      ("Principal Assignees", "Principal Assignees"),
      ("Secondary Assignees", "Secondary Assignees"),
      ("Risk Owners", "Risk Owners"),
      ("Other Contacts", "Other Contacts"),
  ])

  _title_uniqueness = False

  DRAFT = 'Draft'
  ACTIVE = 'Active'
  DEPRECATED = 'Deprecated'

  VALID_STATES = (DRAFT, ACTIVE, DEPRECATED, )

  # REST properties
  _api_attrs = reflection.ApiAttributes(
      'template_object_type',
      'test_plan_procedure',
      'procedure_description',
      'default_people',
      'audit',
      'verification_workflow',
      'review_levels_count',
      reflection.Attribute('issue_tracker', create=False, update=False),
      reflection.Attribute('archived', create=False, update=False),
      reflection.Attribute(
          'DEFAULT_PEOPLE_LABELS', create=False, update=False),
  )

  _fulltext_attrs = [
      "archived",
      "verification_workflow",
      "review_levels_count",
  ]

  _custom_publish = {
      'audit': audit.build_audit_stub,
  }

  DEFAULT_ASSESSMENT_TYPE_OPTIONS = (
      "Access Groups",
      "Account Balances",
      "Data Assets",
      "Facilities",
      "Key Reports",
      "Markets",
      "Org Groups",
      "Processes",
      "Product Groups",
      "Products",
      "Systems",
      "Technology Environments",
      "Vendors",
      "Contracts",
      "Controls",
      "Objectives",
      "Policies",
      "Regulations",
      "Requirements",
      "Risks",
      "Standards",
      "Threats",
  )

  TICKET_TRACKER_STATES = ("On", "Off")
  _HINT_VERIFIERS_ASSIGNEES = "Allowed values are:\n" \
      "For all Assessment Types except of Control and Risk:" \
      "\n{}\nuser@example.com\n" \
      "For Assessment type of Control:\n{}\n" \
      "user@example.com\n" \
      "For Assessment type of Risk:\n{}\n" \
      "user@example.com".format(
          "\n".join(_DEFAULT_PEOPLE_LABELS_ACTUAL.values()),
          "\n".join(_DEFAULT_PEOPLE_LABELS_CONTROL.values()),
          "\n".join(_DEFAULT_PEOPLE_LABELS_RISK.values()),
      )

  _aliases = {
      "verification_workflow": {
          "display_name": "Verification Workflow",
          "mandatory": False,
          "description": (
              "Allowed values are:\n"
              "Standard flow\n"
              "SOX 302 flow\n"
              "Multi-level verification flow\n\n"
              "Specify number of Verification Levels "
              "for assessments with multi-level verification flow."
          ),
      },
      "status": {
          "display_name": "State",
          "mandatory": False,
          "description": "Allowed values are:\n{}".format(
              '\n'.join(VALID_STATES))
      },
      "default_assignees": {
          "display_name": "Default Assignees",
          "mandatory": True,
          "filter_by": None,
          "description": _HINT_VERIFIERS_ASSIGNEES,
      },
      "default_verifier": {
          "display_name": "Default Verifiers",
          "mandatory": False,
          "filter_by": None,
          "description": _HINT_VERIFIERS_ASSIGNEES,
      },
      "procedure_description": {
          "display_name": "Default Assessment Procedure",
          "filter_by": None,
      },
      "test_plan_procedure": {
          "display_name": "Use Control Assessment Procedure",
          "mandatory": False,
      },
      "template_object_type": {
          "display_name": "Default Assessment Type",
          "mandatory": True,
          "description": "Allowed values are:\n{}".format(
              '\n'.join(DEFAULT_ASSESSMENT_TYPE_OPTIONS),
          ),
      },
      "archived": {
          "display_name": "Archived",
          "mandatory": False,
          "ignore_on_update": True,
          "view_only": True,
      },
      "issue_severity": {
          "display_name": "Severity",
          "mandatory": False,
          "description": "Allowed values are:\n{}".format(
              '\n'.join(constants.AVAILABLE_SEVERITIES))
      },
      "enabled": {
          "display_name": "Ticket Tracker Integration",
          "mandatory": False,
          "description": "Allowed values are:\n{}".format(
              '\n'.join(TICKET_TRACKER_STATES)),
      },
      "template_custom_attributes": {
          "display_name": "Custom Attributes",
          "type": AttributeInfo.Type.SPECIAL_MAPPING,
          "filter_by": None,
          "description": (
              "List of custom attributes for the assessment template\n"
              "One attribute per line. fields are separated by commas ','\n\n"
              "<attribute type>, <attribute name>, [<attribute value1>, "
              "<attribute value2>, ...]\n\n"
              "Valid attribute types: Text, Rich Text, Date, Checkbox, Person,"
              "Multiselect, Dropdown.\n"
              "attribute name: Any single line string without commas. Leading "
              "and trailing spaces are ignored.\n"
              "list of attribute values: Comma separated list, only used if "
              "attribute type is 'Dropdown'. Prepend '(a)' if the value has a "
              "mandatory attachment and/or '(c)' if the value requires a "
              "mandatory comment.\n\n"
              "list of attribute values (only if 'SOX 302 Assessment "
              "workflow' = YES):\n"
              "- for Dropdown: Comma separated list. Prepend '(a)' if the "
              "value has a mandatory attachment and/or '(c)' if the value "
              "requires a mandatory comment and/or '(n)' if the value should "
              "be treated as negative answer.\n"
              "- for Text and Reach text: options possible are 'Not empty' or "
              "'Empty'. Prepend '(n)' if the value should be treated as "
              "negative answer.\n\n"
              "Limitations: Dropdown values can not start with either '(a)', "
              "'(c)' or '(n)' and attribute names can not contain commas ','."
          ),
      },
  }

  @staticmethod
  def specific_column_handlers():
    """Column handlers for assessment template obj"""
    from ggrc.converters.handlers import handlers
    return {"verification_workflow": handlers.TextColumnHandler}

  @classmethod
  def eager_query(cls, **kwargs):
    query = super(AssessmentTemplate, cls).eager_query(**kwargs)
    return query.options(
        orm.Load(cls).joinedload("audit").undefer_group("Audit_complete"),
        orm.Load(cls).joinedload("audit").joinedload(
            audit.Audit.issuetracker_issue
        ),
    )

  @classmethod
  def indexed_query(cls):
    query = super(AssessmentTemplate, cls).indexed_query()
    return query.options(
        orm.Load(cls).joinedload("audit").undefer_group("Audit_complete")
    )

  @staticmethod
  def generate_slug_prefix():
    return "TEMPLATE"

  @staticmethod
  def set_verification_workflow(assessment, template):
    """
      Populate assessment verification workflow and related fields from
      related assessment template.

      Args:
        assessment - Assessment model object.
        template - AssessmentTemplate model object.
    """

    if template:
      assessment.verification_workflow = template.verification_workflow
      assessment.review_levels_count = template.review_levels_count
      assessment.create_review_levels()

  @validates('default_people')
  def validate_default_people(self, key, value):
    """Check that default people lists are not empty.

    Check if the default_people contains both assignees and verifiers. The
    values of those fields must be truthy, and if the value is a string it
    must be a valid default people label. If the value is not a string, it
    should be a list of valid user ids, but that is too expensive to test in
    this validator.
    """
    # pylint: disable=unused-argument
    for mandatory in self._mandatory_default_people:
      mandatory_value = value.get(mandatory)
      if (not mandatory_value or
              isinstance(mandatory_value, list) and
              any(not isinstance(p_id, (int, long))
                  for p_id in mandatory_value) or
              isinstance(mandatory_value, basestring) and
              mandatory_value not in self.DEFAULT_PEOPLE_LABELS):
        raise ValidationError(
            'Invalid value for default_people.{field}. Expected a people '
            'label in string or a list of int people ids, received {value}.'
            .format(field=mandatory, value=mandatory_value),
        )

    return value

  @orm.validates("verification_workflow")
  # pylint: disable=unused-argument,no-self-use
  def validate_verification_workflow(self, attr_name, attr_value):
    """
      Check that verification_level is set to a valid
      verification flow string value.
    """
    if attr_value not in VerificationWorkflow.ALL:
      raise ValueError(
          "Verification workflow should be one of {}, {}, {}.".format(
              *VerificationWorkflow.ALL
          ),
      )

    return attr_value

  @orm.validates("review_levels_count")
  # pylint: disable=unused-argument
  def validate_review_levels_count(self, attr_name, attr_value):
    """
      Check that review_levels_count lies in a range with
      boundaries specified in application settings.
    """
    if attr_value not in range(
        settings.REVIEW_LEVELS_MIN_COUNT,
        settings.REVIEW_LEVELS_MAX_COUNT + 1,
    ) and self.verification_workflow == VerificationWorkflow.MLV:
      raise ValueError(
          "Number of review levels should be in range [{}, {}]"
          " if multiple review levels are enabled.".format(
              settings.REVIEW_LEVELS_MIN_COUNT,
              settings.REVIEW_LEVELS_MAX_COUNT,
          ),
      )

    return attr_value

  @simple_property
  def sox_302_enabled(self):
    """Flag defining if SOX 302 flow is activated for object."""
    return self.verification_workflow == VerificationWorkflow.SOX302

  @simple_property
  def archived(self):
    """Fetch the archived boolean from Audit"""
    if hasattr(self, 'context') and hasattr(self.context, 'related_object'):
      return getattr(self.context.related_object, 'archived', False)
    return False

  def _clone(self, target=None):
    """Clone Assessment Template.

    Args:
      target: Destination Audit object.

    Returns:
      Instance of assessment template copy.
    """
    data = {
        "title": self.title,
        "audit": target,
        "template_object_type": self.template_object_type,
        "test_plan_procedure": self.test_plan_procedure,
        "procedure_description": self.procedure_description,
        "default_people": self.default_people,
        "modified_by": login.get_current_user(),
        "status": self.status,
        "verification_workflow": self.verification_workflow,
    }
    assessment_template_copy = AssessmentTemplate(**data)
    db.session.add(assessment_template_copy)
    return assessment_template_copy

  def clone(self, target):
    """Clone Assessment Template and related custom attributes."""
    assessment_template_copy = self._clone(target)
    rel = relationship.Relationship(
        source=target,
        destination=assessment_template_copy
    )
    db.session.add(rel)
    db.session.flush()

    # pylint: disable=not-an-iterable
    for cad in self.custom_attribute_definitions:
      # pylint: disable=protected-access
      cad._clone(assessment_template_copy)

    return (assessment_template_copy, rel)


def create_audit_relationship(audit_stub, obj):
  """Create audit to assessment template relationship"""
  # pylint: disable=W0212
  parent_audit = audit.Audit.query.get(audit_stub["id"])
  if not permissions_for()._is_allowed_for(parent_audit, "update"):
    raise Forbidden()
  rel = relationship.Relationship(
      source=parent_audit,
      destination=obj,
      context=parent_audit.context)
  db.session.add(rel)


@signals.Restful.model_posted.connect_via(AssessmentTemplate)
def handle_assessment_template(sender, obj=None, src=None, service=None):
  # pylint: disable=unused-argument
  """Handle Assessment Template POST

  If "audit" is set on POST, create relationship with Assessment template.
  """
  if "audit" in src:
    create_audit_relationship(src["audit"], obj)
