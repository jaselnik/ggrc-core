# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
  Module contains definition for SavedSearch model.

  SavedSearch model is used for storing query API
  requests allowing users to save their searches
  and share them with other users (sharing is
  implemented on FE side).
"""

import json

from sqlalchemy.orm import validates
from sqlalchemy.schema import UniqueConstraint

from ggrc import db
from ggrc.models import all_models
from ggrc.models.exceptions import ValidationError
from ggrc.models.mixins.base import CreationTimeTracked, Dictable, Identifiable
from ggrc.utils.contributed_objects import CONTRIBUTED_OBJECTS

_EXTENSION_SUPPORTED_OBJECT_TYPES = [
    all_models.Workflow,
    all_models.TaskGroup,
    all_models.TaskGroupTask,
    all_models.CycleTaskGroupObjectTask,
]


def _get_supported_object_types():
  """Get list of supported object types"""

  result = list(model.__name__ for model in CONTRIBUTED_OBJECTS)
  for model in _EXTENSION_SUPPORTED_OBJECT_TYPES:
    result.append(model.__name__)
  return result


SUPPORTED_OBJECT_TYPES = _get_supported_object_types()


class SavedSearch(CreationTimeTracked, Dictable, Identifiable, db.Model):
  """
    Represents table which stores query API filters for
    given user.
  """

  __tablename__ = "saved_searches"
  __table_args__ = (
      UniqueConstraint(
          "person_id",
          "name",
          name="unique_pair_saved_search_name_person_id",
      ),
  )

  ADVANCED_SEARCH = "AdvancedSearch"
  GLOBAL_SEARCH = "GlobalSearch"
  VALID_SAVED_SEARCH_TYPES = [ADVANCED_SEARCH, GLOBAL_SEARCH]

  name = db.Column(db.String, nullable=False)
  object_type = db.Column(db.String, nullable=False)
  person_id = db.Column(db.Integer, db.ForeignKey("people.id"))
  filters = db.Column(db.Text, nullable=True)
  search_type = db.Column(db.String, nullable=False)

  # pylint: disable-msg=too-many-arguments
  def __init__(self, name, object_type, user, search_type, filters=""):
    self.validate_name_uniqueness(user, name, search_type, object_type)

    super(SavedSearch, self).__init__(
        name=name,
        object_type=object_type,
        person_id=user.id,
        search_type=search_type,
        filters=filters,
    )

  @staticmethod
  def validate_name_uniqueness(user, name, search_type, object_type):
    """Check that for given user there are no saved searches with name."""
    if search_type == SavedSearch.GLOBAL_SEARCH:
      saved_seqrch_q = user.saved_searches.filter(
          SavedSearch.name == name,
          SavedSearch.search_type == search_type,
      )
      if db.session.query(saved_seqrch_q.exists()).scalar():
        raise ValidationError(
            u"Global Saved search with name '{}' already exists".format(name)
        )
    else:
      saved_seqrch_q = user.saved_searches.filter(
          SavedSearch.name == name,
          SavedSearch.search_type == search_type,
          SavedSearch.object_type == object_type,
      )
      if db.session.query(saved_seqrch_q.exists()).scalar():
        raise ValidationError(
            u"Advanced Saved search for {} with "
            u"name '{}' already exists".format(object_type, name)
        )

  @validates("name")
  def validate_name(self, _, name):
    """
      Validate that name is not blank.
    """
    # pylint: disable=no-self-use
    if not name:
      raise ValidationError("Saved search name can't be blank")

    return name

  @validates("object_type")
  def validate_object_type(self, _, object_type):
    """
      Validate that supplied object type supports search api filters saving.
    """
    # pylint: disable=no-self-use
    if object_type and object_type not in SUPPORTED_OBJECT_TYPES:
      raise ValidationError(
          u"Object of type '{}' does not support search saving".format(
              object_type,
          ),
      )

    return object_type

  @validates("filters")
  def validate_filters(self, _, filters):
    """Validate correctness of supplied search filters.

    Validates that filters is valid json formatted string.

    Args:
      filters: string value with filters

    Returns:
      JSON object with filters

    """
    # pylint: disable=no-self-use
    if filters:
      return json.dumps(filters)
    return None

  @validates('search_type')
  def validate_search_type(self, _, saved_search_type):
    """Valid that saved search type is correct

    Args: Type of saved search. Valid values are AdvancedSearch and
    GlobalSearch

    Returns:
      Correct saved search type

    Raises:
      ValidationError: if saved_search_type is missing or not valid value
    """
    # pylint: disable=no-self-use
    if not saved_search_type:
      raise ValidationError("Saved search type can't be blank")

    if saved_search_type not in self.VALID_SAVED_SEARCH_TYPES:
      raise ValidationError("Invalid saved search type")

    return saved_search_type
