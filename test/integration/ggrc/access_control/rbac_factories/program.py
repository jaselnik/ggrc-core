# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Program RBAC Factory."""
from ggrc import access_control
from ggrc.models import all_models
from integration.ggrc import Api, generator
from integration.ggrc.access_control.rbac_factories import base
from integration.ggrc.models import factories


class ProgramRBACFactory(base.BaseRBACFactory):
  """Program RBAC factory class."""

  def __init__(self, user_id, acr, parent=None):
    """Set up objects for Program permission tests.

    Args:
        user_id: Id of user under which all operations will be run.
        acr: Instance of ACR that should be assigned for tested user.
        parent: Model name in scope of which objects should be set up.
    """
    # pylint: disable=unused-argument
    self.setup_program_scope(user_id, acr, "Program")

    self.admin_control_id = {
        name: id for id, name
        in access_control.role.get_custom_roles_for("Control").items()
    }["Admin"]
    self.api = Api()
    self.objgen = generator.ObjectGenerator()
    self.objgen.api = self.api

    if user_id:
      self.user_id = user_id
      user = all_models.Person.query.get(user_id)
      self.api.set_user(user)

  def create(self):
    """Create new Program object."""
    return self.api.post(all_models.Program, {
        "program": {
            "title": "New program",
            "program": {"id": self.program_id},
            "context": None,
            "access_control_list": [],
        }
    })

  def read(self):
    """Read existing Audit object."""
    return self.api.get(all_models.Program, self.program_id)

  def update(self):
    """Update title of existing Audit object."""
    program = all_models.Program.query.get(self.program_id)
    return self.api.put(program, {"title": factories.random_str()})

  def delete(self):
    """Delete Audit object."""
    program = all_models.Program.query.get(self.program_id)
    return self.api.delete(program)

  def read_revisions(self):
    """Read revisions for Assessment object."""
    responses = []
    for query in ["source_type={}&source_id={}",
                  "destination_type={}&destination_id={}",
                  "resource_type={}&resource_id={}"]:
      responses.append(
          self.api.get_query(
              all_models.Program, query.format("program", self.program_id)
          )
      )
    return responses

  def map_control(self):
    """Map new Control to Program."""
    with factories.single_commit():
      control = factories.ControlFactory()
      for acl in control._access_control_list:
        if acl.ac_role_id == self.admin_control_id:
          factories.AccessControlPersonFactory(
              person_id=self.user_id,
              ac_list=acl,
          )

    program = all_models.Program.query.get(self.program_id)

    return self.objgen.generate_relationship(
        source=program,
        destination=control,
    )[0]

  def unmap_control(self):
    """Unmap Control from Program."""
    control = factories.ControlFactory()
    program = all_models.Program.query.get(self.program_id)
    rel = factories.RelationshipFactory(source=control, destination=program)

    return self.api.delete(rel)

  def read_mapped(self):
    """Read project mapped to Program."""
    program = all_models.Program.query.get(self.program_id)
    with factories.single_commit():
      project = factories.IssueFactory()
      factories.RelationshipFactory(source=project, destination=program)
    return self.api.get(project, project.id)

  def update_mapped(self):
    """Update project mapped to Program."""
    program = all_models.Program.query.get(self.program_id)
    with factories.single_commit():
      project = factories.IssueFactory()
      factories.RelationshipFactory(source=project, destination=program)
    return self.api.put(project, {"title": factories.random_str()})

  def delete_mapped(self):
    """Delete project mapped to Program."""
    program = all_models.Program.query.get(self.program_id)
    with factories.single_commit():
      project = factories.IssueFactory()
      factories.RelationshipFactory(source=project, destination=program)
    return self.api.delete(project)
