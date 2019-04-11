# Copyright (C) 2019 Google Inc.
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
from contextlib import contextmanager

import factory

from ggrc import db
from ggrc.models import all_models

from ggrc.access_control import roleable

from integration.ggrc.models.model_factory import ModelFactory


def random_str(length=8, prefix="", chars=None):
  chars = chars or string.ascii_uppercase + string.digits + "  _.-"
  return prefix + "".join(random.choice(chars) for _ in range(length))


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

  _value_iterator = iter(xrange(sys.maxint))

  @classmethod
  def next(cls):
    return next(cls._value_iterator)


class TitledFactory(ModelFactory):
  title = factory.LazyAttribute(lambda m: random_str(prefix='title '))


class WithACLandCAFactory(ModelFactory):
  """Factory class to create object with ACL and CA in one step"""

  @classmethod
  def _create(cls, target_class, *args, **kwargs):
    """Create instance of model"""
    acls = []
    if "access_control_list_" in kwargs:
      acls = kwargs.pop("access_control_list_")
    cavs = []
    if "custom_attribute_values_" in kwargs:
      cavs = kwargs.pop("custom_attribute_values_")

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
    if cavs and isinstance(instance, all_models.mixins.CustomAttributable):
      for cav in cavs:
        db.session.add(all_models.CustomAttributeValue(
            attributable=instance,
            attribute_value=cav.get("attribute_value"),
            attribute_object_id=cav.get("attribute_object_id"),
            custom_attribute_id=cav.get("custom_attribute_id"),
        ))

    if isinstance(instance, all_models.CustomAttributeValue):
      cls._log_event(instance.attributable)
    if hasattr(instance, "log_json"):
      cls._log_event(instance)
    if getattr(db.session, "single_commit", True):
      db.session.commit()
    return instance


class CustomAttributeDefinitionFactory(TitledFactory):

  class Meta:
    model = all_models.CustomAttributeDefinition

  definition_type = None
  definition_id = None
  attribute_type = "Text"
  multi_choice_options = None


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


class ControlFactory(TitledFactory):

  class Meta:
    model = all_models.Control

  assertions = factory.LazyAttribute(lambda _: '["{}"]'.format(random_str()))
  directive = factory.LazyAttribute(lambda m: RegulationFactory())
  external_id = factory.LazyAttribute(lambda m:
                                      SynchronizableExternalId.next())
  external_slug = factory.LazyAttribute(lambda m: random_str())
  review_status = all_models.Review.STATES.UNREVIEWED
  review_status_display_name = "some status"


class IssueFactory(TitledFactory):

  class Meta:
    model = all_models.Issue


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


class ContractFactory(TitledFactory):

  class Meta:
    model = all_models.Contract


class EventFactory(ModelFactory):

  class Meta:
    model = all_models.Event
  revisions = []


class RelationshipFactory(ModelFactory):

  class Meta:
    model = all_models.Relationship
  source = None
  destination = None

  @classmethod
  def randomize(cls, *args):
    """Create a relationship with randomly shuffled source and destination."""
    obj1, obj2 = random.sample(args, 2)
    return cls(source=obj1, destination=obj2)


class PersonFactory(ModelFactory):

  class Meta:
    model = all_models.Person

  email = factory.LazyAttribute(
      lambda _: random_str(chars=string.ascii_letters) + "@example.com"
  )


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


class ObjectiveFactory(TitledFactory):

  class Meta:
    model = all_models.Objective


class OptionFactory(TitledFactory):

  class Meta:
    model = all_models.Option


class RegulationFactory(TitledFactory):

  class Meta:
    model = all_models.Regulation


class OrgGroupFactory(TitledFactory):

  class Meta:
    model = all_models.OrgGroup


class SystemFactory(TitledFactory):

  class Meta:
    model = all_models.System


class KeyReportFactory(TitledFactory):

  class Meta:
    model = all_models.KeyReport


class AccountBalanceFactory(TitledFactory):

  class Meta:
    model = all_models.AccountBalance


class ProcessFactory(TitledFactory):

  class Meta:
    model = all_models.Process


class PolicyFactory(TitledFactory):

  class Meta:
    model = all_models.Policy


class MarketFactory(TitledFactory):

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


class AccessGroupFactory(TitledFactory):
  """Access Group factory class"""

  class Meta:
    model = all_models.AccessGroup


class DataAssetFactory(TitledFactory):
  """DataAsset factory class"""

  class Meta:
    model = all_models.DataAsset


class FacilityFactory(TitledFactory):
  """Facility factory class"""

  class Meta:
    model = all_models.Facility


class ObjectPersonFactory(ModelFactory):
  """ObjectPerson factory class"""

  class Meta:
    model = all_models.ObjectPerson


class ProductFactory(TitledFactory):
  """Product factory class"""

  class Meta:
    model = all_models.Product


class RequirementFactory(TitledFactory):
  """Requirement factory class"""

  class Meta:
    model = all_models.Requirement


class StandardFactory(TitledFactory):
  """Standard factory class"""

  class Meta:
    model = all_models.Standard

  description = factory.LazyAttribute(lambda _: random_str(length=100))


class VendorFactory(TitledFactory):
  """Vendor factory class"""

  class Meta:
    model = all_models.Vendor


class RiskFactory(TitledFactory):
  """Risk factory class"""

  class Meta:
    model = all_models.Risk

  risk_type = "Some Type"
  description = factory.LazyAttribute(lambda _: random_str(length=100))

  external_id = factory.LazyAttribute(lambda m:
                                      SynchronizableExternalId.next())
  external_slug = factory.LazyAttribute(lambda m: random_str())


class ThreatFactory(TitledFactory):
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


class RiskAssessmentFactory(TitledFactory):

  class Meta:
    model = all_models.RiskAssessment

  status = "Draft"
  program = factory.LazyAttribute(lambda _: ProgramFactory())


class ProjectFactory(TitledFactory):

  class Meta:
    model = all_models.Project


class TechnologyEnvironmentFactory(TitledFactory):

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


class MetricFactory(TitledFactory):

  class Meta:
    model = all_models.Metric


class ProductGroupFactory(TitledFactory):

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
    kwargs["content"] = kwargs.get("content", {})
    kwargs["modified_by_id"] = kwargs.get(
        "modified_by_id", PersonFactory().id
    )
    kwargs["obj"] = kwargs.get("obj", ControlFactory())

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
      "RiskAssessment": RiskAssessmentFactory,
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
