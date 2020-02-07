# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for Standard and Regulation (ExternalDirective) model."""

import ddt

from ggrc import db
from ggrc.models import all_models
from integration.ggrc import TestCase, api_helper
from integration.ggrc.models import factories


@ddt.ddt
class TestExternalDirectiveGGRC(TestCase):
  """Tests for external_directive model for GGRC users."""

  def setUp(self):
    """setUp, nothing else to add."""
    super(TestExternalDirectiveGGRC, self).setUp()
    self.api = api_helper.Api()

  @ddt.data(all_models.Regulation, all_models.Standard)
  def test_create_directive(self, object_model):
    """Test {0.__name__} object create with internal user."""
    response = self.api.post(object_model, {"title": "new-title"})

    self.assert403(response)
    object_count = object_model.query.filter(
        object_model.title == "new-title"
    ).count()
    self.assertEqual(0, object_count)

  @ddt.data(all_models.Regulation, all_models.Standard)
  def test_update_directive(self, object_model):
    """Test {0.__name__} update with internal user."""
    obj = factories.get_model_factory(object_model.__name__)(title="old-title")
    old_title = obj.title

    response = self.api.put(obj, {"title": "new-title"})

    self.assert403(response)
    obj = object_model.query.get(obj.id)
    self.assertEqual(old_title, obj.title)

  @ddt.data(all_models.Regulation, all_models.Standard)
  def test_delete_directive(self, object_model):
    """Test {0.__name__} delete with internal user."""
    obj = factories.get_model_factory(object_model.__name__)()

    response = self.api.delete(obj)

    self.assert403(response)
    obj = object_model.query.get(obj.id)
    self.assertIsNotNone(obj.title)

  def test_create_external_comment(self):
    """Test unable create external_comments."""
    response_ext_comment = self.api.post(
        all_models.ExternalComment,
        data={
            "external_comment": {
                "external_id": 1,
                "external_slug": "random slug",
                "description": "External comment",
                "context": None,
            }
        }
    )

    self.assert403(response_ext_comment)
    comment_count = db.session.query(all_models.ExternalComment).count()
    self.assertEqual(comment_count, 0)

  @ddt.data(all_models.Regulation, all_models.Standard)
  def test_add_reference_url(self, object_model):
    """Test add reference url to {0.__name__} objects"""
    obj = factories.get_model_factory(object_model.__name__)()
    obj_id, obj_type = obj.id, obj.type
    response = self.api.post(
        all_models.Document, {
            "document": {
                "link": factories.random_str(),
                "title": factories.random_str(),
                "context": None,
            }
        }
    )
    self.assert201(response)
    response = self.api.post(
        all_models.Relationship,
        {
            "relationship": {
                "source": {"id": obj_id, "type": obj_type},
                "destination": {
                    "id": response.json["document"]["id"],
                    "type": "Document",
                },
                "context": None
            },
        }
    )
    self.assert201(response)
