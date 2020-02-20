# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test import and export of objects with custom attributes."""

import itertools
import collections

import ddt

from ggrc import models
from ggrc.models import all_models
from ggrc.models.mixins import ScopeObject
from integration.ggrc import TestCase
from integration.ggrc.models import factories


@ddt.ddt
class TestACLImportExport(TestCase):
  """Test import and export with custom attributes."""
  _random_emails = [
      "user_1@example.com",
      "user_2@example.com",
      "user_3@example.com",
      "user_4@example.com",
  ]

  def test_single_acl_entry(self):
    """Test ACL column import with single email."""
    role = factories.AccessControlRoleFactory(object_type="Regulation")
    role_id = role.id

    response = self.import_data(collections.OrderedDict([
        ("object_type", "Regulation"),
        ("code", ""),
        ("title", "Title"),
        ("Admin", "user@example.com"),
        (role.name, "user@example.com"),
    ]))
    self._check_csv_response(response, {})
    market = models.Regulation.query.first()
    acl = models.AccessControlList.query.filter_by(
        ac_role_id=role_id,
        object_id=market.id,
        object_type="Regulation"
    )
    self.assertEqual(acl.count(), 1)
    self.assertEqual(acl.first().ac_role_id, role_id)
    self.assertEqual(
        acl.first().access_control_people[0].person.email,
        "user@example.com",
    )

  def test_acl_multiple_entries(self):
    """Test ACL column import with multiple emails."""
    with factories.single_commit():
      role = factories.AccessControlRoleFactory(object_type="Regulation")
      emails = {factories.PersonFactory().email for _ in range(3)}

    response = self.import_data(collections.OrderedDict([
        ("object_type", "Regulation"),
        ("code", ""),
        ("title", "Title"),
        ("Admin", "user@example.com"),
        (role.name, "\n".join(emails)),
    ]))
    self._check_csv_response(response, {})
    market = models.Regulation.query.first()
    self.assertEqual(
        {person.email for person, _ in market.access_control_list},
        emails | {"user@example.com"},
    )

  def test_acl_update(self):
    """Test ACL column import with multiple emails."""
    with factories.single_commit():
      role_name = factories.AccessControlRoleFactory(
          object_type="Regulation").name
      emails = {factories.PersonFactory().email for _ in range(4)}

    update_emails = set(list(emails)[:2]) | {"user@example.com"}

    response = self.import_data(collections.OrderedDict([
        ("object_type", "Regulation"),
        ("code", ""),
        ("title", "Title"),
        ("Admin", "user@example.com"),
        (role_name, "\n".join(emails)),
    ]))
    self._check_csv_response(response, {})

    regulation = all_models.Regulation.query.filter_by(title="Title").first()
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Regulation"),
        ("code", regulation.slug),
        ("title", "Title"),
        ("Admin", "user@example.com"),
        (role_name, "\n".join(update_emails)),
    ]))
    self._check_csv_response(response, {})
    regulation = models.Regulation.query.first()
    self.assertEqual(
        {person.email for person, _ in regulation.access_control_list},
        update_emails,
    )

  def test_acl_empty_update(self):
    """Test ACL column import with multiple emails."""
    with factories.single_commit():
      role_name = factories.AccessControlRoleFactory(
          object_type="Regulation").name
      emails = {factories.PersonFactory().email for _ in range(3)}

    response = self.import_data(collections.OrderedDict([
        ("object_type", "Regulation"),
        ("code", ""),
        ("title", "Title"),
        ("Admin", "user@example.com"),
        (role_name, "\n".join(emails)),
    ]))
    self._check_csv_response(response, {})

    regulation = all_models.Regulation.query.filter_by(title="Title").first()
    response = self.import_data(collections.OrderedDict([
        ("object_type", "Regulation"),
        ("code", regulation.slug),
        ("title", "Title"),
        ("Admin", "user@example.com"),
        (role_name, ""),
    ]))
    self._check_csv_response(response, {})
    regulation = models.Regulation.query.first()
    self.assertEqual(
        {person.email for person, _ in regulation.access_control_list},
        emails | {"user@example.com"},
    )

  def test_acl_export(self):
    """Test ACL field export."""
    with factories.single_commit():
      role_name = factories.AccessControlRoleFactory(
          object_type="Regulation").name
      empty_name = factories.AccessControlRoleFactory(
          object_type="Regulation",
      ).name
      emails = {factories.PersonFactory().email for _ in range(3)}

    self.import_data(collections.OrderedDict([
        ("object_type", "Regulation"),
        ("code", ""),
        ("title", "Title"),
        ("Admin", "user@example.com"),
        (role_name, "\n".join(emails)),
    ]))

    search_request = [{
        "object_name": "Regulation",
        "filters": {
            "expression": {}
        },
        "fields": [
            "slug",
            "__acl__:{}".format(role_name),
            "__acl__:{}".format(empty_name),
        ],
    }]
    self.client.get("/login")
    parsed_data = self.export_parsed_csv(
        search_request
    )["Regulation"]
    self.assertEqual(
        set(parsed_data[0][role_name].splitlines()),
        emails
    )
    self.assertEqual(parsed_data[0][empty_name], "")

  @staticmethod
  def _generate_role_import_dict(roles, object_type="Regulation"):
    """Generate simple import dict with all roles and emails."""
    scoping_models_names = [m.__name__ for m in all_models.all_models
                            if issubclass(m, ScopeObject)]

    regulation = models.Regulation.query.first()

    import_dict = collections.OrderedDict([
        ("object_type", object_type),
        ("code", ""),
        ("title", "Title"),
        ("title", "Title"),
        ("Admin", "user@example.com"),
    ])
    if regulation:
      import_dict["code"] = regulation.slug
    if object_type == "Issue":
      import_dict["code"] = "Issue12"
      import_dict["due date"] = "2022-11-12"
    if object_type == "Control":
      import_dict["Assertions*"] = "Privacy"
    if object_type in scoping_models_names:
      import_dict["Assignee"] = "user@example.com"
      import_dict["Verifier"] = "user@example.com"
    for role_name, emails in roles.items():
      import_dict[role_name] = "\n".join(emails)
    return import_dict

  @ddt.data({
      "role_name_1": set(),
      "role_name_2": set(_random_emails[2:]),
  }, {
      "role_name_1": set(_random_emails[:3]),
      "role_name_2": set(_random_emails[2:]),
      "role_name_3": set(_random_emails),
  })
  def test_multiple_acl_roles_add(self, roles):
    """Test importing new object with multiple ACL roles."""
    with factories.single_commit():
      for email in self._random_emails:
        factories.PersonFactory(email=email)

      for role_name in roles.keys():
        factories.AccessControlRoleFactory(
            object_type="Regulation",
            name=role_name + "  ",
        )

    import_dict = self._generate_role_import_dict(roles)
    self.import_data(import_dict)
    regulation = models.Regulation.query.first()

    stored_roles = {}
    for role_name in roles.keys():
      stored_roles[role_name] = {
          person.email for person, acl in regulation.access_control_list
          if acl.ac_role.name == role_name
      }

    self.assertEqual(stored_roles, roles)

  @ddt.data(*list(itertools.combinations([{
      "role_name_1": set(),
      "role_name_2": set(),
      "role_name_3": set(),
  }, {
      "role_name_1": set(),
      "role_name_2": set(_random_emails[2:]),
      "role_name_3": set(_random_emails),
  }, {
      "role_name_1": set(_random_emails[:3]),
      "role_name_2": set(_random_emails[2:]),
      "role_name_3": set(_random_emails),
  }, {
      "role_name_1": set(_random_emails),
      "role_name_2": set(_random_emails),
      "role_name_3": set(_random_emails),
  }], 2)))
  @ddt.unpack
  def test_multiple_acl_roles_update(self, first_roles, edited_roles):
    """Test updating objects via import with multiple ACL roles."""
    with factories.single_commit():
      for email in self._random_emails:
        factories.PersonFactory(email=email)

      for role_name in first_roles.keys():
        factories.AccessControlRoleFactory(
            object_type="Regulation",
            name=role_name,
        )

    import_dict = self._generate_role_import_dict(first_roles)
    self.import_data(import_dict)
    regulation = models.Regulation.query.first()

    stored_roles = {}
    for role_name in first_roles.keys():
      stored_roles[role_name] = {
          person.email for person, acl in regulation.access_control_list
          if acl.ac_role.name == role_name
      }

    self.assertEqual(stored_roles, first_roles)

    import_dict = self._generate_role_import_dict(edited_roles)
    self.import_data(import_dict)
    regulation = models.Regulation.query.first()

    stored_roles = {}
    for role_name in edited_roles.keys():
      stored_roles[role_name] = {
          person.email for person, acl in regulation.access_control_list
          if acl.ac_role.name == role_name
      }

    self.assertEqual(stored_roles, edited_roles)

  @ddt.data({"Issue": {"other role name": set(_random_emails[:1])}})
  def test_same_name_roles(self, model_dict):
    """Test role with the same names on different objects."""
    with factories.single_commit():
      for email in self._random_emails:
        factories.PersonFactory(email=email)

      import_dicts = []
      for object_type, roles in model_dict.items():
        for role_name in roles.keys():
          factories.AccessControlRoleFactory(
              object_type=object_type,
              name=role_name,
          )

        import_dicts.append(
            self._generate_role_import_dict(roles, object_type)
        )

    response = self.import_data(*import_dicts)
    self._check_csv_response(response, {})
    stored_roles = {}
    for object_type, roles in model_dict.items():
      model = getattr(models, object_type)
      obj = model.query.first()
      stored_roles[object_type] = {}
      for role_name in roles.keys():
        stored_roles[object_type][role_name] = {
            person.email for person, acl in obj.access_control_list
            if acl.ac_role.name == role_name and
            acl.ac_role.object_type == object_type
        }
    self.assertEqual(stored_roles, model_dict)

  def test_acl_revision_on_import(self):
    """Test creation of separate revision for ACL in import"""
    with factories.single_commit():
      role_name = factories.AccessControlRoleFactory(
          object_type="Regulation").name
      emails = {factories.PersonFactory().email for _ in range(3)}

    response = self.import_data(collections.OrderedDict([
        ("object_type", "Regulation"),
        ("code", ""),
        ("title", "Title"),
        ("Admin", "user@example.com"),
        (role_name, "\n".join(emails)),
    ]))
    self._check_csv_response(response, {})
    regulation_revisions = models.Revision.query.filter_by(
        resource_type="Regulation"
    ).count()
    self.assertEqual(regulation_revisions, 1)

    acr_revisions = models.Revision.query.filter_by(
        resource_type="AccessControlRole"
    ).count()
    self.assertEqual(acr_revisions, 1)

    acl_revisions = models.Revision.query.filter_by(
        resource_type="AccessControlList"
    ).count()
    self.assertEqual(acl_revisions, 4)

  def test_acl_roles_clear(self):
    """Test clearing ACL roles for Program with '--' value"""
    with factories.single_commit():
      program = factories.ProgramFactory()
      for role in ["Program Editors", "Program Editors", "Program Readers"]:
        person = factories.PersonFactory()
        acl = program.acr_name_acl_map[role]
        factories.AccessControlPersonFactory(
            ac_list=acl,
            person=person,
        )

    for role in {"Program Editors", "Program Readers"}:
      response = self.import_data(collections.OrderedDict([
          ("object_type", program.type),
          ("code", program.slug),
          (role, "--"),
      ]))
      self._check_csv_response(response, {})
      program = models.all_models.Program.query.first()
      for _, acl in program.access_control_list:
        self.assertNotEqual(acl.ac_role.name, role)
