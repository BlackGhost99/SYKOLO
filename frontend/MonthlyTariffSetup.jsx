import React,{useState} from "react";

export default function MonthlyTariffSetup({classes,year,busy,onGenerate}){
  const [selected,setSelected]=useState([]);
  const [amount,setAmount]=useState("");
  const [first,setFirst]=useState("");
  const [last,setLast]=useState("");
  const [day,setDay]=useState("5");
  const groups=Object.entries(classes.reduce((acc,room)=>{
    const key=room.cycle_name||"Autres classes";
    (acc[key]??=[]).push(room);
    return acc;
  },{}));
  const selectedIds=selected.filter(id=>classes.some(room=>room.id===id));
  const toggle=(ids,checked)=>setSelected(old=>checked?[...new Set([...old,...ids])]:old.filter(id=>!ids.includes(id)));
  const count=first&&last ? (Number(last.slice(0,4))-Number(first.slice(0,4)))*12+
    Number(last.slice(5))-Number(first.slice(5))+1 : 0;
  const valid=Boolean(year&&selectedIds.length&&selectedIds.length<=100&&count>=1&&count<=24&&
    count*selectedIds.length<=1200&&Number(amount)>0&&Number.isInteger(Number(amount))&&Number(day)>=1&&Number(day)<=31&&Number.isInteger(Number(day)));
  return <section aria-label="Générer les mensualités" className="card">
    <h3>Générer les mensualités</h3>
    <p className="hint">Sélectionnez les classes d’un même tarif, leur montant mensuel et les mois à facturer.
      Chaque échéance devient un tarif distinct ; aucun paiement ni frais élève n’est créé à cette étape.
      Le jour est ramené au dernier jour du mois si nécessaire.</p>
    {!year?<p>Choisissez d’abord une année scolaire.</p>:<form onSubmit={e=>{
      e.preventDefault();
      if(!valid||busy)return;
      onGenerate({year,classrooms:selectedIds,amount,first_month:first,last_month:last,due_day:Number(day)});
    }}>
      <fieldset disabled={busy}>
        <legend>Classes concernées</legend>
        {!classes.length?<p>Aucune classe active dans cette année.</p>:<>
          <label><input type="checkbox" checked={selectedIds.length===classes.length}
            onChange={e=>toggle(classes.map(room=>room.id),e.target.checked)}/> Toutes les classes</label>
          {groups.map(([group,rooms])=><div key={group}>
            <label><input type="checkbox" checked={rooms.every(room=>selectedIds.includes(room.id))}
              onChange={e=>toggle(rooms.map(room=>room.id),e.target.checked)}/> Cycle : {group}</label>
            <div style={{display:"flex",gap:"1rem",flexWrap:"wrap"}}>
              {rooms.map(room=><label key={room.id}><input type="checkbox" checked={selectedIds.includes(room.id)}
                onChange={e=>toggle([room.id],e.target.checked)}/> {room.name}</label>)}
            </div>
          </div>)}
        </>}
      </fieldset>
      <div className="two">
        <label className="field">Montant mensuel (FCFA)
          <input type="number" min="1" step="1" required value={amount} onChange={e=>setAmount(e.target.value)} disabled={busy}/></label>
        <label className="field">Premier mois
          <input type="month" required value={first} onChange={e=>setFirst(e.target.value)} disabled={busy}/></label>
        <label className="field">Dernier mois
          <input type="month" required value={last} onChange={e=>setLast(e.target.value)} disabled={busy}/></label>
        <label className="field">Jour limite de paiement (1–31)
          <input type="number" min="1" max="31" step="1" required value={day} onChange={e=>setDay(e.target.value)} disabled={busy}/></label>
      </div>
      <p className="hint">{selectedIds.length} classe(s) · {Math.max(0,count)} mois · {selectedIds.length*Math.max(0,count)} tarifs potentiels.
        Les doublons identiques sont ignorés ; une configuration incompatible bloque la génération.</p>
      <button type="submit" disabled={!valid||busy}>Générer les mensualités</button>
    </form>}
  </section>;
}
