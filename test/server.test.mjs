import test from "node:test";
import assert from "node:assert/strict";
import { createServer } from "../src/server.mjs";
import { presets } from "../src/domain/presets.mjs";
test("API et serveur HTTP", async (t) => {
  const server = createServer();
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  t.after(() => new Promise((r) => server.close(r)));
  const base = `http://127.0.0.1:${server.address().port}`;
  await t.test("page et modules servis", async () => {
    for (const path of [
      "/",
      "/app.mjs",
      "/styles.css",
      "/domain/policy.mjs",
      "/domain/presets.mjs",
    ]) {
      const r = await fetch(base + path);
      assert.equal(r.status, 200);
      assert.ok(r.headers.get("content-security-policy"));
    }
  });
  await t.test("santé et version", async () => {
    const r = await fetch(base + "/healthz");
    assert.equal(r.status, 200);
    assert.equal((await r.json()).version, "0.1.0");
  });
  await t.test("modèles exposés", async () =>
    assert.equal(
      (await (await fetch(base + "/api/v1/presets")).json()).length,
      8,
    ),
  );
  const post = (path, body) =>
    fetch(base + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  await t.test("simulation API", async () => {
    const r = await post("/api/v1/evaluate", {
      policy: presets[2].policy,
      entries: [{ score: 15, weight: 1 }],
    });
    assert.equal(r.status, 200);
    assert.equal((await r.json()).score, 15);
  });
  await t.test("validation API", async () =>
    assert.equal(
      (await post("/api/v1/policies/validate", presets[0].policy)).status,
      200,
    ),
  );
  await t.test("config invalide", async () =>
    assert.equal((await post("/api/v1/policies/validate", {})).status, 422),
  );
  await t.test("JSON malformé", async () =>
    assert.equal(
      (
        await fetch(base + "/api/v1/evaluate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{",
        })
      ).status,
      400,
    ),
  );
  await t.test("type média", async () =>
    assert.equal(
      (await fetch(base + "/api/v1/evaluate", { method: "POST", body: "x" }))
        .status,
      415,
    ),
  );
  await t.test("limite requête", async () =>
    assert.equal(
      (await post("/api/v1/policies/validate", { x: "x".repeat(70000) }))
        .status,
      413,
    ),
  );
  await t.test("fichiers privés inaccessibles", async () => {
    for (const path of [
      "/.git/config",
      "/package.json",
      "/src/server.mjs",
      "/unknown",
    ])
      assert.equal((await fetch(base + path)).status, 404);
  });
  await t.test("méthode interdite", async () =>
    assert.equal((await fetch(base + "/", { method: "DELETE" })).status, 405),
  );
});
