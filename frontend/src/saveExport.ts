import {save} from '@tauri-apps/plugin-dialog';
import {writeFile} from '@tauri-apps/plugin-fs';

/**
 * Save an already authenticated export without putting the desktop session
 * token in a URL. The native Save As dialog scopes file access to the user's
 * explicitly selected file; there is no blanket filesystem permission.
 */
export async function saveExport(blob:Blob, filename:string):
  Promise<'saved'|'cancelled'|'requested'> {
  if ('__TAURI_INTERNALS__' in window) {
    const extension = filename.toLowerCase().split('.').pop() ?? '';
    if (!['csv','xlsx','pdf','html'].includes(extension)) {
      throw new Error('Unsupported export file extension');
    }
    const target = await save({
      title:'Save PilotODIN export',
      defaultPath:filename,
      filters:[{name:extension.toUpperCase()+' files',extensions:[extension]}]
    });
    if (target===null) return 'cancelled';
    // Typed binary bytes support CSV, XLSX, HTML and PDF without content loss.
    await writeFile(target,new Uint8Array(await blob.arrayBuffer()));
    return 'saved';
  }

  // Existing source-development browser mode retains browser downloads.
  const url=URL.createObjectURL(blob);
  try{
    const anchor=document.createElement('a');
    anchor.href=url;anchor.download=filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    return 'requested';
  }finally{
    window.setTimeout(()=>URL.revokeObjectURL(url),60000);
  }
}
