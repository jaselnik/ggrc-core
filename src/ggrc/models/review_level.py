# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
  Module contains definition for ReviewLevel model.

  Review Level model is used for storing data for
  specific review levels of assessments of type
  "Multiple Levels Of Verification".
"""

from sqlalchemy.ext.hybrid import hybrid_property

from ggrc import db
from ggrc.models import (
    mixins,
    reflection,
    person,
)


# pylint: disable=invalid-name
review_levels_people = db.Table(
    "review_levels_people",
    db.Model.metadata,
    db.Column(
        "review_level_id",
        db.Integer,
        db.ForeignKey("review_levels.id"),
    ),
    db.Column(
        "person_id",
        db.Integer,
        db.ForeignKey("people.id"),
    )
)


class ReviewLevel(
    mixins.base.Dictable,
    mixins.base.ContextRBAC,
    mixins.base.Identifiable,
    db.Model
):
  """
    Model for storing data for specific review levels of
    assessments of type "Multiple Levels Of Verification".
  """

  # pylint: disable=too-few-public-methods
  class Status(object):
    """
      Container for valid review level statuses.
    """
    NOT_STARTED = "Not Started"
    IN_REVIEW = "In Review"
    REVIEWED = "Reviewed"

    ALL = (NOT_STARTED, IN_REVIEW, REVIEWED)

  __tablename__ = "review_levels"

  assessment_id = db.Column(db.Integer, db.ForeignKey("assessments.id"))
  level_number = db.Column(db.Integer, nullable=False)
  status = db.Column(db.String, nullable=False, default="Not Started")
  completed_at = db.Column(db.DateTime, nullable=True, default=None)
  verified_by = db.Column(db.Integer, db.ForeignKey("people.id"))

  verifiers = db.relationship("Person", secondary=review_levels_people)

  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute(
          "users",
          update=False,
          create=False,
      ),
      reflection.Attribute(
          "level_number",
          update=False,
          create=False,
      ),
      reflection.Attribute(
          "status",
          update=True,
          create=False,
      ),
  )

  @hybrid_property
  def users(self):
    """
      Alias for verification_levels InstrumentedAttribute.

      Used by ggrc.builder.json for serializing and
      updating assessment objects.
    """
    return self.verifiers

  def update_from_dict(self, review_level_dict):
    """
      Update attribute values from given dict.

      Args:
        review_level_dict - dictionary containing values for
          review_level fields.
    """
    for attribute in (
        "status",
        "completed_at",
        "verified_by",
        "users",
    ):
      if attribute in review_level_dict:
        if attribute == "users":
          self.update_verifiers(review_level_dict["users"])
        else:
          setattr(self, attribute, review_level_dict[attribute])

    self._validate_status()

  def update_verifiers(self, users):
    """
      Update current review level verifiers list.

      Method compares existing verfiers and given verifiers
      to figure out what to do with current review level
      verifiers i.e. remove or add.

      Args:
        users - dictionaries with user ids to be used
        for comparison.
    """
    current_verifiers_ids = {verifier.id for verifier in self.verifiers}
    updated_verifiers_ids = {user["id"] for user in users}

    verifiers_to_remove = current_verifiers_ids - updated_verifiers_ids
    verifiers_to_add = updated_verifiers_ids - current_verifiers_ids

    for verifier_id in verifiers_to_remove:
      self._validate_id_type(verifier_id)
      db.session.execute("""
        DELETE FROM review_levels_people
        WHERE
          review_level_id = {} AND
          person_id = {}
      """.format(self.id, verifier_id))

    for verifier_id in verifiers_to_add:
      self._validate_id_type(verifier_id)
      self._validate_user_exists(verifier_id)

      db.session.execute("""
        INSERT INTO review_levels_people (review_level_id, person_id)
        VALUES ({}, {})
      """.format(self.id, verifier_id))

  def _validate_status(self):
    """
      Validate review_level status.

      It should not be possible to change status
      from 'Not Started' if there are no verifiers
      assigned to current review level.
    """
    if (
        self.status in (self.Status.REVIEWED, self.Status.IN_REVIEW) and
        not self.verifiers
    ):
      raise ValueError(
          "Can't change review_level with id = {} from '{}' "
          "due to missing verifiers.".format(
              self.id,
              self.Status.NOT_STARTED,
          )
      )

  @staticmethod
  def _validate_id_type(verifier_id):
    """
      Validate wether given verifier_id is a valid id.

      Args:
        verifier_id - id value to validate.
    """
    if (
        (
            not isinstance(verifier_id, long) and
            not isinstance(verifier_id, int)
        ) or
        verifier_id < 1
    ):
      raise ValueError("Field user.id can only be positive number")

  @staticmethod
  def _validate_user_exists(verifier_id):
    """
      Validate wether given verifier_id is an id of
      existing user.

      Args:
        verifier_id - id to use for user lookup.
    """
    if not person.Person.query.get(verifier_id):
      raise ValueError("User with id = {} is not found".format(verifier_id))

  @classmethod
  def find_and_update(cls, review_level_dict):
    """
      Find and update review level which conforms given
      dict attribute values.

      Args:
        review_level_dict - dictionary containing values for
          review_level fields. Must include review level id.
    """
    cls._validate_id_type(review_level_dict["id"])

    review_level = cls.query.get(review_level_dict["id"])

    review_level.update_from_dict(review_level_dict)
