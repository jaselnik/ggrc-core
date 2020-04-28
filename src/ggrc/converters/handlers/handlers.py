# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Generic handlers for imports and exports."""
import json
import re
from logging import getLogger
from datetime import date
from datetime import datetime
from dateutil.parser import parse

from sqlalchemy import and_
from sqlalchemy import or_

from ggrc import db
from ggrc import settings
from ggrc.converters import get_exportables, errors
from ggrc.login import get_current_user
from ggrc.models import all_models
from ggrc.models.exceptions import ValidationError
from ggrc.models.mixins.with_custom_restrictions import WithCustomRestrictions
from ggrc.models.reflection import AttributeInfo
from ggrc.rbac import permissions

# pylint: disable=invalid-name,too-many-lines
from ggrc.services import signals

logger = getLogger(__name__)

MAPPING_PREFIX = "__mapping__:"
CUSTOM_ATTR_PREFIX = "__custom__:"


class PersonColumnHandlerMixin(object):
  """Mixin providing base functionality for people column handlers."""

  @staticmethod
  def get_people_emails_from_value(value):
    # type: (str) -> List[str]
    """Return list of people emails from `value`."""
    email_list = re.split("[, ;\n]+", value.lower().strip())
    email_list = filter(None, email_list)
    return sorted(email_list)

  @classmethod
  def validate_email(cls, email):
    # type: (str) -> None
    """Validate email. If not valid, `ValidationError` will be raised."""
    empty_values = getattr(cls, "EXPLICIT_EMPTY_VALUE", set())
    if not (email in empty_values or all_models.Person.is_valid_email(email)):
      message = "Email address '{}' is invalid. Valid email must be provided"
      raise ValidationError(message.format(email))


class ColumnHandler(object):
  """Default column handler.

  This handler can be used on any model attribute that can accept normal text
  value.
  """

  # pylint: disable=too-many-instance-attributes

  # special marker to set the field empty
  EXPLICIT_EMPTY_VALUE = {"-", "--", "---"}

  def __init__(self, row_converter, key, **options):
    self.row_converter = row_converter
    self.key = key
    self.value = None
    self.set_empty = False
    self.is_duplicate = False
    self.raw_value = options.get("raw_value", "").strip()
    self.validator = options.get("validator")
    self.mandatory = options.get("mandatory", False)
    self.view_only = options.get("view_only", False)
    self.default = options.get("default")
    self.description = options.get("description", "")
    self.display_name = options.get("display_name", "")
    self.dry_run = row_converter.block_converter.converter.dry_run
    self.new_objects = self.row_converter.block_converter.converter.new_objects
    self.unique = options.get("unique", False)
    self.ignore = False

  def value_explicitly_empty(self, value):
    return value in self.EXPLICIT_EMPTY_VALUE

  def check_unique_consistency(self):
    """Returns true if no object exists with the same unique field."""
    if not self.unique:
      return
    if not self.value:
      return
    if not self.row_converter.obj:
      return
    if self.is_duplicate:
      # a hack to avoid two different errors for the same non-unique cell
      return
    nr_duplicates = self.row_converter.object_class.query.filter(and_(
        getattr(self.row_converter.object_class, self.key) == self.value,
        self.row_converter.object_class.id != self.row_converter.obj.id
    )).count()
    if nr_duplicates > 0:
      self.add_error(
          errors.DUPLICATE_VALUE, column_name=self.key, value=self.value
      )
      self.row_converter.set_ignore()

  def set_value(self):
    "set value for current culumn after parsing"
    self.value = self.parse_item()

  def get_value(self):
    "get value for current column from instance"
    return getattr(self.row_converter.obj, self.key, self.value)

  def add_error(self, template, **kwargs):
    "add error to current row"
    self.row_converter.add_error(template, **kwargs)

  def add_warning(self, template, **kwargs):
    "add warning to current row"
    self.row_converter.add_warning(template, **kwargs)

  def parse_item(self):
    "Parse item default handler"
    return self.raw_value

  def set_obj_attr(self):
    "Set attribute value to object"
    if not self.set_empty and not self.value:
      return
    try:
      if getattr(self.row_converter.obj, self.key, None) != self.value:
        setattr(self.row_converter.obj, self.key, self.value)
    except ValueError as e:
      self.add_error(
          errors.VALIDATION_ERROR,
          column_name=self.display_name,
          message=e.message
      )
    except Exception as e:  # pylint: disable=bare-except
      self.add_error(errors.UNKNOWN_ERROR)
      logger.exception(
          "Import failed with setattr(%r, %r, %r)",
          self.row_converter.obj,
          self.key,
          self.value,
      )

  def get_default(self):
    "Get default value to column"
    if callable(self.default):
      return self.default()
    return self.default

  def insert_object(self):
    """ For inserting fields such as custom attributes and mappings """
    pass


