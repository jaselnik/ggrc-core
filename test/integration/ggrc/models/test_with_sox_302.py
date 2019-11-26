# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

# pylint: disable=protected-access,too-many-lines

"""Integration tests for `WithSOX302Flow` logic."""

import collections

import ddt
from ggrc import settings
from ggrc.models import all_models
from ggrc.models.assessment_template import VerificationWorkflow
from ggrc.models.mixins import statusable
from integration import ggrc as integration_tests_ggrc
from integration.ggrc import api_helper
from integration.ggrc import query_helper
from integration.ggrc.models import factories as ggrc_factories


class BaseTestWithSOX302(integration_tests_ggrc.TestCase):
  """Base class for test cases for `WithSOX302Flow` logic."""

  def _login(self):
    """Make `self.client` to exec further requests as if issuer's logged in."""
    self.client.get("/login")

  @staticmethod
  def _get_query_by_audit_for(obj_type, audit_id):
    # type: (db.Model, int) -> sqlalchemy.Query
    """Build sqlalchemy query for specific object type filtered by audit.

    Build sqlalchemy query for objects of type `obj_type` which are related to
    audit with `audit_id` ID. This helper method allows to build DB query when
    audit ID is known and use this query later.

    Args:
        obj_type (db.Model): Class instance of objects to query.
        audit_id (int): ID of Audit instance whose related objects should be
          queried.

    Returns:
      Sqlalchemy.Query object which could be used for later queries.
    """
    return obj_type.query.filter(obj_type.audit_id == audit_id)

  @staticmethod
  def _refresh_object(obj_type, obj_id):
    # type: (db.Model) -> db.Model
    """Refresh passed object and attach it to the current session.

    Args:
        objs (db.Model): Instances of db.Model class to be refreshed.

    Returns:
      Refreshed instance of db.Model class.
    """
    return obj_type.query.get(obj_id)

  @staticmethod
  def _get_asmt_tmpl_lcas(asmt_template):
    # type: (model.AssessmentTemplate) -> List[model.CustomAttributeDefinition]
    """Return list of local CADs of AssessmentTemplate.

    Return list of local CustomAttributeDefinition instances related to the
    given AssessmentTemplate.

    Args:
      asmt_template (model.AssessmentTemplate): Assessment template whose
        local custom attributes should be queried from DB.

    Returns:
      List of CustomAttributeDefinition instances.
    """
    cad = all_models.CustomAttributeDefinition
    return cad.query.filter(
        cad.definition_type == asmt_template._inflector.table_singular,
        cad.definition_id == asmt_template.id,
    ).all()

  def _assert_sox_302_enabled_flag(self, obj, expected_value):
    # type: (db.Model, bool) -> None
    """Assert that `sox_302_enabled` flag has expected value on object.

    For this assertion to pass, following conditions should be met:
      - Given object should be derived from `WithSOX302Flow` mixin;
      - Value of `sox_302_enabled` on object should match `expected_value`.

    Args:
      obj (db.Model): Instance of db.Model class on which value of
        `sox_302_enabled` flag should be checked.
      expected_value (bool): Expected value of `sox_302_enabled` flag on the
        given object.
    """
    self.assertIsNotNone(obj)
    self.assertEqual(
        obj.sox_302_enabled,
        expected_value,
    )

  def _assert_negative_options(self, cads, expected_cad_count,
                               expected_options, expected_negatives):
    # type: (List[model.CustomAttributeDefinition], int, list, list) -> None
    """Assert that provided CADs have correct negative options.

    For this assertion to pass, following conditions should be met:
      - Number of CADs should match with `expected_cad_count`;
      - Options of each CAD should match with options from `expected_options`;
      - Options from `expected_negatives` should be negative ones on CAD;

    Args:
      cads (List[model.CustomAttributeDefinition]): List of CADs whoose options
        should be checked.
      expected_cad_count (int): Expected number of CADs.
      expected_options (List[str]): List of expected options for each CAD.
      expected_negatives (List[str]): List of expected negative options for
        each CAD.
    """
    self.assertEqual(expected_cad_count, len(cads))
    for item in zip(cads, expected_options, expected_negatives):
      lca, exp_options, exp_negatives = item
      self.assertEqual(exp_options, lca.multi_choice_options)
      self.assertIn(exp_negatives, lca.negative_options)


