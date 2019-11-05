# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module validate status affection"""

from sqlalchemy import inspect

from ggrc.utils.statusaffected import attribute_tracker


AFFECTED_MAP = {
    'Evidence': {
        'Assessment': {
            'no_affect': attribute_tracker.AttributesGroupTracker(
                'notes',
                'description'
            ),
            'side_affect': attribute_tracker.AttributesGroupTracker(
                attribute_tracker.ACLAttributeTracker('_access_control_list')
            ),
            'optional_affect': attribute_tracker.AttributesGroupTracker(
                'updated_at',
                'modified_by_id',
            )
        },
    },
}


class StatusAffectedChanges(object):
  # pylint: disable=too-many-instance-attributes
  """Validator obj changes for affected_obj status"""

  def __init__(self, obj, affected_obj):
    """
    Args:
      obj: object which has attribute updates
      affected_obj: object which was affected by changed object
    """
    self.obj = obj
    self.object_class = obj.__class__.__name__
    self.affected_obj = affected_obj
    self.affected_obj_class = affected_obj.__class__.__name__
    self.no_affect = dict()
    self.side_affect = dict()
    self.optional_affect = dict()
    self.base_attrs = attribute_tracker.AttributesGroupTracker()
    self.prepare_attrs()

  def prepare_attrs(self):
    """Prepare all attr groups"""
    affected_map = AFFECTED_MAP.get(
        self.object_class, {}
    ).get(self.affected_obj_class)
    if not affected_map:
      return
    self.no_affect = affected_map.get('no_affect', dict())
    self.side_affect = affected_map.get('side_affect', dict())
    self.optional_affect = affected_map.get('optional_affect', dict())
    all_attrs_names = [attr.key for attr in inspect(self.obj).attrs]
    for attr in all_attrs_names:
      if bool(self.no_affect.get(attr) is None and
              self.side_affect.get(attr) is None and
              self.optional_affect.get(attr) is None):
        self.base_attrs.add(attr)

  def was_affected(self):
    """Return decision if request changes affected status"""
    for _, attr in self.base_attrs.iteritems():
      if attr.track_changes(self.obj):
        return True
    for _, attr in self.side_affect.iteritems():
      if attr.track_changes(self.obj):
        return True
    for _, attr in self.no_affect.iteritems():
      if attr.track_changes(self.obj):
        return False
    return True