class DeleteColumnHandler(ColumnHandler):
  """Column handler for deleting objects."""

  # this is a white list of objects that can be deleted in a cascade
  # e.g. deleting a Market can delete the associated Relationship object too
  DELETE_WHITELIST = {"Relationship", "AccessControlList", "ObjectPerson"}
  ALLOWED_VALUES = {"", "no", "false", "true", "yes", "force"}
  TRUE_VALUES = {"true", "yes", "force"}

  def __init__(self, *args, **kwargs):
    self._allow_cascade = False
    super(DeleteColumnHandler, self).__init__(*args, **kwargs)

  def get_value(self):
    return ""

  def parse_item(self):
    if self.raw_value:
      self.add_error(
          u"Line {line}: Delete column is temporary disabled, please use web "
          u"interface to delete current object."
      )
      return None
    if self.raw_value.lower() not in self.ALLOWED_VALUES:
      self.add_error(errors.WRONG_VALUE_ERROR, column_name=self.display_name)
      return False
    is_delete = self.raw_value.lower() in self.TRUE_VALUES
    if is_delete and isinstance(self.row_converter.obj, all_models.Metric):
      if settings.GGRC_Q_INTEGRATION_URL:
        self.add_warning(
            errors.DEPRECATED_DELETED_METRIC_STATUS,
            object_type=self.row_converter.obj.__class__.__name__,
            object_title=self.row_converter.obj.title,
            ggrc_q_link=settings.GGRC_Q_INTEGRATION_URL,
            action_status="deletion",
        )
    self._allow_cascade = self.raw_value.lower() == "force"
    self.row_converter.is_delete = is_delete
    return is_delete

  def set_obj_attr(self):
    if not self.value:
      return
    obj = self.row_converter.obj
    if self.row_converter.is_new:
      self.add_error(
          errors.DELETE_NEW_OBJECT_ERROR, object_type=obj.type, slug=obj.slug
      )
      return
    if self.row_converter.ignore:
      return
    tr = db.session.begin_nested()
    try:
      tr.session.delete(obj)
      deleted = len(
          [
              o for o in tr.session.deleted
              if o.type not in self.DELETE_WHITELIST
          ]
      )
      if deleted > 1 and not self._allow_cascade:
        self.add_error(
            errors.DELETE_CASCADE_ERROR, object_type=obj.type, slug=obj.slug
        )
    finally:
      if self.dry_run or self.row_converter.ignore:
        tr.rollback()
      else:
        indexer = self.row_converter.block_converter.converter.indexer
        if indexer is not None:
          for o in tr.session.deleted:
            indexer.delete_record(o.id, o.__class__.__name__, commit=False)
        tr.commit()


class StatusColumnHandler(ColumnHandler):
  """Handle for Status attribute."""

  def __init__(self, row_converter, key, **options):
    self.key = key
    self.valid_states = row_converter.object_class.VALID_STATES
    self.state_mappings = {str(s).lower(): s for s in self.valid_states}
    super(StatusColumnHandler, self).__init__(row_converter, key, **options)

  def parse_item(self):
    value = self.raw_value.lower()
    status = self.state_mappings.get(value)
    if status is not None:
      if status == "Deprecated" and isinstance(
          self.row_converter.obj, all_models.Metric
      ):
        if settings.GGRC_Q_INTEGRATION_URL:
          self.add_warning(
              errors.DEPRECATED_DELETED_METRIC_STATUS,
              object_type=self.row_converter.obj.__class__.__name__,
              object_title=self.row_converter.obj.title,
              ggrc_q_link=settings.GGRC_Q_INTEGRATION_URL,
              action_status="deprecation",
          )
      return status
    if self.row_converter.obj.status:
      status = self.row_converter.obj.status
      error_tmpl = errors.WRONG_VALUE_CURRENT
    else:
      status = self.row_converter.object_class.default_status()
      error_tmpl = errors.WRONG_VALUE_DEFAULT
    self.add_warning(error_tmpl, column_name=self.display_name)
    return status


