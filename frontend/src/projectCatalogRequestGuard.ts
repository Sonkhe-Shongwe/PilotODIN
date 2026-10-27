/** Prevent stale async project catalogue requests from overwriting newer shell state.
 * No dataset, project selection, or preferences are stored here.
 */
export function createProjectCatalogRequestGuard(){
  let latestRequest=0;
  return {
    begin():number{return ++latestRequest;},
    accepts(requestId:number):boolean{return requestId>0&&requestId===latestRequest;},
    invalidate():void{latestRequest++;}
  };
}
