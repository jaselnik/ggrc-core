# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test for indexing of snapshotted objects"""

import unittest

import ddt
from sqlalchemy.sql.expression import tuple_

from ggrc import db
from ggrc import models
from ggrc.models import all_models
from ggrc.fulltext.mysql import MysqlRecordProperty as Record
from ggrc.snapshotter import indexer as snapshotter_indexer
from ggrc.snapshotter import rules as snapshotter_rules

from integration.ggrc import api_helper
from integration.ggrc.snapshotter import SnapshotterBaseTestCase
from integration.ggrc.models import factories
from integration.ggrc_workflows.models import factories as wf_factories


def get_records(_audit, _snapshots):
  """Get Record objects related to provided audit and snapshots"""
  return db.session.query(Record).filter(
      tuple_(
          Record.type,
          Record.key,
          Record.property,
          Record.content
      ).in_(
          {("Snapshot", s.id, "parent", "Audit-{}".format(_audit.id))
           for s in _snapshots}
      ))


def get_record_query(key, obj_property, content):
  """Returns Record query"""
  return db.session.query(Record).filter(
      Record.key == key,
      Record.type == "Snapshot",
      Record.property == obj_property,
      Record.content == content
  )


@ddt.ddt
class TestSnapshotIndexing(SnapshotterBaseTestCase):
  """Test cases for Snapshoter module"""

  # pylint: disable=invalid-name,too-many-locals
  def setUp(self):
    super(TestSnapshotIndexing, self).setUp()
    self.api = api_helper.Api()
    self.client.get("/login")
    self.headers = {
        'Content-Type': 'application/json',
        "X-Requested-By": "GGRC",
    }

  @ddt.data(
      *(snapshotter_rules.Types.all - snapshotter_rules.Types.external)
  )
  def test_create_indexing(self, model_name):
    """Test that creating objects results in full index"""
    program = self.create_object(models.Program, {
        "title": "Test Program Snapshot 1"
    })
    object_model = models.get_model(model_name)
    model_object = self.create_object(object_model, {
        "title": "Test Snapshot 1 - {}".format(model_name)
    })

    self.create_mapping(program, model_object)
    self.refresh_object(model_object)

    program = self.refresh_object(program)
    audit = self.create_audit(program)

    snapshots = db.session.query(models.Snapshot).all()
    records = get_records(audit, snapshots)

    self.assertEqual(records.count(), 1)

  @ddt.data(
      *(snapshotter_rules.Types.all - snapshotter_rules.Types.external)
  )
  def test_update_indexing(self, model_name):
    """Test that updating objects results in full index"""
    program = self.create_object(models.Program, {
        "title": "Test Program Snapshot 1"
    })
    object_model = models.get_model(model_name)
    model_object = self.create_object(object_model, {
        "title": "Test Snapshot 1 - {}".format(model_name)
    })
    model_object_id = model_object.id

    self.create_mapping(program, model_object)
    model_object = self.refresh_object(model_object)
    self.api.modify_object(model_object, {
        "title": "Test Snapshot 1 - {} EDIT".format(model_name)
    })

    program = self.refresh_object(program)
    audit = self.create_audit(program)

    # Initiate update operation
    self.api.modify_object(audit, {
        "snapshots": {
            "operation": "upsert"
        }
    })

    snapshots = db.session.query(models.Snapshot).all()
    records = get_records(audit, snapshots)

    self.assertEqual(records.count(), 1)

    snapshot = db.session.query(models.Snapshot).filter(
        models.Snapshot.child_type == model_object.type,
        models.Snapshot.child_id == model_object_id,
    ).one()

    _title = get_record_query(snapshot.id, "title",
                              "Test Snapshot 1 - {} EDIT".format(model_name))
    self.assertEqual(_title.count(), 1)

  @unittest.skip("Deprecated during GGRC-8069 until full_reindex and "
                 "reindex_snapshot haven't work properly")
  @ddt.data(
      *(snapshotter_rules.Types.all - snapshotter_rules.Types.external)
  )
  def test_full_reindex(self, model_name):
    """Test full reindex of all snapshots"""
    object_factory = factories.get_model_factory(model_name)
    with factories.single_commit():
      program = factories.ProgramFactory()
      obj = object_factory()
      factories.RelationshipFactory(source=program, destination=obj)

    program = self.refresh_object(program)
    audit = self.create_audit(program)

    snapshots = db.session.query(models.Snapshot).all()
    records = get_records(audit, snapshots)

    self.assertEqual(records.count(), 1)

    snapshotter_indexer.delete_records({s.id for s in snapshots})
    records = get_records(audit, snapshots)
    self.assertEqual(records.count(), 0)

    self.client.post("/admin/full_reindex")
    records = get_records(audit, snapshots)
    self.assertEqual(records.count(), 1)

  def assert_indexed_fields(self, obj, search_property, values):
    """Assert index content in full text search table."""
    all_found_records = dict(Record.query.filter(
        Record.key == obj.id,
        Record.type == obj.type,
        Record.property == search_property.lower(),
    ).values("subproperty", "content"))
    for field, value in values.iteritems():
      self.assertIn(field, all_found_records)
      self.assertEqual(value, all_found_records[field])

  @unittest.skip("Deprecated during GGRC-8069 until full_reindex and "
                 "reindex_snapshot haven't work properly")
  @ddt.data(
      ("principal_assessor", "Principal Assignees"),
      ("secondary_assessor", "Secondary Assignees"),
      ("contact", "Control Operators"),
      ("secondary_contact", "Control Owners"),
  )
  @ddt.unpack
  def test_search_no_acl_in_content(self, field, role_name):
    """Test search older revisions without access_control_list."""
    with factories.single_commit():
      person = factories.PersonFactory(email="{}@example.com".format(field),
                                       name=field)
      control = factories.ControlFactory()
    revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == control.id,
        all_models.Revision.resource_type == control.type,
    ).one()
    with factories.single_commit():
      snapshot = factories.SnapshotFactory(
          child_id=control.id,
          child_type=control.type,
          revision=revision)
      old_content = revision.content.copy()
      old_content.pop("access_control_list")
      old_content[field] = {"id": person.id}
      revision.content = old_content
      db.session.add(revision)
    person_id = person.id
    snapshot_id = snapshot.id

    self.client.post("/admin/full_reindex")
    person = all_models.Person.query.get(person_id)
    snapshot = all_models.Snapshot.query.get(snapshot_id)
    self.assert_indexed_fields(snapshot, role_name, {
        "{}-email".format(person.id): person.email,
        "{}-name".format(person.id): person.name,
        "__sort__": person.email,
    })

  @unittest.skip("Deprecated during GGRC-8069 until full_reindex and "
                 "reindex_snapshot haven't work properly")
  def test_index_by_acr(self):
    """Test index by ACR."""
    role_name = "Test name"
    factories.AccessControlRoleFactory(name=role_name, object_type="Control")
    with factories.single_commit():
      person = factories.PersonFactory(email="test@example.com", name='test')
      control = factories.ControlFactory()
      factories.AccessControlPersonFactory(
          ac_list=control.acr_name_acl_map[role_name],
          person=person,
      )
    revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == control.id,
        all_models.Revision.resource_type == control.type,
    ).one()
    revision.content = control.log_json()
    db.session.add(revision)
    with factories.single_commit():
      snapshot = factories.SnapshotFactory(
          child_id=control.id,
          child_type=control.type,
          revision=revision)
    db.session.expire_all()
    person_id = person.id
    snapshot_id = snapshot.id
    self.client.post("/admin/full_reindex")
    person = all_models.Person.query.get(person_id)
    snapshot = all_models.Snapshot.query.get(snapshot_id)
    self.assert_indexed_fields(snapshot, role_name, {
        "{}-email".format(person.id): person.email,
        "{}-name".format(person.id): person.name,
        "__sort__": person.email,
    })

  @unittest.skip("Deprecated during GGRC-8069 until full_reindex and "
                 "reindex_snapshot haven't work properly")
  @ddt.data(
      (True, "Yes"),
      (False, "No"),
      ("1", "Yes"),
      ("0", "No"),
      (1, "Yes"),
      (0, "No"),
  )
  @ddt.unpack
  def test_filter_by_checkbox_cad(self, value, search_value):
    """Test index by Checkdoxed cad {0} value and search_value {1}."""
    checkbox_type = all_models.CustomAttributeDefinition.ValidTypes.CHECKBOX
    cad_title = "Checkbox"
    with factories.single_commit():
      cad = factories.CustomAttributeDefinitionFactory(
          attribute_type=checkbox_type,
          definition_type="objective",
          title=cad_title,
      )
      objective = factories.ObjectiveFactory()
      factories.CustomAttributeValueFactory(
          custom_attribute=cad,
          attributable=objective,
          attribute_value=value,
      )
    revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == objective.id,
        all_models.Revision.resource_type == objective.type,
    ).first()
    revision.content = objective.log_json()
    db.session.add(revision)
    with factories.single_commit():
      snapshot = factories.SnapshotFactory(
          child_id=objective.id,
          child_type=objective.type,
          revision=revision)
    db.session.expire_all()
    snapshot_id = snapshot.id
    self.client.post("/admin/full_reindex")
    snapshot = all_models.Snapshot.query.get(snapshot_id)
    self.assert_indexed_fields(snapshot, cad_title, {"": search_value})

  @unittest.skip("Deprecated during GGRC-8069 until full_reindex and "
                 "reindex_snapshot haven't work properly")
  def test_filter_by_checkbox_cad_no_cav(self):
    """Test index by Checkdoxed cad no cav."""
    checkbox_type = all_models.CustomAttributeDefinition.ValidTypes.CHECKBOX
    cad_title = "Checkbox"
    search_value = "No"
    with factories.single_commit():
      factories.CustomAttributeDefinitionFactory(
          attribute_type=checkbox_type,
          definition_type="objective",
          title=cad_title,
      )
      objective = factories.ObjectiveFactory()
    revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == objective.id,
        all_models.Revision.resource_type == objective.type,
    ).first()
    revision.content = objective.log_json()
    db.session.add(revision)
    with factories.single_commit():
      snapshot = factories.SnapshotFactory(
          child_id=objective.id,
          child_type=objective.type,
          revision=revision)
    db.session.expire_all()
    snapshot_id = snapshot.id
    self.client.post("/admin/full_reindex")
    snapshot = all_models.Snapshot.query.get(snapshot_id)
    self.assert_indexed_fields(snapshot, cad_title, {"": search_value})

  @ddt.data(
      (True, "Yes"),
      (False, "No"),
      ("1", "Yes"),
      ("0", "No"),
      (1, "Yes"),
      (0, "No"),
  )
  @ddt.unpack
  def test_filter_by_needs_verification(self, value, search_value):
    """Test index by needs verification {0} value and search_value {1}."""
    workflow = wf_factories.WorkflowFactory(is_verification_needed=value)
    cycle = wf_factories.CycleFactory(workflow=workflow,
                                      is_verification_needed=value)
    task = wf_factories.CycleTaskGroupObjectTaskFactory(
        cycle=cycle,
        title="test_index_{0}_{1}".format(value, search_value)
    )
    self.assert_indexed_fields(task, "needs verification",
                               {"": search_value})

  def test_index_deleted_acr(self):
    """Test index by removed ACR."""
    role_name = "Test name"
    acr = factories.AccessControlRoleFactory(
        name=role_name,
        object_type="Control",
    )
    with factories.single_commit():
      person = factories.PersonFactory(email="test@example.com", name='test')
      control = factories.ControlFactory()
      factories.AccessControlPersonFactory(
          ac_list=control.acr_name_acl_map[role_name],
          person=person,
      )
    revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == control.id,
        all_models.Revision.resource_type == control.type,
    ).one()
    revision.content = control.log_json()
    db.session.add(revision)
    with factories.single_commit():
      snapshot = factories.SnapshotFactory(
          child_id=control.id,
          child_type=control.type,
          revision=revision)
    db.session.expire_all()
    db.session.delete(acr)
    db.session.commit()
    snapshot_id = snapshot.id
    self.client.post("/admin/reindex")
    snapshot = all_models.Snapshot.query.get(snapshot_id)
    all_found_records = dict(Record.query.filter(
        Record.key == snapshot.id,
        Record.type == snapshot.type,
        Record.property == role_name.lower()
    ).values("subproperty", "content"))
    self.assertFalse(all_found_records)

  def test_no_reindex_acr_for_same_obj(self):
    """Test that reindex records appear if
    acl is populated with current obj's role."""
    system_role_name = "Admin"
    with factories.single_commit():
      person = factories.PersonFactory(name="Test Name")
      system = factories.SystemFactory()
      audit = factories.AuditFactory()
      factories.AccessControlPersonFactory(
          ac_list=system.acr_name_acl_map[system_role_name],
          person=person,
      )
      person_id = person.id
      person_name = person.name
      person_email = person.email
    revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == system.id,
        all_models.Revision.resource_type == system.type
    ).one()
    revision.content = system.log_json()
    db.session.add(revision)
    db.session.commit()
    self._create_snapshots(audit, [system])
    self.assert_indexed_fields(system, system_role_name, {
        "{}-email".format(person_id): person_email,
        "{}-name".format(person_id): person_name,
        "__sort__": person_email,
    })

  @unittest.skip("Deprecated during GGRC-8069 until full_reindex and "
                 "reindex_snapshot haven't work properly")
  def test_acl_no_reindex_snapshots(self):
    """Test that snapshot reindex is not happened for
    acl where person has the same role for
    different kind of objects."""
    with factories.single_commit():
      person = factories.PersonFactory(name="Test Name")
      system = factories.SystemFactory()
      audit = factories.AuditFactory()
      factories.AccessControlPersonFactory(
          ac_list=system.acr_name_acl_map["Admin"],
          person=person,
      )
      audit_id = audit.id
      system_id = system.id
      person_id = person.id
      person_name = person.name
      person_email = person.email
    revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == system.id,
        all_models.Revision.resource_type == system.type
    ).one()
    revision.content = system.log_json()
    db.session.add(revision)
    db.session.commit()
    self._create_snapshots(audit, [system])
    self.client.post("/admin/reindex_snapshots")
    snapshot = all_models.Snapshot.query.filter(
        all_models.Snapshot.parent_id == audit_id,
        all_models.Snapshot.parent_type == 'Audit',
        all_models.Snapshot.child_id == system_id,
        all_models.Snapshot.child_type == 'System',
    ).one()
    self.assert_indexed_fields(snapshot, "Admin", {
        "{}-email".format(person_id): person_email,
        "{}-name".format(person_id): person_name,
        "__sort__": person_email,
    })

  @unittest.skip("Deprecated during GGRC-8069 until full_reindex and "
                 "reindex_snapshot haven't work properly")
  def test_reindex_snapshots_option_without_title(self):
    """Test that reindex processed successfully.

    Reindex processed successfully with Option
    without 'title' attribute.
    """
    with factories.single_commit():
      product = factories.ProductFactory()
      audit = factories.AuditFactory()
      option = factories.OptionFactory()
      audit_id = audit.id
      product_id = product.id
      option_title = option.title
    revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == product.id,
        all_models.Revision.resource_type == product.type
    ).one()
    revision_content = revision.content
    revision_content["kind"] = {
        "context_id": "null",
        "href": "/api/options/{}".format(option.id),
        "type": "Option",
        "id": option.id
    }
    revision.content = revision_content
    db.session.add(revision)
    db.session.commit()
    self._create_snapshots(audit, [product])
    self.client.post("/admin/reindex_snapshots")
    snapshot = all_models.Snapshot.query.filter(
        all_models.Snapshot.parent_id == audit_id,
        all_models.Snapshot.parent_type == "Audit",
        all_models.Snapshot.child_id == product_id,
        all_models.Snapshot.child_type == "Product",
    ).one()
    self.assert_indexed_fields(snapshot, "kind", {
        "": option_title
    })

  @ddt.data("/admin/reindex_snapshots", "/admin/full_reindex")
  def test_deprecated_endpoints(self, endpoint):
    """Test that deprecated {0} have a correct response."""
    response = self.client.post(endpoint)
    self.assert405(response)
    expected_description = "Endpoint is deprecated. " \
                           "Please consider using '/admin/reindex' instead."
    self.assertIn(expected_description, response.data)
