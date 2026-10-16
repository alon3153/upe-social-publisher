import { test } from "node:test";
import assert from "node:assert/strict";
import { handle, PAGE } from "../functions/approve/handler.ts";
import { mockFetch, json } from "./_mock.mjs";

const SB = "https://proj.supabase.co";
const ROWS = [
  { id: 1, day: 42, token: "tokA", status: "pending", network: "facebook" },
  { id: 2, day: 42, token: "tokB", status: "rejected", network: "linkedin" },
  { id: 3, day: 42, token: "tokC", status: "approved", network: "instagram" },
];

function env(routes, opts = {}) {
  const logs = [];
  const fetch = mockFetch(routes);
  return {
    env: { sbUrl: SB, sbKey: "service-role", fetch, now: () => 1_700_000_000_000, log: (...a) => logs.push(a) },
    fetch, logs,
  };
}

function selectRoute(rows = ROWS) {
  return {
    match: (url, m) => m === "GET" && url.startsWith(`${SB}/rest/v1/post_approvals?`),
    respond: (url) => {
      const q = new URL(url).searchParams;
      let out = rows;
      if (q.get("id")) out = out.filter((r) => `eq.${r.id}` === q.get("id"));
      if (q.get("day")) out = out.filter((r) => `eq.${r.day}` === q.get("day"));
      return json(out);
    },
  };
}

function patchRoute(store, status = 204) {
  return {
    match: (url, m) => m === "PATCH" && url.startsWith(`${SB}/rest/v1/post_approvals?`),
    respond: (url, m, init) => { store.push({ q: new URL(url).searchParams, body: JSON.parse(init.body) }); return new Response(null, { status }); },
  };
}

function loc(res) { return new URL(res.headers.get("location")); }

test("approve: valid id+token approves and redirects ok", async () => {
  const patches = [];
  const { env: e, fetch } = env([selectRoute(), patchRoute(patches)]);
  const res = await handle(new Request(`${SB}/functions/v1/approve?id=1&token=tokA&action=approve`), e);
  assert.equal(res.status, 302);
  const l = loc(res);
  assert.equal(l.origin + l.pathname, PAGE);
  assert.equal(l.searchParams.get("s"), "ok");
  assert.equal(l.searchParams.get("net"), "Facebook");
  assert.equal(l.searchParams.get("day"), "42");
  assert.equal(patches.length, 1);
  assert.equal(patches[0].q.get("id"), "eq.1");
  assert.equal(patches[0].body.status, "approved");
  // service-role key travels only in headers, never in a URL
  for (const c of fetch.calls) assert.ok(!c.url.includes("service-role"));
});

test("approve: wrong token never writes", async () => {
  const patches = [];
  const { env: e } = env([selectRoute(), patchRoute(patches)]);
  const res = await handle(new Request(`${SB}/functions/v1/approve?id=1&token=WRONG-token&action=approve`), e);
  assert.equal(loc(res).searchParams.get("s"), "err");
  assert.equal(patches.length, 0);
});

test("approve: missing token / unknown action / bad method are rejected", async () => {
  const patches = [];
  const { env: e, fetch } = env([selectRoute(), patchRoute(patches)]);
  let res = await handle(new Request(`${SB}/functions/v1/approve?id=1`), e);
  assert.equal(loc(res).searchParams.get("s"), "err");
  res = await handle(new Request(`${SB}/functions/v1/approve?id=1&token=tokA&action=delete`), e);
  assert.equal(loc(res).searchParams.get("s"), "err");
  res = await handle(new Request(`${SB}/functions/v1/approve?id=1&token=tokA`, { method: "POST" }), e);
  assert.equal(res.status, 405);
  assert.equal(fetch.calls.length, 0, "nothing should reach the database");
  assert.equal(patches.length, 0);
});

test("approve: a failed UPDATE is reported as an error, not success", async () => {
  const patches = [];
  const { env: e, logs } = env([selectRoute(), patchRoute(patches, 500)]);
  const res = await handle(new Request(`${SB}/functions/v1/approve?id=1&token=tokA&action=approve`), e);
  assert.equal(loc(res).searchParams.get("s"), "err");
  assert.ok(logs.some((l) => String(l[0]).includes("failure")));
});

test("approve: reject flips status and logs without the token", async () => {
  const patches = [];
  const { env: e, logs } = env([selectRoute(), patchRoute(patches)]);
  const res = await handle(new Request(`${SB}/functions/v1/approve?id=1&token=tokA&action=reject`), e);
  assert.equal(loc(res).searchParams.get("s"), "rej");
  assert.equal(patches[0].body.status, "rejected");
  assert.ok(!JSON.stringify(logs).includes("tokA"));
});

test("approve: published / already-approved rows are not rewritten", async () => {
  const rows = [
    { id: 7, day: 5, token: "t7", status: "published", network: "linkedin" },
    { id: 8, day: 5, token: "t8", status: "approved", network: "linkedin" },
  ];
  const patches = [];
  const { env: e } = env([selectRoute(rows), patchRoute(patches)]);
  let res = await handle(new Request(`${SB}/functions/v1/approve?id=7&token=t7`), e);
  assert.equal(loc(res).searchParams.get("s"), "pub");
  res = await handle(new Request(`${SB}/functions/v1/approve?id=8&token=t8`), e);
  assert.equal(loc(res).searchParams.get("s"), "dup");
  assert.equal(patches.length, 0);
});

test("approve_all: approves pending only, never revives rejected", async () => {
  const patches = [];
  const { env: e } = env([selectRoute(), patchRoute(patches)]);
  const res = await handle(new Request(`${SB}/functions/v1/approve?action=approve_all&day=42&token=tokB`), e);
  assert.equal(loc(res).searchParams.get("s"), "all");
  assert.equal(loc(res).searchParams.get("day"), "42");
  assert.equal(patches.length, 1);
  assert.equal(patches[0].q.get("id"), "in.(1)");
  assert.equal(patches[0].body.status, "approved");
});

test("approve_all: token from another day, bad day, or no rows -> err, no writes", async () => {
  const patches = [];
  const { env: e } = env([selectRoute(), patchRoute(patches)]);
  let res = await handle(new Request(`${SB}/functions/v1/approve?action=approve_all&day=42&token=other-token`), e);
  assert.equal(loc(res).searchParams.get("s"), "err");
  res = await handle(new Request(`${SB}/functions/v1/approve?action=approve_all&day=42%20or%201=1&token=tokA`), e);
  assert.equal(loc(res).searchParams.get("s"), "err");
  res = await handle(new Request(`${SB}/functions/v1/approve?action=approve_all&day=99&token=tokA`), e);
  assert.equal(loc(res).searchParams.get("s"), "err");
  assert.equal(patches.length, 0);
});

test("redirect encodes untrusted values instead of splicing them into the URL", async () => {
  const rows = [{ id: 9, day: "1&t=hacked", token: "t9", status: "pending", network: "x<y" }];
  const patches = [];
  const { env: e } = env([selectRoute(rows), patchRoute(patches)]);
  const res = await handle(new Request(`${SB}/functions/v1/approve?id=9&token=t9`), e);
  const l = loc(res);
  assert.equal(l.searchParams.get("day"), "1&t=hacked");
  assert.equal(l.searchParams.get("t"), null);
  assert.equal(res.headers.get("cache-control"), "no-store");
});