@ddt.ddt
class TestImportWithSOX302(BaseTestWithSOX302):
  """Test import of `WithSOX302Flow` objects."""

  @ddt.data(
      {
          "imported_value": VerificationWorkflow.SOX302,
          "exp_value": True,
      },
      {
          "imported_value": VerificationWorkflow.STANDARD,
          "exp_value": False,
      },
  )
  @ddt.unpack
  def test_sox_302_tmpl_create(self, imported_value, exp_value):
    """Test SOX302 enabled={exp_value} when create asmt tmpl via import."""
    audit = ggrc_factories.AuditFactory()
    audit_id = audit.id

    asmt_tmpl_data = collections.OrderedDict([
        ("object_type", "Assessment Template"),
        ("Code*", ""),
        ("Audit*", audit.slug),
        ("Title", "AssessmentTemplate Title"),
        ("Default Assessment Type*", "Control"),
        ("Default Assignees*", "Auditors"),
        ("Verification Workflow", imported_value),
    ])

    self._login()
    response = self.import_data(asmt_tmpl_data)

    self._check_csv_response(response, {})
    tmpl = self._get_query_by_audit_for(
        all_models.AssessmentTemplate, audit_id).one()
    self._assert_sox_302_enabled_flag(tmpl, exp_value)

  def test_multi_verification_tmpl_create(self):
    # pylint: disable=invalid-name
    """Test SOX302 enabled=False when create MLV asmt tmpl via import."""
    audit = ggrc_factories.AuditFactory()
    audit_id = audit.id

    asmt_tmpl_data = collections.OrderedDict([
        ("object_type", "Assessment Template"),
        ("Code*", ""),
        ("Audit*", audit.slug),
        ("Title", "AssessmentTemplate Title"),
        ("Default Assessment Type*", "Control"),
        ("Default Assignees*", "Auditors"),
        ("Verification Workflow", VerificationWorkflow.MLV),
        ("Verification Levels", settings.REVIEW_LEVELS_MIN_COUNT),
    ])

    self._login()
    response = self.import_data(asmt_tmpl_data)

    self._check_csv_response(response, {})
    tmpl = self._get_query_by_audit_for(
        all_models.AssessmentTemplate, audit_id).one()
    self._assert_sox_302_enabled_flag(tmpl, False)

  @ddt.data(
      {
          "init_workflow": VerificationWorkflow.STANDARD,
          "imported_value": VerificationWorkflow.SOX302,
          "exp_value": True,
      },
      {
          "init_workflow": VerificationWorkflow.MLV,
          "imported_value": VerificationWorkflow.SOX302,
          "exp_value": True,
      },
  )
  @ddt.unpack
  def test_sox_302_tmpl_update(self, init_workflow, imported_value, exp_value):
    """Test SOX302 enabled={exp_value} when update asmt tmpl via import."""
    tmpl = ggrc_factories.AssessmentTemplateFactory(
        verification_workflow=init_workflow,
    )
    tmpl_id = tmpl.id

    asmt_tmpl_data = collections.OrderedDict([
        ("object_type", "Assessment Template"),
        ("Code*", tmpl.slug),
        ("Verification Workflow", imported_value),
    ])

    self._login()
    response = self.import_data(asmt_tmpl_data)

    self._check_csv_response(response, {})
    tmpl = self._refresh_object(tmpl.__class__, tmpl_id)
    self._assert_sox_302_enabled_flag(tmpl, exp_value)

  def test_multi_verification_tmpl_update(self):
    # pylint: disable=invalid-name
    """Test SOX302 enabled=False when update MLV asmt tmpl via import."""
    init_workflow = VerificationWorkflow.STANDARD
    imported_value = VerificationWorkflow.MLV
    tmpl = ggrc_factories.AssessmentTemplateFactory(
        verification_workflow=init_workflow,
    )
    tmpl_id = tmpl.id

    asmt_tmpl_data = collections.OrderedDict([
        ("object_type", "Assessment Template"),
        ("Code*", tmpl.slug),
        ("Verification Workflow", imported_value),
        ("Verification Levels", settings.REVIEW_LEVELS_MIN_COUNT),
    ])

    self._login()
    response = self.import_data(asmt_tmpl_data)

    self._check_csv_response(response, {})
    tmpl = self._refresh_object(tmpl.__class__, tmpl_id)
    self._assert_sox_302_enabled_flag(tmpl, False)

  @ddt.data(
      {
          "asmt_workflow": VerificationWorkflow.SOX302,
          "tmpl_workflow": VerificationWorkflow.SOX302,
          "exp_value": True,
      },
      {
          "asmt_workflow": VerificationWorkflow.SOX302,
          "tmpl_workflow": VerificationWorkflow.STANDARD,
          "exp_value": True,
      },
      {
          "asmt_workflow": VerificationWorkflow.STANDARD,
          "tmpl_workflow": VerificationWorkflow.SOX302,
          "exp_value": False,
      },
      {
          "asmt_workflow": VerificationWorkflow.STANDARD,
          "tmpl_workflow": VerificationWorkflow.STANDARD,
          "exp_value": False,
      },
  )
  @ddt.unpack
  def test_sox_302_asmt_with_tmpl_upd(self, asmt_workflow,
                                      tmpl_workflow, exp_value):
    """Test SOX 302 enabled is immutable when update asmt with tmpl via import.

    Test `sox_302_enabled` on Assessment could not be set via import during
    Assessment update if there is an AssessmentTemplate provided in import
    data. SOX 302 enabled flag is read only on Assessment and could not be
    updated in noway.
    """
    with ggrc_factories.single_commit():
      asmt = ggrc_factories.AssessmentFactory(
          verification_workflow=asmt_workflow,
      )
      tmpl = ggrc_factories.AssessmentTemplateFactory(
          audit=asmt.audit,
          verification_workflow=tmpl_workflow,
      )

    asmt_id = asmt.id

    asmt_data = collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", asmt.slug),
        ("Template", tmpl.slug),
    ])

    self._login()
    response = self.import_data(asmt_data)

    self._check_csv_response(response, {})
    asmt = self._refresh_object(asmt.__class__, asmt_id)
    self._assert_sox_302_enabled_flag(asmt, exp_value)

  @ddt.data(
      {
          "imported_value": VerificationWorkflow.SOX302,
          "exp_value": False,
      },
      {
          "imported_value": VerificationWorkflow.STANDARD,
          "exp_value": False,
      },
      {
          "imported_value": "",
          "exp_value": False,
      },
  )
  @ddt.unpack
  def test_sox_302_immut_asmt_create(self, imported_value, exp_value):
    """
      Test SOX 302 enabled is immutable when create asmt via import.

      Test `sox_302_enabled` on Assessment could not be set via import if there
      isn't any AssessmentTemplate provided in import data. SOX 302 enabled
      flag is read only on Assessment and could be set only from template.
    """
    audit = ggrc_factories.AuditFactory()
    audit_id = audit.id

    asmt_data = collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", ""),
        ("Template", ""),
        ("Audit*", audit.slug),
        ("Title", "Assessment Title"),
        ("Assignees", "user@example.com"),
        ("Creators", "user@example.com"),
        ("Verification Workflow", imported_value),
    ])

    self._login()
    response = self.import_data(asmt_data)

    self._check_csv_response(response, {})
    asmt = self._get_query_by_audit_for(all_models.Assessment, audit_id).one()
    self._assert_sox_302_enabled_flag(asmt, exp_value)

  @ddt.data(
      {
          "init_value": VerificationWorkflow.SOX302,
          "imported_value": VerificationWorkflow.STANDARD,
          "exp_value": True,
      },
      {
          "init_value": VerificationWorkflow.SOX302,
          "imported_value": "",
          "exp_value": True,
      },
      {
          "init_value": VerificationWorkflow.STANDARD,
          "imported_value": VerificationWorkflow.SOX302,
          "exp_value": False,
      },
      {
          "init_value": VerificationWorkflow.SOX302,
          "imported_value": "",
          "exp_value": True,
      },
      {
          "init_value": VerificationWorkflow.STANDARD,
          "imported_value": "",
          "exp_value": False,
      },
  )
  @ddt.unpack
  def test_sox_302_immut_asmt_upd(self, init_value, imported_value, exp_value):
    """
      Test SOX 302 enabled is immutable when update asmt via import.

      Test `sox_302_enabled` on Assessment could not be set via import during
      Assessment update if there isn't any AssessmentTemplate provided in
      import data. SOX 302 enabled flag is read only on Assessment and could
      not be updated in noway.
    """
    asmt = ggrc_factories.AssessmentFactory(
        verification_workflow=init_value,
    )
    asmt_id = asmt.id

    asmt_data = collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", asmt.slug),
        ("Verification Workflow", imported_value),
    ])

    self._login()
    response = self.import_data(asmt_data)

    self._check_csv_response(response, {})
    asmt = self._refresh_object(asmt.__class__, asmt_id)
    self._assert_sox_302_enabled_flag(asmt, exp_value)

  @ddt.data(
      {
          "lca_to_import": "Dropdown, LCA with negative, yes, (n)no",
          "expected_options": ["yes,no"],
          "expected_negatives": ["no"],
          "expected_lca_count": 1,
      },
      {
          "lca_to_import": "Rich Text, LCA with negative, empty, (n)not empty",
          "expected_options": ["empty,not empty"],
          "expected_negatives": ["not empty"],
          "expected_lca_count": 1,
      },
      {
          "lca_to_import": "Text, LCA with negative, (n)empty, not empty",
          "expected_options": ["empty,not empty"],
          "expected_negatives": ["empty"],
          "expected_lca_count": 1,
      },
  )
  @ddt.unpack
  def test_negative_lca_create(self, lca_to_import, expected_options,
                               expected_negatives, expected_lca_count):
    """Test LCA with negative options is created when create tmpl via import.

    Test that local Custom Attribute with negative options is created when
    creating new Assessment Template via import.
    """
    audit = ggrc_factories.AuditFactory()
    audit_id = audit.id

    asmt_tmpl_data = collections.OrderedDict([
        ("object_type", "Assessment Template"),
        ("Code*", ""),
        ("Audit*", audit.slug),
        ("Title*", "AssessmentTemplate Title"),
        ("Default Assessment Type*", "Control"),
        ("Default Assignees*", "Auditors"),
        ("Custom Attributes", lca_to_import),
    ])

    self._login()
    response = self.import_data(asmt_tmpl_data)

    self._check_csv_response(response, {})
    tmpl = self._get_query_by_audit_for(
        all_models.AssessmentTemplate, audit_id).one()
    self._assert_negative_options(
        cads=self._get_asmt_tmpl_lcas(tmpl),
        expected_cad_count=expected_lca_count,
        expected_options=expected_options,
        expected_negatives=expected_negatives,
    )


