# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Utilties to deal with introspecting GGRC models for publishing, creation,
and update from resource format representations, such as JSON."""
import bisect
from collections import defaultdict

import flask
from sqlalchemy.sql.schema import UniqueConstraint

from ggrc.utils import rules
from ggrc.utils import title_from_camelcase
from ggrc.utils import underscore_from_camelcase


EXCLUDE_CUSTOM_ATTRIBUTES = set([
    "AssessmentTemplate",
])

EXCLUDE_MAPPINGS = set([
    "AssessmentTemplate",
])


def is_filter_only(alias_properties):
  """Determine if alias is for filter use only.

  Prevents alias filters from being exportable.

  Args:
    alias_properties: Alias properties.
  Returns:
    Boolean reflecting if it's filter only or not.
  """
  if isinstance(alias_properties, dict):
    if alias_properties.get("filter_only"):
      return True
  return False


# pylint: disable=too-few-public-methods
class Attribute(object):
  """Class to define api attribute with allowed actions with that attribute."""

  __slots__ = ["attr", "create", "update", "read"]

  def __init__(self, attr, create=True, update=True, read=True):
    self.attr = attr
    self.create = create
    self.update = update
    self.read = read


# pylint: disable=too-few-public-methods
class SerializableAttribute(Attribute):
  """Base attribute class with serializer."""

  # pylint: disable=unused-argument,no-self-use
  def deserialize(self, value):
    """Deserialize json respresentation to internal value."""
    raise NotImplementedError


# pylint: disable=too-few-public-methods
class ExternalUserAttribute(SerializableAttribute):
  """Attribute class for deserialization of external user."""

  def __init__(self, attr, force_create=False, **kwargs):
    super(ExternalUserAttribute, self).__init__(attr, **kwargs)

    self.force_create = force_create

  def deserialize(self, value):
    """Deserialize json representation to Person object.

    Creates non existing person if force_create attribute is True.
    """
    from ggrc.utils import user_generator

    if value.get("email"):
      email = value.get("email")
      name = value.get("name")
      if self.force_create:
        return user_generator.find_or_create_external_user(email, name)
      return user_generator.find_user_by_email(email)
    elif value.get("id"):
      return user_generator.find_user_by_id(value["id"])
    else:
      raise ValueError("Provided data are incorrect.")


class HybridAttribute(Attribute):
  """Class for attributes which are hybrid_properties on models."""

  __slots__ = ["hybrid"]

  def __init__(self, attr, create=True, update=True, read=True):
    super(HybridAttribute, self).__init__(
        attr, create=create, update=update, read=read
    )
    self.hybrid = True


class ApiAttributes(dict):
  """Class to collect all required api attributes."""

  def __init__(self, *attrs):
    super(ApiAttributes, self).__init__()
    self.add(*attrs)

  def add(self, *attrs):
    """Append attrs.

    Attrs is the list of strings/unicodes or instances of Attribute class.
    """
    for attr in attrs:
      if isinstance(attr, basestring):
        attr = Attribute(attr)
      self[attr.attr] = attr


class AttributeInfo(object):

  """Gather model CRUD information by reflecting on model classes. Builds and
  caches a list of the publishing properties for a class by walking the
  class inheritance tree.
  """

  MAPPING_PREFIX = "__mapping__:"
  UNMAPPING_PREFIX = "__unmapping__:"
  CUSTOM_ATTR_PREFIX = "__custom__:"
  OBJECT_CUSTOM_ATTR_PREFIX = "__object_custom__:"
  SNAPSHOT_MAPPING_PREFIX = "__snapshot_mapping__:"
  ALIASES_PREFIX = "__acl__"

  ATTRIBUTE_ORDER = (
      "slug",
      "assessment_template",
      "audit",
      "revision_date",
      "control",
      "program",
      "task_group",
      "workflow",
      "title",
      "description",
      'risk_type',
      'threat_source',
      'threat_event',
      'vulnerability',
      "notes",
      "test_plan",
      "owners",
      "task_type",
      "start_date",
      "end_date",
      "last_deprecated_date",
      "due_date",
      "archived",
      "report_start_date",
      "report_end_date",
      "finished_date",
      "verified_date",
      "status",
      "labels",
      "review_status",
      "review_status_display_name",
      "reviewers",
      "assertions",
      "categories",
      "contact",
      "design",
      "directive",
      "fraud_related",
      "key_control",
      "kind",
      "link",
      "means",
      "network_zone",
      "operationally",
      "secondary_contact",
      "assessment_type",
      "verify_frequency",
      "name",
      "email",
      "is_enabled",
      "company",
      "user_role",
      "recipients",
      "send_by_default",
      "evidences_file",
      "evidences_url",
      "documents_file",
      "documents_url",
      "documents_reference_url",
      "notify_custom_message",
      "frequency",
      "notify_on_change",
      "is_verification_needed",
      "updated_at",
      "modified_by",
      "created_at",
      "folder",
      "delete",
      "repeat_every",
      "unit",
      "readonly",
      "created_by",
      "last_submitted_at",
      "last_submitted_by",
      "last_verified_at",
      "last_verified_by",
      ALIASES_PREFIX,
      "comments",
      "last_comment",
      CUSTOM_ATTR_PREFIX,
      OBJECT_CUSTOM_ATTR_PREFIX,
      "issue_tracker",
      "component_id",
      "enabled",
      "hotlist_id",
      "issue_priority",
      "issue_severity",
      "issue_title",
      "issue_type",
      "verification_workflow",
      "review_levels_count",
  )

  class Type(object):
    """Types of model attributes."""
    # TODO: change to enum.
    # pylint: disable=too-few-public-methods
    PROPERTY = "property"
    MAPPING = "mapping"
    AC_ROLE = "mapping"
    SPECIAL_MAPPING = "special_mapping"
    CUSTOM = "custom"  # normal custom attribute
    OBJECT_CUSTOM = "object_custom"  # object level custom attribute
    USER_ROLE = "user_role"

  def __init__(self, tgt_class):
    self._publish_attrs = AttributeInfo.gather_publish_attrs(tgt_class)
    self._update_attrs = AttributeInfo.gather_update_attrs(tgt_class)
    self._create_attrs = AttributeInfo.gather_create_attrs(tgt_class)
    self._include_links = AttributeInfo.gather_include_links(tgt_class)
    self._update_raw = AttributeInfo.gather_update_raw(tgt_class)
    self._aliases = AttributeInfo.gather_aliases(tgt_class)
    self._visible_aliases = AttributeInfo.gather_visible_aliases(tgt_class)

  @classmethod
  def get_attr(cls, tgt_class, src_attr, attr):
    """Get the particular attribute from `tgt_class` or it's base classes."""
    for base in tgt_class.__mro__:
      attrs = getattr(base, src_attr, None) or {}
      if attr in attrs:
        return attrs[attr]
    return None

  @classmethod
  def gather_attr_dicts(cls, tgt_class, src_attr):
    """ Gather dictionaries from target class parents """
    result = {}
    _complete = getattr(tgt_class, src_attr + "_complete", None)
    if _complete:
      result.update(_complete)
    else:
      for base in reversed(tgt_class.__mro__):
        result.update(getattr(base, src_attr, None) or {})
    return result

  @classmethod
  def gather_attrs(cls, tgt_class, src_attr):
    """Gathers the attrs to be included in a list for publishing, update, or
    some other purpose. Supports inheritance by iterating the list of
    ``src_attrs`` until a list is found.
    """
    accumulator = set()
    callable_attrs = set()
    for base in tgt_class.__mro__:
      attrs = getattr(base, src_attr, None)
      if callable(attrs):
        callable_attrs.add(attrs)
      else:
        accumulator = accumulator.union(set(attrs or []))
    for attr in callable_attrs:
      accumulator = accumulator.union(attr(tgt_class))
    return accumulator

  @classmethod
  def gather_publish_attrs(cls, tgt_class):
    return [attr_name for attr_name, attr in
            cls.gather_attr_dicts(tgt_class, "_api_attrs").iteritems()
            if attr.read]

  @classmethod
  def gather_aliases(cls, tgt_class):
    return cls.gather_attr_dicts(tgt_class, '_aliases')

  @classmethod
  def gather_visible_aliases(cls, tgt_class):
    return {
        attr: props for attr, props
        in AttributeInfo.gather_aliases(tgt_class).iteritems()
        if props is not None and not is_filter_only(props)
    }

  @classmethod
  def gather_update_attrs(cls, tgt_class):
    return [attr_name for attr_name, attr in
            cls.gather_attr_dicts(tgt_class, "_api_attrs").iteritems()
            if attr.update]

  @classmethod
  def gather_create_attrs(cls, tgt_class):
    return [attr_name for attr_name, attr in
            cls.gather_attr_dicts(tgt_class, "_api_attrs").iteritems()
            if attr.create]

  @classmethod
  def gather_include_links(cls, tgt_class):
    return cls.gather_attrs(tgt_class, '_include_links')

  @classmethod
  def gather_update_raw(cls, tgt_class):
    return cls.gather_attrs(tgt_class, '_update_raw')

  @classmethod
  def get_acl_definitions(cls, object_class):
    """Return list of ACL dicts."""
    from ggrc.access_control.role import AccessControlRole
    from ggrc import db
    if not hasattr(flask.g, "acl_role_names"):
      flask.g.acl_role_names = defaultdict(set)
      names_query = db.session.query(
          AccessControlRole.object_type,
          AccessControlRole.name,
          AccessControlRole.mandatory,
      ).filter(~AccessControlRole.internal)
      for object_type, name, mandatory in names_query:
        flask.g.acl_role_names[object_type].add((name, mandatory))

    return {
        u"{}:{}".format(cls.ALIASES_PREFIX, name): {
            "display_name": name,
            "attr_name": name,
            "mandatory": mandatory,
            "unique": False,
            "description": u"Multiple values are allowed.\nDelimiter is"
                           u" 'line break'.\nAllowed values are emails",
            "type": cls.Type.AC_ROLE,
        }
        for name, mandatory in flask.g.acl_role_names[object_class.__name__]
    }

  @classmethod
  def _generate_mapping_definition(cls, rules_set, prefix, display_name_tmpl,
                                   read_only_types=None):
    """Generate definition from template"""
    definitions = {}
    from ggrc.snapshotter.rules import Types
    read_only = read_only_types or Types.parents | Types.scoped
    read_only_text = "Read only column and will be ignored on import."
    for klass in rules_set:
      klass_name = title_from_camelcase(klass)
      key = "{}{}".format(prefix, klass_name)
      definitions[key.lower()] = {
          "display_name": display_name_tmpl.format(klass_name),
          "attr_name": klass.lower(),
          "mandatory": False,
          "unique": False,
          "description": read_only_text if klass in read_only else "",
          "type": cls.Type.MAPPING,
      }
    return definitions

  @classmethod
  def get_mapping_definitions(cls, object_class):
    """Get column definitions for allowed (un)mappings for object_class.

    For an Audit-scope object, generates snapshot mappings for all allowed
    mappings with snapshottable objects and direct mappings with all allowed
    mappings with non-snapshottable objects.

    For a normal object, generates direct mappings with all allowed mappings.

    For every direct mapping column generated it also generates an unmapping
    column.
    """

    definitions = {}

    definitions.update(cls._generate_mapping_definition(
        rules.get_mapping_rules().get(object_class.__name__, set()),
        cls.MAPPING_PREFIX, "map:{}",
    ))
    mapping_types = rules.get_snapshot_mapping_rules().get(
        object_class.__name__, set())
    read_only_classes = None
    if object_class.__name__ == "Issue":
      read_only_classes = mapping_types
    definitions.update(cls._generate_mapping_definition(
        mapping_types, cls.SNAPSHOT_MAPPING_PREFIX, "map:{} versions",
        read_only_types=read_only_classes
    ))
    definitions.update(cls._generate_mapping_definition(
        rules.get_unmapping_rules().get(object_class.__name__, set()),
        cls.UNMAPPING_PREFIX, "unmap:{}",
    ))
    return definitions

  @classmethod
  def get_custom_attr_definitions(cls, object_class,
                                  ca_cache=None, fields=None):
    """Get column definitions for custom attributes on object_class.

    Args:
      object_class (db.Model): Model whose attribute definitions to get.
      ca_cache (dict): Dictionary containing custom attribute definitions. If
        it's set this function will not look for CAD in the database. This
        should be used for bulk operations, and eventually replaced with
        memcache.
      fields (iterable): Iterable containing names of custom attribute
        definitions to get. If None, all definitions for passed object class
        will be returned. Defaults to None.

    Returns:
      A dict of custom attribute definitions.
    """
    from ggrc.models import mixins

    definitions = {}
    if not issubclass(object_class, (mixins.CustomAttributable,
                                     mixins.ExternalCustomAttributable)):
      return definitions

    object_name = underscore_from_camelcase(object_class.__name__)
    if isinstance(ca_cache, dict) and object_name:
      custom_attributes = ca_cache.get(object_name, [])
    else:
      custom_attributes = object_class.get_custom_attribute_definitions(fields)
    for attr in custom_attributes:
      description = attr.helptext or u""
      if attr.multi_choice_options:
        if description:
          description += "\n\n"
        description += u"Allowed values are:\n{}".format(
            attr.multi_choice_options.replace(",", "\n")
        )
      elif attr.attribute_type == attr.ValidTypes.CHECKBOX:
        description += u"Allowed values are:\nyes\nno"
      elif attr.ValidTypes.MAP in attr.attribute_type:
        description += u"Allowed values are emails"
      if attr.definition_id:
        ca_type = cls.Type.OBJECT_CUSTOM
        attr_name = u"{}{}".format(
            cls.OBJECT_CUSTOM_ATTR_PREFIX, attr.title).lower()
      else:
        ca_type = cls.Type.CUSTOM
        attr_name = u"{}{}".format(cls.CUSTOM_ATTR_PREFIX, attr.title).lower()

      definition_ids = definitions.get(attr_name, {}).get("definition_ids", [])
      definition_ids.append(attr.id)
      if fields is None or attr.title.lower() in fields:
        definitions[attr_name] = {
            "display_name": attr.title,
            "attr_name": attr.title,
            "mandatory": attr.mandatory,
            "unique": False,
            "description": description,
            "type": ca_type,
            "definition_ids": definition_ids,
        }
    return definitions

  @classmethod
  def get_unique_constraints(cls, object_class):
    """ Return a set of attribute names for single unique columns """
    constraints = object_class.__table__.constraints
    unique = [con for con in constraints if isinstance(con, UniqueConstraint)]
    # we only handle single column unique constraints
    unique_columns = [u.columns.keys() for u in unique if len(u.columns) == 1]
    return set(sum(unique_columns, []))

  # pylint: disable=too-many-arguments,too-many-boolean-expressions
  @classmethod
  def get_object_attr_definitions(cls, object_class, ca_cache=None,
                                  ca_fields=None, include_hidden=False,
                                  for_template=False):
    """Get all column definitions for object_class.

    This function joins custom attribute definitions, mapping definitions and
    the extra delete column. For better performance consider to provide one or
    all of the following arguments: `ca_fields` or `ca_cache`.

    Args:
      object_class (db.Model): Model whose attribute definitions to get.
      ca_cache (dict): Dictionary containing custom attribute definitions
        grouped by their definitions_type. If None, definitions will be queried
        from the DB. Defaults to None.
      ca_fields (iterable): Iterable of custom attribute field names to include
        in returned attribute definitions list. If None, all custom attributes
        will be included. Defaults to None.
      include_hidden (bool): Flag which specifies if we should include
        attribute definition for hidden attributes (they marked as 'hidden'
        in _aliases dict).
      for_template (bool): Flag which specifies if we should exclude column
        handlers for attributes that marked as 'ship_in_template'
        in _aliases dict.

    Returns:
      A dict of attribute definitions.
    """
    definitions = {}

    aliases = AttributeInfo.gather_visible_aliases(object_class).items()

    # push the extra delete column at the end to override any custom behavior
    if hasattr(object_class, "slug"):
      aliases.append(("delete", {
          "display_name": "Delete",
          "description": "Allowed value is:\nYes",
      }))

    unique_columns = cls.get_unique_constraints(object_class)

    for key, value in aliases:
      if (
          not include_hidden and
          isinstance(value, dict) and
          value.get("hidden")
      ) or (
          for_template and
          isinstance(value, dict) and
          value.get("skip_in_template")
      ):
        continue
      column = object_class.__table__.columns.get(key)
      mandatory = False
      if column is not None:
        mandatory = not column.nullable and not column.default
      definition = {
          "display_name": value,
          "attr_name": key,
          "mandatory": mandatory,
          "unique": key in unique_columns,
          "description": "",
          "type": cls.Type.PROPERTY,
          "handler_key": key,
      }
      if isinstance(value, dict):
        definition.update(value)
      definitions[key] = definition

    definitions.update(cls.get_acl_definitions(object_class))
    if object_class.__name__ not in EXCLUDE_CUSTOM_ATTRIBUTES:
      definitions.update(cls.get_custom_attr_definitions(
          object_class, ca_cache=ca_cache, fields=ca_fields
      ))

    if object_class.__name__ not in EXCLUDE_MAPPINGS:
      definitions.update(cls.get_mapping_definitions(object_class))

    return definitions

  @classmethod
  def get_attr_definitions_array(cls, object_class, ca_cache=None):
    """ get all column definitions containing only json serializable data """
    definitions = cls.get_object_attr_definitions(object_class,
                                                  ca_cache=ca_cache,)
    order = cls.get_column_order(definitions.keys())
    result = []
    for key in order:
      item = definitions[key]
      item["key"] = key
      result.append(item)
    return result

  @classmethod
  def _prefixed_attr_key(cls, attr):
    """Construct key for attr started with
    special prefix."""
    return '__%s__' % attr.split('__')[1]

  @classmethod
  def get_column_order(cls, attr_list):
    """ Sort attribute list

    Attribute list should be sorted with 3 rules:
      - attributes in ATTRIBUTE_ORDER variable must be first and in the same
        order as defined in that variable.
      - other attributes except mapping attributes
        are sorted alphabetically after attributes defined in
        ATTRIBUTE ORDER
      - mapping attributes are sorted alphabetically and placed last
    """
    prefixed_attrs = defaultdict(list)
    for attr in attr_list:
      if attr.startswith('__'):
        bisect.insort(prefixed_attrs[cls._prefixed_attr_key(attr)], attr)
    attr_set = set(attr_list)
    ordered_attrs = []
    for attr in cls.ATTRIBUTE_ORDER:
      if attr in attr_set:
        ordered_attrs.append(attr)
      elif attr.startswith("__"):
        ordered_attrs.extend(prefixed_attrs[cls._prefixed_attr_key(attr)])
    ordered_set = set(ordered_attrs)
    other_attrs = [v for v in attr_list if v not in ordered_set]
    other_custom_attrs = [v for v in other_attrs
                          if not v.lower().startswith("map:")]
    mapping_attrs = [v for v in other_attrs if v.lower().startswith("map:")]
    other_custom_attrs.sort(key=lambda x: x.lower())
    mapping_attrs.sort(key=lambda x: x.lower())
    return ordered_attrs + other_custom_attrs + mapping_attrs
