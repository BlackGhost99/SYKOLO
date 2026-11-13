import {describe,it,expect} from "vitest";
import {teacherWorkspacePolicy} from "./teacher-access.js";
describe("YEM: bascule vers l'espace professeur",()=>{
  it("ouvre automatiquement le rôle enseignant simple sur téléphone",()=>{
    expect(teacherWorkspacePolicy({role:"enseignant",permissions:["school.academic.read"]},false,true,null).show).toBe(true);
  });
  it("garde l'administration accessible pour le proviseur qui enseigne",()=>{
    const d={role:"direction",roles:["direction","enseignant"],permissions:["school.staff.manage","school.curriculum.read"]};
    expect(teacherWorkspacePolicy(d,true,true,null)).toEqual({eligible:true,show:false});
    expect(teacherWorkspacePolicy(d,true,true,true).show).toBe(true);
    expect(teacherWorkspacePolicy(d,true,true,false).show).toBe(false);
  });
  it("ouvre sur demande pour un rôle personnalisé lié à un cours",()=>{
    expect(teacherWorkspacePolicy({role:"professeur",roles:["professeur"],permissions:["school.curriculum.read"]},true,true,true).show).toBe(true);
  });
  it("ne crée pas d'espace professeur pour un autre employé non enseignant",()=>{
    expect(teacherWorkspacePolicy({role:"econome",permissions:["school.finance.read"]},false,true,true).show).toBe(false);
    expect(teacherWorkspacePolicy({role:"enseignant"},true,false,true).show).toBe(false);
    expect(teacherWorkspacePolicy({role:"enseignant"},true,true,true,true).show).toBe(false);
  });
});
