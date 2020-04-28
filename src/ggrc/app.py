# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Sets up Flask app."""

from datetime import datetime
import re
import time

from logging import getLogger
from logging.config import dictConfig as setup_logging
import sqlalchemy

import flask
from flask import Flask
from flask import render_template
from flask import request
from flask import url_for
from flask_sqlalchemy import get_debug_queries
from flask_sqlalchemy import SQLAlchemy
from tabulate import tabulate

from ggrc import db
from ggrc import extensions
from ggrc import notifications
from ggrc import settings
from ggrc.gdrive import init_gdrive_routes
from ggrc.utils import benchmark, format_api_error_response
from ggrc.utils import issue_tracker_mock


if settings.ISSUE_TRACKER_MOCK and not settings.PRODUCTION:
  if getattr(settings, "APP_ENGINE", False):
    issue_tracker_mock.init_gae_issue_tracker_mock()
  else:
    issue_tracker_mock.init_issue_tracker_mock()

setup_logging(settings.LOGGING)

logger = getLogger(__name__)


app = Flask('ggrc', instance_relative_config=True)  # noqa pylint: disable=invalid-name
app.config.from_object(settings)
if "public_config" not in app.config:
  app.config.public_config = {}

for key in settings.exports:
  app.config.public_config[key] = app.config[key]

# Configure Flask-SQLAlchemy for app
db.app = app
db.init_app(app)

# This should be imported after db.init_app id performed.
# Imported so it can be used with getattr.
from ggrc import contributions  # noqa  # pylint: disable=unused-import,wrong-import-position


@app.before_request
def _ensure_session_teardown():
  """Ensure db.session is correctly removed

  Occasionally requests are terminated without calling the teardown methods,
  namely with DeadlineExceededError on App Engine.
  """
  if db.session.registry.has():
    db.session.remove()


@app.before_request
def setup_user_timezone_offset():
  """Setup user timezon for current request

  It will setup from request header `X-UserTimezoneOffset`
  offset will be sent in minutes.
  """
  from flask import g
  g.user_timezone_offset = request.headers.get("X-UserTimezoneOffset")


def _setup_maintenance_check():
  """Initialize hook to check maintenance mode"""

  @app.before_request
  def check_if_under_maintenance():
    """Check if the site is in maintenance mode."""

    # allow process some routes even under maintenance
    if request.path == '/_ah/start':
      return None

    with benchmark('Check for maintenance'):
      from ggrc.models.maintenance import Maintenance
      try:
        db_row = db.session.query(Maintenance).get(1)
      except sqlalchemy.exc.ProgrammingError as error:
        if re.search(r"\(1146, \"Table '.+' doesn't exist\"\)$",
                     error.message):
          db_row = None
        else:
          raise

      if not db_row or not db_row.under_maintenance:
        return None

    # for API requests return error in JSON format
    if request.path.startswith('/api/'):
      return format_api_error_response(503, "GGRC is under maintenance")

    # in all other cases redirect user to maintenance page
    return render_template("maintenance_mode/maintenance.html"), 503


def setup_error_handlers(app_):
  from ggrc.utils import error_handlers
  error_handlers.register_handlers(app_)


def init_models(app_):
  import ggrc.models
  ggrc.models.init_app(app_)


def configure_flask_login(app_):
  import ggrc.login
  ggrc.login.init_app(app_)


def configure_jinja(app_):
  """Add basic jinja configuration."""
  app_.jinja_env.add_extension('jinja2.ext.autoescape')
  app_.jinja_env.autoescape = True
  app_.jinja_env.add_extension('jinja2.ext.with_')
  app_.jinja_env.add_extension('hamlpy.ext.HamlPyExtension')


def init_services(app_):
  import ggrc.services
  ggrc.services.init_all_services(app_)


def init_views(app_):
  import ggrc.views
  ggrc.views.init_all_views(app_)


def init_extension_blueprints(app_):
  for extension_module in extensions.get_extension_modules():
    if hasattr(extension_module, 'blueprint'):
      app_.register_blueprint(extension_module.blueprint)


def init_permissions_provider():
  from ggrc.rbac import permissions
  permissions.get_permissions_provider()


def init_extra_listeners():
  """Initializes listeners for additional services"""
  from ggrc.automapper import register_automapping_listeners
  from ggrc.snapshotter.listeners import register_snapshot_listeners
  from ggrc.fulltext import listeners
  register_automapping_listeners()
  register_snapshot_listeners()
  listeners.register_fulltext_listeners()


def _enable_debug_toolbar():
  """Enable flask debug toolbar for benchmarking requests."""
  if getattr(settings, "FLASK_DEBUGTOOLBAR", False):
    from flask_debugtoolbar import DebugToolbarExtension
    DebugToolbarExtension(app)


