# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Handlers evidence entries."""
from logging import getLogger

from ggrc import db
from ggrc.models import all_models
from ggrc.converters import errors
from ggrc.converters.handlers import handlers
from ggrc.login import get_current_user_id
from ggrc.converters.handlers.file_handler import FileHandler
from ggrc.services import signals


logger = getLogger(__name__)


class EvidenceHandler(object):
  """Base Evidence Handler for file on csv imports."""
  # pylint: disable=too-few-public-methods

  def _get_old_map(self):
    pass

  def set_value(self):
    """This should be ignored with second class attributes."""

  def _parse_item(self):
    """Parse evidence link lines.

    Returns:
      list of evidences for all URLs and evidences.
    """
    evidences = []
    if self.raw_value:
      seen_links = set()
      duplicate_links = set()
      user_id = get_current_user_id()

      for line in self.raw_value.splitlines():
        link = line.strip()
        if not link:
          continue

        if link not in seen_links:
          seen_links.add(link)
          evidences.append(self.build_evidence(link, user_id))
        else:
          duplicate_links.add(link)

      if duplicate_links:
        # NOTE: We rely on the fact that links in duplicate_links are all
        # instances of unicode (if that assumption breaks,
        # unicode encode/decode errors can occur for non-ascii link values)
        self.add_warning(errors.DUPLICATE_IN_MULTI_VALUE,
                         column_name=self.display_name,
                         duplicates=u", ".join(sorted(duplicate_links)))

    return evidences


class EvidenceUrlHandler(EvidenceHandler, handlers.ColumnHandler):
  """Handler for Evidence URL field on evidence imports."""

  KIND = all_models.Evidence.URL

  def _get_old_map(self):
    return {d.link: d for d in self.row_converter.obj.evidences_url}

  def set_obj_attr(self):
    self.value = self.parse_item()

  def get_value(self):
    """Generate a new line separated string for all document links.

    Returns:
      string containing all URLs
    """
    return "\n".join(doc.link for doc in self.row_converter.obj.evidences_url)

  def build_evidence(self, link, user_id):
    """Build evidence object"""
    evidence = all_models.Evidence(
        link=link,
        title=link,
        modified_by_id=user_id,
        context=self.row_converter.obj.context,
        kind=self.KIND,
    )
    evidence.add_admin_role()
    return evidence

  def parse_item(self):
    return self._parse_item()

  def insert_object(self):
    """Update document URL values

    This function adds missing URLs and remove existing ones from Documents.
    The existing URLs with new titles just change the title.
    """
    if self.row_converter.ignore:
      return
    new_link_map = {d.link: d for d in self.value}
    old_link_map = self._get_old_map()

    for new_link, new_evidence in new_link_map.iteritems():
      if new_link not in old_link_map:
        rel_obj = all_models.Relationship(
            source=self.row_converter.obj,
            destination=new_evidence
        )
        signals.Restful.model_posted.send(rel_obj.__class__, obj=rel_obj)
      else:
        db.session.expunge(new_evidence)

    for old_link, old_evidence in old_link_map.iteritems():
      if old_link in new_link_map:
        continue
      if old_evidence.related_destinations:
        signals.Restful.model_deleted.send(
            old_evidence.__class__,
            obj=old_evidence
        )
        old_evidence.related_destinations.pop()
      elif old_evidence.related_sources:
        signals.Restful.model_deleted.send(
            old_evidence.__class__,
            obj=old_evidence
        )
        old_evidence.related_sources.pop()
      else:
        logger.warning("Invalid relationship state for document URLs.")


class EvidenceFileHandler(EvidenceHandler, FileHandler,
                          handlers.ColumnHandler):
  """Handler for evidence of type file on evidence imports."""

  files_object = "evidences_file"
  file_error = errors.DISALLOW_EVIDENCE_FILE
  KIND = all_models.Evidence.FILE

  def _get_old_map(self):
    return {d.link: d for d in self.row_converter.obj.evidences_file}

  def _get_new_map(self):
    from ggrc.gdrive.file_actions import get_gdrive_file_link
    return {get_gdrive_file_link(d): d for d in self.value}

  def set_obj_attr(self):
    self.value = self.parse_item()

  def build_evidence(self, link, user_id):
    """Build evidence object"""
    # pylint:disable=no-self-use,unused-argument
    return link

  def build_files(self):  # pylint: disable=inconsistent-return-statements
    if self.row_converter.block_converter.converter.is_bulk_import():
      return self._parse_item()

  def insert_object(self):
    """Update document URL values

    This function adds missing URLs and remove existing ones from Documents.
    The existing URLs with new titles just change the title.
    """
    if self.row_converter.ignore or not \
       self.row_converter.block_converter.converter.is_bulk_import():
      return
    new_link_map = self._get_new_map()
    old_link_map = self._get_old_map()

    user_id = get_current_user_id()

    for new_link, new_gdrive_id in new_link_map.iteritems():
      if new_link not in old_link_map:
        self.setup_evidence(new_gdrive_id, user_id)

    for old_link, old_evidence in old_link_map.iteritems():
      if old_link in new_link_map:
        continue
      if old_evidence.related_destinations:
        signals.Restful.model_deleted.send(
            old_evidence.__class__,
            obj=old_evidence
        )
        old_evidence.related_destinations.pop()
      elif old_evidence.related_sources:
        signals.Restful.model_deleted.send(
            old_evidence.__class__,
            obj=old_evidence
        )
        old_evidence.related_sources.pop()
      else:
        logger.warning("Invalid relationship state for document URLs.")

  def setup_evidence(self, source_gdrive_id, user_id):
    """Generate Evidence File object"""

    parent = self.row_converter.obj

    evidence = all_models.Evidence(title=source_gdrive_id,
                                   modified_by_id=user_id,
                                   context=parent.context,
                                   kind=self.KIND,
                                   source_gdrive_id=source_gdrive_id,
                                   parent_obj={
                                       'id': parent.id,
                                       'type': parent.__class__.__name__
                                   })
    evidence.add_admin_role()
    rel_obj = all_models.Relationship(
        source=all_models.Assessment.query.get(parent.id),
        destination=evidence
    )
    signals.Restful.model_posted.send(rel_obj.__class__, obj=rel_obj)
