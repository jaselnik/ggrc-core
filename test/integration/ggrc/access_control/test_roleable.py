# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Access Control Roleable mixin"""
import ddt
from ggrc import db
from ggrc import utils
from ggrc.access_control import roleable
from ggrc.models import all_models
from integration.ggrc import TestCase
from integration.ggrc.models import factories


@ddt.ddt
class TestAccessControlRoleable(TestCase):
  """Test AccessControlList"""

  def setUp(self):
    super(TestAccessControlRoleable, self).setUp()
    with factories.single_commit():
      self.role = factories.AccessControlRoleFactory(object_type="Control")
      self.person = factories.PersonFactory()

  def test_roleable_eager_query(self):
    """Test eager query on roleable object.

    This test compares the query counts while accessing an object with a single
    user role on it with an object with multiple users.
    """
    with factories.single_commit():
      people = [factories.PersonFactory() for _ in range(5)]
      emails = {person.email for person in people}
      control = factories.ControlFactory()
      control.add_person_with_role_name(people[0], "Admin")
      control_id = control.id

    db.session.expire_all()
    with utils.QueryCounter() as counter:
      control = all_models.Control.eager_query().filter_by(
          id=control_id
      ).one()
      eager_query_count = counter.get
      self.assertEqual(len(control.access_control_list), 1)
      self.assertEqual(eager_query_count, counter.get)
      self.assertEqual(
          control.access_control_list[0][1].ac_role.name,
          "Admin",
      )
      self.assertEqual(eager_query_count, counter.get)
      self.assertEqual(
          control.access_control_list[0][0].email,
          people[0].email,
      )
      self.assertEqual(eager_query_count, counter.get)

    factories.AccessControlRoleFactory(object_type="Control", name="custom")

    with factories.single_commit():
      control_multi = factories.ControlFactory()
      for person in people:
        control_multi.add_person_with_role_name(person, "Admin")
        control_multi.add_person_with_role_name(person, "custom")
      control_multi_id = control_multi.id

    db.session.expire_all()
    with utils.QueryCounter() as counter:
      control_multi = all_models.Control.eager_query().filter_by(
          id=control_multi_id
      ).one()
      self.assertEqual(eager_query_count, counter.get)
      self.assertEqual(
          len(control_multi.access_control_list),
          len(people) * 2,
      )
      self.assertEqual(eager_query_count, counter.get)
      admins = {
          person.email
          for person in control_multi.get_persons_for_rolename("Admin")
      }
      self.assertEqual(admins, emails)
      self.assertEqual(eager_query_count, counter.get)
      custom_role_users = {
          person.email
          for person in control_multi.get_persons_for_rolename("custom")
      }
      self.assertEqual(custom_role_users, emails)
      self.assertEqual(eager_query_count, counter.get)

  @ddt.data(*[
      model for model in all_models.all_models
      if issubclass(model, roleable.Roleable)
  ])
  def test_initial_role_setup(self, model):
    """Check generating acl entries for {0.__name__}."""
    with db.session.no_autoflush:
      obj = model()
      generated_roles = [acl.ac_role for acl in obj.acr_acl_map.values()]
      control_visible_roles = all_models.AccessControlRole.query.filter(
          all_models.AccessControlRole.object_type == obj.type,
          all_models.AccessControlRole.internal == 0,
      ).all()
      self.assertItemsEqual(
          generated_roles,
          control_visible_roles,
      )

  def test_with_dict(self):
    """Test access_control_list setter with a basic dict object.

    This test ensures frontend API compatibility.
    """
    acl_list = [{
        "ac_role_id": self.role.id,
        "person": {
            "id": self.person.id
        }
    }]
    with db.session.no_autoflush:
      obj = all_models.Control(
          title="New Control",
          access_control_list=acl_list
      )
      self.assertIsNotNone(obj.access_control_list)
      person, acl = obj.access_control_list[0]
      self.assertIsNotNone(acl)
      self.assertIsInstance(acl, all_models.AccessControlList)
      self.assertEqual(person.id, self.person.id)
      self.assertEqual(acl.ac_role.id, self.role.id)
      self.assertEqual(acl.object, obj)

  def test_with_dict_objs_multiple(self):
    """Test access_control_list setter without ids"""
    role = factories.AccessControlRoleFactory(object_type="Control")
    person_1 = factories.PersonFactory(name="Frodo", email="frodo@baggins.com")
    person_2 = factories.PersonFactory(name="Bilbo", email="bilbo@baggins.com")
    person_3 = factories.PersonFactory(name="Merry", email="merry@buck.com")
    obj = all_models.Control(title="Test Control")
    obj.access_control_list = [{
        "person": {
            "id": person_1.id,
        },
        "ac_role_id": role.id,
    }, {
        "person": {
            "id": person_2.id,
        },
        "ac_role_id": role.id,
    }]
    db.session.commit()

    acls = db.session.query(
        all_models.AccessControlPerson.person_id,
    ).join(
        all_models.AccessControlList
    ).filter(
        all_models.AccessControlList.object_id == obj.id,
        all_models.AccessControlList.object_type == "Control"
    )

    self.assertItemsEqual([
        (person_1.id, ),
        (person_2.id, ),
    ], acls.all())

    obj.access_control_list = [{
        "person": {
            "id": person_2.id,
        },
        "ac_role_id": role.id,
    }, {
        "person": {
            "id": person_3.id,
        },
        "ac_role_id": role.id,
    }]
    db.session.commit()

    self.assertItemsEqual([
        (person_2.id, ),
        (person_3.id, ),
    ], acls.all())
