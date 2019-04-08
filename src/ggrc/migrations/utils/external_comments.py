# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module contains utils for external comments."""

import sqlalchemy as sa

from ggrc.migrations import utils


def _get_comments_ids_by_obj_type(connection, obj_type, is_external=False):
  """Returns comments ids by object type.

  Args:
    connection: An instance of SQLAlchemy connection.
    obj_type: String representation of object type.
    is_external: Boolean indicator for ExternalComment/Comment.
  """
  comment_type = 'ExternalComment' if is_external else 'Comment'
  result = connection.execute(
      sa.text("""
          SELECT source_id
          FROM relationships
          WHERE source_type = :comment_type AND
          destination_type = :obj_type

          UNION

          SELECT destination_id
          FROM relationships
          WHERE source_type = :obj_type AND
          destination_type = :comment_type
          """),
      comment_type=comment_type,
      obj_type=obj_type).fetchall()

  return result


def _get_comments_relationships_ids(connection, obj_type):
  """Returns comments relationship ids by object type.

  Args:
    connection: An instance of SQLAlchemy connection.
    obj_type: String representation of object type.
  """
  old_rels = connection.execute(
      sa.text("""
          SELECT id, source_type, source_id,
          destination_type, destination_id
          FROM relationships
          WHERE (source_type = 'Comment' AND destination_type = :obj_type) OR
                (destination_type = 'Comment' AND source_type = :obj_type)
      """),
      obj_type=obj_type).fetchall()

  return old_rels


def _move_to_external_comments(connection, obj_type):
  """Moves comments for certain object type to external comments table.

  Args:
    connection: An instance of SQLAlchemy connection.
    obj_type: String representation of object type.
  """
  connection.execute(
      sa.text("""
          INSERT INTO external_comments(
              id, description, assignee_type, created_at, updated_at,
              modified_by_id
          )
          SELECT id, description, assignee_type, created_at, updated_at,
                modified_by_id
          FROM
          (
              SELECT c.id, c.description, c.assignee_type,
                    c.created_at, c.updated_at, c.modified_by_id
              FROM comments c
              JOIN relationships r ON r.source_type = 'Comment' AND
                  r.source_id = c.id AND
                  r.destination_type = :obj_type

              UNION

              SELECT c.id, c.description, c.assignee_type,
                    c.created_at, c.updated_at, c.modified_by_id
              FROM comments c
              JOIN relationships r ON r.destination_type = 'Comment' AND
                  r.destination_id = c.id AND
                  r.source_type = :obj_type
          ) tmp;
      """),
      obj_type=obj_type
  )


def _delete_relationships_comments(connection, obj_type):
  """Removes comments relationships.

  Args:
    connection: An instance of SQLAlchemy connection.
    obj_type: String representation of object type.
  """
  old_rels = _get_comments_relationships_ids(connection, obj_type)

  if old_rels:
    old_rel_ids = [rel.id for rel in old_rels]
    connection.execute(
        sa.text("""
            DELETE FROM relationships
            WHERE id IN :relationship_ids
        """),
        relationship_ids=old_rel_ids,
    )
    utils.add_to_objects_without_revisions_bulk(
        connection,
        old_rel_ids,
        "Relationship",
        action="deleted",
    )


def _delete_control_comments(connection, obj_type):
  """Removes comments for certain object type.

  Args:
    connection: An instance of SQLAlchemy connection.
    obj_type: String representation of object type.
  """
  connection.execute(
      sa.text("""
          DELETE comments
          FROM comments
          JOIN relationships r ON r.source_type = 'Comment' AND
              r.source_id = comments.id AND
              r.destination_type = :obj_type
          """),
      obj_type=obj_type)
  connection.execute(
      sa.text("""
          DELETE comments
          FROM comments
          JOIN relationships r ON r.destination_type = 'Comment' AND
               r.destination_id = comments.id AND
               r.source_type = :obj_type
          """),
      obj_type=obj_type)


