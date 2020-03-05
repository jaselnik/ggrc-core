# coding: utf-8

# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

# pylint: disable=too-many-lines,too-many-locals

"""Tests for /query api endpoint."""
import random
import unittest
from datetime import datetime, date
from operator import itemgetter
import mock
import ddt
import freezegun
from flask import json

from ggrc import app
from ggrc import db
from ggrc import models
from ggrc.models import CustomAttributeDefinition as CAD, all_models
from ggrc.models.mixins.synchronizable import Synchronizable
from ggrc.snapshotter.rules import Types
from ggrc.fulltext.attributes import DateValue

from integration.ggrc import TestCase, generator
from integration.ggrc.query_helper import WithQueryApi
from integration.ggrc.models import factories


# to be moved into converters.query_helper
DATE_FORMAT_REQUEST = "%m/%d/%Y"
DATE_FORMAT_RESPONSE = "%Y-%m-%d"


# pylint: disable=too-many-public-methods
@ddt.ddt
class TestAdvancedQueryAPI(WithQueryApi, TestCase):
  """Basic tests for /query api."""

  def setUp(self):
    """Set up for advance query api."""
    super(TestAdvancedQueryAPI, self).setUp()
    self.client.get("/login")
    self.generator = generator.ObjectGenerator()

  def test_basic_query_eq(self):
    """Filter by = operator."""
    title = "Cat ipsum 1"
    factories.ProgramFactory(title="Cat ipsum 1")
    programs = self._get_first_result_set(
        self._make_query_dict("Program", expression=["title", "=", title]),
        "Program",
    )

    self.assertEqual(programs["count"], 1)
    self.assertEqual(len(programs["values"]), programs["count"])
    self.assertEqual(programs["values"][0]["title"], title)

  def test_basic_query_in(self):
    """Filter by ~ operator."""
    title_pattern = "1"
    with factories.single_commit():
      for i in (1, 2, 10, 21, 5):
        factories.ProgramFactory(title="Cat ipsum {}".format(i))

    programs = self._get_first_result_set(
        self._make_query_dict("Program",
                              expression=["title", "~", title_pattern]),
        "Program",
    )

    self.assertEqual(programs["count"], 3)
    self.assertEqual(len(programs["values"]), programs["count"])
    self.assertTrue(all(title_pattern in program["title"]
                        for program in programs["values"]))

  def test_basic_query_ne(self):
    """Filter by != operator."""
    title = "Cat ipsum 1"
    with factories.single_commit():
      for i in (1, 2, 10, 21, 5):
        factories.ProgramFactory(title="Cat ipsum {}".format(i))

    programs = self._get_first_result_set(
        self._make_query_dict("Program",
                              expression=["title", "!=", title]),
        "Program",
    )

    self.assertEqual(programs["count"], 4)
    self.assertEqual(len(programs["values"]), programs["count"])
    self.assertTrue(all(program["title"] != title
                        for program in programs["values"]))

  def test_basic_query_not_in(self):
    """Filter by !~ operator."""
    title_pattern = "1"
    with factories.single_commit():
      for i in (1, 2, 10, 21, 5):
        factories.ProgramFactory(title="Cat ipsum {}".format(i))

    programs = self._get_first_result_set(
        self._make_query_dict("Program",
                              expression=["title", "!~", title_pattern]),
        "Program",
    )

    self.assertEqual(programs["count"], 2)
    self.assertEqual(len(programs["values"]), programs["count"])
    self.assertTrue(all(title_pattern not in program["title"]
                        for program in programs["values"]))

  def test_basic_query_lt(self):
    """Filter by < operator."""
    expected_date = datetime(2015, 5, 18)
    dates = [datetime(2015, 5, 16),
             datetime(2015, 5, 17),
             datetime(2015, 5, 18),
             datetime(2015, 5, 19),
             datetime(2015, 5, 20),
             ]
    with factories.single_commit():
      for start_date in dates:
        factories.ProgramFactory(start_date=start_date)

    programs = self._get_first_result_set(
        self._make_query_dict("Program",
                              expression=["effective date", "<",
                                          expected_date.strftime(
                                              DATE_FORMAT_REQUEST)
                                          ]),
        "Program",
    )

    self.assertEqual(programs["count"], 2)
    self.assertEqual(len(programs["values"]), programs["count"])
    self.assertTrue(
        all(datetime.strptime(program["start_date"],
                              DATE_FORMAT_RESPONSE) < date
            for program in programs["values"]),
    )

  def test_basic_query_gt(self):
    """Filter by > operator."""
    expected_date = datetime(2015, 5, 18)
    dates = [datetime(2015, 5, 16),
             datetime(2015, 5, 17),
             datetime(2015, 5, 18),
             datetime(2015, 5, 19),
             datetime(2015, 5, 20),
             ]
    with factories.single_commit():
      for start_date in dates:
        factories.ProgramFactory(start_date=start_date)
    programs = self._get_first_result_set(
        self._make_query_dict("Program",
                              expression=["effective date", ">",
                                          expected_date.strftime(
                                              DATE_FORMAT_REQUEST)
                                          ]),
        "Program",
    )

    self.assertEqual(programs["count"], 2)
    self.assertEqual(len(programs["values"]), programs["count"])
    self.assertTrue(
        all(datetime.strptime(program["start_date"],
                              DATE_FORMAT_RESPONSE) > expected_date
            for program in programs["values"]),
    )

  @unittest.skip("Not implemented.")
  def test_basic_query_missing_field(self):
    """Filter fails on non-existing field."""
    data = self._make_query_dict(
        "Program",
        expression=["This field definitely does not exist", "=", "test"],
    )
    response = self._post(data)
    self.assert400(response)

  # pylint: disable=invalid-name
  @ddt.data(
      ("effective date", ">", "05.18.2015"),
      ("start_date", "=", "2015-05.18"),
      ("start_date", "=", "2015-33.18"),
      ("start_date", "=", "2015.05-33"),
      ("start_date", "=", "2015/05.18"),
      ("start_date", "=", "2015.05/18"),
  )
  @ddt.unpack
  def test_basic_query_incorrect_date_format(self, field,
                                             operation, incorrect_date):
    """Filtering should fail because of incorrect date input."""
    dates = [datetime(2015, 5, 16),
             datetime(2015, 5, 17),
             datetime(2015, 5, 18),
             datetime(2015, 5, 19),
             datetime(2015, 5, 20),
             ]
    with factories.single_commit():
      for dt in dates:
        factories.ProgramFactory(start_date=dt)

    data = self._make_query_dict(
        "Program", expression=[field, operation, incorrect_date]
    )
    response = self._post(data)
    self.assert400(response)
    self.assertEqual(DateValue.VALUE_ERROR_MSG, response.json['message'])

  def test_filtering_objective_by_date(self):
    """Filtering by 'mm-dd-yyyy', 'mm-yyyy' date format"""
    with freezegun.freeze_time('08-23-2019'):
      objective = factories.ObjectiveFactory()
      objective_id = objective.id
    with freezegun.freeze_time('08-22-2019'):
      factories.ObjectiveFactory()

    query = ('LAST UPDATED DATE', '=', '08-23-2019')
    data = self._make_query_dict('Objective', expression=query)
    result = self._get_first_result_set(data, 'Objective')

    self.assertEqual(result['count'], 1)
    self.assertEqual(objective_id, result['values'][0]['id'])

  def test_basic_query_text_search(self):
    """Filter by fulltext search."""
    text_pattern = "ea"

    programs_data = [("Program_1_ea", "Notes", "Description"),
                     ("Program_2", "Notes_ea", "Description"),
                     ("Program_3", "Notes", "Description_ea"),
                     ("Program_4", "Notes_ea", "Description sweat"),
                     ("Program_5_ea", "Notes tea", "Description sweat"),
                     ("Program_6", "Noteas", "Description"),
                     ("Program_7", "Notes7", "Deascription7"),
                     ]
    with factories.single_commit():
      for program in programs_data:
        factories.ProgramFactory(title=program[0],
                                 notes=program[1],
                                 description=program[2])
    data = self._make_query_dict("Program")
    data["filters"]["expression"] = {
        "op": {"name": "text_search"},
        "text": text_pattern,
    }
    programs = self._get_first_result_set(data, "Program")

    self.assertEqual(programs["count"], 7)
    self.assertEqual(len(programs["values"]), programs["count"])

  def test_basic_query_pagination(self):
    """Test basic query with pagination info."""
    with factories.single_commit():
      for i in range(1, 6):
        factories.ProgramFactory(title="Cat ipsum {}".format(i))
    from_, to_ = 1, 5
    programs = self._get_first_result_set(
        self._make_query_dict("Program",
                              expression=["title", "~", "Cat ipsum"],
                              order_by=[{"name": "title"}],
                              limit=[from_, to_]),
        "Program",
    )
    self.assertEqual(programs["count"], to_ - from_)
    self.assertEqual(len(programs["values"]), programs["count"])
    self.assertEqual(programs["total"], 5)

  def test_basic_query_total(self):
    """The value of "total" doesn't depend on "limit" parameter."""
    with factories.single_commit():
      for i in range(1, 6):
        factories.ProgramFactory(title="Cat ipsum {}".format(i))
    programs_no_limit = self._get_first_result_set(
        self._make_query_dict("Program"),
        "Program",
    )
    self.assertEqual(programs_no_limit["count"], programs_no_limit["total"])

    from_, to_ = 3, 5
    programs_limit = self._get_first_result_set(
        self._make_query_dict("Program", limit=[from_, to_]),
        "Program",
    )
    self.assertEqual(programs_limit["count"], to_ - from_)

    self.assertEqual(programs_limit["total"], programs_no_limit["total"])

  def test_query_limit(self):
    """The limit parameter trims the result set."""
    def make_query_dict(limit=None):
      """A shortcut for making queries with different limits."""
      return self._make_query_dict("Program", order_by=[{"name": "title"}],
                                   limit=limit)

    def check_counts_and_values(programs, from_, to_, count=None):
      """Make a typical assertion set for count, total and values."""
      if count is None:
        count = to_ - from_
      self.assertEqual(programs["count"], count)
      self.assertEqual(programs["total"], programs_no_limit["total"])
      self.assertEqual(programs["values"],
                       programs_no_limit["values"][from_:to_],
                       sort_sublists=True)

    with factories.single_commit():
      for i in range(1, 11):
        factories.ProgramFactory(title="Cat ipsum {}".format(i))

    programs_no_limit = self._get_first_result_set(
        make_query_dict(),
        "Program",
    )

    self.assertEqual(programs_no_limit["count"], programs_no_limit["total"])

    programs_0_4 = self._get_first_result_set(
        make_query_dict(limit=[0, 4]),
        "Program",
    )

    check_counts_and_values(programs_0_4, from_=0, to_=4)

    programs_4_8 = self._get_first_result_set(
        make_query_dict(limit=[4, 8]),
        "Program",
    )

    check_counts_and_values(programs_4_8, from_=4, to_=8)

    programs_4_top = self._get_first_result_set(
        make_query_dict(limit=[4, programs_no_limit["total"] + 10]),
        "Program",
    )

    check_counts_and_values(programs_4_top, from_=4, to_=None,
                            count=programs_no_limit["total"] - 4)

    # check if a valid integer string representation gets casted
    programs_4_8_str = self._get_first_result_set(
        make_query_dict(limit=[4, "8"]),
        "Program",
    )
    programs_4_str_8 = self._get_first_result_set(
        make_query_dict(limit=["4", 8]),
        "Program",
    )
    self._sort_sublists(programs_4_8_str["values"])
    self._sort_sublists(programs_4_str_8["values"])
    self._sort_sublists(programs_4_8["values"])

    self.assertDictEqual(programs_4_8_str, programs_4_8)
    self.assertDictEqual(programs_4_str_8, programs_4_8)

  def test_query_invalid_limit(self):
    """Invalid limit parameters are handled properly."""
    with factories.single_commit():
      for i in range(1, 6):
        factories.ProgramFactory(title="Cat ipsum {}".format(i))

    # invalid "from"
    response = self._post(
        self._make_query_dict("Program", limit=["invalid", 3]),
    )
    self.assert400(response)
    self.assertEqual(response.json['message'],
                     "Invalid limit operator. Integers expected.")

    # invalid "to"
    response = self._post(
        self._make_query_dict("Program", limit=[0, "invalid"]),
    )
    self.assert400(response)
    self.assertEqual(response.json['message'],
                     "Invalid limit operator. Integers expected.")

    # "from" >= "to"
    response = self._post(
        self._make_query_dict("Program", limit=[4, 0]),
    )
    self.assert400(response)
    self.assertEqual(response.json['message'],
                     "Limit start should be smaller than end.")

    # negative "from"
    response = self._post(
        self._make_query_dict("Program", limit=[-2, 2]),
    )
    self.assert400(response)
    self.assertEqual(response.json['message'],
                     "Limit cannot contain negative numbers.")

    # negative "to"
    response = self._post(
        self._make_query_dict("Program", limit=[2, -1]),
    )
    self.assert400(response)
    self.assertEqual(response.json['message'],
                     "Limit cannot contain negative numbers.")

  def test_query_order_by(self):
    """Results get sorted by own field."""
    # assumes unique title

    def get_titles(programs):
      return [program["title"] for program in programs]

    with factories.single_commit():
      for i in (1, 12, 23, 9, 52, 28):
        factories.ProgramFactory(title="Cat ipsum {}".format(i))

    programs_default = self._get_first_result_set(
        self._make_query_dict("Program",
                              order_by=[{"name": "title"}]),
        "Program", "values",
    )
    titles_default = get_titles(programs_default)

    programs_asc = self._get_first_result_set(
        self._make_query_dict("Program",
                              order_by=[{"name": "title", "desc": False}]),
        "Program", "values",
    )
    titles_asc = get_titles(programs_asc)

    programs_desc = self._get_first_result_set(
        self._make_query_dict("Program",
                              order_by=[{"name": "title", "desc": True}]),
        "Program", "values",
    )
    titles_desc = get_titles(programs_desc)

    # the titles are sorted ascending with desc=False
    self.assertListEqual(titles_asc, sorted(titles_asc))
    # desc=False by default
    self.assertListEqual(titles_default, titles_asc)
    # the titles are sorted descending with desc=True
    self.assertListEqual(titles_desc, list(reversed(titles_asc)))

  def test_order_by_several_fields(self):
    """Results get sorted by two fields at once."""
    regulations_data = [("reg-1", "notes1"),
                        ("reg-2", "notes2"),
                        ("reg-3", "notes3"),
                        ("reg-4", "notes"),
                        ("reg-5", "notes"),
                        ("reg-6", "notes"),
                        ]
    with factories.single_commit():
      for reg in regulations_data:
        factories.RegulationFactory(title=reg[0],
                                    notes=reg[1])

    regulations = self._get_first_result_set(
        self._make_query_dict("Regulation",
                              order_by=[{"name": "notes", "desc": True},
                                        {"name": "title"}]),
        "Regulation", "values",
    )

    regulations_unsorted = self._get_first_result_set(
        self._make_query_dict("Regulation"),
        "Regulation", "values",
    )
    expected = sorted(sorted(regulations_unsorted,
                             key=itemgetter("title")),
                      key=itemgetter("notes"),
                      reverse=True)

    self.assertListEqual(
        self._sort_sublists(regulations),
        self._sort_sublists(expected),
    )

  def test_order_by_related_titled(self):
    """Results get sorted by title of related Titled object."""
    with factories.single_commit():
      for i in ("b", "a", "f", "c", "d"):
        program = factories.ProgramFactory(title="{}-program".format(i))
        factories.AuditFactory(title="{}-audit".format(i),
                               program=program)

    audits_title = self._get_first_result_set(
        self._make_query_dict("Audit",
                              order_by=[{"name": "program"}, {"name": "id"}]),
        "Audit", "values",
    )

    audits_unsorted = self._get_first_result_set(
        self._make_query_dict("Audit"),
        "Audit", "values",
    )

    # get titles from programs to check ordering
    programs = self._get_first_result_set(
        self._make_query_dict("Program"),
        "Program", "values",
    )
    program_id_title = {program["id"]: program["title"]
                        for program in programs}
    expected = sorted(sorted(audits_unsorted, key=itemgetter("id")),
                      key=lambda a: program_id_title[a["program"]["id"]])

    self.assertListEqual(
        self._sort_sublists(audits_title),
        self._sort_sublists(expected)
    )

  def test_query_order_by_owners(self):
    """Results get sorted by name or email of the (first) owner."""
    # TODO: the test data set lacks objects with several owners
    with factories.single_commit():
      for i in ("b", "a", "f", "c", "d"):
        user = factories.PersonFactory(name="{}-admin".format(i),
                                       email="{}-admin@example.com".format(i))
        policy = factories.PolicyFactory(title="Policy {}".format(i))
        policy.add_person_with_role_name(user, "Admin")

    policies_owner = self._get_first_result_set(
        self._make_query_dict("Policy",
                              order_by=[{"name": "Admin"}, {"name": "id"}]),
        "Policy", "values",
    )
    policies_unsorted = self._get_first_result_set(
        self._make_query_dict("Policy"),
        "Policy", "values",
    )
    people = self._get_first_result_set(
        self._make_query_dict("Person"),
        "Person", "values",
    )
    person_id_name = {person["id"]: (person["name"], person["email"])
                      for person in people}
    owner_role = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.name == "Admin",
        all_models.AccessControlRole.object_type == "Policy"
    ).one()
    policy_id_owner = {
        policy["id"]: person_id_name[
            [acl for acl in policy["access_control_list"]
             if acl["ac_role_id"] == owner_role.id][0]["person_id"]
        ]
        for policy in policies_unsorted
    }

    expected = sorted(sorted(policies_unsorted, key=itemgetter("id")),
                      key=lambda p: policy_id_owner[p["id"]])

    self.assertListEqual(
        self._sort_sublists(policies_owner),
        self._sort_sublists(expected),
    )

  def test_order_control_by_option(self):
    """Test correct ordering and by option."""
    options = all_models.Option.query.filter_by(role="network_zone").all()
    self.assertEqual(len(options), 5)
    random.shuffle(options)
    with factories.single_commit():
      for option in options:
        factories.SystemFactory(network_zone=option)

    systems_unordered = self._get_first_result_set(
        self._make_query_dict("System",),
        "System", "values"
    )
    systems_ordered_1 = self._get_first_result_set(
        self._make_query_dict("System",
                              order_by=[{"name": "Network Zone"},
                                        {"name": "id"}]),
        "System", "values"
    )
    options_map = {o.id: o.title for o in models.Option.query}

    def sort_key(val):
      """sorting key getter function"""
      option = val["network_zone"]
      if not option:
        return None
      return options_map[option["id"]]

    systems_ordered_2 = sorted(systems_unordered, key=sort_key)
    self.assertListEqual(
        self._sort_sublists(systems_ordered_1),
        self._sort_sublists(systems_ordered_2),
    )

  def test_filter_system_by_zone(self):
    """Test correct filtering by Network Zone"""
    options = all_models.Option.query.filter_by(role="network_zone")
    with factories.single_commit():
      for option in options:
        factories.SystemFactory(network_zone=option)

    systems = self._get_first_result_set(
        self._make_query_dict(
            "System",
            expression=["Network Zone", "=", "Corp"]
        ),
        "System",
    )
    self.assertEqual(systems["count"], 1)

  def test_query_related_people_for_program(self):
    """Test correct querying of the related people to Program"""

    with factories.single_commit():
      test_pm = factories.PersonFactory(email="smotko@example.com")
      test_pc = factories.PersonFactory(email="sec.con@example.com")
      program = factories.ProgramFactory(title="Cat ipsum 1")
      program.add_person_with_role_name(test_pm, "Program Managers")
      program.add_person_with_role_name(test_pc, "Primary Contacts")
      program_id = program.id

    query_filter = {
        "object_name": "Person",
        "filters": {
            "expression": {
                "object_name": "Program",
                "op": {
                    "name": "related_people",
                },
                "ids": [program_id],
            },
        },
    }
    people = self._get_first_result_set(
        query_filter,
        "Person",
    )
    user_list = [p['email'] for p in people["values"]]
    ref_list = [u'smotko@example.com', u'sec.con@example.com']
    self.assertItemsEqual(user_list, ref_list)

  def test_filter_risk_by_vulnerability(self):
    """Test correct filtering by vulnerability field"""
    with factories.single_commit():
      for _ in range(2):
        factories.RiskFactory(vulnerability="non-key")
      for _ in range(2):
        factories.RiskFactory(vulnerability="another-key")

    risks = self._get_first_result_set(
        self._make_query_dict("Risk",
                              expression=["vulnerability", "=", "non-key"]),
        "Risk",
    )
    self.assertEqual(risks["count"], 2)

  def test_order_control_by_key_control(self):
    """Test correct ordering and by SIGNIFICANCE field"""
    controls_unordered = self._get_first_result_set(
        self._make_query_dict("Control",),
        "Control", "values"
    )
    controls_ordered_1 = self._get_first_result_set(
        self._make_query_dict("Control",
                              order_by=[{"name": "significance"},
                                        {"name": "id"}]),
        "Control", "values"
    )
    controls_ordered_2 = sorted(controls_unordered,
                                key=lambda ctrl: (ctrl["key_control"] is None,
                                                  ctrl["key_control"]),
                                reverse=True)
    self.assertListEqual(
        self._sort_sublists(controls_ordered_1),
        self._sort_sublists(controls_ordered_2),
    )

  def test_filter_risk_by_threat_event(self):
    """Test correct filtering by threat_event field"""
    with factories.single_commit():
      for _ in range(2):
        factories.RiskFactory(threat_event="yes")
      for _ in range(2):
        factories.RiskFactory(threat_event="no")

    risks = self._get_first_result_set(
        self._make_query_dict("Risk",
                              expression=["threat_event", "=", "yes"]),
        "Risk",
    )
    self.assertEqual(risks["count"], 2)

  def test_order_control_by_fraud_related(self):
    """Test correct ordering and by fraud_related field"""
    controls_unordered = self._get_first_result_set(
        self._make_query_dict("Control",),
        "Control", "values"
    )

    controls_ordered_1 = self._get_first_result_set(
        self._make_query_dict("Control",
                              order_by=[{"name": "fraud related"},
                                        {"name": "id"}]),
        "Control", "values"
    )
    controls_ordered_2 = sorted(controls_unordered,
                                key=lambda ctrl: ctrl["fraud_related"])
    self.assertListEqual(
        self._sort_sublists(controls_ordered_1),
        self._sort_sublists(controls_ordered_2),
    )

  def test_filter_risk_by_risk_type(self):
    """Test correct filtering by risk_type field"""
    with factories.single_commit():
      for _ in range(3):
        factories.RiskFactory(risk_type="privacy")
      for _ in range(2):
        factories.RiskFactory(risk_type="security")

    risks = self._get_first_result_set(
        self._make_query_dict("Risk",
                              expression=["risk_type", "=", "privacy"]),
        "Risk",
    )
    self.assertEqual(risks["count"], 3)

  @ddt.data("assertions", "categories")
  def test_order_control_by_category(self, key):
    """Test correct ordering by {}."""
    with factories.single_commit():
      for val in ("a", "b", "c"):
        factories.ControlFactory(**{key: '["{}"]'.format(val)})

    controls_unordered = self._get_first_result_set(
        self._make_query_dict("Control",),
        "Control",
        "values"
    )
    controls_ordered_1 = self._get_first_result_set(
        self._make_query_dict("Control", order_by=[{"name": key}]),
        "Control",
        "values"
    )
    controls_ordered_2 = sorted(controls_unordered, key=lambda c: c.get(key))
    self.assertListEqual(
        self._sort_sublists(controls_ordered_1),
        self._sort_sublists(controls_ordered_2),
    )

  def test_filter_risk_by_threat_source(self):
    """Test correct filtering by threat_source field"""
    with factories.single_commit():
      for _ in range(3):
        factories.RiskFactory(threat_source="Corrective")
      for _ in range(2):
        factories.RiskFactory(threat_source="Another")

    risks = self._get_first_result_set(
        self._make_query_dict(
            "Risk",
            expression=["threat_source", "=", "Corrective"]),
        "Risk",
    )
    self.assertEqual(risks["count"], 3)

  def test_query_count(self):
    """The value of "count" is same for "values" and "count" queries."""
    with factories.single_commit():
      for i in range(1, 6):
        factories.ProgramFactory(title="Cat ipsum {}".format(i))

    programs_values = self._get_first_result_set(
        self._make_query_dict("Program", type_="values"),
        "Program",
    )
    programs_count = self._get_first_result_set(
        self._make_query_dict("Program", type_="count"),
        "Program",
    )

    self.assertEqual(programs_values["count"], programs_count["count"])

  @ddt.data("Regulation",
            "System",
            "Process",
            "Contract",
            "Policy",
            "Standard")
  def test_query_total(self, model_name):
    """Test corresponding value of 'total' field."""
    number_of_objects = 2
    object_factory = factories.get_model_factory(model_name)
    object_class = models.get_model(model_name)
    total_before_creation = object_class.query.count()

    with factories.single_commit():
      object_ids = [object_factory().id for _ in range(number_of_objects)]

    # Check that objects has been created correctly.
    created_objects_count = object_class.query.filter(
        object_class.id.in_(object_ids)
    ).count()
    self.assertEqual(created_objects_count, number_of_objects)

    data = [{
        "object_name": model_name,
        "filters": {"expression": {}},
        "limit": [0, 10],
        "order_by": [{"name": "updated_at", "desc": True}]
    }]

    # Check corresponding value of 'total' field.
    result = self._get_first_result_set(data, model_name, "total")
    self.assertEqual(number_of_objects, result - total_before_creation)

  def test_query_ids(self):
    """The ids are the same for "values" and "ids" queries."""
    with factories.single_commit():
      for i in range(1, 6):
        factories.ProgramFactory(title="Cat ipsum {}".format(i))

    programs_values = self._get_first_result_set(
        self._make_query_dict("Program", type_="values"),
        "Program",
    )
    programs_ids = self._get_first_result_set(
        self._make_query_dict("Program", type_="ids"),
        "Program",
    )

    self.assertEqual(
        set(obj.get("id") for obj in programs_values["values"]),
        set(programs_ids["ids"]),
    )

  @unittest.skip("Skip until fix resp order problem to mysql 5.6")
  def test_multiple_queries(self):
    """Multiple queries POST is identical to multiple single-query POSTs."""
    data_list = [
        self._make_query_dict("Program",
                              order_by=[{"name": "title"}],
                              limit=[1, 12],
                              expression=["title", "~", "Cat ipsum"]),
        self._make_query_dict("Program",
                              type_="values"),
        self._make_query_dict("Program",
                              type_="count"),
        self._make_query_dict("Program",
                              type_="ids"),
        self._make_query_dict("Program",
                              type_="ids",
                              expression=["title", "=", "Cat ipsum 1"]),
        self._make_query_dict("Program",
                              expression=["title", "~", "1"]),
        self._make_query_dict("Program",
                              expression=["title", "!=", "Cat ipsum 1"]),
        self._make_query_dict("Program",
                              expression=["title", "!~", "1"]),
        self._make_query_dict("Program",
                              expression=["effective date", "<",
                                          "05/18/2015"]),
        self._make_query_dict("Program",
                              expression=["effective date", ">",
                                          "05/18/2015"]),
        {
            "object_name": "Regulation",
            "fields": ["description", "notes"],
            "filters": {
                "expression": {
                    "op": {"name": "text_search"},
                    "text": "ea",
                },
            },
        },
    ]

    response_multiple_posts = [
        json.loads(self._post(data).data)[0] for data in data_list
    ]
    response_single_post = json.loads(self._post(data_list).data)

    self.assertEqual(response_multiple_posts,
                     response_single_post,
                     sort_sublists=True)

  def test_is_empty_query_by_native_attrs(self):
    """Filter by native object attrs with 'is empty' operator."""
    with factories.single_commit():
      factories.ProgramFactory(title="Cat ipsum 1")
      factories.ProgramFactory(title="Cat ipsum 2",
                               notes="sample notes1")
      factories.ProgramFactory(title="Cat ipsum 3",
                               notes="sample notes2")
    programs = self._get_first_result_set(
        self._make_query_dict("Program",
                              expression=["notes", "is", "empty"]),
        "Program",
    )
    self.assertEqual(programs["count"], 1)
    self.assertEqual(set([u'Cat ipsum 1']),
                     set([program["title"] for program
                          in programs["values"]]))

  @ddt.data(
      (all_models.Control, [all_models.Objective, all_models.Control,
                            all_models.Market, all_models.Objective]),
      (all_models.Comment, [all_models.Control, all_models.Control,
                            all_models.Market, all_models.Objective]),
  )
  @ddt.unpack
  def test_search_relevant_to_type(self, base_type, relevant_types):
    """Test filter with 'relevant to' conditions."""
    if issubclass(base_type, Synchronizable):
      with self.generator.api.as_external():
        _, base_obj = self.generator.generate_object(base_type)
    else:
      _, base_obj = self.generator.generate_object(base_type)

    relevant_objects = []
    for type_ in relevant_types:
      if issubclass(type_, Synchronizable):
        with self.generator.api.as_external():
          obj = self.generator.generate_object(type_)[1]
      else:
        obj = self.generator.generate_object(type_)[1]

      relevant_objects.append(obj)

    with factories.single_commit():
      query_data = []
      for relevant_obj in relevant_objects:
        if base_type is all_models.Control and \
           isinstance(relevant_obj, (all_models.Market, all_models.Objective)):
          with mock.patch('ggrc.models.relationship.is_external_app_user',
                          return_value=True):
            factories.RelationshipFactory(source=base_obj,
                                          destination=relevant_obj,
                                          is_external=True)
        else:
          factories.RelationshipFactory(source=base_obj,
                                        destination=relevant_obj)

        query_data.append(self._make_query_dict(
            relevant_obj.type,
            expression=["id", "=", relevant_obj.id],
            type_="ids",
        ))

    filter_relevant = {
        "filters": {
            "expression": {
                "left": {
                    "left": {
                        "ids": "0",
                        "object_name": "__previous__",
                        "op": {"name": "relevant"}
                    },
                    "op": {"name": "AND"},
                    "right": {
                        "ids": "1",
                        "object_name": "__previous__",
                        "op": {"name": "relevant"}
                    }
                },
                "op": {"name": "AND"},
                "right": {
                    "left": {
                        "ids": "2",
                        "object_name": "__previous__",
                        "op": {"name": "relevant"}
                    },
                    "op": {"name": "AND"},
                    "right": {
                        "ids": "3",
                        "object_name": "__previous__",
                        "op": {"name": "relevant"}
                    }
                }
            }
        },
        "object_name": base_type.__name__
    }
    query_data.append(filter_relevant)
    response = json.loads(self._post(query_data).data)
    # Last batch contain result for query with "related" condition
    result_count = response[-1][base_type.__name__]["count"]
    self.assertEqual(result_count, 1)

  @ddt.data(
      (all_models.Assessment, [all_models.Control, all_models.Control,
                               all_models.Market, all_models.Objective]),
      (all_models.Assessment, [all_models.Issue, all_models.Issue,
                               all_models.Issue, all_models.Issue]),
      (all_models.Issue, [all_models.Assessment, all_models.Assessment,
                          all_models.Assessment, all_models.Assessment]),
  )
  @ddt.unpack
  def test_search_relevant_to_type_audit(self, base_type, relevant_types):
    """Test filter with 'relevant to' conditions (Audit scope)."""
    audit = factories.AuditFactory()
    audit_data = {"audit": {"id": audit.id}}

    if base_type == all_models.Issue or all_models.Issue in relevant_types:
      audit_data["due_date"] = "10/10/2019"

    _, base_obj = self.generator.generate_object(base_type, audit_data)
    relevant_objects = []
    for type_ in relevant_types:
      if issubclass(type_, Synchronizable):
        with self.generator.api.as_external():
          obj = self.generator.generate_object(type_, audit_data)[1]
      else:
        obj = self.generator.generate_object(type_, audit_data)[1]

      relevant_objects.append(obj)

    with factories.single_commit():
      query_data = []
      for relevant_obj in relevant_objects:
        related_obj = relevant_obj

        # Snapshotable objects are related through the Snapshot
        if relevant_obj.type in Types.all:
          related_obj = factories.SnapshotFactory(
              parent=audit,
              child_id=relevant_obj.id,
              child_type=relevant_obj.type,
              revision_id=models.Revision.query.filter_by(
                  resource_type=relevant_obj.type
              ).first().id,
          )
        factories.RelationshipFactory(source=base_obj, destination=related_obj)

        query_data.append(self._make_query_dict(
            relevant_obj.type,
            expression=["id", "=", relevant_obj.id],
            type_="ids",
        ))

    filter_relevant = {
        "filters": {
            "expression": {
                "left": {
                    "left": {
                        "ids": "0",
                        "object_name": "__previous__",
                        "op": {"name": "relevant"}
                    },
                    "op": {"name": "AND"},
                    "right": {
                        "ids": "1",
                        "object_name": "__previous__",
                        "op": {"name": "relevant"}
                    }
                },
                "op": {"name": "AND"},
                "right": {
                    "left": {
                        "ids": "2",
                        "object_name": "__previous__",
                        "op": {"name": "relevant"}
                    },
                    "op": {"name": "AND"},
                    "right": {
                        "ids": "3",
                        "object_name": "__previous__",
                        "op": {"name": "relevant"}
                    }
                }
            }
        },
        "object_name": base_type.__name__
    }
    query_data.append(filter_relevant)
    response = json.loads(self._post(query_data).data)
    # Last batch contain result for query with "related" condition
    result_count = response[-1][base_type.__name__]["count"]
    self.assertEqual(result_count, 1)


