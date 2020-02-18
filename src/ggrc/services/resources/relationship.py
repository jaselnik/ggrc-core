# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Custom Resource for Relationship that creates Snapshots when needed.

When Audit-Snapshottable Relationship is POSTed, a Snapshot should be created
instead.
"""

from werkzeug.exceptions import MethodNotAllowed, Forbidden

from ggrc.builder import json as json_builder
from ggrc import db
import ggrc.services.common
from ggrc.models.snapshot import Snapshot
from ggrc.models import relationship
from ggrc.models.hooks.common import check_mapping_permissions
from ggrc.models.mixins.with_readonly_access import WithReadOnlyAccess
from ggrc.login import get_current_user
from ggrc.rbac import permissions
from ggrc.utils import referenced_objects
from ggrc.utils.validators import relationship as relationship_validators


class RelationshipResource(ggrc.services.common.Resource):
  """Custom Resource that transforms Relationships to Snapshots on un-json."""

  # pylint: disable=abstract-method

  def __init__(self, *args, **kwargs):
    super(RelationshipResource, self).__init__(*args, **kwargs)
    self._no_revision = False

  @staticmethod
  def _validate_readonly_relationship(obj_with_readonly_access, obj2):
    # type: (WithReadOnlyAccess, Any) -> None
    """Validate if relationship change allowed to obj2

    Args:
      obj_with_readonly_access: object of type WithReadOnlyAccess
      obj2: another object which also can have type WithReadOnlyAccess
    """

    if not obj_with_readonly_access.can_change_relationship_with(obj2):
      raise MethodNotAllowed(
          description="The object is in a read-only mode and is "
                      "dedicated for SOX needs")

  @staticmethod
  def _validate_readonly_access(obj, src):
    """Ensure that relationship is allowed for read-only objects"""

    if not isinstance(obj, relationship.Relationship):
      # skip Snapshot objects
      return

    obj1 = referenced_objects.get(obj.source_type, obj.source_id)
    obj2 = referenced_objects.get(obj.destination_type, obj.destination_id)

    if isinstance(obj1, WithReadOnlyAccess):
      RelationshipResource._validate_readonly_relationship(obj1, obj2)

    if isinstance(obj2, WithReadOnlyAccess):
      RelationshipResource._validate_readonly_relationship(obj2, obj1)

    check_mapping_permissions(obj1, obj2)

  @staticmethod
  def _parse_snapshot_data(src):
    """Try to find parent-child pair from src.

    Args:
      src: source JSON from which a Relationship would have been created.

    Returns:
      (parent, child, is_snapshot):
          (source, destination, True) if source is a Parent and destination is
          a Snapshottable;
          (destination, source, True) if source is a Snapshottable and
          destination is a Parent;
          (None, None, False) otherwise.
    """
    from ggrc.snapshotter import rules as snapshot_rules
    parent, child = None, None
    if src["source"]["type"] in snapshot_rules.Types.parents:
      parent, child = src["source"], src["destination"]
    elif src["destination"]["type"] in snapshot_rules.Types.parents:
      parent, child = src["destination"], src["source"]

    is_snapshot = bool(parent) and child["type"] in snapshot_rules.Types.all
    return parent, child, is_snapshot

  def _get_model_instance(self, src=None):
    """For Parent and Snapshottable src and dst, create an empty Snapshot.
    Args:
      src: dict containing new object source.

    Returns:
      obj: An instance of current model.
    """
    self.needs_update = True
    _, _, is_snapshot = self._parse_snapshot_data(src)

    if is_snapshot:
      snapshot = Snapshot()
      db.session.add(snapshot)

      return snapshot

    _relationship = self._get_relationship(src)

    if _relationship:
      self.is_new = False
      self.needs_update = _relationship.is_external
    else:
      _relationship = relationship.Relationship()
      db.session.add(_relationship)
    return _relationship

  def json_create(self, obj, src):
    """For Parent and Snapshottable src and dst, fill in the Snapshot obj."""
    parent, child, is_snapshot = self._parse_snapshot_data(src)

    if is_snapshot:
      snapshot_data = {
          "parent": parent,
          "child_type": child["type"],
          "child_id": child["id"],
          "update_revision": "new",
      }
      json_builder.create(obj, snapshot_data)
      obj.modified_by = get_current_user()
      obj.context = obj.parent.context
      relationship_obj = relationship.Relationship()
      relationship_obj.source = obj.parent
      relationship_obj.destination = obj
      db.session.add(relationship_obj)
      return None

    return super(RelationshipResource, self).json_create(obj, src)

  def put(self, id):  # pylint: disable=redefined-builtin
    """Disable ability to make PUT operation handler."""
    raise MethodNotAllowed()

  def _check_post_create_options(self, body):
    """Check post relationship params"""
    for obj in body:
      relationship_validators.validate_relation_by_type(
          obj["relationship"]["source"]["type"],
          obj["relationship"]["destination"]["type"],
      )

  def _check_post_permissions(self, objects):
    for obj in objects:
      if obj.type == "Snapshot" and\
         not permissions.is_allowed_update(obj.child_type,
                                           obj.child_id,
                                           obj.context_id):
        db.session.expunge_all()
        raise Forbidden()
    super(RelationshipResource, self)._check_post_permissions(objects)
