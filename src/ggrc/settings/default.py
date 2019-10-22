# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module defines application settings."""

import datetime
import os

import jinja2

DEBUG = False
TESTING = False
PRODUCTION = False
GOOGLE_INTERNAL = False

# Flask-SQLAlchemy fix to be less than `wait_time` in /etc/mysql/my.cnf
SQLALCHEMY_POOL_RECYCLE = 120

# Settings in app.py
AUTOBUILD_ASSETS = False
DEBUG_ASSETS = False
FULLTEXT_INDEXER = None
USER_PERMISSIONS_PROVIDER = \
    'ggrc_basic_permissions.CompletePermissionsProvider'
EXTENSIONS = [
    'ggrc_basic_permissions',
    'ggrc_workflows',
]
exports = [
    "GAPI_KEY",
    "GAPI_CLIENT_ID",
    "GAPI_ADMIN_GROUP",
    "VERSION",
    "MAX_INSTANCES",
    "CREATE_ISSUE_URL",
    "CREATE_ISSUE_BUTTON_NAME",
    "ASSESSMENT_SHORT_URL_PREFIX",
    "NOTIFICATION_PREFIX",
    "DAILY_DIGEST_BATCH_SIZE",
    "CHANGE_REQUEST_URL",
]  # pylint: disable=invalid-name

# Deployment-specific variables
COMPANY = os.environ.get("COMPANY", "Company, Inc.")
COMPANY_LOGO = "/static/images/ggrc-logo.svg"
COMPANY_LOGO_TEXT = os.environ.get("COMPANY_LOGO_TEXT", "Company")
COPYRIGHT = u"Confidential. Copyright \u00A9"  # \u00A9 is the (c) symbol

# Construct build number
BUILD_NUMBER = ""
try:
  import build_number
  BUILD_NUMBER = " ({0})".format(build_number.BUILD_NUMBER[:7])
except ImportError:
  pass

# NOTE: This version name is used for GAE deployments along with the current
# commit hash. The version and hash are trimmed to 30 characters (see do_deploy
# for more info) and if the version name were to exceed 30 characters, all
# deployments would go to the same GAE app version. Please take that into
# consideration when modifying this string.
VERSION = "2.21.0-Pumpkin" + BUILD_NUMBER

# Migration owner
MIGRATOR = os.environ.get(
    'GGRC_MIGRATOR',
    'Default Migrator <migrator@example.com>',
)

# Google Analytics variables
GOOGLE_ANALYTICS_ID = os.environ.get('GGRC_GOOGLE_ANALYTICS_ID', '')
GOOGLE_ANALYTICS_DOMAIN = os.environ.get('GGRC_GOOGLE_ANALYTICS_DOMAIN', '')

ANALYTICS_TEMPLATE = """
<script type="text/javascript">
(function (i,s,o,g,r,a,m) {i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
(i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
})(window,document,'script','https://www.google-analytics.com/analytics.js','ga');

ga('create', '%s', 'auto');
ga('send', 'pageview');
</script>
"""

if GOOGLE_ANALYTICS_ID:
  GOOGLE_ANALYTICS_SCRIPT = ANALYTICS_TEMPLATE % GOOGLE_ANALYTICS_ID
else:
  GOOGLE_ANALYTICS_SCRIPT = ""

# Initialize from environment if present
SQLALCHEMY_DATABASE_URI = os.environ.get('GGRC_DATABASE_URI', '')
SECRET_KEY = os.environ.get('GGRC_SECRET_KEY', 'Replace-with-something-secret')
PERMANENT_SESSION_LIFETIME = os.environ.get('GGRC_PERMANENT_SESSION_LIFETIME',
                                            datetime.timedelta(days=365))

MEMCACHE_MECHANISM = True

# AppEngine Email
APPENGINE_EMAIL = os.environ.get('APPENGINE_EMAIL', '')

CALENDAR_MECHANISM = False

MAX_INSTANCES = os.environ.get('MAX_INSTANCES', '3')

# Users with authorized domain will automatically get Creator role.
AUTHORIZED_DOMAIN = os.environ.get('AUTHORIZED_DOMAIN', "")

ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN', '')

JINJA2 = jinja2.Environment(loader=jinja2.PackageLoader('ggrc', 'templates'))
EMAIL_DIGEST = JINJA2.get_template("notifications/email_digest.html")
EMAIL_DAILY = JINJA2.get_template("notifications/view_daily_digest.html")
EMAIL_PENDING = JINJA2.get_template("notifications/view_pending_digest.html")
EMAIL_IMPORT_EXPORT = JINJA2.get_template("notifications/import_export.html")
EMAIL_BULK_CHILD_SYNC_SUCCEEDED = JINJA2.get_template(
    "notifications/bulk_child_sync_succeded.html"
)
EMAIL_BULK_CHILD_SYNC_FAILED = JINJA2.get_template(
    "notifications/bulk_child_sync_failed.html"
)
EMAIL_BULK_CHILD_SYNC_EXCEPTION = JINJA2.get_template(
    "notifications/bulk_child_sync_exception.html"
)
EMAIL_BULK_SYNC_SUCCEEDED = JINJA2.get_template(
    "notifications/bulk_sync_succeded.html"
)
EMAIL_BULK_SYNC_FAILED = JINJA2.get_template(
    "notifications/bulk_sync_failed.html"
)
EMAIL_BULK_SYNC_EXCEPTION = JINJA2.get_template(
    "notifications/bulk_sync_exception.html"
)
EMAIL_MENTIONED_PERSON = JINJA2.get_template(
    "notifications/email_mentioned.html"
)

