# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>


"""
 GGRC email notification module hook to prepares email, email digest, notify
 email to recipients
"""


from collections import defaultdict
from datetime import date
from datetime import datetime
from logging import getLogger
from operator import itemgetter
from dateutil import relativedelta

import flask

from sqlalchemy.orm import joinedload
from sqlalchemy.sql.expression import true
from sqlalchemy import inspect
from werkzeug.exceptions import Forbidden
from google.appengine.api import mail

from ggrc import db, extensions, settings, utils
from ggrc import models
from ggrc.app import app
from ggrc.gcalendar import calendar_event_builder
from ggrc.gcalendar import calendar_event_sync
from ggrc.models import Person
from ggrc.models import Notification, NotificationHistory
from ggrc.models import background_task
from ggrc.notifications.unsubscribe import unsubscribe_url
from ggrc.rbac import permissions
from ggrc.utils import DATE_FORMAT_US, merge_dict, benchmark
from ggrc.utils import generate_query_chunks
from ggrc.notifications.notification_handlers import SEND_TIME

from ggrc_workflows.models import CycleTaskGroupObjectTask
from ggrc_workflows.notification.notification_handler \
    import done_tasks_notify, not_done_tasks_notify

from ggrc_workflows.notification.data_handler import (
    cycle_tasks_cache, deleted_task_rels_cache, get_cycle_task_data
)


# pylint: disable=invalid-name
logger = getLogger(__name__)


class Services(object):
  """Helper class for notification services.

  This class is a helper class for calling a notification service for a given
  object. The first call get_service_function must be done after all modules
  have been initialized.
  """

  services = []

  @classmethod
  def get_service_function(cls, name):
    """Get callback function for an object.

    This returns a service function which is a registered callback for an
    object that has a notification.

    Args:
      name: Name of an object for which we want to get a service function, such
        as "CycleTask", "Assessment", etc.

    Returns:
      callable: A function that takes a notification and returns a data dict
        with all the data for that notification.
    """
    if not cls.services:
      cls.services = extensions.get_module_contributions(
          "contributed_notifications")
    if name not in cls.services:
      raise ValueError("unknown service name: %s" % name)
    return cls.services[name]

  @classmethod
  def call_service(cls, notif, **kwargs):
    """Call data handler service for the object in the notification.

    Args:
      notif (Notification): Notification object for which we want to get the
        notification data dict.

    Returns:
      dict: Result of the data handler for the object in the notification.
    """
    service = cls.get_service_function(notif.object_type)

    if service is get_cycle_task_data:
      return service(
          notif,
          tasks_cache=kwargs.get("tasks_cache"),
          del_rels_cache=kwargs.get('del_rels_cache')
      )

    return service(notif)


def get_filter_data(
    notification, people_cache, tasks_cache=None, del_rels_cache=None
):
  """Get filtered notification data.

  This function gets notification data for all users who should receive it. A
  single notification can be for multiple users (such as all assignees) but
  only some should receive it depending on if it's an instant notification or
  a daily digest and the specific users notification settings.

  Args:
    notification (Notification): Notification object for which we want to get
      data.
    tasks_cache (dict): prefetched CycleTaskGroupObjectTask instances
      accessible by their ID as a key
    del_rels_cache (dict): prefetched Revision instances representing the
      relationships to Tasks that were deleted grouped by task ID as a key

  Returns:
    dict: dictionary containing notification data for all users who should
      receive it, according to their notification settings.
  """
  result = {}
  data = Services.call_service(
      notification, tasks_cache=tasks_cache, del_rels_cache=del_rels_cache)

  for user, user_data in data.iteritems():
    if should_receive(notification, user_data, people_cache):
      result[user] = user_data
  return result


def get_notification_data(notifications):
  """Get notification data for all notifications.

  This function returns a filtered data for all notifications for the users
  that should receive it.

  Args:
    notifications (list of Notification): List of notification for which we
      want to get notification data.

  Returns:
    dict: Filtered dictionary containing all the data that should be sent for
      the given notification list.
  """
  if not notifications:
    return {}
  aggregate_data = {}
  people_cache = {}

  tasks_cache = cycle_tasks_cache(notifications)
  deleted_rels_cache = deleted_task_rels_cache(tasks_cache.keys())

  for notification in notifications:
    filtered_data = get_filter_data(
        notification, people_cache, tasks_cache=tasks_cache,
        del_rels_cache=deleted_rels_cache)
    aggregate_data = merge_dict(aggregate_data, filtered_data)

  # Remove notifications for objects without a contact (such as task groups)
  aggregate_data.pop("", None)

  return aggregate_data