@ddt.ddt
class TestExportWithSOX302(query_helper.WithQueryApi,
                           BaseTestWithSOX302):
  """Test export of of `WithSOX302Flow` objects."""

  def _assert_sox_302_enabled_flag_exported(self, exported_data, obj_name,
                                            expected_value):
    # type: (dict, str, str) -> None
    # pylint: disable=invalid-name
    """Assert that `sox_302_enabled` has expected value in exported data.

    For this assertion to pass, following conditions should be met:
      - Given object name should be present in exported data;
      - There should be only one object of provided type in exported data.
      - Value of "SOX 302 assessment workflow" in exported data should match
        with passed `expected_value`.

    Args:
      exported_data (dict): Dict representing exported object. Keys are field
        names as they should be named in resulting .CSV file.
      obj_name (str): Capitalized human readable object name.
      expected_value (str): Expected value of "SOX 302 assessment workflow"
        column in exported data.
    """
    self.assertIn(obj_name, exported_data)
    self.assertEqual(1, len(exported_data[obj_name]))
    exported_obj_data = exported_data[obj_name][0]
    self.assertEqual(
        exported_obj_data["Verification Workflow"],
        expected_value,
    )

  @ddt.data(
      VerificationWorkflow.SOX302,
      VerificationWorkflow.STANDARD,
      VerificationWorkflow.MLV,
  )
  def test_sox_302_tmpl_export(self, workflow):
    """Test `SOX 302 assessment workflow` is exported correctly for tmpl."""
    tmpl = ggrc_factories.AssessmentTemplateFactory(
        verification_workflow=workflow,
    )
    tmpl_id = tmpl.id

    self._login()
    exported_data = self.export_parsed_csv([
        self._make_query_dict(
            "AssessmentTemplate",
            expression=["id", "=", tmpl_id],
        )
    ])

    self._assert_sox_302_enabled_flag_exported(
        exported_data,
        "Assessment Template",
        workflow,
    )

  @ddt.data(
      VerificationWorkflow.SOX302,
      VerificationWorkflow.STANDARD,
      VerificationWorkflow.MLV,
  )
  def test_sox_302_asmt_export(self, workflow):
    """Test `SOX 302 assessment workflow` is exported correctly for asmt."""
    asmt = ggrc_factories.AssessmentFactory(
        verification_workflow=workflow,
    )
    asmt_id = asmt.id

    self._login()

    exported_data = self.export_parsed_csv([
        self._make_query_dict(
            "Assessment",
            expression=["id", "=", asmt_id],
        )
    ])

    self._assert_sox_302_enabled_flag_exported(
        exported_data,
        "Assessment",
        workflow,
    )


