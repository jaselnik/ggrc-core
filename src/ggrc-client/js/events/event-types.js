/*
    Copyright (C) 2020 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

/**
 * Fired after instance refresh.
 *
 * @event refreshed
 * @type {object}
 * @property {string} type - Event name.
 */
const REFRESHED = {
  type: 'refreshed',
};

/**
 *
 * @event refreshRelated
 * @type {object}
 * @property {string} type - Event name.
 * @property {string} model -  Model name.
 */
const REFRESH_RELATED = {
  type: 'refreshRelated',
};

/**
 *
 * @event addRelated
 * @type {object}
 * @property {string} type - Event name.
 * @property {string} model -  Model name.
 */
const ADD_RELATED = {
  type: 'addRelated',
};

/**
 *
 * @event relatedRefreshed
 * @type {object}
 * @property {string} type - Event name.
 * @property {string} model -  Model name.
 */
const RELATED_REFRESHED = {
  type: 'relatedRefreshed',
};

/**
 * @event relatedAdded
 * @type {object}
 * @property {string} type - Event name.
 * @property {string} model -  Model name.
 */
const RELATED_ADDED = {
  type: 'relatedAdded',
};

/**
 *
 * @event rolesConflict
 * @type {object}
 * @property {string} type - Event name.
 * @property {string} groupId - Role ID.
 */
const ROLES_CONFLICT = {
  type: 'rolesConflict',
};

/**
 * Switch to tab with validation error
 * @event switchToErrorPanel
 * @type {object}
 */
const SWITCH_TO_ERROR_PANEL = {
  type: 'switchToErrorPanel',
};

/**
 * Scroll to validation error field and lint it
 * @event showInvalidField
 * @type {object}
 */
const SHOW_INVALID_FIELD = {
  type: 'showInvalidField',
};

/**
 * Set id number of tab with validation error
 * @event validationError
 * @type {object}
 */
const VALIDATION_ERROR = {
  type: 'validationError',
};

/**
 *
 * @event destinationUnmapped
 * @type {object}
 * @property {string} type - Event name.
 */
const DESTINATION_UNMAPPED = {
  type: 'destinationUnmapped',
};

/**
 * Notifies that proposal was created
 * @event proposalCreated
 * @type {object}
 * @property {string} type - Event name.
 */
const PROPOSAL_CREATED = {
  type: 'proposalCreated',
};

/**
 * Refreshes diff of proposals
 * @event refreshProposalDiff
 * @type {object}
 * @property {string} type - Event name.
 */
const REFRESH_PROPOSAL_DIFF = {
  type: 'refreshProposalDiff',
};

/**
 * Navigate to info-pane's tab
 * @event navigateToTab
 * @type {object}
 * @property {string} type - Event name.
 * @property {string} tabId - id of tab.
 */
const NAVIGATE_TO_TAB = {
  type: 'navigateToTab',
};

/**
 * Refreshes comments of instance
 * @event refreshProposalDiff
 * @type {object}
 * @property {string} type - Event name.
 */
const REFRESH_COMMENTS = {
  type: 'refreshComments',
};

/**
 * Notifies that related items are loaded
 * @event RELATED_ITEMS_LOADED
 * @type {object}
 * @property {string} type - Event name.
 */
const RELATED_ITEMS_LOADED = {
  type: 'RELATED_ITEMS_LOADED',
};

/**
 * Notifies that new comment created and sends its instance
 * @event COMMENT_CREATED
 * @type {object}
 * @property {string} type - Event name.
 * @property {object} comment - Created comment.
 */
const COMMENT_CREATED = {
  type: 'COMMENT_CREATED',
};

/**
 * Notifies that new objects are about to map to the instance
 * @event beforeMapping
 * @type {object}
 * @property {string} type - Event name.
 * @property {string} destinationType - Type of mapped object.
 */
const BEFORE_MAPPING = {
  type: 'beforeMapping',
};

/**
 * Refreshes mappings of instance
 * @event refreshMapping
 * @type {object}
 * @property {string} type - Event name.
 * @property {string} destinationType - Type of mapped object.
 */
const REFRESH_MAPPING = {
  type: 'refreshMapping',
};

/**
 * Refreshes sub tree for instance
 * @event refreshSubTree
 * @type {object}
 * @property {string} type - Event name.
 */
const REFRESH_SUB_TREE = {
  type: 'refreshSubTree',
};

