# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Test export for full filled model"""
import csv
import datetime
from StringIO import StringIO

import ddt

from ggrc import (
    db,
    settings,
    converters,
)
from ggrc.converters import import_helper
from ggrc.models import all_models
from ggrc.models import assessment_template
from integration.ggrc import TestCase, api_helper
from integration.ggrc.models import factories


def get_exportables():
  """Get all exportables models except snapshot"""
  exportables = set(converters.get_exportables().values())
  exportables.discard(all_models.Snapshot)
  return exportables


def set_attribute(obj, attribute, value):
  if getattr(obj, attribute, None) in ([], '', None):
    setattr(obj, attribute, value)


@ddt.ddt
class TestFullFilledModelExport(TestCase):
  """Test for export a full filled model"""
  # pylint: disable=undefined-variable

  FIELDS_FILLED_RULES = {
      'archived': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'archived',
          False
      ),
      'assertions': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'assertions',
          'assertions'
      ),
      'assessment_template': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'assessment_template',
          'assessment_template'
      ),
      'assessment_type': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'assessment_type',
          'Control'
      ),
      'audit': lambda **kwargs: TestFullFilledModelExport._map_object(
          source=kwargs['obj'],
          destination=kwargs['obj'].audit
      ),
      'categories': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'categories',
          '["categories"]'
      ),
      'comments': lambda **kwargs: TestFullFilledModelExport._map_object(
          source=kwargs['obj'],
          destination=factories.CommentFactory(
              description='description',
              assignee_type='Admin'
          )
      ),
      'company': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'company',
          'company'
      ),
      'component_id': lambda **kwargs: factories.IssueTrackerIssueFactory(
          enabled=True,
          issue_tracked_obj=kwargs['obj'],
          issue_id=123,
          issue_type="PROCESS",
          component_id=12345,
          hotlist_id=12345,
          issue_priority="P2",
          issue_severity="S2",
          issue_url="somelink",
      ),
      'contact': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'contact',
          kwargs['user']
      ),
      'created_at': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'created_at',
          datetime.date(2019, 9, 24)
      ),
      'created_by': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'created_by_id',
          kwargs['user'].id
      ),
      'cycle': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'cycle',
          'cycle'
      ),
      'cycle_task_group': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'cycle_task_group',
          'cycle_task_group'
      ),
      'cycle_workflow': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'cycle_workflow',
          'cycle_workflow'
      ),
      'default_assignees': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'default_assignees',
          kwargs['user']
      ),
      'default_verifier': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'default_verifier',
          kwargs['user']
      ),
      'directive': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'directive',
          'directive'
      ),
      'delete': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'delete',
          'delete'
      ),
      'description': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'description',
          'description'
      ),
      'design': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'design',
          'Effective'
      ),
      'documents_file': lambda **kwargs: TestFullFilledModelExport._map_object(
          source=factories.DocumentFileFactory(link='link'),
          destination=kwargs['obj'],
      ),
      'documents_reference_url':
      lambda **kwargs: TestFullFilledModelExport._map_object(
          source=factories.DocumentReferenceUrlFactory(link='link'),
          destination=kwargs['obj'],
      ),
      'due_date': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'due_date',
          datetime.date(2019, 9, 24)
      ),
      'email': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'email',
          'somebody@mail.com'
      ),
      'enabled': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'enabled',
          True
      ),
      'end_date': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'end_date',
          datetime.date(2019, 9, 24)
      ),
      'evidences_file': lambda **kwargs: TestFullFilledModelExport._map_object(
          source=factories.EvidenceFileFactory(),
          destination=kwargs['obj'],
      ),
      'evidences_url': lambda **kwargs: TestFullFilledModelExport._map_object(
          source=factories.EvidenceUrlFactory(),
          destination=kwargs['obj'],
      ),
      'finished_date': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'finished_date',
          datetime.date(2019, 9, 24)
      ),
      'folder': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'folder',
          'folder'
      ),
      'fraud_related': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'fraud_related',
          True
      ),
      'hotlist_id': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'hotlist_id',
          'hotlist_id'
      ),
      'is_verification_needed': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'is_verification_needed',
          True
      ),
      'issue_priority': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'issue_priority',
          'issue_priority'
      ),
      'issue_severity': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'issue_severity',
          'issue_severity'
      ),
      'issue_title': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'issue_title',
          'issue_title'
      ),
      'issue_tracker': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'issue_tracker',
          'issue_tracker'
      ),
      'issue_type': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'issue_type',
          'issue_type'
      ),
      'key_control': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'key_control',
          True
      ),
      'kind': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'kind',
          all_models.Option.query.filter(
              all_models.Option == 'product_type'
          ).first()
      ),
      'labels': lambda **kwargs: factories.ObjectLabelFactory(
          labeled_object=kwargs['obj'],
          label=factories.LabelFactory(
              object_type=kwargs['obj'].__tablename__
          ),
      ),
      'last_assessment_date':
      lambda **kwargs: TestFullFilledModelExport._create_attributes(
          kwargs['obj'],
          1
      ),
      'last_comment':
      lambda **kwargs: TestFullFilledModelExport._create_attributes(
          kwargs['obj'],
          3
      ),
      'last_deprecated_date': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'last_deprecated_date',
          datetime.date(2019, 9, 24)
      ),
      'last_submitted_at': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'last_submitted_at',
          datetime.date(2019, 9, 24)
      ),
      'last_submitted_by': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'last_submitted_by_id',
          kwargs['user'].id
      ),
      'last_verified_at': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'last_verified_at',
          datetime.date(2019, 9, 24)
      ),
      'last_verified_by': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'last_verified_by_id',
          kwargs['user'].id
      ),
      'means': lambda **kwargs: set_attribute(kwargs['obj'], 'means', 'means'),
      'modified_by': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'modified_by',
          kwargs['user']
      ),
      'name': lambda **kwargs: set_attribute(kwargs['obj'], 'name', 'name'),
      'network_zone': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'network_zone',
          all_models.Option.query.filter(
              all_models.Option == 'network_zone'
          ).first()
      ),
      'notes': lambda **kwargs: set_attribute(kwargs['obj'], 'notes', 'notes'),
      'notify_custom_message': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'notify_custom_message',
          'notify_custom_message'
      ),
      'notify_on_change': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'notify_on_change',
          True
      ),
      'operationally': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'operationally',
          'Effective'
      ),
      'people_sync_enabled': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'people_sync_enabled',
          True
      ),
      'procedure_description': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'procedure_description',
          'procedure description'
      ),
      'program': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'program',
          'program'
      ),
      'readonly': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'readonly',
          True
      ),
      'recipients': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'recipients',
          'recipients'
      ),
      'repeat_every': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'repeat_every',
          1
      ),
      'report_end_date': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'report_end_date',
          datetime.date(2019, 9, 24)),
      'report_start_date': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'report_start_date',
          datetime.date(2019, 8, 20)
      ),
      'review_status': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'review_status',
          'review status'
      ),
      'review_status_display_name': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'review_status_display_name',
          'review status display name'
      ),
      'reviewers': lambda **kwargs: TestFullFilledModelExport._create_acl(
          'Reviewers',
          factories.ReviewFactory(reviewable=kwargs['obj']),
          kwargs['user'],
      ),
      'risk_type': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'risk_type',
          'risk_type'
      ),
      'secondary_contact': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'secondary_contact',
          kwargs['user']
      ),
      'send_by_default': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'send_by_default',
          True
      ),
      'slug': lambda **kwargs: set_attribute(kwargs['obj'], 'slug', 'slug'),
      'start_date': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'start_date',
          datetime.date(2019, 8, 20)
      ),
      'status': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'status',
          'In Progress'
      ),
      'task_group': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'task_group',
          'task_group'
      ),
      'task_type': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'task_type',
          'text'
      ),
      'template_custom_attributes': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'template_custom_attributes',
          'adsasd'
      ),
      'template_object_type': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'template_object_type',
          'Objective'
      ),
      'test_plan': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'test_plan',
          'test_plan'
      ),
      'test_plan_procedure': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'test_plan_procedure',
          True
      ),
      'threat_event': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'threat_event',
          'threat event'
      ),
      'threat_source': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'threat_source',
          'threat source'
      ),
      'title': lambda **kwargs: set_attribute(kwargs['obj'], 'title', 'title'),
      'unit': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'unit',
          all_models.Workflow.DAY_UNIT
      ),
      'updated_at': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'updated_at',
          datetime.date(2019, 8, 20)
      ),
      'user_role': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'user_role',
          'user_role'
      ),
      'verified_date': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'verified_date',
          datetime.date(2019, 9, 24)
      ),
      'verify_frequency': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'verify_frequency',
          'verify frequency'
      ),
      'vulnerability': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'vulnerability',
          'vulnerability'
      ),
      'workflow': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'workflow',
          'workflow'
      ),
      'review_levels_count': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'review_levels_count',
          settings.REVIEW_LEVELS_MIN_COUNT
      ),
      'verification_workflow': lambda **kwargs: set_attribute(
          kwargs['obj'],
          'verification_workflow',
          assessment_template.VerificationWorkflow.MLV
      ),
  }

  @staticmethod
  def _create_attributes(obj, attribute_template_id):
    """Create attribute for object"""
    attr = all_models.Attributes(
        object_id=obj.id,
        object_type=obj.__class__.__name__,
        value_datetime=datetime.datetime(2019, 9, 26),
        value_string="last comment",
        attribute_template_id=attribute_template_id,
        updated_at=datetime.datetime.now(),
        created_at=datetime.datetime.now(),
    )
    db.session.add(attr)
    db.session.commit()

  @staticmethod
  def _map_object(source, destination):
    """Create relationship with between two objects"""
    from ggrc.models import exceptions
    try:
      factories.RelationshipFactory(source=source, destination=destination)
    except exceptions.ValidationError:
      return

  def _map_snapshot(self, obj, destination):
    """Create relationship between object and his snapshot"""
    revision = self._get_latest_object_revisions([obj])[0]
    parent = destination
    if not isinstance(parent, all_models.Audit):
      parent = destination.audit
    snapshot = factories.SnapshotFactory(
        child_id=revision.resource_id,
        child_type=revision.resource_type,
        revision=revision,
        parent=parent,
        parent_id=parent.id,
    )
    factories.RelationshipFactory(source=snapshot, destination=destination)

  @staticmethod
  def _create_acl(role, obj, user):
    """Propagate acl for obj"""
    ac_role = all_models.AccessControlRole.query.filter(
        all_models.AccessControlRole.name == role,
        all_models.AccessControlRole.object_type == obj.__class__.__name__,
    ).one()
    factories.AccessControlPersonFactory(
        ac_list=obj.acr_acl_map[ac_role],
        person=user,
    )

  @staticmethod
  def _set_field(alias, obj, user):
    """Set field for model"""
    kwargs = {'obj': obj, 'user': user}
    set_attr = TestFullFilledModelExport.FIELDS_FILLED_RULES[alias]
    set_attr(**kwargs)

  @staticmethod
  def _get_aliases(model):
    """Get aliases for provided model"""
    return [c for c in import_helper.get_object_column_definitions(model)]

  def assert_full_filled_model(self, data):
    """Assert that all columns are filled for export

    Args:
      data: list of rows from csv table

    Raises:
      AssertionError: if not all require columns are filled for model

    """
    errors = []
    # these columns only for import
    ignore = ['Delete', 'Comments',
              'Policy / Regulation / Standard / Contract',
              'Template', 'Custom Attributes']
    rows = csv.reader(StringIO(data))
    rows = [r for r in rows][:3]

    for top, column_name, field_value in zip(*rows):
      if column_name.startswith('unmap:') or column_name in ignore:
        continue
      elif top == 'Object type':
        title = column_name
        continue
      if field_value == '':
        errors.append(column_name)

    self.assertEqual(errors, [],
                     'These columns for {0} are not exported: {1}'.format(
                     title, ', '.join(errors)))

  def build_object(self, model):
    """Fill all fields in model"""
    errors = []
    obj = factories.get_model_factory(model.__name__)()
    aliases = sorted(self._get_aliases(model))

    for alias in aliases:
      if alias.startswith('__mapping__'):
        title = alias.split(':')[1]
        mapped_model = ''.join([part.title() for part in title.split()])
        destination_obj = factories.get_model_factory(mapped_model)()

        self._map_object(source=obj, destination=destination_obj)
      elif alias.startswith('__snapshot_mapping__'):
        title = alias.split(':')[1]
        mapped_model = ''.join([part.title() for part in title.split()])
        destination_obj = factories.get_model_factory(mapped_model)()

        self._map_snapshot(destination_obj, obj)
      elif alias.startswith('__acl__'):
        role = alias.split(':')[1]
        self._create_acl(role, obj, self.user)
      elif not alias.startswith('__'):
        try:
          self._set_field(alias, obj, self.user)
        except KeyError:
          errors.append(alias)
      else:
        continue

    db.session.commit()

    self.assertEqual(errors, [],
                     'These columns are not filled for model: {}. '
                     'Need to add rule for these into '
                     'FIELDS_FILLED_RULES'.format(
                     ', '.join(errors)))
    return obj

  def setUp(self):
    super(TestFullFilledModelExport, self).setUp()
    self.api = api_helper.Api()
    self.client.get('/login')

    self.user = all_models.Person.query.filter(
        all_models.Person.email == "user@example.com"
    ).one()

  @ddt.data(
      *get_exportables()
  )
  def test_full_filled_model_export(self, model):
    """Test export of {0.__name__} with all filled columns

    We defined dict with fillable fields from all models.
    So since we get some new column in model we need define it in `attrs_dict`

    Raises:
      AssertionError: 1. Raised when column isn't present in `attrs_dict`.
        So we need to add rules for this column to dict.

        2. Raised when some columns are missed for export. So we need fix rules
        for columns in `attrs_dict`.
    """
    model_name = model.__name__
    obj = self.build_object(model)

    data = [{
        "object_name": model_name,
        "filters": {
            "expression": {
                'left': 'id',
                'op': {'name': '='},
                'right': obj.id,
            }
        },
        "fields": "all",
    }]
    response = self.export_csv(data)
    response_data = response.data

    self.assert_full_filled_model(response_data)
    self.assert200(response)