class UserColumnHandler(PersonColumnHandlerMixin, ColumnHandler):
  """Handler for a single user fields.

  Used for primary and secondary contacts.
  """

  def get_users_list(self):
    users = set()
    email_lines = self.raw_value.splitlines()
    owner_emails = filter(unicode.strip, email_lines)  # noqa
    for raw_line in owner_emails:
      email = raw_line.strip().lower()
      person = self.get_person(email)
      if person:
        users.add(person)
      else:
        self.add_warning(errors.UNKNOWN_USER_WARNING, email=email)
    return list(users)

  def get_person(self, email):
    new_objects = self.row_converter.block_converter.converter.new_objects
    if email not in new_objects[all_models.Person]:
      people_cache = self.row_converter.block_converter.people_cache
      new_objects[all_models.Person][email] = people_cache.get(email)
    return new_objects[all_models.Person].get(email)

  def _parse_emails(self, email_list):
    """Parse user email. If it were multiply emails in this column parse them.

    We use next rules:
      - Return first valid user.
      - If this field is mandatory and there were no emails provided
        MISSING_VALUE error occurs.
      - If field is mandatory and there were no valid users NO_VALID_USERS
        error occurs.
      - If field isn't mandatory and there were no valid users UNKNOWN_USER
        warning occurs for each invalid email.
    """
    person = None

    for email in email_list:
      person = self.get_person(email)
      if person:
        break
    if self.mandatory:
      if not email_list:
        self.add_error(
            errors.MISSING_VALUE_ERROR, column_name=self.display_name
        )
      elif not person:
        self.add_error(
            errors.NO_VALID_USERS_ERROR, column_name=self.display_name
        )
    else:
      if email_list and not person:
        for email in email_list:
          self.add_warning(errors.UNKNOWN_USER_WARNING, email=email)

    return person

  def parse_item(self):
    people_errors = self.row_converter.block_converter.gather_people_errors(
        row_idx=self.row_converter.idx, attr_name=self.key
    )
    if people_errors:
      for template, kwargs in people_errors:
        self.add_error(template, **kwargs)
      return None

    email_list = self.get_people_emails_from_value(self.raw_value)

    if len(email_list) > 1:
      self.add_warning(
          errors.MULTIPLE_ASSIGNEES, column_name=self.display_name
      )

    return self._parse_emails(email_list)

  def get_value(self):
    person = getattr(self.row_converter.obj, self.key)
    if person:
      return person.email
    return self.value


class UsersColumnHandler(UserColumnHandler):
  """Handler for multi user fields."""

  def _missed_mandatory_person(self):
    """Create response for missing mandatory field"""
    self.add_warning(errors.OWNER_MISSING, column_name=self.display_name)
    return [get_current_user()]

  def parse_item(self):
    """Parses multi users field."""
    people_errors = self.row_converter.block_converter.gather_people_errors(
        row_idx=self.row_converter.idx, attr_name=self.key
    )
    if people_errors:
      for template, kwargs in people_errors:
        self.add_error(template, **kwargs)

    people = set()
    if self.value_explicitly_empty(self.raw_value):
      if not self.mandatory:
        self.set_empty = True
        return None
      return self._missed_mandatory_person()

    email_lines = self.raw_value.splitlines()
    owner_emails = filter(unicode.strip, email_lines)  # noqa
    for raw_line in owner_emails:
      email = raw_line.strip().lower()
      person = self.get_person(email)
      if person:
        people.add(person)
      else:
        self.add_warning(errors.UNKNOWN_USER_WARNING, email=email)

    if not people and self.mandatory:
      return self._missed_mandatory_person()

    return list(people)


