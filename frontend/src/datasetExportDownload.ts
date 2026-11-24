/** B5: admit only the bounded bytes described by the local export response.
 * A matching digest detects corruption/mismatch, not an independent signature.
 * Native publication must still verify authoritative backend provenance and consent.
 */
export const MAX_DATASET_EXPORT_BYTES=75*1024*1024;
export type DatasetExportRequest={
  version:number;
  format:'csv'|'xlsx';
  columns?:string[]|null;
  filters?:readonly unknown[];
};
export type VerifiedDatasetDownload={
  blob:Blob;filename:string;format:'csv'|'xlsx';version:number;
  expectedBytes:number;sha256:string;rows:number;
};
const INVALID='Dataset export metadata or bytes do not match the requested export. No file was downloaded.';
function decimal(value:string|null):number {
  if(value===null||!/^(0|[1-9][0-9]*)$/.test(value))throw new Error(INVALID);
  const n=Number(value);
  if(!Number.isSafeInteger(n))throw new Error(INVALID);
  return n;
}

export async function verifyDatasetDownload(response:Response,request:DatasetExportRequest):Promise<VerifiedDatasetDownload>{
  let reader:ReadableStreamDefaultReader<Uint8Array>|undefined;
  try{
    if(response.status!==200||!Number.isSafeInteger(request.version)||request.version<0||
       (request.format!=='csv'&&request.format!=='xlsx'))throw new Error(INVALID);
    const version=decimal(response.headers.get('x-pilotodin-dataset-version'));
    const expectedBytes=decimal(response.headers.get('content-length'));
    const rows=decimal(response.headers.get('x-pilotodin-exported-rows'));
    const sha256=response.headers.get('x-pilotodin-export-sha256')??'';
    const disposition=response.headers.get('content-disposition')??'';
    const filename=/^attachment; filename="([A-Za-z0-9_-]{1,70}_cleaned_v[0-9]+(?:_filtered)?\.(?:csv|xlsx))"$/.exec(disposition)?.[1];
    const suffix='_cleaned_v'+request.version+(request.filters?.length?'_filtered':'')+'.'+request.format;
    const mime=(response.headers.get('content-type')??'').split(';')[0].trim().toLowerCase();
    const expectedMime=request.format==='csv'?'text/csv':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
    if(version!==request.version||expectedBytes<1||expectedBytes>MAX_DATASET_EXPORT_BYTES||
       !/^[a-f0-9]{64}$/.test(sha256)||!filename||!filename.endsWith(suffix)||mime!==expectedMime||
       !response.body||!globalThis.crypto?.subtle)throw new Error(INVALID);
    // Preallocate only after validating the declared cap. Never use unbounded
    // response.blob() or JSON byte arrays for an untrusted transfer.
    const bytes=new Uint8Array(expectedBytes);
    reader=response.body.getReader();
    let offset=0;
    for(;;){
      const {done,value}=await reader.read();
      if(done)break;
      if(value.byteLength>expectedBytes-offset)throw new Error(INVALID);
      bytes.set(value,offset);
      offset+=value.byteLength;
    }
    if(offset!==expectedBytes)throw new Error(INVALID);
    const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),
      b=>b.toString(16).padStart(2,'0')).join('');
    if(digest!==sha256)throw new Error(INVALID);
    const csv=bytes.length>=5&&bytes[0]===0xef&&bytes[1]===0xbb&&bytes[2]===0xbf&&
      bytes[bytes.length-2]===13&&bytes[bytes.length-1]===10;
    const xlsx=bytes.length>=4&&bytes[0]===0x50&&bytes[1]===0x4b&&bytes[2]===3&&bytes[3]===4;
    if(request.format==='csv'?!csv:!xlsx)throw new Error(INVALID);
    return {blob:new Blob([bytes],{type:expectedMime}),filename,format:request.format,version,expectedBytes,sha256,rows};
  }catch(error){
    // Cancel the response on metadata/stream refusal so the backend can settle
    // its owned transfer. Cancellation failure does not admit invalid bytes.
    try{if(reader)await reader.cancel();else await response.body?.cancel()}catch{}
    throw error;
  }finally{
    reader?.releaseLock();
  }
}
