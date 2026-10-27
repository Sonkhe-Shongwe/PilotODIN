/** Prevent stale async project catalogue requests from overwriting newer shell state.
 * No dataset, project selection, or preferences are stored here.
 */
export function createProjectCatalogRequestGuard(){
  let nextRequest=0;
  let activeRequest=0;
  return {
    begin():number {activeRequest=++nextRequest;return activeRequest;},
    accepts(requestId:number):boolean {return requestId>0&&requestId===activeRequest;},
    invalidate():void {activeRequest=0;}
  };
}
