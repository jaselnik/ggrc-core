# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Handlers used for custom attribute columns."""
import re

from datetime import datetime
from dateutil.parser import parse

from ggrc import db
from ggrc import models
from ggrc import utils
from ggrc.converters import errors
from ggrc.converters.handlers import handlers
from ggrc.utils import url_parser

_types = models.CustomAttributeDefinition.ValidTypes


def _get_ca_date_value(value):
  """Extract formatted value for ca with date type."""
  try:
    attr_val = datetime.strptime(
        value.attribute_value, "%Y-%m-%d"
    ).strftime("%m/%d/%Y")
  except ValueError:
    attr_val = u""
  return attr_val


class CustomAttributeColumnHandler(handlers.TextColumnHandler):

  """Custom attribute column handler

  This is a handler for all types of custom attribute column. It works with
  any custom attribute definition and with mandatory flag on or off.
  """

  _type_handlers = {
      _types.TEXT: lambda self: self.get_text_value(),
      _types.DATE: lambda self: self.get_date_value(),
      _types.DROPDOWN: lambda self: self.get_dropdown_value(),
      _types.CHECKBOX: lambda self: self.get_checkbox_value(),
      _types.MULTISELECT: lambda self: self.get_multiselect_values(),
      _types.RICH_TEXT: lambda self: self.get_rich_text_value(),
      _types.MAP: lambda self: self.get_person_value(),
  }

  def set_obj_attr(self):
    """Set object attribute method should do nothing for custom attributes.

    CA values set in insert_object() method.
    """
    if self.value is None:
      return

    cav = self._get_or_create_ca()

    get_indexed_value = cav.custom_attribute.get_indexed_value
    if get_indexed_value(self.value) != get_indexed_value(cav.attribute_value):
      cav.attribute_value = self.value
    if isinstance(cav.attribute_value, models.mixins.base.Identifiable):
      obj = cav.attribute_value
      cav.attribute_value = obj.__class__.__name__
      cav.attribute_object_id = obj.id

  def parse_item(self):
    """Parse raw value from csv file

    Returns:
      CustomAttributeValue with the correct definition type and value.
    """
    definition = self.get_ca_definition()
    if definition is None:
      # In dry run mode CADs is not created for new objects.
      if not self.dry_run and self.raw_value:
        self.add_warning(errors.INVALID_ATTRIBUTE_WARNING,
                         column_name=self.display_name)
      return None
    type_ = definition.attribute_type.split(":")[0]
    value_handler = self._type_handlers[type_]
    return value_handler(self)

  def get_value(self):
    """Return the value of the custom attribute field.

    Returns:
      Text representation if the custom attribute value if it exists, otherwise
      None.
    """
    definition = self.get_ca_definition()
    if not definition:
      return ""
    for value in self.row_converter.obj.custom_attribute_values:
      if value.custom_attribute_id == definition.id:
        if value.custom_attribute.attribute_type.startswith("Map:"):
          # pylint: disable=protected-access
          if value.attribute_object_id is not None and \
             value._attribute_object_attr is not None:
            obj = value.attribute_object
            return getattr(obj, "email", getattr(obj, "slug", None))
        elif value.custom_attribute.attribute_type == _types.CHECKBOX:
          attr_val = value.attribute_value if value.attribute_value else u"0"
          try:
            attr_val = int(attr_val)
          except ValueError:
            attr_val = False
          return "yes" if bool(attr_val) else "no"
        elif value.custom_attribute.attribute_type == _types.DATE:
          return _get_ca_date_value(value)
        else:
          return value.attribute_value

    return None

  def _get_or_create_ca(self):
    """Get a CA value object for the current definition.

    This function returns a custom attribute value object that already existed
    or creates a new one.

    Returns:
        custom attribute value object.
    """
    ca_definition = self.get_ca_definition()
    if not self.row_converter.obj or not ca_definition:
      return None
    for ca_value in self.row_converter.obj.custom_attribute_values:
      if ca_value.custom_attribute_id == ca_definition.id:
        return ca_value
    cav = models.all_models.CustomAttributeValue
    ca_value = cav(
        custom_attribute=ca_definition,
        attributable=self.row_converter.obj,
    )
    return ca_value

  def insert_object(self):
    """Add custom attribute objects to db session."""

  def get_date_value(self):
    """Get date value from input string date."""
    if not self.mandatory and self.raw_value == "":
      return None  # ignore empty fields
    value = None
    try:
      value = parse(self.raw_value).strftime(
          utils.DATE_FORMAT_ISO,
      )
    except (TypeError, ValueError):
      self.add_warning(errors.WRONG_VALUE, column_name=self.display_name)
    if self.mandatory and value is None:
      self.add_error(errors.MISSING_VALUE_ERROR, column_name=self.display_name)
    return value

  def get_checkbox_value(self):
    """Get boolean value for checkbox fields."""
    if not self.mandatory and self.raw_value == "":
      return None  # ignore empty fields
    self.raw_value = re.sub(r'\s+', "", self.raw_value)
    value = self.raw_value.lower() in ("yes", "true")
    if self.raw_value.lower() not in ("yes", "true", "no", "false"):
      self.add_warning(errors.WRONG_VALUE, column_name=self.display_name)
      value = None
    if self.mandatory and value is None:
      self.add_error(errors.MISSING_VALUE_ERROR, column_name=self.display_name)
    return value

  def get_multiselect_values(self):
    """Get valid value for multiselect fields."""
    if not self.raw_value:
      if self.mandatory:
        self.add_error(
            errors.MISSING_VALUE_ERROR,
            column_name=self.display_name
        )
      return None

    definition = self.get_ca_definition()
    choices_list = definition.multi_choice_options.split(",")
    choice_map = {choice.lower(): choice for choice in choices_list}
    is_valid_values = True
    valid_values = ""

    for raw_value in self.raw_value.lower().split(","):
      valid_value = choice_map.get(raw_value)
      if not valid_value:
        is_valid_values = False
        continue
      valid_values += "{},".format(valid_value)

    valid_values = valid_values.rstrip(",")

    if not is_valid_values:
      self.add_warning(errors.WRONG_VALUE, column_name=self.display_name)
    if self.mandatory and not valid_values:
      self.add_error(
          errors.MISSING_VALUE_ERROR,
          column_name=self.display_name
      )
    return valid_values

  def get_dropdown_value(self):
    """Get valid value of the dropdown field."""
    definition = self.get_ca_definition()
    choices_list = definition.multi_choice_options.split(",")
    valid_choices = [val.strip() for val in choices_list]
    choice_map = {choice.lower(): choice for choice in valid_choices}
    value = choice_map.get(self.raw_value.lower())
    if value is None and self.raw_value != "":
      self.add_warning(errors.WRONG_VALUE, column_name=self.display_name)
    if self.mandatory and value is None:
      self.add_error(errors.MISSING_VALUE_ERROR, column_name=self.display_name)
    return value

  def get_text_value(self):
    """Get cleaned text value."""
    if not self.mandatory and self.raw_value == "":
      return None  # ignore empty fields
    value = self.clean_whitespaces(self.raw_value)
    if self.mandatory and not value:
      self.add_error(errors.MISSING_VALUE_ERROR, column_name=self.display_name)
    return value

  def get_rich_text_value(self):
    """Get parsed rich text value."""
    if not self.mandatory and self.raw_value == "":
      return None  # ignore empty fields
    value = url_parser.parse(self.raw_value)
    if self.mandatory and not value:
      self.add_error(errors.MISSING_VALUE_ERROR, column_name=self.display_name)
    return value

  def get_person_value(self):
    """Fetch a person based on the email text in column.

    Returns:
        Person model instance
    """
    if not self.mandatory and self.raw_value == "":
      return None  # ignore empty fields
    if self.mandatory and not self.raw_value:
      self.add_error(errors.MISSING_VALUE_ERROR, column_name=self.display_name)
      return None
    value = models.Person.query.filter_by(email=self.raw_value).first()
    if self.mandatory and not value:
      self.add_error(errors.WRONG_VALUE, column_name=self.display_name)
    return value

  def get_ca_definition(self):
    """Get custom attribute definition."""
    cache = self.row_converter.block_converter.ca_definitions_cache
    return cache.get((None, self.display_name))


