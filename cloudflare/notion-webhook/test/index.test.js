import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import test from "node:test";

import { shouldTriggerEvent, verifyNotionSignature } from "../src/index.js";

test("content-changing Notion events trigger a sync", () => {
  assert.equal(shouldTriggerEvent("page.created"), true);
  assert.equal(shouldTriggerEvent("page.content_updated"), true);
  assert.equal(shouldTriggerEvent("page.properties_updated"), true);
  assert.equal(shouldTriggerEvent("data_source.content_updated"), true);
});

test("unrelated Notion events are ignored", () => {
  assert.equal(shouldTriggerEvent("comment.created"), false);
  assert.equal(shouldTriggerEvent("page.locked"), false);
  assert.equal(shouldTriggerEvent(undefined), false);
});

test("Notion HMAC signatures are verified against the raw request body", async () => {
  const body = JSON.stringify({ id: "event-id", type: "page.content_updated" });
  const token = "secret_example";
  const signature = `sha256=${createHmac("sha256", token).update(body).digest("hex")}`;

  assert.equal(await verifyNotionSignature(body, signature, token), true);
  assert.equal(await verifyNotionSignature(`${body} `, signature, token), false);
  assert.equal(await verifyNotionSignature(body, "sha256=not-hex", token), false);
  assert.equal(await verifyNotionSignature(body, null, token), false);
});
