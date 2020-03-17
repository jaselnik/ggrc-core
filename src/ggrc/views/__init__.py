# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""ggrc.views
Handle non-RESTful views, e.g. routes which return HTML rather than JSON
"""
# pylint: disable=too-many-lines

import collections
import datetime
import json
import logging

import sqlalchemy
import flask
from werkzeug import exceptions

from ggrc import fulltext, login, models, settings, utils as ggrc_utils, \
    extensions as ggrc_extensions, converters as ggrc_converters
from ggrc.app import app, db
from ggrc.builder import json as builder_json
from ggrc.cache import utils as cache_utils
from ggrc.fulltext import mixin
from ggrc.integrations import integrations_errors, issues
from ggrc.integrations.synchronization_jobs import one_time_back_sync
from ggrc.models import background_task, reflection, revision
from ggrc.models.hooks.issue_tracker import integration_utils
from ggrc.notifications import common
from ggrc.query import views as query_views
from ggrc.rbac import permissions
from ggrc.services import common as services_common, signals
from ggrc.snapshotter import rules, indexer as snapshot_indexer
from ggrc.utils import benchmark, helpers, log_event, revisions
from ggrc.utils import empty_revisions
from ggrc.utils.contributed_objects import CONTRIBUTED_OBJECTS
from ggrc.views import external_mappings  # noqa: F401
from ggrc.views import saved_searches  # noqa: F401
from ggrc.views import converters, cron, filters, notifications, registry, \
    utils, serializers, folder
from ggrc.views.bulk_operations import bulk_operations   # noqa: F401

logger = logging.getLogger(__name__)
REINDEX_CHUNK_SIZE = 100


# Needs to be secured as we are removing @login_required
@app.route("/_background_tasks/propagate_acl", methods=["POST"])
@background_task.queued_task
def propagate_acl(_):
  """Web hook to update revision content."""
  models.hooks.acl.propagation.propagate_all()
  return app.make_response(("success", 200, [("Content-Type", "text/html")]))


@app.route("/_background_tasks/create_missing_revisions", methods=["POST"])
@background_task.queued_task
def create_missing_revisions(_):
  """Web hook to create revisions for new objects."""
  revisions.do_missing_revisions()
  return app.make_response(("success", 200, [("Content-Type", "text/html")]))


@app.route("/_background_tasks/find_empty_revisions", methods=["POST"])
@background_task.queued_task
def find_empty_revisions(_):
  """Web hook to find empty revisions."""
  empty_revisions.find_empty_revisions()
  return app.make_response(("success", 200, [("Content-Type", "text/html")]))


@app.route("/_background_tasks/reindex_snapshots", methods=["POST"])
@background_task.queued_task
def reindex_snapshots(_):
  """Web hook to update the full text search index."""
  logger.info("Updating index for: %s", "Snapshot")
  with benchmark("Create records for %s" % "Snapshot"):
    snapshot_indexer.reindex()
  return app.make_response(("success", 200, [("Content-Type", "text/html")]))


@app.route("/_background_tasks/reindex", methods=["POST"])
@background_task.queued_task
def reindex(_):
  """Web hook to update the full text search index."""
  do_reindex()
  return app.make_response(("success", 200, [("Content-Type", "text/html")]))


@app.route("/_background_tasks/full_reindex", methods=["POST"])
@background_task.queued_task
def full_reindex(_):
  """Web hook to update the full text search index for all models."""
  do_full_reindex()
  return app.make_response(("success", 200, [("Content-Type", "text/html")]))


@app.route("/_background_tasks/compute_attributes", methods=["POST"])
@background_task.queued_task
def compute_attributes(task):
  """Web hook to update the full text search index."""
  with benchmark("Run compute_attributes background task"):
    event_id = task.parameters.get("event_id")
    revision_ids = task.parameters.get("revision_ids")

    if event_id and not revision_ids:
      rows = db.session.query(
          revision.Revision.id
      ).filter_by(event_id=event_id).all()
      revision_ids = [revision_id for revision_id, in rows]
    elif str(revision_ids) == "all_latest":
      revision_ids = "all_latest"
    else:
      revision_ids = list(revision_ids)

    from ggrc.data_platform import computed_attributes
    computed_attributes.compute_attributes(revision_ids)
    return app.make_response(("success", 200, [("Content-Type", "text/html")]))


@app.route("/_background_tasks/indexing", methods=["POST"])
@background_task.queued_task
def bg_update_ft_records(task):
  """Background indexing endpoint"""
  fulltext.listeners.update_ft_records(task.parameters.get("models_ids", {}),
                                       task.parameters.get("chunk_size"))
  db.session.plain_commit()
  return app.make_response(('success', 200, [('Content-Type', 'text/html')]))


@app.route('/_background_tasks/update_audit_issues', methods=['POST'])
@background_task.queued_task
def update_audit_issues(args):
  """Web hook to update the issues associated with an audit."""
  audit_id = args.parameters['audit_id']
  message = args.parameters['message']

  if not audit_id or not message:
    logger.warning(
        'One or more of required parameters (audit_id, message) is empty.')
    return app.make_response((
        'Parameters audit_id and message are required.',
        400, [('Content-Type', 'text/html')]))

  issue_tracker = models.all_models.IssuetrackerIssue
  relationships = models.all_models.Relationship
  query = db.session.query(
      issue_tracker.enabled,
      issue_tracker.issue_id,
      issue_tracker.object_id
  ).join(
      relationships,
      relationships.source_id == issue_tracker.object_id
  ).filter(
      relationships.source_type == 'Assessment',
      relationships.destination_type == 'Audit',
      relationships.destination_id == audit_id
  )
  cli = issues.Client()
  issue_params = {
      'comment': message,
  }
  for enabled, issue_id, assessment_id in query.all():
    if not enabled:
      continue

    try:
      cli.update_issue(issue_id, issue_params)
    except integrations_errors.Error as error:
      logger.error(
          'Unable to update IssueTracker issue ID=%s '
          'for Assessment ID=%s while archiving/unarchiving Audit ID=%s: %s',
          issue_id, assessment_id, audit_id, error)
  return app.make_response(('success', 200, [('Content-Type', 'text/html')]))


@app.route(
    "/_background_tasks/run_children_issues_generation", methods=["POST"]
)
@background_task.queued_task
def run_children_issues_generation(task):
  """Generate IssueTracker issues for objects of child type in parent."""
  try:
    params = getattr(task, "parameters", {})
    parent_type = params.get("parent", {}).get("type")
    parent_id = params.get("parent", {}).get("id")
    child_type = params.get("child_type")

    from ggrc.integrations import issuetracker_bulk_sync
    bulk_creator = issuetracker_bulk_sync.IssueTrackerBulkChildCreator()
    return bulk_creator.sync_issuetracker(parent_type, parent_id, child_type)
  except integrations_errors.Error as error:
    logger.error('Bulk issue generation failed with error: %s', error.message)
    raise exceptions.BadRequest(error.message)


@app.route(
    "/_background_tasks/run_children_issues_updater", methods=["POST"]
)
@background_task.queued_task
def run_children_issues_updater(task):
  """
    Send comments to IssueTracker issues for objects of child type in parent.
  """
  try:
    params = getattr(task, "parameters", {})
    parent_type = params.get("parent", {}).get("type")
    parent_id = params.get("parent", {}).get("id")
    child_type = params.get("child_type")

    from ggrc.integrations import issuetracker_bulk_sync
    bulk_creator = issuetracker_bulk_sync.IssueTrackerAuditChildUpdated()
    return bulk_creator.sync_issuetracker(parent_type, parent_id, child_type)
  except integrations_errors.Error as error:
    logger.error('Sending comments to issues failed with error: %s',
                 error.message)
    raise exceptions.BadRequest(error.message)


@app.route(
    "/_background_tasks/run_issues_generation", methods=["POST"]
)
@background_task.queued_task
def run_issues_generation(task):
  """Generate linked IssueTracker issues for provided objects."""
  try:
    from ggrc.integrations import issuetracker_bulk_sync
    bulk_creator = issuetracker_bulk_sync.IssueTrackerBulkCreator()
    params = getattr(task, "parameters", {})
    (_, errors) = bulk_creator.sync_issuetracker(params)
    if errors is None:
      errors = []
    return bulk_creator.make_response(errors)
  except integrations_errors.Error as error:
    logger.error('Bulk issue generation failed with error: %s', error.message)
    raise exceptions.BadRequest(error.message)


@app.route(
    "/_background_tasks/run_issues_update", methods=["POST"]
)
@background_task.queued_task
def run_issues_update(task):
  """Update linked IssueTracker issues for provided objects."""
  try:
    from ggrc.integrations import issuetracker_bulk_sync
    bulk_updater = issuetracker_bulk_sync.IssueTrackerBulkUpdater()
    params = getattr(task, "parameters", {})
    (_, errors) = bulk_updater.sync_issuetracker(params)
    if errors is None:
      errors = []
    return bulk_updater.make_response(errors)
  except integrations_errors.Error as error:
    logger.error('Bulk issue update failed with error: %s', error.message)
    raise exceptions.BadRequest(error.message)


@app.route(
    "/_background_tasks/background_issues_update", methods=["POST"]
)
@background_task.queued_task
def background_issues_update(task):
  """Update linked IssueTracker issues for provided objects."""
  # pylint: disable=too-many-locals
  try:
    from ggrc.integrations import issuetracker_bulk_sync
    comment_updater = issuetracker_bulk_sync.IssueTrackerCommentUpdater()
    status_comment_updater = issuetracker_bulk_sync.\
        IssueTrackerStatusCommentUpdater()
    bulk_updater = issuetracker_bulk_sync.IssueTrackerBulkUpdater()
    bulk_creator = issuetracker_bulk_sync.IssueTrackerBulkCreator()
    params = getattr(task, "parameters", {})
    revision_ids = params.get("revision_ids")
    mail_data = params.get("mail_data")
    issuetracker_status_info = params.get('issuetracker_status_info')
    update_args = integration_utils.build_updated_objects_args(revision_ids,
                                                               mail_data)
    update_errors = None
    if update_args.get("objects"):
      if "notification_messages" in params:
        update_args["notification_messages"] = params["notification_messages"]

      (_, update_errors) = bulk_updater.sync_issuetracker(update_args)

    create_args = integration_utils.build_created_objects_args(revision_ids,
                                                               mail_data)
    create_errors = None
    if create_args.get("objects"):
      (_, create_errors) = bulk_creator.sync_issuetracker(create_args)

    comment_args = integration_utils.build_comments_args(revision_ids,
                                                         mail_data)
    if comment_args.get("comments"):
      comment_updater.sync_issuetracker(comment_args)

    if issuetracker_status_info:
      status_args = integration_utils.build_status_comments_args(
          mail_data,
          issuetracker_status_info
      )
      status_comment_updater.sync_issuetracker(status_args)

    errors = _merge_errors(create_errors, update_errors)
    return bulk_creator.make_response(errors)
  except integrations_errors.Error as error:
    logger.error('Bulk issue update failed with error: %s', error.message)
    raise exceptions.BadRequest(error.message)


def _merge_errors(create_errors, update_errors):
  """Merge errors for bulk update and create."""
  if create_errors is None:
    errors = [] if update_errors is None else update_errors
  else:
    errors = create_errors.extend(update_errors) \
        if update_errors else create_errors
  return errors


@app.route("/_background_tasks/update_cad_related_objects", methods=["POST"])
@background_task.queued_task
@helpers.without_sqlalchemy_cache
def update_cad_related_objects(task):
  """Update CAD related objects"""
  event = models.all_models.Event.query.filter_by(
      id=task.parameters.get("event_id")
  ).first()
  model = models.get_model(task.parameters.get("model_name"))
  cad_model = models.all_models.CustomAttributeDefinition
  cad = cad_model.query.filter_by(id=event.resource_id).first()
  query = db.session.query(model
                           if task.parameters.get("need_revisions")
                           else model.id)
  objects_count = len(query.all())
  handled_objects = 0
  for chunk in ggrc_utils.generate_query_chunks(query):
    chunk_objects = chunk.all()
    handled_objects += len(chunk_objects)
    logger.info(
        "Updating CAD related objects: %s/%s", handled_objects, objects_count
    )
    if task.parameters.get("need_revisions"):
      for obj in chunk_objects:
        obj.updated_at = datetime.datetime.utcnow()
        obj.modified_by_id = task.parameters.get("modified_by_id")
    else:
      model.bulk_record_update_for([obj_id for obj_id, in chunk_objects])
    log_event.log_event(db.session, cad, event=event)
    db.session.commit()
  return app.make_response(("success", 200, [("Content-Type", "text/html")]))


def start_update_cad_related_objs(event_id, model_name, need_revisions=None):
  """Start a background task to update related objects of CAD."""
  background_task.create_task(
      name="update_cad_related_objects",
      url=flask.url_for(update_cad_related_objects.__name__),
      parameters={
          "event_id": event_id,
          "model_name": model_name,
          "modified_by_id": login.get_current_user_id(),
          "need_revisions": need_revisions,
      },
      method="POST",
      queued_callback=update_cad_related_objects
  )
  db.session.commit()


def start_compute_attributes(revision_ids=None, event_id=None):
  """Start a background task for computed attributes."""
  background_task.create_task(
      name="compute_attributes",
      url=flask.url_for(compute_attributes.__name__),
      parameters={"revision_ids": revision_ids, "event_id": event_id},
      method="POST",
      queued_callback=compute_attributes
  )
  db.session.commit()


def start_update_audit_issues(audit_id, message):
  """Start a background task to update IssueTracker issues related to Audit."""
  background_task.create_task(
      name='update_audit_issues',
      url=flask.url_for(update_audit_issues.__name__),
      parameters={
          'audit_id': audit_id,
          'message': message,
      },
      method=u'POST',
      queued_callback=update_audit_issues,
  )
  db.session.commit()


def start_update_children_issues(parent_type, parent_id, child_type):
  """Start a background task to send comments to IssueTracker issues
     related to Audit child items
  """
  background_task.create_task(
      name="delete_children_issues",
      url=flask.url_for(run_children_issues_updater.__name__),
      queued_callback=run_children_issues_updater,
      parameters={
          "parent": {"type": parent_type, "id": parent_id},
          "child_type": child_type
      },
      operation_type="delete_children_issues",
  )
  db.session.commit()


@app.route("/_background_tasks/generate_wf_tasks_notifications",
           methods=["POST"])
@background_task.queued_task
def generate_wf_tasks_notifications(_):
  """Generate notifications for wf cycle tasks."""
  common.generate_cycle_tasks_notifs()
  return app.make_response(("success", 200, [("Content-Type", "text/html")]))


@app.route("/_background_tasks/onetime_back_sync", methods=["POST"])
@background_task.queued_task
def onetime_back_sync(_):
  """Onetime synchronization of IssueTrackerIssue component_id/hotlist_id."""
  one_time_back_sync.update_synced_issues()
  return app.make_response(('success', 200, [("Content-Type", "text/json")]))


def _remove_dead_reindex_objects(indexed_models):
  """Remove fulltext record entries for deleted objects.

  This function cleans up orphan records for objects that have been deleted
  but that have not removed their records for some reason.
  """
  record = fulltext.mysql.MysqlRecordProperty
  with benchmark("Removing dead index records"):
    for model_name, model in sorted(indexed_models.items()):
      logger.info("Removing dead records for: %s", model_name)
      record.query.filter(
          record.type == model_name,
          ~record.key.in_(db.session.query(model.id))
      ).delete(synchronize_session='fetch')


@helpers.without_sqlalchemy_cache
def do_reindex(with_reindex_snapshots=False, delete=False):
  """Update the full text search index."""

  indexer = fulltext.get_indexer()
  indexed_models = {
      m.__name__: m for m in models.all_models.all_models
      if issubclass(m, mixin.Indexed) and m.REQUIRED_GLOBAL_REINDEX
  }
  people_query = db.session.query(
      models.all_models.Person.id,
      models.all_models.Person.name,
      models.all_models.Person.email
  )
  indexer.cache["people_map"] = {p.id: (p.name, p.email) for p in people_query}
  indexer.cache["ac_role_map"] = dict(db.session.query(
      models.all_models.AccessControlRole.id,
      models.all_models.AccessControlRole.name,
  ))
  _remove_dead_reindex_objects(indexed_models)
  for model_name in sorted(indexed_models.keys()):
    if delete:
      with benchmark("Deleting records for %s" % model_name):
        pass

    logger.info("Updating index for: %s", model_name)
    with benchmark("Create records for %s" % model_name):
      model = indexed_models[model_name]
      ids = [id_[0] for id_ in db.session.query(model.id)]
      ids_count = len(ids)
      handled_ids = 0
      ids_chunks = ggrc_utils.list_chunks(ids, chunk_size=REINDEX_CHUNK_SIZE)
      for ids_chunk in ids_chunks:
        handled_ids += len(ids_chunk)
        logger.info("%s: %s / %s", model.__name__, handled_ids, ids_count)
        model.bulk_record_update_for(ids_chunk)
        db.session.plain_commit()

  if with_reindex_snapshots:
    logger.info("Updating index for: %s", "Snapshot")
    with benchmark("Create records for %s" % "Snapshot"):
      snapshot_indexer.reindex()

  indexer.invalidate_cache()


@helpers.without_sqlalchemy_cache
def do_full_reindex():
  """Update the full text search index for all models."""

  do_reindex(with_reindex_snapshots=True)
  start_compute_attributes(revision_ids="all_latest")


class SetEncoder(json.JSONEncoder):
  """Encoder that can handle python sets"""
  # pylint: disable=method-hidden
  # false positive: https://github.com/PyCQA/pylint/issues/414

  def default(self, obj):  # pylint: disable=arguments-differ
    """If we get a set we first transform it to a list and then just use
       the default encoder"""
    if isinstance(obj, set):
      return list(obj)
    return super(SetEncoder, self).default(obj)


def get_permissions_json():
  """Get all permissions for current user"""
  with benchmark("Get permission JSON"):
    permissions.permissions_for(permissions.get_user())
    return json.dumps(
        getattr(flask.g, '_request_permissions', None),
        cls=SetEncoder
    )


def get_config_json():
  """Get public app config"""
  with benchmark("Get config JSON"):
    public_config = dict(app.config.public_config)
    public_config.update(get_public_config())

    for extension_module in ggrc_extensions.get_extension_modules():
      if hasattr(extension_module, 'get_public_config'):
        public_config.update(
            extension_module.get_public_config(login.get_current_user()))

    return json.dumps(public_config)


def get_public_config():
  """Expose additional permissions-dependent config to client."""
  if settings.INTEGRATION_SERVICE_URL:
    external_service = "/people/suggest"
  else:
    external_service = None

  public_config = {
      "external_help_url": getattr(settings, "EXTERNAL_HELP_URL", ""),
      "external_maintenance_schedules_url":
          getattr(settings, "EXTERNAL_MAINTENANCE_SCHEDULES_URL", ""),
      "external_import_help_url":
          getattr(settings, "EXTERNAL_IMPORT_HELP_URL", ""),
      "snapshotable_objects": list(rules.Types.all),
      "snapshotable_ignored": list(rules.Types.ignore),
      "snapshotable_parents": list(rules.Types.parents),
      "snapshot_related": list(
          rules.Types.parents | rules.Types.scoped | rules.Types.trans_scope),
      "external_services": {"Person": external_service},
      "enable_release_notes": settings.ENABLE_RELEASE_NOTES,
  }

  return public_config


def get_full_user_json():
  """Get the full current user"""
  with benchmark("Get full user JSON"):
    from ggrc.models.person import Person
    current_user = login.get_current_user()
    person = Person.eager_query().filter_by(id=current_user.id).one()
    result = builder_json.publish_representation(
        builder_json.publish(person, (), services_common.inclusion_filter)
    )
    return services_common.as_json(result)


def get_current_user_json():
  """Get current user"""
  with benchmark("Get current user JSON"):
    person = login.get_current_user()
    return services_common.as_json({
        "id": person.id,
        "company": person.company,
        "email": person.email,
        "language": person.language,
        "name": person.name,
        "system_wide_role": person.system_wide_role,
        "profile": person.profile,
    })


def get_access_control_roles_json():
  """Get a list of all access control roles"""
  with benchmark("Get access roles JSON"):
    attrs = models.all_models.AccessControlRole.query.options(
        sqlalchemy.orm.undefer_group("AccessControlRole_complete")
    ).filter(~models.all_models.AccessControlRole.internal).all()
    published = []
    for attr in attrs:
      published.append(builder_json.publish(attr))
    published = builder_json.publish_representation(published)
    return services_common.as_json(published)


def get_internal_roles_json():
  """Get a list of all access control roles"""
  with benchmark("Get access roles JSON"):
    attrs = models.all_models.AccessControlRole.query.options(
        sqlalchemy.orm.undefer_group("AccessControlRole_complete")
    ).filter(
        models.all_models.AccessControlRole.internal == sqlalchemy.true()
    ).all()
    published = []
    for attr in attrs:
      published.append(builder_json.publish(attr))
    published = builder_json.publish_representation(published)
    return services_common.as_json(published)


def get_attributes_json():
  """Get a list of all custom attribute definitions"""
  with benchmark("Get attributes JSON"):
    with benchmark("Get attributes JSON: query"):
      attrs = models.CustomAttributeDefinition.eager_query().filter(
          models.CustomAttributeDefinition.definition_id.is_(None),
      ).all()
    with benchmark("Get attributes JSON: publish"):
      published = []
      for attr in attrs:
        published.append(builder_json.publish(attr))
      published = builder_json.publish_representation(published)
    with benchmark("Get attributes JSON: json"):
      publish_json = services_common.as_json(published)
      return publish_json


def get_import_types(export_only=False):
  """Returns types that can be imported (and exported) or exported only.

  Args:
    export_only (default False): If set to true, return objects that can only
        be exported and not imported.
  Returns:
    A list of models with model_singular and title_plural as keys.
  """
  # pylint: disable=protected-access
  types = ggrc_converters.get_importables_visible
  if export_only:
    types = ggrc_converters.get_exportables
  data = []
  for model in set(types().values()):
    data.append({
        "model_singular": model.__name__,
        "title_plural": model._inflector.title_plural
    })
  data.sort()
  response_json = json.dumps(data)
  return response_json


def get_export_definitions():
  with benchmark("Get export definitions"):
    return get_import_types(export_only=True)


def get_import_definitions():
  with benchmark("Get import definitions"):
    return get_import_types(export_only=False)


def get_all_attributes_json(load_custom_attributes=False):
  """Get a list of all attribute definitions

  This exports all attributes related to a given model, including custom
  attributes and mapping attributes, that are used in csv import and export.
  """
  with benchmark('Loading all attributes JSON'):
    published = {}
    ca_cache = collections.defaultdict(list)
    if load_custom_attributes:
      # get only GCA and exclude external CADs
      # external GCA should be deleted from internal GCA table
      definitions = models.CustomAttributeDefinition.eager_query().group_by(
          models.CustomAttributeDefinition.title,
          models.CustomAttributeDefinition.definition_type,
      )
      for attr in definitions:
        ca_cache[attr.definition_type].append(attr)
    for model in models.all_models.all_models:
      published[model.__name__] = \
          reflection.AttributeInfo.get_attr_definitions_array(
              model, ca_cache=ca_cache)
    return services_common.as_json(published)


@app.context_processor
def base_context():
  """Gets the base context"""
  return dict(
      get_model=models.get_model,
      permissions_json=get_permissions_json,
      permissions=permissions,
      config_json=get_config_json,
      current_user_json=get_current_user_json,
      full_user_json=get_full_user_json,
      attributes_json=get_attributes_json,
      access_control_roles_json=get_access_control_roles_json,
      internal_access_control_roles_json=get_internal_roles_json,
      all_attributes_json=get_all_attributes_json,
      import_definitions=get_import_definitions,
      export_definitions=get_export_definitions,
  )


# Actual HTML-producing routes
#


@app.route("/")
def index():
  """The initial entry point of the app."""

  if not settings.PRODUCTION:
    flask.flash(
        u"""This is not the production instance of the GGRC application.<br>
        Company confidential, sensitive or personally identifiable
        information <b>*MUST NOT*</b> be entered or stored here.<br>
        For any questions, please contact your administrator.""",
        "alert alert-warning"
    )

  logged_in_user = login.get_current_user()
  # for already logged in users redirects to dashboard
  # to avoid useless login screen
  if logged_in_user.is_authenticated():
    return flask.redirect("/dashboard")

  about_url = getattr(settings, "ABOUT_URL", None)
  about_text = getattr(settings, "ABOUT_TEXT", "About GGRC")
  return flask.render_template(
      "welcome/index.haml",
      about_url=about_url,
      about_text=about_text,
  )


@app.route("/dashboard")
@login.login_required
def dashboard():
  """The dashboard page."""
  return flask.render_template(
      "dashboard/index.haml",
      page_type="MY_WORK",
      page_title="My Work",
  )


@app.route("/objectBrowser")
@login.login_required
def object_browser():
  """The object Browser page
  """
  return flask.render_template(
      "dashboard/index.haml",
      page_type="ALL_OBJECTS",
      page_title="All Objects",
  )


@app.route("/admin/reindex_snapshots", methods=["POST"])
@ggrc_utils.deprecated_endpoint(description=(
    "Endpoint is deprecated. Please consider using '/admin/reindex' instead."
))
@login.login_required
@login.admin_required
def admin_reindex_snapshots():
  """Calls a webhook that reindexes indexable objects
  """
  bg_task = background_task.create_task(
      name="reindex_snapshots",
      url=flask.url_for(reindex_snapshots.__name__),
      queued_callback=reindex_snapshots,
  )
  db.session.commit()
  return bg_task.make_response(
      app.make_response(("scheduled %s" % bg_task.name, 200,
                         [('Content-Type', 'text/html')])))


@app.route("/admin/reindex", methods=["POST"])
@login.login_required
@login.admin_required
def admin_reindex():
  """Calls a webhook that reindexes indexable objects
  """
  bg_task = background_task.create_task(
      name="reindex",
      url=flask.url_for(reindex.__name__),
      queued_callback=reindex,
  )
  db.session.commit()
  return bg_task.make_response(
      app.make_response(("scheduled %s" % bg_task.name, 200,
                         [('Content-Type', 'text/html')])))


@app.route("/admin/full_reindex", methods=["POST"])
@ggrc_utils.deprecated_endpoint(description=(
    "Endpoint is deprecated. Please consider using '/admin/reindex' instead."
))
@login.login_required
@login.admin_required
def admin_full_reindex():
  """Calls a webhook that reindexes all indexable objects
  """
  bg_task = background_task.create_task(
      name="full_reindex",
      url=flask.url_for(full_reindex.__name__),
      queued_callback=full_reindex
  )
  db.session.commit()
  return bg_task.make_response(
      app.make_response(("scheduled %s" % bg_task.name, 200,
                         [('Content-Type', 'text/html')])))


@app.route("/admin/compute_attributes", methods=["POST"])
@login.login_required
@login.admin_required
def send_event_job():
  """Trigger background task on every event for computed attributes."""
  with benchmark("POST /admin/compute_attributes"):
    if flask.request.data:
      revision_ids = flask.request.get_json().get("revision_ids", [])
    else:
      revision_ids = "all_latest"
    start_compute_attributes(revision_ids=revision_ids)
    return app.make_response(("success", 200, [("Content-Type", "text/html")]))


@app.route("/admin/propagate_acl", methods=["POST"])
@login.login_required
@login.admin_required
def admin_propagate_acl():
  """Propagates all ACL entries"""
  admins = getattr(settings, "BOOTSTRAP_ADMIN_USERS", [])
  if login.get_current_user().email not in admins:
    raise exceptions.Forbidden()

  bg_task = background_task.create_task(
      name="propagate_acl",
      url=flask.url_for(propagate_acl.__name__),
      queued_callback=propagate_acl,
  )
  db.session.commit()
  return bg_task.make_response(
      app.make_response(("scheduled %s" % bg_task.name, 200,
                         [('Content-Type', 'text/html')])))


@app.route("/admin/create_missing_revisions", methods=["POST"])
@login.login_required
@login.admin_required
def admin_create_missing_revisions():
  """Create revisions for new objects"""
  admins = getattr(settings, "BOOTSTRAP_ADMIN_USERS", [])
  if login.get_current_user().email not in admins:
    raise exceptions.Forbidden()

  bg_task = background_task.create_task(
      name="create_missing_revisions",
      url=flask.url_for(create_missing_revisions.__name__),
      queued_callback=create_missing_revisions,
  )
  db.session.commit()
  return bg_task.make_response(
      app.make_response(("scheduled %s" % bg_task.name, 200,
                        [('Content-Type', 'text/html')])))


@app.route("/admin/find_empty_revisions", methods=["POST"])
@login.login_required
@login.admin_required
def admin_find_empty_revisions():
  """Process all revisions and find empty."""
  bg_task = background_task.create_task(
      name="find_empty_revisions",
      url=flask.url_for(find_empty_revisions.__name__),
      queued_callback=find_empty_revisions,
  )
  db.session.commit()
  return bg_task.make_response(
      app.make_response(("scheduled %s" % bg_task.name, 200,
                        [('Content-Type', 'text/html')])))


@app.route("/admin/onetime_back_sync", methods=["POST"])
@login.login_required
@login.admin_required
def admin_onetime_back_sync():
  """Back sync for IssuetrackerIssues"""
  bg_task = background_task.create_task(
      name="onetime_back_sync",
      url=flask.url_for(onetime_back_sync.__name__),
      queued_callback=onetime_back_sync,
  )
  db.session.commit()
  return bg_task.task_scheduled_response()


@app.route("/admin")
@login.login_required
@login.admin_required
def admin():
  """The admin dashboard page
  """
  return flask.render_template("admin/index.haml")


@app.route("/assessments_view")
@login.login_required
def assessments_view():
  """The clutter-free list of all Person's Assessments"""
  return flask.render_template("assessments_view/index.haml")


