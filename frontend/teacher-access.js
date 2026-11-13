/** UI-only routing policy; the server independently enforces teacher assignment/permissions. */
export function teacherWorkspacePolicy(access, assigned, mobile, requested, platform=false) {
  const roles=[access?.role,...(access?.roles||[])];
  const eligible=!platform && (roles.includes("enseignant") || Boolean(assigned));
  const privileged=["school.staff.manage","school.members.write","school.finance.read",
    "school.roles.manage","school.academic.manage","school.students.manage"];
  const auto=access?.role==="enseignant"&&!privileged.some(p=>(access?.permissions||[]).includes(p));
  return {eligible,show:Boolean(mobile&&eligible&&(requested===null?auto:requested))};
}
