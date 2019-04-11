# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for usage of X-external-user header."""


import json
import ddt
import mock

from ggrc.models import all_models

from integration.ggrc import TestCase
from integration.ggrc.models import factories


@ddt.ddt
@mock.patch('ggrc.settings.ALLOWED_QUERYAPI_APP_IDS', new='ggrcq-id')
@mock.patch('ggrc.settings.AUTHORIZED_DOMAIN', new='example.com')
@mock.patch('ggrc.settings.INTEGRATION_SERVICE_URL', new='endpoint')
@mock.patch('ggrc.settings.EXTERNAL_APP_USER',
            new='External App <external_app@example.com>')
class TestExternalPermissions(TestCase):
  """Tests for external permissions and modified by."""

  def setUp(self):
    """Set up request mock and mock dependencies."""
    super(TestExternalPermissions, self).setUp()
    self.clear_data()
    self.headers = {
        "Content-Type": "application/json",
        "X-requested-by": "GGRC",
        "X-appengine-inbound-appid": "ggrcq-id",
        "X-ggrc-user": json.dumps({"email": "external_app@example.com"}),
        "X-external-user": json.dumps({
            "email": "new_ext_user@example.com",
            "user": "John Doe",
        })
    }
    self.client.get("/login", headers=self.headers)

  def _post(self, url, data, headers):
    return self.client.post(
        url,
        content_type='application/json',
        data=data,
        headers=headers,
    )

  MODELS = [
      all_models.AccessGroup,
      all_models.AccountBalance,
      all_models.Contract,
      all_models.Control,
      all_models.DataAsset,
      all_models.Facility,
      all_models.Issue,
      all_models.Market,
      all_models.Metric,
      all_models.Objective,
      all_models.OrgGroup,
      all_models.Policy,
      all_models.Process,
      all_models.Product,
      all_models.ProductGroup,
      all_models.Program,
      all_models.Project,
      all_models.Regulation,
      all_models.Requirement,
      all_models.Risk,
      all_models.Standard,
      all_models.System,
      all_models.KeyReport,
      all_models.TechnologyEnvironment,
      all_models.Threat,
      all_models.Vendor,
      all_models.Workflow
  ]

  @ddt.data(*MODELS)
  def test_post_modifier(self, model):
    """Test modifier of models when working as external user."""
    model_plural = model._inflector.table_plural
    model_singular = model._inflector.table_singular

    model_data = {
        "title": "{}1".format(model_singular),
        "context": 0,
    }

    if model_plural == "risks":
      model_data["risk_type"] = "some text"
      model_data["external_id"] = factories.SynchronizableExternalId.next()
      model_data["external_slug"] = factories.random_str()

    if model_plural == "controls":
      model_data["assertions"] = '["test assertion"]'
      model_data["external_id"] = factories.SynchronizableExternalId.next()
      model_data["external_slug"] = factories.random_str()
      model_data["review_status"] = all_models.Review.STATES.UNREVIEWED
      model_data["review_status_display_name"] = "some status"

    response = self._post(
        "api/{}".format(model_plural),
        data=json.dumps({
            model_singular: model_data
        }),
        headers=self.headers)
    self.assertEqual(response.status_code, 201)

    ext_person = all_models.Person.query.filter_by(
        email="new_ext_user@example.com"
    ).first()
    ext_person_id = ext_person.id

    # check model modifier
    model_json = response.json[model_singular]
    self.assertEqual(model_json['modified_by']['id'], ext_person_id)

    # check model revision modifier
    model_revision = all_models.Revision.query.filter(
        all_models.Revision.resource_type == model.__name__).order_by(
        all_models.Revision.id.desc()).first()
    self.assertEqual(model_revision.modified_by_id, ext_person_id)

    # check model event modifier
    event = all_models.Event.query.filter(
        all_models.Event.resource_type == model.__name__).order_by(
        all_models.Event.id.desc()).first()
    self.assertEqual(event.modified_by_id, ext_person_id)

  def test_relationship_creation(self):
    """Test external relationship post on behalf of external user."""
    destination = factories.SystemFactory()
    source = factories.MarketFactory()
    relationship_data = json.dumps([{
        "relationship": {
            "source": {"id": source.id,
                       "type": source.type},
            "destination": {"id": destination.id,
                            "type": destination.type},
            "context": {"id": None},
            "is_external": True
        }
    }])
    response = self._post(
        "/api/relationships",
        data=relationship_data,
        headers=self.headers)
    self.assert200(response)

    ext_person = all_models.Person.query.filter_by(
        email="new_ext_user@example.com"
    ).first()
    ext_person_id = ext_person.id

    relationship = all_models.Relationship.query.get(
        response.json[0][-1]["relationship"]["id"])
    self.assertEqual(relationship.source_type, source.type)
    self.assertEqual(relationship.source_id, source.id)
    self.assertEqual(relationship.destination_type, "System")
    self.assertEqual(relationship.destination_id, destination.id)
    self.assertTrue(relationship.is_external)
    self.assertEqual(relationship.modified_by_id, ext_person_id)
    self.assertIsNone(relationship.parent_id)
    self.assertIsNone(relationship.automapping_id)
    self.assertIsNone(relationship.context_id)

    # check that POST on creation of existing relation return 200 code
    response = self._post(
        "/api/relationships",
        data=relationship_data,
        headers=self.headers)
    self.assert200(response)

  def test_external_user_creation(self):
    """Test creation of external user and its role."""
    response = self._post(
        "api/{}".format("markets"),
        data=json.dumps({
            "market": {
                "title": "some market",
                "context": 0
            }
        }),
        headers=self.headers)
    self.assertEqual(response.status_code, 201)

    ext_person = all_models.Person.query.filter_by(
        email="new_ext_user@example.com"
    ).first()
    self.assertEqual(ext_person.system_wide_role, "Creator")

  @ddt.data("new_ext_user@example.com",
            json.dumps({"email": "external_app"}))
  def test_post_invalid_modifier(self, email):
    """Test that validation is working for X-external-user."""
    model = all_models.Market
    self.headers["X-external-user"] = email

    model_plural = model._inflector.table_plural
    model_singular = model._inflector.table_singular
    response = self._post(
        "api/{}".format(model_plural),
        data=json.dumps({
            model_singular: {
                "title": "{}_invalid_1".format(model_singular),
                "context": 0
            }
        }),
        headers=self.headers)
    self.assertEqual(response.status_code, 400)