@app.route(
    "/background_task_status/<object_type>/<object_id>",
    methods=['GET']
)
@login.login_required
def get_background_task_status(object_type, object_id):
  """Gets the status of a background task which was created for object."""
  bg_task = models.BackgroundTask
  bg_operation = models.BackgroundOperation
  task = bg_task.query.join(
      bg_operation,
      bg_operation.bg_task_id == bg_task.id
  ).filter(
      bg_operation.object_type == object_type,
      bg_operation.object_id == object_id,
  ).order_by(
      bg_task.created_at.desc()
  ).first()

  if task and task.bg_operation:
    body = {
        "status": task.status,
        "operation": task.bg_operation.bg_operation_type.name,
        "errors": task.get_content().get("errors", []),
    }
    response = app.make_response(
        (json.dumps(body), 200, [("Content-Type", "application/json")])
    )
  else:
    response = app.make_response(
        ("", 404, [("Content-Type", "application/json")])
    )
  return response


def contributed_object_views():
  """Contributed object views"""
  return [registry.object_view(obj) for obj in CONTRIBUTED_OBJECTS]


def all_object_views():
  """Gets all object views defined in the application"""
  views = contributed_object_views()

  for extension_module in ggrc_extensions.get_extension_modules():
    contributions = getattr(extension_module, "contributed_object_views", None)
    if contributions:
      if callable(contributions):
        contributions = contributions()
      views.extend(contributions)

  return views


