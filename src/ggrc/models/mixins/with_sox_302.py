# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Contains `WithSOX302` mixin."""


from ggrc import sox
from ggrc.builder import simple_property
from ggrc.models.mixins import customattributable
from ggrc.models.mixins import rest_handable
from ggrc.models.mixins import statusable


class WithSOX302Flow(rest_handable.WithPutBeforeCommitHandable):
  """Mixin which adds a support of SOX 302 flow."""

  @simple_property
  def sox_302_enabled(self):
    """Flag defining if SOX 302 flow is activated for object."""
    return self.verification_workflow == sox.VerificationWorkflow.SOX302

  def _has_negative_cavs(self):
    """Check if current object has any CAVs with values marked as negative."""
    from ggrc.models.custom_attribute_value \
        import CustomAttributeValue as cav_model

    local_cads = {
        # pylint: disable=access-member-before-definition,
        # pylint: disable=attribute-defined-outside-init
        cad.id: cad for cad in self.local_custom_attribute_definitions
    }

    local_cavs = []
    if local_cads:
      local_cavs = cav_model.query.filter(
          cav_model.custom_attribute_id.in_(local_cads.keys()),
      ).all()

    return any(
        local_cads[cav.custom_attribute_id].is_value_negative(cav)
        for cav in local_cavs
    )

  def exec_sox_302_status_flow(self, initial_state):
    # type: (collections.namedtuple) -> None
    """Execute SOX 302 status change flow.

    Perform SOX 302 status change flow for object method is called on. Current
    object should be instance of `statusable.Statusable` and should have flag
    `sox_302_enabled` set to `True` in order for SOX 302 to be executed.

    Args:
      initial_state (collections.namedtuple): Initial state of the object.
    """
    follow_sox_302_flow = (
        isinstance(self, statusable.Statusable) and
        isinstance(self, customattributable.CustomAttributable) and
        self.sox_302_enabled
    )

    # pylint: disable=access-member-before-definition,
    # pylint: disable=attribute-defined-outside-init
    moved_in_review = (
        initial_state.status != self.status and
        self.status == statusable.Statusable.DONE_STATE
    )

    if (
        follow_sox_302_flow and
        moved_in_review and
        not self._has_negative_cavs()
    ):
      self.status = statusable.Statusable.FINAL_STATE

  def handle_put_before_commit(self, initial_state):
    # type: (collections.namedtuple) -> None
    """Handle `model_put_before_commit` signals.

    This method is called after `model_put_before_commit` signal is being sent.
    Triggers SOX 302 status change flow.

    Args:
      initial_state (collections.namedtuple): Initial state of the object.
    """
    self.exec_sox_302_status_flow(initial_state)
