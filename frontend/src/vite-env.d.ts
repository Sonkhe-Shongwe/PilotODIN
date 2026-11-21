/// <reference types="vite/client" />

// Compile-time Vite types for the opt-in, DEV-only native A4 smoke window.
// No runtime setting or production override is introduced by this declaration.
interface ImportMetaEnv {
  readonly VITE_PILOTODIN_NATIVE_SMOKE?: string;
}
