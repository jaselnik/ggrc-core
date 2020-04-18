# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Superusers synchronization functionality via cron job."""

import logging

from ggrc import settings
from ggrc import db
from ggrc.models import all_models
from ggrc.utils import user_generator
from ggrc.utils import log_event
from ggrc import login


logger = logging.getLogger(__name__)


def sync_superusers():
  """Delete roles stored in database for superusers

  Superuser role allows users full permissions, and it overrides the
  role stored in the database.
  Admin page filters the users by their roles in the database and displays
  it on the UI, but if user has Superuser role than it will be used
  """
  users = all_models.Person.query.filter(
      all_models.Person.email.in_(settings.BOOTSTRAP_ADMIN_USERS)
  ).all()
  logger.info("Syncing state of %d superusers.", len(users))
  processed_ids_count = 0
  user_id = login.get_current_user_id() or user_generator.get_migrator_id()
  for user in all_models.Person.query.filter(
      all_models.Person.email.in_(settings.BOOTSTRAP_ADMIN_USERS)
  ):
    for user_role in user.user_roles:
      db.session.delete(user_role)
      log_event.log_event(db.session, user_role, current_user_id=user_id)
      processed_ids_count += 1
  logger.info(
      "Sync is done, %d superusers(s) were processed.",
      processed_ids_count,
  )
  if processed_ids_count:
    db.session.commit()
