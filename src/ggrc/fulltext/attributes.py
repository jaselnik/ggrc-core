# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

""" This module collect all custom full text attributes classes"""
import json
from logging import getLogger
from collections import defaultdict

import datetime

from flask import g

from ggrc.utils import date_parsers
from ggrc.fulltext.mixin import Indexed

logger = getLogger(__name__)

EMPTY_SUBPROPERTY_KEY = ''


class FullTextAttr(object):
  """Custom full text index attribute class

  Allows to add full text indexing rule for attribute with a custom alias,
  getting value rule and subproperties.
  Alias should be a string that will be used as search field.
  Prop_getter can be a string or a callable.
  If prop_getter is a string, then the stored value will be the current
  instance's attribute value.
  If prop_getter is a callable, then the stored value will be the result of
  called prop_getter with current instance as an attribute.
  Subproperties may be empty or a list of strings. Each element of the list
  should be an attribute of the stored value.
  The first subproperty in the list - the one used for sorting.
  """

  SUB_KEY_TMPL = "{id_val}-{sub}"

  def __init__(self, alias, prop_getter, subproperties=None,
               with_template=True, getter_kwargs=None):
    self.alias = alias
    self.prop_getter = prop_getter
    self.getter_kwargs = getter_kwargs or {}
    self.subproperties = subproperties or [EMPTY_SUBPROPERTY_KEY]
    self.with_template = with_template
    self.is_sortable = EMPTY_SUBPROPERTY_KEY not in self.subproperties

  def get_attribute_name(self, instance):
    """Get attribute's name from it's alias

    If template exists for the property, it's being applied
    """
    if isinstance(instance, Indexed):
      return instance.get_fulltext_attr_name(self)

    return self.alias

  def get_value_for(self, instance):
    """Get value from the given instance using 'prop_getter' rule"""
    if callable(self.prop_getter):
      return self.prop_getter(instance, **self.getter_kwargs)
    return getattr(instance, self.prop_getter)

  def get_property_for(self, instance):
    """Collect property dict for the given instance"""
    value = self.get_value_for(instance)
    results = {}
    sorted_dict = {}
    sorting_subprop = self.subproperties[0]
    for subprop in self.subproperties:
      if value is not None and subprop != EMPTY_SUBPROPERTY_KEY:
        subprop_key = self.SUB_KEY_TMPL.format(id_val=value.id, sub=subprop)
        result = getattr(value, subprop)
        results[subprop_key] = result
        if result and subprop == sorting_subprop:
          sorted_dict[value.id] = unicode(result)
      else:
        results[subprop] = value
    if self.is_sortable and results:
      results['__sort__'] = u':'.join(sorted(sorted_dict.values()))
    return {self.get_attribute_name(instance): results}

  # pylint: disable=unused-argument
  @staticmethod
  def get_filter_value(value, operation):
    return value

  def get_attribute_revisioned_value(self, content):
    """Get attribute value from the given revision content

    accorging to the FullTextAttr rules
    """
    return content.get(self.alias, None)


class CustomOrderingFullTextAttr(FullTextAttr):
  """Custom full text index attribute class for specific ordering

  Used in case when we need to have custom sort
  """
  def __init__(self, *args, **kwargs):
    kwargs["subproperties"] = None
    order_prop_getter = kwargs.pop("order_prop_getter")

    assert order_prop_getter is not None

    self.order_prop_getter = order_prop_getter
    super(CustomOrderingFullTextAttr, self).__init__(*args, **kwargs)

  def get_order_value_for(self, instance):
    """Get value from the given instance using 'order_prop_getter' rule"""
    if callable(self.order_prop_getter):
      return self.order_prop_getter(instance)

    return getattr(instance, self.order_prop_getter)

  def get_property_for(self, instance):
    """Collect property dict for the given instance"""
    attribute_name = self.get_attribute_name(instance)
    value = self.get_value_for(instance)

    order_value = self.get_order_value_for(instance)
    results = {"__sort__": order_value, attribute_name: value}
    return {attribute_name: results}


