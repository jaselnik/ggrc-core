# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for threat model."""

from ggrc import db
from ggrc.fulltext import mixin as ft_mixins
from ggrc.models import comment
from ggrc.models import mixins
from ggrc.models import object_document
from ggrc.models import object_person
from ggrc.models import relationship


class Threat(mixins.synchronizable.Synchronizable,
             mixins.synchronizable.RoleableSynchronizable,
             mixins.WithExternalCreatedBy,
             comment.ExternalCommentable,
             mixins.CustomAttributable,
             object_person.Personable,
             relationship.Relatable,
             mixins.LastDeprecatedTimeboxed,
             object_document.PublicDocumentable,
             mixins.TestPlanned,
             mixins.base.ContextRBAC,
             mixins.BusinessObject,
             mixins.Folderable,
             mixins.WithWorkflowState,
             ft_mixins.Indexed,
             db.Model):
  """Threat model."""
  __tablename__ = 'threats'

  _aliases = {
      "documents_file": None,
  }
