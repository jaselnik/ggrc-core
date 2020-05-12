# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Custom attribute definition module"""

import collections
import re

import flask
import sqlalchemy as sa
from sqlalchemy.orm import validates
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.sql.schema import UniqueConstraint
from werkzeug import exceptions

from ggrc import builder
from ggrc import db
from ggrc.access_control import role as acr
from ggrc.cache import memcache
from ggrc.models.revision import Revision
from ggrc.models import (
    mixins,
    reflection,
    deferred,
)
from ggrc.models.exceptions import ValidationError
from ggrc.models.mixins import attributevalidator
from ggrc.models.mixins import base
from ggrc.models.mixins.with_external_mapping import WithExternalMapping
from ggrc.utils import errors
from ggrc.utils import validators


class CustomAttributeDefinitionBase(attributevalidator.AttributeValidator,
                                    base.ContextRBAC,
                                    mixins.Base,
                                    mixins.Titled,
                                    db.Model):
  """CustomAttributeDefinition base class."""
  __abstract__ = True

  class ValidTypes(object):
    """Class representing valid custom attribute definitions.

    Basically an enum, therefore no need for public methods.
    """
    # pylint: disable=too-few-public-methods
    TEXT = "Text"
    RICH_TEXT = "Rich Text"
    DROPDOWN = "Dropdown"
    CHECKBOX = "Checkbox"
    MULTISELECT = "Multiselect"
    DATE = "Date"
    MAP = "Map"

    DEFAULT_VALUE = {
        CHECKBOX: "0",
        MULTISELECT: "",
        RICH_TEXT: "",
        TEXT: "",
        DROPDOWN: "",
        DATE: ""
    }

    DEFAULT_VALUE_MAPPING = {
        CHECKBOX: {
            True: "Yes",
            False: "No",
            "0": "No",
            "1": "Yes",
            "yes": "Yes",
            "no": "No"
        },
    }

  definition_type = db.Column(db.String, nullable=False)
  attribute_type = db.Column(db.String, nullable=False)
  multi_choice_options = db.Column(db.String)
  mandatory = db.Column(db.Boolean, nullable=True, default=False)
  helptext = db.Column(db.String)
  placeholder = db.Column(db.String)
  external_name = db.Column(db.String, nullable=True)

  _sanitize_html = [
      "multi_choice_options",
      "helptext",
      "placeholder",
  ]

  _reserved_names = {}

  @classmethod
  def get_default_value_for(cls, attribute_type):
    return cls.ValidTypes.DEFAULT_VALUE.get(attribute_type)

  @builder.simple_property
  def default_value(self):
    return self.get_default_value_for(self.attribute_type)

  @property
  def value_mapping(self):
    return self.ValidTypes.DEFAULT_VALUE_MAPPING.get(self.attribute_type) or {}

  def get_indexed_value(self, value):
    return self.value_mapping.get(value, value)

  @validates("attribute_type")
  def validate_attribute_type(self, _, value):
    """Check that provided attribute_type is allowed."""
    if value not in self.VALID_TYPES.values():
      raise ValidationError("Invalid attribute_type: got {v}, "
                            "expected one of {l}"
                            .format(v=value,
                                    l=list(self.VALID_TYPES.values())))
    return value

  @validates("multi_choice_options")
  def validate_multi_choice_options(self, _, value):
    """Strip spaces around options in dropdown options."""
    # pylint: disable=no-self-use
    # TODO: this should be "if value is not None" to disallow value == ""
    if value:
      value_list = [part.strip() for part in value.split(",")]
      value_set = set(value_list)
      if len(value_set) != len(value_list):
        raise ValidationError("Duplicate attribute options are not allowed: "
                              "'{}'".format(value))
      if "" in value_set:
        raise ValidationError("Empty attribute options are not allowed: '{}'"
                              .format(value))
      value = ",".join(value_list)

    return value

  @validates("title", "definition_type")
  def validate_title(self, key, value):
    """Validate CAD title/name uniqueness.

    Note: title field is used for storing CAD names.
    CAD names need to follow 6 uniqueness rules:
      1) Names must not match any attribute name on any existing object.
      2) Object level CAD names must not match any global CAD name.
      3) Object level CAD names can clash, but not for the same Object
         instance. This means we can have two CAD with a name "my cad", with
         different attributable_id fields.
      4) Names must not match any existing custom attribute role name
      5) Names should not contains special values (.validate_name_correct)
      6) Names should be stripped

    Third rule is handled by the database with unique key uq_custom_attribute
    (`definition_type`,`definition_id`,`title`).

    This validator should check for name collisions for 1st and 2nd rule.

    This validator works, because definition_type is never changed. It only
    gets set when the cad is created and after that only title filed can
    change. This makes validation using both fields possible.

    Args:
      value: custom attribute definition name

    Returns:
      value if the name passes all uniqueness checks.
    """
    if value:
      value = re.sub(r"\s+", " ", value).strip()
    if not value:
      raise ValueError("Invalid value: {}".format(value))

    if key == "title":
      validators.validate_name_correctness(value)

    if key == "title" and self.definition_type:
      orig_name = value
      definition_type = self.definition_type
    elif key == "definition_type" and self.title:
      orig_name = self.title
      definition_type = value.lower()
    else:
      return value

    name = orig_name.lower()
    if name in self._get_reserved_names(definition_type):
      raise ValueError(
          errors.DUPLICATE_RESERVED_NAME.format(attr_name=orig_name)
      )

    if (self._get_global_cad_names(definition_type).get(name) is not None and
            self._get_global_cad_names(definition_type).get(name) != self.id):
      raise ValueError(errors.DUPLICATE_GCAD_NAME.format(attr_name=orig_name))

    self.assert_acr_exist(orig_name, definition_type)
    if definition_type == "assessment_template":
      self.assert_acr_exist(orig_name, "assessment")

    if definition_type == "assessment":
      self.validate_assessment_title(name)

    return value

  @staticmethod
  def assert_acr_exist(name, definition_type):
    """Validate that there is no ACR with provided name."""
    model_name = get_inflector_model_name_dict()[definition_type]
    acrs = {i.lower() for i in acr.get_custom_roles_for(model_name).values()}
    if name.lower() in acrs:
      raise ValueError(
          errors.DUPLICATE_CUSTOM_ROLE.format(role_name=name)
      )


