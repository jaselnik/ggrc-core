/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import canCompute from 'can-compute';
import canList from 'can-list';
import canMap from 'can-map';
let customAttributesType = {
  Text: 'input',
  'Rich Text': 'text',
  'Map:Person': 'person',
  Date: 'date',
  Input: 'input',
  Checkbox: 'checkbox',
  Multiselect: 'multiselect',
  Dropdown: 'dropdown',
};

let CUSTOM_ATTRIBUTE_TYPE = Object.freeze({
  LOCAL: 1,
  GLOBAL: 2,
});

const CA_DD_FLAGS = {
  COMMENT: 0b001, // 1
  ATTACHMENT: 0b10, // 2
  URL: 0b100, // 4
};

const LCA_DROPDOWN_TITLES_MAP = {
  '1': 'Comment',
  '2': 'Evidence File',
  '3': 'Comment and Evidence File',
  '4': 'Evidence Url',
  '5': 'Comment and Evidence Url',
  '6': 'Evidence File and Url',
  '7': 'Comment, Evidence File and Url',
};


/**
 * Convert DD validation value to validation map
 * @param  {Number} value validation value
 * @return {Object}       validation map
 */
function ddValidationValueToMap(value) {
  return {
    attachment: !!(value & CA_DD_FLAGS.ATTACHMENT),
    comment: !!(value & CA_DD_FLAGS.COMMENT),
    url: !!(value & CA_DD_FLAGS.URL),
  };
}

/**
 * Converts DD validation map to a bitmask number
 * @param  {Object} map A map of values which must be encoded into the bitmask
 * @return {Number}     Bitmask representing the flags map
 */
function ddValidationMapToValue(map = {}) {
  let attach = map.attachment ? CA_DD_FLAGS.ATTACHMENT : 0;
  let comment = map.comment ? CA_DD_FLAGS.COMMENT : 0;
  let url = map.url ? CA_DD_FLAGS.URL : 0;

  return attach | comment | url;
}


/**
 * @deprecated Use CustomAttributeObject API to get access to the necessary custom
 * attribute field and make some manipulations with it.
 * Util methods for custom attributes.
 * @param {*} a
 * @param {*} b
 * @return {*}
 */
function sortCustomAttributes(a, b) {
  return a.custom_attribute_id - b.custom_attribute_id;
}

/**
 * @deprecated Use CustomAttributeObject API to get access to the necessary custom
 * attribute field and make some manipulations with it.
 * Return normalized Custom Attribute Type from Custom Attribute Definition
 * @param {String} type - String Custom Attribute Value from JSON
 * @return {String} - Normalized Custom Attribute Type
 */
function getCustomAttributeType(type) {
  return customAttributesType[type] || 'input';
}

/**
 * @deprecated Use CustomAttributeObject API to get access to the necessary custom
 * attribute field and make some manipulations with it.
 * Converts custom attribute value for UI controls.
 * @param {String} type - Custom attribute type
 * @param {Object} value - Custom attribute value
 * @param {Object} valueObj - Custom attribute object
 * @return {Object} Converted value
 */
function convertFromCaValue(type, value, valueObj) {
  if (type === 'checkbox') {
    return value === '1';
  }

  if (type === 'input') {
    if (!value) {
      return null;
    }
    return value.trim();
  }

  if (type === 'person') {
    if (valueObj) {
      return valueObj.id;
    }
    return null;
  }

  if (type === 'dropdown' || type === 'multiselect') {
    if (value === null || value === undefined) {
      return '';
    }
  }
  return value;
}

/**
 * @deprecated Use CustomAttributeObject API to get access to the necessary custom
 * attribute field and make some manipulations with it.
 * Custom Attributes specific parsing logic to simplify business logic of Custom Attributes
 * @param {Array} definitions - original list of Custom Attributes Definition
 * @param {Array} values - original list of Custom Attributes Values
 * @return {Array} Updated Custom attributes
 */
