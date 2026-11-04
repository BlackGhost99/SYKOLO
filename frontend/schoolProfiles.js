// YEM: institution profiles used by the existing green school/admin forms.
export const SCHOOL_TYPES = [
  ["maternelle", "Maternelle"],
  ["primaire", "École primaire"],
  ["college", "Collège"],
  ["lycee", "Lycée"],
  ["groupe_scolaire", "Groupe scolaire / plusieurs cycles"],
];
export const CYCLE_TYPES = [
  ["maternelle", "Maternelle"],
  ["primaire", "Primaire"],
  ["college", "Collège"],
  ["lycee", "Lycée"],
];
export const defaultCycles = kind => kind === "groupe_scolaire" ? [] : kind && kind !== "a_configurer" ? [kind] : [];
export const toggleCycle = (cycles, code) => cycles.includes(code)
  ? cycles.filter(x => x !== code)
  : CYCLE_TYPES.map(([key]) => key).filter(x => cycles.includes(x) || x === code);
