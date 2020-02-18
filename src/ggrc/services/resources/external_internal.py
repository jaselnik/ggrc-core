# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""API resource for models that can be as external as internal."""

from ggrc import login
from ggrc.services import common
from ggrc.utils.validators import ggrcq


class ExternalInternalResource(common.Resource):
  """Resource handler for models that can work as external and as internal."""
  # pylint: disable=abstract-method

  def validate_headers_for_put_or_delete(self, obj):
    """Check ETAG for internal request and skip for external."""
    if login.is_external_app_user():
      return None
    return super(
        ExternalInternalResource, self
    ).validate_headers_for_put_or_delete(obj)


class ExternalInternalCADResource(ExternalInternalResource):
  """Resource handler for CustomAttributeDefinition model."""

  def put(self, id):
    """
        This is to extend the put request for additional data.
    Args:
      id: int() requested object id.
    Returns:
        View function
    """
    from ggrc.models import CustomAttributeDefinition as cad

    obj = cad.query.get(id)
    src = common.request.json["custom_attribute_definition"]
    read_only_attrs = {"title", }
    if src.get("multi_choice_options"):
      read_only_attrs.add("multi_choice_options")
    for attr in read_only_attrs:
      ggrcq.validate_cad_attrs_update(obj, src, attr)

    return super(ExternalInternalCADResource, self).put(id)
