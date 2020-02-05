# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Person integration functionality via cron job."""

import logging
import datetime

from ggrc.integrations import client
from ggrc.models import all_models
from ggrc.utils import user_generator
from ggrc.utils import log_event
from ggrc import rbac
from ggrc import db


logger = logging.getLogger(__name__)


def sync_people():
  """Synchronizes person object name attribute from integration service."""
  logger.info(
      "Person synchronization start: %s",
      datetime.datetime.utcnow()
  )
  users = all_models.Person.query.all()
  users_dict = {
      user.user_name: (user.name, user) for user in users
      if user_generator.is_authorized_domain(user.email)
  }
  logger.info("Syncing state of %d people.", len(users))
  service = client.PersonClient()
  entries = service.search_persons(users_dict.keys())
  processed_ids = []
  disabled_ids = []
  user_id = user_generator.get_migrator_id()
  for entry in entries:
    full_name = "%s %s" % (entry['firstName'], entry['lastName'])
    user = users_dict[entry["username"]][1]
    if not entry["isActive"] and user.user_roles and \
       user.system_wide_role != rbac.SystemWideRoles.NO_ACCESS:
      for user_role in user.user_roles:
        db.session.delete(user_role)
        log_event.log_event(db.session, user_role, current_user_id=user_id)
      disabled_ids.append(user.id)
    elif users_dict[entry["username"]][0] != full_name:
      user.name = full_name
      processed_ids.append(user.id)
      db.session.add(user)
  logger.info(
      "Sync is done, %d person(people) were processed. "
      "%d person(people) are not active now and were set with No Role",
      len(processed_ids), len(disabled_ids)
  )
  if processed_ids or disabled_ids:
    db.session.commit()
