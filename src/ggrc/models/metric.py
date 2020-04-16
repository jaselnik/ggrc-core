# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Metric model."""

from ggrc import db
from ggrc.fulltext.mixin import Indexed
from ggrc.models.comment import ScopedCommentable
from ggrc.models import mixins
from ggrc.models.mixins import synchronizable
from ggrc.models.object_document import PublicDocumentable
from ggrc.models.object_person import Personable
from ggrc.models.relationship import Relatable


class Metric(Personable,
             synchronizable.RoleableSynchronizable,
             Relatable,
             synchronizable.Synchronizable,
             PublicDocumentable,
             ScopedCommentable,
             mixins.TestPlanned,
             mixins.LastDeprecatedTimeboxed,
             mixins.CustomAttributable,
             mixins.ScopeObject,
             mixins.base.ContextRBAC,
             mixins.Folderable,
             mixins.WithWorkflowState,
             Indexed,
             db.Model):
  """Representation for Metric model."""
  __tablename__ = 'metrics'