class TestQueryAssessmentCA(TestCase, WithQueryApi):
  """Test filtering assessments by CAs"""

  def setUp(self):
    """Set up for query assessment CA."""
    super(TestQueryAssessmentCA, self).setUp()
    self._generate_special_assessments()
    self.client.get("/login")

  @staticmethod
  def _generate_special_assessments():
    """Generate two Assessments for two local CADs with same name."""
    audit = factories.AuditFactory(
        slug="audit"
    )
    assessment_with_date = factories.AssessmentFactory(
        title="Assessment with date",
        slug="ASMT-SPECIAL-DATE",
        audit=audit,
    )
    assessment_with_text = factories.AssessmentFactory(
        title="Assessment with text",
        slug="ASMT-SPECIAL-TEXT",
        audit=audit,
    )
    cad_with_date_1 = factories.CustomAttributeDefinitionFactory(
        title="Date or arbitrary text",
        definition_type="assessment",
        definition_id=assessment_with_date.id,
        attribute_type="Date",
    )
    cad_with_text_1 = factories.CustomAttributeDefinitionFactory(
        title="Date or arbitrary text",
        definition_type="assessment",
        definition_id=assessment_with_text.id,
        attribute_type="Text",
    )
    cad_with_date_2 = factories.CustomAttributeDefinitionFactory(
        title="Date or text styled as date",
        definition_type="assessment",
        definition_id=assessment_with_date.id,
        attribute_type="Date",
    )
    cad_with_text_2 = factories.CustomAttributeDefinitionFactory(
        title="Date or text styled as date",
        definition_type="assessment",
        definition_id=assessment_with_text.id,
        attribute_type="Text",
    )
    factories.CustomAttributeValueFactory(custom_attribute=cad_with_date_1,
                                          attributable=assessment_with_date,
                                          attribute_value="10/31/2016")
    factories.CustomAttributeValueFactory(custom_attribute=cad_with_text_1,
                                          attributable=assessment_with_text,
                                          attribute_value="Some text 2016")
    factories.CustomAttributeValueFactory(custom_attribute=cad_with_date_2,
                                          attributable=assessment_with_date,
                                          attribute_value="11/09/2016")
    factories.CustomAttributeValueFactory(custom_attribute=cad_with_text_2,
                                          attributable=assessment_with_text,
                                          attribute_value="11/09/2016")

  # pylint: disable=invalid-name
  def test_ca_query_different_types_local_ca(self):
    """Filter by local CAs with same title and different types."""
    expected_date = datetime(2016, 10, 31)
    assessments_date = self._get_first_result_set(
        self._make_query_dict(
            "Assessment",
            expression=["Date or arbitrary text", "=",
                        expected_date.strftime(DATE_FORMAT_REQUEST)],
        ),
        "Assessment", "values",
    )

    self.assertItemsEqual([asmt["title"] for asmt in assessments_date],
                          ["Assessment with date"])

    assessments_text = self._get_first_result_set(
        self._make_query_dict(
            "Assessment",
            expression=["Date or arbitrary text", "=", "Some text 2016"],
        ),
        "Assessment", "values",
    )

    self.assertItemsEqual([asmt["title"] for asmt in assessments_text],
                          ["Assessment with text"])

    assessments_mixed = self._get_first_result_set(
        self._make_query_dict(
            "Assessment",
            expression=["Date or arbitrary text", "~", "2016"],
        ),
        "Assessment", "values",
    )

    self.assertItemsEqual([asmt["title"] for asmt in assessments_mixed],
                          ["Assessment with text", "Assessment with date"])

    expected_date = datetime(2016, 11, 9)
    assessments_mixed = self._get_first_result_set(
        self._make_query_dict(
            "Assessment",
            expression=["Date or text styled as date", "=",
                        expected_date.strftime(DATE_FORMAT_REQUEST)],
        ),
        "Assessment", "values",
    )

    self.assertItemsEqual([asmt["title"] for asmt in assessments_mixed],
                          ["Assessment with text", "Assessment with date"])


