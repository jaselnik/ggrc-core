# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module with tools to move from html to markdown."""

from HTMLParser import HTMLParser


class HTML2MarkdownParser(HTMLParser, object):
  """HTMLParser for moving html text to markdown.

    1) Will replace html links <a href="..."> with markdown links (...)[...].
    2) Will replace <li> with dash sign "-" and </li> with a newline symbol.
    3) Will replace 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'br' html tags
       with newline symbol.
    4) Will replace 'strong', 'i', 'b', 'div', 'p', 'dl', 'dt' html tags
       with whitespaces.
    5) Will preserve the source content of <img> tag.
    6) Will delete all other html tags.
    7) Will replace mailto links with a format +some@email.com

    self.parsed_data - is cleaned data without html tags.
  """

  LINK_TAG = "a"
  LIST_TAG = "li"
  IMAGE_TAG = "img"
  NEWLINE = "\n"
  TAGS_TO_REPLACE_WITH_SPACES = ['strong', 'i', 'b', 'div', 'p', 'dl', 'dt']
  TAGS_TO_REPLACE_WITH_NEWLINE = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                                  'hr', 'br']

  def __init__(self):
    """Initialize parser."""
    super(HTML2MarkdownParser, self).__init__()
    self._clean()

  def _clean(self):
    """Initialize internal fields."""
    self.parsed_data = []
    self.tags_stack = []
    self.current_link = ''
    self.current_link_data = []

  def feed(self, data):
    """Feed HTML data to the parser."""
    if not data:
      return data
    self._clean()
    super(HTML2MarkdownParser, self).feed(data)
    return self.get_data()

  def get_data(self):
    """Get data after parsing."""
    return (u''.join(self.parsed_data)).strip()

  def handle_endtag(self, tag):
    """Handle ending html tag"""
    lower_tag = tag.lower()
    if lower_tag == self.LINK_TAG and self.current_link:
      data = ''.join(self.current_link_data)
      link_title = 'link' if not data or data.isspace() else data
      self.parsed_data.append("[" + link_title + "]")
      self.parsed_data.append(self.current_link)
    elif (lower_tag in self.TAGS_TO_REPLACE_WITH_NEWLINE or
          lower_tag == self.LIST_TAG):
      self.parsed_data.append(self.NEWLINE)
    elif lower_tag in self.TAGS_TO_REPLACE_WITH_SPACES:
      self.parsed_data.append(' ')
    if self.tags_stack and self.tags_stack[-1] == lower_tag:
      self.tags_stack.pop(-1)

  def handle_starttag(self, tag, attrs):
    """Handle starting html tag."""
    lower_tag = tag.lower()
    self.tags_stack.append(lower_tag)
    attrs_dict = {key: value for key, value in attrs}
    if lower_tag == self.LINK_TAG:
      href = attrs_dict.get('href', '')
      # pylint: disable=attribute-defined-outside-init
      if href.startswith('mailto:'):
        self.current_link = ''
        self.parsed_data.append('+' + href.replace('mailto:', ''))
      else:
        self.current_link = "(" + href + ")" if href else ''
      self.current_link_data = []
      # pylint: enable=attribute-defined-outside-init
    elif lower_tag == self.LIST_TAG:
      self.parsed_data.append('- ')
    elif lower_tag == self.IMAGE_TAG:
      src = attrs_dict.get('src', '')
      self.parsed_data.append(src)
    elif lower_tag in self.TAGS_TO_REPLACE_WITH_NEWLINE:
      self.parsed_data.append(self.NEWLINE)
    elif lower_tag in self.TAGS_TO_REPLACE_WITH_SPACES:
      self.parsed_data.append(' ')

  def handle_data(self, data):
    """Handle data inside or outside tags."""
    if not self.tags_stack and data:
      self.parsed_data.append(data)
    else:
      if self.tags_stack[-1] == self.LINK_TAG:
        if self.current_link:
          self.current_link_data.append(data)
      else:
        self.parsed_data.append(data)
