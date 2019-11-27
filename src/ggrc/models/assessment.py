# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for Assessment object"""

from sqlalchemy import ext, orm, and_

from ggrc import (
    db,
    utils,
)
from ggrc.builder import simple_property
from ggrc.fulltext import mixin

from ggrc.models import (
    audit,
    comment,
    custom_attribute_definition,
    reflection,
    object_person,
    relationship,
    deferred,
    review_level,
    assessment_template,
)

from ggrc.models.mixins import (
    with_last_comment,
    base,
    BusinessObject,
    CustomAttributable,
    FinishedDate,
    Notifiable,
    TestPlanned,
    LastDeprecatedTimeboxed,
    VerifiedDate,
    reminderable,
    statusable,
    labeled,
    issue_tracker,
    rest_handable,
    with_custom_restrictions,
)

from ggrc.models.mixins.audit_relationship import AuditRelationship
from ggrc.models.mixins.assignable import Assignable
from ggrc.models.mixins.autostatuschangeable import AutoStatusChangeable
from ggrc.models.mixins.with_action import WithAction
from ggrc.models.mixins.with_evidence import WithEvidence
from ggrc.models.mixins.with_similarity_score import WithSimilarityScore


class Assessment(
    Assignable,
    statusable.Statusable,
    AuditRelationship,
    AutoStatusChangeable,
    TestPlanned,
    CustomAttributable,
    WithEvidence,
    comment.Commentable,
    object_person.Personable,
    reminderable.Reminderable,
    relationship.Relatable,
    LastDeprecatedTimeboxed,
    WithSimilarityScore,
    FinishedDate,
    VerifiedDate,
    Notifiable,
    WithAction,
    labeled.Labeled,
    with_last_comment.WithLastComment,
    issue_tracker.IssueTrackedWithUrl,
    base.ContextRBAC,
    BusinessObject,
    with_custom_restrictions.WithCustomRestrictions,
    rest_handable.WithPutBeforeCommitHandable,
    mixin.Indexed,
    db.Model,
):

  """Class representing Assessment.

  Assessment is an object representing an individual assessment performed on
  a specific object during an audit to ascertain whether or not
  certain conditions were met for that object.
  """

  __tablename__ = 'assessments'
  _title_uniqueness = False

  REWORK_NEEDED = u"Rework Needed"
  NOT_DONE_STATES = statusable.Statusable.NOT_DONE_STATES | {REWORK_NEEDED, }
  VALID_STATES = tuple(NOT_DONE_STATES | statusable.Statusable.DONE_STATES |
                       statusable.Statusable.INACTIVE_STATES)

  REMINDERABLE_HANDLERS = {
      "statusToPerson": {
          "handler":
              reminderable.Reminderable.handle_state_to_person_reminder,
          "data": {
              statusable.Statusable.START_STATE: "Assignees",
              "In Progress": "Assignees"
          },
          "reminders": {"assessment_assignees_reminder", }
      }
  }

  design = deferred.deferred(
      db.Column(db.String, nullable=False, default=""),
      "Assessment",
  )
  operationally = deferred.deferred(
      db.Column(db.String, nullable=False, default=""),
      "Assessment",
  )
  audit_id = deferred.deferred(
      db.Column(db.Integer, db.ForeignKey('audits.id'), nullable=False),
      'Assessment',
  )
  assessment_type = deferred.deferred(
      db.Column(db.String, nullable=False, server_default="Control"),
      "Assessment",
  )

  # whether to use the object test plan on snapshot mapping
  test_plan_procedure = db.Column(db.Boolean, nullable=False, default=True)

  verification_workflow = db.Column(
      db.String,
      nullable=False,
      default=assessment_template.VerificationWorkflow.STANDARD,
  )

  review_levels_count = db.Column(
      db.Integer,
  )

  review_levels = db.relationship("ReviewLevel")

  object = {}  # we add this for the sake of client side error checking

  VALID_CONCLUSIONS = (
      "Effective",
      "Ineffective",
      "Needs improvement",
      "Not Applicable",
  )

  # REST properties
  _api_attrs = reflection.ApiAttributes(
      'design',
      'operationally',
      'audit',
      'assessment_type',
      'test_plan_procedure',
      'review_levels',
      reflection.Attribute(
          'verification_workflow',
          create=False,
          update=False,
      ),
      reflection.Attribute(
          'review_levels_count',
          create=False,
          update=False,
      ),
      reflection.Attribute('archived', create=False, update=False),
      reflection.Attribute('folder', create=False, update=False),
      reflection.Attribute('object', create=False, update=False),
  )

  _include_links = ["review_levels"]
  _update_raw = ["review_levels"]

  _fulltext_attrs = [
      'archived',
      'design',
      'operationally',
      'folder',
      'verification_workflow',
      'review_levels_count'
  ]

  AUTO_REINDEX_RULES = [
      mixin.ReindexRule("Audit", lambda x: x.assessments, ["archived"]),
  ]

  _custom_publish = {
      'audit': audit.build_audit_stub,
  }

  _in_progress_restrictions = (
      "access_control_list",
      "description",
      "title",
      "labels",
      "test_plan",
      "assessment_type",
      "slug",
      "notes",
      "start_date",
      "design",
      "operationally",
      "reminderType",
      "issue_tracker",
      "map: Snapshot",
      "map: Issue",
  )

  _done_state_restrictions = _in_progress_restrictions + (
      "custom_attributes_values",
      "map: Evidence",
  )

  _restriction_condition = {
      "status": {
          (statusable.Statusable.START_STATE,
           statusable.Statusable.PROGRESS_STATE,
           REWORK_NEEDED,
           statusable.Statusable.DONE_STATE): _in_progress_restrictions,
          (statusable.Statusable.VERIFIED_STATE,
           statusable.Statusable.FINAL_STATE,
           statusable.Statusable.DEPRECATED): _done_state_restrictions
      }
  }

  ASSESSMENT_TYPE_OPTIONS = \
      assessment_template.AssessmentTemplate.DEFAULT_ASSESSMENT_TYPE_OPTIONS

  _aliases = {
      "owners": None,
      "verification_workflow": {
          "display_name": "Verification Workflow",
          "description": (
              "Allowed values are:\n"
              "Standard flow\n"
              "SOX 302 flow\n"
              "Multi-level verification flow\n\n"
              "Specify number of Verification Levels "
              "for assessments with multi-level verification flow."
          ),
          "mandatory": False,
          "view_only": True,
      },
      "assessment_template": {
          "display_name": "Template",
          "ignore_on_update": True,
          "filter_by": "_ignore_filter",
          "type": reflection.AttributeInfo.Type.MAPPING,
      },
      "assessment_type": {
          "display_name": "Assessment Type",
          "mandatory": False,
          "description": "Allowed values are:\n{}".format(
              '\n'.join(ASSESSMENT_TYPE_OPTIONS)),
      },
      "design": {
          "display_name": "Conclusion: Design",
          "description": "Allowed values are:\n{}".format(
              '\n'.join(VALID_CONCLUSIONS)),
      },
      "operationally": {
          "display_name": "Conclusion: Operation",
          "description": "Allowed values are:\n{}".format(
              '\n'.join(VALID_CONCLUSIONS)),
      },
      "archived": {
          "display_name": "Archived",
          "mandatory": False,
          "ignore_on_update": True,
          "view_only": True,
          "description": "Allowed values are:\nyes\nno"
      },
      "test_plan": "Assessment Procedure",
      # Currently we decided to have 'Due Date' alias for start_date,
      # but it can be changed in future
      "start_date": "Due Date",
      "status": {
          "display_name": "State",
          "mandatory": False,
          "description": "Allowed values are:\n{}".format('\n'.join(
              VALID_STATES))
      },
      "issue_tracker": {
          "display_name": "Ticket Tracker",
          "mandatory": False,
          "view_only": True,
      },
  }

  @staticmethod
  def specific_column_handlers():
    """Column handlers for assessment obj"""
    from ggrc.converters.handlers import handlers
    return {"verification_workflow": handlers.TextColumnHandler}

  # pylint: disable=no-self-use
  def set_raw_review_levels(self, review_level_dicts):
    for review_level_dict in review_level_dicts or []:
      review_level.ReviewLevel.find_and_update(review_level_dict)

  @classmethod
  def _ignore_filter(cls, _):
    return None

  @classmethod
  def _populate_query(cls, query):
    return query.options(
        orm.Load(cls).undefer_group("Assessment_complete"),
        orm.Load(cls).joinedload("audit").undefer_group("Audit_complete"),
        orm.Load(cls).joinedload("audit").joinedload(
            audit.Audit.issuetracker_issue,
        ),
    )

  @classmethod
  def eager_query(cls, **kwargs):
    return cls._populate_query(super(Assessment, cls).eager_query(**kwargs))

  @classmethod
  def indexed_query(cls):
    return super(Assessment, cls).indexed_query().options(
        orm.Load(cls).load_only(
            "id",
            "design",
            "operationally",
            "audit_id",
        ),
        orm.Load(cls).joinedload(
            "audit"
        ).load_only(
            "archived",
            "folder"
        ),
    )

  @simple_property
  def sox_302_enabled(self):
    """Flag defining if SOX 302 flow is activated for object."""
    return self.verification_workflow == \
        assessment_template.VerificationWorkflow.SOX302

  def _has_negative_cavs(self):
    """Check if current object has any CAVs with values marked as negative."""
    from ggrc.models.custom_attribute_value \
        import CustomAttributeValue as cav_model

    # pylint: disable=not-an-iterable
    local_cads = {
        cad.id: cad for cad in self.local_custom_attribute_definitions
    }

    local_cavs = []
    if local_cads:
      local_cavs = cav_model.query.filter(
          cav_model.custom_attribute_id.in_(local_cads.keys()),
      ).all()

    return any(
        local_cads[cav.custom_attribute_id].is_value_negative(cav)
        for cav in local_cavs
    )

  def exec_sox_302_status_flow(self, initial_state):
    # type: (collections.namedtuple) -> None
    """Execute SOX 302 status change flow.

    Perform SOX 302 status change flow for object method is called on. Current
    object should be instance of `statusable.Statusable` and should have flag
    `sox_302_enabled` set to `True` in order for SOX 302 to be executed.

    Args:
      initial_state (collections.namedtuple): Initial state of the object.
    """
    follow_sox_302_flow = (
        isinstance(self, statusable.Statusable) and
        isinstance(self, CustomAttributable) and
        self.sox_302_enabled
    )

    moved_in_review = (
        initial_state.status != self.status and
        self.status == statusable.Statusable.DONE_STATE
    )

    if (
        follow_sox_302_flow and
        moved_in_review and
        not self._has_negative_cavs()
    ):
      self.status = statusable.Statusable.FINAL_STATE

  def handle_put_before_commit(self, initial_state):
    # type: (collections.namedtuple) -> None
    """Handle `model_put_before_commit` signals.

    This method is called after `model_put_before_commit` signal is being sent.
    Triggers SOX 302 status change flow.

    Args:
      initial_state (collections.namedtuple): Initial state of the object.
    """
    self.exec_sox_302_status_flow(initial_state)

  @simple_property
  def archived(self):
    """Returns a boolean whether assessment is archived or not."""
    return self.audit.archived if self.audit else False

  @simple_property
  def folder(self):
    return self.audit.folder if self.audit else ""

  @ext.declarative.declared_attr
  def object_level_definitions(cls):  # pylint: disable=no-self-argument
    """Set up a backref so that we can create an object level custom
       attribute definition without the need to do a flush to get the
       assessment id.

      This is used in the relate_ca method in hooks/assessment.py.
    """
    cad = custom_attribute_definition.CustomAttributeDefinition
    current_type = cls.__name__

    def join_expr():
      return and_(
          orm.foreign(orm.remote(cad.definition_id)) == cls.id,
          cad.definition_type == utils.underscore_from_camelcase(current_type),
      )

    # Since there is some kind of generic relationship on CAD side, correct
    # join expression for backref should be provided. If default, every call of
    # "{}_definition".format(definition_type) on CAD will produce a lot of
    # unnecessary DB queries returning nothing.
    def backref_join_expr():
      return orm.remote(cls.id) == orm.foreign(cad.definition_id)

    return db.relationship(
        "CustomAttributeDefinition",
        primaryjoin=join_expr,
        backref=db.backref(
            "{}_definition".format(
                utils.underscore_from_camelcase(current_type)
            ),
            lazy="joined",
            primaryjoin=backref_join_expr,
        ),
        cascade="all, delete-orphan",
    )

  @orm.validates("status")
  def validate_status(self, key, value):
    value = super(Assessment, self).validate_status(key, value)
    # pylint: disable=unused-argument
    if self.status == value:
      return value
    if self.status == self.REWORK_NEEDED:
      valid_states = [self.DONE_STATE, self.FINAL_STATE, self.DEPRECATED]
      if value not in valid_states:
        if not getattr(self, "skip_rework_validation", False):
          raise ValueError("Assessment in `Rework Needed` "
                           "state can be only moved to: [{}]".format(
                               ",".join(valid_states)))
    return value

  @orm.validates("operationally")
  def validate_opperationally(self, key, value):
    """Validate assessment operationally by validating conclusion"""
    # pylint: disable=unused-argument
    return value if value in self.VALID_CONCLUSIONS else ""

  @orm.validates("design")
  def validate_design(self, key, value):
    """Validate assessment design by validating conclusion"""
    # pylint: disable=unused-argument
    return value if value in self.VALID_CONCLUSIONS else ""

  @orm.validates("assessment_type")
  def validate_assessment_type(self, key, value):
    """Validate assessment type to be the same as existing model name"""
    # pylint: disable=unused-argument
    # pylint: disable=no-self-use
    from ggrc.snapshotter.rules import Types
    if value and value not in Types.all:
      raise ValueError(
          "Assessment type '{}' is not snapshotable".format(value)
      )
    return value

  def create_review_levels(self):
    """
      Create review levels for assessment when it is generated
      from assessment template.
    """

    if self.review_levels:
      return

    if self.verification_workflow == \
      assessment_template.VerificationWorkflow.MLV:  # noqa

      for level_number in range(1, self.review_levels_count + 1):
        db.session.add(
            review_level.ReviewLevel(
                level_number=level_number,
                assessment_id=self.id,
                context_id=self.context_id,
            ),
        )
        db.session.commit()

  def log_json(self):
    out_json = super(Assessment, self).log_json()
    out_json["folder"] = self.folder

    return out_json