class TestSortingQuery(TestCase, WithQueryApi):
  """Test sorting is correct requested with query API"""
  def setUp(self):
    """Set up sorting query."""
    super(TestSortingQuery, self).setUp()
    self.client.get("/login")

  def create_assessment(self, title=None, people=None):
    """Create default assessment with some default assignees in all roles.
    Args:
      people: List of tuples with email address and their assignee roles for
              Assessments.
    Returns:
      Assessment object.
    """
    assessment = factories.AssessmentFactory(title=title)
    context = factories.ContextFactory(related_object=assessment)
    assessment.context = context

    if not people:
      people = [
          ("creator@example.com", "Creators"),
          ("assessor_1@example.com", "Assignees"),
          ("assessor_2@example.com", "Assignees"),
          ("verifier_1@example.com", "Verifiers"),
          ("verifier_2@example.com", "Verifiers"),
      ]

    defined_assessors = len([1 for _, role in people
                             if "Assignees" in role])
    defined_creators = len([1 for _, role in people
                            if "Creators" in role])
    defined_verifiers = len([1 for _, role in people
                             if "Verifiers" in role])

    assignee_roles = self.create_assignees(assessment, people)

    creators = [assignee for assignee, role in assignee_roles
                if role == "Creators"]
    assignees = [assignee for assignee, role in assignee_roles
                 if role == "Assignees"]
    verifiers = [assignee for assignee, role in assignee_roles
                 if role == "Verifiers"]

    self.assertEqual(len(creators), defined_creators)
    self.assertEqual(len(assignees), defined_assessors)
    self.assertEqual(len(verifiers), defined_verifiers)
    return assessment

  # pylint: disable=invalid-name
  def test_sorting_assessments_by_assignees(self):
    """Test assessments are sorted by multiple assignees correctly"""
    people_set_1 = [
        ("2creator@example.com", "Creators"),
        ("assessor_2@example.com", "Assignees"),
        ("assessor_1@example.com", "Assignees"),
        ("1verifier_1@example.com", "Verifiers"),
        ("2verifier_2@example.com", "Verifiers"),
    ]
    self.create_assessment("Assessment_1", people_set_1)
    people_set_2 = [
        ("1creator@example.com", "Creators"),
        ("1assessor@example.com", "Assignees"),
        ("2assessor@example.com", "Assignees"),
        ("verifier_1@example.com", "Verifiers"),
        ("verifier_2@example.com", "Verifiers"),
    ]
    self.create_assessment("Assessment_2", people_set_2)

    assessments_by_creators = self._get_first_result_set(
        self._make_query_dict("Assessment",
                              order_by=[{"name": "creators",
                                         "desc": False}]),
        "Assessment", "values",
    )
    self.assertListEqual([ass["title"] for ass in assessments_by_creators],
                         ["Assessment_2", "Assessment_1"])

    assessments_by_verifiers = self._get_first_result_set(
        self._make_query_dict("Assessment",
                              order_by=[{"name": "verifiers",
                                         "desc": False}]),
        "Assessment", "values",
    )
    self.assertListEqual([ass["title"] for ass in assessments_by_verifiers],
                         ["Assessment_1", "Assessment_2"])

    assessments_by_assessors = self._get_first_result_set(
        self._make_query_dict("Assessment",
                              order_by=[{"name": "assignees",
                                         "desc": False}]),
        "Assessment", "values",
    )
    self.assertListEqual([ass["title"] for ass in assessments_by_assessors],
                         ["Assessment_2", "Assessment_1"])