@ddt.ddt
class TestApiWithSOX302(BaseTestWithSOX302):
  """Test REST API functonality of `WithSOX302Flow` objects."""

  def setUp(self):
    """Set up for SOX 302 REST API test case."""
    super(TestApiWithSOX302, self).setUp()
    self.api = api_helper.Api()

  @ddt.data(
      {
          "workflow": VerificationWorkflow.SOX302,
          "exp_value": True,
      },
      {
          "workflow": VerificationWorkflow.STANDARD,
          "exp_value": False,
      },
  )
  @ddt.unpack
  def test_sox_302_tmpl_create(self, workflow, exp_value):
    """Test SOX302 enabled={exp_value} when create asmt tmpl via API."""
    audit = ggrc_factories.AuditFactory()
    audit_id = audit.id

    response = self.api.post(
        all_models.AssessmentTemplate,
        {
            "assessment_template": {
                "audit": {"id": audit.id},
                "context": {"id": audit.context.id},
                "default_people": {
                    "assignees": "Admin",
                    "verifiers": "Admin",
                },
                "title": "AssessmentTemplate Title",
                "verification_workflow": workflow,
            },
        },
    )

    self.assert201(response)
    tmpl = self._get_query_by_audit_for(
        all_models.AssessmentTemplate, audit_id).one()
    self._assert_sox_302_enabled_flag(tmpl, exp_value)

  @ddt.data(
      {
          "init_workflow": VerificationWorkflow.SOX302,
          "sent_workflow": VerificationWorkflow.SOX302,
          "exp_value": True,
      },
      {
          "init_workflow": VerificationWorkflow.SOX302,
          "sent_workflow": VerificationWorkflow.STANDARD,
          "exp_value": False,
      },
      {
          "init_workflow": VerificationWorkflow.STANDARD,
          "sent_workflow": VerificationWorkflow.SOX302,
          "exp_value": True,
      },
      {
          "init_workflow": VerificationWorkflow.STANDARD,
          "sent_workflow": VerificationWorkflow.STANDARD,
          "exp_value": False,
      },
  )
  @ddt.unpack
  def test_sox_302_tmpl_update(self, init_workflow, sent_workflow, exp_value):
    """Test SOX302 enabled={exp_value} when update asmt tmpl via API."""

    tmpl = ggrc_factories.AssessmentTemplateFactory(
        verification_workflow=init_workflow,
    )
    tmpl_id = tmpl.id

    response = self.api.put(
        tmpl,
        {
            "verification_workflow": sent_workflow,
        },
    )

    self.assert200(response)
    tmpl = self._refresh_object(tmpl.__class__, tmpl_id)
    self._assert_sox_302_enabled_flag(tmpl, exp_value)

  @ddt.data(
      {"orig_value": VerificationWorkflow.SOX302, "exp_value": True},
      {"orig_value": VerificationWorkflow.STANDARD, "exp_value": False},
  )
  @ddt.unpack
  def test_sox_302_tmpl_clone(self, orig_value, exp_value):
    """Test AssessmentTemplate SOX 302 enabled={0} when clone via API."""

    tmpl = ggrc_factories.AssessmentTemplateFactory(
        verification_workflow=orig_value,
    )
    audit_id = tmpl.audit.id
    tmpl_id = tmpl.id

    response = self.api.send_request(
        self.api.client.post,
        api_link="/api/assessment_template/clone",
        data=[{
            "sourceObjectIds": [tmpl.id],
            "destination": {
                "type": "Audit",
                "id": tmpl.audit.id,
            },
            "mappedObjects": []
        }],
    )

    self.assert200(response)
    tmpl_q = self._get_query_by_audit_for(
        all_models.AssessmentTemplate, audit_id)
    tmpl_clone = tmpl_q.filter(
        all_models.AssessmentTemplate.id != tmpl_id).one()
    self._assert_sox_302_enabled_flag(tmpl_clone, exp_value)

  @ddt.data(
      {"sent_value": VerificationWorkflow.SOX302, "exp_value": False},
      {"sent_value": VerificationWorkflow.STANDARD, "exp_value": False},
  )
  @ddt.unpack
  def test_sox_302_immut_asmt_create(self, sent_value, exp_value):
    """Test SOX 302 enabled is immutable when create asmt via API.

    Test `sox_302_enabled` on Assessment could not be set via API if there
    isn't any AssessmentTemplate provided in request data. SOX 302 enabled flag
    is read only on Assessment and could be set only from template.
    """
    audit = ggrc_factories.AuditFactory()
    audit_id = audit.id

    response = self.api.post(
        all_models.Assessment,
        {
            "assessment": {
                "audit": {"id": audit.id},
                "title": "Assessment Title",
                "verification_workflow": sent_value,
            },
        },
    )

    self.assert201(response)
    asmt = self._get_query_by_audit_for(all_models.Assessment, audit_id).one()
    self._assert_sox_302_enabled_flag(asmt, exp_value)

  @ddt.data(
      {
          "tmpl_value": VerificationWorkflow.SOX302,
          "sent_value": VerificationWorkflow.SOX302,
          "exp_value": True,
      },
      {
          "tmpl_value": VerificationWorkflow.STANDARD,
          "sent_value": VerificationWorkflow.SOX302,
          "exp_value": False,
      },
      {
          "tmpl_value": VerificationWorkflow.SOX302,
          "sent_value": VerificationWorkflow.STANDARD,
          "exp_value": True,
      },
      {
          "tmpl_value": VerificationWorkflow.STANDARD,
          "sent_value": VerificationWorkflow.STANDARD,
          "exp_value": False,
      },
  )
  @ddt.unpack
  def test_sox_302_asmt_with_tmpl_create(self, tmpl_value, sent_value,
                                         exp_value):
    # pylint: disable=invalid-name
    """Test SOX 302 enabled is mutable when create asmt with tmpl via API.

    Test `sox_302_enabled` on Assessment could be set via API if there is an
    AssessmentTemplate provided in request data. SOX 302 enabled flag is read
    only on Assessment and could be set only from template.
    """
    with ggrc_factories.single_commit():
      audit = ggrc_factories.AuditFactory()
      asmt_tmpl = ggrc_factories.AssessmentTemplateFactory(
          audit=audit,
          verification_workflow=tmpl_value,
      )
    audit_id = audit.id

    response = self.api.post(
        all_models.Assessment,
        {
            "assessment": {
                "audit": {"id": audit.id},
                "template": {"id": asmt_tmpl.id},
                "title": "Assessment Title",
                "verification_workflow": sent_value,
            },
        },
    )

    self.assert201(response)
    asmt = self._get_query_by_audit_for(all_models.Assessment, audit_id).one()
    self._assert_sox_302_enabled_flag(asmt, exp_value)

  @ddt.data(
      {
          "init_value": VerificationWorkflow.SOX302,
          "sent_value": VerificationWorkflow.SOX302,
          "exp_value": True,
      },
      {
          "init_value": VerificationWorkflow.SOX302,
          "sent_value": VerificationWorkflow.STANDARD,
          "exp_value": True,
      },
      {
          "init_value": VerificationWorkflow.STANDARD,
          "sent_value": VerificationWorkflow.SOX302,
          "exp_value": False,
      },
      {
          "init_value": VerificationWorkflow.STANDARD,
          "sent_value": VerificationWorkflow.STANDARD,
          "exp_value": False,
      },
  )
  @ddt.unpack
  def test_sox_302_immut_asmt_upd(self, init_value, sent_value, exp_value):
    """Test SOX 302 enabled is immutable when update asmt via API.

    Test `sox_302_enabled` on Assessment could not be updated via API.
    SOX 302 enabled flag is read only on Assessment and could be set only
    during creation with AssessmentTemplate.
    """
    asmt = ggrc_factories.AssessmentFactory(
        verification_workflow=init_value,
    )
    asmt_id = asmt.id

    response = self.api.put(
        asmt,
        {
            "verification_workflow": sent_value,
        },
    )

    self.assert200(response)
    asmt = self._refresh_object(asmt.__class__, asmt_id)
    self._assert_sox_302_enabled_flag(asmt, exp_value)


