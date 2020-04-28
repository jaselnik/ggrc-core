# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Bootstrap for ggrc db."""
import threading
import flask
from flask_sqlalchemy import SQLAlchemy

from ggrc.utils import benchmark


class CommitHooksEnableFlag(threading.local):
  """Special Semaphore construction that allows to run hook later."""

  def __init__(self, *args, **kwargs):
    super(CommitHooksEnableFlag, self).__init__(*args, **kwargs)
    self._flag = True

  def enable(self):
    self._flag = True

  def disable(self):
    self._flag = False

  def __bool__(self):
    return self._flag

  __nonzero__ = __bool__


def get_db():  # noqa
  """Get modified db object."""
  database = SQLAlchemy()

  class String(database.String):
    """Simple subclass of sqlalchemy.orm.String which provides a default
    length for `String` types to satisfy MySQL
    """
    # pylint: disable=too-few-public-methods
    # this class is just to set the default string length and is not meant to
    # do anything else, so it does not need any other public methods.

    def __init__(self, length=None, *args, **kwargs):
      # TODO: Check for MySQL and only apply when needed
      if length is None:
        length = 250
      super(String, self).__init__(length, *args, **kwargs)

  database.String = String

  database.session.plain_commit = database.session.commit

  database.session.commit_hooks_enable_flag = CommitHooksEnableFlag()

  def pre_commit_hooks():
    """All pre commit hooks handler."""
    with benchmark("pre commit hooks"):
      if not database.session.commit_hooks_enable_flag:
        return
      database.session.flush()
      if hasattr(database.session, "reindex_set"):
        database.session.reindex_set.indexing_hook()

  def post_commit_hooks():
    """All post commit hooks handler."""
    with benchmark("post commit hooks"):
      if not database.session.commit_hooks_enable_flag:
        return
      # delete flask caches in order to avoid
      # using cached instances after commit
      if hasattr(flask.g, "user_cache"):
        del flask.g.user_cache
      if hasattr(flask.g, "user_creator_roles_cache"):
        del flask.g.user_creator_roles_cache
      from ggrc.models.hooks import acl
      acl.after_commit()

  database.session.post_commit_hooks = post_commit_hooks
  database.session.pre_commit_hooks = pre_commit_hooks

  def hooked_commit(*args, **kwargs):
    """Commit override function.

    This function is meant for a single after commit hook that should only be
    used for ACL propagation.
    """
    database.session.pre_commit_hooks()
    with benchmark("plain commit"):
      database.session.plain_commit(*args, **kwargs)
    database.session.post_commit_hooks()

  database.session.commit = hooked_commit

  return database
