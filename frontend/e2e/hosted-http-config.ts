// Only existing disposable real-HTTP workflows may prepare this environment.
// The trusted fixture coordinator supplies the private capability to Vite and
// its owned backend. Browser and auxiliary audit children receive only the
// explicit non-serving environment below; no capability in config or traces.
import {randomBytes} from 'node:crypto';
import {resolve} from 'node:path';

export function prepareHostedHttp(){
 const env=process.env;
 if(env.CI!=='true'||env.GITHUB_ACTIONS!=='true'||env.P1_REAL_HTTP_E2E!=='1'||
    !/^\d+$/.test(env.GITHUB_RUN_ID??'')||!env.RUNNER_TEMP||
    env.PILOTODIN_HOME!==resolve(env.RUNNER_TEMP,'pilotodin-p1-real-http-'+env.GITHUB_RUN_ID)){
   throw Error('Explicit disposable hosted browser fixture required');
 }
 if(env.PILOTODIN_DESKTOP_SESSION||env.PILOTODIN_DESKTOP_PORT||
    (env.PILOTODIN_DESKTOP_ALLOW_DEV??'0')!=='0')throw Error('Mixed hosted serving configuration');
 if(env.PILOTODIN_DEV_CAPABILITY!==undefined&&!/^[0-9a-f]{64}$/.test(env.PILOTODIN_DEV_CAPABILITY)){
   throw Error('Invalid hosted fixture capability');
 }
 env.PILOTODIN_DEV_CAPABILITY??=randomBytes(32).toString('hex');
 env.PILOTODIN_SERVER_MODE='hosted-fixture';
 env.PILOTODIN_DEV_PORT='8000';
 env.PILOTODIN_DEV_ORIGIN='http://127.0.0.1:5178';
 env.VITE_PILOTODIN_AUTH_DEV='1';
}

// The hosted real-HTTP suites run on Linux CI. Do not copy the ambient process
// environment into Chromium: the coordinator holds a private serving credential.
// Keep only ordinary runtime inputs, not runner tokens or PilotODIN flags.
const childRuntimeKeys=[
 'PATH','HOME','USER','LOGNAME','LANG','LC_ALL','LC_CTYPE','TZ',
 'TMPDIR','TMP','TEMP','DISPLAY','WAYLAND_DISPLAY','XAUTHORITY',
 'XDG_RUNTIME_DIR','XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME',
 'XDG_DATA_DIRS','LD_LIBRARY_PATH',
] as const;
function selectedChildEnvironment(env:NodeJS.ProcessEnv,keys:readonly string[]):Record<string,string>{
 const selected:Record<string,string>={};
 for(const key of keys){
   const value=env[key];
   if(typeof value==='string')selected[key]=value;
 }
 return selected;
}
export function hostedBrowserEnvironment(env:NodeJS.ProcessEnv=process.env):Record<string,string>{
 return selectedChildEnvironment(env,childRuntimeKeys);
}
// Auxiliary Python fixture guards still require the exact CI allocation
// witness and Python runtime. They do not require the private HTTP capability.
export function hostedAuditEnvironment(env:NodeJS.ProcessEnv=process.env):Record<string,string>{
 return selectedChildEnvironment(env,[...childRuntimeKeys,'CI','GITHUB_ACTIONS',
  'P1_REAL_HTTP_E2E','GITHUB_RUN_ID','RUNNER_TEMP','PILOTODIN_HOME','PYTHONDONTWRITEBYTECODE']);
}