def _update_comment_relationships(connection, obj_type):
  """Replaces 'Comment' object_type with 'ExternalComment' for relationships.

  Args:
    connection: An instance of SQLAlchemy connection.
    obj_type: String representation of object type.
  """
  old_rels = _get_comments_relationships_ids(connection, obj_type)

  if old_rels:
    migrator_id = utils.get_migration_user_id(connection)
    for _, s_type, s_id, d_type, d_id in old_rels:
      connection.execute(
          sa.text("""
              INSERT INTO relationships(
                source_type, source_id, destination_type, destination_id,
                modified_by_id, created_at, updated_at, is_external
              )
              VALUES(
                :source_type, :source_id, :dest_type, :dest_id,
                :modified_by_id, NOW(), NOW(), TRUE
              );
          """),
          source_type='ExternalComment' if s_type == 'Comment' else s_type,
          source_id=s_id,
          dest_type='ExternalComment' if d_type == 'Comment' else d_type,
          dest_id=d_id,
          modified_by_id=migrator_id,
      )

    new_rels = connection.execute(
        sa.text("""
            SELECT id
            FROM relationships
            WHERE (source_type = 'ExternalComment' AND
                   destination_type = :obj_type) OR
                  (destination_type = 'ExternalComment' AND
                   source_type = :obj_type)
        """),
        obj_type=obj_type).fetchall()

    new_rel_ids = [rel.id for rel in new_rels]
    utils.add_to_objects_without_revisions_bulk(
        connection,
        new_rel_ids,
        "Relationship",
    )


def _create_comments_revisions(connection, obj_type):
  """Creates delete revisions for comments.

  Args:
    connection: An instance of SQLAlchemy connection.
    obj_type: String representation of object type.
  """
  result = _get_comments_ids_by_obj_type(connection, obj_type)

  if result:
    result = [row[0] for row in result]
    utils.add_to_objects_without_revisions_bulk(
        connection,
        result,
        "Comment",
        action="deleted",
    )


def _create_external_comments_revs(connection, obj_type):
  """Creates revisions for external comments.

  Args:
    connection: An instance of SQLAlchemy connection.
    obj_type: String representation of object type.
  """
  result = _get_comments_ids_by_obj_type(
      connection, obj_type, is_external=True)

  if result:
    result = [row[0] for row in result]
    utils.add_to_objects_without_revisions_bulk(
        connection,
        result,
        "ExternalComment"
    )


def _update_comments_acl(connection, obj_type):
  """Updates object_type in ACR and ACL for ExternalComments.

  Args:
    connection: An instance of SQLAlchemy connection.
    obj_type: String representation of object type.
  """
  ext_admin_id = connection.execute(
      sa.text("""
          SELECT id FROM access_control_roles
          WHERE name = 'Admin' AND object_type = 'ExternalComment'
      """)
  ).fetchone()[0]

  result = _get_comments_ids_by_obj_type(
      connection, obj_type, is_external=True)

  if result:
    obj_ids = [row[0] for row in result]
    connection.execute(
        sa.text("""
            UPDATE access_control_list
            SET object_type = 'ExternalComment',
                ac_role_id = :acr_id
            WHERE object_type = 'Comment' AND
                  object_id IN :obj_ids AND
                  parent_id IS NULL;
        """),
        obj_ids=obj_ids,
        acr_id=ext_admin_id
    )


def move_to_external_comments(connection, obj_type):
  """Moves comments to external comments for object type.

  Args:
    connection: An instance of SQLAlchemy connection.
    obj_type: String representation of object type.
  """
  _move_to_external_comments(connection, obj_type)
  _update_comment_relationships(connection, obj_type)
  _create_comments_revisions(connection, obj_type)
  _create_external_comments_revs(connection, obj_type)
  _update_comments_acl(connection, obj_type)
  _delete_control_comments(connection, obj_type)
  _delete_relationships_comments(connection, obj_type)
