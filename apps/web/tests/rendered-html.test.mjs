import assert from "node:assert/strict";
import test from "node:test";

const workerUrl = new URL("../dist/server/index.js", import.meta.url);

async function render() {
  const workerModule = await import(`${workerUrl.href}?test=${Date.now()}`);
  return workerModule.default.fetch(new Request("http://localhost/", { headers: { accept: "text/html" } }), { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } }, { waitUntil() {}, passThroughOnException() {} });
}

test("server-renders the SignalOps investigation shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /SignalOps/);
  assert.match(html, /Orders latency on payment dependency/);
  assert.match(html, /Incident timeline/);
  assert.match(html, /Evidence/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape/);
});
