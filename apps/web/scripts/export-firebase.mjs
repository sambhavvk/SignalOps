import { cp, mkdir, readFile, writeFile } from "node:fs/promises";

const output = new URL("../firebase-dist/", import.meta.url);
const workerUrl = new URL("../dist/server/index.js", import.meta.url);
const { default: worker } = await import(`${workerUrl.href}?firebase-export=${Date.now()}`);

const response = await worker.fetch(
  new Request("https://signalops-sambhavvk.web.app/", { headers: { accept: "text/html", host: "signalops-sambhavvk.web.app", "x-forwarded-proto": "https" } }),
  { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
  { waitUntil() {}, passThroughOnException() {} },
);

if (!response.ok) throw new Error(`Static render failed with HTTP ${response.status}`);
const html = await response.text();
if (!html.includes("Orders latency on payment dependency")) throw new Error("Static render did not contain the SignalOps investigation");

await mkdir(output, { recursive: true });
await cp(new URL("../dist/client/", import.meta.url), output, { recursive: true });
await writeFile(new URL("index.html", output), html, "utf8");
await writeFile(new URL("404.html", output), html, "utf8");

const generated = await readFile(new URL("index.html", output), "utf8");
if (!generated.includes("/assets/") || !generated.includes("og.png")) throw new Error("Firebase export is missing compiled assets or metadata");
