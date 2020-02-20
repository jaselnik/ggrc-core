# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Test /search REST API
"""

from collections import defaultdict

import ddt

from ggrc.models import all_models

from integration.ggrc import TestCase
from integration.ggrc.api_helper import Api
from integration.ggrc.generator import ObjectGenerator
from integration.ggrc.models import factories


class TestResource(TestCase):
  """
  Test /search REST API
  """

  def setUp(self):
    super(TestResource, self).setUp()
    self.api = Api()
    self.object_generator = ObjectGenerator()
    self.create_objects()

  def create_objects(self):
    """Create objects to be searched.

    Creates five Requirements and makes relationships.
    0   1   2   3   4
    |---|   |---|   |
    |-------|-------|
    """
    with factories.single_commit():
      self.objects = [
          factories.RequirementFactory()
          for _ in xrange(5)
      ]
      for src, dst in [(0, 1), (0, 2), (2, 3), (2, 4)]:
        factories.RelationshipFactory(
            source=self.objects[src],
            destination=self.objects[dst],
        )

    self.objects = all_models.Requirement.eager_query().filter(
        all_models.Requirement.id.in_([o.id for o in self.objects])
    ).all()

  def search(self, *args, **kwargs):
    res, _ = self.api.search(*args, **kwargs)
    return res.json["results"]["entries"]

  def test_search_all(self):
    """Test search for all objects of a type."""
    res, _ = self.api.search("Requirement")
    self.assertEqual(len(res.json["results"]["entries"]), 5)

  def test_search_query(self):
    """Test search with query by title."""
    entries = self.search("Requirement", query=self.objects[0].title)
    self.assertEqual({entry["id"] for entry in entries},
                     {self.objects[0].id})

  def test_search_relevant(self):
    """Test search with 'relevant to' single object."""
    relevant_objects = "Requirement:{}".format(self.objects[0].id)
    entries = self.search("Requirement", relevant_objects=relevant_objects)
    self.assertEqual({entry["id"] for entry in entries},
                     {self.objects[i].id for i in [1, 2]})

  def test_search_relevant_multi(self):
    """Test search with 'relevant to' multiple objects."""
    ids = ",".join("Requirement:{}".format(self.objects[i].id) for i in (0, 3))
    entries = self.search("Requirement", relevant_objects=ids)
    self.assertEqual({entry["id"] for entry in entries},
                     {self.objects[2].id})


class TestStatus(TestCase):
  """
  Test /search REST API status code
  """

  def setUp(self):
    super(TestStatus, self).setUp()
    self.api = Api()

  def test_search_existing_type(self):
    """Test search for existing type"""
    res, _ = self.api.search(types="Requirement")
    self.assert200(res)

  def test_search_non_existing_type(self):
    """Test search for non existing type"""
    res, _ = self.api.search(types="Requirementsss")
    self.assert200(res)

  def test_search_multiple_types(self):
    """Test search for multiple types"""
    res, _ = self.api.search(types="Requirement,Requirement")
    self.assert200(res)

  def test_counts_existing_type(self):
    """Test counts for existing type"""
    res, _ = self.api.search(types="Requirement", counts=True)
    self.assert200(res)

  def test_counts_non_existing_type(self):
    """Test counts for non existing type"""
    res, _ = self.api.search(types="Requirementsss", counts=True)
    self.assert200(res)

  def test_counts_multiple_types(self):
    """Test counts for multiple types"""
    res, _ = self.api.search(types="Requirement,Requirement", counts=True)
    self.assert200(res)

  # pylint: disable=invalid-name
  def test_search_fail_with_terms_none(self):
    """Test search to fail with BadRequest (400 Error) when terms are None."""
    query = '/search?types={}&counts_only={}'.format("Requirement", False)
    response = self.api.client.get(query)
    self.assert400(response)
    self.assertEqual(response.json['message'], 'Query parameter "q" '
                     'specifying search terms must be provided.')


@ddt.ddt
class TestMultipleTypes(TestCase):
  """
  Test /search REST API
  """

  def setUp(self):
    """Create indexable objects which provide required set of fulltext attrs

    Fulltext attributes are: title, name, email, notes, description, slug
    """

    super(TestMultipleTypes, self).setUp()

    self.api = Api()

    self.objects = dict()

    with factories.single_commit():
      # Create Requirements
      requirements = [factories.RequirementFactory(title=title,
                                                   description=desc,
                                                   notes=notes)
                      for title, desc, notes in (('t01', 'd01', 'n01'),
                                                 ('t02', 'd02', 'n02'),
                                                 ('t11', 'd11', 'n11'),
                                                 )]
      self.objects['Requirement'] = dict((i.title, i.id) for i in requirements)

      # Create people
      people = [factories.PersonFactory(name=name, email=email)
                for name, email in (('n01', 'e01@example.com'),
                                    ('n02', 'e02@example.com'),
                                    ('n11', 'e11@example.com'),
                                    )]
      self.objects['Person'] = dict((i.name, i.id) for i in people)

      # Create regulations (regulations represented as directives)
      regulations = [factories.RegulationFactory(title=title, notes=notes,
                                                 description=desc)
                     for title, notes, desc in (('t01r', 'n01', 'd01'),
                                                ('t02r', 'n02-qq1', 'd02'),
                                                ('t11r', 'n11', 'd11'),
                                                )]
      self.objects['Regulation'] = dict((i.title, i.id) for i in regulations)

      # Create standards (standards represented as directives)
      standards = [factories.StandardFactory(title=title, notes=notes,
                                             description=desc)
                   for title, notes, desc in (('t01s', 'n01-qq1', 'd01'),
                                              ('t02s', 'n02', 'd02'),
                                              ('t11s', 'n11', 'd11'),
                                              ('t21s', 'n21', 'd11'),
                                              )]
      self.objects['Standard'] = dict((i.title, i.id) for i in standards)

  def _get_search_ids(self, types, query, extra_params):
    """Make request and return entries in format dict(type->list_of_ids)"""

    response, _ = self.api.search(types=types, query=query, counts=False,
                                  extra_params=extra_params)

    entries = response.json['results']['entries']

    ret = defaultdict(set)
    for entry in entries:
      ret[entry['type']].add(entry['id'])

    return dict(ret)

  def _get_count_ids(self, types, query, extra_params, extra_columns=None):
    """Make request and return entries in format dict(type->number_of_ids)"""
    response, _ = self.api.search(types=types, query=query, counts=True,
                                  extra_params=extra_params,
                                  extra_columns=extra_columns)

    return response.json['results']['counts']

  def _convert_expected_to_dict(self, expected):
    """Convert list of (type, title) to dict (type -> list_of_ids)"""

    ret = defaultdict(set)
    for type_, key in expected:
      ret[type_].add(self.objects[type_][key])

    return dict(ret)

  @staticmethod
  # pylint: disable=invalid-name
  def _convert_expected_dict_to_counts(expected):
    """Convert dict(type->list_of_ids) to dict(type->count_of_ids)"""

    return dict((k, len(v)) for k, v in expected.iteritems())

  @ddt.data(
      # search for Requirements by title
      ("Requirement", "t0", None, (('Requirement', 't01'),
                                   ('Requirement', 't02'),
                                   )),
      # search for Requirements by description
      ("Requirement", "d1", None, (('Requirement', 't11'),
                                   )),
      # search for Requirements by slug
      ("Requirement", "REQUIREMENT", None, (('Requirement', 't01'),
                                            ('Requirement', 't02'),
                                            ('Requirement', 't11'),
                                            )),
      # search for people by name
      ("Person", "n0", None, (('Person', 'n01'),
                              ('Person', 'n02'),
                              )),
      # search for people by email
      ("Person", "e1", None, (('Person', 'n11'),
                              )),
      # search for regulations by notes
      ("Regulation", "n0", None, (('Regulation', 't01r'),
                                  ('Regulation', 't02r'),
                                  )),
      # search for regulations by title
      ("Regulation", "t1", None, (('Regulation', 't11r'),
                                  )),
      # search for Requirements and Reguklations by title
      ("Requirement,Regulation", "t0", None, (('Requirement', 't01'),
                                              ('Requirement', 't02'),
                                              ('Regulation', 't01r'),
                                              ('Regulation', 't02r'),
                                              )),
      # search for subtypes of the same base type
      # Regulation and Standard are both represented as Directive model
      ("Regulation,Standard", "-qq1", None, (('Regulation', 't02r'),
                                             ('Standard', 't01s'),
                                             )),
      # search with empty types
      ("", "", None, ()),
      # search with non-existing type
      ("qwe", "", None, ()),
      # search for 2 types, one does not exist
      ("Requirement,qwe", "t0", None, (('Requirement', 't01'),
                                       ('Requirement', 't02'),
                                       )),
      # search for empty text
      ("Requirement", "", None, (('Requirement', 't01'),
                                 ('Requirement', 't02'),
                                 ('Requirement', 't11'),
                                 )),
      # search for added empty extra_params
      ("Requirement", "", "", (('Requirement', 't01'),
                               ('Requirement', 't02'),
                               ('Requirement', 't11'),
                               )),
      # search by title using extra_params
      ("Requirement", "", "Requirement:title=t01", (('Requirement', 't01'),
                                                    )),
      # search by title using extra_params where model name is lowercase
      ("Requirement", "", "requirement:title=t01", (('Requirement', 't01'),
                                                    )),
      # search by title using extra_params where model name is lowercase
      ("Regulation", "", "Requirement:title=t01", (('Regulation', 't01r'),
                                                   ('Regulation', 't02r'),
                                                   ('Regulation', 't11r'),
                                                   )),
      # search nonexisting type by title using extra_params
      ("Requirement", "", "qwe:title=t01", (('Requirement', 't01'),
                                            ('Requirement', 't02'),
                                            ('Requirement', 't11'),
                                            )),
      # search in multiple models, one by title using extra_params
      # filter uses AND operation to search indexed fields and extra_params
      # for single model.
      # There is no such Requirement where indexed fields contain "d0" and
      # title is "t01", so only regulations will be returned where indexed
      # fields contain "n0"
      ("Requirement,Regulation", "d0", "Requirement:title=t11",
          (('Regulation', 't01r'),
           ('Regulation', 't02r'),
           )),
      # search for subtypes of the same base type based on extra_params
      # Regulation and Standard are both represented as Directive model
      # ensure that extra_params for Regulation will not return Standard
      # with the same notes
      ("Regulation,Standard", "-qq1", "Regulation:description=d02",
          (('Regulation', 't02r'),  # contains "-qq1" and description = "d02"
           ('Standard', 't01s'),  # contains "-qq1"
           )),
  )
  @ddt.unpack
  def test_search(self, types, query, extra_params, expected):
    """Test search of objects for types={0}, q={1}, extra_params={2}"""

    exp_search = self._convert_expected_to_dict(expected)
    response_search = self._get_search_ids(types, query, extra_params)
    self.assertEqual(response_search, exp_search)

    exp_count = self._convert_expected_dict_to_counts(exp_search)
    response_count = self._get_count_ids(types, query, extra_params)
    self.assertEqual(response_count, exp_count)

  @ddt.data(
      ("Standard", "", "Standard:title=t01s;SS:description=d11",
       "SS=Standard",
       {
           "Standard": 1,
           "SS": 2
       }),
      # Add "Standard_ALL" column for which extra_params is not defined
      ("Standard", "", "SS:description=d11",
       "SS=Standard,Standard_All=Standard",
       {
           "SS": 2,
           "Standard_All": 4
       }),
      # types can contain column name from extra_columns
      # ensure that it is also handled correctly
      ("Standard_All", "", "SS:description=d11",
       "SS=Standard,Standard_All=Standard",
       {
           "Standard_All": 4,
           "SS": 2
       }),
  )
  @ddt.unpack
  # pylint: disable=too-many-arguments
  def test_count_with_extra_coloumns(self, types, query, extra_params,
                                     extra_columns, expected):
    """Test extra_columns types={0}, q={1}, extra_params={2}, extra_columns={3}
    """

    response_count = self._get_count_ids(types, query, extra_params,
                                         extra_columns)
    self.assertEqual(response_count, expected)
