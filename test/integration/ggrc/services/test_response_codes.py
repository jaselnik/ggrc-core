# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests API response codes."""

import json
from mock import patch

import ddt

from ggrc import db
from ggrc.models import all_models
from integration.ggrc import api_helper
from integration.ggrc.services import TestCase
from integration.ggrc.models import factories


class TestCollectionPost(TestCase):
  """Test response codes for post requests."""

  def setUp(self):
    super(TestCollectionPost, self).setUp()
    self.client.get("/login")

  def _post(self, data):
    return self.client.post(
        self.mock_url(),
        content_type='application/json',
        data=data,
        headers=[('X-Requested-By', 'Unit Tests')],
    )

  def test_post_successful_response(self):
    """Test successful model post call."""
    data = json.dumps({
        'services_test_mock_model': {
            'foo': 'bar',
            'code': '1',
            'validated': 'good',
            'context': None
        }}
    )
    response = self._post(data)
    self.assertStatus(response, 201)

  def test_post_bad_request(self):
    """Test all bad request calls."""
    data = json.dumps({
        'services_test_mock_model': {
            'foo': 'bar',
            'code': '1',
            'validated': 'Value Error',
            'context': None
        }}
    )
    response = self._post(data)
    self.assert400(response)
    # TODO: check why response.json contains unwrapped string
    self.assertEqual(response.json, "raised Value Error")

    data = json.dumps({
        'services_test_mock_model': {
            'foo': 'bar',
            'code': '1',
            'validated': 'Validation Error',
            'context': None
        }}
    )
    response = self._post(data)
    self.assert400(response)
    # TODO: check why response.json contains unwrapped string
    self.assertEqual(response.json, "raised Validation Error")

    response = self._post("what")
    self.assert400(response)
    self.assertEqual(response.json["message"],
                     "The browser (or proxy) sent a request that this server "
                     "could not understand.")

  @patch("ggrc.rbac.permissions.is_allowed_create_for")
  def test_post_forbidden(self, is_allowed):
    """Test posting a forbidden model."""
    is_allowed.return_value = False
    data = json.dumps({
        'services_test_mock_model': {
            'foo': 'bar',
            'code': '1',
            'validated': 'good',
            'context': None
        }}
    )
    response = self._post(data)
    self.assertStatus(response, 403)


@ddt.ddt
class TestMapDeletedObject(TestCase):
  """Test mapping operations for deleted objects."""

  def setUp(self):
    super(TestMapDeletedObject, self).setUp()
    self.api = api_helper.Api()
    with factories.single_commit():
      source_id = factories.RegulationFactory().id
      destination_id = factories.RegulationFactory().id
      del_source_id = factories.RegulationFactory().id
      del_dest_id = factories.RegulationFactory().id

    self.objects = {
        "source": {"type": "Regulation", "id": source_id},
        "destination": {"type": "Regulation", "id": destination_id},
        "deleted_source": {"type": "Regulation", "id": del_source_id},
        "deleted_destination": {"type": "Regulation", "id": del_dest_id},
    }

    with factories.single_commit():
      del_source = all_models.Regulation.query.get(del_source_id)
      del_dest = all_models.Regulation.query.get(del_dest_id)
      db.session.delete(del_dest)
      db.session.delete(del_source)

  @ddt.data(
      ("source", "destination", 201),
      ("source", "deleted_destination", 400),
      ("deleted_source", "destination", 400),
      ("deleted_source", "deleted_destination", 400),
  )
  @ddt.unpack
  def test_map_deleted_object(self, source_key, destination_key, status_code):
    """Status code is {2} when {0} is mapped to {1}."""
    response = self.api.post(
        all_models.Relationship,
        {
            "relationship": {
                "source": self.objects[source_key],
                "destination": self.objects[destination_key],
                "context": None,
            },
        },
    )

    self.assertStatus(response, status_code)
