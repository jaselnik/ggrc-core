# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Factories for ggrc models.

These are factories for generating regular ggrc models. The factories create a
model and log a post event with the model revision. These do not however
trigger signals. For tests that rely on proper signals being triggered, we must
use the object generator in the ggrc.generator module.
"""

# pylint: disable=too-few-public-methods,missing-docstring,old-style-class
# pylint: disable=no-init

import sys
import random
import string
import datetime
from contextlib import contextmanager

import factory

from ggrc import db
from ggrc.models.mixins import synchronizable
from ggrc.models import saved_search
from ggrc.models import all_models, get_model

from ggrc.access_control import roleable

from integration.ggrc.models.model_factory import ModelFactory


def random_str(length=8, prefix="", chars=None, suppress_whitespace=True):
  """Generate random string.

  Args:
    length: length of expected random string.
    prefix: string prefix.
    chars: set of chars for generating.
    suppress_whitespace: suppress whitespace duplication.
  Returns:
    Prefix with random string.
  """
  chars = chars or string.ascii_uppercase + string.digits + "  _.-"
  random_string = ''
  while len(random_string) < length:
    random_char = random.choice(chars)
    if suppress_whitespace:
      is_second_whitespace = bool(
          random_string and random_char == random_string[-1] == " ")
      is_start_end_whitespace = bool(
          random_char == " " and
          (not random_string or len(random_string) + 1 == length))
      if is_second_whitespace or is_start_end_whitespace:
        continue
    random_string += random_char
  return prefix + random_string


@contextmanager
def single_commit():
  """Run all factory create calls in single commit."""
  db.session.single_commit = False
  try:
    yield
  except:
    raise
  else:
    db.session.commit()
  finally:
    db.session.single_commit = True


class SynchronizableExternalId:
  """Helper class for object external ID generation.

  Note: It should not be used as values for `id` field on factories due to
  compatibility errors with factory boy library.
  """

  _value_iterator = iter(xrange(sys.maxint))

  @classmethod
  def next(cls):
    return next(cls._value_iterator)


class TitledFactory(ModelFactory):
  """Base factory class for `Titled` objects."""

  title = factory.LazyAttribute(lambda m: random_str(prefix='title '))


class PersonFactory(ModelFactory):
  """Factory class for `Person` objects."""

  class Meta:
    model = all_models.Person

  email = factory.LazyAttribute(
      lambda _: random_str(chars=string.ascii_letters) + "@example.com"
  )
  name = factory.LazyAttribute(
      lambda _: random_str(prefix="Person", chars=string.ascii_letters)
  )


class ExternalResourceFactory(ModelFactory):
  """Base factory class for external objects."""

  id = factory.Sequence(lambda x: x + 1)  # pylint: disable=invalid-name

  external_id = factory.Sequence(lambda x: x + 1)
  external_slug = factory.LazyAttribute(lambda _: random_str())

  created_by = factory.SubFactory(PersonFactory)
  created_by_id = factory.SelfAttribute("created_by.id")


class SystemOrProcess(ExternalResourceFactory):
  """SystemOrProcess factory class"""
  class Meta:
    model = all_models.SystemOrProcess


class WithACLandCAFactory(ModelFactory):
  """Factory class to create object with ACL and CA in one step"""

  @classmethod
  def _create(cls, target_class, *args, **kwargs):
    """Create instance of model"""
    acls = kwargs.pop("access_control_list_", [])
    cavs = kwargs.pop("custom_attribute_values_", [])

    instance = target_class(**kwargs)
    db.session.add(instance)
    db.session.flush()

    if acls and isinstance(instance, roleable.Roleable):
      for acl in acls:
        db.session.add(all_models.AccessControlList(
            object=instance,
            ac_role_id=acl.get("ac_role_id"),
            person_id=acl.get("person_id"),
        ))
    for cav in cavs:
      if isinstance(instance, all_models.mixins.CustomAttributable):
        db.session.add(all_models.CustomAttributeValue(
            attributable=instance,
            attribute_value=cav.get("attribute_value"),
            attribute_object_id=cav.get("attribute_object_id"),
            attribute_object_id_nn=cav.get("attribute_object_id_nn"),
            custom_attribute_id=cav.get("custom_attribute_id"),
        ))

    if isinstance(instance, all_models.CustomAttributeValue):
      cls._log_event(instance.attributable)
    if hasattr(instance, "log_json"):
      cls._log_event(instance)
    if getattr(db.session, "single_commit", True):
      db.session.commit()
    return instance


class ExternalMappingFactory(ModelFactory):
  class Meta:
    model = all_models.ExternalMapping


class CustomAttributeDefinitionFactory(TitledFactory):

  class Meta:
    model = all_models.CustomAttributeDefinition

  definition_type = None
  definition_id = None
  attribute_type = "Text"
  multi_choice_options = None

  @classmethod
  def _create(cls, target_class, *args, **kwargs):
    """Assert definition_type"""
    model = get_model(kwargs.get('definition_type'))
    if issubclass(model, synchronizable.Synchronizable):

      if "external_id" in kwargs:
        external_id = int(kwargs.pop("external_id"))
      else:
        external_id = factory.Sequence(lambda x: x + 1)

      if "external_type" in kwargs:
        external_type = kwargs.pop("external_type")
      else:
        external_type = "custom_attribute_definition"

    cad = super(CustomAttributeDefinitionFactory, cls)._create(
        target_class,
        *args,
        **kwargs
    )
    # pylint: disable=protected-access
    if issubclass(model, synchronizable.Synchronizable):
      cad._external_info = ExternalMappingFactory(
          external_id=external_id,
          object_type=target_class.type,
          external_type=external_type,
          object_id=int(cad.id)
      )

    return cad


class CustomAttributeValueFactory(ModelFactory):

  class Meta:
    model = all_models.CustomAttributeValue

  custom_attribute = None
  attributable_id = None
  attributable_type = None
  attribute_value = None
  attribute_object_id = None


class DirectiveFactory(TitledFactory):

  class Meta:
    model = all_models.Directive


class ControlFactory(ExternalResourceFactory, TitledFactory):

  class Meta:
    model = all_models.Control

  assertions = factory.LazyAttribute(lambda _: '["{}"]'.format(random_str()))
  review_status = all_models.Review.STATES.UNREVIEWED
  review_status_display_name = "some status"


class IssueFactory(TitledFactory):

  class Meta:
    model = all_models.Issue

  due_date = factory.LazyFunction(datetime.datetime.utcnow)


class IssueTrackerIssueFactory(TitledFactory):

  class Meta:
    model = all_models.IssuetrackerIssue

  issue_tracked_obj = factory.LazyAttribute(lambda m: AssessmentFactory())
  issue_id = factory.LazyAttribute(lambda _: random.randint(1, 1000))


class AssessmentFactory(TitledFactory):

  class Meta:
    model = all_models.Assessment

  audit = factory.LazyAttribute(lambda m: AuditFactory())


class ContextFactory(ModelFactory):

  class Meta:
    model = all_models.Context

  name = factory.LazyAttribute(
      lambda obj: random_str(prefix="SomeObjectType Context"))
  related_object = None


class ProgramFactory(TitledFactory):

  class Meta:
    model = all_models.Program

  context = factory.LazyAttribute(lambda _: ContextFactory())


class AuditFactory(TitledFactory):

  class Meta:
    model = all_models.Audit

  status = "Planned"
  program = factory.LazyAttribute(lambda _: ProgramFactory())
  context = factory.LazyAttribute(lambda _: ContextFactory())

  @classmethod
  def _create(cls, target_class, *args, **kwargs):
    """Fix context related_object when audit is created"""
    instance = super(AuditFactory, cls)._create(target_class, *args, **kwargs)
    instance.context.related_object = instance

    if getattr(db.session, "single_commit", True):
      db.session.commit()
    return instance


class SnapshotFactory(ModelFactory):

  class Meta:
    model = all_models.Snapshot

  parent = factory.LazyAttribute(lambda _: AuditFactory())
  child_id = 0
  child_type = ""
  revision_id = 0


class AssessmentTemplateFactory(TitledFactory):

  class Meta:
    model = all_models.AssessmentTemplate

  audit = factory.LazyAttribute(lambda m: AuditFactory())
  template_object_type = None
  test_plan_procedure = False
  procedure_description = factory.LazyAttribute(
      lambda _: random_str(length=100))
  default_people = {"assignees": "Admin",
                    "verifiers": "Admin"}


class ContractFactory(ExternalResourceFactory, TitledFactory):

  class Meta:
    model = all_models.Contract


class EventFactory(ModelFactory):

  class Meta:
    model = all_models.Event
  revisions = []


class AutomappingFactory(ModelFactory):
  """Automapping factory class"""

  class Meta:
    model = all_models.Automapping

  parent = None


class RelationshipFactory(ModelFactory):

  class Meta:
    model = all_models.Relationship

  automapping_id = None

  @classmethod
  def _create(cls, target_class, *args, **kwargs):
    destination = kwargs.pop("destination")
    source = kwargs.pop("source")

    if destination:
      kwargs["destination_id"] = int(destination.id)
      kwargs["destination_type"] = destination.type
    if source:
      kwargs["source_id"] = int(source.id)
      kwargs["source_type"] = source.type

    res = super(RelationshipFactory, cls)._create(
        target_class, *args, **kwargs)

    setattr(res, "{}_source".format(source.type), source)
    setattr(res, "{}_destination".format(destination.type), destination)

    return res


class CommentFactory(ModelFactory):

  class Meta:
    model = all_models.Comment


class ExternalCommentFactory(ModelFactory):

  class Meta:
    model = all_models.ExternalComment


class DocumentFactory(ModelFactory):

  class Meta:
    model = all_models.Document

  title = "some link"
  link = "some link"


class DocumentFileFactory(DocumentFactory):
  kind = all_models.Document.FILE


class DocumentReferenceUrlFactory(DocumentFactory):
  kind = all_models.Document.REFERENCE_URL


class EvidenceFactory(ModelFactory):

  class Meta:
    model = all_models.Evidence

  link = "some link"
  title = "some title"


class EvidenceUrlFactory(EvidenceFactory):
  kind = all_models.Evidence.URL


class EvidenceFileFactory(EvidenceFactory):
  kind = all_models.Evidence.FILE
  source_gdrive_id = 'source_gdrive_id'


class ObjectiveFactory(ExternalResourceFactory, TitledFactory):

  class Meta:
    model = all_models.Objective


class OptionFactory(TitledFactory):

  class Meta:
    model = all_models.Option


class RegulationFactory(TitledFactory):

  class Meta:
    model = all_models.Regulation


class OrgGroupFactory(ExternalResourceFactory, TitledFactory):

  class Meta:
    model = all_models.OrgGroup


class SystemFactory(SystemOrProcess, TitledFactory):

  class Meta:
    model = all_models.System


class KeyReportFactory(ExternalResourceFactory, TitledFactory):

  class Meta:
    model = all_models.KeyReport


class AccountBalanceFactory(ExternalResourceFactory, TitledFactory):

  class Meta:
    model = all_models.AccountBalance


class ProcessFactory(SystemOrProcess, TitledFactory):

  class Meta:
    model = all_models.Process


class PolicyFactory(ExternalResourceFactory, TitledFactory):

  class Meta:
    model = all_models.Policy


class MarketFactory(ExternalResourceFactory, TitledFactory):

  class Meta:
    model = all_models.Market


class AccessControlPersonFactory(ModelFactory):
  """Access Control People factory class"""

  class Meta:
    model = all_models.AccessControlPerson


class AccessControlListFactory(ModelFactory):
  """Access Control List factory class"""

  class Meta:
    model = all_models.AccessControlList


class AccessControlRoleFactory(ModelFactory):
  """Access Control Role factory class"""

  class Meta:
    model = all_models.AccessControlRole

  name = factory.LazyAttribute(
      lambda _: random_str(prefix="Access Control Role - ")
  )
  non_editable = False


class AccessControlRoleAdminFactory(AccessControlRoleFactory):
  """Access Control Role Admin factory class"""
  mandatory = u"1"
  name = "Admin"


class AccessGroupFactory(ExternalResourceFactory, TitledFactory):
  """Access Group factory class"""

  class Meta:
    model = all_models.AccessGroup


class DataAssetFactory(ExternalResourceFactory, TitledFactory):
  """DataAsset factory class"""

  class Meta:
    model = all_models.DataAsset


class FacilityFactory(ExternalResourceFactory, TitledFactory):
  """Facility factory class"""

  class Meta:
    model = all_models.Facility


class ObjectPersonFactory(ModelFactory):
  """ObjectPerson factory class"""

  class Meta:
    model = all_models.ObjectPerson


class ProductFactory(ExternalResourceFactory, TitledFactory):
  """Product factory class"""

  class Meta:
    model = all_models.Product


class RequirementFactory(ExternalResourceFactory, TitledFactory):
  """Requirement factory class"""

  class Meta:
    model = all_models.Requirement


class StandardFactory(TitledFactory):
  """Standard factory class"""

  class Meta:
    model = all_models.Standard

  description = factory.LazyAttribute(lambda _: random_str(length=100))


class VendorFactory(ExternalResourceFactory, TitledFactory):
  """Vendor factory class"""

  class Meta:
    model = all_models.Vendor


class RiskFactory(ExternalResourceFactory, TitledFactory):
  """Risk factory class"""

  class Meta:
    model = all_models.Risk

  risk_type = "Some Type"
  description = factory.LazyAttribute(lambda _: random_str(length=100))
  review_status = all_models.Review.STATES.UNREVIEWED
  review_status_display_name = "some status"


class ThreatFactory(ExternalResourceFactory, TitledFactory):
  """Threat factory class"""

  class Meta:
    model = all_models.Threat


class LabelFactory(ModelFactory):
  """Label factory class"""

  class Meta:
    model = all_models.Label

  name = factory.LazyAttribute(lambda m: random_str(prefix='name'))
  object_type = factory.LazyAttribute('Assessment')


class ObjectLabelFactory(ModelFactory):
  """ObjectLabel factory class"""

  class Meta:
    model = all_models.ObjectLabel


class ProposalFactory(ModelFactory):

  class Meta:
    model = all_models.Proposal

  proposed_by = factory.LazyAttribute(lambda _: PersonFactory())
  content = None


class ReviewFactory(ModelFactory):

  class Meta:
    model = all_models.Review

  reviewable = factory.LazyAttribute(lambda _: ProgramFactory())
  notification_type = all_models.Review.NotificationTypes.EMAIL_TYPE


class ProjectFactory(ExternalResourceFactory, TitledFactory):

  class Meta:
    model = all_models.Project


class TechnologyEnvironmentFactory(ExternalResourceFactory, TitledFactory):

  class Meta:
    model = all_models.TechnologyEnvironment


class ImportExportFactory(ModelFactory):

  class Meta:
    model = all_models.ImportExport

  @classmethod
  def _log_event(cls, instance, action="POST"):
    """Stub to disable parent method"""


class BackgroundTaskFactory(ModelFactory):

  class Meta:
    model = all_models.BackgroundTask


class BackgroundOperationFactory(ModelFactory):

  class Meta:
    model = all_models.BackgroundOperation


class MetricFactory(ExternalResourceFactory, TitledFactory):

  class Meta:
    model = all_models.Metric


class ProductGroupFactory(ExternalResourceFactory, TitledFactory):

  class Meta:
    model = all_models.ProductGroup


class CalendarEventFactory(TitledFactory):

  class Meta:
    model = all_models.CalendarEvent


class RevisionFactory(ModelFactory):

  class Meta:
    model = all_models.Revision

  @classmethod
  def _create(cls, target_class, *args, **kwargs):
    """Fix context related_object when audit is created"""
    kwargs["action"] = kwargs.get("action", "created")
    kwargs["modified_by_id"] = kwargs.get(
        "modified_by_id", PersonFactory().id
    )
    kwargs["obj"] = kwargs.get("obj", ControlFactory())
    kwargs["content"] = kwargs.get("content", {}) or kwargs["obj"].log_json()

    event = EventFactory(
        modified_by_id=kwargs["modified_by_id"],
        action="POST",
        resource_id=kwargs["obj"].id,
        resource_type=kwargs["obj"].__class__.__name__,
    )

    rev = target_class(*args, **kwargs)
    rev.event_id = event.id
    db.session.add(rev)
    if getattr(db.session, "single_commit", True):
      db.session.commit()
    return rev


class MaintenanceFactory(ModelFactory):

  class Meta:
    model = all_models.Maintenance

  id = 1  # pylint: disable=invalid-name


class SavedSearchFactory(ModelFactory):

  class Meta:
    model = saved_search.SavedSearch

  name = factory.LazyAttribute(lambda _: random_str(prefix="SavedSearch "))
  object_type = "Assessment"
  user = factory.LazyAttribute(lambda _: PersonFactory())
  filters = ""
  search_type = saved_search.SavedSearch.ADVANCED_SEARCH
  is_visible = True


def get_model_factory(model_name):
  """Get object factory for provided model name"""
  from integration.ggrc_workflows.models import factories as wf_factories
  model_factories = {
      "AccessControlRole": AccessControlRoleFactory,
      "AccessControlList": AccessControlListFactory,
      "AccessGroup": AccessGroupFactory,
      "AccountBalance": AccountBalanceFactory,
      "Assessment": AssessmentFactory,
      "AssessmentTemplate": AssessmentTemplateFactory,
      "Audit": AuditFactory,
      "Automapping": AutomappingFactory,
      "CalendarEvent": CalendarEventFactory,
      "Comment": CommentFactory,
      "ExternalComment": ExternalCommentFactory,
      "Contract": ContractFactory,
      "Control": ControlFactory,
      "Cycle": wf_factories.CycleFactory,
      "CycleTaskGroup": wf_factories.CycleTaskGroupFactory,
      "CycleTaskGroupObjectTask": wf_factories.CycleTaskGroupObjectTaskFactory,
      "DataAsset": DataAssetFactory,
      "Document": DocumentFactory,
      "Evidence": EvidenceFactory,
      "Facility": FacilityFactory,
      "ImportExport": ImportExportFactory,
      "Issue": IssueFactory,
      "IssueTrackerIssue": IssueTrackerIssueFactory,
      "KeyReport": KeyReportFactory,
      "Label": LabelFactory,
      "Maintenance": MaintenanceFactory,
      "Market": MarketFactory,
      "Metric": MetricFactory,
      "Objective": ObjectiveFactory,
      "ObjectLabel": ObjectLabelFactory,
      "OrgGroup": OrgGroupFactory,
      "Option": OptionFactory,
      "Person": PersonFactory,
      "Policy": PolicyFactory,
      "Process": ProcessFactory,
      "Product": ProductFactory,
      "ProductGroup": ProductGroupFactory,
      "Program": ProgramFactory,
      "Project": ProjectFactory,
      "Proposal": ProposalFactory,
      "Regulation": RegulationFactory,
      "Requirement": RequirementFactory,
      "Risk": RiskFactory,
      "Review": ReviewFactory,
      "Revision": RevisionFactory,
      "SavedSearch": SavedSearchFactory,
      "Standard": StandardFactory,
      "System": SystemFactory,
      "TaskGroup": wf_factories.TaskGroupFactory,
      "TaskGroupTask": wf_factories.TaskGroupTaskFactory,
      "TechnologyEnvironment": TechnologyEnvironmentFactory,
      "Threat": ThreatFactory,
      "Vendor": VendorFactory,
      "Workflow": wf_factories.WorkflowFactory,
  }
  return model_factories[model_name]
