const TRIGGER_EVENT_TYPES = new Set([
  "page.created",
  "page.content_updated",
  "page.properties_updated",
  "page.deleted",
  "page.undeleted",
  "page.moved",
  "data_source.content_updated",
  "data_source.schema_updated",
]);

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "GET" && (url.pathname === "/" || url.pathname === "/health")) {
      return jsonResponse({
        ok: true,
        service: "KyapyaTango Notion webhook",
        configured: {
          githubToken: Boolean(env.GITHUB_TOKEN),
          notionVerificationToken: Boolean(env.NOTION_VERIFICATION_TOKEN),
        },
      });
    }

    if (request.method !== "POST" || (url.pathname !== "/" && url.pathname !== "/notion-webhook")) {
      return jsonResponse({ ok: false, error: "Not found" }, 404);
    }

    const rawBody = await request.text();
    let payload;

    try {
      payload = JSON.parse(rawBody);
    } catch {
      return jsonResponse({ ok: false, error: "Invalid JSON" }, 400);
    }

    // Notion sends this once when a webhook subscription is created.
    if (typeof payload.verification_token === "string") {
      if (
        env.NOTION_VERIFICATION_TOKEN &&
        payload.verification_token !== env.NOTION_VERIFICATION_TOKEN
      ) {
        return jsonResponse({ ok: false, error: "Verification token mismatch" }, 401);
      }

      console.log(
        JSON.stringify({
          kind: "notion_webhook_verification",
          verification_token: payload.verification_token,
        }),
      );

      return jsonResponse({
        ok: true,
        verification_token: payload.verification_token,
        next: "Store this value as the NOTION_VERIFICATION_TOKEN Worker secret.",
      });
    }

    if (!env.NOTION_VERIFICATION_TOKEN) {
      return jsonResponse(
        { ok: false, error: "NOTION_VERIFICATION_TOKEN is not configured" },
        503,
      );
    }

    const notionSignature = request.headers.get("X-Notion-Signature");
    const trusted = await verifyNotionSignature(
      rawBody,
      notionSignature,
      env.NOTION_VERIFICATION_TOKEN,
    );

    if (!trusted) {
      return jsonResponse({ ok: false, error: "Invalid Notion signature" }, 401);
    }

    if (!shouldTriggerEvent(payload.type)) {
      return jsonResponse(
        { ok: true, ignored: true, eventType: payload.type ?? null },
        202,
      );
    }

    if (!env.GITHUB_TOKEN) {
      return jsonResponse({ ok: false, error: "GITHUB_TOKEN is not configured" }, 503);
    }

    try {
      const dispatchResult = await dispatchWorkflow(env);
      console.log(
        JSON.stringify({
          kind: "github_workflow_dispatched",
          notionEventId: payload.id ?? null,
          notionEventType: payload.type,
          workflowRunId: dispatchResult?.workflow_run_id ?? null,
          workflowRunUrl: dispatchResult?.html_url ?? null,
        }),
      );

      return jsonResponse(
        {
          ok: true,
          dispatched: true,
          eventType: payload.type,
          workflowRunUrl: dispatchResult?.html_url ?? null,
        },
        202,
      );
    } catch (error) {
      console.error(
        JSON.stringify({
          kind: "github_workflow_dispatch_failed",
          notionEventId: payload.id ?? null,
          notionEventType: payload.type,
          error: error instanceof Error ? error.message : String(error),
        }),
      );

      // A non-2xx response lets Notion retry delivery.
      return jsonResponse({ ok: false, error: "GitHub dispatch failed" }, 502);
    }
  },
};

export function shouldTriggerEvent(eventType) {
  return TRIGGER_EVENT_TYPES.has(eventType);
}

export async function verifyNotionSignature(rawBody, signatureHeader, verificationToken) {
  if (!signatureHeader || !verificationToken) {
    return false;
  }

  const prefix = "sha256=";
  if (!signatureHeader.startsWith(prefix)) {
    return false;
  }

  const signatureBytes = hexToBytes(signatureHeader.slice(prefix.length));
  if (!signatureBytes) {
    return false;
  }

  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(verificationToken),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["verify"],
  );

  return crypto.subtle.verify(
    "HMAC",
    key,
    signatureBytes,
    encoder.encode(rawBody),
  );
}

async function dispatchWorkflow(env) {
  const owner = env.GITHUB_OWNER || "Kyapya";
  const repo = env.GITHUB_REPO || "KyapyaTango";
  const workflow = env.GITHUB_WORKFLOW || "sync-notion.yml";
  const ref = env.GITHUB_REF || "main";
  const endpoint = `https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/actions/workflows/${encodeURIComponent(workflow)}/dispatches`;

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      "Content-Type": "application/json",
      "User-Agent": "KyapyaTango-Notion-Webhook",
      "X-GitHub-Api-Version": "2026-03-10",
    },
    body: JSON.stringify({ ref }),
  });

  const responseText = await response.text();
  if (!response.ok) {
    throw new Error(`GitHub API ${response.status}: ${responseText.slice(0, 500)}`);
  }

  if (!responseText) {
    return null;
  }

  try {
    return JSON.parse(responseText);
  } catch {
    return null;
  }
}

function hexToBytes(hex) {
  if (!/^[0-9a-f]+$/i.test(hex) || hex.length % 2 !== 0) {
    return null;
  }

  const bytes = new Uint8Array(hex.length / 2);
  for (let index = 0; index < hex.length; index += 2) {
    bytes[index / 2] = Number.parseInt(hex.slice(index, index + 2), 16);
  }
  return bytes;
}

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}
