import { isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';

const repo = fileURLToPath(new URL('../../', import.meta.url));
const legacyDialog = fileURLToPath(new URL(
  '../../qa/p4_native/Invoke_P4_Native_Project_Switch_Dialog.ps1', import.meta.url,
));

export function projectSwitchCommand({ n12Journey, python, pid, action }) {
  if (n12Journey) {
    if (!python || !isAbsolute(python) || !/^[1-9][0-9]*$/.test(pid ?? '')) {
      throw new Error('The N12 driver requires the runner Python executable and staged app PID');
    }
    return {
      file: python,
      args: ['-B', '-m', 'qa.p4_research.n12_project_switch', '--pid', pid, '--action', action],
      cwd: repo,
    };
  }
  return {
    file: 'powershell.exe',
    args: ['-NoProfile', '-NonInteractive', '-STA', '-File', legacyDialog, '-Action', action],
  };
}