class CustomAttributeDefinitionFK(object):

  @declared_attr
  def revision_id(cls):  # pylint: disable=no-self-argument
    return deferred.deferred(
        db.Column(
            db.Integer,
            db.ForeignKey('revisions.id', ondelete='SET NULL'),
            nullable=True,
        ),
        'Comment',
    )

  @declared_attr
  def revision(cls):  # pylint: disable=no-self-argument
    return db.relationship(
        'Revision',
        uselist=False,
    )

  @declared_attr
  def custom_attribute_definition_id(cls):  # pylint: disable=no-self-argument
    return deferred.deferred(
        db.Column(
            db.Integer,
            db.ForeignKey(
                'custom_attribute_definitions.id',
                ondelete='SET NULL',
            ),
            nullable=True,
        ),
        cls.__name__,
    )

  @declared_attr
  def custom_attribute_definition(cls):  # pylint: disable=no-self-argument
    return db.relationship(
        'CustomAttributeDefinition',
        uselist=False,
    )

  # REST properties
  _api_attrs = reflection.ApiAttributes(
      "assignee_type",
      reflection.Attribute(
          "custom_attribute_revision",
          create=False,
          update=False,
      ),
      reflection.Attribute(
          "custom_attribute_revision_upd",
          read=False,
      ),
  )

  _aliases = {
      "custom_attribute_definition": "custom_attribute_definition",
  }

  @classmethod
  def eager_query(cls, **kwargs):
    query = super(CustomAttributeDefinitionFK, cls).eager_query(**kwargs)
    return query.options(
        sa.orm.joinedload('revision'),
        sa.orm.joinedload('custom_attribute_definition')
            .undefer_group('CustomAttributeDefinition_complete'),
    )

  def log_json(self):
    """Log custom attribute revisions."""
    res = super(CustomAttributeDefinitionFK, self).log_json()
    res["custom_attribute_revision"] = self.custom_attribute_revision
    return res

  @builder.simple_property
  def custom_attribute_revision(self):
    """Get the historical value of the relevant CA value."""
    if not self.revision:
      return None
    revision = self.revision.content
    cav_stored_value = revision['attribute_value']
    cad = self.custom_attribute_definition
    return {
        'custom_attribute': {
            'id': cad.id if cad else None,
            'title': cad.title if cad else 'DELETED DEFINITION',
        },
        'custom_attribute_stored_value': cav_stored_value,
    }

  def custom_attribute_revision_upd(self, value):
    """Create a Comment-CA mapping with current CA value stored."""
    ca_revision_dict = value.get('custom_attribute_revision_upd')
    if not ca_revision_dict:
      return
    ca_val_dict = self._get_ca_value(ca_revision_dict)

    ca_val_id = ca_val_dict['id']
    ca_val_revision = Revision.query.filter_by(
        resource_type='CustomAttributeValue',
        resource_id=ca_val_id,
    ).order_by(
        Revision.created_at.desc(),
    ).limit(1).first()
    if not ca_val_revision:
      raise exceptions.BadRequest(
          "No Revision found for CA value with id provided under "
          "'custom_attribute_value': {}".format(ca_val_dict),
      )

    self.revision_id = ca_val_revision.id
    self.revision = ca_val_revision

    # Here *attribute*_id is assigned to *definition*_id, strange but,
    # as you can see in src/ggrc/models/custom_attribute_value.py
    # custom_attribute_id is link to custom_attribute_definitions.id
    # possible best way is use definition id from request:
    # ca_revision_dict["custom_attribute_definition"]["id"]
    # but needs to be checked that is always exist in request
    self.custom_attribute_definition_id = ca_val_revision.content.get(
        'custom_attribute_id',
    )

    self.custom_attribute_definition = CustomAttributeDefinition.query.get(
        self.custom_attribute_definition_id,
    )

  @staticmethod
  def _get_ca_value(ca_revision_dict):
    """Get CA value dict from json and do a basic validation."""
    ca_val_dict = ca_revision_dict.get('custom_attribute_value')
    if not ca_val_dict:
      raise ValueError(
          "CA value expected under 'custom_attribute_value': "
          "{}".format(ca_revision_dict),
      )
    if not ca_val_dict.get('id'):
      raise ValueError(
          "CA value id expected under 'id': {}".format(ca_val_dict),
      )
    return ca_val_dict


