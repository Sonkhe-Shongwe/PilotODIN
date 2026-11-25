import { defineConfig } from 'vite';
import {createLiveDevProxy, liveDevProxyTrust} from './scripts/live-dev-api-proxy.mjs';

// Vite watches the frontend project root for HMR by default. The Rust/Cargo
// output directory is inside that root but must never be watched: on Windows
// MSVC holds freshly linked .dll files open briefly, causing chokidar EBUSY
// and aborting Tauri's beforeDevCommand partway through dependency builds.
//
// Keep watching application source as usual; exclude only generated Rust
// build products, irrespective of the selected Cargo build profile.
export default defineConfig(({command})=>{
  // Only the explicit paired launcher enables this server-side middleware.
  // Never put the capability into define, envPrefix, HTML, or client code.
  const trust=command==='serve' && process.env.VITE_PILOTODIN_AUTH_DEV==='1'
    ? liveDevProxyTrust(process.env) : null;
  return {
  plugins:trust?[{name:'pilotodin-live-dev-api',configureServer(server){
    server.middlewares.use(createLiveDevProxy(trust));
  }}]:[],
  server: {
    ...(trust?{host:'127.0.0.1',port:trust.port,strictPort:true}:{}),
    watch: {
      ignored: [
        '**/src-tauri/target',
        '**/src-tauri/target/**',
      ],
    },
  },
  };
});
