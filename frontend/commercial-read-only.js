// Preserve the original Response, including its body, for existing API clients.
export function installCommercialReadOnlyNotice(target){
  const original=target.fetch;
  if(typeof original!=="function")return;
  target.fetch=async function(...args){
    const response=await original.apply(target,args);
    try{
      const input=args[0];
      const url=new URL(typeof input==="string"||input instanceof URL?input:input.url,target.location.href);
      const match=url.origin===target.location.origin&&url.pathname.match(/^\/api\/v1\/schools\/([0-9a-f-]{36})(?:\/|$)/i);
      if(match&&response.status===403){
        const data=await response.clone().json();
        if(data.code==="commercial_workspace_read_only"&&String(data.school_id)===match[1]){
          target.dispatchEvent(new target.CustomEvent("yem:commercial-read-only",{detail:{schoolId:match[1]}}));
        }
      }
    }catch{ /* ordinary errors remain handled by existing API clients */ }
    return response;
  };
}
