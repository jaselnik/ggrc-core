# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for threat model."""

from ggrc import db
from ggrc.access_control.roleable import Roleable
from ggrc.fulltext.mixin import Indexed
from ggrc.models import mixins, review
from ggrc.models.comment import Commentable
from ggrc.models.object_document import PublicDocumentable
from ggrc.models.object_person import Personable
from ggrc.models.relationship import Relatable


class Threat(Roleable,
             review.Reviewable,
             mixins.CustomAttributable,
             Personable,
             Relatable,
             mixins.LastDeprecatedTimeboxed,
             PublicDocumentable,
             Commentable,
             mixins.TestPlanned,
             mixins.base.ContextRBAC,
             mixins.BusinessObject,
             mixins.Folderable,
             mixins.WithWorkflowState,
             Indexed,
             db.Model):
  __tablename__ = 'threats'

  _aliases = {
      "documents_file": None,
  }
