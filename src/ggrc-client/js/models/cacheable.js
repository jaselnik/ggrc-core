/*
    Copyright (C) 2020 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import loFind from 'lodash/find';
import {filteredMap} from '../plugins/ggrc-utils';
import loThrottle from 'lodash/throttle';
import loIsEmpty from 'lodash/isEmpty';
import loIsFunction from 'lodash/isFunction';
import loForEach from 'lodash/forEach';
// Disabling some minor eslint rules until major refactoring
/* eslint-disable no-console, id-length */

import {ggrcAjax} from '../plugins/ajax-extensions';
import canBatch from 'can-event/batch/batch';
import canModel from 'can-model';
import canList from 'can-list';
import canMap from 'can-map';
import CustomAttributeAccess from '../plugins/utils/custom-attribute/custom-attribute-access';
import {CUSTOM_ATTRIBUTE_TYPE} from '../plugins/utils/custom-attribute/custom-attribute-config';
import {
  isSnapshot,
} from '../plugins/utils/snapshot-utils';
import resolveConflict from './conflict-resolution/conflict-resolution';
import PersistentNotifier from '../plugins/persistent-notifier';
import enqueue from './save-queue';
import tracker from '../tracker';
import {delayLeavingPageUntil} from '../plugins/utils/current-page-utils';
import Stub from './stub';

