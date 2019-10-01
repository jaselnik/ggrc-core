# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Defines a Revision model for storing snapshots."""
import json

import flask

from ggrc import builder
from ggrc import db
from ggrc import utils
from ggrc.access_control import role
from ggrc.models import automapping
from ggrc.models import mixins
from ggrc.models import reflection
from ggrc.models import types
from ggrc.models.mixins import base
from ggrc.models.mixins import before_flush_handleable
from ggrc.models.mixins import filterable
from ggrc.models.mixins import synchronizable
from ggrc.models.mixins import with_readonly_access as wroa
from ggrc.utils import referenced_objects
from ggrc.utils.revisions_diff import builder as revisions_diff
from ggrc.utils.revisions_diff import meta_info


class Revision(before_flush_handleable.BeforeFlushHandleable,
               synchronizable.ChangesSynchronized,
               filterable.Filterable,
               base.ContextRBAC,
               mixins.Base,
               db.Model):
  """Revision object holds a JSON snapshot of the object at a time."""
  # pylint: disable=too-many-public-methods

  __tablename__ = 'revisions'

  resource_id = db.Column(db.Integer, nullable=False)
  resource_type = db.Column(db.String, nullable=False)
  event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
  action = db.Column(db.Enum(u'created', u'modified', u'deleted'),
                     nullable=False)
  _content = db.Column('content', types.LongJsonType, nullable=False)

  resource_slug = db.Column(db.String, nullable=True)
  source_type = db.Column(db.String, nullable=True)
  source_id = db.Column(db.Integer, nullable=True)
  destination_type = db.Column(db.String, nullable=True)
  destination_id = db.Column(db.Integer, nullable=True)

  is_empty = db.Column(db.Boolean, nullable=False, default=False)

  @staticmethod
  def _extra_table_args(_):
    return (
        db.Index("revisions_modified_by", "modified_by_id"),
        db.Index("ix_revisions_resource_action",
                 "resource_type",
                 "resource_id",
                 "action"),
        db.Index("fk_revisions_source", "source_type", "source_id"),
        db.Index("fk_revisions_destination",
                 "destination_type", "destination_id"),
        db.Index('ix_revisions_resource_slug', 'resource_slug'),
    )

  _api_attrs = reflection.ApiAttributes(
      'resource_id',
      'resource_type',
      'source_type',
      'source_id',
      'destination_type',
      'destination_id',
      'action',
      'content',
      'description',
      reflection.Attribute('diff_with_current', create=False, update=False),
      reflection.Attribute('meta', create=False, update=False),
  )

  _filterable_attrs = [
      'action',
      'resource_id',
      'resource_type',
      'source_type',
      'source_id',
      'destination_type',
      'destination_id',
  ]

  @classmethod
  def eager_query(cls, **kwargs):
    from sqlalchemy import orm

    query = super(Revision, cls).eager_query(**kwargs)
    return query.options(
        orm.subqueryload('modified_by'),
        # Event's action is loaded here since it is used in description.
        orm.joinedload('event').load_only('action'),
    )

  def __init__(self, obj, modified_by_id, action, content):
    self.resource_id = obj.id
    self.resource_type = obj.__class__.__name__
    self.resource_slug = getattr(obj, "slug", None)
    self.modified_by_id = modified_by_id
    self.action = action
    if "access_control_list" in content and content["access_control_list"]:
      for acl in content["access_control_list"]:
        acl["person"] = {
            "id": acl["person_id"],
            "type": "Person",
            "href": "/api/people/{}".format(acl["person_id"]),
        }

    self._content = content

    for attr in ["source_type",
                 "source_id",
                 "destination_type",
                 "destination_id"]:
      setattr(self, attr, getattr(obj, attr, None))

  @builder.callable_property
  def diff_with_current(self):
    """Callable lazy property for revision."""
    referenced_objects.mark_to_cache(self.resource_type, self.resource_id)
    revisions_diff.mark_for_latest_content(self.resource_type,
                                           self.resource_id)

    def lazy_loader():
      """Lazy load diff for revisions."""
      referenced_objects.rewarm_cache()
      revisions_diff.rewarm_latest_content()
      instance = referenced_objects.get(self.resource_type, self.resource_id)
      if instance:
        return revisions_diff.prepare(instance, self.content)
      # return empty diff object has already been removed
      return {}

    return lazy_loader

  @builder.callable_property
  def meta(self):
    """Callable lazy property for revision."""
    referenced_objects.mark_to_cache(self.resource_type, self.resource_id)

    def lazy_loader():
      """Lazy load diff for revisions."""
      referenced_objects.rewarm_cache()
      instance = referenced_objects.get(self.resource_type, self.resource_id)
      meta_dict = {}
      if instance:
        instance_meta_info = meta_info.MetaInfo(instance)
        meta_dict["mandatory"] = instance_meta_info.mandatory
      return meta_dict

    return lazy_loader

  @builder.simple_property
  def description(self):
    """Compute a human readable description from action and content."""
    if 'display_name' not in self._content:
      return ''
    display_name = self._content['display_name']
    if not display_name:
      result = u"{0} {1}".format(self.resource_type, self.action)
    elif u'<->' in display_name:
      if self.action == 'created':
        msg = u"{destination} linked to {source}"
      elif self.action == 'deleted':
        msg = u"{destination} unlinked from {source}"
      else:
        msg = u"{display_name} {action}"
      source, destination = self._content['display_name'].split('<->')[:2]
      result = msg.format(source=source,
                          destination=destination,
                          display_name=self._content['display_name'],
                          action=self.action)
    elif 'mapped_directive' in self._content:
      # then this is a special case of combined map/creation
      # should happen only for Requirement and Control
      mapped_directive = self._content['mapped_directive']
      if self.action == 'created':
        result = u"New {0}, {1}, created and mapped to {2}".format(
            self.resource_type,
            display_name,
            mapped_directive
        )
      elif self.action == 'deleted':
        result = u"{0} unmapped from {1} and deleted".format(
            display_name, mapped_directive)
      else:
        result = u"{0} {1}".format(display_name, self.action)
    else:
      # otherwise, it's a normal creation event
      result = u"{0} {1}".format(display_name, self.action)
    if self.event.action == "BULK":
      result += ", via bulk action"
    return result

  def populate_reference_url(self):
    """Add reference_url info for older revisions."""
    if 'url' not in self._content:
      return {}
    reference_url_list = []
    for key in ('url', 'reference_url'):
      link = self._content[key]
      # link might exist, but can be an empty string - we treat those values
      # as non-existing (empty) reference URLs
      if not link:
        continue

      # if creation/modification date is not available, we estimate it by
      # using the corresponding information from the Revision itself
      created_at = (self._content.get("created_at") or
                    self.created_at.isoformat())
      updated_at = (self._content.get("updated_at") or
                    self.updated_at.isoformat())

      reference_url_list.append({
          "display_name": link,
          "kind": "REFERENCE_URL",
          "link": link,
          "title": link,
          "id": None,
          "created_at": created_at,
          "updated_at": updated_at,
      })
    return {'reference_url': reference_url_list}

  @classmethod
  def _filter_internal_acls(cls, access_control_list):
    """Remove internal access control list entries.

    This is needed due to bugs in older code that in some cases the revisions
    stored internal ACL entries.
    Due to possible role removal, the parent_id is the only true flag that we
    can use for filtering

    Args:
      access_control_list: list of dicts containing ACL entries.

    Returns:
      access_control_list but without any ACL entry that was generated from
        some other ACL entry.
    """
    return [
        acl for acl in access_control_list
        if acl.get("parent_id") is None
    ]

  @classmethod
  def _populate_acl_with_people(cls, access_control_list):
    """Add person property with person stub on access control list."""
    for acl in access_control_list:
      if "person" not in acl:
        acl["person"] = {"id": acl.get("person_id"), "type": "Person"}
    return access_control_list

  def populate_acl(self):
    """Add access_control_list info for older revisions."""
    # pylint: disable=too-many-locals
    roles_dict = role.get_custom_roles_for(self.resource_type)
    reverted_roles_dict = {n: i for i, n in roles_dict.iteritems()}
    access_control_list = self._content.get("access_control_list") or []
    map_field_to_role = {
        "principal_assessor": reverted_roles_dict.get("Principal Assignees"),
        "secondary_assessor": reverted_roles_dict.get("Secondary Assignees"),
        "contact": reverted_roles_dict.get("Primary Contacts"),
        "secondary_contact": reverted_roles_dict.get("Secondary Contacts"),
        "owners": reverted_roles_dict.get("Admin"),
    }

    is_control = bool(self.resource_type == "Control")
    is_control_snapshot = bool(self.resource_type == "Snapshot" and
                               self._content["child_type"] == "Control")
    # for Control type we do not have Primary and Secondary Contacts roles.
    if is_control or is_control_snapshot:
      map_field_to_role.update({
          "contact": reverted_roles_dict.get("Control Operators"),
          "secondary_contact": reverted_roles_dict.get("Control Owners")
      })

    exists_roles = {i["ac_role_id"] for i in access_control_list}

    for field, role_id in map_field_to_role.items():
      if role_id in exists_roles or role_id is None:
        continue
      if field not in self._content:
        continue
      field_content = self._content.get(field) or {}
      if not field_content:
        continue
      if not isinstance(field_content, list):
        field_content = [field_content]
      person_ids = {fc.get("id") for fc in field_content if fc.get("id")}
      for person_id in person_ids:
        access_control_list.append({
            "display_name": roles_dict[role_id],
            "ac_role_id": role_id,
            "context_id": None,
            "created_at": None,
            "object_type": self.resource_type,
            "updated_at": None,
            "object_id": self.resource_id,
            "modified_by_id": None,
            "person_id": person_id,
            # Frontend require data in such format
            "person": {
                "id": person_id,
                "type": "Person",
                "href": "/api/people/{}".format(person_id)
            },
            "modified_by": None,
            "id": None,
        })

    acl_with_people = self._populate_acl_with_people(access_control_list)
    filtered_acl = self._filter_internal_acls(acl_with_people)
    result_acl = [
        acl for acl in filtered_acl if acl["ac_role_id"] in roles_dict
    ]
    return {
        "access_control_list": result_acl,
    }

  def populate_folder(self):
    """Add folder info for older revisions."""
    if "folder" in self._content:
      return {}
    folders = self._content.get("folders") or [{"id": ""}]
    return {"folder": folders[0]["id"]}

  def populate_labels(self):
    """Add labels info for older revisions."""
    if "label" not in self._content:
      return {}
    label = self._content["label"]
    return {"labels": [{"id": None,
                        "name": label}]} if label else {"labels": []}

  def populate_status(self):
    """Update status for older revisions or add it if status does not exist."""
    workflow_models = {
        "Cycle",
        "CycleTaskGroup",
        "CycleTaskGroupObjectTask",
    }
    statuses_mapping = {
        "InProgress": "In Progress"
    }
    status = statuses_mapping.get(self._content.get("status"))
    if self.resource_type in workflow_models and status:
      return {"status": status}

    pop_models = {
        # ggrc
        "AccessGroup",
        "AccountBalance",
        "Control",
        "DataAsset",
        "Directive",
        "Facility",
        "Issue",
        "KeyReport",
        "Market",
        "Objective",
        "OrgGroup",
        "Product",
        "Program",
        "Project",
        "Requirement",
        "System",
        "Vendor",
        "Risk",
        "Threat",
    }
    if self.resource_type not in pop_models:
      return {}
    statuses_mapping = {
        "Active": "Active",
        "Deprecated": "Deprecated",
        "Effective": "Active",
        "Final": "Active",
        "In Scope": "Active",
        "Ineffective": "Active",
        "Launched": "Active",
    }
    return {"status": statuses_mapping.get(self._content.get("status"),
                                           "Draft")}

  def populate_review_status(self):
    """Replace os_state with review state for old revisions"""
    from ggrc.models import review
    result = {}
    if "os_state" in self._content:
      if self._content["os_state"] is not None:
        result["review_status"] = self._content["os_state"]
      else:
        result["review_status"] = review.Review.STATES.UNREVIEWED
    return result

  def populate_review_status_display_name(self, result):
    """Get review_status if review_status_display_name is not found"""
    # pylint: disable=invalid-name

    if self.resource_type in ("Control", "Risk"):
      if "review_status_display_name" in self._content:
        result["review_status_display_name"] = self._content[
            "review_status_display_name"]
      elif "review_status" in result:
        result["review_status_display_name"] = result["review_status"]

  def populate_readonly(self):
    """Add readonly=False to older revisions of WithReadOnlyAccess models"""

    from ggrc.models import all_models

    model = getattr(all_models, self.resource_type, None)
    if not model or not issubclass(model, wroa.WithReadOnlyAccess):
      return dict()

    if "readonly" in self._content:
      # revision has flag "readonly", use it
      return {"readonly": self._content["readonly"]}

    # not flag "readonly" in revision, use default value False
    return {"readonly": False}

  def _document_evidence_hack(self):
    """Update display_name on evideces

    Evidences have display names from links and titles, and until now they used
    slug property to calculate the display name. This hack is here since we
    must support older revisions with bad data, and to avoid using slug
    differently than everywhere else in the app.

    This function only modifies existing evidence entries on any given object.
    If an object does not have and document evidences then an empty dict is
    returned.

    Returns:
      dict with updated display name for each of the evidence entries if there
      are any.
    """
    if "document_evidence" not in self._content:
      return {}
    document_evidence = self._content.get("document_evidence")
    for evidence in document_evidence:
      evidence[u"display_name"] = u"{link} {title}".format(
          link=evidence.get("link"),
          title=evidence.get("title"),
      ).strip()
    return {u"documents_file": document_evidence}

  def populate_categoies(self, key_name):
    """Return names of categories."""
    if self.resource_type != "Control":
      return {}
    result = []
    categories = self._content.get(key_name)
    if isinstance(categories, (str, unicode)) and categories:
      result = json.loads(categories)
    elif isinstance(categories, list):
      for category in categories:
        if isinstance(category, dict):
          result.append(category.get("name"))
        elif isinstance(category, (str, unicode)):
          result.append(category)

    return {key_name: result}

  def _get_cavs(self):
    """Return cavs values from content."""
    if "custom_attribute_values" in self._content:
      return self._content["custom_attribute_values"]
    if "custom_attributes" in self._content:
      return self._content["custom_attributes"]
    return []

  def _get_cads(self):
    """Return cads definitions from content and new CADs from db."""
    if "custom_attribute_definitions" in self._content:
      return self._content["custom_attribute_definitions"]
    return []

  def populate_cavs(self):
    """Setup cads in cav list if they are not presented in content

    but now they are associated to instance."""
    cads = self._get_cads()
    cavs = {int(i["custom_attribute_id"]): i for i in self._get_cavs()}
    cads_ids = set()
    for cad in cads:
      custom_attribute_id = int(cad["id"])
      cads_ids.add(custom_attribute_id)
      if custom_attribute_id in cavs:
        # Old revisions can contain falsy values for a Checkbox
        if cad["attribute_type"] == "Checkbox" \
                and not cavs[custom_attribute_id]["attribute_value"]:
          cavs[custom_attribute_id]["attribute_value"] = cad["default_value"]
        continue
      if cad["attribute_type"] == "Map:Person":
        value = "Person"
      else:
        value = cad["default_value"]
      cavs[custom_attribute_id] = {
          "attribute_value": value,
          "custom_attribute_id": custom_attribute_id,
          "attributable_id": self.resource_id,
          "attributable_type": self.resource_type,
          "display_name": "",
          "attribute_object": None,
          "type": "CustomAttributeValue",
          "context_id": None,
      }

    cavs = {cad_id: value for cad_id, value in cavs.iteritems()
            if cad_id in cads_ids}

    return {"custom_attribute_values": cavs.values(),
            "custom_attribute_definitions": cads}

  def populate_cad_default_values(self):
    """Setup default_value to CADs if it's needed."""
    from ggrc.models import all_models
    if "custom_attribute_definitions" not in self._content:
      return {}
    cads = []
    for cad in self._content["custom_attribute_definitions"]:
      if "default_value" not in cad:
        cad["default_value"] = (
            all_models.CustomAttributeDefinition.get_default_value_for(
                cad["attribute_type"]
            )
        )
      cads.append(cad)
    return {"custom_attribute_definitions": cads}

  def populate_requirements(self, populated_content):  # noqa pylint: disable=too-many-branches
    """Populates revision content for Requirement models and models with fields

    that can contain Requirement old names. This fields would be checked and
    updated where necessary
    """
    # change to add Requirement old names
    requirement_type = ["Section", "Clause"]
    # change to add models and fields that can contain Requirement old names
    affected_models = {
        "AccessControlList": ["object_type", ],
        "AccessControlRole": ["object_type", ],
        "Assessment": ["assessment_type", ],
        "AssessmentTemplate": ["template_object_type", ],
        "Automapping": ["source_type", "destination_type", ],
        "CustomAttributeValue": ["attributable_type", ],
        "ExternalCustomAttributeValue": ["attributable_type", ],
        "Event": ["resource_type", ],
        "ObjectPerson": ["personable_type", ],
        "Relationship": ["source_type", "destination_type", ],
        "Revision": ["resource_type", ],
        "Label": ["object_type", ],
        "Context": ["related_object_type", ],
        "IssuetrackerIssue": ["object_type", ],
        "ObjectLabel": ["object_type", ],
        "ObjectTemplates": ["name", ],
        "Proposal": ["instance_type", ],
        "Snapshot": ["child_type", "parent_type", ],
    }
    # change to add special values cases
    special_cases = {
        "CustomAttributeDefinition": {
            "fields": ["definition_type", ],
            "old_values": ["section", "clause"],
            "new_value": "requirement",
        }
    }

    obj_type = self.resource_type

    # populate fields if they contain old names
    if obj_type in affected_models.keys():
      for field in affected_models[obj_type]:
        if populated_content.get(field) in requirement_type:
          populated_content[field] = "Requirement"

    # populate fields for models that contain old names in special spelling
    if obj_type in special_cases.keys():
      for field in special_cases[obj_type]["fields"]:
        if populated_content[field] in special_cases[obj_type]["old_values"]:
          populated_content[field] = special_cases[obj_type]["new_value"]

    # populate Requirements revisions
    if obj_type == "Requirement":
      populated_content["type"] = "Requirement"

      acls = populated_content.get("access_control_list", {})
      if acls:
        for acl in acls:
          if acl.get("object_type") in requirement_type:
            acl["object_type"] = "Requirement"
        populated_content["access_control_list"] = acls

      cavs = populated_content.get("custom_attribute_values", {})
      if cavs:
        for cav in cavs:
          if cav.get("attributable_type") in requirement_type:
            cav["attributable_type"] = "Requirement"
        populated_content["custom_attribute_values"] = cavs

  def populate_options(self, populated_content):
    """Update revisions for Sync models to have Option fields as string."""
    if self.resource_type == "Control":
      for attr in ["kind", "means", "verify_frequency"]:
        attr_value = populated_content.get(attr)
        if isinstance(attr_value, dict):
          populated_content[attr] = attr_value.get("title")
        elif isinstance(attr_value, (str, unicode)):
          populated_content[attr] = attr_value
        else:
          populated_content[attr] = None

  def populate_automappings(self):
    """Add automapping info in revisions.

    Populate Relationship revisions with automapping info to help FE
    show Change Log, but we should not show automapping info
    in case of deleted relationship"""
    if ("automapping_id" not in self._content or
            not self._content["automapping_id"] or
            self.action != "created"):
      return {}
    automapping_id = self._content["automapping_id"]
    if not hasattr(flask.g, "automappings_cache"):
      flask.g.automappings_cache = dict()
    if automapping_id not in flask.g.automappings_cache:
      automapping_obj = automapping.Automapping.query.get(automapping_id)
      if automapping_obj is None:
        return {}
      automapping_json = automapping_obj.log_json()
      flask.g.automappings_cache[automapping_id] = automapping_json
    else:
      automapping_json = flask.g.automappings_cache[automapping_id]
    return {"automapping": automapping_json}

  def populate_type(self):
    """Add object_types field to content were need it
    Early created revisions didn't have type field
    in content data, but we should either add it here from
    resource_type field.
    """

    if "type" not in self._content:
      return {"type": self.resource_type}
    return {}

  @builder.simple_property
  def content(self):
    """Property. Contains the revision content dict.

    Updated by required values, generated from saved content dict."""
    # pylint: disable=too-many-locals
    populated_content = self._content.copy()
    populated_content.update(self.populate_acl())
    populated_content.update(self.populate_reference_url())
    populated_content.update(self.populate_folder())
    populated_content.update(self.populate_labels())
    populated_content.update(self.populate_status())
    populated_content.update(self.populate_review_status())
    populated_content.update(self._document_evidence_hack())
    populated_content.update(self.populate_categoies("categories"))
    populated_content.update(self.populate_categoies("assertions"))
    populated_content.update(self.populate_cad_default_values())
    populated_content.update(self.populate_cavs())
    populated_content.update(self.populate_readonly())
    populated_content.update(self.populate_automappings())
    populated_content.update(self.populate_type())

    self.populate_requirements(populated_content)
    self.populate_options(populated_content)
    self.populate_review_status_display_name(populated_content)
    # remove custom_attributes,
    # it's old style interface and now it's not needed
    populated_content.pop("custom_attributes", None)
    # remove attribute_object_id not used by FE anymore
    for item in populated_content["custom_attribute_values"]:
      item.pop("attribute_object_id", None)
    return populated_content

  @content.setter
  def content(self, value):
    """ Setter for content property."""
    self._content = value

  def _handle_if_empty(self):
    """Check if revision is empty and update is_empty flag if true."""

    # Check if new revision contains any changes in resource state. Revisions
    # created with "created" or "deleted" action are not considered empty.
    if self in db.session.new and self.action == u"modified":
      obj = referenced_objects.get(self.resource_type, self.resource_id)
      # Content serialization and deserialization is needed since content of
      # prev revision stored in DB was serialized before storing and due to
      # this couldn't be correctly compared to content of revision in hands.
      content = json.loads(utils.as_json(self.content))
      self.is_empty = bool(
          obj and not revisions_diff.changes_present(obj, content))

  def handle_before_flush(self):
    """Handler that called  before SQLAlchemy flush event."""
    self._handle_if_empty()