class DateColumnHandler(ColumnHandler):
  """Handler for fields that contains date."""

  def parse_item(self):
    if self.view_only:
      self._check_errors_non_importable_objects(
          self.get_value(), self.raw_value
      )
      return
    value = self.raw_value
    if value and not re.match(
        r"[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}|"
        r"[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}", self.raw_value
    ):
      self.add_error(errors.UNKNOWN_DATE_FORMAT, column_name=self.display_name)
      return

    # TODO: change all importable date columns' type from 'DateTime'
    # to 'Date' type. Remove if statement after it.
    try:
      value = value or self.get_value()
      if not value:
        if self.mandatory:
          self.add_error(errors.MISSING_VALUE_ERROR,
                         column_name=self.display_name)
        return None

      parsed_value = parse(value)
      if isinstance(getattr(self.row_converter.obj, self.key, None), date):
        parsed_value = parsed_value.date()
      if self.key in ("last_assessment_date", "verified_date") and \
         self.check_readonly_changes(parsed_value, self.key):
        return None
      return parsed_value
    except:  # pylint: disable=bare-except
      self.add_error(errors.WRONG_VALUE_ERROR, column_name=self.display_name)

  def _check_errors_non_importable_objects(self, object_date, import_date):
    """Check whether a warning should be ejected"""
    if not import_date:
      return

    if object_date:
      try:
        import_date = datetime.strptime(import_date, "%Y-%m-%d")
      except ValueError:
        try:
          import_date = datetime.strptime(import_date, "%m/%d/%Y")
        except ValueError:
          self.add_warning(
              errors.EXPORT_ONLY_WARNING, column_name=self.display_name
          )
          return

      object_date = datetime.strptime(object_date, '%m/%d/%Y')

      if object_date == import_date:
        return
    self.add_warning(errors.EXPORT_ONLY_WARNING, column_name=self.display_name)

  def get_value(self):
    value = getattr(self.row_converter.obj, self.key)
    if value:
      return value.strftime("%m/%d/%Y")
    return ""

  def check_readonly_changes(self, new_date, attr_name):
    """Check if the new object don't contain changed date."""
    old_date = getattr(self.row_converter.obj, attr_name, None)
    is_modified = old_date and new_date and old_date != new_date
    if is_modified:
      self.add_warning(errors.UNMODIFIABLE_COLUMN,
                       column_name=self.display_name,)
      return True
    return False


class NullableDateColumnHandler(DateColumnHandler):
  """Nullable date column handler."""

  DEFAULT_EMPTY_VALUE = "--"

  def parse_item(self):
    """Datetime column can be nullable."""
    if not self.value_explicitly_empty(self.raw_value) and \
            self.raw_value != "":
      return super(NullableDateColumnHandler, self).parse_item()
    if self.mandatory:
      self.add_error(
          errors.MISSING_COLUMN, s="", column_names=self.display_name
      )
    else:
      self.set_empty = True

  def get_value(self):
    if getattr(self.row_converter.obj, self.key):
      return super(NullableDateColumnHandler, self).get_value()
    return self.DEFAULT_EMPTY_VALUE


class EmailColumnHandler(ColumnHandler):
  """Handler for Email attribute."""

  def parse_item(self):
    """ emails are case insensitive """
    email = self.raw_value.lower()
    if not email:
      self.add_error(errors.MISSING_VALUE_ERROR, column_name="Email")
    elif not all_models.Person.is_valid_email(email):
      self.add_error(errors.WRONG_VALUE_ERROR, column_name=self.display_name)
      return ""
    return email


class TextColumnHandler(ColumnHandler):
  """Single line text field handler."""

  def parse_item(self):
    """Remove multiple spaces and new lines from text."""
    value = self.raw_value or ""
    value = self.clean_whitespaces(value)

    if self.mandatory and not value:
      self.add_error(errors.MISSING_VALUE_ERROR, column_name=self.display_name)

    return value

  @staticmethod
  def clean_whitespaces(value):
    return re.sub(r'\s+', " ", value)


class RichTextColumnHandler(TextColumnHandler):
  """Multiline text handler for rich text fields."""

  def parse_item(self):
    """
    Replace newline chars with <p></p> tags.

    Remove multiple spaces and new lines from text.
    """
    value = self.raw_value or ""
    lines = value.splitlines()
    value = "".join(["<p>{}</p>".format(l) for l in lines])
    value = self.clean_whitespaces(value)

    if self.mandatory and not value:
      self.add_error(errors.MISSING_VALUE_ERROR, column_name=self.display_name)

    return value

  def get_value(self):
    """Replace <br> and <p></p> tags with newline char."""
    value = getattr(self.row_converter.obj, self.key, self.value)
    lines = re.sub("<p>|<br>", "", value).split("</p>")
    value = "".join("{}\n".format(l) for l in lines)
    value = value.replace("\n\n", "\n").rstrip("\n")

    return value


