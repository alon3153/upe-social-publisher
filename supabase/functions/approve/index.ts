// Approve / reject a queued post from the daily approval email.
//
// This source was missing from the repo until 14.08.2026 — it existed only as a
// deployed function, so a bug in it could not be reviewed or fixed from here.
// Keep this file in sync with what is deployed on project nlcbjhpfneutjuscqkjx
// (deploy via .github/workflows/deploy-edge-functions.yml).
//
// All request logic lives in handler.ts so it can be unit-tested outside Deno
// (supabase/tests/approve.test.mjs).
import { handle } from "./handler.ts";

const SB_URL = Deno.env.get("SUPABASE_URL")!;
const SB_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

Deno.serve((req) => handle(req, {
  sbUrl: SB_URL,
  sbKey: SB_KEY,
  fetch: (input, init) => fetch(input, init),
  now: () => Date.now(),
  log: (...args) => console.log(...args),
}));
