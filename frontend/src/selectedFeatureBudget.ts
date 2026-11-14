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
  missing: number;
};
export type SelectedBudgetLimits = {
  labelled_rows: number;
  estimated_dense_mb_limit: number;
};
export type SelectedFeatureBudget = {
  includedFeatures: number;
  encodedColumnsByField: ReadonlyMap<string, number | null>;
  estimatedEncodedColumns: number;
  estimatedDenseTrainingMb: number;
  denseLimitExceeded: boolean;
};

export function selectedFeatureBudget(
  fields: readonly SelectedFeatureAudit[],
  limits: SelectedBudgetLimits,
  excluded: readonly string[],
  splitStrategy: 'random'|'group'|'time',
  splitColumn: string,
  categoricalImputation: 'most_frequent'|'constant' = 'most_frequent'
): SelectedFeatureBudget {
  const exclusions = new Set(excluded);
  const active = fields.filter(field => field.default_included &&
    !exclusions.has(field.column) &&
    (splitStrategy==='random' || field.column!==splitColumn));
  const encodedColumnsByField = new Map<string, number | null>();
  let width = 0;
  let valid = Number.isSafeInteger(limits.labelled_rows) && limits.labelled_rows>=0 &&
    Number.isFinite(limits.estimated_dense_mb_limit) && limits.estimated_dense_mb_limit>0;
  for (const field of active) {
    if (!Number.isSafeInteger(field.distinct) || field.distinct<=0 ||
        (field.kind!=='numeric' && field.kind!=='categorical')) {
      encodedColumnsByField.set(field.column, null);
      valid = false;
      continue;
    }
    const missingMarker = categoricalImputation==='constant' && field.missing>0;
    const columns = field.kind==='numeric' ? 1 : Math.min(25, field.distinct + Number(missingMarker));
    encodedColumnsByField.set(field.column, columns);
    width += columns;
  }
  const bytes = limits.labelled_rows*width*8;
  const safe = valid && Number.isSafeInteger(width) && Number.isSafeInteger(bytes);
  return {
    includedFeatures: active.length,
    encodedColumnsByField,
    estimatedEncodedColumns: valid ? width : 0,
    estimatedDenseTrainingMb: safe ? Math.round(bytes / (1024*1024)*100)/100 : 0,
    // No predictors is blocked by the existing backend's validate_config too.
    denseLimitExceeded: !safe || width===0 || bytes > limits.estimated_dense_mb_limit*1024*1024,
  };
}
