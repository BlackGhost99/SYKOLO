import http from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { evaluate, validatePolicy, ValidationError } from "./domain/policy.mjs";
import { presets } from "./domain/presets.mjs";
const files = new Map([
  ["/", ["../public/index.html", "text/html; charset=utf-8"]],
  ["/app.mjs", ["../public/app.mjs", "text/javascript; charset=utf-8"]],
  ["/styles.css", ["../public/styles.css", "text/css; charset=utf-8"]],
  [
    "/domain/policy.mjs",
    ["./domain/policy.mjs", "text/javascript; charset=utf-8"],
  ],
  [
    "/domain/presets.mjs",
    ["./domain/presets.mjs", "text/javascript; charset=utf-8"],
  ],
]);
// Public files are an allowlist; filesystem paths never come from the request.
export function createServer() {
  return http.createServer(async (req, res) => {
    const headers = {
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "no-referrer",
      "X-Frame-Options": "DENY",
      "Content-Security-Policy":
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
      "Cache-Control": "no-store",
    };
    const send = (status, data) => {
      res.writeHead(status, {
        ...headers,
        "Content-Type": "application/json; charset=utf-8",
      });
      res.end(JSON.stringify(data));
    };
    try {
      const path = new URL(req.url, "http://localhost").pathname;
      if (req.method === "GET" && path === "/healthz")
        return send(200, {
          status: "ok",
          version: "0.1.0",
          commit: process.env.RENDER_GIT_COMMIT || "local",
        });
      if (req.method === "GET" && path === "/api/v1/presets")
        return send(200, presets);
      if (
        req.method === "POST" &&
        ["/api/v1/evaluate", "/api/v1/policies/validate"].includes(path)
      ) {
        if (!req.headers["content-type"]?.startsWith("application/json"))
          return send(415, { error: "Format JSON requis." });
        const chunks = [];
        let size = 0;
        for await (const chunk of req) {
          size += chunk.length;
          if (size > 65536) {
            send(413, { error: "Configuration trop volumineuse." });
            req.resume();
            return;
          }
          chunks.push(chunk);
        }
        let data;
        try {
          data = JSON.parse(Buffer.concat(chunks).toString("utf8"));
        } catch {
          return send(400, { error: "JSON invalide." });
        }
        if (path.endsWith("/validate")) {
          validatePolicy(data);
          return send(200, { valid: true });
        }
        return send(200, evaluate(data?.policy, data?.entries));
      }
      if (req.method !== "GET")
        return send(405, { error: "Méthode non autorisée." });
      if (!files.has(path))
        return send(404, { error: "Ressource introuvable." });
      const [file, type] = files.get(path);
      const content = await readFile(new URL(file, import.meta.url));
      res.writeHead(200, { ...headers, "Content-Type": type });
      res.end(content);
    } catch (error) {
      if (error instanceof ValidationError)
        return send(422, { error: error.message });
      console.error("Request failed:", error.name);
      send(500, { error: "Erreur interne." });
    }
  });
}
if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const server = createServer();
  server.listen(Number(process.env.PORT || 3000), "0.0.0.0", () =>
    console.log("SYKOLO ready"),
  );
  for (const signal of ["SIGINT", "SIGTERM"])
    process.on(signal, () => {
      server.close(() => process.exit(0));
      setTimeout(() => process.exit(1), 10000).unref();
    });
}
