/** Explicitly user-authored report outlines. No AI, numerical claims or
 * automatically generated conclusions enter a frozen evidence-backed report.
 * Sections are plain text so existing HTML/PDF exporters keep one narrative.
 */
export const REPORT_OUTLINES = [
 {id:'analysis',label:'General analysis',headings:[
  'Purpose and decision',
  'Verified evidence interpretation',
  'Limitations and uncertainty',
  'Recommendations and next steps',
 ]},
 {id:'quality',label:'Data quality review',headings:[
  'Purpose of quality review',
  'Verified quality findings',
  'Reviewed treatment decisions',
  'Limitations and follow-up',
 ]},
 {id:'model',label:'Model evaluation',headings:[
  'Prediction objective',
  'Held-out evaluation interpretation',
  'Model reliability and limitations',
  'Recommended validation',
 ]},
] as const;
export type ReportOutlineId=typeof REPORT_OUTLINES[number]['id'];

export function getReportOutline(id:ReportOutlineId){
 const found=REPORT_OUTLINES.find(item=>item.id===id);
 if(!found)throw new Error('Unknown report outline');
 return found;
}
export function canStartReportOutline(text:string):boolean {
 return text.trim().length===0;
}
export function createReportOutline(id:ReportOutlineId):string {
 const outline=getReportOutline(id);
 return outline.headings.join('\n\n')+'\n';
}
export function reportOutlineProgress(id:ReportOutlineId,text:string){
 const outline=getReportOutline(id),lines=text.replace(/\r\n/g,'\n').split('\n');
 const sections=outline.headings.map(heading=>({heading,count:0,content:''}));
 let current=-1;
 for(const line of lines){
  const index=sections.findIndex(section=>line.trim()===section.heading);
  if(index>=0){
   current=index;
   sections[index].count++;
  }else if(current>=0){
   sections[current].content+=line+'\n';
  }
 }
 const entries=sections.map(section=>({
  heading:section.heading,
  complete:section.count===1&&section.content.trim().length>0,
 }));
 const completeCount=entries.filter(entry=>entry.complete).length;
 return {entries,completeCount,total:entries.length,
  complete:completeCount===entries.length};
}
