# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Base file handlers entries."""


class FileHandler(object):
  """Base File Handler for file on csv imports."""

  @staticmethod
  def _parse_line(line):
    """Parse a single line and return link.

    Args:
      line: string containing a single line from a cell.

    Returns:
      string containing a link or empty string.
    """
    parts = line.strip().split()
    return parts[0] if parts else ''

  def insert_object(self):
    """Import not allowed"""
    pass

  def get_value(self):
    """Generate a new line separated string for all links.

    Returns:
      string containing all URLs and titles.
    """
    return u"\n".join(
        u"{} {}".format(d.link, d.title)
        for d in getattr(self.row_converter.obj, self.files_object)
    )

  def build_files(self):
    pass

  def parse_item(self):  # pylint: disable=inconsistent-return-statements
    """Is not allowed to import document of type File

    if file already mapped to parent we ignore it and not show warning
    """

    if self.row_converter.block_converter.converter.is_bulk_import():
      return self.build_files()
    if self.raw_value:
      parent = self.row_converter.obj
      existing_file_links = {
          file.link for file in getattr(parent, self.files_object)
      }

      for line in self.raw_value.splitlines():
        if line:
          link = self._parse_line(line)
          if link and link not in existing_file_links:
            self.add_warning(self.file_error, parent=parent.type)
