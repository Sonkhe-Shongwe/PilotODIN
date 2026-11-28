/** Build an inert preview of the exact authenticated SAVED HTML revision.
 *
 * The report is already HTML-escaped by backend.reports.render_html. This
 * additionally enforces an opaque-origin sandbox (at the iframe call site)
 * and a locked-down content policy. No URLs, base href, script, iframe,
 * fonts or external styles are permitted to load in the preview frame.
 *
 * Not an HTML sanitizer for arbitrary outside documents. Never use this
 * for user-supplied raw HTML or permit sandbox="allow-scripts".
 */
export const MAX_SAVED_HTML_PREVIEW_CHARS=4_000_000;

const PREVIEW_POLICY='<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'none\'; connect-src \'none\'; img-src data:; font-src data:; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'; object-src \'none\'; frame-src \'none\'">';

export function savedReportPreviewDocument(raw:string):string {
 if(typeof raw!=='string'||raw.length===0||raw.length>MAX_SAVED_HTML_PREVIEW_CHARS)
  throw new Error('Saved HTML preview is empty or exceeds the local display limit.');
 if(!/^\s*<!doctype html>/i.test(raw)||!/<head(?:\s[^>]*)?>/i.test(raw)||!/<\/html>\s*$/i.test(raw))
  throw new Error('The saved report did not return a complete HTML document.');
 if(/<\s*(?:script|iframe|object|embed|base|link|form)\b/i.test(raw)||/<meta\b[^>]*http-equiv\s*=\s*["']?refresh\b/i.test(raw))
  throw new Error('The saved report contains unsupported active HTML.');
 // Only this already saved, locally generated HTML is displayed. Its inline
 // ReportLab-adjacent chart SVG and <style> are retained, but no network
 // resources or scripts are permitted by the frame's CSP.
 return raw.replace(/<head(?:\s[^>]*)?>/i,head=>head+PREVIEW_POLICY);
}