def init_extra_views(app_):
  """Init any extra views needed by the app

  This should be used for any views that might use extension modules.
  """
  filters.init_filter_views()
  converters.init_converter_views()
  cron.init_cron_views(app_)
  notifications.init_notification_views(app_)
  query_views.init_query_views(app_)
  query_views.init_clone_views(app_)
  folder.init_folder_views(app_)


def init_all_views(app_):
  """Inits all views defined in the core module and submodules"""
  for entry in all_object_views():
    entry.service_class.add_to(
        app_,
        '/{0}'.format(entry.url),
        entry.model_class,
        decorators=(login.login_required,)
    )

  init_extra_views(app_)
  for extension_module in ggrc_extensions.get_extension_modules():
    ext_extra_views = getattr(extension_module, "init_extra_views", None)
    if ext_extra_views:
      ext_extra_views(app_)


@app.route("/permissions")
@login.login_required
def user_permissions():
  """Permissions object for the currently logged in user"""
  return get_permissions_json()


@app.route("/api/document/documents_exist", methods=["POST"])
@login.login_required
def is_document_exists():
  """Check if documents with gdrive_ids are exists"""
  utils.DocumentEndpoint.validate_doc_request(flask.request.json)
  ids = flask.request.json["gdrive_ids"]
  result_set = db.session.query(
      models.all_models.Document.id,
      models.all_models.Document.gdrive_id
  ).filter(
      models.all_models.Document.gdrive_id.in_(ids)
  )
  response = utils.DocumentEndpoint.build_doc_exists_response(
      flask.request.json,
      result_set
  )
  return flask.Response(json.dumps(response), mimetype='application/json')


