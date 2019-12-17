# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Person integration functionality via cron job."""

import logging
import datetime

from ggrc.integrations import client
from ggrc.models import all_models
from ggrc.utils import user_generator
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
      user.email.split("@")[0]: (user.name, user) for user in users
      if user_generator.is_authorized_domain(user.email)
  }
  logger.info("Syncing state of %d people.", len(users))
  service = client.PersonClient()
  entries = service.search_persons(users_dict.keys())
  processed_ids = []
  for entry in entries:
    first_name = "%s %s" % (entry['firstName'], entry['lastName'])
    if users_dict[entry["username"]][0] != first_name:
      user = users_dict[entry["username"]][1]
      user.name = first_name
      processed_ids.append(user.id)
      db.session.add(user)
  logger.info(
      "Sync is done, %d person(people) were processed.",
      len(processed_ids)
  )
  if processed_ids:
    db.session.commit()