class MappingColumnHandler(ColumnHandler):
  """ Handler for mapped objects """

  def __init__(self, row_converter, key, **options):
    self.key = key
    exportable = get_exportables()
    self.attr_name = options.get("attr_name", "")
    self.mapping_object = exportable.get(self.attr_name)
    self.new_slugs = row_converter.block_converter.converter.new_objects[
        self.mapping_object
    ]
    self.unmap = self.key.startswith(AttributeInfo.UNMAPPING_PREFIX)
    super(MappingColumnHandler, self).__init__(row_converter, key, **options)

  def parse_item(self):
    """Parse a list of slugs to be mapped.

    Parse a new line separated list of slugs and check if they are valid
    objects.

    Returns:
      list of objects. During dry_run, the list can contain a slug instead of
      an actual object if that object will be generated in the current import.
    """
    # pylint: disable=protected-access
    class_ = self.mapping_object
    lines = set(self.raw_value.splitlines())
    slugs = set([slug.lower() for slug in lines if slug.strip()])
    objects = []

    for slug in slugs:
      obj = class_.query.filter_by(slug=slug).first()

      if obj:
        is_allowed_by_type = self._is_allowed_mapping_by_type(
            source_type=self.row_converter.obj.__class__.__name__,
            destination_type=class_.__name__,
        )
        if not is_allowed_by_type:
          self._add_mapping_warning(
              source=self.row_converter.obj,
              destination=obj,
          )
          continue
        if not permissions.is_allowed_update_for(obj):
          self.add_warning(
              errors.MAPPING_PERMISSION_ERROR,
              object_type=class_._inflector.human_singular.title(),
              slug=slug,
          )
          continue
        if isinstance(self.row_converter.obj, WithCustomRestrictions):
          if self.row_converter.obj.is_mapping_restricted(obj):
            self.add_error(
                errors.MAPPING_PERMISSION_ERROR,
                object_type=class_._inflector.human_singular.title(),
                slug=slug,
            )
            continue
        objects.append(obj)
      elif slug in self.new_slugs and not self.dry_run:
        objects.append(self.new_slugs[slug])
      elif slug in self.new_slugs and self.dry_run:
        objects.append(slug)
      else:
        self.add_warning(
            errors.UNKNOWN_OBJECT,
            object_type=class_._inflector.human_singular.title(),
            slug=slug
        )
    if self.mandatory and not objects and self.row_converter.is_new:
      self.add_error(errors.MISSING_VALUE_ERROR, column_name=self.display_name)
    return objects

  def _is_allowed_mapping_by_type(self, source_type, destination_type):
    # pylint: disable=no-self-use
    """Checks if a mapping is allowed between given types."""
    try:
      all_models.Relationship.validate_relation_by_type(source_type,
                                                        destination_type)
    except ValidationError:
      return False

    return True

  def _add_mapping_warning(self, source, destination):
    """Add warning if we have changes mappings """
    mapping = all_models.Relationship.find_related(source, destination)

    src_object_type = source.__class__.__name__
    dest_object_type = destination.__class__.__name__
    mapping_error = None
    _SCOPING_MODELS = [scope_model.__name__
                       for scope_model in all_models.get_scope_models()]

    if (src_object_type in _SCOPING_MODELS and
       dest_object_type in ["Control", "Risk", "Regulation", "Standard"]):
      mapping_error = errors.MAP_UNMAP_SCOPE_ERROR
    elif (src_object_type == "Regulation" and
          dest_object_type in ["Control", "Risk"] + _SCOPING_MODELS):
      mapping_error = errors.MAP_UNMAP_REGULATION_ERROR
    elif (src_object_type == "Standard" and
          dest_object_type in ["Control", "Risk"] + _SCOPING_MODELS):
      mapping_error = errors.MAP_UNMAP_STANDARD_ERROR
    else:
      mapping_error = errors.MAP_UNMAP_SCOPE_ERROR

    if (self.unmap and mapping) or (not self.unmap and not mapping):
      self.add_warning(
          mapping_error,
          object_type=dest_object_type,
          action="unmap" if self.unmap else "map"
      )

  def set_obj_attr(self):
    self.value = self.parse_item()

  def insert_object(self):
    """ Create a new mapping object """
    if self.dry_run or not self.value:
      return
    current_obj = self.row_converter.obj
    relationships = []
    mapping = None
    for obj in self.value:
      if current_obj.id:
        mapping = all_models.Relationship.find_related(current_obj, obj)
      if not self.unmap and not mapping:
        if not (
            self.mapping_object.__name__ == "Audit" and
            not getattr(current_obj, "allow_map_to_audit", True)
        ):
          mapping = all_models.Relationship(source=current_obj,
                                            destination=obj)
          signals.Import.mapping_created.send(obj.__class__,
                                              instance=obj,
                                              counterparty=current_obj)
          signals.Import.mapping_created.send(current_obj.__class__,
                                              instance=current_obj,
                                              counterparty=obj)
          relationships.append(mapping)
          db.session.add(mapping)
        else:
          self.add_warning(
              errors.SINGLE_AUDIT_RESTRICTION,
              mapped_type=obj.type,
              object_type=current_obj.type
          )
      elif self.unmap and mapping:
        if not (
            self.mapping_object.__name__ == "Audit" and
            not getattr(current_obj, "allow_unmap_from_audit", True)
        ):
          db.session.delete(mapping)
        else:
          self.add_warning(
              errors.UNMAP_AUDIT_RESTRICTION,
              mapped_type=obj.type,
              object_type=current_obj.type
          )
    db.session.flush()
    self.dry_run = True

  def get_value(self):
    if self.unmap or not self.mapping_object:
      return ""
    cache = self.row_converter.block_converter.get_mapping_cache()
    slugs = cache[self.row_converter.obj.id][self.mapping_object.__name__]
    return "\n".join(slugs)

  def set_value(self):
    pass


