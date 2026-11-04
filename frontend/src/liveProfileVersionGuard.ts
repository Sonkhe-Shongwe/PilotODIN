/** Quality versions are monotonic, including after an approved restore.
 * Prevent out-of-order read-only live-profile replies from rolling back a
 * verified project's visible dataset or accepting stale experiment metadata.
 */
export function createLiveProfileVersionGuard(initialProjectId='',initialVersion=0){
  let activeProjectId=initialProjectId;
  let latestVersion=Number.isSafeInteger(initialVersion)&&initialVersion>=0?initialVersion:0;
  const valid=(v:number)=>Number.isSafeInteger(v)&&v>=0;
  return {
    reset(projectId:string,version:number):void{
      if(!projectId||!valid(version))throw new Error('Invalid verified profile version.');
      activeProjectId=projectId;latestVersion=version;
    },
    accept(projectId:string,version:number):boolean{
      if(!projectId||projectId!==activeProjectId||!valid(version)||version<latestVersion)return false;
      latestVersion=version;return true;
    },
    isCurrent(projectId:string,version:number):boolean{
      return !!projectId&&projectId===activeProjectId&&valid(version)&&version===latestVersion;
    },
    snapshot(){return {projectId:activeProjectId,version:latestVersion};}
  };
}
