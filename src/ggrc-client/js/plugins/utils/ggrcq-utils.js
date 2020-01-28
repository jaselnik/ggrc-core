/*
 Copyright (C) 2020 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import {
  externalBusinessObjects,
  externalDirectiveObjects,
  scopingObjects,
} from '../../plugins/models-types-collections';

/**
 * Util methods for integration with GGRCQ.
 */

/**
 * Determine whether model type could have mapped questions.
 * @param {Object} instance - The model instance
 * @return {Boolean} True or False
 */
function hasQuestions(instance) {
  return instance &&
    instance.constructor &&
    instance.constructor.isQuestionnaireable;
}

/**
 * Determine whether model type is changeable externally.
 * @param {Object} instance - The model instance
 * @return {Boolean} True or False
 */
function isChangeableExternally(instance) {
  return instance &&
    instance.constructor &&
    instance.constructor.isChangeableExternally;
}

/**
 * Determine whether model type is mappable externally.
 * @param {Object} source - Source model
 * @param {Object} destination - Destination model
 * @return {Boolean} True or False
 */
function isMappableExternally(source, destination) {
  return (
    (externalDirectiveObjects.includes(source.model_singular) &&
    scopingObjects.includes(destination.model_singular)) ||
    (scopingObjects.includes(source.model_singular) &&
    externalDirectiveObjects.includes(destination.model_singular))
  );
}

/**
 * Get url to questionnaire
 * @param {Object} options - The url options
 * @param {String} options.model - The model name
 * @param {String} options.path - The questionnaire path
 * @param {String} options.slug - The model slug
 * @param {String} options.view - The view path
 * @param {String} options.params - Additional url params
 * @return {String} Url to questions
 */
function getUrl({model, path, slug, view, params}) {
  let url = GGRC.GGRC_Q_INTEGRATION_URL;
  if (!url) {
    return '';
  }
  if (!url.endsWith('/')) {
    url += '/';
  }

  let modelParams = '';

  if (model && slug) {
    model = model.toLowerCase();
    slug = slug.toLowerCase();
    modelParams = `/${model}=${slug}`;
  }

  path = path ? path.toLowerCase() : '';
  view = view ? `/${view}` : '';
  params = params ? `?${params}` : '';

  return `${url}${path}${modelParams}${view}${params}`;
}

/**
 * Get url to page with questions
 * @param {Object} instance - The model instance
 * @return {String} Url to questions
 */
function getQuestionsUrl(instance) {
  return getUrl({
    model: instance.constructor.table_singular,
    path: 'questionnaires',
    slug: instance.slug,
  });
}

/**
 * Get attribute url to page with questions
 * @param {Object} instance - The model instance
 * @return {String} Url to questions
 */
function getQuestionsAttrUrl(instance) {
  const questionsUrl = getQuestionsUrl(instance);
  if (instance.status === 'Active') {
    return `${questionsUrl}/initialize`;
  }
  return questionsUrl;
}

/**
 * Get url to info view
 * @param {Object} instance - The model instance
 * @return {String} Url to info view
 */
function getInfoUrl(instance) {
  const model = instance.constructor.model_singular;
  const isScoping = scopingObjects.includes(model);

  if (isScoping) {
    return getQuestionsUrl(instance);
  }

  return getUrl({
    model: instance.constructor.table_singular,
    path: instance.constructor.table_plural,
    slug: instance.slug,
    view: 'info',
  });
}

/**
 * Get url to comment form
 * @param {Object} instance - The model instance
 * @return {String} Url to comment form
 */
function getCommentFormUrl(instance) {
  return getUrl({
    model: instance.constructor.table_singular,
    path: instance.constructor.table_plural,
    slug: instance.slug,
    view: 'info',
    params: 'comments=open',
  });
}

/**
 * Get url to review view
 * @param {Object} instance - The model instance
 * @return {String} Url to review view
 */
function getReviewUrl(instance) {
  return getUrl({
    model: instance.constructor.table_singular,
    path: instance.constructor.table_plural,
    slug: instance.slug,
    view: 'review',
  });
}

/**
 * Get url to import page
 * @return {String} Url to import page
 */
function getImportUrl() {
  return getUrl({
    path: 'import',
  });
}

/**
 * Get url to proposals view
 * @param {Object} instance - The model instance
 * @return {String} Url to proposals view
 */
function getProposalsUrl(instance) {
  return getUrl({
    model: instance.constructor.table_singular,
    path: instance.constructor.table_plural,
    slug: instance.slug,
    view: 'proposals',
  });
}

