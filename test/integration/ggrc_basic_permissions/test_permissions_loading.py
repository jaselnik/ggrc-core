# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test user permissions loading and caching."""
import mock

from appengine import base

from ggrc.models import all_models
from ggrc.cache import utils as cache_utils
from integration.ggrc import TestCase, generator
from integration.ggrc.api_helper import Api
from integration.ggrc.models import factories as ggrc_factories
from integration.ggrc_basic_permissions.models \
    import factories as rbac_factories


# pylint: disable=invalid-name


# stub for module, which cannot be imported in global scope bacause of
# import error
ggrc_basic_permissions = None  # pylint: invalid-name


def _lazy_load_module():
  """Load required module in runtime to prevent import error"""

  global ggrc_basic_permissions  # pylint: global-statement,invalid-name
  import ggrc_basic_permissions  # pylint: disable=redefined-outer-name


@base.with_memcache
class TestMemcacheBase(TestCase):
  """Base class for permissions tests"""

  def setUp(self):
    super(TestMemcacheBase, self).setUp()
    _lazy_load_module()

  def set_dummy_permissions_in_cache(self, *user_ids):
    """Set dummy permissions for users in memcache.

    Set dummy permissions for passed users in memcache. Note that this will
    override permissions present in memcache.

    Args:
      user_ids (tuple): IDs of users for which permissions should be set.
    """
    cached_keys = set("permissions:{}".format(user_id) for user_id in user_ids)
    self.memcache_client.set("permissions:list", cached_keys)

  def assert_permissions_not_in_memcache(self, *user_ids):
    """Assert that permissions for users are not present in memcache.

    Check that permissions for users with `user_ids` IDs are not present in
    memcache. This check will fail if permissions for at least one user are
    present in memcache.

    Args:
      user_ids (tuple): IDs of users which permissions should be checked.
    """
    cached_keys = self.memcache_client.get("permissions:list")
    present = any("permissions:{}".format(user_id) in cached_keys
                  for user_id in user_ids)
    self.assertFalse(present)

  def assert_permissions_in_memcache(self, *user_ids):
    """Assert that permissions for users are present in memcache.

    Check that permissions for users with `user_ids` IDs are present in
    memcache. This check will fail if permissions for at least one user are
    not present in memcache.

    Args:
      user_ids (tuple): IDs of users which permissions should be checked.
    """
    cached_keys = self.memcache_client.get("permissions:list")
    present = all("permissions:{}".format(user_id) in cached_keys
                  for user_id in user_ids)
    self.assertTrue(present)


