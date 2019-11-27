# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Settings for Flask and Flask-SQLAlchemy

Flask: http://flask.pocoo.org/docs/config/
Flask-SQLAlchemy:
  https://github.com/mitsuhiko/flask-sqlalchemy/blob/master/docs/config.rst

Default settings should go in `settings.default`.

Environment/deployment-specific settings should go in
`settings.<environment_name>`.
"""

import json
import os

BASE_DIR = os.path.realpath(os.path.join(
    os.path.dirname(__file__), '..', '..'))
MODULE_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
SETTINGS_DIR = os.path.join(BASE_DIR, 'ggrc', 'settings')
THIRD_PARTY_DIR = os.path.realpath(os.path.join(BASE_DIR, '..', 'third_party'))
MANIFEST_CFG_PATH = os.path.join(BASE_DIR, 'ggrc', 'manifest.json')

from ggrc.settings.default import *  # noqa

try:
  manifest_data = json.load(open(MANIFEST_CFG_PATH))  # noqa # pylint: disable=invalid-name
  STYLES_CSS_PATH = manifest_data['styles.css']
  VENDOR_CSS_PATH = manifest_data['vendor.css']
  VENDOR_JS_PATH = manifest_data['vendor.js']
  COMMON_JS_PATH = manifest_data['common.js']
  DASHBOARD_JS_PATH = manifest_data['dashboard.js']
  IMPORT_JS_PATH = manifest_data['import.js']
  EXPORT_JS_PATH = manifest_data['export.js']
  ADMIN_JS_PATH = manifest_data['admin.js']
  LOGIN_JS_PATH = manifest_data['login.js']
except (KeyError, IOError):
  raise RuntimeError("File '{}' with JS configuration should exist. "
                     "Next keys should be present there: "
                     "'dashboard.css, dashboard.js, vendor.css, "
                     "vendor.js'.".format(MANIFEST_CFG_PATH))

SETTINGS_MODULE = os.environ.get("GGRC_SETTINGS_MODULE", '')
CUSTOM_URL_ROOT = os.environ.get("GGRC_CUSTOM_URL_ROOT")
ABOUT_URL = os.environ.get("GGRC_ABOUT_URL")
ABOUT_TEXT = os.environ.get("GGRC_ABOUT_TEXT")
EXTERNAL_HELP_URL = os.environ.get("GGRC_EXTERNAL_HELP_URL")
EXTERNAL_IMPORT_HELP_URL = os.environ.get("GGRC_EXTERNAL_IMPORT_HELP_URL")
SERVER_SOFTWARE = os.environ.get('SERVER_SOFTWARE', '')
# whether the code is running in production or in the local development server
CLOUD_APPSERVER = SERVER_SOFTWARE.startswith('Google App Engine/')

REVIEW_LEVELS_MIN_COUNT = int(os.environ.get("REVIEW_LEVELS_MAX_COUNT", "1"))
REVIEW_LEVELS_MAX_COUNT = int(os.environ.get("REVIEW_LEVELS_MAX_COUNT", "10"))

if len(SETTINGS_MODULE.strip()) == 0:
  raise RuntimeError("Specify your settings using the `GGRC_SETTINGS_MODULE` "
                     "environment variable")

for module_name in SETTINGS_MODULE.split(" "):
  if len(module_name.strip()) == 0:
    continue

  filename = "{0}.py".format(module_name)
  fullpath = os.path.join(SETTINGS_DIR, filename)

  if not os.path.exists(fullpath):
    fullpath = "{0}.py".format(os.path.join(*module_name.split('.')))
  if not os.path.exists(fullpath):
    import imp
    module_name_parts = module_name.split('.')
    base_package = module_name_parts[0]
    _file, pathname, description = imp.find_module(base_package)
    fullpath = "{0}/{1}.py".format(
        pathname, os.path.join(*module_name_parts[1:]))

  namespace = {}
  execfile(fullpath, globals(), namespace)

  EXTENSIONS.extend(namespace.pop("EXTENSIONS", []))
  exports.extend(namespace.pop("exports", []))
  LOGGING_LOGGERS.update(namespace.pop("LOGGING_LOGGERS", {}))

  globals().update(namespace)


LOGGING = {
    "version": 1,
    "root": {
        "level": LOGGING_ROOT,
    },
    "loggers": {
        name: {"level": level}
        for name, level in LOGGING_LOGGERS.iteritems()
    },
    # Use preconfigured handlers and formatters when run on AppEngine
    "incremental": globals().get('APP_ENGINE', False),
}

if not LOGGING["incremental"]:
  LOGGING.update({
      "formatters": {
          "default": LOGGING_FORMATTER,
      },
      "handlers": {
          "default": LOGGING_HANDLER,
      },
      "disable_existing_loggers": False,
  })
  LOGGING["root"]["handlers"] = ["default"]
