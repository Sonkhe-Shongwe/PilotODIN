/** Guards against stale async work from the previously selected project.
 * A new project transition or unmount invalidates every prior operation.
 * This does not cancel backend jobs; it prevents their replies crossing UI scopes.
 */
export function createProjectOperationGuard(){
  let activeId='';
  let epoch=0;
  return {
    begin(projectId:string):number {activeId=projectId;return ++epoch;},
    snapshot(projectId:string):number {return activeId===projectId?epoch:-1;},
    accepts(projectId:string,generation:number):boolean {
      return !!projectId&&activeId===projectId&&generation===epoch;
    },
    invalidate():void {activeId='';epoch++;}
  };
}