@ddt.ddt
class TestQueriesWithSOX302(query_helper.WithQueryApi,
                            BaseTestWithSOX302):
  """Test query API filtering for `WithSOX302Flow` objects."""

  def setUp(self):
    super(TestQueriesWithSOX302, self).setUp()
    self.api = api_helper.Api()

  def _assert_right_obj_found(self, query_result, expected_obj_type,
                              expected_obj_id):
    # type: (dict, str, int) -> None
    """Assert that only expected object was found by query API.

    For this assertion to pass, following conditions should be met:
      - Given query result should contain only one object;
      - ID of object in the query result should match with the given expected
        object ID.

    Args:
      query_result (dict): Dict representing result of query API request.
      expected_obj_type (str): Expected type of found object.
      expected_obj_id (int): Expected ID of found object.
    """
    response_asmt_tmpl = query_result[0][expected_obj_type]
    self.assertEqual(1, response_asmt_tmpl["count"])
    self.assertEqual(
        response_asmt_tmpl["values"][0]["id"],
        expected_obj_id,
    )

  @ddt.data(
      VerificationWorkflow.STANDARD,
      VerificationWorkflow.SOX302,
  )
  def test_sox_302_enabled_filter_tmpl(self, filter_by_value):
    # pylint: disable=invalid-name
    """Test tmpl could be filtered by sox_302_enabled field."""

    with ggrc_factories.single_commit():
      tmpl = ggrc_factories.AssessmentTemplateFactory(
          verification_workflow=filter_by_value,
      )
      ggrc_factories.AssessmentTemplateFactory(
          verification_workflow=VerificationWorkflow.MLV,
      )

    searched_tmpl_id = tmpl.id

    query_request_data = [
        self._make_query_dict(
            "AssessmentTemplate",
            expression=["Verification Workflow", "=", filter_by_value],
        ),
    ]

    response = self.api.send_request(
        self.api.client.post, data=query_request_data, api_link="/query"
    )

    self.assert200(response)
    self._assert_right_obj_found(
        response.json,
        "AssessmentTemplate",
        searched_tmpl_id,
    )

  @ddt.data(
      VerificationWorkflow.STANDARD,
      VerificationWorkflow.SOX302,
  )
  def test_sox_302_enabled_filter(self, filter_by_value):
    """Test asmt could be filtered by sox_302_enabled field."""
    with ggrc_factories.single_commit():
      asmt = ggrc_factories.AssessmentFactory(
          verification_workflow=filter_by_value,
      )
      ggrc_factories.AssessmentFactory(
          verification_workflow=VerificationWorkflow.MLV,
      )
    searched_amst_id = asmt.id

    query_request_data = [
        self._make_query_dict(
            "Assessment",
            expression=["Verification Workflow", "=", filter_by_value],
        ),
    ]

    response = self.api.send_request(
        self.api.client.post, data=query_request_data, api_link="/query"
    )

    self.assert200(response)
    self._assert_right_obj_found(
        response.json,
        "Assessment",
        searched_amst_id,
    )


