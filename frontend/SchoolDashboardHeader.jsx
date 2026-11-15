import React, {useEffect,useRef,useState} from "react";
import {Icon} from "./yem-ui.jsx";

export function SchoolHeaderBanner({brand}) {
  if (!brand?.name) return <div className="yd-fixed-banner-spacer" aria-hidden="true"/>;
  return <div className={"yd-fixed-banner"+(brand.banner?" has-image":"")} aria-label={"Identité de "+brand.name}>
    {brand.banner&&<img className="yd-fixed-banner-art" src={brand.banner} alt=""/>}
    <div className="yd-fixed-banner-mark">
      {brand.logo&&<img src={brand.logo} alt="Logo de l’établissement"/>}
      <span><strong>{brand.name}</strong>{brand.city&&<small>{brand.city}</small>}</span>
    </div>
  </div>;
}

const clean = value => String(value||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().trim();
export function SchoolHeaderSearch({nav,canSearchStudents,onNavigate}) {
  const [open,setOpen]=useState(false);
  const [query,setQuery]=useState("");
  const trigger=useRef(null);
  const field=useRef(null);
  const area=useRef(null);
  const panelId=React.useId();
  useEffect(()=>{
    if(!open)return;
    field.current?.focus();
    const outside=event=>{if(!area.current?.contains(event.target))setOpen(false);};
    document.addEventListener("pointerdown",outside);
    return()=>document.removeEventListener("pointerdown",outside);
  },[open]);
  function close(restore=false){setOpen(false);setQuery("");if(restore)trigger.current?.focus();}
  function go(id,tab="",params=null){close();onNavigate(id,tab,params);}
  const matches=nav.filter(([id,,label])=>id!=="dashboard"&&clean(label).includes(clean(query)));
  return <div className="yd-header-search" ref={area} onKeyDown={e=>{if(e.key==="Escape"){e.stopPropagation();close(true);}}}>
    <button type="button" ref={trigger} className="yd-header-search-toggle" aria-label="Rechercher dans l’établissement" aria-expanded={open} aria-controls={panelId} onClick={()=>open?close():setOpen(true)}><Icon name="search" size={23}/></button>
    {open&&<div className="yd-header-search-panel" id={panelId}>
      <form onSubmit={e=>{e.preventDefault();if(canSearchStudents&&query.trim())go("students","live",{query:query.trim()});else if(matches.length===1)go(matches[0][0]);}}>
        <label htmlFor={panelId+"-input"}>Rechercher</label>
        <input ref={field} id={panelId+"-input"} value={query} onChange={e=>setQuery(e.target.value)} placeholder="Élève, matricule ou module…" autoComplete="off"/>
        {canSearchStudents&&query.trim()&&<button className="yd-search-result" type="submit"><Icon name="users"/>Rechercher « {query.trim()} » dans les élèves</button>}
      </form>
      <div className="yd-search-results" aria-label="Modules disponibles">
        {matches.map(([id,icon,label])=><button key={id} type="button" className="yd-search-result" onClick={()=>go(id)}><Icon name={icon}/>{label}</button>)}
        {!matches.length&&!canSearchStudents&&<p>Aucun module correspondant.</p>}
      </div>
    </div>}
  </div>;
}

export function DashboardShortcuts({items=[],onNavigate}) {
  if(!items.length)return null;
  return <nav className="yd-dashboard-shortcuts" aria-label="Raccourcis du tableau de bord">
    {items.map(({id,tab,icon,title,subtitle})=><button type="button" key={id+":"+tab} onClick={()=>onNavigate(id,tab)}>
      <Icon name={icon} size={28}/><span><strong>{title}</strong><small>{subtitle}</small></span>
    </button>)}
  </nav>;
}
