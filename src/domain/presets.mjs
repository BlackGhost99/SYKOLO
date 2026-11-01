// Starting examples are editable data, never institutional rules.
const bands = [
  { min: 0, label: "À renforcer", value: 25 },
  { min: 50, label: "Satisfaisant", value: 60 },
  { min: 70, label: "Bien", value: 75 },
  { min: 85, label: "Très bien", value: 92 },
];
const base = {
  schemaVersion: 1,
  name: "Mon profil pédagogique",
  scale: { kind: "numeric", max: 20 },
  precision: 2,
  missing: "exclude",
  bands,
  report: { showScore: true, showLabel: true },
  notification: {
    enabled: false,
    below: 50,
    message: "Un accompagnement pédagogique est à prévoir.",
  },
};
export const presets = [
  ...[10, 15, 20, 100].map((max) => ({
    id: `numeric-${max}`,
    title: `Notes sur ${max}`,
    policy: {
      ...base,
      name: `Notes sur ${max}`,
      scale: { kind: "numeric", max },
    },
  })),
  {
    id: "percentage",
    title: "Pourcentages",
    policy: {
      ...base,
      name: "Pourcentages",
      scale: { kind: "percentage", max: 100 },
    },
  },
  {
    id: "letters",
    title: "Lettres",
    policy: {
      ...base,
      name: "Lettres",
      scale: { kind: "letters", max: 100 },
      report: { showScore: false, showLabel: true },
      bands: [
        { min: 0, label: "C", value: 25 },
        { min: 50, label: "B", value: 65 },
        { min: 75, label: "A", value: 82 },
        { min: 90, label: "A+", value: 95 },
      ],
    },
  },
  {
    id: "appreciation",
    title: "Appréciations",
    policy: {
      ...base,
      name: "Appréciations",
      scale: { kind: "appreciation", max: 100 },
      report: { showScore: false, showLabel: true },
    },
  },
  {
    id: "competency",
    title: "Compétences",
    policy: {
      ...base,
      name: "Compétences",
      scale: { kind: "competency", max: 100 },
      report: { showScore: false, showLabel: true },
      bands: [
        { min: 0, label: "Non acquis", value: 20 },
        { min: 40, label: "En cours", value: 55 },
        { min: 70, label: "Acquis", value: 80 },
        { min: 90, label: "Maîtrisé", value: 95 },
      ],
    },
  },
];