@app.route("/api/document/make_admin", methods=["POST"])
@login.login_required
def make_document_admin():
  """Add current user as document admin"""
  utils.DocumentEndpoint.validate_doc_request(flask.request.json)
  ids = flask.request.json["gdrive_ids"]
  docs = models.all_models.Document.query.filter(
      models.all_models.Document.gdrive_id.in_(ids))
  for doc in docs:
    doc.add_admin_role()
  db.session.commit()
  cache_utils.clear_permission_cache()
  response = utils.DocumentEndpoint.build_make_admin_response(
      flask.request.json,
      docs
  )
  return flask.Response(json.dumps(response), mimetype='application/json')


@app.route("/generate_children_issues", methods=["POST"])
@login.login_required
def generate_children_issues():
  """Generate linked issuetracker issues for children objects.

  This endpoint is used to create tickets for all specific type instances
  in scope of parent. For example it allows to create tickets for all
  Assessments in some Audit.
  """
  validate_child_bulk_gen_data(flask.request.json)
  bg_task = background_task.create_task(
      name="generate_children_issues",
      url=flask.url_for(run_children_issues_generation.__name__),
      queued_callback=run_children_issues_generation,
      parameters=flask.request.json,
      operation_type="generate_children_issues",
  )
  db.session.commit()
  return bg_task.task_scheduled_response()


