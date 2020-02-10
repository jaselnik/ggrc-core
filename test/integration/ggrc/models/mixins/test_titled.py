# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration test for Titled mixin"""

import ddt

from ggrc.models import all_models

from integration.ggrc import TestCase
from integration.ggrc.api_helper import Api


@ddt.ddt
class TestTitledMixin(TestCase):
  """Test cases for Labeled mixin"""

  def setUp(self):
    super(TestTitledMixin, self).setUp()
    self.api = Api()
    self.api.login_as_normal()

  def test_post_no_title(self):
    """Test object creation request without title key"""
    response = self.api.post(
        all_models.Issue,
        {'issue': {"description": "desc", "due_date": "2022-11-22"}}
    )

    self.assert400(response)
    self.assertEqual(response.json, "'title' must be specified")

  def test_post_title_is_null(self):
    """Test object creation request title=null"""
    response = self.api.post(
        all_models.Issue,
        {'issue': {"description": "desc",
                   "title": None,
                   "due_date": "2022-11-22"}}
    )

    self.assert400(response)
    self.assertEqual(response.json, "'title' must be specified")

  @ddt.data(
      ('a', 'a'),
      ('  a  ', 'a'),
      ('', ''),
      ('  ', ''),
  )
  @ddt.unpack
  def test_post_title_is_valid(self, title, expected):
    """Test object creation request title={0!r}"""
    response = self.api.post(
        all_models.Issue,
        {'issue': {"description": "desc",
                   "title": title,
                   "due_date": "2022-11-22"}}
    )

    self.assertStatus(response, 201)
    issue = all_models.Issue.query.get(
        response.json['issue']['id']
    )
    self.assertEqual(issue.title, expected)
