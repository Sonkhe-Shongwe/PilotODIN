/** One-purpose native window close consent. No fields or project data cross IPC.
 * The Rust close interceptor creates a one-use ticket and blocks native close
 * before this handler runs. Browser reload keeps its separate beforeunload guard.
 */
export const NATIVE_CLOSE_EVENT='pilotodin:native-close-requested';
export type NativeCloseRequest={token:string};
export const NATIVE_CLOSE_MESSAGE=
 'You have unsaved changes in the workspace. Closing this window will discard those changes. Close PilotODIN?';

export async function resolveNativeCloseRequest(
 payload:unknown,
 hasUnsavedForm:()=>boolean,
 ask:(message:string,token:string)=>boolean|Promise<boolean>,
 resolve:(token:string,approve:boolean)=>Promise<void>
):Promise<void> {
 if(!payload||typeof payload!=='object'||!('token' in payload))return;
 const token=(payload as {token:unknown}).token;
 // UUID v4 simple form from Rust, not an unrestricted native close command.
 if(typeof token!=='string'||!(/^[a-f0-9]{32}$/i.test(token)))return;
 let approve=false;
 try {
  // Await native dialog IPC: a Promise is never implicit consent.
  // Only the literal boolean true can authorize a native discard.
  approve=!hasUnsavedForm()||(await ask(NATIVE_CLOSE_MESSAGE,token))===true;
 }catch {
  // Faults in the dirty check or dialog must NEVER authorize discard.
  approve=false;
 }
 await resolve(token,approve);
}
