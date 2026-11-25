import { defineConfig } from 'vite';
import {createLiveDevProxy, liveDevProxyTrust} from './scripts/live-dev-api-proxy.mjs';

// Vite watches the frontend project root for HMR by default. The Rust/Cargo
// output directory is inside that root but must never be watched: on Windows
// MSVC holds freshly linked .dll files open briefly, causing chokidar EBUSY
// and aborting Tauri's beforeDevCommand partway through dependency builds.
//
// Keep watching application source as usual; exclude only generated Rust
// build products, irrespective of the selected Cargo build profile.
export default defineConfig(({command,mode})=>{
  const intercepted=command==='serve'&&mode==='intercepted-fixture';
  if(intercepted&&Object.keys(process.env).some(key=>
      /^(?:PILOTODIN_|VITE_PILOTODIN_)/i.test(key))){
    throw new Error('Intercepted browser fixture must not inherit serving configuration');
  }
  // Only the explicit paired launcher enables this server-side middleware.
  // Never put the capability into define, envPrefix, HTML, or client code.
  const trust=command==='serve' && process.env.VITE_PILOTODIN_AUTH_DEV==='1'
    ? liveDevProxyTrust(process.env) : null;
  return {
  plugins:intercepted?[{name:'pilotodin-intercepted-fixture-deny-api',configureServer(server){
    // The browser route handler owns every mock response. If it is absent
    // or misses a request, Vite must never forward it or serve an API result.
    server.middlewares.use((req,res,next)=>{
      const pathname=(req.url??'').split('?')[0];
      if(pathname==='/api'||pathname.startsWith('/api/')){
        res.writeHead(403,{'content-type':'application/json','cache-control':'no-store'});
        res.end(JSON.stringify({detail:'Unintercepted synthetic API request refused'}));
        return;
      }
      next();
    });
  }}]:trust?[{name:'pilotodin-live-dev-api',configureServer(server){
    server.middlewares.use(createLiveDevProxy(trust));
  }}]:[],
  server: {
    ...(intercepted?{host:'127.0.0.1',port:5187,strictPort:true}:trust?{host:'127.0.0.1',port:trust.port,strictPort:true}:{}),
    watch: {
      ignored: [
        '**/src-tauri/target',
        '**/src-tauri/target/**',
      ],
    },
  },
  };
});
