# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Audit RBAC Factory."""
from ggrc import access_control
from ggrc.models import all_models, get_model
from integration.ggrc import Api, generator
from integration.ggrc.access_control.rbac_factories import base
from integration.ggrc.models import factories


class AuditRBACFactory(base.BaseRBACFactory):
  """Audit RBAC factory class."""

  def __init__(self, user_id, acr, parent=None):
    """Set up objects for Audit permission tests.

    Args:
        user_id: Id of user under which all operations will be run.
        acr: Instance of ACR that should be assigned for tested user.
        parent: Model name in scope of which objects should be set up.
    """
    # pylint: disable=unused-argument
    self.setup_program_scope(user_id, acr, "Audit")

    self.api = Api()
    self.objgen = generator.ObjectGenerator()
    self.objgen.api = self.api

    self.admin_control_id = {
        name: id for id, name
        in access_control.role.get_custom_roles_for("Control").items()
    }["Admin"]
    if user_id:
      self.user_id = user_id
      user = all_models.Person.query.get(user_id)
      self.api.set_user(user)

  def create(self):
    """Create new Audit object."""
    return self.api.post(all_models.Audit, {
        "audit": {
            "title": "New audit",
            "program": {"id": self.program_id},
            "context": None,
            "access_control_list": [],
        }
    })

  def read(self):
    """Read existing Audit object."""
    return self.api.get(all_models.Audit, self.audit_id)

  def update(self):
    """Update title of existing Audit object."""
    audit = all_models.Audit.query.get(self.audit_id)
    return self.api.put(audit, {"title": factories.random_str()})

  def delete(self):
    """Delete Audit object."""
    audit = all_models.Audit.query.get(self.audit_id)
    return self.api.delete(audit)

  def clone(self):
    """Clone existing Audit with Assessment Templates."""
    return self.api.post(all_models.Audit, {
        "audit": {
            "program": {"id": self.program_id, "type": "Program"},
            # workaround - title is required for validation
            "title": "test title",
            "context": None,
            "operation": "clone",
            "cloneOptions": {
                "sourceObjectId": self.audit_id,
                "mappedObjects": "AssessmentTemplate"
            }
        }
    })

  def read_revisions(self):
    """Read revisions for Audit object."""
    model_class = get_model("Audit")
    responses = []
    for query in ["source_type={}&source_id={}",
                  "destination_type={}&destination_id={}",
                  "resource_type={}&resource_id={}"]:
      responses.append(
          self.api.get_query(model_class, query.format("audit", self.audit_id))
      )
    return responses

  def map_external_control(self):
    """Map Control (on which current user don't have any rights) to Audit."""
    control = factories.ControlFactory()
    audit = all_models.Audit.query.get(self.audit_id)

    return self.objgen.generate_relationship(
        source=audit,
        destination=control,
    )[0]

  def map_control(self):
    """Map new snapshot of Control to Audit."""
    with factories.single_commit():
      control = factories.ControlFactory()
      acl = [
          acl
          for acl in control._access_control_list
          if acl.ac_role_id == self.admin_control_id
      ][0]
      factories.AccessControlPersonFactory(
          person_id=self.user_id,
          ac_list=acl
      )
    audit = all_models.Audit.query.get(self.audit_id)

    return self.objgen.generate_relationship(
        source=audit,
        destination=control,
    )[0]

  def deprecate(self):
    """Set status 'Deprecated' for Audit."""
    audit = all_models.Audit.query.get(self.audit_id)
    return self.api.modify_object(audit, {
        "status": "Deprecated"
    })

  def archive(self):
    """Move Audit into archived state."""
    audit = all_models.Audit.query.get(self.audit_id)
    return self.api.modify_object(audit, {
        "archived": True
    })

  def unarchive(self):
    """Move Audit into unarchived state."""
    audit = all_models.Audit.query.get(self.audit_id)
    return self.api.modify_object(audit, {
        "archived": False
    })

  def summary(self):
    """Get Audit summary information."""
    return self.api.client.get(
        "api/audits/{}/{}".format(self.audit_id, "summary")
    )
