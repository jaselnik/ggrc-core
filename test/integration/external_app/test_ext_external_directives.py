# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for Standard & Regulation model as external user."""

import datetime

import ddt

from ggrc import db
from ggrc.models import all_models

from integration.external_app.external_api_helper import ExternalApiClient

from integration.ggrc import TestCase
from integration.ggrc.models import factories


@ddt.ddt
class TestSyncServiceExternalDirective(TestCase):
  """Tests for external_directive model for GGRCQ users."""

  def setUp(self):
    """setUp, nothing else to add."""
    super(TestSyncServiceExternalDirective, self).setUp()
    self.api = ExternalApiClient()

  @staticmethod
  def generate_directive_body(kind):
    """Generate JSON body for Directive object."""
    test_date = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    body = {
        "id": 10,
        "title": "External directive",
        "created_at": test_date,
        "updated_at": test_date,
        "external_id": 10,
        "external_slug": "external_slug",
        "kind": kind,
    }

    return body

  @staticmethod
  def generate_comment_body():
    """Generate JSON body for ExternalDirective comment."""
    body = {
        "external_id": 1,
        "external_slug": factories.random_str(),
        "description": "External comment",
        "context": None,
    }

    return body

  def assert_instance(self, expected, directive):
    """Compare expected response body with actual."""
    directive_values = {}
    expected_values = {}

    for field, value in expected.items():
      expected_values[field] = value
      attr = getattr(directive, field, None)
      if isinstance(attr, datetime.datetime):
        # this is datetime object
        attr = attr.strftime("%Y-%m-%d")
      directive_values[field] = attr

    self.assertEqual(expected_values, directive_values)

  @ddt.data(all_models.Regulation, all_models.Standard)
  def test_create_directive(self, object_model):
    """Test create {0.__name__} with external user."""
    object_type = object_model.__name__
    directive_body = self.generate_directive_body(kind=object_type)

    response = self.api.post(
        object_model,
        data={object_type.lower(): directive_body},
    )

    self.assert201(response)
    directive = object_model.query.get(directive_body["id"])
    self.assert_instance(directive_body, directive)

  @ddt.data(all_models.Regulation, all_models.Standard)
  def test_update_directive(self, object_model):
    """Test {0.__name__} update with external user."""
    object_type = object_model.__name__
    test_date = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    directive_id = factories.get_model_factory(object_type)().id
    created_at = test_date
    updated_at = test_date
    new_values = {
        "title": "New directive",
        "created_at": created_at,
        "updated_at": updated_at,
    }
    directive = object_model.query.get(directive_id)

    response = self.api.put(directive, directive.id, new_values)

    self.assert200(response)
    directive = object_model.query.get(directive_id)
    self.assert_instance(new_values, directive)

  @ddt.data(all_models.Regulation, all_models.Standard)
  def test_create_directive_comments(self, object_model):
    """Test external comments creation for {0.__name__}."""
    object_type = object_model.__name__
    directive_body = self.generate_directive_body(kind=object_type)
    response = self.api.post(
        object_model,
        data={object_type.lower(): directive_body}
    )
    self.assert201(response)
    comment_body = self.generate_comment_body()

    response_ext_comment = self.api.post(
        all_models.ExternalComment,
        data={"external_comment": comment_body}
    )

    self.assert201(response_ext_comment)
    comment = db.session.query(all_models.ExternalComment.description).one()
    self.assertEqual(comment, (comment_body["description"],))
    directive_id = db.session.query(object_model.id).one()[0]
    comment_id = db.session.query(all_models.ExternalComment.id).one()[0]

    response_relationship = self.api.post(
        all_models.Relationship,
        data={
            "relationship": {
                "source": {"id": directive_id, "type": object_type},
                "destination": {"id": comment_id, "type": "ExternalComment"},
                "context": None,
                "is_external": True
            },
        }
    )

    self.assert201(response_relationship)
    rels = all_models.Relationship.query.filter_by(
        source_type=object_type,
        source_id=directive_id,
        destination_type="ExternalComment",
        destination_id=comment_id
    )
    self.assertEqual(rels.count(), 1)

  @ddt.data(all_models.Regulation, all_models.Standard)
  def test_get_directive_external_comment(self, object_model):
    """Test query endpoint for {0.__name__} ExternalComments."""
    # pylint: disable=invalid-name
    object_type = object_model.__name__
    with factories.single_commit():
      directive = factories.get_model_factory(object_type)()
      comment = factories.ExternalCommentFactory(description="comment")
      factories.RelationshipFactory(source=directive, destination=comment)
    request_data = [{
        "filters": {
            "expression": {
                "object_name": object_type,
                "op": {
                    "name": "relevant"
                },
                "ids": [directive.id]
            },
        },
        "object_name":"ExternalComment",
        "order_by": [{"name": "created_at", "desc": "true"}],
    }]

    response = self.api.post(
        object_model,
        data=request_data,
        url="/query",
    )

    self.assert200(response)
    response_data = response.json[0]["ExternalComment"]
    self.assertEqual(response_data["count"], 1)
    self.assertEqual(response_data["values"][0]["description"], "comment")

  @ddt.data(all_models.Regulation, all_models.Standard)
  def test_search_directive_by_users(self, object_model):
    """Test query endpoint for {0.__name__} by users."""
    object_type = object_model.__name__
    with factories.single_commit():
      person = factories.PersonFactory()
      factories.get_model_factory(object_type)(**{"created_by": person})
    request_data = [{
        "filters": {
            "expression": {
                "left": {
                    "left": "Created By",
                    "op": {"name": "~"},
                    "right": person.email,
                },
                "op": {"name": "AND"},
                "right": {
                    "left": "Status",
                    "op": {"name": 'IN'},
                    "right": ["Active", "Draft", "Deprecated"],
                }
            }
        },
        "object_name": object_type,
        "order_by": [{"name": "updated_at", "desc": "true"}],
    }]

    response = self.api.post(
        object_model,
        data=request_data,
        url="/query",
    )

    self.assert200(response)
    response_data = response.json[0][object_type]
    self.assertEqual(response_data["count"], 1)
    self.assertEqual(
        response_data["values"][0]["created_by"]['email'],
        person.email,
    )
