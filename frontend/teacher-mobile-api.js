export async function teacherRequest(path, data, method="POST") {
  if (data !== undefined) {
    const token=await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
    if(!token.ok)throw Error("Votre session a expiré.");
  }
  const csrf=document.cookie.split("; ").find(v=>v.startsWith("csrftoken="))?.split("=")[1]||"";
  const response=await fetch("/api/v1/"+path,{
    method:data===undefined?"GET":method,credentials:"same-origin",
    headers:data===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":csrf},
    body:data===undefined?undefined:JSON.stringify(data),
  });
  if(!response.headers.get("content-type")?.includes("application/json"))
    throw Error("Le service YEM est momentanément indisponible.");
  const result=await response.json();
  if(!response.ok)throw Error(result.error||"Accès non autorisé.");
  return result;
}
export const displayNumber=value=>value===null||value===undefined?"—":Number(value).toLocaleString("fr-FR",{maximumFractionDigits:2});
