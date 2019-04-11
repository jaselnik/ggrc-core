# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test for indexing of snapshotted objects"""

import ddt

from sqlalchemy.sql.expression import tuple_

from ggrc import db
from ggrc import models
from ggrc.models import all_models
from ggrc.fulltext.mysql import MysqlRecordProperty as Record
from ggrc.snapshotter.indexer import delete_records

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


@ddt.ddt
class TestSnapshotIndexing(SnapshotterBaseTestCase):
  """Test cases for Snapshoter module"""

  # pylint: disable=invalid-name,too-many-locals

  def setUp(self):
    super(TestSnapshotIndexing, self).setUp()

    self.client.get("/login")
    self.headers = {
        'Content-Type': 'application/json',
        "X-Requested-By": "GGRC",
    }

  def test_create_indexing(self):
    """Test that creating objects results in full index"""

    self._check_csv_response(self._import_file("snapshotter_create.csv"), {})

    access_group = db.session.query(models.AccessGroup).filter(
        models.AccessGroup.slug == "ag-2"
    ).one()
    objective = db.session.query(models.Objective).filter(
        models.Objective.slug == "obj-1"
    ).one()
    process = db.session.query(models.Process).filter(
        models.Process.slug == "proc-2"
    ).one()
    custom_attribute_defs = self.create_custom_attribute_definitions()
    custom_attribute_values = [
        {
            "custom_attribute": custom_attribute_defs["objective"],
            "attributable": objective,
            "attribute_value": "objective value 1",
        },
        {
            "custom_attribute": custom_attribute_defs["process"],
            "attributable": process,
            "attribute_value": "07/12/2016",
        },
        {
            "custom_attribute": custom_attribute_defs["access_group"],
            "attributable": access_group,
            "attribute_value": "access_group text value 1",
        },
    ]

    for value in custom_attribute_values:
      factories.CustomAttributeValueFactory(**value)

    # Add custom attribute values via factory doesn't create revisions, so
    # we modify all the objects via import, which saves the full object
    # state in revisions table (including custom attribute values).
    self._check_csv_response(self._import_file("snapshotter_update.csv"), {})

    program = db.session.query(models.Program).filter(
        models.Program.slug == "Prog-13211"
    ).one()

    self.create_audit(program)

    audit = db.session.query(models.Audit).filter(
        models.Audit.title.like("%Snapshotable audit%")).first()

    snapshots = db.session.query(models.Snapshot).all()

    records = db.session.query(Record).filter(
        tuple_(
            Record.type,
            Record.key,
            Record.property,
            Record.content
        ).in_(
            {("Snapshot", s.id, "parent", "Audit-{}".format(audit.id))
             for s in snapshots}
        ))

    self.assertEqual(records.count(), 66)

    # At this point all objects are no longer in the session and we have to
    # manually refresh them from the database
    access_group = db.session.query(models.AccessGroup).filter(
        models.AccessGroup.slug == "ag-2"
    ).one()
    objective = db.session.query(models.Objective).filter(
        models.Objective.slug == "obj-1"
    ).one()
    process = db.session.query(models.Process).filter(
        models.Process.slug == "proc-2"
    ).one()

    custom_attributes = [
        (objective, "objective rich field 1", "objective value 1"),
        (process, "process date field 1", "07/12/2016"),
        (access_group, "access group text field 2",
         "access_group text value 1")
    ]

    for obj, definition, value in custom_attributes:
      snapshot = db.session.query(models.Snapshot).filter(
          models.Snapshot.child_type == obj.type,
          models.Snapshot.child_id == obj.id,
      ).one()

      _cav = db.session.query(Record).filter(
          Record.key == snapshot.id,
          Record.type == "Snapshot",
          Record.property == definition,
          Record.content == value
      )
      _title = db.session.query(Record).filter(
          Record.key == snapshot.id,
          Record.type == "Snapshot",
          Record.property == "title",
          Record.content == obj.title
      )
      _desc = db.session.query(Record).filter(
          Record.key == snapshot.id,
          Record.type == "Snapshot",
          Record.property == "description",
          Record.content == obj.description
      )
      self.assertEqual(_cav.count(), 1)
      self.assertEqual(_title.count(), 1)
      self.assertEqual(_desc.count(), 1)

  def test_update_indexing(self):
    """Test that creating objects results in full index"""

    self._check_csv_response(self._import_file("snapshotter_create.csv"), {})

    access_group = db.session.query(models.AccessGroup).filter(
        models.AccessGroup.title == "ag-2"
    ).one()
    objective = db.session.query(models.Objective).filter(
        models.Objective.title == "obj-1"
    ).one()
    custom_attribute_defs = self.create_custom_attribute_definitions()
    custom_attribute_values = [
        {
            "custom_attribute": custom_attribute_defs["objective"],
            "attributable": objective,
            "attribute_value": "objective value 1",
        },
        {
            "custom_attribute": custom_attribute_defs["access_group"],
            "attributable": access_group,
            "attribute_value": "access_group text value 1",
        },
    ]

    for value in custom_attribute_values:
      factories.CustomAttributeValueFactory(**value)

    # Add custom attribute values via factory doesn't create revisions, so
    # we modify all the objects via import, which saves the full object
    # state in revisions table (including custom attribute values).
    self._check_csv_response(self._import_file("snapshotter_update.csv"), {})

    program = db.session.query(models.Program).filter(
        models.Program.slug == "Prog-13211"
    ).one()

    self.create_audit(program)

    objective_cav = db.session.query(models.CustomAttributeValue).filter(
        models.CustomAttributeValue.attribute_value == "objective value 1"
    ).one()

    access_group_cav = db.session.query(models.CustomAttributeValue).filter(
        models.CustomAttributeValue.attribute_value ==
        "access_group text value 1"
    ).one()

    cavs = [
        (objective_cav, "objective CA value edited after initial index"),
        (access_group_cav, "access_group CA value edited after initial index"),
    ]

    # This is not a correct way to update CAVs but PUT request on CAV
    # doesn't work and attaching full custom attribute signature
    # (custom_attribute_definitions, custom_attribute_values and
    # custom_attributes) is out of scope for this.
    for obj, val in cavs:
      obj.attribute_value = val
      db.session.add(obj)
    db.session.commit()

    access_group = db.session.query(models.AccessGroup).filter(
        models.AccessGroup.slug == "ag-2"
    ).one()
    objective = db.session.query(models.Objective).filter(
        models.Objective.slug == "obj-1"
    ).one()

    obj_edits = [
        (objective, "objective title edited after initial index"),
        (access_group, "access group title edited after initial index")
    ]

    for obj, title in obj_edits:
      obj = self.refresh_object(obj)
      self.api.modify_object(obj, {
          "title": title
      })

    audit = db.session.query(models.Audit).filter(
        models.Audit.title.like("%Snapshotable audit%")).one()
    # Initiate update operation
    self.api.modify_object(audit, {
        "snapshots": {
            "operation": "upsert"
        }
    })

    snapshots = db.session.query(models.Snapshot).all()

    records = db.session.query(Record).filter(
        tuple_(
            Record.type,
            Record.key,
            Record.property,
            Record.content
        ).in_(
            {("Snapshot", s.id, "parent", "Audit-{}".format(s.parent_id))
             for s in snapshots}
        ))

    self.assertEqual(records.count(), 66)

    custom_attributes = [
        (objective,
         "objective title edited after initial index",
         "objective rich field 1",
         "objective CA value edited after initial index"),
        (access_group,
         "access group title edited after initial index",
         "access group text field 2",
         "access_group CA value edited after initial index")
    ]

    for obj, title, definition, value in custom_attributes:
      obj = self.refresh_object(obj)
      snapshot = db.session.query(models.Snapshot).filter(
          models.Snapshot.child_type == obj.type,
          models.Snapshot.child_id == obj.id,
      ).one()

      _cav = db.session.query(Record).filter(
          Record.key == snapshot.id,
          Record.type == "Snapshot",
          Record.property == definition,
          Record.content == value
      )
      _title = db.session.query(Record).filter(
          Record.key == snapshot.id,
          Record.type == "Snapshot",
          Record.property == "title",
          Record.content == title
      )
      _desc = db.session.query(Record).filter(
          Record.key == snapshot.id,
          Record.type == "Snapshot",
          Record.property == "description",
          Record.content == obj.description
      )
      self.assertEqual(_cav.count(), 1)
      self.assertEqual(_title.count(), 1)
      self.assertEqual(_desc.count(), 1)

  def test_full_reindex(self):
    """Test full reindex of all snapshots"""
    self._check_csv_response(self._import_file("snapshotter_create.csv"), {})

    program = db.session.query(models.Program).filter(
        models.Program.slug == "Prog-13211"
    ).one()

    self.create_audit(program)

    audit = db.session.query(models.Audit).filter(
        models.Audit.title.like("%Snapshotable audit%")).first()

    snapshots = db.session.query(models.Snapshot).all()

    records = get_records(audit, snapshots)

    self.assertEqual(records.count(), 63)

    delete_records({s.id for s in snapshots})

    records = get_records(audit, snapshots)
    self.assertEqual(records.count(), 0)

    self.client.post("/admin/full_reindex")

    records = get_records(audit, snapshots)

    self.assertEqual(records.count(), 63)

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
          definition_type="control",
          title=cad_title,
      )
      control = factories.ControlFactory()
      factories.CustomAttributeValueFactory(
          custom_attribute=cad,
          attributable=control,
          attribute_value=value,
      )
    revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == control.id,
        all_models.Revision.resource_type == control.type,
    ).first()
    revision.content = control.log_json()
    db.session.add(revision)
    with factories.single_commit():
      snapshot = factories.SnapshotFactory(
          child_id=control.id,
          child_type=control.type,
          revision=revision)
    db.session.expire_all()
    snapshot_id = snapshot.id
    self.client.post("/admin/full_reindex")
    snapshot = all_models.Snapshot.query.get(snapshot_id)
    self.assert_indexed_fields(snapshot, cad_title, {"": search_value})

  def test_filter_by_checkbox_cad_no_cav(self):
    """Test index by Checkdoxed cad no cav."""
    checkbox_type = all_models.CustomAttributeDefinition.ValidTypes.CHECKBOX
    cad_title = "Checkbox"
    search_value = "No"
    with factories.single_commit():
      factories.CustomAttributeDefinitionFactory(
          attribute_type=checkbox_type,
          definition_type="control",
          title=cad_title,
      )
      control = factories.ControlFactory()
    revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == control.id,
        all_models.Revision.resource_type == control.type,
    ).first()
    revision.content = control.log_json()
    db.session.add(revision)
    with factories.single_commit():
      snapshot = factories.SnapshotFactory(
          child_id=control.id,
          child_type=control.type,
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
    self.client.post("/admin/full_reindex")
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
