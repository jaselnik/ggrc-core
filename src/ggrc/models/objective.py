# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for Objective model."""

from ggrc import db
from ggrc.access_control import roleable
from ggrc.fulltext import mixin as ft_mixins
from ggrc.models import comment
from ggrc.models import mixins
from ggrc.models import object_document
from ggrc.models import object_person
from ggrc.models import relationship
from ggrc.models import review


class Objective(mixins.synchronizable.Synchronizable,
                mixins.WithExternalCreatedBy,
                comment.ExternalCommentable,
                mixins.with_last_assessment_date.WithLastAssessmentDate,
                roleable.Roleable,
                review.Reviewable,
                mixins.CustomAttributable,
                mixins.WithStartDate,
                mixins.WithLastDeprecatedDate,
                relationship.Relatable,
                object_person.Personable,
                object_document.PublicDocumentable,
                mixins.TestPlanned,
                mixins.with_similarity_score.WithSimilarityScore,
                mixins.base.ContextRBAC,
                mixins.BusinessObject,
                mixins.Folderable,
                mixins.WithWorkflowState,
                ft_mixins.Indexed,
                db.Model):
  """Class representing Objective."""

  __tablename__ = 'objectives'
  _include_links = []
  _aliases = {
      "documents_file": None,
  }