function prepareCustomAttributes(definitions, values) {
  return definitions.map(function (def) {
    let valueData = false;
    let id = def.id;
    let options = (def.multi_choice_options || '').split(',');
    let optionsRequirements = (def.multi_choice_mandatory || '').split(',');
    let type = getCustomAttributeType(def.attribute_type);
    let stub = {
      id: null,
      custom_attribute_id: id,
      attribute_value: def.default_value,
      attribute_object: null,
      validation: {
        empty: true,
        mandatory: def.mandatory,
        valid: true,
      },
      def: def,
      attributeType: type,
      preconditions_failed: [],
      errorsMap: {
        comment: false,
        evidence: false,
        url: false,
      },
    };

    values.forEach(function (value) {
      let errors = [];
      if (value.custom_attribute_id === id) {
        errors = value.preconditions_failed || [];
        value.def = def;
        value.attributeType = type;
        value.validation = {
          empty: errors.indexOf('value') > -1,
          mandatory: def.mandatory,
          valid: errors.indexOf('comment') < 0 &&
            errors.indexOf('evidence') < 0 &&
            errors.indexOf('url') < 0,
        };
        value.errorsMap = {
          comment: errors.indexOf('comment') > -1,
          evidence: errors.indexOf('evidence') > -1,
          url: errors.indexOf('url') > -1,
        };
        valueData = value;
      }
    });

    valueData = valueData || stub;

    if (type === 'dropdown') {
      valueData.validationConfig = {};
      options.forEach(function (item, index) {
        if (optionsRequirements[index]) {
          valueData.validationConfig[item] =
            Number(optionsRequirements[index]);
        }
      });
    }
    return valueData;
  });
}

/**
 * @deprecated Use CustomAttributeObject API to get access to the necessary custom
 * attribute field and make some manipulations with it.
 * @param {*} field
 * @return {*}
 */
function isEvidenceRequired(field) {
  const fieldValidationConf = field.attr(`validationConfig.${field.value}`);
  return ddValidationValueToMap(fieldValidationConf).attachment;
}

/**
 * @deprecated Use CustomAttributeObject API to get access to the necessary custom
 * attribute field and make some manipulations with it.
 * @param {*} field
 * @return {*}
 */
function isCommentRequired(field) {
  const fieldValidationConf = field.attr(`validationConfig.${field.value}`);
  return ddValidationValueToMap(fieldValidationConf).comment;
}

function isUrlRequired(field) {
  const fieldValidationConf = field.attr(`validationConfig.${field.value}`);
  return ddValidationValueToMap(fieldValidationConf).url;
}
/**
 * @deprecated Use CustomAttributeObject API to get access to the necessary custom
 * attribute field and make some manipulations with it.
 * Converts value from UI controls back to CA value.
 * @param {String} type - Custom attribute type
 * @param {Object} value - Control value
 * @param {Object} defaultValue - Control default value
 * @return {Object} Converted value
 */
function convertToCaValue(type, value, defaultValue) {
  if (type === 'checkbox') {
    return value ? '1' : '0';
  }

  return value || defaultValue;
}

/**
 * @deprecated Use CustomAttributeObject API to get access to the necessary custom
 * attribute field and make some manipulations with it.
 * Converts CA values array to form fields.
 * @param {canList|undefined} customAttributeValues - Custom attributes values
 * @return {Array} From fields array
 */
function convertValuesToFormFields(customAttributeValues) {
  return (customAttributeValues || new canList([]))
    .map(convertToEditableField);
}

/**
 * @deprecated Use CustomAttributeObject API to get access to the necessary custom
 * attribute field and make some manipulations with it.
 * @param {*} attr
 * @return {*}
 */
function convertToFormViewField(attr) {
  let options = attr.def.multi_choice_options;
  return {
    type: attr.attributeType,
    id: attr.def.id,
    required: attr.def.mandatory,
    value: convertFromCaValue(
      attr.attributeType,
      attr.attribute_value,
      attr.attribute_object
    ),
    title: attr.def.title,
    placeholder: attr.def.placeholder,
    options: options &&
    typeof options === 'string' ?
      options.split(',') : [],
    helptext: attr.def.helptext,
  };
}
/**
 * @deprecated Use CustomAttributeObject API to get access to the necessary custom
 * attribute field and make some manipulations with it.
 * @param {*} attr
 * @return {*}
 */
