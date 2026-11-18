import React,{createContext,useContext,useEffect,useLayoutEffect,useId,useRef,useState} from "react";
import {createPortal} from "react-dom";
import "./context-menu.css";

// The school shell supplies the commercial state; backend authorization remains authoritative.
export const ContextReadOnly = createContext(false);
const RowMenu = createContext(null);
const NATIVE = "input,textarea,select,option,a[href],[data-native-context],[contenteditable]:not([contenteditable='false'])";
export function availableContextActions(actions=[],readOnly=false){
  return actions.filter(a=>a && a.id && a.label && typeof a.run==="function" && !a.hidden && !(readOnly&&a.write));
}
function nativeTarget(event){
  return event.target instanceof Element && (event.target.closest(NATIVE) || Boolean(window.getSelection()?.toString().trim()));
}
function Menu({id,point,actions,close,invoke,portalTarget}){
  const menu=useRef(null);
  const [position,setPosition]=useState(point);
  useLayoutEffect(()=>{
    const el=menu.current;
    if(!el)return;
    const rect=el.getBoundingClientRect(), pad=8, viewport=window.visualViewport;
    const left=viewport?.offsetLeft||0, top=viewport?.offsetTop||0;
    const width=viewport?.width||window.innerWidth, height=viewport?.height||window.innerHeight;
    setPosition({x:Math.max(left+pad,Math.min(point.x,left+width-rect.width-pad)),
      y:Math.max(top+pad,Math.min(point.y,top+height-rect.height-pad))});
    (el.querySelector("button:not(:disabled)")||el).focus({preventScroll:true});
  },[point]);
  useEffect(()=>{
    const outside=e=>{if(!menu.current?.contains(e.target))close(false)};
    const dismiss=()=>close(false);
    const scroll=e=>{if(!(e.target instanceof Node)||!menu.current?.contains(e.target))dismiss()};
    document.addEventListener("pointerdown",outside,true);
    document.addEventListener("scroll",scroll,true);
    window.addEventListener("resize",dismiss);
    window.addEventListener("scroll",scroll,true);
    window.visualViewport?.addEventListener("resize",dismiss);
    window.visualViewport?.addEventListener("scroll",dismiss);
    window.addEventListener("blur",dismiss);
    return ()=>{document.removeEventListener("pointerdown",outside,true);
      document.removeEventListener("scroll",scroll,true);
      window.removeEventListener("scroll",scroll,true);
      window.visualViewport?.removeEventListener("resize",dismiss);
      window.visualViewport?.removeEventListener("scroll",dismiss);
      window.removeEventListener("resize",dismiss);window.removeEventListener("blur",dismiss)};
  },[close]);
  function key(e){
    if(e.key==="Escape"){e.preventDefault();e.stopPropagation();close(true);return}
    if(e.key==="Tab"){close(true);return}
    if(!["ArrowDown","ArrowUp","Home","End"].includes(e.key))return;
    e.preventDefault();e.stopPropagation();
    const items=[...menu.current.querySelectorAll("button:not(:disabled)")];
    if(!items.length)return;
    const i=items.indexOf(document.activeElement);
    const next=e.key==="Home"?0:e.key==="End"?items.length-1:e.key==="ArrowDown"?(i+1)%items.length:(i<=0?items.length-1:i-1);
    items[next].focus();
  }
  return createPortal(<div ref={menu} id={id} tabIndex={-1} className="yem-context-menu" role="menu" aria-label="Actions contextuelles"
    style={{left:position.x,top:position.y}} onKeyDown={key} onClick={e=>e.stopPropagation()}
    onContextMenu={e=>{e.preventDefault();e.stopPropagation()}}>
    {actions.map(a=><button key={a.id} type="button" role="menuitem" tabIndex={-1} disabled={!!a.disabled}
      className={a.danger?"yem-context-danger":""} onClick={()=>invoke(a.id)}>{a.label}</button>)}
  </div>,portalTarget||document.body);
}
export function ContextTrigger({className="",label="Ouvrir les actions contextuelles"}){
  const value=useContext(RowMenu);
  if(!value?.enabled)return null;
  return <button type="button" className={"yem-context-trigger "+className} aria-label={label}
    aria-haspopup="menu" aria-expanded={value.open} aria-controls={value.open?value.id:undefined} onClick={e=>{
      e.preventDefault();e.stopPropagation();
      const r=e.currentTarget.getBoundingClientRect();
      value.show({x:r.left,y:r.bottom},e.currentTarget);
    }}>⋯</button>;
}
// Opt-in only. Existing native controls and form submit behavior are preserved.
export function ContextTarget({as:Tag="div",actions=[],showTrigger=false,children,onContextMenu,onKeyDown,...props}){
  const readOnly=useContext(ContextReadOnly);
  const list=availableContextActions(actions,readOnly);
  const enabled=list.some(a=>!a.disabled);
  const [point,setPoint]=useState(null);
  const anchor=useRef(null),root=useRef(null),invoked=useRef(false),currentActions=useRef(list);
  currentActions.current=list;
  const id=useId();
  const signature=list.map(a=>a.id+":"+Boolean(a.disabled)).join("|");
  useLayoutEffect(()=>{setPoint(null)},[signature]);
  const close=React.useCallback((restore=false)=>{
    setPoint(null);
    if(restore&&anchor.current?.isConnected)anchor.current.focus({preventScroll:true});
  },[]);
  useEffect(()=>{
    if(!point)return;
    const dismiss=()=>close(false);
    window.addEventListener("yem:context-open",dismiss);
    return()=>window.removeEventListener("yem:context-open",dismiss);
  },[point,close]);
  function show(p,element){
    if(!enabled)return;
    window.dispatchEvent(new Event("yem:context-open"));
    invoked.current=false;anchor.current=element;setPoint(p);
  }
  function invoke(id){
    if(invoked.current)return;
    const action=currentActions.current.find(a=>a.id===id&&!a.disabled);
    invoked.current=true;
    close(true);
    if(action&&root.current?.isConnected)action.run();
  }
  function context(e){
    onContextMenu?.(e);
    if(e.defaultPrevented||!enabled||nativeTarget(e))return;
    e.preventDefault();e.stopPropagation();
    const r=e.currentTarget.getBoundingClientRect();
    show({x:e.clientX||r.left,y:e.clientY||r.bottom},e.currentTarget);
  }
  function keyboard(e){
    onKeyDown?.(e);
    if(e.defaultPrevented||!enabled||nativeTarget(e))return;
    if(e.key!=="ContextMenu"&&!(e.shiftKey&&e.key==="F10"))return;
    e.preventDefault();e.stopPropagation();
    const r=e.currentTarget.getBoundingClientRect();
    show({x:r.left,y:r.top},e.target);
  }
  return <RowMenu.Provider value={{enabled,open:!!point,show,id}}>
    <Tag {...props} ref={root} tabIndex={enabled?(props.tabIndex??0):props.tabIndex} onContextMenu={context} onKeyDown={keyboard}>
      {children}{showTrigger&&<ContextTrigger/>}
    </Tag>
    {point&&enabled&&<Menu id={id} portalTarget={root.current?.closest("dialog[open]")} point={point} actions={list} close={close} invoke={invoke}/>}
  </RowMenu.Provider>;
}
