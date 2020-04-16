# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Module for OrgGroup object"""
from ggrc import db
from ggrc.fulltext.mixin import Indexed
from ggrc.models.comment import ScopedCommentable
from ggrc.models import mixins
from ggrc.models.mixins import synchronizable
from ggrc.models.object_document import PublicDocumentable
from ggrc.models.object_person import Personable
from ggrc.models.relationship import Relatable


class OrgGroup(synchronizable.Synchronizable,
               synchronizable.RoleableSynchronizable,
               mixins.CustomAttributable,
               Personable,
               Relatable,
               mixins.LastDeprecatedTimeboxed,
               ScopedCommentable,
               mixins.TestPlanned,
               PublicDocumentable,
               mixins.base.ContextRBAC,
               mixins.ScopeObject,
               mixins.Folderable,
               mixins.WithWorkflowState,
               Indexed,
               db.Model):
  """Class representing OrgGroup."""
  __tablename__ = 'org_groups'
  _aliases = {
      "documents_file": None,
  }

  def __str__(self):
    return self.title
