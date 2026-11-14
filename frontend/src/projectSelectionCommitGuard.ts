/**
 * Prevent an old asynchronous Studio project load from overwriting a newer
 * selection made in another tab while its GET requests were in flight.
 *
 * A direct, user-approved local switch may begin with a different selected
 * project ID, so the request may commit if the shared selection is unchanged
 * since it began OR already equals this request's project. A third ID means
 * another selection won: reject before resetting forms or writing storage.
 * No project data or draft values are read, persisted or sent by this helper.
 */
export function mayCommitProjectSelection(
  selectedWhenStarted:string,
  selectedNow:string,
  requestedId:string
):boolean{
  return !!requestedId&&(selectedNow===selectedWhenStarted||selectedNow===requestedId);
}
