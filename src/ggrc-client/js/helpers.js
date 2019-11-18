/*
    Copyright (C) 2019 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import loGet from 'lodash/get';
import loReduce from 'lodash/reduce';
import loFind from 'lodash/find';
import moment from 'moment';
import makeArray from 'can-util/js/make-array/make-array';
import canStache from 'can-stache';
import canList from 'can-list';
import canMap from 'can-map';
import Spinner from 'spin.js';
import isFunction from 'can-util/js/is-function/is-function';
import {
  getPageInstance,
} from './plugins/utils/current-page-utils';
import {
  getRole,
  isAuditor,
} from './plugins/utils/acl-utils';
import {
  isAllowed,
  isAllowedFor,
  isAllowedAny,
} from './permission';
import modalModels from './models/modal-models';
import {isScopeModel} from './plugins/utils/models-utils';
import {scopingObjects} from './plugins/models-types-collections';
import {
  allowedToMap,
  allowedToCreate,
} from './models/mappers/mappings';
import {
  getFormattedLocalDate,
  formatDate,
} from './plugins/utils/date-utils';
import {validateAttr, isValidAttr} from './plugins/utils/validation-utils';
import {
  isStandardFlow,
  isSox302Flow,
  isMultiLevelFlow,
} from './plugins/utils/verification-flow-utils';

/**
 * Builds class name of two segments - prefix and computed value
 * @param  {String|computed} prefix class prefix
 * @param  {String|computed} compute some computed value
 * @return {String} computed class string
 */
canStache.registerHelper('addclass', function (prefix, compute) {
  prefix = resolveComputed(prefix);
  let computeVal = resolveComputed(compute) || '';
  let classSegment = computeVal.trim()
    .replace(/[\s\t]+/g, '')
    .toLowerCase();

  return [prefix, classSegment].join('-');
});

// Resolve and return the first computed value from a list
canStache.registerHelper('firstexist', function () {
  let args = makeArray(arguments).slice(0, arguments.length - 1); // ignore the last argument (some Can object)
  for (let i = 0; i < args.length; i++) {
    let v = resolveComputed(args[i]);
    if (v && v.length) {
      return v.toString();
    }
  }
  return '';
});

// Return the first value from a list that computes to a non-empty string
canStache.registerHelper('firstnonempty', function () {
  let args = makeArray(arguments).slice(0, arguments.length - 1); // ignore the last argument (some Can object)
  for (let i = 0; i < args.length; i++) {
    let v = resolveComputed(args[i]);
    if (v !== null && v !== undefined && !!v.toString()
      .trim().replace(/&nbsp;|\s|<br *\/?>/g, '')) return v.toString();
  }
  return '';
});

// Like 'render', but doesn't serialize the 'context' object, and doesn't
// apply options.hash
canStache.registerHelper('renderLive', function (template, context, options) {
  if (!options) {
    options = context;
    context = this;
  } else {
    options.contexts = options.contexts.add(context);
  }

  if (typeof context === 'function') {
    context = context();
  }

  if (typeof template === 'function') {
    template = template();
  }

  if (options.hash) {
    options.contexts = options.contexts.add(options.hash);
  }

  let view = GGRC.Templates[template];
  return canStache(view)(options.contexts);
});

/**
 *  Helper for rendering date or datetime values in current local time
 *
 *  @param {boolean} hideTime - if set to true, render date only
 *  @return {String} - date or datetime string in the following format:
 *    * date: MM/DD/YYYY),
 *    * datetime (MM/DD/YYYY hh:mm:ss [PM|AM] [local timezone])
 */
canStache.registerHelper('date', function (date, hideTime) {
  date = isFunction(date) ? date() : date;
  return formatDate(date, hideTime);
});

/**
 *  Helper for rendering datetime values in current local time
 *
 *  @return {String} - datetime string in the following format:
 *  (MM/DD/YYYY hh:mm:ss [PM|AM] [local timezone])
 */
canStache.registerHelper('dateTime', function (date) {
  date = isFunction(date) ? date() : date;
  return getFormattedLocalDate(date);
});

/**
 * Checks permissions.
 * Usage:
 *  {{#is_allowed ACTION [ACTION2 ACTION3...] RESOURCE_TYPE_STRING context=CONTEXT_ID}} content {{/is_allowed}}
 *  {{#is_allowed ACTION RESOURCE_INSTANCE}} content {{/is_allowed}}
 */