class ObjectCaColumnHandler(CustomAttributeColumnHandler):

  """Handler for object level custom attributes."""

  def set_value(self):
    pass

  def set_obj_attr(self):
    """Parse item and set the current value.

    This is a hack to get set_value on this handler called after all other
    values have already been set.
    """
    self.value = self.parse_item()
    if self.value_explicitly_empty(self.value) and self._delete_unset_values():
      return
    super(ObjectCaColumnHandler, self).set_obj_attr()

  def _delete_unset_values(self):
    """
    Check if CAD need to deleted from object and delete if need it

    Returns:
       bool: True if old value from cav has been deleted.
        False if no need to delete old cav value
    """
    ca_definition = self.get_ca_definition()
    if ca_definition.attribute_type.split(":")[0] == _types.MAP:
      if not self.row_converter.obj or not ca_definition:
        return False
      for ca_value in self.row_converter.obj.custom_attribute_values:
        if ca_value.custom_attribute_id == ca_definition.id:
          db.session.delete(ca_value)
      return True
    return False

  def get_ca_definition(self):
    """Get custom attribute definition for a specific object."""
    cache = self.row_converter.block_converter.ca_definitions_cache
    if self.row_converter.obj.id is None:
      if self.row_converter.object_class == models.all_models.Assessment:
        template = self._get_assessment_template()
        cad = cache.get((template.id if template else None, self.display_name))
        return cad

      return None
    return cache.get((self.row_converter.obj.id, self.display_name))

  def _get_assessment_template(self):
    """Collect assessment template from row_converter"""
    template_handler = self.row_converter.objects.get("assessment_template")
    if template_handler is None:
      return None

    templates = template_handler.parse_item()
    if not templates:
      return None

    template = templates[0]
    return template

  def get_date_value(self):
    """Get date value from input string date."""
    if self.raw_value == "":
      return None  # ignore empty fields
    value = None
    try:
      value = parse(self.raw_value).strftime(
          utils.DATE_FORMAT_ISO,
      )
    except (TypeError, ValueError):
      self.add_warning(errors.WRONG_VALUE, column_name=self.display_name)
    return value

  def get_checkbox_value(self):
    """Get boolean value for checkbox fields."""
    if self.raw_value == "":
      return None  # ignore empty fields
    self.raw_value = re.sub(r'\s+', "", self.raw_value)
    value = self.raw_value.lower() in ("yes", "true")
    if self.raw_value.lower() not in ("yes", "true", "no", "false"):
      self.add_warning(errors.WRONG_VALUE, column_name=self.display_name)
      value = None
    return value

  def get_multiselect_values(self):
    """Get valid value for multiselect fields."""
    if self.raw_value == "":
      return None  # ignore empty fields

    definition = self.get_ca_definition()
    choices_list = definition.multi_choice_options.split(",")
    choice_map = {choice.lower(): choice for choice in choices_list}
    is_valid_values = True
    valid_values = ""

    for raw_value in self.raw_value.lower().split(","):
      valid_value = choice_map.get(raw_value)
      if not valid_value:
        is_valid_values = False
        continue
      valid_values += "{},".format(valid_value)

    valid_values = valid_values.rstrip(",")

    if not is_valid_values:
      self.add_warning(errors.WRONG_VALUE, column_name=self.display_name)
    return valid_values or None

  def get_dropdown_value(self):
    """Get valid value of the dropdown field."""
    if self.raw_value == "":
      return None  # ignore empty fields
    definition = self.get_ca_definition()
    choices_list = definition.multi_choice_options.split(",")
    valid_choices = [val.strip() for val in choices_list]
    choice_map = {choice.lower(): choice for choice in valid_choices}
    value = choice_map.get(self.raw_value.lower())
    if value is None and self.raw_value != "":
      self.add_warning(errors.WRONG_VALUE, column_name=self.display_name)
    return value

  def get_text_value(self):
    """Get cleaned text value."""
    if self.raw_value == "":
      return None  # ignore empty fields
    value = self.clean_whitespaces(self.raw_value)
    return value

  def get_rich_text_value(self):
    """Get parsed rich text value."""
    if self.raw_value == "":
      return None  # ignore empty fields
    value = url_parser.parse(self.raw_value)
    return value

  def get_person_value(self):
    """Fetch a person based on the email text in column.

    Returns:
        Person model instance
    """
    if self.value_explicitly_empty(self.raw_value):
      return self.raw_value
    if self.raw_value == "":
      return None  # ignore empty fields
    value = models.Person.query.filter_by(email=self.raw_value).first()
    if not value:
      self.add_warning(errors.WRONG_VALUE, column_name=self.display_name)
      value = None
    return value
