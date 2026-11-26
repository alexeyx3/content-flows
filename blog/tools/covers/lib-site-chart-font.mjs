/** Fonts bundled by www-astro, converted from its WOFF2 assets to TTF. */
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import opentype from 'opentype.js';

export function createSiteChartFont(assetsDir,name) {
  const bytes=readFileSync(join(assetsDir,name));
  const face=opentype.parse(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength));
  const glyphOf=ch=>{
    const glyph=face.charToGlyph(ch);
    if(glyph.index===0) throw Error(`Missing chart-font glyph: ${ch}`);
    return glyph;
  };
  const widthOf=(value,size)=>[...String(value)].reduce((sum,ch)=>sum+glyphOf(ch).advanceWidth*size/face.unitsPerEm,0);
  const pathOf=(value,x,y,size,fill)=>{
    const parts=[];
    let cursor=0;
    for(const ch of String(value)){
      const glyph=glyphOf(ch),scale=size/face.unitsPerEm;
      const d=glyph.getPath(0,0,face.unitsPerEm).toPathData(2);
      if(d.includes('NaN')) throw Error(`NaN chart-font glyph: ${ch}`);
      if(d) parts.push(`<path d="${d}" transform="translate(${(x+cursor).toFixed(2)} ${y.toFixed(2)}) scale(${scale.toFixed(5)})"/>`);
      cursor+=glyph.advanceWidth*scale;
    }
    return `<g fill="${fill}">${parts.join('')}</g>`;
  };
  const wrap=(value,size,maxWidth)=>{
    const lines=[];
    let line='';
    for(const word of String(value).split(/\s+/)){
      const candidate=line?`${line} ${word}`:word;
      if(line && widthOf(candidate,size)>maxWidth){lines.push(line);line=word;}
      else line=candidate;
    }
    if(line)lines.push(line);
    return lines;
  };
  return {widthOf,pathOf,wrap};
}