class TestPermissionsLoading(TestMemcacheBase):
  """Test user permissions loading."""

  def setUp(self):
    super(TestPermissionsLoading, self).setUp()
    self.api = Api()
    self.generator = generator.ObjectGenerator()

    _, self.user = self.generator.generate_person(user_role="Creator")
    _, self.user1 = self.generator.generate_person(user_role="Creator")
    self.api.set_user(self.user)
    self.user_id = self.user.id
    self.user1_id = self.user1.id

  def test_permissions_loading(self):
    """Test if permissions created only once for GET requests."""
    control_id = ggrc_factories.ControlFactory().id
    with mock.patch(
        "ggrc_basic_permissions.store_results_into_memcache",
        side_effect=ggrc_basic_permissions.store_results_into_memcache
    ) as store_perm:
      self.api.get(all_models.Control, control_id)
      store_perm.assert_called_once()
      store_perm.call_count = 0

      # On second GET permissions should be loaded from memcache
      # but not created from scratch.
      self.api.get(all_models.Control, control_id)
      store_perm.assert_not_called()

  def test_post_object_with_acl(self):
    """Permissions are recalculated only for assigned people on POST."""
    pa_role = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.object_type == "Program",
        all_models.AccessControlRole.name == "Program Managers"
    ).first()

    self.set_dummy_permissions_in_cache(self.user_id, self.user1_id)
    self.api.post(all_models.Program, {
        "program": {
            "title": "Program title",
            "context": None,
            "access_control_list": [{
                "ac_role_id": pa_role.id,
                "person": {
                    "type": "Person",
                    "id": self.user_id,
                }
            }],
        },
    })
    cached_keys = self.memcache_client.get("permissions:list")
    self.assertNotIn("permissions:{}".format(self.user_id), cached_keys)
    self.assertIn("permissions:{}".format(self.user1_id), cached_keys)

  def test_delete_object_with_acl(self):
    """Permissions are recalculated only for affected people on DELETE."""
    pa_role = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.object_type == "Program",
        all_models.AccessControlRole.name == "Program Managers"
    ).first()

    response = self.api.post(all_models.Program, {
        "program": {
            "title": "Program title",
            "context": None,
            "access_control_list": [{
                "ac_role_id": pa_role.id,
                "person": {
                    "type": "Person",
                    "id": self.user_id,
                }
            }],
        },
    })
    program = all_models.Program.query.get(response.json["program"]["id"])
    self.set_dummy_permissions_in_cache(self.user_id, self.user1_id)
    self.api.delete(program)
    cached_keys = self.memcache_client.get("permissions:list")
    self.assertNotIn("permissions:{}".format(self.user_id), cached_keys)
    self.assertIn("permissions:{}".format(self.user1_id), cached_keys)

  def test_add_acl(self):
    """Permissions are recalculated only for assigned people on PUT."""
    # Memcache should be cleared first since it contains permissions for
    # both users on startup due to setUp method which creates users with
    # `UserRole`. Creation of `UserRole` causes cached permissions
    # recalculation.
    self.memcache_client.delete("permissions:list")

    pa_role = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.object_type == "Program",
        all_models.AccessControlRole.name == "Program Managers"
    ).first()

    response = self.api.post(all_models.Program, {
        "program": {
            "title": "Program title",
            "context": None,
            "access_control_list": [{
                "ac_role_id": pa_role.id,
                "person": {
                    "type": "Person",
                    "id": self.user_id,
                }
            }],
        },
    })
    program = all_models.Program.query.get(response.json["program"]["id"])
    cached_keys = self.memcache_client.get("permissions:list")
    self.assertNotIn("permissions:{}".format(self.user_id), cached_keys)
    self.assertNotIn("permissions:{}".format(self.user1_id), cached_keys)

    self.set_dummy_permissions_in_cache(self.user_id, self.user1_id)
    self.api.put(program, {
        "access_control_list": [{
            "ac_role_id": pa_role.id,
            "person": {
                "type": "Person",
                "id": self.user_id,
            }
        }, {
            "ac_role_id": pa_role.id,
            "person": {
                "type": "Person",
                "id": self.user1_id,
            }
        }],
    })
    cached_keys = self.memcache_client.get("permissions:list")
    self.assertIn("permissions:{}".format(self.user_id), cached_keys)
    self.assertNotIn("permissions:{}".format(self.user1_id), cached_keys)

  def test_remove_acl(self):
    """Permissions are recalculated only for unassigned people on PUT."""
    pa_role = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.object_type == "Program",
        all_models.AccessControlRole.name == "Program Managers"
    ).first()

    response = self.api.post(all_models.Program, {
        "program": {
            "title": "Program title",
            "context": None,
            "access_control_list": [{
                "ac_role_id": pa_role.id,
                "person": {
                    "type": "Person",
                    "id": self.user_id,
                }
            }, {
                "ac_role_id": pa_role.id,
                "person": {
                    "type": "Person",
                    "id": self.user1_id,
                }
            }],
        },
    })
    program = all_models.Program.query.get(response.json["program"]["id"])
    cached_keys = self.memcache_client.get("permissions:list")
    self.assertNotIn("permissions:{}".format(self.user_id), cached_keys)
    self.assertNotIn("permissions:{}".format(self.user1_id), cached_keys)

    self.set_dummy_permissions_in_cache(self.user_id, self.user1_id)
    self.api.put(program, {
        "access_control_list": [{
            "ac_role_id": pa_role.id,
            "person": {
                "type": "Person",
                "id": self.user_id,
            }
        }]
    })
    cached_keys = self.memcache_client.get("permissions:list")
    self.assertIn("permissions:{}".format(self.user_id), cached_keys)
    self.assertNotIn("permissions:{}".format(self.user1_id), cached_keys)

  def test_mapping(self):
    """Perm dict should be recalculated for affected users on map/unmap."""
    pa_role = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.object_type == "Program",
        all_models.AccessControlRole.name == "Program Managers"
    ).first()
    ia_role = all_models.AccessControlRole.query.filter_by(
        name="Admin",
        object_type="Issue",
    ).one()

    response = self.api.post(all_models.Program, {
        "program": {
            "title": "Program title",
            "context": None,
            "access_control_list": [{
                "ac_role_id": pa_role.id,
                "person": {
                    "type": "Person",
                    "id": self.user_id,
                }
            }],
        },
    })
    program = all_models.Program.query.get(response.json["program"]["id"])

    response = self.api.post(all_models.Issue, {
        "issue": {
            "access_control_list": [{
                "ac_role_id": ia_role.id,
                "person": {
                    "id": self.user_id,
                    "type": "Person",
                }
            }],
            "title": "Issue title",
            "due_date": "02/24/2020",
            "context": None,
        },
    })
    issue = all_models.Issue.query.get(response.json["issue"]["id"])

    self.set_dummy_permissions_in_cache(self.user_id, self.user1_id)
    response = self.api.post(all_models.Relationship, {
        "relationship": {
            "source": {
                "id": program.id,
                "type": "Program",
            },
            "destination": {
                "id": issue.id,
                "type": "Issue"
            },
            "context": None,
        },
    })
    cached_keys = self.memcache_client.get("permissions:list")
    self.assertNotIn("permissions:{}".format(self.user_id), cached_keys)
    self.assertIn("permissions:{}".format(self.user1_id), cached_keys)

    self.set_dummy_permissions_in_cache(self.user_id, self.user1_id)
    relationship = all_models.Relationship.query.get(
        response.json["relationship"]["id"])
    self.api.delete(relationship)
    cached_keys = self.memcache_client.get("permissions:list")
    self.assertNotIn("permissions:{}".format(self.user_id), cached_keys)
    self.assertIn("permissions:{}".format(self.user1_id), cached_keys)

  def test_add_comment(self):
    """Permissions dict should be flushed for affected users on add comment."""
    aa_role = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.object_type == "Assessment",
        all_models.AccessControlRole.name == "Assignees"
    ).first()
    ac_role = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.object_type == "Audit",
        all_models.AccessControlRole.name == "Audit Captains"
    ).first()
    pa_role = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.object_type == "Program",
        all_models.AccessControlRole.name == "Program Managers"
    ).first()

    response = self.api.post(all_models.Program, {
        "program": {
            "title": "Program title",
            "context": None,
            "access_control_list": [{
                "ac_role_id": pa_role.id,
                "person": {
                    "type": "Person",
                    "id": self.user_id,
                }
            }],
        },
    })
    response = self.api.post(all_models.Audit, {
        "audit": {
            "program": {
                "id": response.json["program"]["id"],
                "type": "Program"
            },
            "access_control_list": [{
                "ac_role_id": ac_role.id,
                "person": {
                    "type": "Person",
                    "id": self.user1_id,
                }
            }],
            "context": None,
            "title": "Some title"
        }
    })
    response = self.api.post(all_models.Assessment, {
        "assessment": {
            "audit": {
                "id": response.json["audit"]["id"],
                "type": "Audit"
            },
            "access_control_list": [{
                "ac_role_id": aa_role.id,
                "person": {
                    "type": "Person",
                    "id": self.user1_id,
                }
            }],
            "context": None,
            "title": "Some title"
        }
    })
    assessment = all_models.Assessment.query.get(
        response.json["assessment"]["id"]
    )
    self.set_dummy_permissions_in_cache(self.user_id, self.user1_id)
    request_data = [{
        "comment": {
            "description": "<p>{}</p>".format("test"),
            "context": None,
            "assignee_type": "Assignees,Verifiers,Creators",
        },
    }]

    # logged user will be set as comment admin
    response = self.api.post(all_models.Comment, request_data)
    cached_keys = self.memcache_client.get("permissions:list")
    self.assertNotIn("permissions:{}".format(self.user_id), cached_keys)
    self.assertIn("permissions:{}".format(self.user1_id), cached_keys)

    self.set_dummy_permissions_in_cache(self.user_id, self.user1_id)
    self.api.set_user(self.user1)
    self.api.put(assessment, {
        "actions": {"add_related": [{
            "id": response.json[0][1]["comment"]["id"],
            "type": "Comment"
        }]},
    })
    cached_keys = self.memcache_client.get("permissions:list")
    self.assertNotIn("permissions:{}".format(self.user_id), cached_keys)
    self.assertNotIn("permissions:{}".format(self.user1_id), cached_keys)

  def test_add_evidence(self):
    """Perm dict should be flushed for affected users on add evidence."""
    aa_role = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.object_type == "Assessment",
        all_models.AccessControlRole.name == "Assignees"
    ).first()
    ac_role = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.object_type == "Audit",
        all_models.AccessControlRole.name == "Audit Captains"
    ).first()
    pa_role = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.object_type == "Program",
        all_models.AccessControlRole.name == "Program Managers"
    ).first()
    ea_role = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.object_type == "Evidence",
        all_models.AccessControlRole.name == "Admin"
    ).first()

    response = self.api.post(all_models.Program, {
        "program": {
            "title": "Program title",
            "context": None,
            "access_control_list": [{
                "ac_role_id": pa_role.id,
                "person": {
                    "type": "Person",
                    "id": self.user_id,
                }
            }],
        },
    })
    response = self.api.post(all_models.Audit, {
        "audit": {
            "program": {
                "id": response.json["program"]["id"],
                "type": "Program"
            },
            "access_control_list": [{
                "ac_role_id": ac_role.id,
                "person": {
                    "type": "Person",
                    "id": self.user_id,
                }
            }],
            "context": None,
            "title": "Some title"
        }
    })
    response = self.api.post(all_models.Assessment, {
        "assessment": {
            "audit": {
                "id": response.json["audit"]["id"],
                "type": "Audit"
            },
            "access_control_list": [{
                "ac_role_id": aa_role.id,
                "person": {
                    "type": "Person",
                    "id": self.user_id,
                }
            }],
            "context": None,
            "title": "Some title"
        }
    })
    assessment = all_models.Assessment.query.get(
        response.json["assessment"]["id"]
    )
    response = self.api.post(all_models.Evidence, {
        "evidence": {
            "access_control_list": [{
                "ac_role_id": ea_role.id,
                "person": {
                    "id": self.user_id,
                    "type": "Person",
                }
            }],
            "link": ggrc_factories.random_str(),
            "title": ggrc_factories.random_str(),
            "context": None,
        }
    })
    self.set_dummy_permissions_in_cache(self.user_id, self.user1_id)
    self.api.put(assessment, {
        "actions": {"add_related": [{
            "id": response.json["evidence"]["id"],
            "type": "Evidence"
        }]},
    })
    cached_keys = self.memcache_client.get("permissions:list")
    self.assertNotIn("permissions:{}".format(self.user_id), cached_keys)
    self.assertIn("permissions:{}".format(self.user1_id), cached_keys)

  def test_edit_object_title(self):
    """Permissions shouldn't be recalculated on PUT if no acls were changed."""
    pa_role = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.object_type == "Program",
        all_models.AccessControlRole.name == "Program Managers"
    ).first()

    response = self.api.post(all_models.Program, {
        "program": {
            "title": "Program title",
            "context": None,
            "access_control_list": [{
                "ac_role_id": pa_role.id,
                "person": {
                    "type": "Person",
                    "id": self.user_id,
                }
            }],
        },
    })
    cached_keys = self.memcache_client.get("permissions:list")
    self.assertNotIn("permissions:{}".format(self.user_id), cached_keys)

    self.api.get(all_models.Program, response.json["program"]["id"])
    cached_keys = self.memcache_client.get("permissions:list")
    self.assertIn("permissions:{}".format(self.user_id), cached_keys)

    program = all_models.Program.query.get(response.json["program"]["id"])
    self.api.put(program, {
        "title": "Program title 1"
    })
    cached_keys = self.memcache_client.get("permissions:list")
    self.assertIn("permissions:{}".format(self.user_id), cached_keys)