let allowedActions = ['create', 'read', 'update', 'delete', '__GGRC_ADMIN__'];
canStache.registerHelper('is_allowed', function (...args) {
  let actions = [];
  let resource;
  let resourceType;
  let contextUnset = {};
  let contextId = contextUnset;
  let contextOverride;
  let options = args[args.length - 1];
  let passed = true;

  // Resolve arguments
  args.forEach(function (arg, i) {
    while (typeof arg === 'function' && arg.isComputed) {
      arg = arg();
    }

    if (typeof arg === 'string' && allowedActions.includes(arg)) {
      actions.push(arg);
    } else if (typeof arg === 'string') {
      resourceType = arg;
    } else if (typeof arg === 'object' && arg instanceof canMap) {
      resource = arg;
    }
  });
  if (options.hash && options.hash.hasOwnProperty('context')) {
    contextId = options.hash.context;
    if (typeof contextId === 'function' && contextId.isComputed) {
      contextId = contextId();
    }
    if (contextId && typeof contextId === 'object' && contextId.id) {
      // Passed in the context object instead of the context ID, so use the ID
      contextId = contextId.id;
    }
    //  Using `context=null` in templates, when `null` is not defined,
    //  causes `context_id` to be `""`.
    if (contextId === '' || contextId === undefined) {
      contextId = null;
    } else if (contextId === 'for' || contextId === 'any') {
      contextOverride = contextId;
      contextId = undefined;
    }
  }

  if (resourceType && contextId === contextUnset) {
    throw new Error(
      'If `resource_type` is a string, `context` must be explicit');
  }
  if (actions.length === 0) {
    throw new Error('Must specify at least one action');
  }

  if (resource) {
    resourceType = resource.constructor.model_singular;
    contextId = resource.context ? resource.context.id : null;
  }

  // Check permissions
  actions.forEach(function (action) {
    if (resource && isAllowedFor(action, resource)) {
      passed = true;
      return;
    }
    if (contextId !== undefined) {
      passed = passed && isAllowed(action, resourceType,
        contextId);
    }
    if (passed && contextOverride === 'for' && resource) {
      passed = passed && isAllowedFor(action, resource);
    } else if (passed && contextOverride === 'any' && resourceType) {
      passed = passed && isAllowedAny(action, resourceType);
    }
  });

  // remove Delete permission for all Scope objects
  if (actions.includes('delete') && scopingObjects.includes(resourceType)) {
    passed = false;
  }

  return passed ? options.fn(options.contexts || this) :
    options.inverse(options.contexts || this);
});

canStache.registerHelper('any_allowed', function (action, data, options) {
  let passed = [];
  let hasPassed;
  data = resolveComputed(data);

  data.forEach(function (item) {
    passed.push(isAllowedAny(action, item.model_name));
  });
  hasPassed = passed.some(function (val) {
    return val;
  });
  return options[hasPassed ? 'fn' : 'inverse'](options.contexts || this);
});

canStache.registerHelper('is_allowed_to_map',
  function (source, target, options) {
    //  For creating mappings, we only care if the user has update permission on
    //  source and/or target.
    //  - `source` must be a model instance
    //  - `target` can be the name of the target model or the target instance
    let canMap;

    source = resolveComputed(source);
    target = resolveComputed(target);
    canMap = allowedToMap(source, target, options);

    if (canMap) {
      return options.fn(options.contexts || this);
    }
    return options.inverse(options.contexts || this);
  });

canStache.registerHelper('is_allowed_to_create', (source, target, options) => {
  let canCreate;

  source = resolveComputed(source);
  target = resolveComputed(target);
  canCreate = allowedToCreate(source, target);

  if (canCreate) {
    return options.fn(options.contexts);
  }
  return options.inverse(options.contexts);
});

function resolveComputed(maybeComputed, alwaysResolve) {
  return (typeof maybeComputed === 'function'
    && (maybeComputed.isComputed || alwaysResolve)) ?
    resolveComputed(maybeComputed(), alwaysResolve) : maybeComputed;
}

canStache.registerHelper('attach_spinner', function (spinOpts, styles) {
  spinOpts = isFunction(spinOpts) ? spinOpts() : spinOpts;
  styles = isFunction(styles) ? styles() : styles;
  spinOpts = typeof spinOpts === 'string' ? JSON.parse(spinOpts) : {};
  styles = typeof styles === 'string' ? styles : '';
  return function (el) {
    let spinner = new Spinner(spinOpts).spin();
    $(el).append($(spinner.el).attr('style',
      $(spinner.el).attr('style') + ';' + styles)).data('spinner', spinner);
  };
});