class ValueMapFullTextAttr(FullTextAttr):
  """Custom full text index attribute class for specific values

  Used in case when we need to cast property value to some
  specific value to be indexed.
  """
  def __init__(self, *args, **kwargs):
    value_map = kwargs.pop("value_map", None)
    assert value_map is not None
    self.value_map = value_map
    super(ValueMapFullTextAttr, self).__init__(*args, **kwargs)

  def get_value_for(self, instance):
    """Get value from the instance using value_map rule"""
    value = super(ValueMapFullTextAttr, self).get_value_for(instance)
    # handle error if value_map doesn't have mapping for the given value
    return self.value_map.get(value, None)

  def get_attribute_revisioned_value(self, content):
    """Get attribute value from the given revision content

    accorging to the FullTextAttr rules
    """
    return self.value_map.get(content[self.alias], None)


class BooleanFullTextAttr(ValueMapFullTextAttr):
  """Custom full text index attribute class for Boolean values

  Used in case we need to cast property boolean value to some
  specific value to be indexed.
  E.g. 1/0 to key/non-key (for Significance field)
  """
  # pylint: disable=too-many-arguments
  def __init__(self, alias, prop_getter, subproperties=None,
               true_value="true", false_value="false",
               with_template=True,):
    value_map = {True: true_value, False: false_value}
    super(BooleanFullTextAttr, self).__init__(alias, prop_getter,
                                              subproperties=subproperties,
                                              with_template=with_template,
                                              value_map=value_map)

  def get_value_for(self, instance):
    """Get value from the instance using value_map rule"""
    # pylint: disable=bad-super-call
    value = super(ValueMapFullTextAttr, self).get_value_for(instance)
    if value is not None:
      return self.value_map.get(value, None)
    return None

  def get_attribute_revisioned_value(self, content):
    """Get attribute value from the given revision content

    accorging to the FullTextAttr rules
    """
    rev_val = content[self.alias]
    if rev_val is None:
      return None
    if not isinstance(rev_val, bool):
      rev_val = bool(int(str(rev_val)))
    return self.value_map.get(rev_val, None)


class CustomRoleAttr(FullTextAttr):
  """Custom full text index attribute class for custom roles"""
  # pylint: disable=too-few-public-methods
  def __init__(self, alias):
    super(CustomRoleAttr, self).__init__(alias, alias)
    self.with_template = False

  def get_property_for(self, instance):
    """Returns index properties of all custom roles for a given instance"""
    results = {}
    sorted_roles = defaultdict(list)
    for person, acl in getattr(instance, self.alias, []):
      if not acl.ac_role:
        # If acl is not properly set the acl record was *most likely* created
        # through acl propagation hook and probably shouldn't be indexed at
        # all, because we are creating internal roles. In any case we can
        # properly check for the internal property on the role once GGRC-3784
        # is done.
        continue
      if acl.ac_role.internal:
        # Don't index internal roles they are not presented to user.
        continue
      if instance.type != acl.ac_role.object_type:
        logger.warning("Reindex: role %s, id %s is skipped for %s, id %s, "
                       "because it relates to %s", acl.ac_role.name,
                       acl.ac_role.id, instance.__class__.__name__,
                       instance.id, acl.ac_role.object_type)
        continue
      ac_role = acl.ac_role.name
      person_id = person.id
      if not results.get(acl.ac_role.name, None):
        results[acl.ac_role.name] = {}
      sorted_roles[ac_role].append(person.email)
      results[ac_role]["{}-email".format(person_id)] = person.email
      results[ac_role]["{}-name".format(person_id)] = person.name
    for role in sorted_roles:
      results[role]["__sort__"] = u':'.join(sorted(sorted_roles[role]))
    return results


class MultipleSubpropertyFullTextAttr(FullTextAttr):
  """Custom full text index attribute class for multiple return values

  subproperties required for this class
  this class required for store in full text search more than 1 returned value
  this values should be instances with `id` attribute or None values
  In the case if values is None id in subquery template will be set up as
  `EMPTY` value
  """

  def __init__(self, *args, **kwargs):
    super(MultipleSubpropertyFullTextAttr, self).__init__(*args, **kwargs)
    assert EMPTY_SUBPROPERTY_KEY not in self.subproperties
    assert self.is_sortable

  def get_property_for(self, instance):
    """Collect property for sended instance"""
    values = self.get_value_for(instance)
    results = {}
    sorted_dict = {}
    sorting_subprop = self.subproperties[0]
    for sub in self.subproperties:
      for value in values:
        if value is not None:
          sub_key = self.SUB_KEY_TMPL.format(id_val=value.id, sub=sub)
          result = getattr(value, sub)
          results[sub_key] = result
          if result and sub == sorting_subprop:
            sorted_dict[value.id] = unicode(result)
        else:
          sub_key = self.SUB_KEY_TMPL.format(id_val='EMPTY', sub=sub)
          results[sub_key] = None
    if self.is_sortable and results:
      results['__sort__'] = u':'.join(sorted(sorted_dict.values()))
    return {self.get_attribute_name(instance): results}