class TestQueryAssessmentByEvidenceURL(TestCase, WithQueryApi):
  """Test assessments filtering by Evidence and/or URL"""
  def setUp(self):
    super(TestQueryAssessmentByEvidenceURL, self).setUp()
    self.client.get("/login")

  def test_query_evidence_url(self):
    """Test assessments query filtered by Evidence"""
    evidence_url1 = "http://i.imgur.com/Lppr347.jpg"
    evidence_url2 = "http://i.imgur.com/Lppr447.jpg"

    with factories.single_commit():
      for i in range(1, 3):
        assmt = factories.AssessmentFactory(
            title="Assessment title {}".format(i))
        evidence = factories.EvidenceUrlFactory(link=evidence_url1)
        factories.RelationshipFactory(source=assmt, destination=evidence)
      for i in range(3, 5):
        assmt = factories.AssessmentFactory(
            title="Assessment title {}".format(i))
        evidence = factories.EvidenceUrlFactory(link=evidence_url2)
        factories.RelationshipFactory(source=assmt, destination=evidence)

    assessments_by_evidence = self._get_first_result_set(
        self._make_query_dict(
            "Assessment",
            expression=["Evidence Url", "~", "Lppr347.jpg"],
        ),
        "Assessment", "values",
    )
    self.assertEqual(len(assessments_by_evidence), 2)
    self.assertItemsEqual([asmt["title"] for asmt in assessments_by_evidence],
                          ["Assessment title 1", "Assessment title 2"])

    assessments_by_url = self._get_first_result_set(
        self._make_query_dict(
            "Assessment",
            expression=["Evidence URL", "~", "i.imgur.com"],
        ),
        "Assessment", "values",
    )

    self.assertEqual(len(assessments_by_url), 4)
    self.assertItemsEqual([asmt["title"] for asmt in assessments_by_url],
                          ["Assessment title 1",
                           "Assessment title 2",
                           "Assessment title 3",
                           "Assessment title 4",
                           ])


