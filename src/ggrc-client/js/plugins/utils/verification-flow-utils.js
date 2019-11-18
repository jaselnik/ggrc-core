/*
 Copyright (C) 2019 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

import canMap from 'can-map';

const VERIFICATION_FLOWS = {
  STANDARD: 'STANDARD',
  SOX_302: 'SOX302',
  MULTI_LEVEL: 'MLV',
};

const getAssessmentFlows = () => {
  return Object.keys(VERIFICATION_FLOWS).map((key) => VERIFICATION_FLOWS[key]);
};

const isStandardFlow = (instance = canMap()) => {
  return instance.attr('verification_workflow') === VERIFICATION_FLOWS.STANDARD;
};

const isSox302Flow = (instance = canMap()) => {
  return instance.attr('verification_workflow') === VERIFICATION_FLOWS.SOX_302;
};

const isMultiLevelFlow = (instance = canMap()) => {
  return instance.attr('verification_workflow') ===
    VERIFICATION_FLOWS.MULTI_LEVEL;
};

export {
  isStandardFlow,
  isSox302Flow,
  isMultiLevelFlow,
  getAssessmentFlows,
};
