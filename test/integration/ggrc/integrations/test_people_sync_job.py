# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration test for Person object sync cron job."""

import mock

from ggrc import settings
from ggrc.models import all_models
from ggrc.integrations import synchronization_jobs

from integration import ggrc
from integration.ggrc.models import factories
from integration.ggrc_basic_permissions.models \
    import factories as rbac_factories


@mock.patch.object(settings, "AUTHORIZED_DOMAIN", "example.com")
class TestPeopleSyncJob(ggrc.TestCase):
  """Test cron job for sync Person objects."""

  def setUp(self):
    super(TestPeopleSyncJob, self).setUp()
    with factories.single_commit():
      role = all_models.Role.query.filter(
          all_models.Role.name == "Administrator"
      ).one()
      self.admin1 = factories.PersonFactory(
          email="test@example.com",
          name="Test Test",
      )
      rbac_factories.UserRoleFactory(role=role, person=self.admin1)
      self.admin2 = factories.PersonFactory(
          email="test2@example.com",
          name="Some Some",
      )
      rbac_factories.UserRoleFactory(role=role, person=self.admin2)
      self.unauthorized_person = factories.PersonFactory(
          email="test@test.com",
          name="Unauthorized Person",
      )

  def test_updated_one_person(self):
    """Test updated one person"""
    with mock.patch(
        "ggrc.integrations.client.PersonClient.search_persons",
        return_value=[
            {
                "username": self.admin1.user_name,
                "firstName": "NewName",
                "lastName": "NewLastName",
                "isActive": True,
            },
        ],
    ):
      synchronization_jobs.sync_people()
      admin1 = self.refresh_object(self.admin1)
      self.assertEqual(admin1.name, "NewName NewLastName")

  def test_updated_many_people(self):
    """Test updated list of people"""
    with mock.patch(
        "ggrc.integrations.client.PersonClient.search_persons",
        return_value=[
            {
                "username": self.admin1.user_name,
                "firstName": "NewName",
                "lastName": "NewLastName",
                "isActive": True,
            },
            {
                "username": self.admin2.user_name,
                "firstName": "SomeName",
                "lastName": "SomeLastName",
                "isActive": True,
            }
        ],
    ):
      synchronization_jobs.sync_people()
      admin1 = self.refresh_object(self.admin1)
      admin2 = self.refresh_object(self.admin2)
      self.assertEqual(admin1.name, "NewName NewLastName")
      self.assertEqual(admin2.name, "SomeName SomeLastName")

  # pylint: disable=invalid-name
  def test_no_sync_unauthorized_domain(self):
    """Test people with unauthorized domain not updated"""
    with mock.patch(
        "ggrc.integrations.client.PersonClient.search_persons",
        return_value=[
            {
                "username": self.unauthorized_person.user_name,
                "firstName": "NewName",
                "lastName": "NewLastName",
                "isActive": True,
            },
        ],
    ):
      synchronization_jobs.sync_people()
      unauthorized_person = self.refresh_object(self.unauthorized_person)
      self.assertEqual(unauthorized_person.name, "Unauthorized Person")

  def test_no_role_one_person(self):
    """Test person set to no role when isActive = false"""
    with mock.patch(
        "ggrc.integrations.client.PersonClient.search_persons",
        return_value=[
            {
                "username": self.admin1.user_name,
                "firstName": "Test",
                "lastName": "Test",
                "isActive": False,
            },
        ],
    ):
      synchronization_jobs.sync_people()
      admin1 = self.refresh_object(self.admin1)
      self.assertEqual(admin1.user_roles, [])

  def test_no_role_many_person(self):
    """Test many people set to no role when isActive = false"""
    with mock.patch(
        "ggrc.integrations.client.PersonClient.search_persons",
        return_value=[
            {
                "username": self.admin1.user_name,
                "firstName": "Test",
                "lastName": "Test",
                "isActive": False,
            },
            {
                "username": self.admin2.user_name,
                "firstName": "Some",
                "lastName": "Some",
                "isActive": False,
            }
        ],
    ):
      synchronization_jobs.sync_people()
      admin1 = self.refresh_object(self.admin1)
      admin2 = self.refresh_object(self.admin2)
      self.assertEqual(admin1.user_roles, [])
      self.assertEqual(admin2.user_roles, [])

  def test_one_no_role_one_update(self):
    """Test one person updated name, one set no role when isActive = false"""
    with mock.patch(
        "ggrc.integrations.client.PersonClient.search_persons",
        return_value=[
            {
                "username": self.admin1.user_name,
                "firstName": "Test",
                "lastName": "Test",
                "isActive": False,
            },
            {
                "username": self.admin2.user_name,
                "firstName": "SomeName",
                "lastName": "SomeLastName",
                "isActive": True,
            }
        ],
    ):
      synchronization_jobs.sync_people()
      admin1 = self.refresh_object(self.admin1)
      admin2 = self.refresh_object(self.admin2)
      self.assertEqual(admin1.user_roles, [])
      self.assertNotEqual(admin2.user_roles, [])
      self.assertEqual(admin2.name, "SomeName SomeLastName")

  def test_one_no_role_no_update(self):
    """Test person set to no role when isActive = false and no name updates"""
    with mock.patch(
        "ggrc.integrations.client.PersonClient.search_persons",
        return_value=[
            {
                "username": self.admin1.user_name,
                "firstName": "NewName",
                "lastName": "NewLastName",
                "isActive": False,
            },
        ],
    ):
      synchronization_jobs.sync_people()
      admin1 = self.refresh_object(self.admin1)
      self.assertEqual(admin1.user_roles, [])
      self.assertEqual(admin1.name, "Test Test")
