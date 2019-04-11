# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for Risk model."""

import datetime
import json
import unittest

from ggrc.models import all_models
from integration.ggrc import TestCase
from integration.ggrc import api_helper
from integration.ggrc.models import factories
from integration.ggrc_basic_permissions.models.factories import UserRoleFactory


def generate_creator():
  """Create user with Global Creator permissions."""
  role = all_models.Role.query.filter(
      all_models.Role.name == "Creator").one()
  user = factories.PersonFactory()

  UserRoleFactory(role=role, person=user)

  return user


@unittest.skip("Need investigation.")
class TestRiskGGRC(TestCase):
  """Tests for risk model for GGRC users."""

  def setUp(self):
    """setUp, nothing else to add."""
    super(TestRiskGGRC, self).setUp()
    self.user = generate_creator()
    self.api = api_helper.ExternalApi()
    self.api.headers["X-GGRC-User"] = json.dumps({
        "email": self.user.email,
        "name": self.user.name
    })
    del self.api.headers["X-External-User"]

  def test_create(self):
    """Test risk create with internal user."""
    data = {"risk": {"title": "new-title", "risk_type": "risk"}}
    response = self.api.post("/api/risks", data)
    self.assert403(response)

    risk_count = all_models.Risk.query.filter(
        all_models.Risk.title == "new-title").count()
    self.assertEqual(0, risk_count)

  def test_update(self):
    """Test risk update with internal user."""
    risk = factories.RiskFactory()
    url = "/api/risks/%s" % risk.id
    old_title = risk.title

    data = {"risk": {"title": "new-title", "risk_type": "risk"}}
    response = self.api.put(url, data)
    self.assert403(response)

    risk = all_models.Risk.query.get(risk.id)
    self.assertEqual(old_title, risk.title)

  def test_delete(self):
    """Test risk delete with internal user."""
    risk = factories.RiskFactory()
    url = "/api/risks/%s" % risk.id

    response = self.api.delete(url)
    self.assert403(response)

    risk = all_models.Risk.query.get(risk.id)
    self.assertIsNotNone(risk)


@unittest.skip("Need investigation.")
class TestRiskGGRCQ(TestCase):
  """Tests for risk model for GGRCQ users."""

  def setUp(self):
    """setUp, nothing else to add."""
    super(TestRiskGGRCQ, self).setUp()
    self.api = api_helper.ExternalApi()

  @staticmethod
  def generate_risk_body():
    """Generate JSON body for Risk."""
    body = {
        "id": 10,
        "title": "External risk",
        "slug": "Slug",
        "description": "Description",
        "risk_type": "External risk",
        "created_at": datetime.datetime(2019, 1, 1, 12, 30),
        "updated_at": datetime.datetime(2019, 1, 2, 13, 30),
        "external_id": 10,
        "external_slug": "external_slug"
    }

    return body

  def assert_instance(self, expected, risk):
    """Compare expected response body with actual."""
    risk_values = {}
    expected_values = {}

    for field, value in expected.items():
      expected_values[field] = value
      risk_values[field] = getattr(risk, field, None)

    self.assertEqual(expected_values, risk_values)

  def test_create(self):
    """Test risk create with external user."""
    risk_body = self.generate_risk_body()

    response = self.api.post("/api/risks", {"risk": risk_body})
    self.assertEqual(201, response.status_code)

    risk = all_models.Risk.query.get(risk_body["id"])
    self.assert_instance(risk_body, risk)

  def test_update(self):
    """Test risk update with external user."""
    risk = factories.RiskFactory()
    url = "/api/risks/%s" % risk.id

    risk_body = self.generate_risk_body()
    risk_body["id"] = risk.id
    response = self.api.put(url, {"risk": risk_body})
    self.assert200(response)

    risk = all_models.Risk.query.get(risk.id)
    self.assert_instance(risk_body, risk)

  def test_delete(self):
    """Test risk delete with external user."""
    risk = factories.RiskFactory()
    url = "/api/risks/%s" % risk.id

    response = self.api.delete(url)
    self.assert200(response)

    risk = all_models.Risk.query.get(risk.id)
    self.assertIsNone(risk)