def _set_display_queries(report_type):
  """Set the app request handler for displaying sql queries.

  Args:
    report_type: String specifying if we should display entire queries, just
      slow ones, just counts or none at all.
  """
  # pylint: disable=unused-variable
  @app.after_request
  def display_queries(response):
    """Display database queries

    Prints out SQL queries, EXPLAINs for queries above slow_threshold, and
    a final count of queries after every HTTP request
    """
    if report_type not in ('slow', 'all'):
      return response

    slow_threshold = 0.5  # EXPLAIN queries that ran for more than 0.5s
    queries = get_debug_queries()

    # We have to copy the queries list below otherwise queries executed
    # in the for loop will be appended causing an endless loop
    for i, query in enumerate(list(queries)):
      if report_type == 'slow' and query.duration < slow_threshold:
        continue
      logger.info(
          "Query #%s\n"
          "Duration: %.8f (from %s to %s) in %s\n"
          "Statement:\n%s\n"
          "Parameters:\n%s",
          i + 1,
          query.duration,
          datetime.fromtimestamp(query.start_time),
          datetime.fromtimestamp(query.end_time),
          query.context,
          query.statement,
          query.parameters)
      is_select = bool(re.match('SELECT', query.statement, re.I))
      if query.duration > slow_threshold and is_select:
        try:
          statement = "EXPLAIN " + query.statement
          engine = SQLAlchemy().get_engine(app)
          result = engine.execute(statement, query.parameters)
          logger.info(tabulate(result.fetchall(), headers=result.keys()))
        except:  # pylint: disable=bare-except
          logger.warning("Statement failed: %s", statement, exc_info=True)

    return response


def _display_sql_queries():
  """Set up display database queries

  This function makes sure we display the sql queries if the record setting is
  enabled.
  """
  report_type = getattr(settings, "SQLALCHEMY_RECORD_QUERIES", False)
  valid_types = ('count', 'slow', 'all')
  if report_type:
    if report_type not in valid_types:
      raise Exception("""Invalid SQLALCHEMY_RECORD_QUERIES value specified.
        Possible options: {}""".format(', '.join(valid_types)))

    _set_display_queries(report_type)


def _display_request_time():
  """Request time logger

  Logs request time for every request, highlighting the ones that were slow"""

  # pylint: disable=unused-variable
  @app.before_request
  def before_request():
    """Measure time when before the request starts"""
    flask.g.request_start = (time.time(), time.clock())

  @app.after_request
  def after_request(response):
    """Print out request time"""
    queries = get_debug_queries()
    query_time = sum(query.duration for query in queries)
    start_time, start_clock = flask.g.request_start
    total = time.time() - start_time
    total_cpu = time.clock() - start_clock
    str_ = u"%.2fs (%.2fs CPU and %.2fs for %-2s db queries) '%s %s' %s"
    payload = (total, total_cpu, query_time, len(queries),
               request.method, request.path, response.status)

    performance_logger = getLogger("ggrc.performance")
    if getattr(settings, "PRODUCTION", True):
      # Always use INFO level in production
      performance_logger.info(str_, *payload)
      return response
    if total > 1:
      performance_logger.warning(str_, *payload)
    else:
      performance_logger.info(str_, *payload)
    return response


def register_indexing():
  """Register indexing after request hook"""
  from ggrc.models import background_task
  from ggrc.views import bg_update_ft_records

  # pylint: disable=unused-variable
  @app.after_request
  def create_indexing_bg_task(response):
    """Create background task for indexing
    Adds header 'X-GGRC-Indexing-Task-Id' with BG task id
    """
    if hasattr(db.session, "reindex_set"):
      model_ids = db.session.reindex_set.model_ids_to_reindex
      if model_ids:
        with benchmark("Create indexing bg task"):
          chunk_size = db.session.reindex_set.CHUNK_SIZE
          bg_task = background_task.create_task(
              name="indexing",
              url=url_for(bg_update_ft_records.__name__),
              parameters={"models_ids": model_ids,
                          "chunk_size": chunk_size},
              queued_callback=bg_update_ft_records
          )
          db.session.expunge_all()  # improves plain_commit time
          db.session.add(bg_task)
          db.session.plain_commit()
          response.headers.add("X-GGRC-Indexing-Task-Id", bg_task.id)
    return response


setup_error_handlers(app)
init_models(app)
configure_flask_login(app)
configure_jinja(app)
init_services(app)
init_views(app)
init_extension_blueprints(app)
init_gdrive_routes(app)
init_permissions_provider()
init_extra_listeners()
notifications.register_notification_listeners()
register_indexing()

_enable_debug_toolbar()
_display_sql_queries()
_display_request_time()
_setup_maintenance_check()
