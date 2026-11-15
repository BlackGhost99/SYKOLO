import React,{useEffect,useState} from "react";
import {Card} from "./yem-ui.jsx";
import {teacherRequest} from "./teacher-mobile-api.js";

function CriteriaForm({path,year,level}){
  const [data,setData]=useState(null);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [busy,setBusy]=useState(false);
  const [reload,setReload]=useState(0);
  useEffect(()=>{
    let alive=true;
    teacherRequest(path+"?"+new URLSearchParams({year,level}))
      .then(result=>{if(alive)setData(result);})
      .catch(failure=>{if(alive)setError(failure.message);});
    return()=>{alive=false;};
  },[path,year,level,reload]);

  function change(id,fields){
    setData(previous=>({...previous,criteria:previous.criteria.map(
      criterion=>criterion.id===id?{...criterion,...fields}:criterion,
    )}));
    setNotice("");
  }

  async function save(event){
    event.preventDefault();
    setBusy(true);setError("");setNotice("");
    try{
      setData(await teacherRequest(path,{year,level,revision:data.revision,criteria:data.criteria},"PATCH"));
      setNotice("Référentiel enregistré.");
    }catch(failure){setError(failure.message);}
    finally{setBusy(false);}
  }

  return <>
    {error&&<p role="alert">{error}</p>}
    {error&&<button type="button" onClick={()=>{setError("");setData(null);setReload(value=>value+1);}}>
      Recharger le référentiel
    </button>}
    {notice&&<p role="status">{notice}</p>}
    {!data&&!error&&<p role="status">Chargement du référentiel…</p>}
    {data&&<form className="yf-form" onSubmit={save}>
      {!data.criteria.length&&<p>Aucun critère pour ce niveau.</p>}
      {data.criteria.map(criterion=><fieldset key={criterion.id} className="yf-grid" disabled={busy}>
        <label className="field">Critère de maîtrise
          <input required maxLength={120} readOnly={!data.editable} value={criterion.label}
            onChange={event=>change(criterion.id,{label:event.target.value})}/>
        </label>
        <label className="field">Piste de remédiation
          <textarea maxLength={300} rows={2} readOnly={!data.editable} value={criterion.remediation}
            onChange={event=>change(criterion.id,{remediation:event.target.value})}/>
        </label>
        {data.editable&&<button type="button" onClick={()=>setData(previous=>({...previous,
          criteria:previous.criteria.filter(item=>item.id!==criterion.id),
        }))}>Retirer ce critère</button>}
      </fieldset>)}
      {data.editable&&<div className="yf-inline-form wrap">
        <button type="button" disabled={busy||data.criteria.length>=30} onClick={()=>setData(previous=>({...previous,
          criteria:[...previous.criteria,{id:crypto.randomUUID(),label:"",remediation:""}],
        }))}>Ajouter un critère</button>
        <button type="submit" disabled={busy}>Enregistrer le référentiel</button>
      </div>}
    </form>}
  </>;
}

export default function PrimaryCriteria({schoolId,yearId}){
  const path="schools/"+schoolId+"/academic/primary-criteria";
  const [levels,setLevels]=useState(null);
  const [level,setLevel]=useState("");
  const [error,setError]=useState("");
  useEffect(()=>{
    let alive=true;
    teacherRequest(path+"?"+new URLSearchParams({year:yearId})).then(result=>{
      if(!alive)return;
      const choices=result.levels||[];
      setLevels(choices);
      if(choices.length===1)setLevel(choices[0].id);
    }).catch(failure=>{if(alive)setError(failure.message);});
    return()=>{alive=false;};
  },[path,yearId]);
  return <Card title="Critères de maîtrise du primaire" icon="layers">
    {error&&<p role="alert">{error}</p>}
    {!levels&&!error&&<p role="status">Chargement des niveaux…</p>}
    {levels?.length===0&&<p>Aucun niveau primaire accessible pour cette année.</p>}
    {!!levels?.length&&<label className="field">Niveau primaire
      <select value={level} onChange={event=>setLevel(event.target.value)}>
        <option value="">Choisir un niveau</option>
        {levels.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
    </label>}
    {level&&<CriteriaForm key={level} path={path} year={yearId} level={level}/>}
  </Card>;
}
