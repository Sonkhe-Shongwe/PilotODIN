// Verification-only Tauri dev hook. The launcher has already selected and
// checked the fixed overlay. No listener, private credential or child process.
// Do not re-evaluate Tauri's own generated configuration environment here.
import {assertHostedFrontdoorContext} from "./native-dev-plan.mjs";
try {
  assertHostedFrontdoorContext(process.env);
  const origin="http://127.0.0.1:5173";
  const reply=await fetch(origin+"/api/health",{
    headers:{"X-PilotODIN-Dev-Request":"1",Origin:origin},
    redirect:"error",signal:AbortSignal.timeout(3000)
  });
  if(!reply.ok||(await reply.json()).status!=="ok")
    throw Error("Authenticated frontdoor unavailable.");
} catch {
  console.error("STOP: hosted native frontdoor verification refused.");
  process.exitCode=2;
}
