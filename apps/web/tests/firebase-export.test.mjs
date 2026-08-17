import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

test("produces a self-contained Firebase Hosting export", async () => {
  const html = await readFile(new URL("../firebase-dist/index.html", import.meta.url), "utf8");
  assert.match(html, /SignalOps/);
  assert.match(html, /Orders latency on payment dependency/);
  assert.match(html, /https:\/\/signalops-sambhavvk\.web\.app\/og\.png/);
  await access(new URL("../firebase-dist/og.png", import.meta.url));
  await access(new URL("../firebase-dist/assets", import.meta.url));
});
