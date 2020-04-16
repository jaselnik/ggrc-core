# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

""" Module that contains Vendor model"""


from ggrc import db
from ggrc.fulltext.mixin import Indexed
from ggrc.models.comment import ScopedCommentable
from ggrc.models import mixins
from ggrc.models.mixins import synchronizable
from ggrc.models.object_document import PublicDocumentable
from ggrc.models.object_person import Personable
from ggrc.models.relationship import Relatable


class Vendor(synchronizable.RoleableSynchronizable,
             synchronizable.Synchronizable,
             mixins.CustomAttributable,
             Personable,
             Relatable,
             mixins.LastDeprecatedTimeboxed,
             PublicDocumentable,
             ScopedCommentable,
             mixins.TestPlanned,
             mixins.base.ContextRBAC,
             mixins.ScopeObject,
             mixins.Folderable,
             mixins.WithWorkflowState,
             Indexed,
             db.Model):
  """Class for Vendor model"""
  __tablename__ = 'vendors'

  _aliases = {
      "documents_file": None,
  }
