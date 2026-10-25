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
