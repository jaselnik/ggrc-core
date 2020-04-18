# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration test for Superusers persons sync cron job."""


import mock

from ggrc import settings
from ggrc.models import all_models
from ggrc.integrations import synchronization_jobs

from integration import ggrc
from integration.ggrc.models import factories
from integration.ggrc_basic_permissions.models \
    import factories as rbac_factories


@mock.patch.object(
    settings,
    "BOOTSTRAP_ADMIN_USERS",
    ["superuser@example.com"],
)
class TestSuperuserSyncJob(ggrc.TestCase):
  """Test cron job for sync Superuser Person objects."""

  def setUp(self):
    super(TestSuperuserSyncJob, self).setUp()
    with factories.single_commit():
      role = all_models.Role.query.filter(
          all_models.Role.name == "Administrator"
      ).one()
      self.admin = factories.PersonFactory(
          email="test@example.com",
          name="Test Test",
      )
      rbac_factories.UserRoleFactory(role=role, person=self.admin)
      self.superuser = factories.PersonFactory(
          email="superuser@example.com",
          name="Super User",
      )
      rbac_factories.UserRoleFactory(role=role, person=self.superuser)

  def test_superuser_role_deleted(self):
    """Test superuser person with admin role set to no role"""
    synchronization_jobs.sync_superusers()
    admin = self.refresh_object(self.admin)
    superuser = self.refresh_object(self.superuser)
    self.assertNotEqual(admin.user_roles, [])
    self.assertEqual(superuser.user_roles, [])
