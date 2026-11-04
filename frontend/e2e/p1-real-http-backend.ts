/** CI-only Uvicorn process lifecycle for the disposable P1 real-HTTP test.
 *
 * The child process is started by THIS test and is the only process it can
 * terminate. Refuses a local developer run, arbitrary home, or occupied port.
 * Nothing in PilotODIN's production API exposes a shutdown/restart endpoint.
 */
import {spawn} from 'node:child_process';
import type {ChildProcess} from 'node:child_process';
import {existsSync,realpathSync} from 'node:fs';
import {createServer} from 'node:net';
import {resolve} from 'node:path';
import {setTimeout as sleep} from 'node:timers/promises';

export type DisposableBackend = {child:ChildProcess;pid:number;log:()=>string};
const BASE='http://127.0.0.1:8000/api/health';

function guardRunner():void{
  const env=process.env;
  if(env.CI!=='true'||env.GITHUB_ACTIONS!=='true'||env.P1_REAL_HTTP_E2E!=='1'
    ||!env.GITHUB_RUN_ID||!/^\d+$/.test(env.GITHUB_RUN_ID)
    ||!env.RUNNER_TEMP||!env.PILOTODIN_HOME){
    throw new Error('Backend lifecycle is restricted to dedicated GitHub CI.');
  }
  const runner=realpathSync(env.RUNNER_TEMP);
  const expected=resolve(runner,'pilotodin-p1-real-http-'+env.GITHUB_RUN_ID);
  const supplied=resolve(env.PILOTODIN_HOME);
  if(supplied!==expected||(existsSync(supplied)&&realpathSync(supplied)!==expected)){
    throw new Error('Refuse backend process operations outside the temporary CI workspace.');
  }
}

async function portUnoccupied():Promise<void>{
  const s=createServer();
  await new Promise<void>((resolveFree,reject)=>{
    s.once('error',reject);
    s.listen(8000,'127.0.0.1',()=>{
      s.removeListener('error',reject);
      s.close(error=>error?reject(error):resolveFree());
    });
  });
}

export async function startDisposableBackend():Promise<DisposableBackend>{
  guardRunner();
  await portUnoccupied(); // Never attach to or kill somebody else's service.
  const repoRoot=resolve(__dirname,'../..');
  const child=spawn('python',
    ['-m','uvicorn','backend.main:app','--host','127.0.0.1',
     '--port','8000','--no-access-log'],
    {cwd:repoRoot,env:{...process.env,PILOTODIN_DESKTOP_SESSION:'',
       PILOTODIN_DESKTOP_ALLOW_DEV:'0'},stdio:['ignore','pipe','pipe']});
  if(!child.pid)throw new Error('Temporary backend process did not start.');
  let recent='';
  for(const stream of [child.stdout,child.stderr]){
    stream?.on('data',(data:Buffer)=>{
      // Bounded private diagnostics; no dataset rows are logged.
      recent=(recent+data.toString('utf8')).slice(-2500);
    });
  }
  const handle={child,pid:child.pid,log:()=>recent};
  const until=Date.now()+25_000;
  while(Date.now()<until){
    if(child.exitCode!==null||child.signalCode!==null){
      throw new Error('Temporary backend exited before health check: '+recent);
    }
    try{
      const res=await fetch(BASE,{signal:AbortSignal.timeout(900)});
      if(res.status===200 && (await res.json()).status==='ok')return handle;
    }catch{/* The owned child can still be starting. */}
    await sleep(180);
  }
  await stopDisposableBackend(handle);
  throw new Error('Temporary backend did not become healthy: '+recent);
}

export async function stopDisposableBackend(handle:DisposableBackend):Promise<void>{
  guardRunner();
  const child=handle.child; // No PID search or arbitrary process signalling.
  if(child.exitCode===null&&child.signalCode===null){
    const exited=new Promise<void>(resolveExit=>{
      if(child.exitCode!==null||child.signalCode!==null)resolveExit();
      else child.once('exit',()=>resolveExit());
    });
    child.kill('SIGTERM');
    const completed=await Promise.race([exited.then(()=>true),sleep(8_000).then(()=>false)]);
    if(!completed){
      child.kill('SIGKILL'); // Kill only the child owned by this test.
      const killed=await Promise.race([exited.then(()=>true),sleep(3_000).then(()=>false)]);
      if(!killed)throw new Error('Owned disposable backend did not stop.');
    }
  }
  await portUnoccupied();
}
