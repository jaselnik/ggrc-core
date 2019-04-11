# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for snapshot export."""
import collections
import json
import unittest

from ggrc import models, db
from ggrc.utils import QueryCounter, DATE_FORMAT_US
from integration.ggrc import TestCase
from integration.ggrc.models import factories

from appengine import base


@base.with_memcache
class TestExportSnapshots(TestCase):
  """Tests basic snapshot export."""

  def setUp(self):
    super(TestExportSnapshots, self).setUp()
    self.client.get("/login")
    self.headers = {
        "Content-Type": "application/json",
        "X-Requested-By": "GGRC",
        "X-export-view": "blocks",
    }

  def test_simple_export(self):
    """Test simple empty snapshot export."""
    search_request = [{
        "object_name": "Snapshot",
        "filters": {
            "expression": {
                "left": "child_type",
                "op": {"name": "="},
                "right": "Control",
            },
        },
    }]
    parsed_data = self.export_parsed_csv(search_request)["Snapshot"]
    self.assertEqual(parsed_data, [])

  @staticmethod
  def _get_cav(control, cad_name):
    """Get proper CA value for a given CAD name."""
    for cav in control.custom_attribute_values:
      if cav.custom_attribute.title == cad_name:
        if cav.custom_attribute.attribute_type == "Checkbox":
          return u"yes" if int(cav.attribute_value) else u"no"
        elif cav.custom_attribute.attribute_type == "Map:Person":
          return cav.attribute_object.email if cav.attribute_object else u""
        elif cav.custom_attribute.attribute_type == "Date":
          parts = cav.attribute_value.split("-")
          return u"{}/{}/{}".format(parts[1], parts[2], parts[0])

        return cav.attribute_value
    return u""

  @staticmethod
  def _create_cads(type_):
    """Create all types of custom attribute definitions for tests."""
    with factories.single_commit():
      cad = factories.CustomAttributeDefinitionFactory
      return [
          cad(title="date", definition_type=type_, attribute_type="Date"),
          cad(title="checkbox", definition_type=type_,
              attribute_type="Checkbox"),
          cad(title="person", definition_type=type_,
              attribute_type="Map:Person"),
          cad(title="RT", definition_type=type_, attribute_type="Rich Text"),
          cad(title="dropdown",
              definition_type=type_,
              attribute_type="Dropdown",
              multi_choice_options="one,two,three,four,five"),
      ]

  @unittest.skip("Skip until import for controls will be deprecated")
  def test_full_control_export(self):
    """Test exporting of a single full control snapshot."""
    self._create_cads("control")
    self.import_file("control_snapshot_data_single.csv")
    # Duplicate import because we have a bug in logging revisions and this
    # makes sure that the fixture created properly.
    self.import_file("control_snapshot_data_single.csv")

    controls = models.Control.query.all()
    with factories.single_commit():
      audit = factories.AuditFactory()
      snapshots = self._create_snapshots(audit, controls)

    control_dicts = {
        control.slug: {
            # normal fields
            "Code": u"*" + control.slug,
            "Revision Date":
                snapshot.revision.created_at.strftime(DATE_FORMAT_US),
            "Description": control.description,
            "Effective Date": control.start_date.strftime(DATE_FORMAT_US),
            "Fraud Related": u"yes" if control.fraud_related else u"no",
            "Frequency": control.verify_frequency,
            "Kind/Nature": control.kind,
            "Notes": control.notes,
            "Review State": control.review_status,
            "Review Status": control.review_status_display_name,
            "Reviewers": u"",
            "Significance": u"key" if control.key_control else u"non-key",
            "State": control.status,
            "Last Deprecated Date": u"",
            "Assessment Procedure": control.test_plan,
            "Title": control.title,
            "Type/Means": control.means,
            # Custom attributes
            "RT": self._get_cav(control, "RT"),
            "checkbox": self._get_cav(control, "checkbox"),
            "date": self._get_cav(control, "date"),
            "dropdown": self._get_cav(control, "dropdown"),
            "person": self._get_cav(control, "person"),
            # Special snapshot export fields
            "Audit": audit.slug,
            "Document File": u"\n".join(c.link + " " + c.title for c in
                                        control.documents_file),
            "Reference URL": u"\n".join(c.link for c in
                                        control.documents_reference_url),
            "Assertions": u",".join(json.loads(control.assertions)),
            "Categories": u",".join(json.loads(control.categories)),
            "Folder": u"",
            "Archived": u"yes" if audit.archived else u"no",
            # Computed attributes
            "Last Assessment Date": u"",
            "Admin": u"admin@example.com\ncreator@example.com\n"
                     u"editor@example.com",
            "Control Operators": u"creator@example.com",
            "Control Owners": u"creator@example.com",
            "Other Contacts": u"creator@example.com",
            "Principal Assignees": u"creator@example.com",
            "Secondary Assignees": u"creator@example.com",
            'Created Date': control.created_at.strftime(DATE_FORMAT_US),
            'Last Updated Date': control.updated_at.strftime(DATE_FORMAT_US),
            'Last Updated By': control.modified_by.email,
        }
        for snapshot, control in zip(snapshots, controls)
    }

    search_request = [{
        "object_name": "Snapshot",
        "filters": {
            "expression": {
                "left": "child_type",
                "op": {"name": "="},
                "right": "Control",
            },
        },
    }]
    parsed_data = self.export_parsed_csv(search_request)["Control Snapshot"]
    parsed_dict = {line["Code"]: line for line in parsed_data}

    self.assertEqual(
        parsed_dict["*Control 1"],
        control_dicts["Control 1"],
    )

  def test_snapshot_mappings_export(self):
    """Test exporting snapshots with object mappings."""
    with factories.single_commit():
      control = factories.ControlFactory(slug="Control 1")
      audit = factories.AuditFactory()
      snapshot = self._create_snapshots(audit, [control])[0]
      assessments = [factories.AssessmentFactory() for _ in range(3)]
      issues = [factories.IssueFactory() for _ in range(3)]
      assessment_slugs = {assessment.slug for assessment in assessments}
      issue_slugs = {issue.slug for issue in issues}

      for assessment, issue in zip(assessments, issues):
        factories.RelationshipFactory(source=snapshot, destination=assessment)
        factories.RelationshipFactory(source=issue, destination=snapshot)

    search_request = [{
        "object_name": "Snapshot",
        "filters": {
            "expression": {
                "left": "child_type",
                "op": {"name": "="},
                "right": "Control",
            },
        },
        "fields": ["mappings"]
    }]
    parsed_data = self.export_parsed_csv(search_request)["Control Snapshot"]
    exported_control_dict = parsed_data[0]

    self.assertEqual(
        set(exported_control_dict["Map: Assessment"].splitlines()),
        assessment_slugs,
    )
    self.assertEqual(
        set(exported_control_dict["Map: Issue"].splitlines()),
        issue_slugs,
    )

  def test_empty_control_export(self):
    """Test exporting of a single full control snapshot."""
    cads = self._create_cads("control")
    with factories.single_commit():
      controls = [factories.ControlFactory(slug="Control 1")]
      for cad in cads:
        factories.CustomAttributeValueFactory(
            attributable=controls[0],
            custom_attribute=cad,
        )
      audit = factories.AuditFactory()
      snapshots = self._create_snapshots(audit, controls)

    control_dicts = {
        control.slug: {
            # normal fields
            "Code": "*" + control.slug,
            "Revision Date":
                snapshot.revision.created_at.strftime(DATE_FORMAT_US),
            "Description": u"",
            "Effective Date": u"",
            "Fraud Related": u"",
            "Frequency": u"",
            "Kind/Nature": u"",
            "Notes": u"",
            "Review Status": u"some status",
            "Significance": u"",
            "State": u"Draft",
            "Last Deprecated Date": u"",
            "Assessment Procedure": u"",
            "Title": control.title,
            "Type/Means": u"",
            # Special snapshot export fields
            "Audit": audit.slug,
            "Archived": u"yes" if audit.archived else u"no",
            # Computed attributes
            "Last Assessment Date": u"",

            # Custom attributes
            "RT": u"",
            "Reference URL": u"",
            "checkbox": u"no",
            "date": u"",
            "dropdown": u"",
            "person": u"",

            # Fields that are not included in snapshots - Known bugs.
            "Assertions": u",".join(json.loads(control.assertions)),
            "Categories": u"",
            "Document File": u"",
            "Admin": u"",
            "Control Operators": u"",
            "Control Owners": u"",
            "Other Contacts": u"",
            "Principal Assignees": u"",
            "Secondary Assignees": u"",
            'Created Date': control.created_at.strftime(DATE_FORMAT_US),
            'Last Updated Date': control.updated_at.strftime(DATE_FORMAT_US),
            'Last Updated By': "",
            "Folder": u"",
        }
        for snapshot, control in zip(snapshots, controls)
    }

    search_request = [{
        "object_name": "Snapshot",
        "filters": {
            "expression": {
                "left": "child_type",
                "op": {"name": "="},
                "right": "Control",
            },
        },
    }]
    parsed_data = self.export_parsed_csv(search_request)["Control Snapshot"]
    parsed_dict = {line["Code"]: line for line in parsed_data}

    self.assertEqual(
        parsed_dict["*Control 1"],
        control_dicts["Control 1"],
    )

  def test_same_revison_export(self):
    """Exporting the same revision multiple times."""
    with factories.single_commit():
      controls = [factories.ControlFactory(slug="Control 1")]
      audit1 = factories.AuditFactory()
      self._create_snapshots(audit1, controls)
      audit2 = factories.AuditFactory()
      self._create_snapshots(audit2, controls)
      audit_codes = {audit1.slug, audit2.slug}

    search_request = [{
        "object_name": "Snapshot",
        "filters": {
            "expression": {
                "left": "child_type",
                "op": {"name": "="},
                "right": "Control",
            },
        },
    }]
    parsed_data = self.export_parsed_csv(search_request)["Control Snapshot"]

    self.assertEqual(
        [line["Code"] for line in parsed_data],
        ["*Control 1", "*Control 1"],
    )
    self.assertEqual(
        {line["Audit"] for line in parsed_data},
        audit_codes,
    )

  def test_export_query_count(self):
    """Test for a constant number of queries for snapshot export

    The number of database queries should not be linked to the amount of data
    that is being exported.
    """
    # pylint: disable=too-many-locals
    self._create_cads("product")
    self.import_file("product_snapshot_data_multiple.csv")
    # Duplicate import because we have a bug in logging revisions and this
    # makes sure that the fixture created properly.
    self.import_file("product_snapshot_data_multiple.csv")

    product = models.Product.query.all()
    with factories.single_commit():
      audit = factories.AuditFactory()
      snapshots = self._create_snapshots(audit, product)
      count = len(snapshots)
      assessments = [factories.AssessmentFactory() for _ in range(count)]
      issues = [factories.IssueFactory() for _ in range(count)]

      for snapshot, assessment, issue in zip(snapshots, assessments, issues):
        factories.RelationshipFactory(source=snapshot, destination=assessment)
        factories.RelationshipFactory(source=issue, destination=snapshot)

    with QueryCounter() as counter:
      search_request = [{
          "object_name": "Snapshot",
          "filters": {
              "expression": {
                  "left": {
                      "left": "child_type",
                      "op": {"name": "="},
                      "right": "Product",
                  },
                  "op": {"name": "AND"},
                  "right": {
                      "left": "Code",
                      "op": {"name": "="},
                      "right": "Product 1",
                  },
              },
          },
          "fields": ["mappings"],
      }]
      self.assertEqual(
          len(self.export_parsed_csv(search_request)["Product Snapshot"]),
          1,
      )
      single_query_count = counter.get

    with QueryCounter() as counter:
      search_request = [{
          "object_name": "Snapshot",
          "filters": {
              "expression": {
                  "left": "child_type",
                  "op": {"name": "="},
                  "right": "Product",
              },
          },
          "fields": ["mappings"],
      }]
      self.assertEqual(
          len(self.export_parsed_csv(search_request)["Product Snapshot"]),
          5,
      )
      multiple_query_count = counter.get

    self.assertEqual(multiple_query_count, single_query_count)

  def test_acr_control_export(self):
    """Test exporting of a AC roles with linked users."""
    # pylint: disable=too-many-locals
    ac_roles = models.AccessControlRole.query.filter(
        models.AccessControlRole.object_type == "Control",
        models.AccessControlRole.internal == 0,
    ).all()
    control_acr_people = collections.defaultdict(dict)
    with factories.single_commit():
      # Create one more custom role
      ac_roles.append(
          factories.AccessControlRoleFactory(object_type="Control")
      )
      controls = [factories.ControlFactory(slug="Control {}".format(i))
                  for i in range(3)]
      for control in controls:
        for ac_role in ac_roles:
          person = factories.PersonFactory()
          factories.AccessControlPersonFactory(
              ac_list=control.acr_acl_map[ac_role],
              person=person,
          )
          control_acr_people[control.slug][ac_role.name] = person.email
      audit = factories.AuditFactory()
      snapshots = self._create_snapshots(audit, controls)

    control_dicts = {}
    for snapshot, control in zip(snapshots, controls):
      # As revisions for snapshot are created using factories need to
      # update their content and rewrite acl
      snapshot.revision.content = control.log_json()
      for acl in snapshot.revision.content["access_control_list"]:
        acl["person"] = {
            "id": acl["person_id"],
            "type": "Person",
        }
      db.session.add(snapshot.revision)
      db.session.commit()

      control_dicts[control.slug] = {
          "Code": "*" + control.slug,
          "Revision Date":
              snapshot.revision.created_at.strftime(DATE_FORMAT_US),
          "Description": u"",
          "Effective Date": u"",
          "Fraud Related": u"",
          "Frequency": u"",
          "Kind/Nature": u"",
          "Notes": u"",
          "Reference URL": u"",
          "Review Status": u"some status",
          "Significance": u"",
          "State": u"Draft",
          "Last Assessment Date": u"",
          "Last Deprecated Date": u"",
          "Assessment Procedure": u"",
          "Title": control.title,
          "Type/Means": u"",
          "Audit": audit.slug,
          "Assertions": u",".join(json.loads(control.assertions)),
          "Categories": u"",
          "Document File": u"",
          'Created Date': control.created_at.strftime(DATE_FORMAT_US),
          'Last Updated Date': control.updated_at.strftime(DATE_FORMAT_US),
          'Last Updated By': "",
          "Folder": u"",
          "Archived": u"yes" if audit.archived else u"no",
      }
      control_dicts[control.slug].update(**control_acr_people[control.slug])

    search_request = [{
        "object_name": "Snapshot",
        "filters": {
            "expression": {
                "left": "child_type",
                "op": {"name": "="},
                "right": "Control",
            },
        },
    }]
    parsed_data = self.export_parsed_csv(search_request)["Control Snapshot"]
    parsed_dict = {line["Code"]: line for line in parsed_data}

    for i, _ in enumerate(controls):
      self.assertEqual(
          parsed_dict["*Control {}".format(i)],
          control_dicts["Control {}".format(i)],
      )

  def test_export_deleted_acr(self):
    """Test exporting snapshots with ACL entries for deleted ACRs."""
    # pylint: disable=too-many-locals
    ac_role = factories.AccessControlRoleFactory(
        object_type="Control",
        name="Custom Role",
    )
    with factories.single_commit():
      # Create one more custom role
      control = factories.ControlFactory(slug="Control 1")
      person = factories.PersonFactory()
      factories.AccessControlPersonFactory(
          ac_list=control.acr_acl_map[ac_role],
          person=person,
      )
      audit = factories.AuditFactory()

    # pylint: disable=protected-access
    # This is used to update control revision data with the new ACL entry
    # without making a put request to that control.
    factories.ModelFactory._log_event(control)
    self._create_snapshots(audit, [control])

    db.session.delete(ac_role)
    db.session.commit()

    search_request = [{
        "object_name": "Snapshot",
        "filters": {
            "expression": {
                "left": "child_type",
                "op": {"name": "="},
                "right": "Control",
            },
        },
    }]
    parsed_data = self.export_parsed_csv(search_request)["Control Snapshot"][0]
    self.assertNotIn("Custom Role", parsed_data)

  def test_export_archived_snapshot(self):
    """Test exporting snapshots 'archived' status"""
    with factories.single_commit():
      controls = [factories.ControlFactory()]
      audit = factories.AuditFactory()
      audit_slug = audit.slug
      self._create_snapshots(audit, controls)
      audit_archived = factories.AuditFactory(archived=True)
      audit_archived_slug = audit_archived.slug
      self._create_snapshots(audit_archived, controls)

    search_request = [{
        "object_name": "Snapshot",
        "filters": {
            "expression": {},
        },
    }]
    parsed_data = self.export_parsed_csv(search_request)["Control Snapshot"]
    result = {
        parsed_data[0]["Audit"]: parsed_data[0]["Archived"],
        parsed_data[1]["Audit"]: parsed_data[1]["Archived"],
    }
    self.assertEqual(result[audit_slug], u"no")
    self.assertEqual(result[audit_archived_slug], u"yes")
