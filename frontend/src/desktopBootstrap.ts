import {invoke} from '@tauri-apps/api/core';
import {configureDesktopAPI, get} from './api';

type DesktopConnection = {port:number;token:string};

// Tauri only makes this property available inside the native webview.
export function isDesktop(): boolean {
  return '__TAURI_INTERNALS__' in window;
}

export async function startDesktopBackend(): Promise<void> {
  if (!isDesktop()) return;
  const connection = await invoke<DesktopConnection>('launch_backend');
  configureDesktopAPI(connection);
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
