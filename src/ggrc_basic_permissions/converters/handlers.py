# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Handlers columns dealing with user roles."""


from sqlalchemy import and_

from ggrc import db
from ggrc.converters import errors
from ggrc.converters.handlers.handlers import UserColumnHandler
from ggrc.models import Context
from ggrc_basic_permissions.models import Role
from ggrc_basic_permissions.models import UserRole


class UserRoleColumnHandler(UserColumnHandler):
  """User role column handler."""

  _role_map = {
      "admin": "administrator",
      "ggrc admin": "administrator",
  }

  _allowed_roles = [
      "Administrator",
      "Creator",
      "Editor",
      "Reader",
      "No Access",
      ""
  ]

  def parse_item(self):
    value = self.raw_value.lower()
    if value.title() not in self._allowed_roles:
      self.add_error(errors.WRONG_VALUE, column_name=self.display_name)
    name = self._role_map.get(value, value)
    return Role.query.filter_by(name=name).first()

  def set_obj_attr(self):
    pass

  def get_value(self):
    return self.row_converter.obj.system_wide_role

  def remove_current_roles(self):
    """Delete all roles for the current object."""
    allowed_role_ids = db.session.query(Role.id).filter(
        Role.name.in_(self._allowed_roles))
    UserRole.query.filter(and_(
        UserRole.role_id.in_(allowed_role_ids),
        UserRole.person_id == self.row_converter.obj.id)
    ).delete(synchronize_session="fetch")

  def insert_object(self):
    if self.dry_run:
      return
    if not self.value:
      role_value = self.row_converter.objects['user_role'].raw_value
      if role_value.lower() == 'no access':
        self.remove_current_roles()
      return

    self.remove_current_roles()
    context = None
    if self.value.name == "Administrator":
      context = Context.query.filter_by(name="System Administration").first()
    user_role = UserRole(
        role=self.value,
        person=self.row_converter.obj,
        context=context,
    )
    db.session.add(user_role)
    self.dry_run = True
