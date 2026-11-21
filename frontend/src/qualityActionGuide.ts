/** A diagnostic finding is not a correction until the backend offers a proposal.
 * Approval still requires a separate version-bound receipt and user consent.
 */
export type GuidedQualityIssue={kind:string;decision:string;severity:string;proposal:unknown};
export function canReviewCorrection(issue:GuidedQualityIssue):boolean{
 return issue.proposal!==null&&issue.proposal!==undefined&&
  ['pending','undone','rejected'].includes(issue.decision);
}
export function actionDescription(issue:GuidedQualityIssue):string{
 if(canReviewCorrection(issue))return 'Correction available';
 if(issue.decision==='approved')return 'Already approved';
 if(issue.kind==='missing')return 'Investigation only; no direct correction';
 if(issue.severity==='information')return 'Information only';
 return 'Review evidence; no direct correction';
}
export function medianTreatmentHint(isOffered:boolean):string{
 return isOffered
  ?'Median fill is available for this numeric column. Review the trade-offs before requesting approval.'
  :'No median-fill action is offered for this column. Median filling requires an eligible numeric column with observed values. The listed alternatives are advice, not approval buttons.';
}