EMAIL_BULK_COMPLETE = JINJA2.get_template(
    "notifications/bulk_complete.html"
)

USE_APP_ENGINE_ASSETS_SUBDOMAIN = False

BACKGROUND_COLLECTION_POST_SLEEP = 0


LOGGING_HANDLER = {
    "class": "logging.StreamHandler",
    "stream": "ext://sys.stdout",
    "formatter": "default",
}
LOGGING_FORMATTER = {
    "format": "%(levelname)-8s %(asctime)s %(name)s %(message)s",
}
LOGGING_ROOT = "WARNING"
LOGGING_LOGGERS = {
    "ggrc": "INFO",
    "ggrc.performance": "INFO",
    # INFO    - logs performance stats for requests
    # WARNING - logs performance for requests that took longer than 1s

    "sqlalchemy": "WARNING",
    # WARNING - logs warnings and errors only
    # INFO    - logs SQL-queries
    # DEBUG   - logs SQL-queries + result sets

    "werkzeug": "WARNING",
    # WARNING - logs warnings and errors only
    # INFO    - logs HTTP-queries

    # "ggrc.utils.benchmarks": "DEBUG"
    # DEBUG - logs all benchmarks
}


DEBUG_BENCHMARK = os.environ.get("GGRC_BENCHMARK")

# GGRCQ integration
GGRC_Q_INTEGRATION_URL = os.environ.get('GGRC_Q_INTEGRATION_URL', '')

# Integration service
INTEGRATION_SERVICE_URL = os.environ.get('INTEGRATION_SERVICE_URL')

# GGRC user account to be used by external application auth
EXTERNAL_APP_USER = os.environ.get('EXTERNAL_APP_USER', '')

# Sync Service account to validate requests from sync service
SYNC_SERVICE_USER = os.environ.get('SYNC_SERVICE_USER', '')

# Integration service mandatory header value
URLFETCH_SERVICE_ID = os.environ.get('URLFETCH_SERVICE_ID')

# Flag defining whether integration with issue tracker is enabled or not.
ISSUE_TRACKER_ENABLED = bool(os.environ.get('ISSUE_TRACKER_ENABLED'))

# URL template for composing Issue Tracker ticker URL.
ISSUE_TRACKER_BUG_URL_TMPL = os.environ.get('ISSUE_TRACKER_BUG_URL_TMPL')

# Flag defining whether we need to mock issue tracker responses
ISSUE_TRACKER_MOCK = bool(os.environ.get('ISSUE_TRACKER_MOCK'))

# Dashboard integration
_DEFAULT_DASHBOARD_INTEGRATION_CONFIG = {
    "ca_name_regexp": r"^Dashboard_(.*)$",
    "ca_value_regexp": r"^https?://[^\s]+$",
}

if bool(os.environ.get("DASHBOARD_INTEGRATION", "")):
  DASHBOARD_INTEGRATION = _DEFAULT_DASHBOARD_INTEGRATION_CONFIG.copy()
else:
  DASHBOARD_INTEGRATION = None

# App2app QueryAPI endpoints
ALLOWED_QUERYAPI_APP_IDS = os.environ.get(
    "ALLOWED_QUERYAPI_APP_IDS",
    "",
).split()

# Flag to enable or disable What's New pop-up
ENABLE_RELEASE_NOTES = True

# ggrc_basic_permissions specific module settings
BOOTSTRAP_ADMIN_USERS = \
    os.environ.get('GGRC_BOOTSTRAP_ADMIN_USERS', '').split(' ')

# ggrc_gdrive_integration specific module settings
GAPI_KEY = os.environ.get('GGRC_GAPI_KEY', "")
GAPI_CLIENT_ID = os.environ.get('GGRC_GAPI_CLIENT_ID', "")
# Admin group gets writer access to all
GAPI_ADMIN_GROUP = os.environ.get('GGRC_GAPI_ADMIN_GROUP', "")
GAPI_CLIENT_SECRET = os.environ.get('GGRC_GAPI_CLIENT_SECRET', "")

ASSESSMENT_SHORT_URL_PREFIX = os.environ.get(
    'GGRC_ASSESSMENT_SHORT_URL_PREFIX',
    ''
)
NOTIFICATION_PREFIX = os.environ.get(
    'GGRC_NOTIFICATION_PREFIX',
    ''
)

if not os.environ.get('GGRC_DAILY_DIGEST_BATCH_SIZE', ''):
  DAILY_DIGEST_BATCH_SIZE = 5000
else:
  DAILY_DIGEST_BATCH_SIZE = int(
      os.environ.get('GGRC_DAILY_DIGEST_BATCH_SIZE')
  )

# Link for creation issue tracker issue
CREATE_ISSUE_URL = os.environ.get('CREATE_ISSUE_URL', "")
CREATE_ISSUE_BUTTON_NAME = os.environ.get('CREATE_ISSUE_BUTTON_NAME', "")

# Link for change request on my task page
CHANGE_REQUEST_URL = os.environ.get("CHANGE_REQUEST_URL", "")

# BackgroundTask default settings
RETRY_OPTIONS = {
    "min_backoff_seconds": 30,
    "max_backoff_seconds": 3600,
    "max_doublings": 5,
    "task_retry_limit": 10,
}
DEFAULT_QUEUE = "ggrc"

APPENGINE_INSTANCE = os.environ.get('APPENGINE_INSTANCE')
APPENGINE_LOCATION = os.environ.get('APPENGINE_LOCATION', 'us-central1')
