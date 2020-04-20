# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""A module with Access Control Role object creation hooks.

The hooks in this file ensure that all objects get their proper access control
list entries for the new access control role.

Since we have started creating ACL entries eagerly on object creation, we
always assume that every object will have all it's ACL entries created. But
when we create a new role for a given object type, those ACL entries are
missing and so we create them manually.

Note:
  - This hook creates a big performance degradation on creating a new custom
    role. This is expected and preferable over the lazy creation of ACLs which
    would reduce performance on assigning or removing people from a role.

  - This hook also makes it impossible for us to create a new role and assign
    people to it in the same request! People can only be assigned to a role
    that already existed before the request was sent. Adding a person to a
    new role must now be done in separate requests.
"""
# pylint: disable=cyclic-import

import logging

import sqlalchemy as sa

from ggrc import db
from ggrc import utils
from ggrc.models import all_models
from ggrc.models import inflector
from ggrc.services import signals

logger = logging.getLogger(__name__)


def _get_missing_models_query(role):
  """Get query for objects with a missing ACL entry for the given role.

  Note that the filter flag here is just for optimization. When creating a new
  access control role we can be sure that no object will have the ACL entry for
  that role so we can skip the filter.

  Args:
    role: role object for which we want to check acl entries.
    filter_: A flag to filter the possible objects that might already have the
      given acl entry

  Returns:
    sqlalchemy query for the object type specified in the access control role.
  """
  model = inflector.get_model(role.object_type)
  if not model:
    # We only log info instead of warning here because we still leave access
    # control roles of obsolete objects in our database, so that we can use
    # them with old revisions in our history log.
    logger.info("Trying to handle role '%s' for non existent object '%s'",
                role.name, role.object_type)
    return None

  query = model.query.outerjoin(
      all_models.AccessControlList,
      sa.and_(
          all_models.AccessControlList.object_type == model.__name__,
          all_models.AccessControlList.object_id == model.id,
          all_models.AccessControlList.ac_role_id == role.id
      )
  ).filter(
      all_models.AccessControlList.id.is_(None)
  ).order_by(
      model.id
  )

  return query


def handle_role_acls(role=None, role_id=None):
  """Handle creation of ACL entries for the given role.

  This function takes care of eager acl creation when a new role is created.
  Because this is called after the commit on the role, we can not have new
  role creation and people assignment to that role in the same request.
  """
  if not role:
    role = all_models.AccessControlRole.query.get(role_id)
  with utils.benchmark(u"Generating ACL entries on {} for role {}".format(
          role.object_type, role.name)):
    query = _get_missing_models_query(role)
    if not query:
      return

    while query.count():
      for roleable_obj in query.limit(1000):
        db.session.add(all_models.AccessControlList(
            ac_role=role,
            object=roleable_obj,
        ))
      db.session.commit()


def init_hook():
  """Initialize all hooks"""

  # pylint: disable=unused-variable
  @signals.Restful.model_posted_after_commit.connect_via(
      all_models.AccessControlRole)
  def handle_role_posted(sender, obj=None, src=None, service=None, event=None):
    """Handle ACL entries creation for newly created access control role."""
    # pylint: disable=unused-argument
    # Arguments here have to be listed for the hooks to work.
    from ggrc import views
    views.start_compute_role_acls(role_id=obj.id)
