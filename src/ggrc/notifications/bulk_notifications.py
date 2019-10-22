# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""This module handles bulk assessment update notifications"""
from ggrc import db
from ggrc import login
from ggrc import settings

from ggrc.models import all_models
from ggrc.notifications import common
from ggrc.notifications.data_handlers import get_object_url


BULK_UPDATE_TITLE = "Bulk update of Assessments is finished"


def _create_notif_data(assessments):
  """Create data in format applicable for template rendering"""
  result = [
      {"title": assessment.title,
       "url": get_object_url(assessment)} for assessment in assessments
  ]
  return result


def send_notification(update_errors, complete_errors, asmnt_ids):
  """Send bulk complete job finished."""

  not_updated_asmnts = []
  if update_errors:
    not_updated_asmnts = db.session.query(all_models.Assessment).filter(
        all_models.Assessment.slug.in_(update_errors)
    ).all()

  not_completed_asmnts = []
  if complete_errors:
    not_completed_asmnts = db.session.query(all_models.Assessment).filter(
        all_models.Assessment.slug.in_(complete_errors)
    ).all()

  not_updated_ids = set(asmnt.id for asmnt in not_updated_asmnts)
  not_completed_ids = set(asmnt.id for asmnt in not_completed_asmnts)
  success_ids = set(asmnt_ids) - not_updated_ids - not_completed_ids

  success_asmnts = []
  if success_ids:
    success_asmnts = db.session.query(all_models.Assessment).filter(
        all_models.Assessment.id.in_(success_ids)
    ).all()

  bulk_data = {
      "update_errors": _create_notif_data(not_updated_asmnts),
      "complete_errors": _create_notif_data(not_completed_asmnts),
      "succeeded": _create_notif_data(success_asmnts),
  }
  body = settings.EMAIL_BULK_COMPLETE.render(sync_data=bulk_data)
  common.send_email(login.get_current_user().email, BULK_UPDATE_TITLE, body)
