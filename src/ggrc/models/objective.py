# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for Objective model."""

from ggrc import db
from ggrc.access_control.roleable import Roleable
from ggrc.fulltext.mixin import Indexed
from ggrc.models.comment import Commentable
from ggrc.models import mixins, review
from ggrc.models.object_document import PublicDocumentable
from ggrc.models.object_person import Personable
from ggrc.models.relationship import Relatable


class Objective(mixins.with_last_assessment_date.WithLastAssessmentDate,
                Roleable,
                review.Reviewable,
                mixins.CustomAttributable,
                mixins.WithStartDate,
                mixins.WithLastDeprecatedDate,
                Relatable,
                Personable,
                PublicDocumentable,
                Commentable,
                mixins.TestPlanned,
                mixins.with_similarity_score.WithSimilarityScore,
                mixins.base.ContextRBAC,
                mixins.BusinessObject,
                mixins.Folderable,
                mixins.WithWorkflowState,
                Indexed,
                db.Model):
  """Class representing Objective."""

  __tablename__ = 'objectives'
  _include_links = []
  _aliases = {
      "documents_file": None,
  }
