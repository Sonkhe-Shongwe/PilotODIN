// Private server-side Vite middleware for the explicitly paired Live Dev launcher.
// A local dev frontdoor, not authentication against a hostile process running
// as the developer. Browser cross-site/DNS rebinding requests are refused.
import http from 'node:http';
import {isAbsolute, basename, dirname, resolve} from 'node:path';

const LIVE_ORIGIN='http://127.0.0.1:5173';
const HOSTED_ORIGIN='http://127.0.0.1:5178';
const REPORT_CHAIN_ORIGIN='http://127.0.0.1:5176';
const METHODS=new Set(['GET','HEAD','POST','PUT','PATCH','DELETE']);
const UNIQUE=new Set(['host','origin','referer','sec-fetch-site','x-pilotodin-dev-request',
  'content-type','content-length','transfer-encoding']);
const REQUEST_HEADERS=['accept','content-type','content-length'];
const RESPONSE_HEADERS=['content-type','content-length','content-disposition','content-encoding',
  'x-pilotodin-dataset-version','x-pilotodin-exported-rows','x-pilotodin-export-sha256',
  'x-pilotodin-export-project','x-pilotodin-export-operation','x-pilotodin-export-mac'];

export function liveDevProxyTrust(env){
  const live=env.PILOTODIN_SERVER_MODE==='dev'&&env.PILOTODIN_DEV_ORIGIN===LIVE_ORIGIN;
  const hosted=env.PILOTODIN_SERVER_MODE==='hosted-fixture'&&env.PILOTODIN_DEV_ORIGIN===HOSTED_ORIGIN&&
    env.CI==='true'&&env.GITHUB_ACTIONS==='true'&&env.P1_REAL_HTTP_E2E==='1'&&
    /^\d+$/.test(env.GITHUB_RUN_ID??'')&&
    !!env.RUNNER_TEMP&&env.PILOTODIN_HOME===`${env.RUNNER_TEMP}/pilotodin-p1-real-http-${env.GITHUB_RUN_ID}`;
  const home=env.PILOTODIN_HOME??'',localAppData=env.LOCALAPPDATA??'';
  const rawPort=env.PILOTODIN_DEV_PORT??'',backendPort=Number(rawPort);
  const phasePorts={'P2-NATIVE-DELIVER-CONSENT':5177,'P2-NATIVE-TWO-WINDOW-DELIVER':5177,
    'P3-NATIVE-SEMANTIC-CONTEXT':5178,'P3-NATIVE-QUALITY-W5':5178};
  const runName=basename(dirname(home));
  const phase=Object.keys(phasePorts).find(key=>new RegExp('^'+key+'-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{10}$').test(runName));
  const fixed=env.PILOTODIN_SERVER_MODE==='local-devqa'&&phase!==undefined&&
    env.PILOTODIN_DEV_ORIGIN==='http://127.0.0.1:'+phasePorts[phase]&&rawPort==='8000'&&
    isAbsolute(home)&&isAbsolute(localAppData)&&
    !home.split(/[\\/]/).includes('..')&&!localAppData.split(/[\\/]/).includes('..')&&
    basename(home)==='workspace'&&resolve(dirname(dirname(home)))===resolve(localAppData,'PilotODIN','DevQA','runs');
  const chain=env.PILOTODIN_SERVER_MODE==='local-devqa'&&env.RL_invariant==='1'&&
    env.PILOTODIN_DEV_ORIGIN===REPORT_CHAIN_ORIGIN&&isAbsolute(home)&&isAbsolute(localAppData)&&
    !home.split(/[\\/]/).includes('..')&&!localAppData.split(/[\\/]/).includes('..')&&
    basename(home)==='workspace'&&/^P2-NATIVE-CHAIN-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{10}$/.test(basename(dirname(home)))&&
    resolve(dirname(dirname(home)))===resolve(localAppData,'PilotODIN','DevQA','runs')&&
    /^[1-9][0-9]{3,4}$/.test(rawPort)&&backendPort>=1024&&backendPort<=65535&&backendPort!==5176;
  if((!live&&!hosted&&!chain&&!fixed)||env.VITE_PILOTODIN_AUTH_DEV!=='1'||
     (!chain&&env.PILOTODIN_DEV_PORT!=='8000')||
     !/^[0-9a-f]{64}$/.test(env.PILOTODIN_DEV_CAPABILITY??'')||
     env.PILOTODIN_DESKTOP_SESSION||env.PILOTODIN_DESKTOP_PORT||
     env.PILOTODIN_DESKTOP_WATCH_STDIN||env.PILOTODIN_CONTROL_MODE||
     env.PILOTODIN_CONTROL_GENERATION||env.PILOTODIN_CONTROL_CAPABILITY||
     (env.PILOTODIN_DESKTOP_ALLOW_DEV??'0')!=='0'){
    throw new Error('Invalid isolated Live Dev proxy configuration');
  }
  if(fixed)return Object.freeze({capability:env.PILOTODIN_DEV_CAPABILITY,origin:env.PILOTODIN_DEV_ORIGIN,
    host:'127.0.0.1:'+phasePorts[phase],port:phasePorts[phase]});
  if(chain)return Object.freeze({capability:env.PILOTODIN_DEV_CAPABILITY,origin:REPORT_CHAIN_ORIGIN,
    host:'127.0.0.1:5176',port:5176,backendPort});
  return Object.freeze({capability:env.PILOTODIN_DEV_CAPABILITY,origin:env.PILOTODIN_DEV_ORIGIN,
    host:live?'127.0.0.1:5173':'127.0.0.1:5178',port:live?5173:5178});
}

