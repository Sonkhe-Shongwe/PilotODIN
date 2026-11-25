// Only existing disposable real-HTTP workflows may prepare this environment.
// Private capability is inherited by Vite and its owned backend, not placed in
// Playwright config/use/webServer.env, test trace, VITE_ variables or URLs.
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