class TestQueryWithCA(TestCase, WithQueryApi):
  """Test query API with custom attributes."""

  def setUp(self):
    super(TestQueryWithCA, self).setUp()
    self._generate_cad()
    self.client.get("/login")

  @staticmethod
  def _generate_cad():
    """Generate custom attribute definitions."""
    factories.CustomAttributeDefinitionFactory(
        title="CA dropdown",
        definition_type="program",
        multi_choice_options="one,two,three,four,five",
    )
    factories.CustomAttributeDefinitionFactory(
        title="CA text",
        definition_type="program",
    )
    factories.CustomAttributeDefinitionFactory(
        title="CA date",
        definition_type="program",
        attribute_type="Date",
    )

  @staticmethod
  def _flatten_cav(data):
    """Unpack CAVs and put them in data as object attributes."""
    cad_names = dict(db.session.query(CAD.id, CAD.title))
    for entry in data:
      for cav in entry.get("custom_attribute_values", []):
        entry[cad_names[cav["custom_attribute_id"]]] = cav["attribute_value"]
    return data

  # pylint: disable=arguments-differ
  def _get_first_result_set(self, *args, **kwargs):
    """Call this method from super and flatten CAVs additionally."""
    return self._flatten_cav(
        super(TestQueryWithCA, self)._get_first_result_set(*args, **kwargs),
    )

  def test_single_ca_sorting(self):
    """Results get sorted by single custom attribute field."""

    ca_values = ("B", "A", "F", "A", "B")
    ca_text = db.session.query(CAD).filter_by(title="CA text").one()
    with factories.single_commit():
      for i, ca_value in enumerate(ca_values):
        pgm = factories.ProgramFactory(title="program {}".format(i))
        factories.CustomAttributeValueFactory(
            custom_attribute=ca_text,
            attributable=pgm,
            attribute_value=ca_value,
        )

    programs = self._get_first_result_set(
        self._make_query_dict("Program",
                              order_by=[{"name": "title"}]),
        "Program", "values",
    )

    keys = [program["title"] for program in programs]
    self.assertEqual(keys, sorted(keys))

    programs = self._get_first_result_set(
        self._make_query_dict("Program",
                              order_by=[{"name": "CA text"}]),
        "Program", "values",
    )

    keys = [program["CA text"] for program in programs]
    self.assertEqual(keys, sorted(keys))

  def test_mixed_ca_sorting(self):
    """Test sorting by multiple fields with CAs."""

    ca_values = ("B", "A", "F", "A", "B")
    ca_text = db.session.query(CAD).filter_by(title="CA text").one()
    with factories.single_commit():
      for i, ca_value in enumerate(ca_values):
        pgm = factories.ProgramFactory(title="program {}".format(i))
        factories.CustomAttributeValueFactory(
            custom_attribute=ca_text,
            attributable=pgm,
            attribute_value=ca_value,
        )

    programs = self._get_first_result_set(
        self._make_query_dict("Program",
                              order_by=[{"name": "CA text"},
                                        {"name": "title"}]),
        "Program", "values",
    )

    keys = [(program["CA text"], program["title"]) for program in programs]
    self.assertEqual(keys, sorted(keys))

    programs = self._get_first_result_set(
        self._make_query_dict("Program",
                              order_by=[{"name": "title"},
                                        {"name": "CA text"}]),
        "Program", "values",
    )

    keys = [(program["title"], program["CA text"]) for program in programs]
    self.assertEqual(keys, sorted(keys))

  def test_multiple_ca_sorting(self):
    """Test sorting by multiple CA fields"""
    ca_text_values = ("B", "A", "F", "A", "B")
    ca_dp_values = ("one", "two", "four", "three", "five")
    ca_text = db.session.query(CAD).filter_by(title="CA text").one()
    ca_dropdown = db.session.query(CAD).filter_by(title="CA dropdown").one()
    with factories.single_commit():
      for i, (text_val, dp_val) in enumerate(zip(ca_text_values,
                                                 ca_dp_values)):
        program = factories.ProgramFactory(title="program {}".format(i))
        factories.CustomAttributeValueFactory(
            custom_attribute=ca_text,
            attributable=program,
            attribute_value=text_val,
        )
        factories.CustomAttributeValueFactory(
            custom_attribute=ca_dropdown,
            attributable=program,
            attribute_value=dp_val,
        )

    programs = self._get_first_result_set(
        self._make_query_dict("Program",
                              order_by=[{"name": "CA text"},
                                        {"name": "CA dropdown"}]),
        "Program", "values",
    )

    keys = [(prog["CA text"], prog["CA dropdown"]) for prog in programs]
    self.assertEqual(keys, sorted(keys))

  def test_ca_query_eq(self):
    """Test CA date fields filtering by = operator."""
    ca_values = [date(2015, 5, 16),
                 date(2015, 5, 17),
                 date(2015, 5, 18),
                 date(2015, 5, 19),
                 date(2015, 5, 20),
                 ]
    expected_date = datetime(2015, 5, 18)
    ca_date = db.session.query(CAD).filter_by(title="CA date").one()
    with factories.single_commit():
      for i, ca_value in enumerate(ca_values):
        program = factories.ProgramFactory(title="program {}".format(i))
        factories.CustomAttributeValueFactory(
            custom_attribute=ca_date,
            attributable=program,
            attribute_value=ca_value,
        )

    programs = self._get_first_result_set(
        self._make_query_dict("Program",
                              expression=["ca date", "=",
                                          expected_date.strftime(
                                              DATE_FORMAT_REQUEST)
                                          ]),
        "Program", "values",
    )
    titles = [prog["title"] for prog in programs]
    self.assertItemsEqual(titles, ("program 2",))
    self.assertEqual(len(programs), 1)

  def test_ca_query_lt(self):
    """Test CA date fields filtering by < operator."""
    ca_values = [date(2015, 5, 16),
                 date(2015, 5, 17),
                 date(2015, 5, 18),
                 date(2015, 5, 19),
                 date(2015, 5, 20),
                 ]
    expected_date = datetime(2015, 5, 18)
    ca_date = db.session.query(CAD).filter_by(title="CA date").one()

    with factories.single_commit():
      for i, ca_value in enumerate(ca_values):
        program = factories.ProgramFactory(title="program {}".format(i))
        factories.CustomAttributeValueFactory(
            custom_attribute=ca_date,
            attributable=program,
            attribute_value=ca_value,
        )

    programs = self._get_first_result_set(
        self._make_query_dict("Program",
                              expression=["ca date", "<",
                                          expected_date.strftime(
                                              DATE_FORMAT_REQUEST)
                                          ]),
        "Program", "values",
    )
    titles = [prog["title"] for prog in programs]
    self.assertItemsEqual(titles, ("program 0", "program 1"))
    self.assertEqual(len(programs), 2)

  def test_ca_query_gt(self):
    """Test CA date fields filtering by > operator."""
    ca_values = [date(2015, 5, 16),
                 date(2015, 5, 17),
                 date(2015, 5, 18),
                 date(2015, 5, 19),
                 date(2015, 5, 20),
                 ]
    expected_date = datetime(2015, 5, 18)
    ca_date = db.session.query(CAD).filter_by(title="CA date").one()

    with factories.single_commit():
      for i, ca_value in enumerate(ca_values):
        program = factories.ProgramFactory(title="program {}".format(i))
        factories.CustomAttributeValueFactory(
            custom_attribute=ca_date,
            attributable=program,
            attribute_value=ca_value,
        )

    programs = self._get_first_result_set(
        self._make_query_dict("Program",
                              expression=["ca date", ">",
                                          expected_date.strftime(
                                              DATE_FORMAT_REQUEST)
                                          ]),
        "Program", "values",
    )
    titles = [prog["title"] for prog in programs]
    self.assertItemsEqual(titles, ("program 3", "program 4"))
    self.assertEqual(len(programs), 2)

  # pylint: disable=invalid-name
  def test_ca_query_incorrect_date_format(self):
    """CA filtering should fail on incorrect date when CA title is unique."""
    ca_values = [datetime(2015, 5, 16),
                 datetime(2015, 5, 17),
                 datetime(2015, 5, 18),
                 datetime(2015, 5, 19),
                 datetime(2015, 5, 20),
                 ]
    ca_date = db.session.query(CAD).filter_by(title="CA date").first()
    with factories.single_commit():
      for i, ca_value in enumerate(ca_values):
        program = factories.ProgramFactory(title="program {}".format(i))
        factories.CustomAttributeValueFactory(
            custom_attribute=ca_date,
            attributable=program,
            attribute_value=ca_value,
        )

    data = self._make_query_dict(
        "Program",
        expression=["ca date", ">", "05.18.2015"],
    )
    response = self._post(data)
    self.assert400(response)
    self.assertEqual(DateValue.VALUE_ERROR_MSG, response.json['message'])