/**
 * Notifies that new document will be created
 * @event beforeDocumentCreate
 * @type {object}
 * @property {string} type - Event name.
 * @property {string} destinationType - Type of mapped object.
 */
const BEFORE_DOCUMENT_CREATE = {
  type: 'beforeDocumentCreate',
};

/**
 * Notifies that new document creating failed
 * @event documentCreateFailed
 * @type {object}
 * @property {string} type - Event name.
 * @property {string} destinationType - Type of mapped object.
 */
const DOCUMENT_CREATE_FAILED = {
  type: 'documentCreateFailed',
};

/**
 * Maps objects to instance
 * @event mapObjects
 * @type {object}
 * @property {string} type - Event name.
 */
const MAP_OBJECTS = {
  type: 'mapObjects',
};


/**
 * Notifies that object was destroyed and/or unmapped from the instance.
 * @event OBJECT_DESTROYED
 * @type {object}
 * @property {object} object - Destroyed object.
 */
const OBJECT_DESTROYED = {
  type: 'objectDestroyed',
};

/**
 * Notifies that object was destroyed and should be unmapped from the instance.
 * @event UNMAP_DESTROYED_OBJECT
 * @type {object}
 * @property {object} object - Destroyed object.
 */
const UNMAP_DESTROYED_OBJECT = {
  type: 'unmapDestroyedObject',
};

/**
 * Deferred map objects to instance.
 * @event deferredMapObjects
 * @type {object}
 * @property {string} type - Event name.
 * @property {Stub[]|Cacheable[]} objects - Mapped objects (always
 * contain "id" and "type" fields).
 */
const DEFERRED_MAP_OBJECTS = {
  type: 'deferredMapObjects',
};

/**
 * Refreshes counter of mapped objects.
 * @event refreshMappedCounter
 * @type {object}
 * @property {string} type - Event name.
 * @property {string} modelType - Type of model.
 */
const REFRESH_MAPPED_COUNTER = {
  type: 'refreshMappedCounter',
};

/**
 * Objects were mapped via object-mapper functionality.
 * @event objectsMappedViaMapper
 * @type {object}
 * @property {(Stub[]|Cacheable[])=} objects - Mapped objects.
 */
const OBJECTS_MAPPED_VIA_MAPPER = {
  type: 'objectsMappedViaMapper',
};

/**
 * Notifies that some objects were mapped and/or unmapped from the instance.
 * @event deferredMappedUnmapped
 * @type {object}
 * @property {string} type - Event name.
 * @property {Cacheable[]} mapped - Mapped objects.
 * @property {Cacheable[]} unmapped - Unmapped objects.
 */
const DEFERRED_MAPPED_UNMAPPED = {
  type: 'deferredMappedUnmapped',
};

/**
 * Notifies that an items list was updated.
 * @event refreshItemsList
 * @type {object}
 * @property {object} object - Current filter object.
 */
const REFRESH_ITEMS_LIST = {
  type: 'refreshItemsList',
};
/**
 * Notifies that an items list will be updated.
 * @event beforeLoadItems
 * @type {object}
 */
const BEFORE_LOAD_ITEMS = {
  type: 'beforeLoadItems',
};

export {
  REFRESHED,
  REFRESH_SUB_TREE,
  REFRESH_RELATED,
  ADD_RELATED,
  RELATED_REFRESHED,
  RELATED_ADDED,
  ROLES_CONFLICT,
  SWITCH_TO_ERROR_PANEL,
  SHOW_INVALID_FIELD,
  VALIDATION_ERROR,
  DESTINATION_UNMAPPED,
  NAVIGATE_TO_TAB,
  PROPOSAL_CREATED,
  REFRESH_PROPOSAL_DIFF,
  REFRESH_COMMENTS,
  RELATED_ITEMS_LOADED,
  COMMENT_CREATED,
  BEFORE_MAPPING,
  REFRESH_MAPPING,
  BEFORE_DOCUMENT_CREATE,
  DOCUMENT_CREATE_FAILED,
  MAP_OBJECTS,
  DEFERRED_MAP_OBJECTS,
  REFRESH_MAPPED_COUNTER,
  OBJECTS_MAPPED_VIA_MAPPER,
  DEFERRED_MAPPED_UNMAPPED,
  OBJECT_DESTROYED,
  UNMAP_DESTROYED_OBJECT,
  REFRESH_ITEMS_LIST,
  BEFORE_LOAD_ITEMS,
};