class JsonListFullTextAttr(FullTextAttr):
  """Custom fulltext index attribute class for json list values."""

  def get_property_for(self, instance):
    """Collect property for sent instance."""
    json_value = self.get_value_for(instance)
    if not json_value:
      return {}
    values = json.loads(json_value)
    results = {}
    for value in values:
      results[value] = value
    if self.is_sortable and results:
      results["__sort__"] = u":".join(sorted(results.values()))
    return {self.get_attribute_name(instance): results}


# pylint: disable=too-few-public-methods
class DatetimeValue(object):
  """Mixin setup if expected filter value is datetime.

  This mixin should be used for filtering datetime fields values only.
  """

  VALUE_ERROR_MSG = (u"Specified date format is invalid for search, "
                     u"please use the following format for date: "
                     u"mm/dd/yyyy, mm-dd-yyyy, mm/yyyy, mm-yyyy, yyyy.")

  def get_value_error_msg(self):
    return self.VALUE_ERROR_MSG

  @staticmethod
  def get_filter_value(value, operation):
    """returns parsed datetime pairs for selected operation"""
    converted_pairs = date_parsers.parse_date(unicode(value))
    if not converted_pairs:
      return None
    date_dict = {
        "=": converted_pairs,
        "~": converted_pairs,
        "!~": (converted_pairs[1], converted_pairs[0]),
        "!=": (converted_pairs[1], converted_pairs[0]),
        ">": (converted_pairs[1], None),
        "<": (None, converted_pairs[0]),
        ">=": (converted_pairs[0], None),
        "<=": (None, converted_pairs[1]),
    }
    return date_dict.get(operation)


class DateValue(DatetimeValue):
  """Mixin setup if expected filter value is date

  This mixin should be used for filtering date fields values only.
  """

  def get_filter_value(self, value, operation):
    results = super(DateValue, self).get_filter_value(value, operation)
    if not results:
      return None
    return [i.date() if i else i for i in results]


class TimezonedDatetimeValue(DatetimeValue):
  """Mixin setup if expected filter value is datetime depended from timezone.

  This mixin should be used for filtering datetime fields values only.
  """

  def get_filter_value(self, value, operation):
    """returns parsed datetime pairs for selected operation"""
    if getattr(g, "user_timezone_offset", None):
      minutes_offset = int(g.user_timezone_offset)
    else:
      minutes_offset = 0
    offset = datetime.timedelta(minutes=minutes_offset)
    converted_pairs = super(TimezonedDatetimeValue, self).get_filter_value(
        value, operation
    )
    if not converted_pairs:
      return converted_pairs
    return [(p - offset) if p else p for p in converted_pairs]


class DatetimeFullTextAttr(TimezonedDatetimeValue, FullTextAttr):
  """Custom full text index attribute class for Datetime values"""

  def get_attribute_revisioned_value(self, content):
    """Get attribute value from the given revision content

    accorging to the FullTextAttr rules
    """
    if self.prop_getter in content and content[self.alias]:
      return content[self.alias].replace("T", " ")
    return None


DateFullTextAttr = type("DateFullTextAttr", (DateValue, FullTextAttr), {})


DatetimeMultipleSubpropertyFullTextAttr = type(
    "DatetimeMultipleSubpropertyFullTextAttr",
    (TimezonedDatetimeValue, MultipleSubpropertyFullTextAttr),
    {},
)


DateMultipleSubpropertyFullTextAttr = type(
    "DateMultipleSubpropertyFullTextAttr",
    (DateValue, MultipleSubpropertyFullTextAttr),
    {},
)
