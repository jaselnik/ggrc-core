# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Access Control Role model"""

import collections

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.orm import load_only
from sqlalchemy.orm.session import Session

import flask
from werkzeug.exceptions import Forbidden

from ggrc import db
from ggrc.models import mixins
from ggrc.models import reflection
from ggrc.models.mixins import attributevalidator
from ggrc.models.mixins import base
from ggrc.utils.validators import ggrcq


class AccessControlRole(attributevalidator.AttributeValidator,
                        base.ContextRBAC, mixins.Base, db.Model):
  """Access Control Role

  Model holds all roles in the application. These roles can be added
  by the users.
  """
  __tablename__ = 'access_control_roles'

  name = db.Column(db.String, nullable=False)
  object_type = db.Column(db.String)
  tooltip = db.Column(db.String)

  read = db.Column(db.Boolean, nullable=False, default=True)
  update = db.Column(db.Boolean, nullable=False, default=True)
  delete = db.Column(db.Boolean, nullable=False, default=True)
  my_work = db.Column(db.Boolean, nullable=False, default=True)
  mandatory = db.Column(db.Boolean, nullable=False, default=False)
  non_editable = db.Column(db.Boolean, nullable=False, default=False)
  internal = db.Column(db.Boolean, nullable=False, default=False)
  default_to_current_user = db.Column(
      db.Boolean, nullable=False, default=False)
  notify_about_proposal = db.Column(db.Boolean, nullable=False, default=False)
  notify_about_review_status = db.Column(db.Boolean,
                                         nullable=False, default=False)

  access_control_list = db.relationship(
      'AccessControlList', backref='ac_role', cascade='all, delete-orphan')

  parent_id = db.Column(
      db.Integer,
      db.ForeignKey('access_control_roles.id', ondelete='CASCADE'),
      nullable=True,
  )
  parent = db.relationship(
      # pylint: disable=undefined-variable
      lambda: AccessControlRole,
      remote_side=lambda: AccessControlRole.id
  )

  _reserved_names = {}

  @staticmethod
  def _extra_table_args(_):
    return (
        db.UniqueConstraint('name', 'object_type'),
    )

  @classmethod
  def eager_query(cls, **kwargs):
    """Define fields to be loaded eagerly to lower the count of DB queries."""
    return super(AccessControlRole, cls).eager_query(**kwargs)

  _api_attrs = reflection.ApiAttributes(
      "name",
      "object_type",
      "tooltip",
      "read",
      "update",
      "delete",
      "my_work",
      "mandatory",
      "default_to_current_user",
      reflection.Attribute("non_editable", create=False, update=False),
  )

  @sa.orm.validates("name", "object_type")
  def validates_name(self, key, value):  # pylint: disable=no-self-use
    """Validate Custom Role name uniquness.

    Custom Role names need to follow 3 uniqueness rules:
      1) Names must not match any attribute name on any existing object.
      2) Object level CAD names must not match any global CAD name.
      3) Names should not contains special values (.validate_name_correct)

    This validator should check for name collisions for 1st and 2nd rule.

    This validator works, because object_type is never changed. It only
    gets set when the role is created and after that only name filed can
    change. This makes validation using both fields possible.

    Args:
      value: access control role name

    Returns:
      value if the name passes all uniqueness checks.
    """
    value = value.strip()

    if key == "name":
      ggrcq.validate_name_correctness(value)

    if key == "name" and self.object_type:
      name = value.lower()
      object_type = self.object_type
    elif key == "object_type" and self.name:
      name = self.name.strip().lower()
      object_type = value
    else:
      return value

    if name in self._get_reserved_names(object_type):
      raise ValueError(u"Attribute name '{}' is reserved for this object type."
                       .format(name))

    if self._get_global_cad_names(object_type).get(name) is not None:
      raise ValueError(u"Global custom attribute '{}' "
                       u"already exists for this object type"
                       .format(name))

    return value


def invalidate_acr_caches(mapper, content, target):
  # pylint: disable=unused-argument
  """Clear `global_role_names` if ACR created or update or deleted."""
  if hasattr(flask.g, "global_role_names"):
    del flask.g.global_role_names
  if hasattr(flask.g, "global_ac_roles"):
    del flask.g.global_ac_roles


