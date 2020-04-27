# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for people mentions."""

import datetime
from collections import OrderedDict
from urlparse import urljoin

import ddt
import mock
from freezegun import freeze_time

from integration.ggrc import TestCase, api_helper
from integration.ggrc.models import factories
from integration.ggrc.review import generate_review_object
from integration.ggrc_workflows.models import factories as wf_factories

from ggrc import settings
from ggrc import utils
from ggrc.models import all_models
from ggrc.notifications import people_mentions
from ggrc.utils import get_url_root


@ddt.ddt
class TestPeopleMentions(TestCase):
  """Test people mentions notifications."""

  @mock.patch("ggrc.notifications.common.send_email")
  # pylint: disable=no-self-use
  def test_handle_one_comment(self, send_email_mock):
    """Test handling of mapped comment."""
    with factories.single_commit():
      person = factories.PersonFactory(email="author@example.com")
      obj = factories.ProductFactory(title="Product1")
      comment = factories.CommentFactory(
          description=u"One <a href=\"mailto:user@example.com\"></a>",
      )
      comment.modified_by_id = person.id
      comment.created_at = datetime.datetime(2018, 1, 10, 7, 31, 42)
      url = urljoin(get_url_root(), utils.view_url_for(obj))

    people_mentions.handle_comment_mapped(obj, [comment])
    expected_title = (u"author@example.com mentioned you "
                      u"on a comment within Product1")
    expected_body = (
        u"author@example.com mentioned you on a comment within Product1 "
        u"at 01/09/2018 23:31:42 PST:\n"
        u"One <a href=\"mailto:user@example.com\"></a>\n"
    )
    body = settings.EMAIL_MENTIONED_PERSON.render(person_mention={
        "comments": [expected_body],
        "url": url,
    })
    send_email_mock.assert_called_once_with(u"user@example.com",
                                            expected_title, body)

  @mock.patch("ggrc.notifications.common.send_email")
  # pylint: disable=no-self-use
  def test_handle_task_comment(self, send_email_mock):
    """Test handling of mapped comment to cycle task."""
    with factories.single_commit():
      person = factories.PersonFactory(email="author@example.com")
      obj = wf_factories.CycleTaskGroupObjectTaskFactory(
          slug=u"TSK-1",
          title=u"task1",
      )
      comment = factories.CommentFactory(
          description=u"One <a href=\"mailto:user@example.com\"></a>",
      )
      comment.modified_by_id = person.id
      comment.created_at = datetime.datetime(2018, 1, 10, 7, 31, 42)
      url = "http://localhost/dashboard#!task&query=%22task%20slug%22%3DTSK-1"

    people_mentions.handle_comment_mapped(obj, [comment])
    expected_title = (u"author@example.com mentioned you "
                      u"on a comment within task1")
    expected_body = (
        u"author@example.com mentioned you on a comment within task1 "
        u"at 01/09/2018 23:31:42 PST:\n"
        u"One <a href=\"mailto:user@example.com\"></a>\n"
    )
    body = settings.EMAIL_MENTIONED_PERSON.render(person_mention={
        "comments": [expected_body],
        "url": url,
    })
    send_email_mock.assert_called_once_with(u"user@example.com",
                                            expected_title, body)

  @mock.patch("ggrc.notifications.common.send_email")
  # pylint: disable=no-self-use
  def test_handle_empty_comment(self, send_email_mock):
    """Test handling of mapped comment with no mention."""
    with factories.single_commit():
      person = factories.PersonFactory(email="some@example.com")
      obj = factories.ProductFactory(title="Product2")
      comment = factories.CommentFactory(description=u"test")
      comment.created_at = datetime.datetime(2018, 1, 10, 7, 31, 42)
      comment.modified_by_id = person.id
    people_mentions.handle_comment_mapped(obj, [comment])
    send_email_mock.assert_not_called()

  @mock.patch("ggrc.notifications.common.send_email")
  def test_relation_comment_posted(self, send_email_mock):
    """Test sending mention email after posting a relationship to comment."""
    with factories.single_commit():
      author_person = factories.PersonFactory(email="author@example.com")
      factories.PersonFactory(email="some_user@example.com")
      obj = factories.ProductFactory(title="Product3")
      obj_id = obj.id
      comment = factories.CommentFactory(
          description=u"One <a href=\"mailto:some_user@example.com\"></a>",
      )
      comment_id = comment.id
      comment.created_at = datetime.datetime(2018, 07, 10, 8, 31, 42)
      comment.modified_by_id = author_person.id
      url = urljoin(get_url_root(), utils.view_url_for(obj))

    author_person = all_models.Person.query.filter_by(
        email="author@example.com"
    ).one()
    api = api_helper.Api()
    api.set_user(author_person)

    response = api.post(all_models.Relationship, {
        "relationship": {"source": {
            "id": obj_id,
            "type": obj.type,
        }, "destination": {
            "id": comment_id,
            "type": comment.type
        }, "context": None},
    })
    self.assertEqual(response.status_code, 201)

    expected_title = (u"author@example.com mentioned you on "
                      u"a comment within Product3")
    expected_body = (
        u"author@example.com mentioned you on a comment within Product3 "
        u"at 07/10/2018 01:31:42 PDT:\n"
        u"One <a href=\"mailto:some_user@example.com\"></a>\n"
    )
    body = settings.EMAIL_MENTIONED_PERSON.render(person_mention={
        "comments": [expected_body],
        "url": url,
    })
    send_email_mock.assert_called_once_with(u"some_user@example.com",
                                            expected_title, body)

  @mock.patch("ggrc.notifications.common.send_email")
  def test_comment_imported(self, send_email_mock):
    """Test sending mention email after import an object with comments."""
    with factories.single_commit():
      factories.PersonFactory(email="some_user@example.com")
      obj = factories.RegulationFactory(title="Regulation4")
      obj_slug = obj.slug
      url = urljoin(get_url_root(), utils.view_url_for(obj))

    first_comment = u"One <a href=\"mailto:some_user@example.com\"></a>"
    second_comment = u"Two <a href=\"mailto:some_user@example.com\"></a>"

    import_data = OrderedDict(
        [
            ("object_type", "Regulation"),
            ("Code*", obj_slug),
            ("comments", first_comment + u";;" + second_comment)
        ]
    )
    with freeze_time("2018-01-10 07:31:42"):
      response = self.import_data(import_data)
    self._check_csv_response(response, {})
    expected_title = (u"user@example.com mentioned you on "
                      u"a comment within Regulation4")
    body = settings.EMAIL_MENTIONED_PERSON.render(person_mention={
        "comments": [
            (u"user@example.com mentioned you on a comment within Regulation4 "
             u"at 01/09/2018 23:31:42 PST:\n" + first_comment + u"\n"),
            (u"user@example.com mentioned you on a comment within Regulation4 "
             u"at 01/09/2018 23:31:42 PST:\n" + second_comment + u"\n"),
        ],
        "url": url,
    })
    send_email_mock.assert_called_once_with(u"some_user@example.com",
                                            expected_title, body)

  @mock.patch("ggrc.notifications.common.send_email")
  def test_several_mentions_imported(self, send_email_mock):
    """Test sending mention email after import an object with comments
       with mentions of different persons."""
    with factories.single_commit():
      factories.PersonFactory(email="first@example.com")
      factories.PersonFactory(email="second@example.com")
      obj = factories.RegulationFactory(title="Product5")
      obj_slug = obj.slug

    first_comment = u"One <a href=\"mailto:first@example.com\"></a>"
    second_comment = u"Two <a href=\"mailto:second@example.com\"></a>" \
                     u"<a href=\"mailto:first@example.com\"></a>"

    import_data = OrderedDict(
        [
            ("object_type", "Regulation"),
            ("Code*", obj_slug),
            ("comments", first_comment + u";;" + second_comment)
        ]
    )
    with freeze_time("2018-01-10 07:31:42"):
      response = self.import_data(import_data)
    self._check_csv_response(response, {})

    obj = all_models.Regulation.query.filter_by(title="Product5").one()
    url = urljoin(get_url_root(), utils.view_url_for(obj))

    expected_title = (u"user@example.com mentioned you on "
                      u"a comment within Product5")

    first_body = settings.EMAIL_MENTIONED_PERSON.render(person_mention={
        "comments": [
            (u"user@example.com mentioned you on a comment within Product5 "
             u"at 01/09/2018 23:31:42 PST:\n" + first_comment + u"\n"),
            (u"user@example.com mentioned you on a comment within Product5 "
             u"at 01/09/2018 23:31:42 PST:\n" + second_comment + u"\n"),
        ],
        "url": url,
    })
    first_call = mock.call(u"first@example.com", expected_title, first_body)
    second_body = settings.EMAIL_MENTIONED_PERSON.render(person_mention={
        "comments": [(
            u"user@example.com mentioned you on a comment within Product5 "
            u"at 01/09/2018 23:31:42 PST:\n" + second_comment + u"\n"
        )],
        "url": url,
    })
    second_call = mock.call(u"second@example.com", expected_title,
                            second_body)
    send_email_mock.assert_has_calls([second_call, first_call])

  @mock.patch('ggrc.settings.INTEGRATION_SERVICE_URL', new='mock')
  @mock.patch('ggrc.settings.AUTHORIZED_DOMAIN', new='example.com')
  @mock.patch('ggrc.notifications.common.send_email')
  def test_person_mentioned_create(self, send_email_mock, *_):
    """Test that a user with authorized domain is created when mentioned."""
    with factories.single_commit():
      obj = factories.ProductFactory(title="Product6")
      comment = factories.CommentFactory(
          description=u"One <a href=\"mailto:some_new_user@example.com"
                      u"\"></a>",
      )
      comment.created_at = datetime.datetime(2018, 1, 10, 7, 31, 42)

    people_mentions.handle_comment_mapped(obj, [comment])
    person = all_models.Person.query.filter_by(
        email="some_new_user@example.com"
    ).first()
    self.assertIsNotNone(person)
    send_email_mock.assert_called_once()

  @mock.patch("ggrc.notifications.common.send_email")
  @ddt.data(
      all_models.Standard,
      all_models.Program,
      all_models.Regulation,
  )
  def test_review_posted(self, model, send_email_mock):
    """Test mentions in request review comment {}."""
    with factories.single_commit():
      factories.PersonFactory(email="some_user@example.com")
      obj = factories.get_model_factory(model.__name__)()
      url = urljoin(get_url_root(), utils.view_url_for(obj))

    with freeze_time("2018-01-10 07:31:42"):
      resp, _ = generate_review_object(
          obj,
          email_message=u"Test <a href=\"mailto:some_user@example.com\"></a>",
      )
    self.assertEqual(201, resp.status_code)

    expected_title = (u"user@example.com mentioned you on "
                      u"a comment within {title}").format(title=obj.title)
    expected_body = (
        u"user@example.com mentioned you on a comment within {title} "
        u"at 01/09/2018 23:31:42 PST:\n"
        u"<p>Review requested from</p>"
        u"<p>user@example.com</p>"
        u"<p>with a comment:"
        u" Test <a href=\"mailto:some_user@example.com\"></a></p>\n"
    ).format(title=obj.title)
    body = settings.EMAIL_MENTIONED_PERSON.render(person_mention={
        "comments": [expected_body],
        "url": url,
    })
    send_email_mock.assert_called_once_with(u"some_user@example.com",
                                            expected_title, body)

  @mock.patch("ggrc.notifications.common.send_email")
  def test_assessment_comment(self, send_email_mock):  # noqa pylint: disable=no-self-use
    """Test mention in assessment comment"""
    with factories.single_commit():
      person = factories.PersonFactory(email="author@example.com")
      assessment = factories.AssessmentFactory(title='Assessment_1')
      comment = factories.CommentFactory(
          description=u"One <a href=\"mailto:user@example.com\"></a>",
          modified_by_id=person.id,
          created_at=datetime.datetime(2020, 1, 20, 13, 27, 00)
      )

    url = urljoin(get_url_root(), utils.view_url_for(assessment))
    people_mentions.handle_comment_mapped(assessment, [comment])
    expected_title = (u"author@example.com mentioned you "
                      u"on a comment within Assessment_1")
    expected_body = (
        u"author@example.com mentioned you on a comment within Assessment_1 "
        u"at 01/20/2020 05:27:00 PST:\n"
        u"One <a href=\"mailto:user@example.com\"></a>\n"
    )
    body = settings.EMAIL_MENTIONED_PERSON.render(person_mention={
        "comments": [expected_body],
        "url": url,
    })
    send_email_mock.assert_called_once_with(u"user@example.com",
                                            expected_title, body)

  @mock.patch("ggrc.notifications.common.send_email")
  def test_mention_in_propose_change(self, send_email_mock):  # noqa pylint: disable=no-self-use
    """Test mention a person in Propose Changes"""
    with factories.single_commit():
      person = factories.PersonFactory(email="author@example.com")
      program = factories.ProgramFactory(title="Program_1")
      proposal = factories.ProposalFactory(
          instance=program,
          content={"field": "Test_Program_2"},
          agenda=u"One <a href=\"mailto:user@example.com\"></a>",
          proposed_by=person
      )
      comment = factories.CommentFactory(
          description='Proposal has been created with comment: {}'.format(
              proposal.agenda
          ),
          initiator_instance_id=proposal.id,
          initiator_instance_type="Proposal",
          modified_by_id=person.id,
          created_at=datetime.datetime(2020, 1, 20, 13, 27, 00)
      )

    url = urljoin(get_url_root(), utils.view_url_for(program))
    people_mentions.handle_comment_mapped(program, [comment])
    expected_title = (u"author@example.com mentioned you "
                      u"on a comment within Program_1")
    expected_body = (
        u"author@example.com mentioned you on a comment within Program_1 "
        u"at 01/20/2020 05:27:00 PST:\n"
        u"Proposal has been created with comment: "
        u"One <a href=\"mailto:user@example.com\"></a>\n"
    )
    body = settings.EMAIL_MENTIONED_PERSON.render(person_mention={
        "comments": [expected_body],
        "url": url,
    })
    send_email_mock.assert_called_once_with(u"user@example.com",
                                            expected_title, body)

  @mock.patch("ggrc.notifications.common.send_email")
  def test_mention_in_lca(self, send_email_mock):  # noqa pylint: disable=no-self-use
    """Test mention a person in Comment LCA"""
    with factories.single_commit():
      person = factories.PersonFactory(email="author@example.com")
      assessment = factories.AssessmentFactory(title='Assessment_1')
      cad = factories.CustomAttributeDefinitionFactory(
          title='test_lca',
          definition_type='assessment',
          definition_id=assessment.id,
          attribute_type='Dropdown',
          multi_choice_options='1,2',
          multi_choice_mandatory='1,0'
      )
      factories.CustomAttributeValueFactory(
          custom_attribute=cad,
          attributable=assessment,
          attribute_value='1',
      )
      comment = factories.CommentFactory(
          description=u"One <a href=\"mailto:user@example.com\"></a>",
          modified_by_id=person.id,
          created_at=datetime.datetime(2020, 1, 20, 13, 27, 00),
          custom_attribute_definition_id=cad.id
      )

    url = urljoin(get_url_root(), utils.view_url_for(assessment))
    people_mentions.handle_comment_mapped(assessment, [comment])
    expected_title = (u"author@example.com mentioned you "
                      u"on a comment within Assessment_1")
    expected_body = (
        u"author@example.com mentioned you on a comment within Assessment_1 "
        u"at 01/20/2020 05:27:00 PST:\n"
        u"One <a href=\"mailto:user@example.com\"></a>\n"
    )
    body = settings.EMAIL_MENTIONED_PERSON.render(person_mention={
        "comments": [expected_body],
        "url": url,
    })
    send_email_mock.assert_called_once_with(u"user@example.com",
                                            expected_title, body)
