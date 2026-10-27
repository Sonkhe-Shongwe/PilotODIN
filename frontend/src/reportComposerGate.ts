/** Scoped to a single report composer. Does not cancel or roll back server writes. */
export type ComposerWriteKind='save'|'quality';
export type ComposerWriteTicket=Readonly<{id:number;view:number;draft:number;kind:ComposerWriteKind}>;

export class ReportComposerGate {
 private view=0;
 private draft=0;
 private next=0;
 private pending:ComposerWriteTicket|null=null;

 resetProject():void {this.view++;this.draft++;this.pending=null}
 navigate():void {this.view++;this.draft++}
 editDraft():void {this.draft++}
 hasPending():boolean {return this.pending!==null}
 currentView():number {return this.view}
 isCurrentView(token:number):boolean {return this.view===token}
 begin(kind:ComposerWriteKind):ComposerWriteTicket|null {
  if(this.pending!==null)return null;
  const ticket={id:++this.next,view:this.view,draft:this.draft,kind};
  this.pending=ticket;
  return ticket;
 }
 isActive(ticket:ComposerWriteTicket):boolean {return this.pending?.id===ticket.id}
 sameView(ticket:ComposerWriteTicket):boolean {
  return this.isActive(ticket)&&this.view===ticket.view;
 }
 sameDraft(ticket:ComposerWriteTicket):boolean {
  return this.sameView(ticket)&&this.draft===ticket.draft;
 }
 finish(ticket:ComposerWriteTicket):boolean {
  if(!this.isActive(ticket))return false;
  this.pending=null;
  return true;
 }
}

/** Independent latest-response channels. A token is not permission to mutate data. */
export class ReportReadGate {
 private evidence=0;
 private exporting=0;
 private previewing=0;
 beginEvidence():number {return ++this.evidence}
 isCurrentEvidence(ticket:number):boolean {return ticket===this.evidence}
 beginExport():number {return ++this.exporting}
 isCurrentExport(ticket:number):boolean {return ticket===this.exporting}
 beginPreview():number {return ++this.previewing}
 isCurrentPreview(ticket:number):boolean {return ticket===this.previewing}
 invalidatePreview():void {this.previewing++}
 invalidateAll():void {this.evidence++;this.exporting++;this.previewing++}
}
