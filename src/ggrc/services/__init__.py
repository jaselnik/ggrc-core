# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""All GGRC REST services."""

from ggrc.services import common
from ggrc.services.registry import service
from ggrc.services.resources import external_internal


def contributed_services():
  """The list of all GGRC collection services as a list of
  (url, ModelClass) tuples.
  """
  import ggrc.models.all_models as models
  from ggrc.access_control import role
  from ggrc.models import review
  from ggrc.services.resources import access_controle_role
  from ggrc.services.resources import assessment
  from ggrc.services.resources import audit
  from ggrc.services.resources import external
  from ggrc.services.resources import issue
  from ggrc.services.resources import person
  from ggrc.services.resources import related_assessments
  from ggrc.services.resources import relationship
  from ggrc.services.resources import snapshot

  return [
      service('background_tasks', models.BackgroundTask),
      service('access_groups', models.AccessGroup, external.ExternalResource),
      service('audits', models.Audit, audit.AuditResource),
      service('calendar_events', models.CalendarEvent),
      service('contexts', models.Context),
      service('controls', models.Control, external.ExternalResource),
      service('assessments', models.Assessment, assessment.AssessmentResource),
      service('assessment_templates', models.AssessmentTemplate),
      service('comments', models.Comment),
      service('external_comments', models.ExternalComment),
      service('custom_attribute_definitions',
              models.CustomAttributeDefinition,
              external_internal.ExternalInternalCADResource),
      service('data_assets', models.DataAsset, external.ExternalResource),
      service('directives', models.Directive, common.ReadOnlyResource),
      service('contracts', models.Contract),
      service('evidence', models.Evidence),
      service('policies', models.Policy),
      service('regulations', models.Regulation),
      service('standards', models.Standard),
      service('documents', models.Document),
      service('events', models.Event, common.ReadOnlyResource),
      service('facilities', models.Facility, external.ExternalResource),
      service('markets', models.Market, external.ExternalResource),
      service('object_people', models.ObjectPerson),
      service('objectives', models.Objective),
      service('options', models.Option),
      service('org_groups', models.OrgGroup, external.ExternalResource),
      service('vendors', models.Vendor, external.ExternalResource),
      service('people', models.Person, person.PersonResource),
      service('people_profiles', models.PersonProfile),
      service('products', models.Product, external.ExternalResource),
      service('projects', models.Project, external.ExternalResource),
      service('programs', models.Program),
      service('relationships',
              models.Relationship,
              relationship.RelationshipResource),
      service('revisions', models.Revision, common.ReadOnlyResource),
      service('requirements', models.Requirement),
      service('risks', models.Risk, external.ExternalResource),
      service('threats', models.Threat),
      service('systems',
              models.System,
              external.ExternalResource),
      service('processes', models.Process, external.ExternalResource),
      service('metrics', models.Metric, external.ExternalResource),
      service('notification_configs', models.NotificationConfig),
      service('issues', models.Issue, issue.IssueResource),
      service('snapshots', models.Snapshot, snapshot.SnapshotResource),
      service('access_control_roles', role.AccessControlRole,
              access_controle_role.AccessControlRoleResource),
      service('labels', models.Label),
      service('proposals', models.Proposal),
      service('related_assessments', None,
              related_assessments.RelatedAssessmentsResource),
      service('technology_environments', models.TechnologyEnvironment,
              external.ExternalResource),
      service('product_groups', models.ProductGroup,
              external.ExternalResource),
      service('reviews', review.Review),
      service('key_reports', models.KeyReport, external.ExternalResource),
      service('account_balances', models.AccountBalance,
              external.ExternalResource),
  ]


def all_services():
  """Get services from all modules."""
  from ggrc.extensions import get_extension_modules

  services = contributed_services()

  for extension_module in get_extension_modules():
    contributions = getattr(extension_module, 'contributed_services', None)
    if contributions:
      if callable(contributions):
        contributions = contributions()
      services.extend(contributions)
  return services


def init_extra_services(app):
  """Add extra service url rules."""
  from ggrc.login import login_required

  from ggrc.services.search import search
  app.add_url_rule(
      '/search', 'search', login_required(search))

  from ggrc.services.suggest import suggest
  app.add_url_rule('/people/suggest', 'suggest', login_required(suggest))


def init_all_services(app):
  """Register all GGRC REST services with the Flask application ``app``."""
  from ggrc.extensions import get_extension_modules
  from ggrc.login import login_required

  for entry in all_services():
    entry.service_class.add_to(
        app,
        '/api/{0}'.format(entry.name),
        entry.model_class,
        decorators=(login_required,),
    )

  init_extra_services(app)
  for extension_module in get_extension_modules():
    ext_extra_services = getattr(extension_module, 'init_extra_services', None)
    if ext_extra_services:
      ext_extra_services(app)
