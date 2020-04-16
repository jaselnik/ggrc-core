# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""TechnologyEnvironment model."""

from ggrc import db
from ggrc.fulltext.mixin import Indexed
from ggrc.models.comment import ScopedCommentable
from ggrc.models import mixins
from ggrc.models.mixins import synchronizable
from ggrc.models.object_document import PublicDocumentable
from ggrc.models.object_person import Personable
from ggrc.models.relationship import Relatable


class TechnologyEnvironment(mixins.CustomAttributable,
                            synchronizable.Synchronizable,
                            Personable,
                            synchronizable.RoleableSynchronizable,
                            Relatable,
                            PublicDocumentable,
                            ScopedCommentable,
                            mixins.TestPlanned,
                            mixins.LastDeprecatedTimeboxed,
                            mixins.base.ContextRBAC,
                            mixins.ScopeObject,
                            mixins.Folderable,
                            mixins.WithWorkflowState,
                            db.Model,
                            Indexed):
  """Representation for TechnologyEnvironment model."""
  __tablename__ = 'technology_environments'
