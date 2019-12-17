# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration test for Person object sync cron job."""

import mock

from ggrc import settings
from ggrc.integrations.synchronization_jobs import sync_people

from integration import ggrc
from integration.ggrc.models import factories


@mock.patch.object(settings, "AUTHORIZED_DOMAIN", "example.com")
class TestPeopleSyncJob(ggrc.TestCase):
  """Test cron job for sync Person objects."""

  def setUp(self):
    super(TestPeopleSyncJob, self).setUp()
    with factories.single_commit():
      self.person1 = factories.PersonFactory(
          email="test@example.com",
          name="Test Test",
      )
      self.person2 = factories.PersonFactory(
          email="test2@example.com",
          name="Some Some",
      )
      self.person3 = factories.PersonFactory(
          email="test@test.com",
          name="Test Test",
      )

  def test_updated_one_person(self):
    """Test updated one person"""
    with mock.patch(
        "ggrc.integrations.client.PersonClient.search_persons",
        return_value=[
            {
                "username": "test",
                "firstName": "NewName",
                "lastName": "NewLastName",
            },
        ],
    ):
      sync_people()
      person1 = self.refresh_object(self.person1)
      self.assertEqual(person1.name, "NewName NewLastName")

  def test_updated_many_people(self):
    """Test updated list of people"""
    with mock.patch(
        "ggrc.integrations.client.PersonClient.search_persons",
        return_value=[
            {
                "username": "test",
                "firstName": "NewName",
                "lastName": "NewLastName",
            },
            {
                "username": "test2",
                "firstName": "SomeName",
                "lastName": "SomeLastName",
            }
        ],
    ):
      sync_people()
      person1 = self.refresh_object(self.person1)
      person2 = self.refresh_object(self.person2)
      self.assertEqual(person1.name, "NewName NewLastName")
      self.assertEqual(person2.name, "SomeName SomeLastName")

  def test_sync_people_same_username(self):
    """Test people with unauthorized domain not updated"""
    with mock.patch(
        "ggrc.integrations.client.PersonClient.search_persons",
        return_value=[
            {
                "username": "test",
                "firstName": "NewName",
                "lastName": "NewLastName",
            },
        ],
    ):
      sync_people()
      person1 = self.refresh_object(self.person1)
      person3 = self.refresh_object(self.person3)
      self.assertEqual(person1.name, "NewName NewLastName")
      self.assertEqual(person3.name, "Test Test")
