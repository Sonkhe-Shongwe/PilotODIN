/** Presentation-only local wall clock. Not an authoritative audit timestamp. */
export interface ShellClockReadout {
 time: string;
 date: string;
 fullDescription: string;
}

export function formatShellClock(now: Date, locale?: string): ShellClockReadout {
 const timeFormatter = new Intl.DateTimeFormat(locale,{hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
 const timeParts = timeFormatter.formatToParts(now);
 const hour = timeParts.find(item=>item.type==='hour')?.value ?? '00';
 const minute = timeParts.find(item=>item.type==='minute')?.value ?? '00';
 const short = (options: Intl.DateTimeFormatOptions)=>
  new Intl.DateTimeFormat(locale,options).format(now).replace(/\.$/,'').toLocaleUpperCase(locale);
 const weekday = short({weekday:'short'});
 const day = new Intl.DateTimeFormat(locale,{day:'2-digit'}).format(now);
 const month = short({month:'short'});
 const fullDescription = new Intl.DateTimeFormat(locale,{
  weekday:'long',year:'numeric',month:'long',day:'numeric',
  hour:'2-digit',minute:'2-digit',hourCycle:'h23',timeZoneName:'long'
 }).format(now);
 return {time:`${hour}:${minute}`,date:`${weekday} · ${day} ${month}`,fullDescription};
}

/** Recheck just after the next local minute boundary, without constant polling. */
export function msUntilNextClockMinute(timestampMs:number):number {
 const elapsed = ((timestampMs % 60000) + 60000) % 60000;
 return 60000 - elapsed + 35;
}
