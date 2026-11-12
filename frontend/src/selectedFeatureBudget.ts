/**
 * Client-side advisory *upper bound* matching backend/engine.py::training_resource_plan.
 * Server validates the selected labelled-only data and remains authoritative.
 * This never grants an experiment, prediction objective or training approval.
 */
export type SelectedFeatureAudit = {
  column: string;
  kind: 'numeric'|'categorical';
  distinct: number;
  default_included: boolean;
};
export type SelectedBudgetLimits = {
  labelled_rows: number;
  estimated_dense_mb_limit: number;
};
export type SelectedFeatureBudget = {
  includedFeatures: number;
  estimatedEncodedColumns: number;
  estimatedDenseTrainingMb: number;
  denseLimitExceeded: boolean;
};

export function selectedFeatureBudget(
  fields: readonly SelectedFeatureAudit[],
  limits: SelectedBudgetLimits,
  excluded: readonly string[],
  splitStrategy: 'random'|'group'|'time',
  splitColumn: string
): SelectedFeatureBudget {
  const exclusions = new Set(excluded);
  const active = fields.filter(field => field.default_included &&
    !exclusions.has(field.column) &&
    (splitStrategy==='random' || field.column!==splitColumn));
  const valid = Number.isSafeInteger(limits.labelled_rows) && limits.labelled_rows>=0 &&
    Number.isFinite(limits.estimated_dense_mb_limit) && limits.estimated_dense_mb_limit>0 &&
    active.every(field => Number.isSafeInteger(field.distinct) && field.distinct>0 &&
      (field.kind==='numeric'||field.kind==='categorical'));
  const width = valid ? active.reduce((sum, field) => sum +
    (field.kind==='numeric' ? 1 : Math.min(25,Math.max(1,field.distinct))),0) : 0;
  const bytes = limits.labelled_rows*width*8;
  const safe = valid && Number.isSafeInteger(width) && Number.isSafeInteger(bytes);
  return {
    includedFeatures: active.length,
    estimatedEncodedColumns: width,
    estimatedDenseTrainingMb: safe ? Math.round(bytes / (1024*1024)*100)/100 : 0,
    // No predictors is blocked by the existing backend's validate_config too.
    denseLimitExceeded: !safe || width===0 || bytes > limits.estimated_dense_mb_limit*1024*1024,
  };
}