def acr_modified(obj, session):
  """Check if ACR object was changed or deleted"""
  changed = False
  for attr in inspect(obj).attrs:
    # ACL changes should not be checked
    if attr.key == "access_control_list":
      continue
    changed = changed or attr.history.has_changes()
  return changed or obj in session.deleted


def invalidate_noneditable_change(session, flush_context, instances):
  """Handle snapshot objects on api post requests."""
  # pylint: disable=unused-argument
  acrs = [o for o in session if isinstance(o, AccessControlRole)]
  if not acrs:
    return
  for acr in acrs:
    # Reject modifying or deleting of existing roles, creating allowed
    if acr.id and acr_modified(acr, session) and acr.non_editable:
      raise Forbidden()


sa.event.listen(
    AccessControlRole,
    "before_insert",
    ggrcq.validate_object_type_ggrcq
)
sa.event.listen(
    AccessControlRole,
    "before_update",
    ggrcq.modified_only(ggrcq.validate_object_type_ggrcq)
)
sa.event.listen(
    AccessControlRole,
    "before_delete",
    ggrcq.validate_object_type_ggrcq
)
sa.event.listen(
    AccessControlRole,
    "after_insert",
    invalidate_acr_caches
)
sa.event.listen(
    AccessControlRole,
    "after_delete",
    invalidate_acr_caches
)
sa.event.listen(
    AccessControlRole,
    "after_update",
    invalidate_acr_caches
)
sa.event.listen(
    Session,
    "before_flush",
    invalidate_noneditable_change
)


def get_custom_roles_for(object_type):
  """Get all access control role names for the given object type

  return the dict off ACR ids and names related to sent object_type,
  Ids are keys of this dict and names are values.
  """
  if getattr(flask.g, "global_role_names", None) is None:
    flask.g.global_role_names = collections.defaultdict(dict)
    query = db.session.query(
        AccessControlRole.object_type,
        AccessControlRole.id,
        AccessControlRole.name,
    ).filter(
        AccessControlRole.object_type.isnot(None),  # noqa
    )
    for type_, id_, name_ in query:
      flask.g.global_role_names[type_][id_] = name_
  return flask.g.global_role_names[object_type]


def _merge_roles_if_needed(object_type):
  """Merge `object_type` objects from global_ac_roles in session if needed."""
  for role_name, role in flask.g.global_ac_roles[object_type].iteritems():
    if role not in db.session:
      flask.g.global_ac_roles[object_type][role_name] = db.session.merge(role)


def get_ac_roles_for(object_type):
  """Get all ACRs for the given object type.

  Args:
      object_type: Object type for which ACR records should be returned.
  Returns:
      Dict like {"Access Control Role Name": ACR Instance, ...}
  """
  if not hasattr(flask.g, "global_ac_roles"):
    flask.g.global_ac_roles = collections.defaultdict(dict)

  if not flask.g.global_ac_roles[object_type]:
    query = AccessControlRole.query.filter(
        AccessControlRole.object_type == object_type,
        AccessControlRole.internal == sa.sql.expression.false(),
    ).options(
        load_only("id", "name", "object_type", "mandatory")
    )
    for role in query:
      flask.g.global_ac_roles[role.object_type][role.name] = role

  _merge_roles_if_needed(object_type)
  return flask.g.global_ac_roles[object_type]


def get_ac_roles_data_for(object_type):
  """Get all ACRs data for the given object type.

  Data stored as tuple to avoid DetachedInstanceError
  Args:
      object_type: Object type for which ACR records should be returned.
  Returns:
      Dict like {"Access Control Role Name": ACR data, ...}
  """
  if getattr(flask.g, "global_ac_roles_data", None) is None:
    flask.g.global_ac_roles_data = collections.defaultdict(dict)
    query = AccessControlRole.query.filter(
        AccessControlRole.internal == sa.sql.expression.false(),
    ).options(
        load_only("id", "name", "object_type", "mandatory")
    )
    for role in query:
      role_data = (role.id, role.name, role.object_type, role.mandatory)
      flask.g.global_ac_roles_data[role.object_type][role.name] = role_data
  return flask.g.global_ac_roles_data[object_type]
