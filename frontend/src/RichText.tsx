/** Safe GFM-like markdown for model responses. No HTML injection or external renderer. */
import type {ReactNode} from 'react';

function unescapeEntities(v:string){
  return v.replace(/&#(x[0-9a-f]+|\d+);/gi,(_m,num:string)=>{
    const point=num.toLowerCase().startsWith('x')?parseInt(num.slice(1),16):parseInt(num,10);
    return point>0&&point<=0x10ffff?String.fromCodePoint(point):'';
  }).replace(/&nbsp;/gi,' ').replace(/&amp;/gi,'&').replace(/&lt;/gi,'<').replace(/&gt;/gi,'>');
}
function inline(input:string):ReactNode[]{
  return input.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\(https?:\/\/[^)]+\))/g).map((bit,i)=>{
    if(bit.startsWith('`')&&bit.endsWith('`'))return <code key={i}>{bit.slice(1,-1)}</code>;
    if(bit.startsWith('**')&&bit.endsWith('**'))return <strong key={i}>{bit.slice(2,-2)}</strong>;
    if(bit.startsWith('*')&&bit.endsWith('*'))return <em key={i}>{bit.slice(1,-1)}</em>;
    const m=bit.match(/^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/);
    if(m)return <a key={i} href={m[2]} target="_blank" rel="noopener noreferrer">{m[1]}</a>;
    return bit;
  });
}
const separator=(line:string)=>/^\|?\s*:?[-]{3,}:?(?:\s*\|\s*:?[-]{3,}:?)*\s*\|?$/.test(line.trim());
const cell=(line:string)=>line.trim().replace(/^\|/,'').replace(/\|$/,'').split('|').map(s=>s.trim());
export function RichText({text}:{text:string}){
  const normal=unescapeEntities(text).replace(/\\([#*`<>])/g,'$1').replace(/<br\s*\/?\s*>/gi,'\n').replace(/\r/g,'');
  const lines=normal.split('\n');const blocks:ReactNode[]=[];let pos=0;
  while(pos<lines.length){
    const line=lines[pos].trim();
    if(!line){pos++;continue}
    const heading=line.match(/^(#{1,4})\s+(.+)$/);
    if(heading){blocks.push(<h3 key={pos} className="ai-heading">{inline(heading[2])}</h3>);pos++;continue}
    if(line.startsWith('|')&&pos+1<lines.length&&separator(lines[pos+1])){
      const start=pos;const headers=cell(lines[pos]);pos+=2;const rows:string[][]=[];
      while(pos<lines.length&&lines[pos].trim().startsWith('|')){rows.push(cell(lines[pos]));pos++}
      blocks.push(<div className="table-scroll ai-table" key={start}><table><thead><tr>{headers.map((v,j)=><th key={j}>{inline(v)}</th>)}</tr></thead><tbody>{rows.map((r,i)=><tr key={i}>{headers.map((_,j)=><td key={j}>{inline(r[j]??'')}</td>)}</tr>)}</tbody></table></div>);continue;
    }
    if(/^[-*]\s+|^\d+[.)]\s+/.test(line)){
      const ordered=/^\d+[.)]\s+/.test(line);const start=pos;const items:ReactNode[]=[];
      while(pos<lines.length&&(/^[-*]\s+|^\d+[.)]\s+/.test(lines[pos].trim()))){
        items.push(<li key={pos}>{inline(lines[pos].trim().replace(/^([-*]|\d+[.)])\s+/,''))}</li>);pos++;
      }
      blocks.push(ordered?<ol key={start}>{items}</ol>:<ul key={start}>{items}</ul>);continue;
    }
    if(line.startsWith('>')){blocks.push(<blockquote key={pos}>{inline(line.replace(/^>\s*/,''))}</blockquote>);pos++;continue}
    const start=pos;const paragraph=[line];pos++;
    while(pos<lines.length&&lines[pos].trim()&&!/^#{1,4}\s+|^[-*]\s+|^\d+[.)]\s+|^>\s*|^\|/.test(lines[pos].trim())){
      paragraph.push(lines[pos].trim());pos++;
    }
    blocks.push(<p key={start}>{inline(paragraph.join(' '))}</p>);
  }
  return <div className="rich-text">{blocks}</div>;
}
