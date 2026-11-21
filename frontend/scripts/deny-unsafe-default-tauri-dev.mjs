// P4-R06 defence in depth: raw Tauri dev with the production app identifier
// would use com.pilotodin.studio app-local-data/WebView profile by default.
// This hook runs before normal Tauri native development; it cannot provide
// protection against an explicitly bypassed/overridden Tauri CLI config.
console.error("STOP: Default Tauri native development uses PilotODIN production identity. " +
  "No native run is authorised. Use the guarded isolated-native-dev launcher " +
  "only following separate explicit owner approval.");
process.exit(2);