def sort_comments(notif_data):
  """Inline sort comment notifications by comment creation times.

  Comment notifications dictionaries are converted to sorted lists in the
  process.

  Args:
    notif_data: Dictionary containing aggregated notification data for a single
      day.
  Returns:
    None
  """
  comment_notifs = notif_data.get("comment_created", {})

  for parent_obj_info, comments in comment_notifs.iteritems():
    comments_as_list = sorted(
        comments.itervalues(), key=itemgetter("created_at"), reverse=True)
    # modifying a value for a given existing key is fine...
    comment_notifs[parent_obj_info] = comments_as_list


def get_pending_notifications():
  """Get notification data for all future notifications.

  The data dict that get's returned here contains notification data grouped by
  dates on which the notifications should be received.

  Returns
    list of Notifications, data: a tuple of notifications that were handled
      and corresponding data for those notifications.
  """
  notifications = db.session.query(Notification).filter(
      (Notification.sent_at.is_(None)) | (Notification.repeating == true())
  ).all()

  notif_by_day = defaultdict(list)
  for notification in notifications:
    notif_by_day[notification.send_on.date()].append(notification)

  data = defaultdict(dict)
  today = date.today()
  for day, notif in notif_by_day.iteritems():
    current_day = max(day, today)
    data[current_day] = merge_dict(data[current_day],
                                   get_notification_data(notif))

  return notifications, data


def generate_daily_notifications():
  """Generate daily notifications data in chunks."""
  notifications = db.session.query(Notification).options(
      joinedload("notification_type")
  ).filter(
      (Notification.runner == Notification.RUNNER_DAILY) &
      (Notification.send_on <= datetime.today()) &
      ((Notification.sent_at.is_(None)) | (Notification.repeating == true()))
  ).order_by(Notification.repeating, Notification.id)
  all_count = notifications.count()
  handled = 0
  chunk_size = settings.DAILY_DIGEST_BATCH_SIZE
  for data_chunk in generate_query_chunks(
      notifications, chunk_size=chunk_size, needs_ordering=False
  ):
    handled += data_chunk.count()
    logger.info("Processing notifications: %s/%s", handled, all_count)
    yield data_chunk, get_notification_data(data_chunk)


def get_daily_notifications():
  """Get notification data for all future notifications.

  Returns
    list of Notifications, data: a tuple of notifications that were handled
      and corresponding data for those notifications.
  """

  notifications = []
  notifications_data = {}
  for notif_list, notif_data in generate_daily_notifications():
    notifications.extend(notif_list.all())
    notifications_data.update(notif_data)

  return notifications, notifications_data


def should_receive(notif, user_data, people_cache):
  """Check if a user should receive a notification or not.

  Args:
    notif (Notification): A notification entry that we are checking.
    user_data (dict): A dictionary containing data about user notifications.

  Returns:
    True if user should receive the given notification, or False otherwise.
  """
  force_notif = user_data.get("force_notifications", {}).get(notif.id, False)
  person_id = user_data["user"]["id"]
  # The person does not exist
  if person_id == -1:
    return False
  if person_id in people_cache:
    person = people_cache[person_id]
  else:
    person = db.session.query(Person).options(
        joinedload('user_roles').joinedload('role'),
        joinedload('notification_configs')
    ).filter(Person.id == person_id).first()
    people_cache[person_id] = person

  # If the user has no access we should not send any emails
  if person.system_wide_role == "No Access":
    return False

  def is_enabled(notif_type, person):
    """Check user notification settings.

    Args:
      notif_type (string): can be "Email_Digest" or "Email_Now" based on what
        we wish to check.

    Returns:
      Boolean based on what settings users has stored or what the default
      setting is for the given notification.
    """

    notification_configs = [nc for nc in person.notification_configs
                            if nc.notif_type == notif_type]
    if not notification_configs:
      # If we have no results, we need to use the default value, which is
      # true for digest emails.
      return notif_type == "Email_Digest"
    return notification_configs[0].enable_flag

  has_digest = force_notif or is_enabled("Email_Digest", person)

  return has_digest


