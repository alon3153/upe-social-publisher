import { test } from "node:test";
import assert from "node:assert/strict";
import { handle, COOKIE_NAME, ORG_SCOPES, ADVOCATE_SCOPES } from "../functions/linkedin-oauth/handler.ts";
import { mockFetch, json } from "./_mock.mjs";

const SB = "https://proj.supabase.co";
const FN = `${SB}/functions/v1/linkedin-oauth`;
const CONFIG = [
  { key: "linkedin_client_id", value: "cid" },
  { key: "linkedin_client_secret", value: "csec" },
  { key: "linkedin_oauth_redirect", value: FN },
];

function build({ existing = {}, meId = "MEMBER1", tokenStatus = 200 } = {}) {
  const upserts = [];
  const logs = [];
  const fetch = mockFetch([
    { match: (u) => u.startsWith(`${SB}/rest/v1/app_secrets`), respond: () => json(CONFIG) },
    {
      match: (u, m) => m === "GET" && u.startsWith(`${SB}/rest/v1/linkedin_advocate_tokens?`),
      respond: (u) => {
        const acc = new URL(u).searchParams.get("account").replace("eq.", "");
        return json(existing[acc] ? [{ member_urn: existing[acc] }] : []);
      },
    },
    {
      match: (u, m) => m === "POST" && u.startsWith(`${SB}/rest/v1/linkedin_advocate_tokens`),
      respond: (u, m, init) => { upserts.push(JSON.parse(init.body)); return new Response(null, { status: 201 }); },
    },
    {
      match: (u, m) => m === "POST" && u === "https://www.linkedin.com/oauth/v2/accessToken",
      respond: () => json({ access_token: "AT", refresh_token: "RT", expires_in: 100 }, tokenStatus),
    },
    { match: (u) => u === "https://api.linkedin.com/v2/me", respond: () => json({ id: meId }) },
  ]);
  const env = { sbUrl: SB, sbKey: "service-role", fetch, randomNonce: () => "NONCE123", now: () => 1_700_000_000_000, log: (...a) => logs.push(a) };
  return { env, fetch, upserts, logs };
}

test("start: known advocate -> 302 to LinkedIn with nonce in state and HttpOnly cookie", async () => {
  const { env } = build();
  const res = await handle(new Request(`${FN}?advocate=natalia`), env);
  assert.equal(res.status, 302);
  const l = new URL(res.headers.get("location"));
  assert.equal(l.origin + l.pathname, "https://www.linkedin.com/oauth/v2/authorization");
  assert.equal(l.searchParams.get("state"), "natalia.NONCE123");
  assert.equal(l.searchParams.get("scope"), ADVOCATE_SCOPES);
  assert.equal(l.searchParams.get("client_id"), "cid");
  const cookie = res.headers.get("set-cookie");
  assert.match(cookie, new RegExp(`^${COOKIE_NAME}=NONCE123;`));
  assert.match(cookie, /HttpOnly/);
  assert.match(cookie, /Secure/);
  assert.match(cookie, /SameSite=Lax/);
});

test("start: shared credential slug gets the organization scopes", async () => {
  const { env } = build();
  const res = await handle(new Request(`${FN}?advocate=main_callback`), env);
  assert.equal(res.status, 302);
  assert.equal(new URL(res.headers.get("location")).searchParams.get("scope"), ORG_SCOPES);
});

test("start: unknown slug is refused before any redirect", async () => {
  const { env } = build();
  const res = await handle(new Request(`${FN}?advocate=../evil`), env);
  assert.equal(res.status, 200);
  assert.match(await res.text(), /לינק לא תקין/);
});

test("callback: happy path stores the token for the right account", async () => {
  const { env, upserts, logs } = build();
  const res = await handle(new Request(`${FN}?code=CODE&state=natalia.NONCE123`, {
    headers: { cookie: `${COOKIE_NAME}=NONCE123` },
  }), env);
  assert.equal(res.status, 200);
  assert.match(await res.text(), /מחובר/);
  assert.equal(upserts.length, 1);
  assert.equal(upserts[0].account, "li_natalia");
  assert.equal(upserts[0].member_urn, "urn:li:person:MEMBER1");
  assert.equal(upserts[0].access_token, "AT");
  // the token never reaches the log
  assert.ok(!JSON.stringify(logs).includes("AT\""));
  assert.match(res.headers.get("set-cookie"), /Max-Age=0/);
});

test("callback: missing or mismatching nonce cookie is rejected (OAuth CSRF)", async () => {
  const { env, upserts } = build();
  let res = await handle(new Request(`${FN}?code=CODE&state=natalia.NONCE123`), env);
  assert.match(await res.text(), /ההתחברות פגה/);
  res = await handle(new Request(`${FN}?code=CODE&state=natalia.NONCE123`, { headers: { cookie: `${COOKIE_NAME}=OTHER` } }), env);
  assert.match(await res.text(), /ההתחברות פגה/);
  // legacy state without a nonce is no longer accepted either
  res = await handle(new Request(`${FN}?code=CODE&state=natalia`, { headers: { cookie: `${COOKIE_NAME}=NONCE123` } }), env);
  assert.match(await res.text(), /ההתחברות פגה/);
  assert.equal(upserts.length, 0);
});

test("callback: unknown state slug never creates a row", async () => {
  const { env, upserts, fetch } = build();
  const res = await handle(new Request(`${FN}?code=CODE&state=attacker.NONCE123`, { headers: { cookie: `${COOKIE_NAME}=NONCE123` } }), env);
  assert.match(await res.text(), /לינק לא תקין/);
  assert.equal(upserts.length, 0);
  assert.ok(!fetch.calls.some((c) => c.url.includes("accessToken")), "code must not be exchanged");
});

test("callback: a connected advocate cannot be re-bound to a different member", async () => {
  const { env, upserts, logs } = build({ existing: { li_danielle: "urn:li:person:DANIELLE" }, meId: "ATTACKER" });
  const res = await handle(new Request(`${FN}?code=CODE&state=danielle.NONCE123`, { headers: { cookie: `${COOKIE_NAME}=NONCE123` } }), env);
  assert.match(await res.text(), /כבר בשימוש/);
  assert.equal(upserts.length, 0);
  assert.ok(logs.some((l) => String(l[0]).includes("refused re-bind")));
});

test("callback: the same person may reconnect (token refresh path)", async () => {
  const { env, upserts } = build({ existing: { li_danielle: "urn:li:person:DANIELLE" }, meId: "DANIELLE" });
  await handle(new Request(`${FN}?code=CODE&state=danielle.NONCE123`, { headers: { cookie: `${COOKIE_NAME}=NONCE123` } }), env);
  assert.equal(upserts.length, 1);
  assert.equal(upserts[0].account, "li_danielle");
});

test("callback: upstream failure shows a generic message, details stay in the log", async () => {
  const { env, logs } = build({ tokenStatus: 400 });
  const res = await handle(new Request(`${FN}?code=CODE&state=natalia.NONCE123`, { headers: { cookie: `${COOKIE_NAME}=NONCE123` } }), env);
  const text = await res.text();
  assert.match(text, /משהו השתבש/);
  assert.ok(!text.includes("400"), "status codes must not leak to the visitor");
  assert.ok(JSON.stringify(logs).includes("token exchange 400"));
});

test("consent denied and bad methods", async () => {
  const { env } = build();
  let res = await handle(new Request(`${FN}?error=user_cancelled_login`), env);
  assert.match(await res.text(), /בוטלה/);
  res = await handle(new Request(`${FN}?advocate=natalia`, { method: "POST" }), env);
  assert.equal(res.status, 405);
});