@mock.patch('ggrc.settings.INTEGRATION_SERVICE_URL', new='endpoint')
@mock.patch('ggrc.settings.AUTHORIZED_DOMAIN', new='google.com')
@mock.patch('ggrc.settings.ALLOWED_QUERYAPI_APP_IDS', new='ggrcq-id')
@mock.patch('ggrc.settings.EXTERNAL_APP_USER',
            new='External App <external_app@example.com>')
class TestExternalAppRequest(TestCase):
  """Clean tests to emulate external app request"""

  def setUp(self):
    """Set up request mock and mock dependencies."""
    super(TestExternalAppRequest, self).setUp()
    self.headers = {
        "Content-Type": "application/json",
        "X-requested-by": "GGRC",
        "X-appengine-inbound-appid": "ggrcq-id",
        "X-ggrc-user": json.dumps({"email": "external_app@example.com"}),
        "X-external-user": json.dumps({
            "email": "anatseuski@google.com",
            "user": "Aleh Natseuski"
        })
    }

  def test_external_user_creation(self):
    """Test creation of external user and its role."""
    response = self.client.post(
        "api/{}".format("markets"),
        data=json.dumps({
            "market": {
                "title": "some market",
                "context": 0
            }
        }),
        headers=self.headers)

    self.assertEqual(response.status_code, 201)

    ext_person = all_models.Person.query.filter_by(
        email="anatseuski@google.com",
        name="Aleh Natseuski"
    ).one()
    self.assertEqual(ext_person.system_wide_role, "Creator")

  @mock.patch('ggrc.settings.ALLOWED_QUERYAPI_APP_IDS', new='ggrcq-id-updated')
  def test_external_wrong_appid(self):
    """Requests with wrong appid handled as regular request

    If user not exists -> bad request
    """

    self.headers["X-ggrc-user"] = json.dumps({"email": "some@google.com"})

    response = self.client.post(
        "api/{}".format("markets"),
        data=json.dumps({
            "market": {
                "title": "some market",
                "context": 0
            }
        }),
        headers=self.headers)

    self.assertEqual(response.status_code, 400)

  def test_external_wrong_ggrc_user(self):
    """Requests with wrong ggrc_user

    If X-ggrc-user not in configured as external -> handled as regular request
    If user not exists -> bad request
    """

    self.headers["X-ggrc-user"] = json.dumps({"email": "some@google.com"})

    response = self.client.post(
        "api/{}".format("markets"),
        data=json.dumps({
            "market": {
                "title": "some market",
                "context": 0
            }
        }),
        headers=self.headers)

    self.assertEqual(response.status_code, 400)