@ddt.ddt
class TestQueryWithUnicode(TestCase, WithQueryApi):
  """Test query API with unicode values."""

  CAD_TITLE1 = u"CA список" + "X" * 200
  CAD_TITLE2 = u"CA текст" + "X" * 200
  # pylint: disable=anomalous-backslash-in-string
  CAD_TITLE3 = u"АС\ЫЦУМПА"  # definitely did not work

  @classmethod
  def _generate_cad(cls):
    """Generate custom attribute definitions."""
    with app.app.app_context():
      factories.CustomAttributeDefinitionFactory(
          title=cls.CAD_TITLE1,
          definition_type="program",
          multi_choice_options=u"один,два,три,четыре,пять",
      )
      factories.CustomAttributeDefinitionFactory(
          title=cls.CAD_TITLE2,
          definition_type="program",
      )
      factories.CustomAttributeDefinitionFactory(
          title=cls.CAD_TITLE3,
          definition_type="program",
      )

  @staticmethod
  def _flatten_cav(data):
    """Unpack CAVs and put them in data as object attributes."""
    cad_names = dict(db.session.query(CAD.id, CAD.title))
    for entry in data:
      for cav in entry.get("custom_attribute_values", []):
        entry[cad_names[cav["custom_attribute_id"]]] = cav["attribute_value"]
    return data

  def setUp(self):
    super(TestQueryWithUnicode, self).setUp()
    self.client.get("/login")
    self._generate_cad()

  # pylint: disable=invalid-name
  def test_query_attr_with_unicode_value(self):
    """Test query of basic attribute by unicode value."""
    program_title = u"программа A"
    factories.ProgramFactory(title=program_title)
    programs = self._get_first_result_set(
        self._make_query_dict("Program",
                              expression=["title", "=", program_title]),
        "Program",
    )

    self.assertEqual(programs["count"], 1)
    self.assertEqual(len(programs["values"]), programs["count"])

  # pylint: disable=invalid-name
  def test_query_ca_with_unicode_value(self):
    """Test query of custom attribute by unicode value."""

    ca_text_value = u"Ы текст"
    ca_title = self.CAD_TITLE3
    ca_attr = db.session.query(CAD).filter_by(title=ca_title).first()
    with factories.single_commit():
      program = factories.ProgramFactory()
      factories.CustomAttributeValueFactory(custom_attribute=ca_attr,
                                            attributable=program,
                                            attribute_value=ca_text_value)

    programs = self._get_first_result_set(
        self._make_query_dict("Program",
                              expression=[ca_title, "=", ca_text_value]),
        "Program",
    )

    self.assertEqual(programs["count"], 1)
    self.assertEqual(len(programs["values"]), programs["count"])

  def test_sorting_by_ca(self):
    """Test sorting by CA fields with unicode names."""
    ca1_title = self.CAD_TITLE1
    ca2_title = self.CAD_TITLE2
    ca1_values = [u"три", u"один", u"три", u"один", u"четыре"]
    ca2_values = [u"B текст", u"A текст", u"B текст", u"C текст", u"A текст"]
    ca1 = db.session.query(CAD).filter_by(title=ca1_title).one()
    ca2 = db.session.query(CAD).filter_by(title=ca2_title).one()
    with factories.single_commit():
      for i, (ca1_value, ca2_value) in enumerate(zip(ca1_values, ca2_values)):
        program = factories.ProgramFactory(title="program {}".format(i))
        factories.CustomAttributeValueFactory(custom_attribute=ca1,
                                              attributable=program,
                                              attribute_value=ca1_value)
        factories.CustomAttributeValueFactory(custom_attribute=ca2,
                                              attributable=program,
                                              attribute_value=ca2_value)

    programs = self._flatten_cav(
        self._get_first_result_set(
            self._make_query_dict("Program",
                                  order_by=[{"name": self.CAD_TITLE2},
                                            {"name": self.CAD_TITLE1}]),
            "Program", "values",
        )
    )

    keys = [(prog[self.CAD_TITLE2], prog[self.CAD_TITLE1])
            for prog in programs]
    self.assertEqual(keys, sorted(keys))


