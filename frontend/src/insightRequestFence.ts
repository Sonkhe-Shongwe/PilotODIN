// One request owner per mounted panel. Context changes invalidate publication,
// not the underlying work. Never release a newer request from an old finally.
export function createInsightRequestFence(){
  type Ticket={scope:symbol};
  let scope:symbol|null=null;
  let active:Ticket|null=null;
  return {
    enter(){
      const entered=Symbol();
      scope=entered;
      return ()=>{if(scope===entered)scope=null};
    },
    begin():Ticket|null{
      if(scope===null||active!==null)return null;
      active={scope};
      return active;
    },
    isCurrent(ticket:Ticket){
      return active===ticket&&scope===ticket.scope;
    },
    finish(ticket:Ticket){
      if(active!==ticket)return false;
      active=null;
      return scope!==null;
    }
  };
}
