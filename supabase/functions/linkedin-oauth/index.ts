// linkedin-oauth — one-click LinkedIn connect for advocates (and the shared
// company credential via ?advocate=main_callback).
// Flow:
//   GET ?advocate=natalia              -> 302 to LinkedIn consent, state=natalia.<nonce>, nonce cookie
//   GET ?code=...&state=natalia.<nonce> -> verify nonce cookie, exchange code, fetch member URN,
//                                          refuse to re-bind a connected advocate to another member,
//                                          store token, show success
// No copy-paste, no terminal. Advocate clicks the link once and is done forever.
// verify_jwt = off (public link).
//
// Config (client id/secret/redirect) is read from the service-role-only table
// public.app_secrets, so no dashboard env-secrets step is required. SUPABASE_URL
// and SUPABASE_SERVICE_ROLE_KEY are auto-injected by the Supabase runtime.
//
// All request logic lives in handler.ts so it can be unit-tested outside Deno
// (supabase/tests/linkedin-oauth.test.mjs).
import { handle } from "./handler.ts";

const SB_URL = Deno.env.get("SUPABASE_URL")!;
const SB_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

Deno.serve((req) => handle(req, {
  sbUrl: SB_URL,
  sbKey: SB_KEY,
  fetch: (input, init) => fetch(input, init),
  randomNonce: () => crypto.randomUUID().replace(/-/g, ""),
  now: () => Date.now(),
  log: (...args) => console.log(...args),
}));