@ddt.ddt
class TestFilteringAttributes(WithQueryApi, TestCase):
  """Test query API filtering by attributes."""

  def setUp(self):
    super(TestFilteringAttributes, self).setUp()
    self.client.get("/login")

    generator_ = generator.ObjectGenerator()

    _, self.person = generator_.generate_person({'name': 'old_name'})
    generator_.modify(self.person, 'person', {'name': 'new_name'})

  def test_filtering_by_two_attrs(self):
    """Test filtering by two attributes."""
    revisions = self._get_first_result_set(
        self._make_query_dict(
            "Revision",
            expression=[
                {
                    "left": "resource_id",
                    "op": {
                        "name": "="
                    },
                    "right": self.person.id
                },
                'AND',
                {
                    "left": "resource_type",
                    "op": {
                        "name": "="
                    },
                    "right": "Person"
                }
            ]
        ),
        "Revision", "values",
    )

    self.assertEqual(len(revisions), 2)

  def test_filtering_by_three_attrs(self):
    """Test filtering by three attributes."""
    revisions = self._get_first_result_set(
        self._make_query_dict(
            "Revision",
            expression=[
                {
                    "left": {
                        "left": "resource_id",
                        "op": {
                            "name": "="
                        },
                        "right": self.person.id
                    },
                    "op": {
                        "name": "AND"
                    },
                    "right": {
                        "left": "resource_type",
                        "op": {
                            "name": "="
                        },
                        "right": "Person"
                    }
                },
                'AND',
                {
                    "left": "action",
                    "op": {
                        "name": "="
                    },
                    "right": "modified"
                }
            ]
        ),
        "Revision", "values",
    )

    self.assertEqual(len(revisions), 1)


@ddt.ddt
class TestQueryWithSpecialChars(TestCase, WithQueryApi):
  """Test query API with '\', '_' and '%' chars."""

  def setUp(self):
    super(TestQueryWithSpecialChars, self).setUp()
    self.client.get("/login")
    with factories.single_commit():
      factories.RiskFactory(description=r"1235_123")
      factories.RiskFactory(description=r"1235123")
      factories.RiskFactory(description=r"1235%123")
      factories.RiskFactory(description=r"123\5123")
      factories.RiskFactory(description=r'1235"123')
      factories.RiskFactory(description=r"123325\123")

  @ddt.data(
      ("description", r"\5", 1),
      ("description", "5_", 1),
      ("description", "5%", 1),
      ("description", '5"', 1),
      ("description", "5", 6),
  )
  @ddt.unpack
  def test_query(self, param, text, count):
    """Test query by unicode value."""

    risks = self._get_first_result_set(
        self._make_query_dict("Risk", expression=[param, "~", text]),
        "Risk",
    )
    self.assertEqual(risks["count"], count)