// Raw headers are used before Node's combined-header view. Never forward
// credentials supplied by a browser/client, cookies, arbitrary destinations,
// proxy metadata, or hop-by-hop headers.
export function liveDevProxyPlan(req,trust){
  const url=req.url??'';
  if(!url.startsWith('/api/'))return url==='/api'||url.startsWith('/api?')?{status:403}:null;
  if(!METHODS.has(req.method)||req.socket?.remoteAddress!=='127.0.0.1'||
     /[\x00-\x20\x7f\\#]/.test(url)||!trust||!/^[0-9a-f]{64}$/.test(trust.capability??'')){
    return {status:403};
  }
  const raw=req.rawHeaders;
  if(!Array.isArray(raw)||raw.length%2!==0)return {status:400};
  const headers=Object.create(null);
  for(let i=0;i<raw.length;i+=2){
    const key=raw[i].toLowerCase(),value=raw[i+1];
    if(key==='forwarded'||key.startsWith('x-forwarded-')||
       key==='x-pilotodin-session'||key==='x-pilotodin-dev-capability'||key==='authorization'){
      return {status:403};
    }
    if(UNIQUE.has(key)&&Object.hasOwn(headers,key))return {status:400};
    headers[key]=value;
  }
  if(headers.host!==trust.host||headers['x-pilotodin-dev-request']!=='1'||
     (headers.origin!==undefined&&headers.origin!==trust.origin)||
     (headers['sec-fetch-site']!==undefined&&headers['sec-fetch-site']!=='same-origin')||
     (headers['sec-fetch-site']!=='same-origin'&&headers.origin!==trust.origin)){
    return {status:403};
  }
  if(headers.referer!==undefined){
    try{if(new URL(headers.referer).origin!==trust.origin)return {status:403};}
    catch{return {status:403};}
  }
  if(headers['content-length']!==undefined&&headers['transfer-encoding']!==undefined)return {status:400};
  const backendPort=trust.backendPort??8000;
  if(!Number.isInteger(backendPort)||backendPort<1024||backendPort>65535||
     (trust.backendPort!==undefined&&(trust.origin!==REPORT_CHAIN_ORIGIN||backendPort===5176)))return {status:403};
  const outgoing={host:'127.0.0.1:'+backendPort,origin:trust.origin,
    'x-pilotodin-dev-capability':trust.capability};
  for(const key of REQUEST_HEADERS)if(headers[key]!==undefined)outgoing[key]=headers[key];
  return {status:200,options:{hostname:'127.0.0.1',port:backendPort,path:url,
    method:req.method,headers:outgoing}};
}

function refuse(res,status){
  if(res.headersSent){res.destroy();return;}
  const body=JSON.stringify({detail:status===502
    ?'Could not connect to PilotODIN\'s local analytics service. Check that the PilotODIN Backend window is running, then try again.'
    :'Isolated Live Dev API request refused'});
  res.writeHead(status,{'content-type':'application/json','cache-control':'no-store'});
  res.end(body);
}

export function createLiveDevProxy(trust,request=http.request){
  return (req,res,next)=>{
    const plan=liveDevProxyPlan(req,trust);
    if(plan===null){next();return;}
    if(plan.status!==200){refuse(res,plan.status);return;}
    let upstream;
    try{
      upstream=request(plan.options,reply=>{
        // Never propagate a redirect (or arbitrary headers) to the browser.
        if(!reply.statusCode||(reply.statusCode>=300&&reply.statusCode<400)){
          reply.resume();refuse(res,502);return;
        }
        const headers={'cache-control':'no-store'};
        for(const key of RESPONSE_HEADERS)if(reply.headers[key]!==undefined)headers[key]=reply.headers[key];
        res.writeHead(reply.statusCode,headers);
        reply.on('error',()=>res.destroy());
        reply.pipe(res);
      });
      upstream.on('error',()=>refuse(res,502));
      req.on('aborted',()=>upstream.destroy());
      res.on('close',()=>{if(!res.writableEnded)upstream.destroy();});
      req.pipe(upstream);
    }catch{upstream?.destroy();refuse(res,502);}
  };
}