def create_daily_digest_bg():
  """Create daily digest background task."""
  models.background_task.create_task(
      name="send_daily_digest_bg",
      url=flask.url_for("send_daily_digest_bg"),
      queued_callback=send_daily_digest_bg,
  )
  db.session.commit()
  return utils.make_simple_response()


@app.route("/_background_tasks/send_daily_digest_bg",
           methods=["POST"])
@background_task.queued_task
def send_daily_digest_bg(task):  # pylint: disable=unused-argument
  """Send emails for today's or overdue notifications."""
  error_msg = None
  try:
    send_daily_digest_notifications()
  except Exception as exp:  # pylint: disable=broad-except
    error_msg = ("Sending of daily digest has failed "
                 "with the following error {}".format(exp.message))
    logger.exception(error_msg)
  return utils.make_simple_response(error_msg)


def send_daily_digest_notifications():
  """Send emails for today's or overdue notifications."""
  with benchmark("contributed cron job send_daily_digest_notifications"):
    for notif_list, notif_data in generate_daily_notifications():
      with benchmark("processing notification data chunk"):
        subject = "GGRC daily digest for {}".format(
            date.today().strftime("%b %d")
        )
        sent_emails = []
        with benchmark("sending daily emails"):
          for user_email, data in notif_data.iteritems():
            data = modify_data(data)
            email_body = settings.EMAIL_DIGEST.render(digest=data)
            send_email(user_email, subject, email_body)
            sent_emails.append(user_email)

        with benchmark("processing sent notifications"):
          process_sent_notifications(notif_list)
        logger.info("emails sent to: %s", ",".join(sent_emails))


def generate_cycle_tasks_notifs():
  """Generate notifications for cycle
  task group object tasks on status change.

  Args:
    day (date): send notification date.
  """
  with benchmark("generate notifications for cycle tasks"):
    day = date.today() - relativedelta.relativedelta(days=1)
    send_datetime = datetime.combine(day, SEND_TIME)

    updated_tasks = CycleTaskGroupObjectTask.query.filter(
        CycleTaskGroupObjectTask.updated_at >= send_datetime
    ).all()

    done_tasks = []
    not_done_tasks = []
    for obj in updated_tasks:
      if obj.is_done:
        done_tasks.append(obj)
      else:
        not_done_tasks.append(obj)
    done_tasks_notify(done_tasks, day)
    not_done_tasks_notify(not_done_tasks, day)
    db.session.commit()


def process_sent_notifications(notif_list):
  """Process sent notifications.

  Set sent time to now for all notifications in the list
  and move all non-repeatable notifications to history table.

  Args:
    notif_list (list of Notification): List of notification for which we want
      to modify sent_at field.
  """
  from ggrc.models import all_models

  for notif in notif_list:
    if (notif.object and notif.object_type == "CycleTaskGroupObjectTask" and
       notif.object.status == all_models.CycleTaskGroupObjectTask.DEPRECATED):
      continue
    if notif.repeating:
      notif.sent_at = datetime.utcnow()
    else:
      notif_history = create_notification_history_obj(notif)
      db.session.add(notif_history)
      db.session.delete(notif)
  db.session.commit()


def create_notification_history_obj(notif):
  """Create notification history object.

  Args:
    notif: Notification object.
  """
  notif_history_context = {c.key: getattr(notif, c.key)
                           for c in inspect(notif).mapper.column_attrs
                           if c.key != "id"}
  notif_history_context["notification_id"] = notif.id
  notif_history_context["sent_at"] = datetime.utcnow()
  return NotificationHistory(**notif_history_context)


def show_pending_notifications():
  """Get notification html for all future notifications.

  The data shown here is grouped by dates on which notifications should be
  sent.

  Note that the dates for all future notifications will be wrong since they are
  based on the current date which will be different when the notification is
  actually sent.

  Returns:
    str: Html containing all future notifications.
  """
  if not permissions.is_admin():
    raise Forbidden()
  _, notif_data = get_pending_notifications()

  for day_notif in notif_data.itervalues():
    for data in day_notif.itervalues():
      data = modify_data(data)
  return settings.EMAIL_PENDING.render(data=sorted(notif_data.iteritems()))


