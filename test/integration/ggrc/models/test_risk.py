# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for Risk model."""

import datetime

from ggrc import db
from ggrc.models import all_models
from integration.ggrc import TestCase
from integration.ggrc import api_helper
from integration.ggrc.models import factories


class TestRiskGGRC(TestCase):
  """Tests for risk model for GGRC users."""

  def setUp(self):
    """setUp, nothing else to add."""
    super(TestRiskGGRC, self).setUp()
    self.api = api_helper.Api()

  def test_create(self):
    """Test risk create with internal user."""
    response = self.api.post(all_models.Risk, {"title": "new-title"})
    self.assert403(response)

    risk_count = all_models.Risk.query.filter(
        all_models.Risk.title == "new-title").count()
    self.assertEqual(0, risk_count)

  def test_update(self):
    """Test risk update with internal user."""
    risk = factories.RiskFactory()
    old_title = risk.title

    response = self.api.put(risk, {"title": "new-title"})
    self.assert403(response)

    risk = all_models.Risk.query.get(risk.id)
    self.assertEqual(old_title, risk.title)

  def test_delete(self):
    """Test risk delete with internal user."""
    risk = factories.RiskFactory()

    response = self.api.delete(risk)
    self.assert403(response)

    risk = all_models.Risk.query.get(risk.id)
    self.assertIsNotNone(risk.title)