class ConclusionColumnHandler(ColumnHandler):
  """ Handler for design and operationally columns in ControlAssesments """

  CONCLUSION_MAP = {i.lower(): i
                    for i in all_models.Assessment.VALID_CONCLUSIONS}

  def parse_item(self):
    """Parse conclusion design and operational values."""

    value = self.CONCLUSION_MAP.get(self.raw_value.lower(), "")
    if self.raw_value and not value:
      self.add_warning(errors.WRONG_VALUE, column_name=self.display_name)
    return value


class OptionColumnHandler(ColumnHandler):
  """Column handler for option fields.

  This column handler is used only for option fields that have their values
  stored in the Options table. Hardcoded options and boolean options should
  not be handled by this class.
  """

  def parse_item(self):
    if not self.mandatory and self.value_explicitly_empty(self.raw_value):
      self.set_empty = True
      return None
    prefixed_key = "{}_{}".format(
        self.row_converter.object_class._inflector.table_singular, self.key
    )
    item = all_models.Option.query.filter(
        and_(
            all_models.Option.title == self.raw_value,
            or_(all_models.Option.role == self.key,
                all_models.Option.role == prefixed_key)
        )
    ).first()
    return item

  def get_value(self):
    option = getattr(self.row_converter.obj, self.key, None)
    if option is None:
      return "--"
    if callable(option.title):
      return option.title()
    return option.title


class ParentColumnHandler(ColumnHandler):
  """ handler for directly mapped columns """

  parent = None

  def parse_item(self):
    """ get parent object """
    # pylint: disable=protected-access
    if self.raw_value == "":
      self.add_error(errors.MISSING_VALUE_ERROR, column_name=self.display_name)
      return None
    slug = self.raw_value
    obj = self.new_objects.get(self.parent, {}).get(slug)
    if obj is None:
      obj = self.parent.query.filter(self.parent.slug == slug).first()
    if obj is None:
      self.add_error(
          errors.UNKNOWN_OBJECT,
          object_type=self.parent._inflector.human_singular.title(),
          slug=slug
      )
      return None
    context_id = None
    if hasattr(obj, "context_id") and \
       hasattr(self.row_converter.obj, "context_id"):
      context_id = obj.context_id
      if context_id is not None:
        name = self.row_converter.obj.__class__.__name__
        if not permissions.is_allowed_create(name, None, context_id) \
           and not permissions.has_conditions('create', name):
          self.add_error(
              errors.MAPPING_PERMISSION_ERROR, object_type=obj.type, slug=slug
          )
          return None
    return obj

  def set_obj_attr(self):
    super(ParentColumnHandler, self).set_obj_attr()
    # inherit context
    obj = self.row_converter.obj
    parent = getattr(obj, self.key, None)
    if parent is not None and \
       hasattr(obj, "context") and \
       hasattr(parent, "context") and \
       parent.context is not None:
      obj.context = parent.context

  def get_value(self):
    value = getattr(self.row_converter.obj, self.key, self.value)
    if not value:
      return None
    return value.slug


class ProgramColumnHandler(ParentColumnHandler):
  """Handler for program column on audit imports."""

  parent = all_models.Program

  def set_obj_attr(self):
    if self.row_converter.is_new:
      super(ProgramColumnHandler, self).set_obj_attr()
    else:
      owned_program_id = self.row_converter.obj.program_id
      given_program_id = self.value.id
      if owned_program_id != given_program_id:
        self.add_warning(errors.UNMODIFIABLE_COLUMN,
                         column_name=self.display_name)