class TestPermissionsCacheFlushing(TestMemcacheBase):
  """Test user permissions loading."""

  def setUp(self):
    super(TestPermissionsCacheFlushing, self).setUp()
    self.api = Api()

  @staticmethod
  def load_perms(user_id, new_perms):
    """Emulate procedure to load permissions
    """

    with mock.patch(
        'ggrc_basic_permissions._load_permissions_from_database',
        return_value=new_perms
    ):

      mock_user = mock.Mock()
      mock_user.id = user_id

      return ggrc_basic_permissions.load_permissions_for(mock_user)

  def test_memcache_flushing(self):
    """Test if memcache is properly cleaned on object creation

      Procedure to test functionality:
      1) load and permissions for specific user and store them in memcahe
      2) emulate new object creation, which cleans permissions in memcache
      3) make request which tries to get cache for permissions from memcache

      Also, it's assumed that 2 or more GGRC workers are running
    """

    client = cache_utils.get_cache_manager().cache_object.memcache_client
    client.flush_all()

    # load perms and store them in memcache
    self.load_perms(11, {"11": "a"})

    # emulate situation when a new object is created
    # this procedure cleans memcache in the end
    cache_utils.clear_permission_cache()

    # emulate work of worker #1 - get permissions for our user
    # the first step - check permissions in memcache
    ggrc_basic_permissions.query_memcache(client, "permissions:11")
    # step 2 - load permissions from DB and save then into memcahe
    # this step is omitted

    # load permission on behalf of worker #2, before step 2 of worker #1
    result = self.load_perms(11, {"11": "b"})

    # ensure that new permissions were returned instead of old ones
    self.assertEquals(result, {"11": "b"})

  def test_permissions_not_flush_on_simple_post(self):
    """Test that permissions in memcache are not cleaned after POST request."""
    user = self.create_user_with_role("Creator")
    self.api.set_user(user)
    self.api.client.get("/permissions")

    perm_ids = self.memcache_client.get("permissions:list")
    self.assertEqual(perm_ids, {"permissions:{}".format(user.id)})

    response = self.api.post(
        all_models.Issue,
        {
            "issue": {
                "title": "Test Issue",
                "context": None,
                "due_date": "02/24/2020",
            },
        }
    )

    self.assert_status(response, 201)

    perm_ids = self.memcache_client.get("permissions:list")
    self.assertIn("permissions:{}".format(user.id), perm_ids)

  def test_permissions_not_flush_on_simple_put(self):
    """Test that permissions in memcache are not cleaned after PUT request."""
    with ggrc_factories.single_commit():
      user = self.create_user_with_role("Creator")
      issue = ggrc_factories.IssueFactory()
      issue_id = issue.id
      issue.add_person_with_role_name(user, "Admin")

    self.api.set_user(user)
    self.api.client.get("/permissions")

    perm_ids = self.memcache_client.get("permissions:list")
    self.assertEqual(perm_ids, {"permissions:{}".format(user.id)})

    issue = all_models.Issue.query.get(issue_id)
    response = self.api.put(issue, {"title": "new title"})
    self.assert200(response)

    perm_ids = self.memcache_client.get("permissions:list")
    self.assertIn("permissions:{}".format(user.id), perm_ids)

  def test_permissions_flush_on_delete(self):
    """Test that permissions in memcache are cleaned after DELETE request."""
    with ggrc_factories.single_commit():
      user = self.create_user_with_role("Creator")
      issue = ggrc_factories.IssueFactory()
      issue.add_person_with_role_name(user, "Admin")
      issue_id = issue.id

    self.api.set_user(user)
    self.api.client.get("/permissions")

    perm_ids = self.memcache_client.get("permissions:list")
    self.assertEqual(perm_ids, {"permissions:{}".format(user.id)})

    issue = all_models.Issue.query.get(issue_id)
    response = self.api.delete(issue)
    self.assert200(response)

    perm_ids = self.memcache_client.get("permissions:list")
    self.assertEqual(perm_ids, set())

  def test_permissions_reload_on_role_post(self):
    """Test permissions in memcache are recalculated on UserRole POST."""
    person = ggrc_factories.PersonFactory()
    person_permissions_key = "permissions:{}".format(person.id)
    admin_role = all_models.Role.query.filter_by(name="Administrator").one()

    self.memcache_client.delete("permissions:list")
    response = self.api.post(
        all_models.UserRole,
        {
            "user_role": {
                "person": {
                    "type": person.type,
                    "id": person.id,
                },
                "role": {
                    "type": admin_role.type,
                    "id": admin_role.id,
                },
            },
        },
    )

    self.assertStatus(response, 201)
    cached_keys = self.memcache_client.get("permissions:list")
    self.assertIn(person_permissions_key, cached_keys)

  def test_permissions_reload_on_role_delete(self):
    """Test permissions in memcache are recalculated on UserRole DELETE."""
    admin_role = all_models.Role.query.filter_by(name="Administrator").one()
    with ggrc_factories.single_commit():
      person = ggrc_factories.PersonFactory()
      person_permissions_key = "permissions:{}".format(person.id)
      person_role = rbac_factories.UserRoleFactory(
          role=admin_role,
          person=person,
      )

    self.memcache_client.delete("permissions:list")
    response = self.api.delete(person_role)

    self.assertStatus(response, 200)
    cached_keys = self.memcache_client.get("permissions:list")
    self.assertIn(person_permissions_key, cached_keys)

  def _generate_assessment(self, audit, snapshot, template):
    """Generate Assessment via REST for Audit with Template and Snapshot."""
    return self.api.post(all_models.Assessment, {
        "assessment": {
            "title": ggrc_factories.random_str(),
            "_generated": True,
            "audit": {
                "id": audit.id,
                "type": audit.type,
            },
            "object": {
                "id": snapshot.id,
                "type": snapshot.type,
            },
            "template": {
                "id": template.id,
                "type": template.type,
            },
        },
    })

  def test_permissions_flush_on_asmt_genertation(self):
    """Test that permissions in memcache are cleaned after asmt generation.

    This test checks that permissions for all affected users are cleaned from
    memcache on Assessment generation from AssessmentTemplate and Snapshot.
    """
    with ggrc_factories.single_commit():
      user_1 = ggrc_factories.PersonFactory()
      user_2 = ggrc_factories.PersonFactory()
      asmt_tmpl = ggrc_factories.AssessmentTemplateFactory(
          default_people={
              "assignees": [user_1.id],
              "verifiers": [user_2.id],
          },
      )
      control = ggrc_factories.ControlFactory()
      control_snapshot, = self._create_snapshots(
          audit=asmt_tmpl.audit,
          objects=[control],
      )

    user_1_id = user_1.id
    user_2_id = user_2.id

    self.set_dummy_permissions_in_cache(user_1_id, user_2_id)
    self.assert_permissions_in_memcache(user_1_id, user_2_id)

    response = self._generate_assessment(
        audit=asmt_tmpl.audit,
        snapshot=control_snapshot,
        template=asmt_tmpl,
    )

    self.assert201(response)
    self.assert_permissions_not_in_memcache(user_1_id, user_2_id)