def show_daily_digest_notifications():
  """Get notification html for today's notifications.

  Returns:
    str: Html containing all today's notifications.
  """
  # pylint: disable=invalid-name
  if not permissions.is_admin():
    raise Forbidden()

  _, notif_data = get_daily_notifications()
  for data in notif_data.itervalues():
    data = modify_data(data)
  return settings.EMAIL_DAILY.render(data=notif_data)


def send_calendar_events():
  """Sends calendar events."""
  error_msg = None
  try:
    with benchmark("Send calendar events"):
      builder = calendar_event_builder.CalendarEventBuilder()
      builder.build_cycle_tasks()
      sync = calendar_event_sync.CalendarEventsSync()
      sync.sync_cycle_tasks_events()
  except Exception as exp:  # pylint: disable=broad-except
    logger.error(exp.message)
    error_msg = exp.message
  return utils.make_simple_response(error_msg)


def get_app_engine_email():
  """Get notification sender email.

  Return the email of the user that will be set as sender. This email should be
  authorized to send emails from the server. For more details, see Application
  Settings for email api authorized senders.

  Returns:
    Valid email address if it's set in the app settings.
  """
  email = getattr(settings, 'APPENGINE_EMAIL')
  return email if mail.is_email_valid(email) else None


def prefix_subject(subject):
  """Add non prod env subject prefix.

  This function ads app engine instance prefix to email subject on all non
  production instances.
  """
  if not settings.NOTIFICATION_PREFIX:
    return subject

  return "[{prefix}] {subject}".format(
      prefix=settings.NOTIFICATION_PREFIX,
      subject=subject,
  )


def send_email(user_email, subject, body):
  """Helper function for sending emails.

  Args:
    user_email (string): Email of the recipient.
    subject (string): Email subject.
    body (basestring): Html body of the email. it can contain unicode
      characters and will be sent as a html mime type.
  """
  sender = get_app_engine_email()
  if not mail.is_email_valid(user_email):
    logger.error("Invalid email recipient: %s", user_email)
    return
  if not sender:
    logger.error("APPENGINE_EMAIL setting is invalid.")
    return
  check_email_body = False
  if 'Ticket generation' in subject and 'completed successfully' in subject:
    check_email_body = True
  subject = prefix_subject(subject)
  message = mail.EmailMessage(sender=sender, subject=subject)

  message.to = user_email
  message.html = body

  if check_email_body and body.count('</div>') != 3:
    logger.info("mail.EmailMessage. DIV's count %s", body.count('</div>'))
    logger.error("Invalid Email body %s", body)

  message.send()


def modify_data(data):
  """Modify notification data dictionary.

  For easier use in templates, it computes/aggregates some additional
  notification data.
  together.

  Args:
    data (dict): notification data.

  Returns:
    dict: the received dict with some additional fields for easier traversal
      in the notification template.
  """
  # combine "my_tasks" from multiple cycles
  data["cycle_started_tasks"] = {}
  if "cycle_data" in data:
    for cycle in data["cycle_data"].values():
      if "my_tasks" in cycle:
        data["cycle_started_tasks"].update(cycle["my_tasks"])

  data["unsubscribe_url"] = unsubscribe_url(data["user"]["id"])

  # Move comment notifications for same object into list and sort by
  # created_at field
  sort_comments(data)
  data["DATE_FORMAT"] = DATE_FORMAT_US

  return data


@app.route("/_background_tasks/send_mentions_bg", methods=["POST"])
@background_task.queued_task
def send_mentions_bg(task):
  """Run sending email mentions for specified comments list in bg."""
  from ggrc.notifications import people_mentions

  error_msg = None
  try:
    with utils.benchmark("Send people mentions"):
      people_mentions.send_mentions(
          comments_data=task.parameters.get("comments_data"),
          object_name=task.parameters.get("object_name"),
          href=task.parameters.get("href"),
      )
  except Exception as exp:  # pylint: disable=broad-except
    error_msg = ("Sending of people mentions has failed "
                 "with the following error {}".format(exp.message))
    logger.exception(error_msg)
  return utils.make_simple_response(error_msg)