class RequirementDirectiveColumnHandler(MappingColumnHandler):

  def get_directive_from_slug(self, directive_class, slug):
    if slug in self.new_objects[directive_class]:
      return self.new_objects[directive_class][slug]
    return directive_class.query.filter_by(slug=slug).first()

  def parse_item(self):
    """ get a directive from slug """
    allowed_directives = [all_models.Policy, all_models.Regulation,
                          all_models.Standard, all_models.Contract]
    if self.raw_value == "":
      return None
    slug = self.raw_value
    for directive_class in allowed_directives:
      directive = self.get_directive_from_slug(directive_class, slug)
      if directive is not None:
        self.mapping_object = type(directive)
        return [directive]
    self.add_error(errors.UNKNOWN_OBJECT, object_type="Program", slug=slug)
    return None

  def get_value(self):
    # Legacy field. With the new mapping system it is not possible to determine
    # which was the primary directive that has been mapped
    return ""


class AuditColumnHandler(MappingColumnHandler):
  """Handler for mandatory Audit mappings on Assessments."""

  def __init__(self, row_converter, key, **options):
    key = "{}audit".format(MAPPING_PREFIX)
    super(AuditColumnHandler, self).__init__(row_converter, key, **options)

  def set_obj_attr(self):
    """Set values to be saved.

    This saves the value for creating the relationships, and if the dry_run
    flag is not set, it will also set the correct context to the parent object.
    """
    self.value = self.parse_item()
    if not self.value:
      # If there is no mandatory value, the parse item will already mark the
      # error, so there is no need to do anything here.
      return

    audit = self.value[0]

    if isinstance(audit, all_models.Audit):
      old_slug = None
      if (
          hasattr(self.row_converter.obj, "audit") and
          self.row_converter.obj.audit
      ):
        old_slug = self.row_converter.obj.audit.slug
      else:
        rel_audits = self.row_converter.obj.related_objects(_types="Audit")
        if rel_audits:
          old_slug = rel_audits.pop().slug
      if not self.row_converter.is_new and audit.slug != old_slug:
        self.add_warning(
            errors.UNMODIFIABLE_COLUMN, column_name=self.display_name
        )
        self.value = []
      else:
        self.row_converter.obj.context = audit.context
        self.row_converter.obj.audit = audit


class ObjectPersonColumnHandler(UserColumnHandler):
  """
  ObjectPerson handler for all specific columns such as "owner" or any other
  role. This handler will remove all people not listed in the value and will
  add people that are missing.
  """

  def parse_item(self):
    return self.get_users_list()

  def set_obj_attr(self):
    pass

  def get_value(self):
    object_person = db.session.query(
        all_models.ObjectPerson.person_id,
    ).filter_by(
        personable_id=self.row_converter.obj.id,
        personable_type=self.row_converter.obj.__class__.__name__
    )
    users = all_models.Person.query.filter(
        all_models.Person.id.in_(object_person),
    )
    emails = [user.email for user in users]
    return "\n".join(emails)

  def remove_current_people(self):
    all_models.ObjectPerson.query.filter_by(
        personable_id=self.row_converter.obj.id,
        personable_type=self.row_converter.obj.__class__.__name__
    ).delete()

  def insert_object(self):
    if self.dry_run or not self.value:
      return
    self.remove_current_people()
    for person in self.value:
      object_person = all_models.ObjectPerson(
          personable=self.row_converter.obj,
          person=person,
          context=self.row_converter.obj.context
      )
      db.session.add(object_person)
      db.session.flush()
    self.dry_run = True


class PersonMappingColumnHandler(ObjectPersonColumnHandler):
  """
  This handler will only add people listed in self.value if they are not yet
  connected to the current object.
  """

  def remove_current_people(self):
    obj = self.row_converter.obj
    self.value = [
        person for person in self.value
        if not all_models.ObjectPerson.query.filter_by(
            personable_id=obj.id,
            personable_type=obj.__class__.__name__,
            person=person
        ).count()
    ]


