/** Guards only disposable/read-only frontend Quality response ordering.
 * The server remains authoritative for dataset versions and write approval.
 */
export function createQualityReadGuard(){
  let snapshot=0,preview=0,highestVersion=-1;
  return {
    beginSnapshot():number{return ++snapshot;},
    currentSnapshotTicket():number{return snapshot;},
    isLatestSnapshot(ticket:number):boolean{return ticket>0&&ticket===snapshot;},
    acceptSnapshot(ticket:number,version:number):boolean{
      if(ticket!==snapshot||!Number.isSafeInteger(version)||version<0||version<highestVersion)
        return false;
      highestVersion=version;return true;
    },
    beginPreview():number{return ++preview;},
    isLatestPreview(ticket:number):boolean{return ticket>0&&ticket===preview;},
    invalidateAll():void{snapshot++;preview++;}
  };
}