@app.route("/generate_issues", methods=["POST"])
@login.login_required
def generate_issues():
  """Bulk generate linked issuetracker issues for provided objects.

  This endpoint creates issuetracker tickets for all provided objects
  (if such tickets haven't been created before).
  """
  validate_bulk_sync_data(flask.request.json)
  bg_task = background_task.create_task(
      name="generate_issues",
      url=flask.url_for(run_issues_generation.__name__),
      queued_callback=run_issues_generation,
      parameters=flask.request.json,
  )
  db.session.commit()
  return bg_task.task_scheduled_response()


@app.route("/update_issues", methods=["POST"])
@login.login_required
def update_issues():
  """Bulk update linked issuetracker issues for provided objects.

  This endpoint update issuetracker tickets for all provided objects
  to the current state in the app.
  """
  validate_bulk_sync_data(flask.request.json)
  bg_task = background_task.create_task(
      name="update_issues",
      url=flask.url_for(run_issues_update.__name__),
      queued_callback=run_issues_update,
      parameters=flask.request.json,
  )
  db.session.commit()
  return bg_task.task_scheduled_response()


def background_update_issues(parameters=None):
  """Bulk update linked issuetracker issues for provided objects.

  This function update issuetracker tickets for all provided objects
  to the current state in the app. Can be called inside import
  task.
  """
  method = "POST"
  bg_task = background_task.create_task(
      name="update_issues",
      url="/_background_tasks/background_issues_update",
      queued_callback=background_issues_update,
      parameters=parameters,
      method=method,
  )
  db.session.commit()
  return bg_task.task_scheduled_response()


