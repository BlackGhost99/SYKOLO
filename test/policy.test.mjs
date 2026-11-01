import test from "node:test";
import assert from "node:assert/strict";
import {
  evaluate,
  validatePolicy,
  ValidationError,
} from "../src/domain/policy.mjs";
import { presets } from "../src/domain/presets.mjs";
const get = (id) => structuredClone(presets.find((p) => p.id === id).policy);
for (const max of [10, 15, 20, 100, 37])
  test(`pondération sur ${max}`, () => {
    const p = get("numeric-20");
    p.scale.max = max;
    const r = evaluate(p, [
      { score: max * 0.5, weight: 1 },
      { score: max, weight: 3 },
    ]);
    assert.equal(r.score, Number((max * 0.875).toFixed(2)));
    assert.equal(r.percent, 87.5);
  });
for (const { id, policy } of presets)
  test(`modèle ${id} valide`, () =>
    assert.equal(validatePolicy(policy), policy));
test("pourcentage ignore le maximum numérique", () => {
  const p = get("percentage");
  p.scale.max = 20;
  assert.equal(evaluate(p, [{ score: 75, weight: 1 }]).score, 75);
});
test("conversion des lettres configurable", () => {
  const p = get("letters");
  assert.equal(
    evaluate(p, [
      { score: "A", weight: 1 },
      { score: "B", weight: 1 },
    ]).label,
    "B",
  );
  p.bands[1].value = 74;
  assert.equal(
    evaluate(p, [
      { score: "A", weight: 1 },
      { score: "B", weight: 1 },
    ]).label,
    "A",
  );
});
test("compétences et appréciations", () => {
  for (const id of ["competency", "appreciation"]) {
    const p = get(id);
    assert.equal(
      evaluate(p, [{ score: p.bands[2].label, weight: 1 }]).label,
      p.bands[2].label,
    );
  }
});
test("absence exclue ou zéro", () => {
  const p = get("numeric-20");
  const es = [
    { score: null, weight: 1 },
    { score: 16, weight: 1 },
  ];
  assert.equal(evaluate(p, es).score, 16);
  p.missing = "zero";
  assert.equal(evaluate(p, es).score, 8);
});
test("toutes absentes ne produit pas zéro si exclusion", () =>
  assert.equal(
    evaluate(get("numeric-20"), [{ score: null, weight: 1 }]).status,
    "empty",
  ));
test("seuil exact et seuils non triés", () => {
  const p = get("numeric-20");
  p.bands.reverse();
  assert.equal(evaluate(p, [{ score: 14, weight: 1 }]).label, "Bien");
  assert.equal(evaluate(p, [{ score: 20, weight: 1 }]).label, "Très bien");
  assert.equal(evaluate(p, [{ score: 0, weight: 1 }]).label, "À renforcer");
});
test("arrondi ne change ni niveau ni alerte", () => {
  const p = get("numeric-20");
  p.precision = 0;
  p.notification.enabled = true;
  p.notification.below = 70;
  const r = evaluate(p, [{ score: 13.99, weight: 1 }]);
  assert.equal(r.score, 14);
  assert.equal(r.label, "Satisfaisant");
  assert.ok(r.notification);
  assert.equal(evaluate(p, [{ score: 14, weight: 1 }]).notification, null);
});
test("config import/export sans changement de calcul", () => {
  const p = get("letters"),
    es = [{ score: "A+", weight: 2 }];
  assert.deepEqual(
    evaluate(JSON.parse(JSON.stringify(p)), es),
    evaluate(p, es),
  );
});
for (const [label, mutate] of [
  ["version", (p) => (p.schemaVersion = 2)],
  ["maximum", (p) => (p.scale.max = 0)],
  ["seuil initial", (p) => (p.bands[0].min = 1)],
  ["seuil double", (p) => (p.bands[1].min = 0)],
  ["niveau nul", (p) => (p.bands[0] = null)],
  ["équivalence incohérente", (p) => (p.bands[0].value = 90)],
  ["libellé double", (p) => (p.bands[1].label = p.bands[0].label)],
  ["bulletin vide", (p) => (p.report = { showScore: false, showLabel: false })],
  ["décimales", (p) => (p.precision = 1.5)],
  ["seuil notification", (p) => (p.notification.below = 101)],
])
  test(`refuse configuration : ${label}`, () => {
    const p = get("numeric-20");
    mutate(p);
    assert.throws(() => validatePolicy(p), ValidationError);
  });
for (const score of [-1, 21, NaN, Infinity, "12", undefined])
  test(`refuse note ${String(score)}`, () =>
    assert.throws(
      () => evaluate(get("numeric-20"), [{ score, weight: 1 }]),
      ValidationError,
    ));
test("refuse poids nul et entrées vides", () => {
  assert.throws(
    () => evaluate(get("numeric-20"), [{ score: 10, weight: 0 }]),
    ValidationError,
  );
  assert.throws(() => evaluate(get("numeric-20"), []), ValidationError);
});
