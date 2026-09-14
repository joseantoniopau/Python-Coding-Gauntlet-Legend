/* Native title controls with the real artwork renderer and an isolated DOM. */
import assert from 'node:assert/strict';
import {installStub,newCanvas} from './stub.mjs';
installStub();
const makeCanvas=document.createElement.bind(document), raf=new Map(), keys=new Set();
let rafId=0,observer=null,modalOpen=false,disconnected=0;
let size={width:1440,height:900};
class Element {
 constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.attributes={};this.style={};this.parentElement=null;this.classes=new Set();this.hidden=false;this.classList={toggle:(c,use)=>use?this.classes.add(c):this.classes.delete(c)};}
 appendChild(child){child.parentElement=this;this.children.push(child);return child;}
 remove(){if(this.parentElement)this.parentElement.children=this.parentElement.children.filter(c=>c!==this);this.parentElement=null;}
 setAttribute(k,v){this.attributes[k]=v;}getAttribute(k){return this.attributes[k]??null;}removeAttribute(k){delete this.attributes[k];}
 focus(){document.activeElement=this;this.onfocus?.();}
 getBoundingClientRect(){return {...size,top:0,left:0};}
}
document.createElement=tag=>tag==='canvas'?makeCanvas(tag):new Element(tag);
const layer=new Element('div'),modal=new Element('div'),aboutButton=new Element('button');
document.querySelector=sel=>sel==='#modal-bg.show'?(modalOpen?modal:null):sel==='#modal-bg'?modal:sel==='#modal button, #modal input, #modal select'?aboutButton:null;
globalThis.MutationObserver=class{constructor(fn){observer=fn;}observe(){}disconnect(){disconnected++;}};
globalThis.addEventListener=(kind,fn)=>{if(kind==='keydown')keys.add(fn);};
globalThis.removeEventListener=(kind,fn)=>{if(kind==='keydown')keys.delete(fn);};
globalThis.requestAnimationFrame=fn=>{raf.set(++rafId,fn);return rafId;};
globalThis.cancelAnimationFrame=id=>raf.delete(id);
function surface(){const cv=newCanvas();cv.parentElement=layer;cv.attributes={};cv.ownerDocument=document;cv.setAttribute=Element.prototype.setAttribute;cv.getAttribute=Element.prototype.getAttribute;cv.removeAttribute=Element.prototype.removeAttribute;layer.appendChild(cv);return cv;}
const {TitleScreen}=await import('../../web/js/title.js');
const selected=[],canvas=surface();
const title=new TitleScreen(canvas,{hasSave:true,onSelect:id=>{selected.push(id);if(id==='about')modalOpen=true;}});
title.resize();title.start();
assert.equal(canvas.attributes['aria-hidden'],'true');
assert.equal(title.menu.attributes['aria-label'],'Main menu');
assert.equal(title.menuRoot.children.find(n=>n.tagName==='H1').textContent,'Python Coding Gauntlet Legend — The Algorithm Realms');
assert.deepEqual(title.buttons.map(b=>b.textContent),['CONTINUE','NEW ARCHITECT','OPTIONS','ABOUT']);
assert.equal(document.activeElement,title.buttons[0]);
function key(key,target=title.buttons[title.index],other={}){const event={key,target,preventDefault(){this.prevented=true;},...other};for(const fn of keys)fn(event);return event;}
key('ArrowDown');assert.equal(document.activeElement,title.buttons[1]);assert.deepEqual(selected,['move']);
key('w',title.buttons[1],{metaKey:true});assert.equal(title.index,1,'Command-W remains a browser shortcut');
const enter=key('Enter');assert(!enter.prevented);assert.deepEqual(selected,['move'],'Native Enter must not activate twice');
title.buttons[1].onclick();title.buttons[1].onclick();key('Enter',canvas);assert.deepEqual(selected,['move','new'],'Fade latches new/continue once');
title.destroy();assert.equal(keys.size,0);assert.equal(raf.size,0);assert.equal(layer.children.length,1);assert.equal(canvas.getAttribute('aria-hidden'),null);assert(title.buttons.every(b=>b.onclick===null&&b.onfocus===null));
const about=new TitleScreen(canvas,{hasSave:false,reducedMotion:true,onSelect:id=>{selected.push(id);if(id==='about')modalOpen=true;}});
about.resize();about.start();assert.equal(raf.size,0,'Reduced motion draws once rather than keeping a clock');
assert.deepEqual(about.buttons.map(b=>b.textContent),['BEGIN THE TRIAL','OPTIONS','ABOUT']);
about.buttons[2].onclick();assert(about.menuRoot.inert);assert.equal(document.activeElement,aboutButton);
const count=selected.length;key('Enter',aboutButton);assert.equal(selected.length,count,'Modal owns Enter');
modalOpen=false;observer();assert(!about.menuRoot.inert);assert.equal(document.activeElement,about.buttons[2]);
for(const [width,height] of [[280,260],[375,300],[480,360],[1200,400],[1440,900]]){
 size={width,height};about.resize();const l=about.layout();
 assert(l.logoTop>=20,`${width}x${height} keeps title onscreen`);
 assert(l.menuTop>l.logoTop+l.cell*15.2+20,`${width}x${height} leaves space between subtitle and controls`);
 const rows=Math.ceil(about.options.length/(l.compact?2:1));assert(l.menuTop+rows*46+(rows-1)*6<=height-35,'Controls fit above instructions');
 assert.equal(about.w,width,'Narrow screens do not inherit a 480px minimum');
}
about.stop();assert(about.menuRoot.hidden);about.start();assert(!about.menuRoot.hidden);about.destroy();assert.equal(disconnected,2);assert.equal(keys.size,0);
console.log('title menu: native labels/focus, arrows+Tab semantics, single activation, modal handoff, reduced motion, 280–1440px layouts, teardown verified');
