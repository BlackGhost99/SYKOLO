import React, {useState} from "react";
import "./admin-password-reset.css";

const csrf = () => document.cookie.split("; ").find(c=>c.startsWith("csrftoken="))?.split("=")[1]||"";

/** Only shown to MFA-verified super-admins on the school member directory. */
export default function AdminPasswordReset({schoolId,member,onClose}) {
  const [reason,setReason]=useState("");
  const [currentPassword,setCurrentPassword]=useState("");
  const [identityVerified,setIdentityVerified]=useState(false);
  const [result,setResult]=useState(null);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [copied,setCopied]=useState(false);

  async function submit(event) {
    event.preventDefault();
    if(!identityVerified||busy)return;
    setBusy(true);setError("");setCopied(false);
    try {
      const csrfResult=await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
      if(!csrfResult.ok)throw Error("Impossible de confirmer la session sécurisée.");
      const response=await fetch("/api/v1/auth/password/admin-reset",{
        method:"POST",credentials:"same-origin",
        headers:{"Content-Type":"application/json","X-CSRFToken":csrf()},
        body:JSON.stringify({school_id:schoolId,member_id:member.id,
          reason:reason.trim(),current_password:currentPassword}),
      });
      const payload=await response.json();
      if(!response.ok)throw Error(payload.error||"Réinitialisation refusée.");
      setCurrentPassword("");
      setResult(payload);
    }catch(e){setError(e.message||"Impossible d'effectuer cette opération.");}
    finally{setBusy(false);}
  }
  async function copyLink(){
    if(!result?.reset_url)return;
    try{await navigator.clipboard.writeText(result.reset_url);setCopied(true);}
    catch{setError("Copie automatique indisponible : sélectionnez et copiez le lien dans le champ.");}
  }
  return <div className="ya-modal-backdrop" role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}>
    <div className="ya-modal ya-reset-modal" role="dialog" aria-modal="true" aria-label="Récupération du mot de passe">
      <div className="ya-modal-heading">
        <h2>Réinitialiser l'accès</h2>
        <button type="button" aria-label="Fermer" onClick={onClose}>×</button>
      </div>
      <p>Compte : <strong>{member.name||member.username}</strong> ({member.username}).</p>
      <p className="ya-reset-context">YEM génère un lien privé permettant à cette personne de choisir son nouveau mot de passe. Vous ne verrez jamais son ancien mot de passe. Le MFA éventuel reste actif.</p>
      {!result ? <form onSubmit={submit}>
        <label className="ya-field">Motif obligatoire (10 caractères minimum)
          <textarea required rows={3} minLength={10} maxLength={240} value={reason}
            onChange={e=>setReason(e.target.value)} placeholder="Ex. Identité vérifiée au secrétariat à la demande du titulaire"/>
        </label>
        <label className="ya-field">Confirmer votre mot de passe super-administrateur
          <input required type="password" autoComplete="current-password" value={currentPassword}
            onChange={e=>setCurrentPassword(e.target.value)}/>
        </label>
        <label className="ya-reset-confirm"><input type="checkbox" checked={identityVerified}
          onChange={e=>setIdentityVerified(e.target.checked)}/>
          J'ai vérifié l'identité du titulaire avant de lui remettre le lien.
        </label>
        {error&&<p role="alert" className="ya-reset-error">{error}</p>}
        <div className="ya-modal-footer">
          <button type="button" className="ya-btn ya-btn-outline" onClick={onClose}>Annuler</button>
          <button type="submit" className="ya-btn ya-btn-primary" disabled={busy||!identityVerified||reason.trim().length<10||!currentPassword}>
            {busy?"Vérification…":"Générer le lien sécurisé"}
          </button>
        </div>
      </form> : <div className="ya-reset-result" role="status">
        <p><strong>Lien généré et opération auditée.</strong> Le lien expirera après {result.expires_in_minutes} minutes et sera inutilisable une fois le mot de passe changé.</p>
        <label className="ya-field">Lien confidentiel — ne pas diffuser publiquement
          <textarea readOnly rows={3} value={result.reset_url} onFocus={e=>e.target.select()}/>
        </label>
        <p className="ya-reset-context">Vérifiez l'identité du titulaire et transmettez ce lien uniquement par un canal privé sûr. Ne l'ajoutez pas dans une conversation ou un groupe public.</p>
        {error&&<p role="alert" className="ya-reset-error">{error}</p>}
        <div className="ya-modal-footer">
          <button type="button" className="ya-btn ya-btn-outline" onClick={onClose}>Terminer</button>
          <button type="button" className="ya-btn ya-btn-primary" onClick={copyLink}>{copied?"Lien copié":"Copier le lien"}</button>
        </div>
      </div>}
    </div>
  </div>;
}
