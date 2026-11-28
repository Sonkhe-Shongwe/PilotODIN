/** P3-03b: display-only review states. No semantic truth or agreement judgement. */
export type FieldReviewState=
  'paired_unassessed'|'owner_without_system_hint'|'owner_description_missing';

export function fieldReviewState(
 column:string,
 hintedColumns:ReadonlySet<string>,
 describedColumns:ReadonlySet<string>,
):FieldReviewState{
 if(!describedColumns.has(column))return 'owner_description_missing';
 return hintedColumns.has(column)?'paired_unassessed':'owner_without_system_hint';
}

export function fieldReviewText(state:FieldReviewState):string{
 if(state==='paired_unassessed')
  return 'Not assessed: the system hint and user description are both unverified.';
 if(state==='owner_without_system_hint')
  return 'No system field hypothesis; user description unverified. Comparison not assessed.';
 return 'No user description; comparison unavailable.';
}
