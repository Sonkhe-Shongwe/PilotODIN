/** Scope local feature-advice responses to their actual selection.
 * A previous target/project/Quality version must not leak a high-risk hint
 * into the current Prepare exclusion diff while a new request is in flight.
 * This function is side-effect free and never grants training approval.
 */
export type FeatureHint={column:string;risk:string;reasons:string[]};
export type ScopedFeatureHints={
 projectId:string;target:string;version:number;features:FeatureHint[]
};
export function visibleFeatureHints(
 snapshot:ScopedFeatureHints|null,
 projectId:string|undefined,
 target:string,
 version:number
):FeatureHint[]{
 return snapshot&&projectId&&target&&
  snapshot.projectId===projectId&&snapshot.target===target&&
  snapshot.version===version?snapshot.features:[];
}
