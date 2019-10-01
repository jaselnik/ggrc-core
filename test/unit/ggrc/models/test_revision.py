# Copyright (C) 2019 Google Inc.

# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Unittests for Revision model """

import datetime
import unittest

import ddt
import mock

from ggrc.models import all_models
from ggrc.utils.revisions_diff import builder as revisions_diff


@ddt.ddt
class TestCheckPopulatedContent(unittest.TestCase):
  """Unittest checks populated content."""
  # pylint: disable=invalid-name

  LIST_OF_REQUIRED_ROLES = [
      "Principal Assignees",
      "Secondary Assignees",
      "Primary Contacts",
      "Secondary Contacts",
  ]

  def setUp(self):
    super(TestCheckPopulatedContent, self).setUp()
    self.object_id = 1
    self.user_id = 123

  @ddt.data(
      # content, expected
      (None, None, "Control"),
      ('principal_assessor', ("Principal Assignees", 1), "Control"),
      ('secondary_assessor', ("Secondary Assignees", 2), "Control"),
      ('contact', ("Primary Contacts", 3), "AccessGroup"),
      ('secondary_contact', ("Secondary Contacts", 4), "AccessGroup"),
      ('contact', ("Control Operators", 3), "Control"),
      ('secondary_contact', ("Control Owners", 4), "Control"),
      ('owners', ("Admin", 5), "Control"),
  )
  @ddt.unpack
  def test_check_populated_content(self, key, role, object_type):
    """Test populated content for revision if ACL doesn't exists."""
    content = {}
    if key:
      content[key] = {"id": self.user_id}
    expected = {"access_control_list": []}
    role_dict = {}
    if role:
      role_name, role_id = role
      expected["access_control_list"].append({
          "display_name": role_name,
          "ac_role_id": role_id,
          "context_id": None,
          "created_at": None,
          "object_type": object_type,
          "updated_at": None,
          "object_id": self.object_id,
          "modified_by_id": None,
          "person_id": self.user_id,
          # Frontend require data in such format
          "person": {
              "id": self.user_id,
              "type": "Person",
              "href": "/api/people/{}".format(self.user_id)
          },
          "modified_by": None,
          "id": None,
      })
      role_dict[role_id] = role_name
    obj = mock.Mock()
    obj.id = self.object_id
    obj.__class__.__name__ = object_type
    revision = all_models.Revision(obj, mock.Mock(), mock.Mock(), content)

    with mock.patch("ggrc.access_control.role.get_custom_roles_for",
                    return_value=role_dict) as get_roles:
      self.assertEqual(revision.populate_acl(), expected)
      get_roles.assert_called_once_with(object_type)

  @ddt.data(None, {}, {"id": None})
  def test_populated_content_no_user(self, user_dict):
    """Test populated content for revision without user id."""
    object_type = "Control"
    content = {"principal_assessor": user_dict}
    role_dict = {1: "Principal Assignees"}
    expected = {"access_control_list": []}
    obj = mock.Mock()
    obj.id = self.object_id
    obj.__class__.__name__ = object_type
    revision = all_models.Revision(obj, mock.Mock(), mock.Mock(), content)
    with mock.patch("ggrc.access_control.role.get_custom_roles_for",
                    return_value=role_dict) as get_roles:
      self.assertEqual(revision.populate_acl(), expected)
      get_roles.assert_called_once_with(object_type)

  @ddt.data(
      ("principal_assessor", "Control"),
      ("secondary_assessor", "Control"),
      ("contact", "Control"),
      ("secondary_contact", "Control"),
      ("contact", "AccessGroup"),
      ("secondary_contact", "AccessGroup"),
  )
  @ddt.unpack
  def test_populated_content_no_role(self, key, object_type):
    """Test populated content for revision without roles."""
    content = {key: {"id": self.user_id}}
    expected = {"access_control_list": []}
    obj = mock.Mock()
    obj.id = self.object_id
    obj.__class__.__name__ = object_type
    revision = all_models.Revision(obj, mock.Mock(), mock.Mock(), content)
    with mock.patch("ggrc.access_control.role.get_custom_roles_for",
                    return_value={}) as get_roles:
      self.assertEqual(revision.populate_acl(), expected)
      get_roles.assert_called_once_with(object_type)

  @ddt.data({
      "url": "www.url-foo.com",
      "reference_url": "www.refurl-bar.com",
      "created_at": "2017-07-15T15:49:14",
      "updated_at": "2017-08-20T13:32:42",
  }, {
      "url": "www.url-foo.com",
      "reference_url": "www.refurl-bar.com",
  })
  def test_populated_content_urls(self, content):
    """Test populated content for revision with urls."""
    dates_in_content = "created_at" in content

    if dates_in_content:
      expected_created_at = "2017-07-15T15:49:14"
      expected_updated_at = "2017-08-20T13:32:42"
    else:
      # Revision's own dates should be used as a fallback
      expected_created_at = "2017-11-12T13:14:15"
      expected_updated_at = "2018-11-12T13:14:15"

    expected = [{'display_name': 'www.url-foo.com',
                 'kind': 'REFERENCE_URL',
                 'id': None,
                 'link': 'www.url-foo.com',
                 'title': 'www.url-foo.com',
                 'created_at': expected_created_at,
                 'updated_at': expected_updated_at, },
                {'display_name': 'www.refurl-bar.com',
                 'kind': 'REFERENCE_URL',
                 'id': None,
                 'link': 'www.refurl-bar.com',
                 'title': 'www.refurl-bar.com',
                 'created_at': expected_created_at,
                 'updated_at': expected_updated_at, }]

    obj = mock.Mock()
    obj.id = self.object_id
    obj.__class__.__name__ = "Control"
    revision = all_models.Revision(obj, mock.Mock(), mock.Mock(), content)
    revision.created_at = datetime.datetime(2017, 11, 12, 13, 14, 15)
    revision.updated_at = datetime.datetime(2018, 11, 12, 13, 14, 15)

    with mock.patch("ggrc.access_control.role.get_custom_roles_for",
                    return_value={}):
      self.assertEqual(revision.populate_reference_url()["reference_url"],
                       expected)

  @ddt.data([{"label": "label"}, [{"id": None, "name": "label"}]],
            [{"label": ""}, []],
            [{"label": None}, []])
  @ddt.unpack
  def test_populated_content_labels(self, content, expected):
    """Test populated content for old revision with label."""
    obj = mock.Mock()
    obj.id = self.object_id
    obj.__class__.__name__ = "Control"

    revision = all_models.Revision(obj, mock.Mock(), mock.Mock(), content)

    with mock.patch("ggrc.access_control.role.get_custom_roles_for",
                    return_value={},):
      self.assertEqual(revision.populate_labels()["labels"],
                       expected)

  @ddt.data(
      [{"status": "Active"}, {"status": "Active"}, "AccessGroup"],
      [{"status": "Not Launched"}, {"status": "Draft"}, "AccountBalance"],
      [{"status": "Deprecated"}, {"status": "Deprecated"}, "Requirement"],
      [{"status": "Draft"}, {"status": "Draft"}, "Control"],
      [{"status": "Effective"}, {"status": "Active"}, "DataAsset"],
      [{"status": "Final"}, {"status": "Active"}, "Directive"],
      [{"status": "In Scope"}, {"status": "Active"}, "Facility"],
      [{"status": "Ineffective"}, {"status": "Active"}, "Issue"],
      [{"status": "Launched"}, {"status": "Active"}, "Market"],
      [{"status": "Not in Scope"}, {"status": "Draft"}, "Objective"],
      [{"status": "Not Launched"}, {"status": "Draft"}, "OrgGroup"],
      [{"status": "Not Launched"}, {"status": "Draft"}, "Product"],
      [{"status": "Not Launched"}, {"status": "Draft"}, "Program"],
      [{"status": "Not Launched"}, {"status": "Draft"}, "Project"],
      [{"status": "Not Launched"}, {"status": "Draft"}, "Requirement"],
      [{"status": "Not Launched"}, {"status": "Draft"}, "System"],
      [{"status": "Not Launched"}, {"status": "Draft"}, "KeyReport"],
      [{"status": "Not Launched"}, {"status": "Draft"}, "Vendor"],
      [{"status": "Not Launched"}, {"status": "Draft"}, "Risk"],
      [{"status": "Not Launched"}, {"status": "Draft"}, "Threat"],
      [{"status": "Not Launched"}, {}, "Regulation"]
  )
  @ddt.unpack
  def test_populated_status(self, content, expected_content, resource_type):
    """Test populated content with status '{0}' to '{1}' in Model '{2}'."""
    obj = mock.Mock()
    obj.id = self.object_id
    obj.__class__.__name__ = resource_type

    revision = all_models.Revision(obj, mock.Mock(), mock.Mock(), content)
    self.assertEqual(revision.populate_status(), expected_content)

  @ddt.data(
      [{"os_state": "Reviewed"}, {"review_status": "Reviewed"}, "Control"],
      [{"os_state": "Unreviewed"}, {"review_status": "Unreviewed"}, "Control"],
      [{"os_state": "Reviewed"}, {"review_status": "Reviewed"}, "Issue"],
      [{"os_state": "Unreviewed"}, {"review_status": "Unreviewed"}, "Market"],
      [{"os_state": None}, {"review_status": "Unreviewed"}, "Control"]
  )
  @ddt.unpack
  def test_populated_review_status(self, content, expected_content,
                                   resource_type):
    """Populated content os_state '{0}' to review_status '{1}' in '{2}'."""
    obj = mock.Mock()
    obj.id = self.object_id
    obj.__class__.__name__ = resource_type

    revision = all_models.Revision(obj, mock.Mock(), mock.Mock(), content)
    self.assertEqual(revision.populate_review_status(), expected_content)

  def test_populate_type(self):
    """Test populated content with type missing in _content field"""
    obj = mock.Mock()
    obj.id = self.object_id
    obj.__class__.__name__ = "Program"

    revision = all_models.Revision(obj, mock.Mock(), mock.Mock(), {})
    self.assertEqual(revision.populate_type(), {"type": "Program"})

  @ddt.data(
      [
          {"review_status": "a"},
          {"review_status": "a", "review_status_display_name": "a"},
          "Control"
      ],
      [
          {"review_status": "a", "review_status_display_name": "b"},
          {"review_status": "a", "review_status_display_name": "b"},
          "Control"
      ],
      [
          {"review_status": "a", "review_status_display_name": None},
          {"review_status": "a", "review_status_display_name": None},
          "Control"
      ],
      [
          {"review_status": "a"},
          {"review_status": "a"},
          "Issue"
      ],
      [
          {"xx": "q"},
          {},
          "Facility"
      ],
  )
  @ddt.unpack
  def test_populated_review_status_display_name(self, content,
                                                expected_result,
                                                resource_type):
    """Populated from '{0}' to '{1}' for {2}"""
    obj = mock.Mock()
    obj.id = self.object_id
    obj.__class__.__name__ = resource_type

    revision = all_models.Revision(obj, mock.Mock(), mock.Mock(), content)

    # emulate situation when review_status is already populated if exists
    populated = dict()
    if 'review_status' in content:
      populated['review_status'] = content['review_status']

    # ensure that correct review_status_display_name is added for Control
    revision.populate_review_status_display_name(populated)
    self.assertEqual(populated, expected_result)

  @ddt.data(
      # Test System
      ["System", {"readonly": True}, {"readonly": True}],
      ["System", {"readonly": False}, {"readonly": False}],
      ["System", {}, {"readonly": False}],
      # Process and System share the same table "systems",
      # so we need to ensure that no value will be set for Process
      ["Process", {}, {}],
      # Test candidates to be extended with WithReadonlyAccess functionality
      ["Control", {}, {}],
      ["Risk", {}, {}],
      ["Process", {}, {}],
      ["KeyReport", {}, {}],
      # Test other objects
      ["Market", {}, {}],
  )
  @ddt.unpack
  def test_populated_readonly(self, resource_type, content, expected_content):
    """Populated readonly if content={1} for {0}."""
    obj = mock.Mock()
    obj.id = self.object_id
    obj.__class__.__name__ = resource_type

    revision = all_models.Revision(obj, mock.Mock(), mock.Mock(), content)
    self.assertEqual(revision.populate_readonly(), expected_content)

  @ddt.data(
      ({}, {}),
      ({"document_evidence": []}, {"documents_file": []}),
      (
          {"document_evidence": [
              {"link": u"aa", "title": u"bb", "display_name": u"bb"},
          ]},
          {"documents_file": [
              {"link": u"aa", "title": u"bb", "display_name": u"aa bb"},
          ]}
      ),
      (
          {"document_evidence": [
              {"link": u"aa", "title": u"bb", "display_name": u"bb"},
              {"link": u"aa\u5555", "title": u"", "display_name": u""},
          ]},
          {"documents_file": [
              {"link": u"aa", "title": u"bb", "display_name": u"aa bb"},
              {"link": u"aa\u5555", "title": u"", "display_name": u"aa\u5555"},
          ]}
      ),
  )
  @ddt.unpack
  def test_populated_content_evidence(self, content, expected_evidence):
    """Test display names for document evidence in revision content.

    The display name should contain link and title, like we used to have in
    slugs.
    Document epic: 'document_evidence' renamed to 'documents_file'
    """
    obj = mock.Mock()
    obj.id = self.object_id
    obj.__class__.__name__ = "Control"

    revision = all_models.Revision(obj, mock.Mock(), mock.Mock(), content)

    self.assertEqual(
        # pylint: disable=protected-access
        revision._document_evidence_hack(),
        expected_evidence,
    )

  @ddt.data(
      [],
      [{}],
      [{"parent_id": None}],
      [{"parent_id": 5}],
      [{"parent_id": 0}],
      [{"parent_id": None}, {}],
      [{"parent_id": None}, {"parent_id": 1}, {}],
      [{"parent_id": None}, {"parent_id": 1}, {"parent_id": 2}],
  )
  def test_internal_acl_filter(self, acl_entries):
    """Test filtering of internal roles for {}."""
    obj = mock.Mock()
    obj.id = self.object_id
    obj.__class__.__name__ = "Control"
    for acl_entry in acl_entries:
      acl_entry.update({"person_id": 1, "ac_role_id": 1})

    content = {"access_control_list": acl_entries}

    role_dict = mock.MagicMock()
    with mock.patch("ggrc.access_control.role.get_custom_roles_for",
                    return_value=role_dict):
      revision = all_models.Revision(obj, mock.Mock(), mock.Mock(), content)

      for acl in revision.content["access_control_list"]:
        self.assertIsNone(acl.get("parent_id"))

  @ddt.data(
      (
          True,
          {},
          {}
      ),
      (
          True,
          {'key_1': 1, 'key_2': 2, 'key_3': 3},
          {'key_1': 1, 'key_2': 2, 'key_3': 3}
      ),
      (
          True,
          {'key_1': 1, 'key_2': 2, 'key_3': None},
          {'key_1': 1, 'key_2': 2}
      ),
      (
          False,
          {'key_1': 1, 'key_2': 2, 'key_3': 3},
          {'key_1': 1, 'key_2': 2, 'key_3': 33}
      ),
      (
          False,
          {'key_1': 1, 'key_2': 2, 'key_3': 3},
          {'key_1': 1, 'key_2': 2}
      ),
      (
          False,
          {'key_1': 1, 'key_2': 2},
          {'key_1': 1, 'key_2': 2, 'key_3': 3},
      ),

  )
  @ddt.unpack
  def test_is_identical_revision(self, expected_result,
                                 context_1,
                                 context_2):
    """Test checks work of is_identical_revision function"""
    self.assertEqual(
        revisions_diff.is_identical_revision(None, context_1, context_2),
        expected_result
    )
