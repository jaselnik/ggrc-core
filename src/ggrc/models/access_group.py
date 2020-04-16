# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for AccessGroup object"""

from ggrc import db
from ggrc.models.comment import ScopedCommentable
from ggrc.models.mixins import base
from ggrc.models import mixins
from ggrc.models.mixins import synchronizable
from ggrc.models.object_document import PublicDocumentable
from ggrc.models.object_person import Personable
from ggrc.models.relationship import Relatable
from ggrc.fulltext.mixin import Indexed


class AccessGroup(synchronizable.RoleableSynchronizable,
                  PublicDocumentable,
                  ScopedCommentable,
                  synchronizable.Synchronizable,
                  mixins.CustomAttributable,
                  Personable,
                  Relatable,
                  mixins.TestPlanned,
                  mixins.LastDeprecatedTimeboxed,
                  base.ContextRBAC,
                  mixins.ScopeObject,
                  mixins.Folderable,
                  mixins.WithWorkflowState,
                  Indexed,
                  db.Model):
  """Class representing AccessGroup."""

  __tablename__ = 'access_groups'

  _aliases = {
      "documents_file": None,
  }