class CustomAttributeDefinition(WithExternalMapping,
                                CustomAttributeDefinitionBase):
  """Custom attribute definition model."""

  __tablename__ = 'custom_attribute_definitions'

  class MultiChoiceMandatoryFlags(object):
    """Enum representing flags in multi_choice_mandatory bitmaps."""
    # pylint: disable=too-few-public-methods
    DEFAULT = 0b0
    COMMENT_REQUIRED = 0b001
    EVIDENCE_REQUIRED = 0b010
    URL_REQUIRED = 0b100
    IS_NEGATIVE = 0b1000

  VALID_TYPES = {
      "Text": "Text",
      "Rich Text": "Rich Text",
      "Dropdown": "Dropdown",
      "Checkbox": "Checkbox",
      "Multiselect": "Multiselect",
      "Date": "Date",
      "Person": "Map:Person",
  }

  definition_id = db.Column(db.Integer)
  multi_choice_mandatory = db.Column(db.String)
  previous_id = db.Column(db.Integer, nullable=True)

  attribute_values = db.relationship('CustomAttributeValue',
                                     backref='custom_attribute',
                                     cascade='all, delete-orphan')

  _extra_table_args = (
      UniqueConstraint('definition_type',
                       'definition_id',
                       'title',
                       name='uq_custom_attribute'),
      db.Index('ix_custom_attributes_title', 'title'))

  _include_links = [
      'definition_type',
      'definition_id',
      'multi_choice_mandatory',
      'mandatory',
      'helptext',
      'placeholder',
      'external_name',
      'previous_id',
  ]

  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute("default_value",
                           read=True,
                           create=False,
                           update=False),
      reflection.Attribute("title", update=True),
      reflection.Attribute("attribute_type", update=False),
      reflection.Attribute("multi_choice_options", update=True),
      *_include_links)

  @property
  def definition_attr(self):
    return '{0}_definition'.format(self.definition_type)

  @property
  def definition(self):
    return getattr(self, self.definition_attr)

  @definition.setter
  def definition(self, value):
    self.definition_id = getattr(value, 'id', None)
    if hasattr(value, '_inflector'):
      self.definition_type = value._inflector.table_singular
    else:
      self.definition_type = ''
    return setattr(self, self.definition_attr, value)

  @property
  def negative_options(self):
    # type: () -> list
    """Get list of negative options of this CAD.

    Return list of negative options of CAD this property is called on. CAD
    option is considered to be a negative one when it has appropriate bitmask
    in `multi_choice_mandatory` field. This field stores bitmasks for each
    option in comma-separated manner. It means that first bitmask is related to
    first option in `multi_choice_options`, second bitmask to second option and
    so on. Option is negative when binary AND of its bitmask and `IS_NEGATIVE`
    from `MultiChoiceMandatoryFlags` enum evaluates to True.

    Returns:
      List of options that are marked as negative ones.
    """
    if not self.multi_choice_mandatory:
      return []
    bitmasks = self.multi_choice_mandatory.split(",")
    options = self.multi_choice_options.split(",")
    return [
        option for option, bitmask in zip(options, bitmasks)
        if int(bitmask) & self.MultiChoiceMandatoryFlags.IS_NEGATIVE
    ]

  @staticmethod
  def _is_negative_dropdown(cav, negative_options):
    # type: (models.CustomAttributeValue, list) -> bool
    """Check if passed CAV of `Dropdown` type is negative.

    Check if passed CustomAttributeValue object contains value which should be
    considered "negative" on current CustomAttributeDefinition. Note that for
    correct resuls only CAV related to current CAD should be passed here and
    current CAD should be of `Dropdown` type.

    Args:
      cav (models.CustomAttributeValue): CustomAttributeValue instance related
        to current CustomAttributeDefinition.
      negative_options (list): List of strings representing options that are
        marked as "negative" for current CustomAttributeDefinition.

    Returns:
      Boolean flag indicating if CAV's value is negative.
    """
    return cav.attribute_value in negative_options

  @staticmethod
  def _is_negative_text(cav, negative_options):
    # type: (models.CustomAttributeValue, list) -> bool
    """Check if passed CAV of `Text` or `Rich Text` type is negative.

    Check if passed CustomAttributeValue object contains value which should be
    considered "negative" on current CustomAttributeDefinition. Note that for
    correct resuls only CAV related to current CAD should be passed here and
    current CAD should be of `Text` or `Rich Text` type.

    Args:
      cav (models.CustomAttributeValue): CustomAttributeValue instance related
        to current CustomAttributeDefinition.
      negative_options (list): List of strings representing options that are
        marked as "negative" for current CustomAttributeDefinition.

    Returns:
      Boolean flag indicating if CAV's value is negative.
    """
    negative_options = [o.lower() for o in negative_options]
    return "empty" in negative_options and not cav.attribute_value \
        or "not empty" in negative_options and cav.attribute_value

  @staticmethod
  def _is_negative(cav, negative_options):  # pylint: disable=unused-argument
    # type: (models.CustomAttributeValue, list) -> bool
    """Check if passed CAV is negative.

    Check if passed CustomAttributeValue object contains value which should be
    considered "negative" on current CustomAttributeDefinition. Note that this
    is a default implementation and it always returns `False`. For each CAD
    type specific method should be implemented.

    Args:
      cav (models.CustomAttributeValue): CustomAttributeValue instance related
        to current CustomAttributeDefinition.
      negative_options (list): List of strings representing options that are
        marked as "negative" for current CustomAttributeDefinition.

    Returns:
      Boolean flag indicating if CAV's value is negative.
    """
    return False

  def is_value_negative(self, cav):
    # type: (models.CustomAttributeValue) -> bool
    """Check if passed CAV has value marked as negative on current CAD.

    Check if passed CustomAttributeValue `cav` has value which is marked as a
    negative one on the current CustomAttributeDefinition.

    Args:
      cav (models.CustomAttributeValue): CAV which value should be checked.

    Returns:
      Boolean flag indicating if CAV value is negative or not.
    """
    is_negative_validators = collections.defaultdict(lambda: self._is_negative)
    is_negative_validators.update({
        "Dropdown": self._is_negative_dropdown,
        "Rich Text": self._is_negative_text,
        "Text": self._is_negative_text,
    })

    is_negative_validator = is_negative_validators[self.attribute_type]
    return is_negative_validator(cav, self.negative_options)

  def _clone(self, target):
    """Clone custom attribute definitions."""
    data = {
        "title": self.title,
        "definition_type": self.definition_type,
        "definition_id": target.id,
        "context": target.context,
        "attribute_type": self.attribute_type,
        "multi_choice_options": self.multi_choice_options,
        "multi_choice_mandatory": self.multi_choice_mandatory,
        "mandatory": self.mandatory,
        "helptext": self.helptext,
        "placeholder": self.placeholder,
    }
    ca_definition = CustomAttributeDefinition(**data)
    db.session.add(ca_definition)
    return ca_definition

  def log_json(self):
    """Add extra fields to be logged in CADs."""
    results = super(CustomAttributeDefinition, self).log_json()
    results["default_value"] = self.default_value
    return results

  @validates("multi_choice_mandatory")
  def validate_multi_choice_mandatory(self, _, value):
    """Strip spaces around bitmas in dropdown options."""
    # pylint: disable=no-self-use
    if value:
      value = ",".join(part.strip() for part in value.split(","))

    return value

  def validate_assessment_title(self, name):
    """Check assessment title uniqueness.

    Assessment CAD should not match any name from assessment_template.
    Currently assessment templates do not have global custom attributes, but
    in the future global CAD on assessment templates could be applied to all
    generated assessments. That's why we do not differentiate between global
    and local CAD here.

    Args:
      name: Assessment custom attribute definition title.
    Raises:
      ValueError if name is an invalid CAD title.
    """
    if self.definition_id:
      # Local Assessment CAD can match local and global Assessment Template
      # CAD.
      # NOTE: This is not the best way of checking if the current CAD is local,
      # since it relies on the fact that if definition_id will be set, it will
      # be set along with definition_type. If we manually set definition_type
      # then title then definition_id, this check would fail.
      return

    if not getattr(flask.g, "template_cad_names", set()):
      query = db.session.query(self.__class__.title).filter(
          self.__class__.definition_type == "assessment_template"
      )
      flask.g.template_cad_names = {cad.title.lower() for cad in query}

    if name in flask.g.template_cad_names:
      raise ValueError(u"Local custom attribute '{}' "
                       u"already exists for this object type."
                       .format(name))


def init_cad_listeners():
  """Register event listeners for CAD and eCAD models"""

  for action in ("before_insert", "before_update", "before_delete"):
    sa.event.listen(CustomAttributeDefinition,
                    action,
                    validators.validate_definition_type_ecad)
  for action in ("after_insert", "after_update", "after_delete"):
    sa.event.listen(CustomAttributeDefinition,
                    action,
                    attributevalidator.invalidate_gca_cache)


def raise_method_is_not_allowed(*args, **kwargs):
  """Raise MethodNotAllowed exception for use with sa.event.listen"""
  del args, kwargs
  raise exceptions.MethodNotAllowed()


@memcache.cached
def get_inflector_model_name_pairs():
  """Returns pairs with asociation between definition_type and model_name"""
  from ggrc.models import all_models
  return [(m._inflector.table_singular, m.__name__)
          for m in all_models.all_models]


def get_inflector_model_name_dict():
  return dict(get_inflector_model_name_pairs())


@memcache.cached
def get_model_name_inflector_dict():
  return {m: i for i, m in get_inflector_model_name_pairs()}