class PersonUnmappingColumnHandler(ObjectPersonColumnHandler):
  """
  This handler will only remove people listed in self.value if they are already
  connected to the current object.
  """

  def insert_object(self):
    if self.dry_run or not self.value:
      return
    obj = self.row_converter.obj
    context = getattr(obj, 'context', None)
    user_role = getattr(all_models, 'UserRole', None)
    for person in self.value:
      all_models.ObjectPerson.query.filter_by(
          personable_id=obj.id,
          personable_type=obj.__class__.__name__,
          person=person
      ).delete()
      if context and user_role:
        # The fix is a bit hackish, because it uses ``UserRole`` model
        # from ``ggrc_basic_permissions``. But it is the only way I found to
        # fix the issue, without massive refactoring.
        user_role.query.filter_by(person=person, context=context).delete()
    self.dry_run = True


class DocumentsColumnHandler(ColumnHandler):

  def get_value(self):
    lines = [
        u"{} {}".format(d.title, d.link)
        for d in self.row_converter.obj.documents
    ]
    return u"\n".join(lines)

  def parse_item(self):
    lines = [line.rsplit(" ", 1) for line in self.raw_value.splitlines()]
    documents = []
    for line in lines:
      if len(line) != 2:
        self.add_warning(errors.WRONG_VALUE, column_name=self.display_name)
        continue
      title, link = line
      documents.append(
          all_models.Document(title=title.strip(), link=link.strip())
      )
    return documents

  def set_obj_attr(self):
    pass

  def insert_object(self):
    if self.dry_run or not self.value:
      return
    self.row_converter.obj.documents = self.value
    self.dry_run = True


class LabelsHandler(ColumnHandler):
  """ Handler for labels """

  def parse_item(self):
    if self.raw_value is None:
      return
    names = set(l.strip() for l in self.raw_value.split(',') if l.strip())
    return [{'id': None, 'name': name} for name in names]

  def set_obj_attr(self):
    self.row_converter.obj.labels = self.value

  def get_value(self):
    return ','.join(label.name for label in self.row_converter.obj.labels)


class ExportOnlyColumnHandler(ColumnHandler):
  """Only on export column handler base class"""

  def __init__(self, *args, **kwargs):
    kwargs["view_only"] = True
    kwargs["mandatory"] = False
    super(ExportOnlyColumnHandler, self).__init__(*args, **kwargs)

  def parse_item(self):
    pass

  def set_obj_attr(self):
    pass

  def insert_object(self):
    pass

  def set_value(self):
    pass


class DirecPersonMappingColumnHandler(ExportOnlyColumnHandler):

  def get_value(self):
    person = getattr(self.row_converter.obj, self.key, self.value)
    return getattr(person, "email", "")


class ExportOnlyDateColumnHandler(ExportOnlyColumnHandler):

  def get_value(self):
    value = getattr(self.row_converter.obj, self.key)
    if value:
      return value.strftime("%m/%d/%Y")
    return ""


class ExportOnlyPersonColumnHandler(ExportOnlyColumnHandler):
  """Only on export handler for Person type columns"""
  def get_value(self):
    person = getattr(self.row_converter.obj, self.key, self.value)
    return getattr(person, "email", "")


class ExportOnlyIssueTrackerColumnHandler(ExportOnlyColumnHandler):

  def get_value(self):
    cache = self.row_converter.block_converter.get_ticket_tracker_cache()
    return cache.get(self.row_converter.obj.id, "")


class ReviewableColumnHandler(ExportOnlyColumnHandler):
  """Only on export handler for Reviewable columns"""

  def _validate_item(self):
    """Adds 'ignored message' warnings if new value unequal initial"""
    if self.raw_value and self.raw_value != self.get_value():
      self.add_warning(
          errors.READONLY_WILL_BE_IGNORED,
          column_name=self.display_name
      )

  def set_value(self):
    self._validate_item()


class ReviewersColumnHandler(ReviewableColumnHandler):
  """Only on export handler for Reviewers column"""

  def get_value(self):
    reviewers = self.row_converter.obj.reviewers
    if not reviewers:
      return ''

    return '\n'.join(sorted(
        reviewer.email for reviewer in reviewers
    ))


class JsonListColumnHandler(ColumnHandler):
  """Handler for fields with json list values."""

  def get_value(self):
    json_values = getattr(self.row_converter.obj, self.key, "[]")
    values = []
    try:
      if json_values:
        values = json.loads(json_values)
    except ValueError:
      logger.error(
          "Failed to convert {} field for {} {}".format(
              self.key, self.row_converter.obj.type, self.row_converter.obj.id
          )
      )
    return "\n".join(values)