def validate_child_bulk_gen_data(json_data):
  """Check correctness of input data for bulk child sync."""
  if not json_data or not isinstance(json_data, dict):
    raise exceptions.BadRequest("No data provided.")

  parent_type = json_data.get("parent", {}).get("type")
  parent_id = json_data.get("parent", {}).get("id")
  child_type = json_data.get("child_type")

  if not all((parent_id, parent_type, child_type)):
    raise exceptions.BadRequest("Required parameters is not provided.")

  parent = models.get_model(parent_type)
  child = models.get_model(child_type)
  from ggrc.models.mixins import issue_tracker
  if not issubclass(parent, issue_tracker.IssueTracked) or \
     not issubclass(child, issue_tracker.IssueTracked):
    raise exceptions.BadRequest("Provided model is not IssueTracked.")


def validate_bulk_sync_data(json_data):
  """Check correctness of input data for bulk child sync."""
  if not json_data or not isinstance(json_data, dict):
    raise exceptions.BadRequest("No data provided.")

  objects = json_data.get("objects", {})
  if not objects or not isinstance(objects, list):
    raise exceptions.BadRequest("Objects list is not provided.")

  for obj in objects:
    if not obj.get("id"):
      raise exceptions.BadRequest("Object id is not provided.")

    model = models.get_model(obj.get("type"))
    from ggrc.models.mixins import issue_tracker
    if not issubclass(model, issue_tracker.IssueTracked):
      raise exceptions.BadRequest("Provided object is not IssueTracked.")


