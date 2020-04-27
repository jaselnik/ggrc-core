# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration tests for WithSimilarityScore logic.

These tests use a bit more complex test case generation with DDT in order for
the test cases themselves to be easier to read and understand.
"""

import json

import ddt

from ggrc import db
from ggrc import models

from integration.ggrc.models import factories
from integration.ggrc.models.test_assessment_base import TestAssessmentBase


def expand_test_cases(*argv):
  """Expand the DDT test cases to a more suitable form.

  This function expands a test case in form of

  Input: (
      [A, B, C],     # Assessments related to each other.
      [(A,B), (A,C)] # Relationships needed for assessments to be related.
  )

  Output: (
    A,               # Tested assessment title
    [B, C]           # Assessments that are relevant to it
    [(A,B), (A,C)]   # Relationships, unchanged.
  ), (
    B,               # Second assessment to be tested
    [A, C]           # Assessments that are relevant to it
    [(A,B), (A,C)]   # unchanged
  ), (
    C,               # Same
    [A, B]
    [(A,B), (A,C)]
  )

  Reasoning:

    The first form is a lot easier to write and read and also less error prone
    when copy pasting to create different test cases. Second form is easier to
    test. Initial test only used the second expanded form but the number of
    test cases rose too fast and it was not clear or readable. The first
    concise form was then introduced, but the problems with it were that same
    test had to check multiple things, meaning either ugly try catch or missing
    bugs until previous tests are fixed.

    Both forms were then joined by using this function at the expense of a bit
    more complexity to understand the code, but with the benefit of easier to
    read and understand tests.
  """
  for related_assessments, relationships in argv:
    for assessment in related_assessments:
      expected_assessments = list(related_assessments)
      expected_assessments.remove(assessment)
      yield assessment, expected_assessments, relationships


@ddt.ddt
class TestRelatedAssessments(TestAssessmentBase):
  """Comprehensive tests for all related assessment cases.

  For easier reading these tests will utilize DDT with complex setup data.
  All data in the test will be referred to by its title and all titles will be
  unique in form of object type + id . For snapshots we will create fake titles
  that will be composed by the keyword snapshot + audit title + object title.
  Since we can not have more than one version of an object snapshot in an
  audit, the given title also addresses a single snapshot revision.

  Relationships will be pairs with
  (source title, destination title)

  All tests will come with the base setup data that will contain:

    "Control 1"
    "Control 2"
    "Requirement 1"
    "Requirement 2"
    "Program 1"
      "Audit 1"
        "Assessment 1" - Type Control
        "Assessment 2" - Type Control
        "Assessment 3" - Type Control
        "Assessment 4" - Type Requirement
        "Assessment 5" - Type Requirement
        "Assessment 6" - Type Standard
        "Snapshot Audit 1 Control 1"
        "Snapshot Audit 1 Control 2"
        "Snapshot Audit 1 Requirement 1"
        "Snapshot Audit 1 Requirement 2"

      "Audit 2"
        "Assessment 7" - Type Control
        "Assessment 8" - Type Control
        "Snapshot Audit 2 Control 1"
        "Snapshot Audit 2 Control 2"

    "Program 2"
      "Audit 3"
        "Assessment 9" - Type Control
        "Assessment 10" - Type Requirement
        "Snapshot Audit 3 Control 1"
        "Snapshot Audit 3 Control 2"
        "Snapshot Audit 3 Requirement 1"
        "Snapshot Audit 3 Requirement 2"


  Example of a single test case:

    (
        ["Assessment 1", "Assessment 7", "Assessment 9"],
        [
            ("Assessment 1", "Snapshot Audit 1 Control 1"),
            ("Assessment 7", "Snapshot Audit 2 Control 1"),
            ("Assessment 9", "Snapshot Audit 3 Control 1"),
        ]
    )

    In this example we fill first create relationships between assessment 1 and
    snapshot of control one in audit 1, and so on.

    Then we check related assessments for Assessment 1 and assert that related
    assessments contain both Assessment 7 and 9.
    Then we also check the same for Assessment 7 that it contains 1 and 9,
    and similarly for Assessment 9.

    Tests cases will also sometimes just have source and destination swapped
    to ensure that all cases are covered.
  """

  def _create_obj(self, factory, title, **kwargs):
    """Create an object and store it to local object_map dict."""
    obj = factory(title=title, **kwargs)
    self.object_map[title] = obj
    return obj

  def _create_assessments(self, audit, types, offset=1):
    """Create one assessment for each assessment type in a given audit."""
    user = models.Person.query.first()

    for i, type_ in enumerate(types):
      assessment = self._create_obj(
          factories.AssessmentFactory,
          "Assessment {}".format(i + offset),
          audit=audit,
          assessment_type=type_,
      )
      if i % 2 == 0:
        factories.RelationshipFactory(source=audit, destination=assessment)
      else:
        factories.RelationshipFactory(source=assessment, destination=audit)

      factories.AccessControlPersonFactory(
          ac_list=assessment.acr_name_acl_map["Assignees"],
          person=user,
      )
      factories.AccessControlPersonFactory(
          ac_list=assessment.acr_name_acl_map["Creators"],
          person=user,
      )

  def _create_relationship(self, pair):
    """Create a single relationship with object title pairs."""
    factories.RelationshipFactory(
        source=self.object_map[pair[0]],
        destination=self.object_map[pair[1]],
    )

  def _create_relationships(self, pairs):
    """Create relationships between object pairs."""
    with factories.single_commit():
      for pair in pairs:
        self._create_relationship(pair)

  def setUp(self):
    super(TestRelatedAssessments, self).setUp()
    self.client.get("/login")
    self.object_map = {}

    # pylint: disable=invalid-name
    # this is just to keep simple names for controls and requirements such as
    # c1, c2 and so on for cleaner code. The names are only used in the setUp
    # stage so it should be fine to disable pylint in this case.

    with factories.single_commit():
      program_1 = factories.ProgramFactory(title="Program 1")
      program_2 = factories.ProgramFactory(title="Program 2")
      audit_1 = factories.AuditFactory(title="Audit 1", program=program_1)
      audit_2 = factories.AuditFactory(title="Audit 2", program=program_1)
      audit_3 = factories.AuditFactory(title="Audit 3", program=program_2)

      types = ["Control", "Control", "Control", "Requirement", "Standard"]
      self._create_assessments(audit_1, types, offset=1)

      types = ["Control", "Control"]
      self._create_assessments(audit_2, types, offset=7)

      types = ["Control"]
      self._create_assessments(audit_3, types, offset=9)

      c1 = self._create_obj(factories.ControlFactory, "Control 1")
      c2 = self._create_obj(factories.ControlFactory, "Control 2")

    snapshots = []
    snapshots.extend(self._create_snapshots(audit_1, [c1, c2]))

    c2.description = "edited"
    # pylint: disable=protected-access
    factories.ModelFactory._log_event(c2, "PUT")
    db.session.commit()

    snapshots.extend(self._create_snapshots(audit_2, [c1, c2]))
    snapshots.extend(self._create_snapshots(audit_3, [c1, c2]))

    for snapshot in snapshots:
      title = "Snapshot {} {}".format(
          snapshot.parent.title,
          snapshot.revision.content["title"],
      )
      self.object_map[title] = snapshot

  def _get_related_assessments(self, assessment):
    """Get all assessments related to a given assessment in order.

    Args:
      assessment: Title of the assessment for which we want related
        information.

    Returns:
      Titles of related assessments in given order.
    """

    query = [{
        "object_name": "Assessment",
        "filters": {
            "expression": {
                "object_name": "Assessment",
                "op": {"name": "similar"},
                "ids": [self.object_map[assessment].id]
            }
        },
        "order_by":[
            {"name": "finished_date", "desc": True},
            {"name": "created_at", "desc": True},
        ],
        "limit": [0, 5],
        "type": "ids",  # This is added just for easier testing
    }]
    response = self.client.post(
        "/query",
        data=json.dumps(query),
        headers={"Content-Type": "application/json"},
    )

    ids = response.json[0]["Assessment"]["ids"]
    if not ids:
      return []

    assessments = models.Assessment.query.filter(models.Assessment.id.in_(ids))
    id_title_map = {
        assessment.id: assessment.title
        for assessment in assessments
    }
    return [id_title_map[id_] for id_ in ids]

  @ddt.data(*expand_test_cases(
      # No related assessments
      (["Assessment 1"], []),
      (["Assessment 1"], [
          ("Assessment 1", "Snapshot Audit 1 Control 1"),
          ("Snapshot Audit 1 Control 2", "Assessment 1"),
      ]),
      (["Assessment 1"], [
          ("Assessment 1", "Snapshot Audit 1 Control 1"),
          ("Snapshot Audit 1 Control 2", "Assessment 2"),
      ]),
      (["Assessment 1"], [
          ("Assessment 1", "Snapshot Audit 1 Control 1"),
          ("Assessment 2", "Snapshot Audit 1 Control 2"),
          ("Assessment 7", "Snapshot Audit 2 Control 2"),
          ("Assessment 9", "Snapshot Audit 3 Control 2"),
      ]),
      (["Assessment 1"], [  # source and destination swapped
          ("Snapshot Audit 1 Control 1", "Assessment 1"),
          ("Snapshot Audit 1 Control 2", "Assessment 2"),
          ("Snapshot Audit 2 Control 2", "Assessment 7"),
          ("Snapshot Audit 3 Control 2", "Assessment 9"),
      ]),


      # Assessments related with the same object

      # Assessment 1 and 2 related to the same snapshot.
      # Src and dst swapped
      (["Assessment 1", "Assessment 2"], [
          ("Assessment 1", "Snapshot Audit 1 Control 1"),
          ("Snapshot Audit 1 Control 1", "Assessment 2"),
      ]),
      (["Assessment 1", "Assessment 2"], [
          ("Snapshot Audit 1 Control 1", "Assessment 1"),
          ("Assessment 2", "Snapshot Audit 1 Control 1"),
      ]),

      # Assessment 1, 2, and 3 related to the same snapshot.
      (["Assessment 1", "Assessment 2", "Assessment 3"], [
          ("Assessment 1", "Snapshot Audit 1 Control 1"),
          ("Snapshot Audit 1 Control 1", "Assessment 2"),
          ("Assessment 3", "Snapshot Audit 1 Control 1"),
      ]),

      # Assessment 1, 2, 7, and 9 related to different snapshot of the same
      # object. Assessment 10 is excluded because it has a different type.
      (["Assessment 1", "Assessment 2", "Assessment 7", "Assessment 9"], [
          ("Assessment 1", "Snapshot Audit 1 Control 1"),
          ("Snapshot Audit 1 Control 1", "Assessment 2"),
          ("Assessment 7", "Snapshot Audit 2 Control 1"),
          ("Snapshot Audit 3 Control 1", "Assessment 9"),
      ]),

      # Assessments mapped to snapshots of two different related objects
      # diagram 2 from the new related assessments spec.

      (["Assessment 1", "Assessment 2"], [
          ("Assessment 1", "Snapshot Audit 1 Control 1"),
          ("Assessment 2", "Snapshot Audit 1 Control 2"),
          ("Control 1", "Control 2"),
      ]),
      (["Assessment 1", "Assessment 2"], [
          ("Snapshot Audit 1 Control 1", "Assessment 1"),
          ("Assessment 2", "Snapshot Audit 1 Control 2"),
          ("Control 2", "Control 1"),
      ]),
      (["Assessment 1", "Assessment 2"], [
          ("Snapshot Audit 1 Control 1", "Assessment 1"),
          ("Snapshot Audit 1 Control 2", "Assessment 2"),
          ("Control 2", "Control 1"),
      ]),
      (["Assessment 1", "Assessment 2", "Assessment 7", "Assessment 9"], [
          ("Assessment 1", "Snapshot Audit 1 Control 2"),
          ("Snapshot Audit 1 Control 1", "Assessment 2"),
          ("Assessment 7", "Snapshot Audit 2 Control 2"),
          ("Snapshot Audit 3 Control 1", "Assessment 9"),
          ("Control 2", "Control 1"),
      ]),
  ))
  @ddt.unpack
  # NOTE: Function parameters are generated! See expand_test_cases
  def test_no_related(self, assessment, related_assessments, relationships):
    """Test related assessments with the given set of relationships.

    This test checks that all and only related assessments are returned with
    the related assessments query.

    Args:
      assessment: Title of the assessment for which related assessments will be
        tested.
      related_assessments: list of all assessment titles that should be related
        to the assessment that is being checked.
      relationships: list of title pairs for all relationships that should be
        created before running the tests. First item in the pair is a title for
        the source object, second item is the title for the destination object.
    """
    self._create_relationships(relationships)
    self.assertItemsEqual(
        self._get_related_assessments(assessment),
        related_assessments,
    )
