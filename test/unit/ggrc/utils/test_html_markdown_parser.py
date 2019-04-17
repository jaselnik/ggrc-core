# -*- coding: utf-8 -*-

# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module with tests for HTML parser."""

import unittest
import ddt

from ggrc.migrations.utils import html_markdown_parser


@ddt.ddt
class TestHTML2MarkdownParser(unittest.TestCase):
  """Test HTML2MarkdownParser class."""

  def setUp(self):
    """Set up for test cases."""
    super(TestHTML2MarkdownParser, self).setUp()
    self.parser = html_markdown_parser.HTML2MarkdownParser()

  @ddt.data(
      (u'<a href="https://www.google.com/">some url</a>',
       u'[some url](https://www.google.com/)'),
      (u'<a href="https://www.google.com/">тест</a>',
       u'[тест](https://www.google.com/)'),
      (u'<a href="https://www.google.com/"> </a>',
       u'[link](https://www.google.com/)'),
      (u'<a href="https://www.google.com/">Some text</a>',
       u'[Some text](https://www.google.com/)'),
      (u'<p><a href="http://localhost:8080/abc">abc</a> '
       u'<a href="http://localhost:8080/qwerty">qwerty</a></p>',
       u'[abc](http://localhost:8080/abc) '
       u'[qwerty](http://localhost:8080/qwerty)'),
      (u'qwerty</a>', u'qwerty'),
  )
  @ddt.unpack
  def test_parse_url(self, html_data, markdown_data):
    """Tests parsing html url."""
    self.parser.feed(html_data)
    self.assertEquals(self.parser.get_data(), markdown_data)

  @ddt.data(
      (u'<img src="https://www.google.com/"/>',
       u'https://www.google.com/'),
      (u'<img src=""/>', u''),
  )
  @ddt.unpack
  def test_parse_image_tag(self, html_data, markdown_data):
    """Tests parsing html tags."""
    self.parser.feed(html_data)
    self.assertEquals(self.parser.get_data(), markdown_data)

  @ddt.data('strong', 'i', 'b', 'div', 'p', 'dl', 'dt')
  def test_replace_html_tags_spaces(self, html_tag):
    """Test replacing html tags with spaces."""
    html_data = "here<{tag}>some</{tag}>text".format(tag=html_tag)
    markdown_data = "here some text"
    self.parser.feed(html_data)
    self.assertEquals(self.parser.get_data(), markdown_data)

  @ddt.data('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'br')
  def test_replace_html_tags_newlines(self, html_tag):
    """Test replacing html tags with spaces."""
    html_data = "here<{tag}>some</{tag}>text".format(tag=html_tag)
    markdown_data = "here\nsome\ntext"
    self.parser.feed(html_data)
    self.assertEquals(self.parser.get_data(), markdown_data)

  @ddt.data(
      (u'<ul><li>1</li><li>2</li></ul>', u'- 1\n- 2'),
      (u'<ol><li>1</li><li>2</li></ol>', u'- 1\n- 2'),
  )
  @ddt.unpack
  def test_parse_html_list(self, html_data, markdown_data):
    """Tests parsing html lists."""
    self.parser.feed(html_data)
    self.assertEquals(self.parser.get_data(), markdown_data)

  def test_unicode(self):
    """Test parsing string with unicode chars."""
    html_data = u"• one <br>• two <br>"
    self.parser.feed(html_data)
    self.assertEquals(self.parser.get_data(), u'\u2022 one \n\u2022 two')

  @ddt.data(
      (u'<a href="mailto:other_user@example.com">user@example.com</a>',
       u'+other_user@example.com'),
      (u'<a href=" mailto:other_user@example.com">user@example.com</a>',
       u'[user@example.com]( mailto:other_user@example.com)'),
      (u'<a href="mailto:first@example.com">user@example.com</a> '
       u'<a href="mailto:second@example.com">user@example.com</a> '
       u'<a href="mailto:third@example.com">user@example.com</a> ',
       u'+first@example.com +second@example.com +third@example.com'),
      (u'<a href="mailto:external@example.com">user@example.com '
       u'<a href="mailto:internal@example.com">user@example.com</a></a> ',
       u'+external@example.com+internal@example.com'),
  )
  @ddt.unpack
  def test_people_mentions_parse(self, html_data, markdown_data):
    """Test parsing of people mentions."""
    self.parser.feed(html_data)
    self.assertEquals(self.parser.get_data(), markdown_data)