function localizeDate(date, options, tmpl, allowNonISO) {
  let formats = [
    'YYYY-MM-DD',
    'YYYY-MM-DDTHH:mm:ss',
    'YYYY-MM-DDTHH:mm:ss.SSSSSS',
  ];
  if (allowNonISO) {
    formats.push('MM/DD/YYYY', 'MM/DD/YYYY hh:mm:ss A');
  }
  if (!options) {
    return moment().format(tmpl);
  }
  date = resolveComputed(date);
  if (date) {
    if (typeof date === 'string') {
      // string dates are assumed to be in ISO format
      return moment.utc(date, formats, true)
        .format(tmpl);
    }
    return moment(new Date(date)).format(tmpl);
  }
  return '';
}

canStache.registerHelper('localize_date',
  function (date, allowNonISO, options) {
    // allowNonIso was not passed
    if (!options) {
      options = allowNonISO;
      allowNonISO = false;
    }
    return localizeDate(date, options, 'MM/DD/YYYY', allowNonISO);
  });

canStache.registerHelper('normalizeLink', (value) => {
  let link = resolveComputed(value);
  if (link) {
    link = link.replace(/^(?!(?:\w+:)?\/)/, 'http://');
  }

  return link;
});

canStache.registerHelper('lowercase', function (value, options) {
  value = resolveComputed(value) || '';
  return value.toLowerCase();
});

canStache.registerHelper('is_dashboard', function (options) {
  return /dashboard/.test(window.location) ?
    options.fn(options.contexts) :
    options.inverse(options.contexts);
});

canStache.registerHelper('is_dashboard_or_all', function (options) {
  return (/dashboard/.test(window.location) ||
    /objectBrowser/.test(window.location)) ?
    options.fn(options.contexts) :
    options.inverse(options.contexts);
});

canStache.registerHelper('current_user_is_admin', function (options) {
  if (isAllowed('__GGRC_ADMIN__')) {
    return options.fn(options.contexts);
  }
  return options.inverse(options.contexts);
});

canStache.registerHelper('urlPath', function () {
  return window.location.pathname;
});

