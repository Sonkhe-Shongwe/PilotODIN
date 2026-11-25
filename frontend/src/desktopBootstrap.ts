import {invoke} from '@tauri-apps/api/core';
import {configureDesktopAPI, configureDevelopmentAPI, get} from './api';
import type {DesktopConnection} from './api';

// Tauri only makes this property available inside the native webview.
export function isDesktop(): boolean {
  return '__TAURI_INTERNALS__' in window;
}

export function isNativeA4SmokeMode(): boolean {
  // Only the source-controlled Vite development server may enable this mode.
  // It is compile-time false in every production Tauri/browser build.
  return import.meta.env.DEV && import.meta.env.VITE_PILOTODIN_NATIVE_SMOKE === '1';
}

export async function startDesktopBackend(): Promise<void> {
  if (!isDesktop()) return;
  if (isNativeA4SmokeMode()) {
    // A4 uses the existing paired Live Dev frontdoor through its isolated
    // Vite relay. Other explicitly migrated native QA uses the paired proxy.
    // Never spawn a bundled sidecar for a native smoke page.
    if (import.meta.env.VITE_PILOTODIN_AUTH_DEV !== '1' ||
        !['http://127.0.0.1:5174', 'http://127.0.0.1:5173'].includes(window.location.origin)) {
      throw new Error('Native smoke requires its authenticated isolated Live Dev frontdoor.');
    }
    configureDevelopmentAPI(window.location.origin);
  } else {
    const connection = await invoke<DesktopConnection>('launch_backend');
    configureDesktopAPI(connection);
  }
  // A Windows-packed Python runtime can take several seconds to initialise.
  // We actively check its health and give a useful failure message at timeout.
  const deadline = Date.now() + 45_000;
  while (Date.now() < deadline) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 1800);
      try {
        const health = await get<{status:string}>('/health', {signal:controller.signal});
        if (health.status === 'ok') return;
      } finally {clearTimeout(timeout);}
    } catch {
      // Expected until the Python sidecar is listening; retry shortly.
    }
    await new Promise(resolve => setTimeout(resolve, 350));
  }
  throw new Error('The analytical engine did not become ready within 45 seconds. Please try again or inspect the application logs.');
}