function convertToEditableField(attr) {
  let options = attr.def.multi_choice_options;
  return {
    type: attr.attributeType,
    id: attr.def.id,
    value: convertFromCaValue(
      attr.attributeType,
      attr.attribute_value,
      attr.attribute_object
    ),
    title: attr.def.title,
    placeholder: attr.def.placeholder,
    options: options &&
    typeof options === 'string' ?
      options.split(',') : [],
    helptext: attr.def.helptext,
    validation: attr.validation.attr(),
    validationConfig: attr.validationConfig,
    errorsMap: attr.errorsMap.attr(),
    valueId: canCompute(function () {
      return attr.attr('id');
    }),
  };
}

/**
 * @deprecated Use CustomAttributeObject API to get access to the necessary custom
 * attribute field and make some manipulations with it.
 * Gets local or global custom attributes from the instance
 * @param  {canMap} instance object instance
 * @param  {Number}  type     types of custom attributes we want to get
 *                            can be either CUSTOM_ATTRIBUTE_TYPE.LOCAL or
 *                            CUSTOM_ATTRIBUTE_TYPE.GLOBAL
 * @return {Array}            Array of filtered custom attributes
 */
function getCustomAttributes(instance, type) {
  let filterFn;
  let values = instance && instance.attr('custom_attribute_values') || [];
  switch (type) {
    case CUSTOM_ATTRIBUTE_TYPE.LOCAL:
      filterFn = function (v) {
        return v.def.definition_id !== null;
      };
      break;
    case CUSTOM_ATTRIBUTE_TYPE.GLOBAL:
      filterFn = function (v) {
        return v.def.definition_id === null;
      };
      break;
    default:
      throw new Error('Unknown attributes type ' + type);
  }
  return values
    .filter(filterFn)
    .sort(sortCustomAttributes);
}

/**
 * @deprecated Use CustomAttributeObject API to get access to the necessary custom
 * attribute field and make some manipulations with it.
 * @param {*} ca
 * @param {*} value
 */
function setCustomAttributeValue(ca, value) {
  if (ca.attr('attributeType') === 'person') {
    let attributeObject = value ? {id: value, type: 'Person'} : null;

    ca.attr('attribute_value', 'Person');
    ca.attr('attribute_object', attributeObject);
  } else {
    let convertedValue = convertToCaValue(
      ca.attr('attributeType'),
      value,
      ca.def.default_value);
    ca.attr('attribute_value', convertedValue);
  }
}

/**
 * @deprecated Use CustomAttributeObject API to get access to the necessary custom
 * attribute field and make some manipulations with it.
 * @param {*} values
 * @param {*} changes
 */
function applyChangesToCAValue(values, changes) {
  canMap.keys(changes).forEach(function (fieldId) {
    values.each(function (item, key) {
      if (item.def.id === Number(fieldId)) {
        if (!item) {
          console.error(`Corrupted Date: ${values}`);
          return;
        }
        setCustomAttributeValue(item, changes[fieldId]);
        values.splice(key, 1, values[key]);
      }
    });
  });
}

function getLCAPopupTitle(validationMap) {
  let fixedValidationMap = Object.assign({}, validationMap);

  if (validationMap.evidence) {
    fixedValidationMap.attachment = true;
  }

  return LCA_DROPDOWN_TITLES_MAP[ddValidationMapToValue(fixedValidationMap)];
}

export {
  convertFromCaValue,
  convertToCaValue,
  convertValuesToFormFields,
  prepareCustomAttributes,
  getCustomAttributes,
  getCustomAttributeType,
  isEvidenceRequired,
  isCommentRequired,
  isUrlRequired,
  convertToFormViewField,
  applyChangesToCAValue,
  CUSTOM_ATTRIBUTE_TYPE,
  CA_DD_FLAGS,
  ddValidationValueToMap,
  ddValidationMapToValue,
  getLCAPopupTitle,
  setCustomAttributeValue,
};