class TestRiskGGRCQ(TestCase):
  """Tests for risk model for GGRCQ users."""

  def setUp(self):
    """setUp, nothing else to add."""
    super(TestRiskGGRCQ, self).setUp()
    self.api = api_helper.Api()
    self.api.login_as_external()

  @staticmethod
  def generate_risk_body():
    """Generate JSON body for Risk."""
    body = {
        "id": 10,
        "title": "External risk",
        "risk_type": "External risk",
        "created_at": datetime.datetime(2019, 1, 1, 12, 30),
        "updated_at": datetime.datetime(2019, 1, 2, 13, 30),
        "external_id": 10,
        "external_slug": "external_slug",
        "review_status": all_models.Review.STATES.UNREVIEWED,
        "review_status_display_name": "some status",
    }

    return body

  @staticmethod
  def generate_comment_body():
    """Generate JSON body for Risk comment."""
    body = {
        "external_id": 1,
        "external_slug": factories.random_str(),
        "description": "External comment",
        "context": None,
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

    response = self.api.post(all_models.Risk, {
        "risk": risk_body
    })

    self.assertEqual(201, response.status_code)

    risk = all_models.Risk.query.get(risk_body["id"])
    self.assert_instance(risk_body, risk)

  # pylint: disable=invalid-name
  def test_create_without_review_status(self):
    """Check risk creation without review_status"""
    risk_body = self.generate_risk_body()
    del risk_body['review_status']

    response = self.api.post(all_models.Risk, risk_body)
    self.assert400(response)

  # pylint: disable=invalid-name
  def test_create_with_empty_review_status(self):
    """Check risk creation with empty review_status"""
    risk_body = self.generate_risk_body()
    risk_body['review_status'] = None

    response = self.api.post(all_models.Risk, risk_body)
    self.assert400(response)

  # pylint: disable=invalid-name
  def test_create_without_review_status_display_name(self):
    """Check risk creation without review_status_display_name"""
    risk_body = self.generate_risk_body()
    del risk_body['review_status_display_name']

    response = self.api.post(all_models.Risk, risk_body)
    self.assert400(response)

  # pylint: disable=invalid-name
  def test_create_with_empty_review_status_display_name(self):
    """Check risk creation with empty review_status_display_name"""
    risk_body = self.generate_risk_body()
    risk_body['review_status_display_name'] = None

    response = self.api.post(all_models.Risk, risk_body)
    self.assert400(response)

  def test_update(self):
    """Test risk update with external user."""
    with factories.single_commit():
      risk_id = factories.RiskFactory().id

    new_values = {
        "title": "New risk",
        "created_at": datetime.datetime(2019, 1, 3, 14, 30),
        "updated_at": datetime.datetime(2019, 1, 4, 14, 30),
        "review_status": all_models.Review.STATES.UNREVIEWED,
        "review_status_display_name": "some status",
    }

    risk = all_models.Risk.query.get(risk_id)
    response = self.api.put(risk, new_values)

    self.assertEqual(200, response.status_code)

    risk = all_models.Risk.query.get(risk_id)
    self.assert_instance(new_values, risk)

  # pylint: disable=invalid-name
  def test_update_review_status_to_null(self):
    """Test review_status is not set to None"""
    risk = factories.RiskFactory()
    response = self.api.put(risk, {"review_status": None})
    self.assert400(response)
    self.assertEqual(response.json["message"],
                     "Review status for the object is not specified")

    risk = db.session.query(all_models.Risk).get(risk.id)
    self.assertIsNotNone(risk.external_id)

  # pylint: disable=invalid-name
  def test_update_review_status(self):
    """Test review_status is updated"""
    risk = factories.RiskFactory()
    new_value = all_models.Review.STATES.REVIEWED
    self.api.put(risk, {"review_status": new_value,
                        "review_status_display_name": "some status"})

    risk = db.session.query(all_models.Risk).get(risk.id)
    self.assertEquals(risk.review_status, new_value)

  # pylint: disable=invalid-name
  def test_update_review_status_display_name_to_null(self):
    """Test review_status_display_name is not set to None"""
    risk = factories.RiskFactory()
    response = self.api.put(risk, {"review_status_display_name": None})
    self.assert400(response)
    self.assertEqual(response.json["message"],
                     "Review status display for the object is not specified")

    risk = db.session.query(all_models.Risk).get(risk.id)
    self.assertIsNotNone(risk.external_id)

  # pylint: disable=invalid-name
  def test_update_review_status_display_name(self):
    """Test review_status_display_name is updated"""
    risk = factories.RiskFactory()
    new_value = "test123"
    self.api.put(risk, {"review_status_display_name": new_value,
                        "review_status": all_models.Review.STATES.UNREVIEWED})

    risk = db.session.query(all_models.Risk).get(risk.id)
    self.assertEquals(risk.review_status_display_name, new_value)

  def test_create_comments(self):
    """Test external comments creation for risk."""
    risk_body = self.generate_risk_body()
    response = self.api.post(all_models.Risk, {
        "risk": risk_body,
    })
    self.assertEqual(response.status_code, 201)

    comment_body = self.generate_comment_body()
    response = self.api.post(all_models.ExternalComment, {
        "external_comment": comment_body,
    })

    self.assertEqual(response.status_code, 201)
    comment = db.session.query(all_models.ExternalComment.description).one()
    self.assertEqual(comment, (comment_body["description"],))

    risk_id = db.session.query(all_models.Risk.id).one()[0]
    comment_id = db.session.query(all_models.ExternalComment.id).one()[0]

    response = self.api.post(all_models.Relationship, {
        "relationship": {
            "source": {"id": risk_id, "type": "Risk"},
            "destination": {"id": comment_id, "type": "ExternalComment"},
            "context": None,
            "is_external": True
        },
    })
    self.assertEqual(response.status_code, 201)
    rels = all_models.Relationship.query.filter_by(
        source_type="Risk",
        source_id=risk_id,
        destination_type="ExternalComment",
        destination_id=comment_id
    )
    self.assertEqual(rels.count(), 1)

  def test_get_risk_external_comment(self):
    """Test query endpoint for risk ExternalComments."""
    with factories.single_commit():
      risk = factories.RiskFactory()
      comment = factories.ExternalCommentFactory(description="comment")
      factories.RelationshipFactory(source=risk, destination=comment)

    request_data = [{
        "filters": {
            "expression": {
                "object_name": "Risk",
                "op": {
                    "name": "relevant"
                },
                "ids": [risk.id]
            },
        },
        "object_name":"ExternalComment",
        "order_by": [{"name": "created_at", "desc": "true"}]
    }]
    response = self.api.send_request(
        self.api.client.post,
        data=request_data,
        api_link="/query"
    )
    self.assert200(response)
    response_data = response.json[0]["ExternalComment"]
    self.assertEqual(response_data["count"], 1)
    self.assertEqual(response_data["values"][0]["description"], "comment")