export default canModel.extend({
  ajax: ggrcAjax,
  root_object: '',
  attr_list: [
    {
      attr_title: 'Title',
      attr_name: 'title',
      order: 10,
    },
    {
      attr_title: 'Code',
      attr_name: 'slug',
      order: 30,
    },
    {
      attr_title: 'Last Updated Date',
      attr_name: 'updated_at',
      order: 70,
    },
    {
      attr_title: 'Last Updated By',
      attr_name: 'modified_by',
      order: 71,
    },
  ],

  root_collection: '',
  model_singular: '',
  model_plural: '',
  table_singular: '',
  table_plural: '',
  title_singular: '',
  title_plural: '',
  findOne: 'GET {href}',

  makeDestroy: function (destroy) {
    return (id) => destroy.call(this, id);
  },

  makeFindAll: function (finder) {
    return function (params, success, error) {
      let deferred = $.Deferred();
      let sourceDeferred = finder.call(this, params);
      let self = this;

      deferred.then(success, error);
      sourceDeferred.then(function (sourceData) {
        if (sourceData[self.root_collection + '_collection']) {
          sourceData = sourceData[self.root_collection + '_collection'];
        }
        if (sourceData[self.root_collection]) {
          sourceData = sourceData[self.root_collection];
        }

        if (!sourceData.splice) {
          sourceData = [sourceData];
        }

        self._modelize(sourceData, deferred);
      }, deferred.reject);

      return deferred;
    };
  },

  setup: function (construct, name, statics) {
    let staticProps = statics;

    // if name for model was not set
    if (typeof name !== 'string') {
      staticProps = name;
    }

    if (!staticProps || !staticProps.findAll) {
      if (!this.findAll || !this.root_collection) {
        this.findAll = () => {
          throw new Error(
            'No default findAll() exists for subclasses of Cacheable');
        };
        this.findPage = () => {
          throw new Error(
            'No default findPage() exists for subclasses of Cacheable');
        };
      } else if (this.root_collection) {
        this.findAll = `GET /api/${this.root_collection}`;
      }
    }

    if (this.root_collection) {
      this.model_plural = staticProps.model_plural || this.root_collection
        .replace(/(?:^|_)([a-z])/g, function (s, l) {
          return l.toUpperCase();
        });

      this.title_plural = staticProps.title_plural || this.root_collection
        .replace(/(^|_)([a-z])/g, function (s, u, l) {
          return (u ? ' ' : '') + l.toUpperCase();
        });
      this.table_plural = staticProps.table_plural || this.root_collection;
    }
    if (this.root_object) {
      this.model_singular = staticProps.model_singular || this.root_object
        .replace(/(?:^|_)([a-z])/g, function (s, l) {
          return l.toUpperCase();
        });
      this.title_singular = staticProps.title_singular || this.root_object
        .replace(/(^|_)([a-z])/g, function (s, u, l) {
          return (u ? ' ' : '') + l.toUpperCase();
        });
      this.table_singular = staticProps.table_singular || this.root_object;
    }

    if (!loIsFunction(this.findAll)) {
      this.findPage = this.makeFindPage(this.findAll);
    }

    // Prevent event "bleeding" from other members of the Cacheable tree.
    // This fix causes breakages in places where we're expecting model class
    //  events not to be isolated (like in the LHN controller).
    //  I've submitted a fix to CanJS for this but it remains to be seen
    //  whether it gets in and when.  --BM 3/4/14
    // this.__bindEvents = {};

    let that = this;

    if (staticProps.mixins) {
      loForEach(staticProps.mixins, function (mixin) {
        mixin.addTo(that);
      });
      delete this._mixins;
    }

    return this._super(...arguments);
  },

  init: function () {
    this.cache = {};

    let idKey = this.id;
    let _update = this.update;
    let _create = this.create;
    this.bind('created', function (ev, newObj) {
      let cache = newObj.constructor.cache;
      if (newObj[idKey] || newObj[idKey] === 0) {
        if (!isSnapshot(newObj)) {
          cache[newObj[idKey]] = newObj;
        }
        if (cache[undefined] === newObj) {
          delete cache[undefined];
        }
      }
    });
    this.bind('destroyed', function (ev, oldObj) {
      delete oldObj.constructor.cache[oldObj[idKey]];
    });

    // FIXME:  This gets set up in a chain of multiple calls to the function defined
    //  below when the update endpoint isn't set in the model's static config.
    //  This leads to conflicts not actually rejecting because on the second go-round
    //  the local and remote objects look the same.  --BM 2015-02-06
    this.update = function (id, params) {
      let modelType = this.constructor.table_singular;
      let ret = _update
        .call(this, id, this.process_args(params))
        .then((obj) => obj,
          (xhr) => {
            let remoteAttrs = xhr.responseJSON && xhr.responseJSON[modelType];
            if (xhr.status === 409 && remoteAttrs) {
              let dfd = $.Deferred();
              resolveConflict(xhr, this.findInCacheById(id), remoteAttrs)
                .then(
                  (obj) => dfd.resolve(obj),
                  (xhr) => dfd.reject(xhr)
                );
              return dfd;
            }
            return xhr;
          });
      delete ret.hasFailCallback;
      return ret;
    };
    this.create = function (params) {
      let ret = _create
        .call(this, this.process_args(params));
      delete ret.hasFailCallback;
      return ret;
    };
  },

  findInCacheById: function (id) {
    return this.cache[id];
  },

  removeFromCacheById: function (key) {
    return delete this.cache[key];
  },

  newInstance: function (args) {
    let cache = this.cache;
    let isKeyExists = args && args[this.id];
    let isObjectExists = isKeyExists && cache[args[this.id]];
    let notSnapshot = args && !isSnapshot(args);
    if (isObjectExists && notSnapshot) {
      // cache[args.id].attr(args, false); //CanJS has bugs in recursive merging
      // (merging -- adding properties from an object without removing existing ones
      //  -- doesn't work in nested objects).  So we're just going to not merge properties.
      return cache[args[this.id]];
    }
    return this._super(...arguments);
  },
  process_args: function (args) {
    let pargs = {};
    let obj = pargs;
    let src;
    let goNames;
    if (this.root_object && !(this.root_object in args)) {
      obj = pargs[this.root_object] = {};
    }
    src = args.serialize ? args.serialize() : args;
    goNames = Object.keys(src);
    for (let i = 0; i < (goNames.length || 0); i++) {
      obj[goNames[i]] = src[goNames[i]];
    }
    return pargs;
  },

  models: function (params) {
    let ms;
    if (params[this.root_collection + '_collection']) {
      params = params[this.root_collection + '_collection'];
    }
    if (params[this.root_collection]) {
      params = params[this.root_collection];
    }
    if (!params || params.length === 0) {
      return new this.List();
    }
    ms = this._super(params);
    if (params instanceof canMap || params instanceof canList) {
      params.replace(ms);
      return params;
    }
    return ms;
  },

  _modelize: function (sourceData, deferred) {
    let obsList = new this.List([]);
    let index = 0;
    let self = this;
    function modelizeMS(ms) {
      let item;
      let start;
      let instances = [];
      let models;

      start = Date.now();
      while (sourceData.length > index && (Date.now() - start) < ms) {
        canBatch.start();
        item = sourceData[index];
        index += 1;
        models = self.models([item]);
        instances.push(...Array.from(models));
        canBatch.stop();
      }
      canBatch.start();
      obsList.push(...Array.from(instances));
      canBatch.stop();
    }

    // Trigger a setTimeout loop to modelize remaining objects
    (function cb() {
      modelizeMS(100);
      if (sourceData.length > index) {
        setTimeout(cb, 5);
      } else {
        deferred.resolve(obsList);
      }
    })();
  },

  object_from_resource: function (params) {
    let objName = this.root_object;
    if (!params) {
      return params;
    }
    if (typeof objName !== 'undefined' && params[objName]) {
      for (let i in params[objName]) {
        if (params[objName].hasOwnProperty(i)) {
          params.attr
            ? params.attr(i, params[objName][i])
            : (params[i] = params[objName][i]);
        }
      }
      if (params.removeAttr) {
        params.removeAttr(objName);
      } else {
        delete params[objName];
      }
    }
    return params;
  },
  model: function (params) {
    let model;
    params = this.object_from_resource(params);
    if (!params) {
      return params;
    }
    if (isSnapshot(params)) {
      this.removeFromCacheById(params[this.id]);
      delete this.cache[params[this.id]];
    }
    model = this.findInCacheById(params[this.id]);
    if (model && !isSnapshot(params)) {
      if (model.cleanupAcl && params.access_control_list) {
        // Clear ACL to avoid "merge" of arrays.
        // "params" has valid ACL array.
        model.cleanupAcl();
      }

      params = params.serialize ? params.serialize() : params;

      model.attr(params);
      model.updateCaObjects(params.custom_attribute_values);
    } else {
      model = this._super(params);
    }
    return model;
  },
  tree_view_options: {
    display_attr_names: ['title', 'status', 'updated_at'],
    mandatory_attr_names: ['title'],
  },
  sub_tree_view_options: {},
  obj_nav_options: {},
  list_view_options: {},

  makeFindPage: function (findAllSpec) {
  /* Create a findPage function that will return a paging object that will
    * provide access to the model items provided in a single page as well
    * as paging capability to retrieve the named pages provided in the
    * response.
    *
    * findPage returns an object with two properties:
    * {this.options.model.root_collection}_collection and paging. The models
    * property will be an array of all model instances in the page retrieved
    * for the collection. The paging property will be an object that can be
    * used to retrieve other named pages from the collection.  The names of
    * pages include first, prev, next, last. Named page properties will
    * either be functions or the null value in the case where there is no
    * link available in the collection under that name.  Paging functions
    * have the same type of return value as the findPage function.
    *
    * This method assumes that findAllSpec is a string like
    * "GET /api/programs". If this assumption is invalid, this function
    * WILL NOT work correctly.
    */
    let parts;
    let method;
    let collectionUrl;
    let baseParams;

    let that = this;

    function makePaginator(paging, baseParams, scope) {
      function getPage(pageName) {
        if (paging[pageName]) {
          return function () {
            // the paging ("next", "prev", etc. URLs already include query
            // string params, thus passing null for them
            return findPageFunc(paging[pageName], null, baseParams, scope);
          };
        }
        return null;
      }

      return {
        count: paging.count,
        total: paging.total,
        first: getPage('first'),
        prev: getPage('prev'),
        next: getPage('next'),
        last: getPage('last'),
        has_next: function () {
          return this.next !== null;
        },
        has_prev: function () {
          return this.prev !== null;
        },
      };
    }

    function findPageFunc(url, data, params, scope) {
      let ajaxOptions = Object.assign({
        url: url,
        data: data,
      }, params);

      return ggrcAjax(ajaxOptions).then(function (response) {
        let collection = response[that.root_collection + '_collection'];
        let paginator = makePaginator(collection.paging, params, scope);
        let ret = {
          paging: paginator,
        };
        ret[scope.root_collection + '_collection'] =
          scope.models(collection[scope.root_collection]);
        return ret;
      });
    }

    if (typeof findAllSpec === 'string') {
      parts = findAllSpec.split(' ');
      method = parts.length === 2 ? parts[0] : 'GET';
      collectionUrl = parts.length === 2 ? parts[1] : parts[0];
    } else if (typeof findAllSpec === 'object') {
      method = findAllSpec.type || 'GET';
      collectionUrl = findAllSpec.url;
    } else {
      return; // TODO make a pager if findAllSpec is a function.
    }

    baseParams = {
      type: method,
      dataType: 'json',
    };

    return function (params) {
      params = params || {};
      if (!params.__page) {
        params.__page = 1;
      }
      if (!params.__page_size) {
        params.__page_size = 20;
      }
      return findPageFunc(collectionUrl, params, baseParams, that);
    };
  },
}, {
  define: {
    custom_attribute_values: {
      validate: {
        validateGCA: function () {
          return this;
        },
      },
    },
  },
  init: function () {
    let cache = this.constructor.cache;
    let idKey = this.constructor.id;
    if ((this[idKey] || this[idKey] === 0) &&
      !isSnapshot(this)) {
      cache[this[idKey]] = this;
    }
    this.notifier = new PersistentNotifier();

    if (this.isCustomAttributable()) {
      this._customAttributeAccess = new CustomAttributeAccess(this);
    }

    /*
    * Trigger validation after each "change" event of instance
    * to have actual "instance.errors" object
    */
    this.on('change', (ev, fieldName) => {
      if (fieldName === 'errors') {
        return;
      }
      this.validate();
    });
  },
  /**
   * Updates custom attribute objects with help custom
   * attribute values.
   * @param {Object[]} caValues - Custom attribute values.
   */
  updateCaObjects(caValues) {
    if (this.isCustomAttributable() && caValues) {
      this._customAttributeAccess.updateCaObjects(caValues);
    }
  },
  load_custom_attribute_definitions: function () {
    let definitions;
    if (this.attr('custom_attribute_definitions')) {
      return;
    }
    if (GGRC.custom_attr_defs === undefined) {
      GGRC.custom_attr_defs = {};
      console.warn('Missing injected custom attribute definitions');
    }
    definitions = filteredMap(GGRC.custom_attr_defs, (def) => {
      let idCheck = !def.definition_id || def.definition_id === this.id;
      if (idCheck &&
          def.definition_type === this.constructor.table_singular) {
        return def;
      }
    });
    this.attr('custom_attribute_definitions', definitions);
  },
  /*
    * 1 version:
    * Returns all custom attribute objects owned by instance.
    * @return {CustomAttributeObject[]} - The array contained custom attribute
    *  objects.
    *
    * 2 version:
    * Returns custom attribute object with certain custom attribute id.
    * @param {number} caId(2) - Custom attribute id.
    * @return {CustomAttributeObject|undefined} - Found custom attribute object
    *  otherwise - undefined if it wasn't found.
    *
    * 3 version:
    * Returns filtered array with help options object.
    * @param {object} options -
    * @param {CUSTOM_ATTRIBUTE_TYPE} options.type - Filters array by custom
    *  attribute type.
    * @return {CustomAttributeObject[]} - Filtered custom attriubte object
    *  list.
    *
    * 4 version:
    * Sets value for certain custom attribute object.
    * @param {number|string} caId(4) - Custom attribute id.
    * @param {number|string|boolean} - Value for custom attribute object.
    */
  customAttr(...args) {
    if (!this.isCustomAttributable()) {
      throw Error('This type has not ability to set custom attribute value');
    }

    switch (args.length) {
      case 0: {
        return this._getAllCustomAttr();
      }
      case 1: {
        return this._getCustomAttr(args[0]);
      }
      case 2: {
        this._setCustomAttr(...args);
        break;
      }
    }
  },
  _getAllCustomAttr() {
    return this._customAttributeAccess.read();
  },
  _getCustomAttr(arg) {
    return this._customAttributeAccess.read(arg);
  },
  _setCustomAttr(caId, value) {
    const change = {caId: Number(caId), value};
    this._customAttributeAccess.write(change);
  },
  isCustomAttributable() {
    return this.constructor.is_custom_attributable;
  },
  validateGCAs() {
    let gcas = this.customAttr({type: CUSTOM_ATTRIBUTE_TYPE.GLOBAL});
    gcas.each((caObject) => caObject.validate());

    let valid = loFind(gcas, (caObject) =>
      caObject.validationState.hasGCAErrors
    ) === undefined;

    this.attr('_gca_valid', valid);
    return valid;
  },
  getInstanceErrors: function () {
    const errors = this.attr('errors');

    if (!errors) {
      return null;
    }

    const serializedErrors = errors.attr();
    return loIsEmpty(serializedErrors) ? null : serializedErrors;
  },
  computed_errors: function () {
    let errors = this.getInstanceErrors();
    if (this.attr('_suppress_errors')) {
      return null;
    }
    return errors;
  },
  computed_unsuppressed_errors: function () {
    return this.getInstanceErrors();
  },
  refresh: function (params) {
    let dfd;
    let href = this.selfLink || this.href;
    let that = this;

    if (!href) {
      return $.Deferred().reject();
    }
    if (!this._pending_refresh) {
      this._pending_refresh = {
        dfd: $.Deferred(),
        fn: loThrottle(function () {
          let dfd = that._pending_refresh.dfd;
          let stopFn = tracker.start(that.type,
            tracker.USER_JOURNEY_KEYS.API,
            tracker.USER_ACTIONS.LOAD_OBJECT);
          ggrcAjax({
            url: href,
            params: params,
            type: 'get',
            dataType: 'json',
          })
            .then((response) => {
              if (that.cleanupAcl) {
                response = that.cleanupAcl(response);
              }
              if (that.cleanupCollections) {
                response = that.cleanupCollections(response);
              }
              return that.constructor.model(response);
            })
            .then((model) => {
              that.afterRefresh && that.afterRefresh();
              return model;
            })
            .done(function (response) {
              response.backup();
              stopFn();
              dfd.resolve(...arguments);
            })
            .fail(function () {
              stopFn(true);
              dfd.reject(...arguments);
            })
            .always(function () {
              delete that._pending_refresh;
            });
        }, 1000, {trailing: false}),
      };
    }
    dfd = this._pending_refresh.dfd;
    this._pending_refresh.fn();
    return dfd;
  },
  // TODO: should be refactored and sliced on multiple functions
  serialize: function () {
    let serial = {};
    let val;
    if (arguments.length) {
      return this._super(...arguments);
    }
    /* Serialize only meaningful properties */
    Object.keys(this._data).forEach(function (name) {
      if (name.startsWith && name.startsWith('_')) {
        return;
      }
      val = this[name];
      if (this.constructor.attributes && this.constructor.attributes[name]) {
        let attrConstructor = this.constructor.attributes[name];
        if (attrConstructor === Stub || attrConstructor === Stub.List) {
          serial[name] = val ? (new attrConstructor(val)).serialize() : null;
        } else {
          serial[name] = val;
        }
      } else if (val && loIsFunction(val.save)) {
        serial[name] = (new Stub(val)).serialize();
      } else if (typeof val === 'object' && val !== null && val.length) {
        serial[name] = filteredMap(val, (v) => {
          let isModel = v && loIsFunction(v.save);
          return isModel ?
            (new Stub(v)).serialize() :
            (v && v.serialize) ? v.serialize() : v;
        });
      } else if (!loIsFunction(val)) {
        if (this[name] && this[name].isComputed) {
          serial[name] = val && val.serialize ? val.serialize() : val;
        } else {
          serial[name] = this[name] && this[name].serialize ?
            this[name].serialize() :
            serial[name] = val;
        }
      }
    }.bind(this));
    return serial;
  },
  display_name: function () {
    if (this.is_deleted()) {
      return `"${this.type} ID: ${this.id}" (DELETED)`;
    }
    return this.title || this.name || `"${this.type} ID: ${this.id}"`;
  },
  is_deleted: function () {
    return !(this.created_at);
  },
  display_type: function () {
    return this.type;
  },
  autocomplete_label: function () {
    return this.title;
  },
  _save: function (saveCallback) {
    let isNew = this.isNew();
    let saveDfd = this._dfd;

    this.dispatch('modelBeforeSave');

    if (isNew) {
      if (this.beforeCreate) {
        this.beforeCreate();
      }
    }

    let saveXHR = saveCallback.call(this)
      .then((result) => {
        if (!isNew) {
          this.afterUpdate && this.afterUpdate();
        }
        this.afterSave && this.afterSave();
        return result;
      }, (xhr, status, message) => {
        this.saveError && this.saveError(xhr.responseText);
        return new $.Deferred().reject(xhr, status, message);
      })
      .fail((response) => {
        this.notifier.onEmpty(() => {
          saveDfd.reject(this, response);
        });
      })
      .done(() => {
        this.notifier.onEmpty(() => {
          saveDfd.resolve(this);
        });
      })
      .always(() => {
        this.dispatch('modelAfterSave');
      });

    delayLeavingPageUntil(saveXHR);

    return saveDfd;
  },
  save: function () {
    this._dfd = new $.Deferred();

    this.beforeEnqueue && this.beforeEnqueue();
    delayLeavingPageUntil(this._dfd);

    enqueue(this, this._super);

    return this._dfd;
  },
});