@ddt.ddt
class TestStatusFlowWithSOX302(BaseTestWithSOX302):
  """Test status flow for `WithSOX302Flow` objects."""

  def setUp(self):
    """Set up for SOX 302 status flow test case."""
    super(TestStatusFlowWithSOX302, self).setUp()
    self.api = api_helper.Api()

  def _assert_status_field(self, obj, expected_value):
    # type: (db.Model, bool) -> None
    """Assert that `status` field has expected value on object.

    For this assertion to pass, following conditions should be met:
      - Given object should be derived from `Statusable` mixin;
      - Value of `status` field on object should match `expected_value`.

    Args:
      obj (db.Model): Instance of db.Model class on which value of
        `status` flag should be checked.
      expected_value (bool): Expected value of `status` field on the
        given object.
    """
    self.assertTrue(isinstance(obj, statusable.Statusable))
    self.assertIsNotNone(obj)
    self.assertEqual(
        obj.status,
        expected_value,
    )

  @staticmethod
  def _setup_local_custom_attributes(obj, cad_cav_pairs):
    # type: (db.Model, list) -> None
    """Setup custom attribute definitions and values for the given object.

    Create custom attribute definitions and and values for them from the given
    `cad_cav_pairs` list of string representations and attach them to `obj`.

    Args:
      obj (db.Model): Object for which custom attributes should be created.
      cad_cav_pairs (list): List containing string representation of custom
        attributes and their values in form:
        [("<Type>; <Title>; <Option1,...>; <Negative1,...>", <Value>),...]
    """
    flag_enum = all_models.CustomAttributeDefinition.MultiChoiceMandatoryFlags

    for cad, cav in cad_cav_pairs:
      cad_type, cad_title, cad_options, cad_negatives = cad.split(";")
      if cad_negatives:
        cad_negatives = cad_negatives.split(",")
        cad_option_flags = ",".join(
            str(flag_enum.IS_NEGATIVE)
            if o in cad_negatives
            else str(flag_enum.DEFAULT)
            for o in cad_options.split(",")
        )
      else:
        cad_option_flags = None
      lca = ggrc_factories.CustomAttributeDefinitionFactory(
          title=cad_title,
          definition_type=obj._inflector.table_singular,
          definition_id=obj.id,
          attribute_type=cad_type,
          multi_choice_options=cad_options,
          multi_choice_mandatory=cad_option_flags,
      )
      ggrc_factories.CustomAttributeValueFactory(
          custom_attribute=lca,
          attributable=obj,
          attribute_value=cav,
      )

  @ddt.data(
      {
          "cad_cav_pairs": [
              ("Dropdown; LCA 1; yes,no; no", "yes"),
          ],
          "start_status": "Not Started",
          "sent_status": "In Review",
          "end_status": "Completed",
      },
      {
          "cad_cav_pairs": [
              ("Text; LCA 1; empty,not empty; empty", "positive"),
          ],
          "start_status": "Not Started",
          "sent_status": "In Review",
          "end_status": "Completed",
      },
      {
          "cad_cav_pairs": [
              ("Rich Text; LCA 1; empty,not empty; not empty", ""),
          ],
          "start_status": "Not Started",
          "sent_status": "In Review",
          "end_status": "Completed",
      },
      {
          "cad_cav_pairs": [
              ("Dropdown; LCA 1; yes,no; no", "yes"),
              ("Text; LCA 2; empty,not empty; empty", "positive"),
              ("Rich Text; LCA 3; empty,not empty; not empty", ""),
          ],
          "start_status": "Not Started",
          "sent_status": "In Review",
          "end_status": "Completed",
      },
      {
          "cad_cav_pairs": [
              ("Map:Person; LCA 1;empty,not empty;", "Person"),
              ("Date; LCA 2; empty,not empty;", "2020-11-20"),
              ("Checkbox; LCA 3; yes,no;", "yes"),
          ],
          "start_status": "Not Started",
          "sent_status": "In Review",
          "end_status": "Completed",
      },
  )
  @ddt.unpack
  def test_sox_302_status_flow_api(self, cad_cav_pairs, start_status,
                                   sent_status, end_status):
    """Test status change flow via API for SOX 302 objects."""
    with ggrc_factories.single_commit():
      asmt = ggrc_factories.AssessmentFactory(
          status=start_status,
          verification_workflow=VerificationWorkflow.SOX302,
      )
      verifier = ggrc_factories.PersonFactory()
      asmt.add_person_with_role_name(verifier, "Verifiers")
      self._setup_local_custom_attributes(asmt, cad_cav_pairs)
    asmt_id = asmt.id

    self._login()
    response = self.api.put(
        asmt,
        {
            "status": sent_status,
        },
    )

    self.assert200(response)
    asmt = self._refresh_object(asmt.__class__, asmt_id)
    self._assert_status_field(asmt, end_status)

  @ddt.data(
      {
          "cad_cav_pairs": [
              ("Dropdown; LCA 1; yes,no; no", "yes"),
          ],
          "start_status": "Not Started",
          "imported_status": "In Review",
          "end_status": "Completed",
      },
      {
          "cad_cav_pairs": [
              ("Text; LCA 1; empty,not empty; empty", "positive"),
          ],
          "start_status": "Not Started",
          "imported_status": "In Review",
          "end_status": "Completed",
      },
      {
          "cad_cav_pairs": [
              ("Rich Text; LCA 1; empty,not empty; not empty", ""),
          ],
          "start_status": "Not Started",
          "imported_status": "In Review",
          "end_status": "Completed",
      },
      {
          "cad_cav_pairs": [
              ("Dropdown; LCA 1; yes,no; no", "yes"),
              ("Text; LCA 2; empty,not empty; empty", "positive"),
              ("Rich Text; LCA 3; empty,not empty; not empty", ""),
          ],
          "start_status": "Not Started",
          "imported_status": "In Review",
          "end_status": "Completed",
      },
      {
          "cad_cav_pairs": [
              ("Dropdown; LCA 1; yes,no; no", "yes"),
          ],
          "start_status": "Not Started",
          "imported_status": "Completed",
          "end_status": "Completed",
      },
      {
          "cad_cav_pairs": [
              ("Text; LCA 1; empty,not empty; empty", "positive"),
          ],
          "start_status": "Not Started",
          "imported_status": "Completed",
          "end_status": "Completed",
      },
      {
          "cad_cav_pairs": [
              ("Rich Text; LCA 1; empty,not empty; not empty", ""),
          ],
          "start_status": "Not Started",
          "imported_status": "Completed",
          "end_status": "Completed",
      },
      {
          "cad_cav_pairs": [
              ("Dropdown; LCA 1; yes,no; no", "yes"),
              ("Text; LCA 2; empty,not empty; empty", "positive"),
              ("Rich Text; LCA 3; empty,not empty; not empty", ""),
          ],
          "start_status": "Not Started",
          "imported_status": "Completed",
          "end_status": "Completed",
      },
  )
  @ddt.unpack
  def test_sox_302_status_flow_import(self, cad_cav_pairs, start_status,
                                      imported_status, end_status):
    """Test status change flow via import for SOX 302 objects."""
    with ggrc_factories.single_commit():
      asmt = ggrc_factories.AssessmentFactory(
          status=start_status,
          verification_workflow=VerificationWorkflow.SOX302,
      )
      verifier = ggrc_factories.PersonFactory()
      asmt.add_person_with_role_name(verifier, "Verifiers")
      self._setup_local_custom_attributes(asmt, cad_cav_pairs)
    asmt_id = asmt.id

    asmt_data = collections.OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", asmt.slug),
        ("State", imported_status),
    ])

    self._login()
    response = self.import_data(asmt_data)

    self._check_csv_response(response, {})
    asmt = self._refresh_object(asmt.__class__, asmt_id)
    self._assert_status_field(asmt, end_status)