/**
 * Get url to change log view
 * @param {Object} instance - The model instance
 * @return {String} Url to change log view
 */
function getChangeLogUrl(instance) {
  const model = instance.constructor.model_singular;
  const isScoping = scopingObjects.includes(model);

  const path = isScoping ? 'questionnaires' : instance.constructor.table_plural;

  return getUrl({
    model: instance.constructor.table_singular,
    path,
    slug: instance.slug,
    view: 'change-log',
  });
}

/**
 * Get urls for for external objects
 * @param {object} instance - The model instance
 * @param {object} destinationModel - Destination model
 * @param {string} statuses - Required statuses list (comma separated)
 * @return {string} Redirection url
 */
function getMapUrl(instance, destinationModel, statuses) {
  const source = instance.constructor.model_singular;
  const destination = destinationModel.constructor.model_singular;

  const scopingSource = scopingObjects.includes(source);
  const scopingDest = scopingObjects.includes(destination);

  const extDirectiveSource = externalDirectiveObjects.includes(source);
  const extDirectiveDest = externalDirectiveObjects.includes(destination);

  const extBusinessSource = externalBusinessObjects.includes(source);
  const extBusinessDest = externalBusinessObjects.includes(destination);


  let view = scopingDest ? 'scope'
    : destinationModel.table_plural;
  let path = instance.constructor.table_plural;

  if (scopingSource) {
    path = 'questionnaires';

    if (extDirectiveDest) {
      view = 'map-objects';
    }
  } else if (extBusinessSource) {
    if (extDirectiveDest) {
      view = 'directives';
    }
  } else if (extDirectiveSource) {
    path = 'directives';

    if (scopingDest) {
      view = 'applicable-scope';
    }
  } else {
    return '';
  }

  let addType = true;
  if (extBusinessDest) {
    addType = false;
  }

  const typeParamName = scopingDest ? 'types'
    : (extDirectiveDest ? 'type' : '');
  const params = `mappingStatus=${statuses}`
    + (addType ? `&${typeParamName}=${destinationModel.table_singular}` : '');

  return getUrl({
    path,
    model: instance.constructor.table_singular,
    slug: instance.slug,
    view,
    params,
  });
}

/**
 * Get url to mapping view
 * @param {Object} instance - The model instance
 * @param {Object} destinationModel - The destination model
 * @return {String} Url to mapping view
 * */
function getMappingUrl(instance, destinationModel) {
  const statuses = 'pending_review,not_in_scope,reviewed';

  return getMapUrl(instance, destinationModel, statuses);
}

/**
 * Get url to unmapping view
 * @param {Object} instance - The model instance
 * @param {Object} destinationModel - The destination model
 * @return {String} Url to unmapping view
 */
function getUnmappingUrl(instance, destinationModel) {
  const statuses = 'pending_review,reviewed';

  return getMapUrl(instance, destinationModel, statuses);
}

/**
 * Get url to create new object
 * @param {Object} model - The object model
 * @return {String} Url to create new object
 */
function getCreateObjectUrl(model) {
  const isScope = scopingObjects.includes(model.model_singular);
  const path = isScope ? 'scope' : model.table_plural;
  const objectBeingCreated = model.root_object;

  const options = {
    path,
    params: `create=${objectBeingCreated}`,
  };

  return getUrl(options);
}

/**
* Get url to instance's attribute
* @param {Object} instance - The model instance
* @param {String} attributeName - Name of attribute
* @param {Boolean} isCustomAttribute - Flag, which defines, is attribute
* custom or not.
* @return {String} Url to attribute
*/
function getProposalAttrUrl(
  instance,
  attributeName,
  isCustomAttribute,
) {
  return getUrl({
    model: instance.constructor.table_singular,
    path: instance.constructor.table_plural,
    slug: instance.slug,
    view: 'info',
    params: `${isCustomAttribute
      ? 'proposalAttribute'
      : 'proposal'
    }=${attributeName}`,
  });
}

export {
  hasQuestions,
  isChangeableExternally,
  isMappableExternally,
  getCommentFormUrl,
  getQuestionsUrl,
  getImportUrl,
  getInfoUrl,
  getReviewUrl,
  getMappingUrl,
  getUnmappingUrl,
  getQuestionsAttrUrl,
  getCreateObjectUrl,
  getUrl,
  getProposalsUrl,
  getChangeLogUrl,
  getProposalAttrUrl,
};
