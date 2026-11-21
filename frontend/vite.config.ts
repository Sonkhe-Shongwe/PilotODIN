import { defineConfig } from 'vite';

// Vite watches the frontend project root for HMR by default. The Rust/Cargo
// output directory is inside that root but must never be watched: on Windows
// MSVC holds freshly linked .dll files open briefly, causing chokidar EBUSY
// and aborting Tauri's beforeDevCommand partway through dependency builds.
//
// Keep watching application source as usual; exclude only generated Rust
// build products, irrespective of the selected Cargo build profile.
export default defineConfig({
  server: {
    watch: {
      ignored: [
        '**/src-tauri/target',
        '**/src-tauri/target/**',
      ],
    },
  },
});
