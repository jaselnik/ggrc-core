# -*- coding: utf-8 -*-
# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for import/export endpoints.

Endpoints:

  - /api/people/person_id/imports
  - /api/people/person_id/exports

"""

import json
from datetime import datetime

import ddt
import mock

from appengine import base

from ggrc import db
from ggrc.models import all_models
from ggrc.notifications import import_export
from ggrc.utils import errors as app_errors

from integration.ggrc import api_helper
from integration.ggrc.models import factories
from integration.ggrc.services import TestCase


class TestImportExportBase(TestCase):
  """Base class for imports/exports tests."""

  def setUp(self):
    super(TestImportExportBase, self).setUp()
    self.client.get("/login")

  def run_full_import(self, user, data):
    """Emulate full cycle of data importing.

    Args:
        user: User object under which import should be run.
        data: data that should be imported.
    """
    imp_exp = factories.ImportExportFactory(
        job_type="Import",
        status="Blocked",
        created_by=user,
        created_at=datetime.now(),
        content=data,
    )

    return self.client.put(
        "/api/people/{}/imports/{}/start".format(user.id, imp_exp.id),
        headers=self.headers,
    )

  def run_full_export(self, user, obj):
    """Run export of test data through the /api/people/{}/exports endpoint."""
    return self.client.post(
        "/api/people/{}/exports".format(user.id),
        data=json.dumps({
            "objects": [{
                "object_name": obj.type,
                "ids": [obj.id]}],
            "current_time": str(datetime.now())}),
        headers=self.headers
    )


@base.with_memcache
class TestImportExportExceptions(TestImportExportBase):
  """Test exceptions Import Export jobs produce"""

  def test_handle_stop_raises_warning(self):
    """Test handle_export_stop method raises STOPPED_WARNING"""
    user = all_models.Person.query.first()
    ie_job = factories.ImportExportFactory(
        job_type="Export",
        created_at=datetime.now(),
        created_by=user,
        status="Stopped",
    )
    response = self.client.put(
        "/api/people/{}/exports/{}/stop".format(user.id, ie_job.id),
        headers=self.headers
    )
    self.assert400(response)
    self.assertEqual(response.json['message'], app_errors.STOPPED_WARNING)

  def test_handle_stop_raises_wrong(self):
    """Test handle_export_stop method raises wrong status exception"""
    user = all_models.Person.query.first()
    ie_job = factories.ImportExportFactory(
        job_type="Export",
        created_at=datetime.now(),
        created_by=user,
        status="Finished",
    )
    response = self.client.put(
        "/api/people/{}/exports/{}/stop".format(user.id, ie_job.id),
        headers=self.headers
    )
    self.assert400(response)
    self.assertEqual(response.json['message'], app_errors.WRONG_STATUS)


@ddt.ddt
@base.with_memcache
class TestImportExports(TestImportExportBase):
  """Tests for imports/exports endpoints."""

  def setUp(self):
    super(TestImportExports, self).setUp()
    self.headers = {
        "Content-Type": "application/json",
        "X-Requested-By": ["GGRC"],
    }
    self.api = api_helper.Api()

  @mock.patch("ggrc.gdrive.file_actions.get_gdrive_file_data",
              new=lambda x: (x, None, ''))
  def test_failed_imports_post(self):
    """Test imports post"""
    user = all_models.Person.query.first()
    data = [
        ['Object type'],
        ['invalid control', 'Title'],
        ['', 'Title'],
        [],
        [],
        ['Object type'],
        ['Control', 'Title'],
        ['', 'Title'],
        [],
        ['Object type'],
        ['Assessment', 'Title'],
        ['', 'Title'],
        [],
    ]
    response = self.client.post(
        "/api/people/{}/imports".format(user.id),
        data=json.dumps(data),
        headers=self.headers)
    self.assert200(response)
    self.assertFalse(response.json["objects"])
    self.assertEqual(response.json["import_export"]["status"],
                     "Analysis Failed")
    self.assertEqual(len(response.json["import_export"]["results"]), 3)
    for block in response.json["import_export"]["results"]:
      if block["name"] == "":
        self.assertEqual(block["rows"], 1)
        self.assertIn(u"Line 2", block["block_errors"][0])
      else:
        self.assertEqual(block["rows"], 1)
        self.assertFalse(block["block_errors"])

  @mock.patch("ggrc.gdrive.file_actions.get_gdrive_file_data",
              new=lambda x: (x, None, ''))
  def test_imports_post(self):
    """Test imports post"""
    user = all_models.Person.query.first()
    data = [
        ['Object type'],
        ['CONTROL', 'Title'],
        ['', 'Title1'],
        ['', 'Title2'],
        [],
        ['Object type'],
        ['Control', 'Title'],
        ['', 'Title3'],
        [],
        ['Object type'],
        ['Assessment', 'Title'],
        ['', 'Title3'],
        [],
        ['Object type'],
        ['Audit', 'Title'],
        ['', ''],
    ]
    response = self.client.post(
        "/api/people/{}/imports".format(user.id),
        data=json.dumps(data),
        headers=self.headers)
    self.assert200(response)
    self.assertEqual(response.json["import_export"]["status"], "Not Started")
    self.assertEqual(response.json["objects"]["Assessment"], 1)
    self.assertEqual(response.json["objects"]["Control"], 3)

  @ddt.data("Import", "Export")
  def test_get(self, job_type):
    """Test imports/exports get"""
    user = all_models.Person.query.first()
    ie1 = factories.ImportExportFactory(job_type=job_type,
                                        created_by=user,
                                        created_at=datetime.now())
    factories.ImportExportFactory(job_type=job_type,
                                  created_by=user,
                                  created_at=datetime.now())
    response = self.client.get(
        "/api/people/{}/{}s/{}".format(user.id, job_type.lower(), ie1.id),
        headers=self.headers)
    self.assert200(response)
    self.assertEqual(response.json["id"], ie1.id)

    response = self.client.get(
        "/api/people/{}/{}s".format(user.id, job_type.lower()),
        headers=self.headers)
    self.assert200(response)
    self.assertEqual(len(response.json), 2)

    response = self.client.get(
        "/api/people/{}/{}s?id__in={}".format(user.id, job_type.lower(),
                                              ie1.id),
        headers=self.headers)
    self.assert200(response)
    self.assertEqual(response.json[0]["id"], ie1.id)

  def test_imports_put(self):
    """Test imports put"""
    user = all_models.Person.query.first()
    ie1 = factories.ImportExportFactory(job_type="Import",
                                        status="Not Started",
                                        created_by=user,
                                        created_at=datetime.now())
    with mock.patch("ggrc.views.converters.run_background_import"):
      response = self.client.put(
          "/api/people/{}/imports/{}/start".format(user.id, ie1.id),
          headers=self.headers
      )
    self.assert200(response)
    self.assertEqual(response.json["id"], ie1.id)
    self.assertEqual(response.json["status"], "Analysis")

  def test_import_export_job(self):
    """Check if proper ImportExport jobs and bg tasks returned."""
    self.init_taskqueue()
    factories.AuditFactory(slug="audit-1")
    data = "Object type,,,\n" \
           "Assessment,Code*,Audit*,Title*,State*,Assignees*,Creators*\n" \
           ",,audit-1,Assessment title 1,,user@example.com,user@example.com"

    user = all_models.Person.query.first()

    imp_exp = factories.ImportExportFactory(
        job_type="Import",
        status="Not Started",
        created_by=user,
        created_at=datetime.now(),
        content=data,
    )

    response = self.client.put(
        "/api/people/{}/imports/{}/start".format(user.id, imp_exp.id),
        headers=self.headers,
    )
    self.assert200(response)
    with mock.patch("ggrc.models.background_task.BackgroundTask.finish"):
      response = self.client.put(
          "/api/people/{}/imports/{}/start".format(user.id, imp_exp.id),
          headers=self.headers,
      )
      self.assert200(response)

    imp_exp.status = "In Progress"
    db.session.add(imp_exp)
    db.session.commit()

    tasks = import_export.get_import_export_tasks()
    self.assertEqual(tasks.count(), 1)
    _, bg_task = tasks.first()

    expected_bg = all_models.BackgroundTask.query.order_by(
        all_models.BackgroundTask.id.desc()
    ).first()
    self.assertEqual(expected_bg.name, bg_task.name)

  def test_imports_get_all(self):
    """Test imports get all items"""
    user = all_models.Person.query.first()
    factories.ImportExportFactory(job_type="Import",
                                  status="Finished",
                                  created_by=user,
                                  created_at=datetime.now())
    response = self.api.client.get(
        "/api/people/{}/imports".format(user.id),
        headers=self.headers
    )
    result = json.loads(response.data)
    self.assertEqual(len(result), 1)
    self.assertEqual(set(all_models.ImportExport.DEFAULT_COLUMNS),
                     set(result[0].keys()))

  def test_imports_get_by_id(self):
    """Test imports get item by id"""
    user = all_models.Person.query.first()
    import_job = factories.ImportExportFactory(
        job_type="Import",
        status="Finished",
        created_by=user,
        created_at=datetime.now()
    )
    response = self.api.client.get(
        "/api/people/{}/imports/{}".format(user.id, import_job.id),
        headers=self.headers
    )
    result = json.loads(response.data)
    observed_columns = set(result.keys())
    expected_columns = set(
        column.name for column in all_models.ImportExport.__table__.columns
        if column.name not in ('content', 'gdrive_metadata')
    )
    self.assertEqual(observed_columns, expected_columns)

  @ddt.data("Import", "Export")
  def test_delete(self, job_type):
    """Test imports/exports delete"""
    user = all_models.Person.query.first()
    ie1 = factories.ImportExportFactory(job_type=job_type,
                                        created_by=user,
                                        created_at=datetime.now())

    response = self.client.delete(
        "/api/people/{}/{}s/{}".format(user.id, job_type.lower(), ie1.id),
        headers=self.headers)
    self.assert200(response)
    self.assertIsNone(all_models.ImportExport.query.get(ie1.id))

  def test_exports_post(self):
    """Test exports post"""
    user = all_models.Person.query.first()
    assessment = factories.AssessmentFactory()
    response = self.client.post(
        "/api/people/{}/exports".format(user.id),
        data=json.dumps({
            "objects": [{
                "object_name": "Assessment",
                "ids": [assessment.id]}],
            "current_time": str(datetime.now())}),
        headers=self.headers)
    self.assert200(response)

  @ddt.data("Import", "Export")
  def test_download(self, job_type):
    """Test imports/exports download"""
    user = all_models.Person.query.first()
    ie1 = factories.ImportExportFactory(
        job_type=job_type,
        status="Finished",
        created_at=datetime.now(),
        created_by=user,
        title="test.csv",
        content="test content")
    response = self.client.get(
        "/api/people/{}/{}s/{}/download?export_to=csv".format(
            user.id,
            job_type.lower(),
            ie1.id),
        headers=self.headers)
    self.assert200(response)
    self.assertEqual(response.data, "test content")

  @ddt.data(u'漢字.csv', u'фыв.csv', u'asd.csv')
  def test_download_unicode_filename(self, filename):
    """Test import history download unicode filename"""
    user = all_models.Person.query.first()
    ie_job = factories.ImportExportFactory(
        job_type='Import',
        status='Finished',
        created_at=datetime.now(),
        created_by=user,
        title=filename,
        content='Test content'
    )
    response = self.client.get(
        "/api/people/{}/imports/{}/download?export_to=csv".format(
            user.id,
            ie_job.id),
        headers=self.headers)
    self.assert200(response)
    self.assertEqual(response.data, "Test content")

  @ddt.data(r"\\\\test.csv",
            "test###.csv",
            '??test##.csv',
            '?test#.csv',
            r'\\filename?.csv',
            '??somenamea??.csv',
            r'!@##??\\.csv')
  def test_imports_with_spec_symbols(self, filename):
    """Test import with special symbols in file name"""
    with mock.patch("ggrc.gdrive.file_actions.get_gdrive_file_data",
                    new=lambda x: (x, None, filename)):
      user = all_models.Person.query.first()
      response = self.client.post(
          "/api/people/{}/imports".format(user.id),
          data=json.dumps([]),
          headers=self.headers)
      self.assert400(response)

  def test_import_stop(self):
    """Test import stop"""
    user = all_models.Person.query.first()
    ie1 = factories.ImportExportFactory(
        job_type="Import",
        status="Analysis",
        created_at=datetime.now(),
        created_by=user,
        title="test.csv",
        content="test content",
    )
    response = self.client.put(
        "/api/people/{}/imports/{}/stop".format(user.id, ie1.id),
        headers=self.headers
    )
    self.assert200(response)
    self.assertEqual(json.loads(response.data)["status"], "Stopped")

  def test_export_stop(self):
    """Test export stop"""
    user = all_models.Person.query.first()
    bg_task_name = "test export"
    instance_name = "test instance"
    export_op_type = all_models.BackgroundOperationType.query.filter_by(
        name="export"
    ).first()

    with factories.single_commit():
      ie_job = factories.ImportExportFactory(
          job_type="Export",
          status="In Progress",
          created_at=datetime.now(),
          created_by=user,
          title="test.csv",
          content="test content",
      )
      bg_task = factories.BackgroundTaskFactory(name=bg_task_name)
      factories.BackgroundOperationFactory(
          object_type=ie_job.type,
          object_id=ie_job.id,
          bg_task_id=bg_task.id,
          bg_operation_type=export_op_type,
      )

    with mock.patch("ggrc.settings.APPENGINE_INSTANCE", new=instance_name):
      with mock.patch("ggrc.cloud_api.task_queue.delete_task") as delete_task:
        response = self.client.put(
            "/api/people/{}/exports/{}/stop".format(user.id, ie_job.id),
            headers=self.headers
        )
        self.assert200(response)
        self.assertEqual(json.loads(response.data)["status"], "Stopped")
        task_name = "projects/{}/locations/{}/queues/{}/tasks/{}".format(
            instance_name, "us-central1", "ggrcImport", bg_task_name
        )
        delete_task.assert_called_once_with(task_name)
        bg_task = all_models.BackgroundTask.query.filter_by(
            name=bg_task_name
        ).first()
        self.assertEqual(
            bg_task.status,
            all_models.BackgroundTask.STOPPED_STATUS
        )

  @ddt.data(("Not Started", True),
            ("Blocked", True),
            ("Finished", False))
  @ddt.unpack
  @mock.patch("ggrc.gdrive.file_actions.get_gdrive_file_data",
              new=lambda x: (x, None, ''))
  def test_delete_previous_imports(self, status, should_be_none):
    """Test deletion of previous imports"""
    user = all_models.Person.query.first()
    ie_item = factories.ImportExportFactory(
        job_type="Import",
        status=status,
        created_at=datetime.now(),
        created_by=user).id

    response = self.client.post(
        "/api/people/{}/imports".format(user.id),
        data=json.dumps([]),
        headers=self.headers)

    self.assert200(response)
    if should_be_none:
      self.assertIsNone(all_models.ImportExport.query.get(ie_item))
    else:
      self.assertIsNotNone(all_models.ImportExport.query.get(ie_item))

    ie_item_in_progress = factories.ImportExportFactory(
        job_type="Import",
        status="In Progress",
        created_at=datetime.now(),
        created_by=user).id
    response = self.client.post(
        "/api/people/{}/imports".format(user.id),
        data=json.dumps([]),
        headers=self.headers)
    self.assert400(response)
    self.assertIsNotNone(all_models.ImportExport.query.get(
        ie_item_in_progress))

  @mock.patch(
      "ggrc.gdrive.file_actions.get_gdrive_file_data",
      new=lambda x: (x, None, '')
  )
  def test_import_risk_revisions(self):
    """Test if new revisions created during import."""
    data = "Object type,,,,,\n" + \
           "Contract,code*,title*,description,admin,state\n" + \
           ",contract-1,contract-1,test,user@example.com,Draft"

    user = all_models.Person.query.first()

    response = self.run_full_import(user, data)
    self.assert200(response)

    contract = all_models.Contract.query.filter_by(title="contract-1").first()
    self.assertIsNotNone(contract)
    revision_actions = db.session.query(all_models.Revision.action).filter(
        all_models.Revision.resource_type == "Contract",
        all_models.Revision.resource_id == contract.id
    )
    self.assertEqual({"created"}, {a[0] for a in revision_actions})

  @mock.patch(
      "ggrc.gdrive.file_actions.get_gdrive_file_data",
      new=lambda x: (x, None, '')
  )
  def test_import_snapshot(self):
    """Test if snapshots can be created from imported objects."""
    data = "Object type,,,,,\n" + \
           "Contract,code*,title*,description,admin,state\n" + \
           ",contract-1,contract-1,test,user@example.com,Draft\n" + \
           ",Contract-2,Contract-2,test,user@example.com,Active\n" + \
           ",Contract-3,Contract-3,test,user@example.com,Draft"

    user = all_models.Person.query.first()

    response = self.run_full_import(user, data)
    self.assert200(response)

    contracts = all_models.Contract.query
    self.assertEqual(3, contracts.count())

    audit = factories.AuditFactory()
    snapshots = self._create_snapshots(audit, contracts.all())
    self.assertEqual(3, len(snapshots))

  def test_import_map_objectives(self):
    """Test import can't map assessments with objectives"""
    audit = factories.AuditFactory(slug='AUDIT-9999')
    audit_id = audit.id
    objectives = [
        factories.ObjectiveFactory(
            title='obj_999{}'.format(i),
            slug='OBJECTIVE-999{}'.format(i)
        ) for i in range(10)
    ]
    for objective in objectives:
      factories.RelationshipFactory(source=audit.program,
                                    destination=objective)

    response = self._import_file(
        'assessments_map_with_objectives_in_scope_of_program.csv', True
    )

    row_errors = {
        'Line 10: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.',
        'Line 11: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.',
        'Line 12: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.',
        'Line 3: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.',
        'Line 4: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.',
        'Line 5: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.',
        'Line 6: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.',
        'Line 7: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.',
        'Line 8: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.',
        'Line 9: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.'
    }

    expected_messages = {
        'Assessment': {
            'created': 0,
            'row_errors': row_errors
        }
    }

    assessments = db.session.query(all_models.Assessment).filter_by(
        audit_id=audit_id).all()

    self.assertEqual(len(assessments), 0)
    self._check_csv_response(response, expected_messages)

    # update the audit to the latest version
    self.api.put(all_models.Audit.query.get(audit_id),
                 {'snapshots': {'operation': 'upsert'}}
                 )

    response = self._import_file('assessments_map_to_obj_snapshots.csv')

    expected_messages = {
        'Assessment': {
            'created': 10,
            'row_errors': set()
        }
    }

    assessments = db.session.query(all_models.Assessment).filter_by(
        audit_id=audit_id).all()

    self.assertEqual(len(assessments), 10)
    self._check_csv_response(response, expected_messages)
