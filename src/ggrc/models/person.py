# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module with Person model definition."""

import re

from sqlalchemy.orm import validates

from ggrc import builder
from ggrc import db
from ggrc import rbac
from ggrc import settings
from ggrc.fulltext import attributes
from ggrc.fulltext import mixin as ft_mixin
from ggrc.models import context
from ggrc.models import exceptions
from ggrc.models import reflection
from ggrc.models import relationship
from ggrc.models.mixins import base
from ggrc.models.mixins import customattributable
from ggrc.models.person_profile import PersonProfile
from ggrc.models.utils import validate_option


class Person(customattributable.CustomAttributable,
             customattributable.CustomAttributeMapable,
             context.HasOwnContext,
             relationship.Relatable,
             base.ContextRBAC,
             base.Base,
             ft_mixin.Indexed,
             db.Model):
  """Person model definition."""

  def __init__(self, *args, **kwargs):
    """Initialize profile relationship while creating Person instance"""
    super(Person, self).__init__(*args, **kwargs)
    self.profile = PersonProfile()

    self.build_object_context(
        context=1,
        name='Personal Context',
        description=''
    )

    self.profile.add_person_with_role_name(self, "Admin")

  __tablename__ = 'people'

  email = db.Column(db.String, nullable=False)
  name = db.Column(db.String, nullable=False)
  language_id = db.Column(db.Integer)
  company = db.Column(db.String)

  object_people = db.relationship(
      'ObjectPerson', backref='person', cascade='all, delete-orphan')
  language = db.relationship(
      'Option',
      primaryjoin='and_(foreign(Person.language_id) == Option.id, '
      'Option.role == "person_language")',
      uselist=False,
  )
  saved_searches = db.relationship(
      "SavedSearch",
      lazy="dynamic",
      cascade="all, delete-orphan",
  )
  profile = db.relationship(
      "PersonProfile",
      foreign_keys='PersonProfile.person_id',
      uselist=False,
      backref="person",
      cascade='all, delete-orphan',
  )
  access_control_people = db.relationship(
      'AccessControlPerson',
      foreign_keys='AccessControlPerson.person_id',
      backref="person",
  )

  @staticmethod
  def _extra_table_args(_):
    return (
        db.Index('ix_people_name_email', 'name', 'email'),
        db.Index('uq_people_email', 'email', unique=True),
    )

  _fulltext_attrs = [
      'company',
      'email',
      'name',
      attributes.FullTextAttr(
          "System Authorizations",
          "system_wide_role"
      ),
  ]
  _api_attrs = reflection.ApiAttributes(
      'company',
      'email',
      'language',
      'name',
      reflection.Attribute('profile', create=False, update=False),
      reflection.Attribute('object_people', create=False, update=False),
      reflection.Attribute('system_wide_role', create=False, update=False),
  )
  _sanitize_html = [
      'company',
      'name',
  ]
  _include_links = []
  ROLE_OPTIONS = ("No Access",
                  "Creator",
                  "Reader",
                  "Editor",
                  "Administrator"
                  )
  _aliases = {
      "name": "Name",
      "email": {
          "display_name": "Email",
          "unique": True,
      },
      "company": "Company",
      "user_role": {
          "display_name": "Role",
          "type": "user_role",
          "filter_by": "_filter_by_user_role",
          "description": "Allowed values are\n{}".format(
              "\n".join(ROLE_OPTIONS))
      },
  }

  @staticmethod
  def specific_column_handlers():
    """Column handlers for person obj"""
    from ggrc_basic_permissions.converters import handlers
    return {
        "user_role": handlers.UserRoleColumnHandler,
    }

  @classmethod
  def _filter_by_user_role(cls, predicate):
    """Custom filter by user roles."""
    from ggrc_basic_permissions.models import Role, UserRole
    return UserRole.query.join(Role).filter(
        (UserRole.person_id == cls.id) &
        (UserRole.context_id.is_(None)) &  # noqa
        predicate(Role.name)
    ).exists()

  # Methods required by Flask-Login
    # pylint: disable=no-self-use
  def is_authenticated(self):
    return self.system_wide_role != 'No Access'

  @property
  def user_name(self):
    return self.email.split("@")[0]

  @property
  def title(self):
    return self.name or self.email

  def is_active(self):
    # pylint: disable=no-self-use
    return True  # self.active

  def is_anonymous(self):
    # pylint: disable=no-self-use
    return False

  def get_id(self):
    return unicode(self.id)  # noqa

  @validates('language')
  def validate_person_options(self, key, option):
    return validate_option(self.__class__.__name__, key, option,
                           'person_language')

  @validates('email')
  def validate_email(self, _, email):
    """Email property validator."""
    if not Person.is_valid_email(email):
      message = "Email address '{}' is invalid. Valid email must be provided"
      raise exceptions.ValidationError(message.format(email))
    return email

  @validates('name')
  def validate_name(self, _, name):
    """Name property validator."""
    if not name:
      raise exceptions.ValidationError("Name is empty")
    return name

  @staticmethod
  def is_valid_email(val):
    """Check for valid email.

    Borrowed from Django. Literal form, ipv4 address (SMTP 4.1.3).
    """
    email_re = re.compile(
        r'^[-!#$%&\'*+\\.\/0-9=?A-Z^_`{|}~]+@([-0-9A-Z]+\.)+([0-9A-Z]){2,4}$',
        re.IGNORECASE)
    return email_re.match(val) if val else False

  @classmethod
  def eager_query(cls, **kwargs):
    from sqlalchemy import orm

    # query = super(Person, cls).eager_query(**kwargs)
    # Completely overriding eager_query to avoid eager loading of the
    # modified_by relationship
    return super(Person, cls).eager_query(**kwargs).options(
        orm.joinedload('language'),
        orm.joinedload('profile'),
        orm.subqueryload('object_people'),
    )

  @classmethod
  def indexed_query(cls):
    from sqlalchemy import orm

    return super(Person, cls).indexed_query().options(
        orm.Load(cls).undefer_group(
            "Person_complete",
        ),
        orm.Load(cls).joinedload('user_roles'),
    )

  def _display_name(self):
    return self.email

  @builder.simple_property
  def system_wide_role(self):
    """For choosing the role string to show to the user; of all the roles in
    the system-wide context, it shows the highest ranked one (if there are
    multiple) or "No Access" if there are none.
    """

    if self.email in getattr(settings, "BOOTSTRAP_ADMIN_USERS", []):
      return rbac.SystemWideRoles.SUPERUSER

    from ggrc.utils.user_generator import is_app_2_app_user_email
    if is_app_2_app_user_email(self.email):
      return rbac.SystemWideRoles.SUPERUSER

    role_hierarchy = {
        rbac.SystemWideRoles.ADMINISTRATOR: 0,
        rbac.SystemWideRoles.EDITOR: 1,
        rbac.SystemWideRoles.READER: 2,
        rbac.SystemWideRoles.CREATOR: 3,
    }
    unique_roles = set([
        user_role.role.name
        for user_role in self.user_roles
        if user_role.role.name in role_hierarchy
    ])
    if not unique_roles:
      return u"No Access"

    # -1 as default to make items not in this list appear on top
    # and thus shown to the user
    sorted_roles = sorted(unique_roles,
                          key=lambda x: role_hierarchy.get(x, -1))
    return sorted_roles[0]
