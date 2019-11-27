# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
  Module contains definition for ReviewLevel model.

  Review Level model is used for storing data for
  specific review levels of assessments of type
  "Multiple Levels Of Verification".
"""

from ggrc import db
from ggrc.models import mixins, reflection

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

  __tablename__ = "review_levels"

  assessment_id = db.Column(db.Integer, db.ForeignKey("assessments.id"))
  level_number = db.Column(db.Integer, nullable=False)
  status = db.Column(db.String, nullable=False, default="Not Started")
  completed_at = db.Column(db.DateTime, nullable=True, default=None)
  verified_by = db.Column(db.Integer, db.ForeignKey("people.id"))

  _api_attrs = reflection.ApiAttributes(
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
    ):
      if attribute in review_level_dict:
        setattr(self, attribute, review_level_dict[attribute])

  @classmethod
  def find_and_update(cls, review_level_dict):
    """
      Find and update review level which conforms given
      dict attribute values.

      Args:
        review_level_dict - dictionary containing values for
          review_level fields. Must include review level id.
    """
    review_level = cls.query.get(review_level_dict["id"])

    review_level.update_from_dict(review_level_dict)