@app.route("/admin/generate_wf_tasks_notifications", methods=["POST"])
@login.login_required
@login.admin_required
def generate_wf_tasks_notifs():
  """Generate notifications for updated wf cycle tasks."""
  bg_task = background_task.create_task(
      name="generate_wf_tasks_notifications",
      url=flask.url_for(generate_wf_tasks_notifications.__name__),
      queued_callback=generate_wf_tasks_notifications,
  )
  db.session.commit()
  return bg_task.make_response(
      app.make_response(("scheduled %s" % bg_task.name, 200,
                        [('Content-Type', 'text/html')])))


class UnmapObjectsView(flask.views.MethodView):
  """View for unmapping objects by deletion of relationships."""

  # pylint: disable=arguments-differ
  @classmethod
  def as_view(cls, *args, **kwargs):
    """Override as_view to decorate with "login_required"."""
    view = super(UnmapObjectsView, cls).as_view(*args, **kwargs)
    return login.login_required(view)

  def dispatch_request(self, *args, **kwargs):
    """Handle validation errors."""
    if not login.is_external_app_user():
      raise exceptions.Forbidden()

    try:
      return super(UnmapObjectsView, self).dispatch_request(*args, **kwargs)
    except ValueError as exc:
      raise exceptions.BadRequest(exc.message)

  @property
  def request(self):
    """Property to access request with "self.request"."""
    return flask.request

  def post(self):
    """Unmap objects by deleting relationship."""
    serializer = serializers.RelationshipSerializer(self.request.json)
    serializer.clean()

    deleted = 0

    for relationship in serializer.as_query():
      self.delete_relationship(relationship)
      deleted += 1

    db.session.commit()

    return flask.jsonify({"count": deleted})

  def delete_relationship(self, relationship):
    """Send post deletion signals."""
    db.session.delete(relationship)

    signals.Restful.model_deleted.send(
        models.Relationship, obj=relationship, service=self)
    modified_objects = services_common.get_modified_objects(db.session)
    event = log_event.log_event(db.session, relationship)
    cache_utils.update_memcache_before_commit(
        self.request, modified_objects,
        services_common.CACHE_EXPIRY_COLLECTION)

    db.session.flush()

    services_common.update_snapshot_index(modified_objects)
    cache_utils.update_memcache_after_commit(flask.request)
    signals.Restful.model_deleted_after_commit.send(
        models.Relationship, obj=relationship, service=self, event=event)
    services_common.send_event_job(event)


app.add_url_rule('/api/relationships/unmap',
                 view_func=UnmapObjectsView.as_view('unmap_objects'))
