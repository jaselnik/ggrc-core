# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
# pylint: disable=too-few-public-methods
"""Module attribute changes trackers"""

from sqlalchemy import inspect


class AttributeChangesTracker(object):
  """Default attribute changes tracker"""

  def __init__(self, attr):
    self.attr = attr

  @staticmethod
  def _has_changes(obj, attr):
    """Detects if object attribute has changes

    Args:
      obj: (db.Model instance) Object on which to perform attribute inspection.
      attr: (string) Attribute to inspect
    Returns:
      A boolean representing if models attribute changed.
    """
    attr = getattr(inspect(obj).attrs, attr)
    return attr.history.has_changes()

  def track_changes(self, obj):
    """Track session changes for `attr`

    Args:
      obj: Instance tracked by the attr
    """
    return self._has_changes(obj, self.attr)


class ACLAttributeTracker(AttributeChangesTracker):
  """Changes tracker for acl attributes"""

  def track_changes(self, obj):
    # pylint: disable=protected-access
    for acl in obj._access_control_list:
      if self._has_changes(acl, 'access_control_people'):
        return True
    return False


class AttributesGroupTracker(dict):
  """Class to collect required api tracked attributes."""

  CHANGES_TRACKER = AttributeChangesTracker

  def __init__(self, *attrs):
    super(AttributesGroupTracker, self).__init__()
    self.add(*attrs)

  def add(self, *attrs):
    """Append attrs.

    Attrs is the list of strings/unicodes or AttributeChangesTracker instances
    """
    for attr in attrs:
      if isinstance(attr, basestring):
        attr = self.CHANGES_TRACKER(attr)
      self[attr.attr] = attr
