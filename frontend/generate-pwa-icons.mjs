/* Generate actual PNG launcher icons in the official YEM green family.
   Pure Node.js 24: reproducible, no image dependency and no binary checked into git.
   This deliberately creates an app launcher icon, not a replacement for the logo in YEM UI.
*/
import fs from "node:fs";
import path from "node:path";
import {deflateSync} from "node:zlib";

const ROOT=path.join(process.cwd(),"frontend","public","icons");
fs.mkdirSync(ROOT,{recursive:true});

const letters={
  Y:["10001","10001","01010","00100","00100","00100","00100"],
  E:["11111","10000","10000","11110","10000","10000","11111"],
  M:["10001","11011","10101","10101","10001","10001","10001"],
};
function crc32(buffer){
  let n=0xffffffff;
  for(const byte of buffer){
    n^=byte;
    for(let k=0;k<8;k++)n=n&1?(n>>>1)^0xedb88320:n>>>1;
  }
  return(n^0xffffffff)>>>0;
}
function chunk(name,data){
  const tag=Buffer.from(name);
  const len=Buffer.alloc(4);len.writeUInt32BE(data.length);
  const crc=Buffer.alloc(4);crc.writeUInt32BE(crc32(Buffer.concat([tag,data])));
  return Buffer.concat([len,tag,data,crc]);
}
function icon(size){
  const raw=Buffer.alloc(size*(1+size*3));
  function point(x,y){
    const X=x/size,Y=y/size;
    let rgb=[27,102,76];
    const pad=.09,r=.18;
    const inside=X>pad&&X<1-pad&&Y>pad&&Y<1-pad;
    if(inside){
      rgb=[23,96,72];
      const line=(Math.min(X-pad,1-pad-X,Y-pad,1-pad-Y)<.013);
      if(line)rgb=[93,165,127];
    }
    // stylized open book in the center
    if(Y>.48&&Y<.79){
      const left=.5-(Y-.48)*.025;
      const span=.25;
      if(X>.5-span&&X<.499 && Y>.49-(X-.5)*.12 &&Y<.77-(.5-X)*.18)rgb=[255,255,255];
      if(X>.501&&X<.5+span&&Y>.49+(X-.5)*.12&&Y<.77-(X-.5)*.18)rgb=[225,243,233];
      if(Math.abs(X-.5)<.005)rgb=[27,102,76];
    }
    // pixel-safe bold YEM title above the open book
    const scale=.022;
    const startX=.5-((5*3+2*2)*scale)/2;
    const startY=.21;
    for(let i=0;i<3;i++){
      const word="YEM"[i],bitmap=letters[word];
      const lx=(X-startX-i*7*scale)/scale,ly=(Y-startY)/scale;
      const col=Math.floor(lx),row=Math.floor(ly);
      if(col>=0&&col<5&&row>=0&&row<7&&bitmap[row][col]==="1")rgb=[255,255,255];
    }
    return rgb;
  }
  for(let y=0;y<size;y++){
    const offset=y*(size*3+1);raw[offset]=0;
    for(let x=0;x<size;x++){
      const rgb=point(x+.5,y+.5);
      raw[offset+1+3*x]=rgb[0];raw[offset+2+3*x]=rgb[1];raw[offset+3+3*x]=rgb[2];
    }
  }
  const ihdr=Buffer.alloc(13);
  ihdr.writeUInt32BE(size,0);ihdr.writeUInt32BE(size,4);
  ihdr[8]=8;ihdr[9]=2;
  const png=Buffer.concat([
    Buffer.from("89504e470d0a1a0a","hex"),
    chunk("IHDR",ihdr),chunk("IDAT",deflateSync(raw,{level:9})),chunk("IEND",Buffer.alloc(0)),
  ]);
  fs.writeFileSync(path.join(ROOT,"icon-"+size+".png"),png);
}
icon(192);
icon(512);
