# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test for review comments."""

import ddt

from ggrc.models import all_models

from integration.ggrc import TestCase
from integration.ggrc.models import factories
from integration.ggrc.review import generate_review_object


@ddt.ddt
class TestCommentsForReview(TestCase):
  """Test generate comments for review."""

  @ddt.data(
      all_models.Standard,
      all_models.Regulation,
      all_models.Program,
  )
  def test_create_comment_post(self, model):
    """Test create review comment for {}."""
    obj = factories.get_model_factory(model.__name__)()
    obj_id = obj.id
    self.assertEqual(0, len(obj.related_objects(_types=["Comment"])))
    resp, _ = generate_review_object(obj, email_message="Test message")
    self.assertEqual(201, resp.status_code)
    obj = model.query.get(obj_id)
    comments = list(obj.related_objects(_types=["Comment"]))
    self.assertEqual(1, len(comments))
    self.assertEqual(
        u"<p>Review requested from</p><p>user@example.com</p>"
        u"<p>with a comment: Test message</p>",
        comments[0].description
    )

  @ddt.data(
      all_models.Standard,
      all_models.Regulation,
      all_models.Program,
  )
  def test_put_comment_empty_text(self, model):
    """Test update review comment for {}."""
    obj = factories.get_model_factory(model.__name__)()
    obj_id = obj.id
    resp, _ = generate_review_object(obj, email_message="Test1")
    self.assertEqual(201, resp.status_code)
    resp, _ = generate_review_object(obj, email_message="")
    self.assertEqual(201, resp.status_code)
    obj = model.query.get(obj_id)
    comments = list(obj.related_objects(_types=["Comment"]))
    self.assertEqual(1, len(comments))
    self.assertEqual(
        u"<p>Review requested from</p><p>user@example.com</p>"
        u"<p>with a comment: Test1</p>",
        comments[0].description
    )