/*
  Evaluates multiple helpers as if they were a single condition

  Each new statement is begun with a newline-prefixed string. The type of logic
  to apply as well as whether it should be a truthy or falsy evaluation may also
  be included with the statement in addition to the helper name.

  Currently, if_helpers only supports Disjunctive Normal Form. All "and" statements are grouped,
  groups are split by "or" statements.

  All hash arguments (some_val=37) must go in the last line and should be prefixed by the
  zero-based index of the corresponding helper. This is necessary because all hash arguments
  are required to be the final arguments for a helper. Here's an example:
    _0_some_val=37 would pass some_val=37 to the first helper.

  Statement syntax:
    '\
    [LOGIC] [TRUTHY_FALSY]HELPER_NAME' arg1 arg2 argN

  Defaults:
    LOGIC = and (accepts: and or)
    TRUTHY_FALSEY = # (accepts: # ^)
    HELPER_NAME = some_helper_name

  Example:
    {{#if_helpers '\n ^if' instance.archived '\n and ^if' instance.deleted}}
      matched all conditions
    {{else}}
      failed
    {{/if_helpers}}

  FIXME: Only synchronous helpers (those which call options.fn() or options.inverse()
    without yielding the thread through defer_render or otherwise) can currently be used
    with if_helpers.  if_helpers should support all helpers by changing the walk through
    conjunctions and disjunctions to one using a loReduce(Array, function (Deferred, item) {}, $.when())
    pattern instead of loReduce(Array, function (Boolean, item) {}, Boolean) pattern. --BM 8/29/2014
*/
canStache.registerHelper('if_helpers', function (...args) {
  let options = args[args.length - 1];
  let helperResult;
  let helperOptions = Object.assign({}, options, {
    fn: function () {
      helperResult = 'fn';
    },
    inverse: function () {
      helperResult = 'inverse';
    },
  });

  // Parse statements
  let statements = [];
  let statement;
  let match;
  let disjunctions = [];
  let index = 0;

  args.forEach(function (arg, i) {
    if (i < args.length - 1) {
      if (typeof arg === 'string' && arg.match(/^\\n\s*/)) {
        if (statement) {
          if (statement.logic === 'or') {
            disjunctions.push(statements);
            statements = [];
          }
          statements.push(statement);
          index = index + 1;
        }
        if (match = arg.match(/^\\n\s*((and|or) )?([#^])?(\S+?)$/)) {
          statement = {
            fn_name: match[3] === '^' ? 'inverse' : 'fn',
            helper: canStache.getHelper(match[4], options.contexts),
            args: [],
            logic: match[2] === 'or' ? 'or' : 'and',
          };

          // Add hash arguments
          if (options.hash) {
            let hash = {};
            let prefix = '_' + index + '_';
            let prop;

            for (prop in options.hash) {
              if (prop.indexOf(prefix) === 0) {
                hash[prop.substr(prefix.length)] = options.hash[prop];
              }
            }
            if (!$.isEmptyObject(hash)) {
              statement.hash = hash;
            }
          }
        } else {
          statement = null;
        }
      } else if (statement) {
        statement.args.push(arg);
      }
    }
  });
  if (statement) {
    if (statement.logic === 'or') {
      disjunctions.push(statements);
      statements = [];
    }
    statements.push(statement);
  }
  disjunctions.push(statements);

  if (disjunctions.length) {
    // Evaluate statements
    let result = loReduce(disjunctions,
      function (disjunctiveResult, conjunctions) {
        if (disjunctiveResult) {
          return true;
        }

        let conjunctiveResult = loReduce(conjunctions,
          function (currentResult, stmt) {
            if (!currentResult) {
              return false;
            } // short circuit

            helperResult = null;
            stmt.helper.fn(...stmt.args.concat([
              Object.assign({}, helperOptions,
                {hash: stmt.hash || helperOptions.hash}),
            ]));
            helperResult = helperResult === stmt.fn_name;
            return currentResult && helperResult;
          }, true);
        return disjunctiveResult || conjunctiveResult;
      }, false);

    // Execute based on the result
    if (result) {
      return options.fn(options.contexts);
    } else {
      return options.inverse(options.contexts);
    }
  }
});

canStache.registerHelper('if_in', function (needle, haystack, options) {
  needle = resolveComputed(needle);
  haystack = resolveComputed(haystack).split(',');

  let found = haystack.some(function (hay) {
    return hay.trim() === needle;
  });
  return options[found ? 'fn' : 'inverse'](options.contexts);
});

canStache.registerHelper('if_instance_of', function (inst, cls, options) {
  let result;
  cls = resolveComputed(cls);
  inst = resolveComputed(inst);

  if (typeof cls === 'string') {
    cls = cls.split('|').map(function (cl) {
      return modalModels[cl];
    });
  } else if (typeof cls !== 'function') {
    cls = [cls.constructor];
  } else {
    cls = [cls];
  }

  result = loFind(cls, (cl) => inst instanceof cl);
  return options[result ? 'fn' : 'inverse'](options.contexts);
});

canStache.registerHelper('ggrc_config_value',
  function (key, default_, options) {
    key = resolveComputed(key);
    if (!options) {
      options = default_;
      default_ = null;
    }
    default_ = resolveComputed(default_);
    default_ = default_ || '';
    return loGet(GGRC.config, key) || default_;
  });

canStache.registerHelper('if_config_exist', function (key, options) {
  key = resolveComputed(key);
  let configValue = loGet(GGRC.config, key);

  return configValue ?
    options.fn(options.contexts) :
    options.inverse(options.contexts);
});

canStache.registerHelper('debugger', function () {
  // This just gives you a helper that you can wrap around some code in a
  // template to see what's in the context. Dev tools need to be open for this
  // to work (in Chrome at least).
  debugger; // eslint-disable-line no-debugger

  let options = arguments[arguments.length - 1];
  return options.fn(options.contexts);
});

/*
Add new variables to current scope. This is useful for passing variables
to initialize a tree view.

Example:
  {{#add_to_current_scope example1="a" example2="b"}}
    {{log .}} // {example1: "a", example2: "b"}
  {{/add_to_current_scope}}
*/
canStache.registerHelper('add_to_current_scope', function (options) {
  return options.fn(options.contexts
    .add(Object.assign({}, options.context, options.hash)));
});

/*
Add spaces to a CamelCase string.

Example:
{{un_camel_case "InProgress"}} becomes "In Progress"
*/
canStache.registerHelper('un_camel_case', function (str, toLowerCase) {
  let value = isFunction(str) ? str() : str;
  toLowerCase = typeof toLowerCase !== 'object';
  if (!value) {
    return value;
  }
  value = value.replace(/([A-Z]+)/g, ' $1').replace(/([A-Z][a-z])/g, ' $1');
  return toLowerCase ? value.toLowerCase() : value;
});

canStache.registerHelper('modifyFieldTitle', function (type, field, options) {
  let titlesMap = {
    Cycle: 'Cycle ',
    CycleTaskGroup: 'Group ',
    CycleTaskGroupObjectTask: 'Task ',
  };
  type = isFunction(type) ? type() : type;

  return titlesMap[type] ? titlesMap[type] + field : field;
});

canStache.registerHelper('is_auditor', function (options) {
  const audit = getPageInstance();
  if (audit.type !== 'Audit') {
    console.warn('is_auditor called on non audit page');
    return options.inverse(options.contexts);
  }

  if (isAuditor(audit, GGRC.current_user)) {
    return options.fn(options.contexts);
  }
  return options.inverse(options.contexts);
});

canStache.registerHelper('has_role', function (role, instance, options) {
  instance = isFunction(instance) ? instance() : instance;
  const acr = instance ? getRole(instance.type, role) : null;

  if (!acr) {
    return options.inverse(options.contexts);
  }

  const hasRole = !!loFind(instance.access_control_list, (item) => {
    return item.ac_role_id === acr.id &&
      item.person_id === GGRC.current_user.id;
  });

  if (hasRole) {
    return options.fn(options.contexts);
  } else {
    return options.inverse(options.contexts);
  }
});

canStache.registerHelper('isScopeModel', function (instance, options) {
  const modelName = isFunction(instance) ? instance().type : instance.type;

  return isScopeModel(modelName) ? options.fn(this) : options.inverse(this);
});

/*
  Given an object, it determines if it's a recurring workflow or not.

  @param object - the object we want to check
  */
canStache.registerHelper('if_recurring_workflow', (object, options) => {
  object = isFunction(object) ? object() : object;
  if (['day', 'week', 'month'].includes(object.unit)) {
    return options.fn(this);
  }
  return options.inverse(this);
});

// Sets current "can" context into element data
canStache.registerHelper('canData',
  (key, options) => {
    key = isFunction(key) ? key() : key;

    return (el) => {
      $(el).data(key, options.context);
    };
  }
);

canStache.registerHelper('validateAttr',
  (instance, attrName, options) => {
    instance = isFunction(instance) ? instance() : instance;
    attrName = isFunction(attrName) ? attrName() : attrName;
    const errorMessage = validateAttr(instance, attrName);

    return errorMessage && !instance._suppress_errors ?
      options.fn(errorMessage) :
      options.inverse(options.contexts);
  }
);

canStache.registerHelper('isValidAttr',
  (instance, attrName, options) => {
    instance = isFunction(instance) ? instance() : instance;
    attrName = isFunction(attrName) ? attrName() : attrName;

    return (isValidAttr(instance, attrName) || instance._suppress_errors) ?
      options.fn(options.context) :
      options.inverse(options.contexts);
  }
);

canStache.registerHelper('initDeferredData',
  (instance, list) => (el) => {
    $(el).data('deferred_to', {
      // list must be a reference to update deffered_to.list data attribute
      // on element if the list has changed
      list: isFunction(list) ? list() : list,
      instance: isFunction(instance) ? instance() : instance,
    });
  }
);

canStache.registerHelper('isArray', (items, options) => {
  items = isFunction(items) ? items() : items;

  return Array.isArray(items) || items instanceof canList ?
    options.fn(options.contexts) :
    options.inverse(options.contexts);
});

canStache.registerHelper('isTextLarge', (data, options) => {
  const lengthThreshold = 100;

  data = isFunction(data) ? data() : data;

  if (!data) {
    return options.inverse(options.contexts);
  }

  return data.length > lengthThreshold ?
    options.fn(data):
    options.inverse(options.contexts);
});

// Formats the counter according to "(number)" format
canStache.registerHelper('displayCount', (countObserver) => {
  let count = countObserver();
  if (count) {
    return '(' + count + ')';
  }
});

canStache.registerHelper('is_edit_denied', (instance, options) => {
  const source = isFunction(instance) ? instance(): instance;
  const isEditDenied = source.archived || source._is_sox_restricted;

  return isEditDenied
    ? options.fn(options.context)
    : options.inverse(options.context);
});

/*
 * Returns true when Standard Verification flow is turned ON for instance.
 */
canStache.registerHelper('is_standard_verification_flow',
  (instance, options) => {
    instance = isFunction(instance) ? instance(): instance;
    return isStandardFlow(instance)
      ? options.fn(options.context)
      : options.inverse(options.context);
  }
);

/*
 * Returns true when SOX 302 Verification flow is turned ON for instance.
 */
canStache.registerHelper('is_sox_302_verification_flow',
  (instance, options) => {
    instance = isFunction(instance) ? instance(): instance;
    return isSox302Flow(instance)
      ? options.fn(options.context)
      : options.inverse(options.context);
  }
);

/*
 * Returns true when Multi-level Verification flow is turned ON for instance.
 */
canStache.registerHelper('is_ML_verification_flow',
  (instance, options) => {
    instance = isFunction(instance) ? instance(): instance;
    return isMultiLevelFlow(instance)
      ? options.fn(options.context)
      : options.inverse(options.context);
  }
);
