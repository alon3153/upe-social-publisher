// linkedin-oauth request handler — pure, testable (no Deno globals).
//
// Security model (audit 2026-09):
//   * `state` carries `<slug>.<nonce>`; the nonce is also set as an HttpOnly cookie
//     on the redirect to LinkedIn and must match on the callback (OAuth CSRF, RFC 6749
//     §10.12). A callback that arrives without the matching cookie is rejected.
//   * The slug on the callback must be a known advocate (or the shared-credential
//     staging slug). Unknown slugs are never written to the token table.
//   * An advocate row that is already bound to a LinkedIn member is never silently
//     re-bound to a DIFFERENT member: whoever gets hold of the link cannot hijack a
//     connected advocate channel. Re-connecting the same person still works.
//   * Errors shown to the visitor are generic; details go to the function log only.

export const COOKIE_NAME = "li_oauth_nonce";
export const COOKIE_MAX_AGE = 900; // seconds — long enough for the LinkedIn consent screen

// Use only scopes already authorized on the app (no openid → no business-email
// verification wall). r_basicprofile lets /v2/me return the member id.
export const ADVOCATE_SCOPES = "w_member_social r_basicprofile";
// Shared company credential (Alon): company pages + personal profile. Must match
// scripts/linkedin_org_oauth.py SCOPES (tests/test_security_hardening.py checks it).
export const ORG_SCOPES =
  "w_organization_social r_organization_social rw_organization_admin w_member_social r_basicprofile";

export const MAIN_CALLBACK = "main_callback";

export const ADVOCATES: Record<string, string> = {
  natalia: "נטליה",
  danielle: "דניאל",
  daniel: "דניאל",
  dorin: "דורין",
};

const SLUG_RE = /^[a-z0-9_]{1,32}$/;

export interface Env {
  sbUrl: string;
  sbKey: string;
  fetch: typeof fetch;
  randomNonce: () => string;
  now: () => number;
  log: (...args: unknown[]) => void;
}

interface Config { cid: string; csec: string; redir: string }

function isKnownSlug(slug: string): boolean {
  return SLUG_RE.test(slug) && (slug === MAIN_CALLBACK || Object.hasOwn(ADVOCATES, slug));
}

function scopesFor(slug: string): string {
  return slug === MAIN_CALLBACK ? ORG_SCOPES : ADVOCATE_SCOPES;
}

function displayFor(slug: string): string {
  return slug === MAIN_CALLBACK ? "Uproduction (shared credential)" : (ADVOCATES[slug] || slug);
}

async function loadConfig(env: Env): Promise<Config> {
  const r = await env.fetch(
    `${env.sbUrl}/rest/v1/app_secrets?select=key,value&key=in.(linkedin_client_id,linkedin_client_secret,linkedin_oauth_redirect)`,
    { headers: { apikey: env.sbKey, Authorization: `Bearer ${env.sbKey}` } },
  );
  if (!r.ok) throw new Error(`config load ${r.status}`);
  const rows: Array<{ key: string; value: string }> = await r.json();
  const m: Record<string, string> = {};
  for (const row of rows) m[row.key] = row.value;
  const cid = m["linkedin_client_id"], csec = m["linkedin_client_secret"], redir = m["linkedin_oauth_redirect"];
  if (!cid || !csec || !redir) throw new Error("missing linkedin config in app_secrets");
  return { cid, csec, redir };
}

export function page(title: string, body: string, ok = true): Response {
  // Supabase serves all edge-function responses on *.supabase.co as text/plain
  // (anti-phishing). So return CLEAN plain text — HTML would show as raw tags.
  const plain = body.replace(/<br\s*\/?>/gi, "\n").replace(/<[^>]+>/g, "");
  const text = `${ok ? "✅" : "⚠️"}  ${title}\n\n${plain}\n`;
  const headers = new Headers();
  headers.set("content-type", "text/plain; charset=utf-8");
  headers.set("cache-control", "no-store");
  headers.set("referrer-policy", "no-referrer");
  headers.set("x-content-type-options", "nosniff");
  return new Response(text, { status: 200, headers });
}

async function exchangeCode(env: Env, cfg: Config, code: string) {
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    redirect_uri: cfg.redir,
    client_id: cfg.cid,
    client_secret: cfg.csec,
  });
  const r = await env.fetch("https://www.linkedin.com/oauth/v2/accessToken", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!r.ok) throw new Error(`token exchange ${r.status}`);
  return await r.json();
}

async function memberUrn(env: Env, token: string): Promise<string> {
  // /v2/me works with r_basicprofile (no openid needed). Returns the member id.
  const r = await env.fetch("https://api.linkedin.com/v2/me", {
    headers: { Authorization: `Bearer ${token}`, "X-Restli-Protocol-Version": "2.0.0" },
  });
  if (!r.ok) throw new Error(`me ${r.status}`);
  const info = await r.json();
  if (!info.id) throw new Error("no id in /v2/me");
  return `urn:li:person:${info.id}`;
}

async function existingMember(env: Env, account: string): Promise<string | null> {
  const q = new URLSearchParams({ select: "member_urn", account: `eq.${account}`, limit: "1" });
  const r = await env.fetch(`${env.sbUrl}/rest/v1/linkedin_advocate_tokens?${q}`, {
    headers: { apikey: env.sbKey, Authorization: `Bearer ${env.sbKey}` },
  });
  if (!r.ok) throw new Error(`advocate lookup ${r.status}`);
  const rows: Array<{ member_urn?: string }> = await r.json();
  return rows.length && rows[0].member_urn ? rows[0].member_urn : null;
}

async function storeToken(env: Env, account: string, display: string, urn: string, tok: any) {
  const expires = new Date(env.now() + (tok.expires_in ?? 5184000) * 1000).toISOString();
  const row = {
    account, display_name: display, member_urn: urn,
    access_token: tok.access_token, refresh_token: tok.refresh_token ?? "",
    expires_at: expires, updated_at: new Date(env.now()).toISOString(),
  };
  const r = await env.fetch(`${env.sbUrl}/rest/v1/linkedin_advocate_tokens?on_conflict=account`, {
    method: "POST",
    headers: {
      apikey: env.sbKey, Authorization: `Bearer ${env.sbKey}`,
      "Content-Type": "application/json", Prefer: "resolution=merge-duplicates",
    },
    body: JSON.stringify(row),
  });
  if (!r.ok) throw new Error(`supabase upsert ${r.status}`);
}

export function parseCookies(header: string | null): Record<string, string> {
  const out: Record<string, string> = {};
  for (const part of (header || "").split(";")) {
    const i = part.indexOf("=");
    if (i < 0) continue;
    const k = part.slice(0, i).trim();
    if (k) out[k] = part.slice(i + 1).trim();
  }
  return out;
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function startRedirect(cfg: Config, slug: string, nonce: string): Response {
  const auth = new URL("https://www.linkedin.com/oauth/v2/authorization");
  auth.searchParams.set("response_type", "code");
  auth.searchParams.set("client_id", cfg.cid);
  auth.searchParams.set("redirect_uri", cfg.redir);
  auth.searchParams.set("scope", scopesFor(slug));
  auth.searchParams.set("state", `${slug}.${nonce}`);
  const headers = new Headers();
  headers.set("Location", auth.toString());
  headers.set("cache-control", "no-store");
  headers.append(
    "Set-Cookie",
    `${COOKIE_NAME}=${nonce}; Max-Age=${COOKIE_MAX_AGE}; Path=/; Secure; HttpOnly; SameSite=Lax`,
  );
  return new Response(null, { status: 302, headers });
}

function clearCookie(res: Response): Response {
  res.headers.append("Set-Cookie", `${COOKIE_NAME}=; Max-Age=0; Path=/; Secure; HttpOnly; SameSite=Lax`);
  return res;
}

export async function handle(req: Request, env: Env): Promise<Response> {
  if (req.method !== "GET" && req.method !== "HEAD") {
    return new Response("method not allowed", { status: 405, headers: { Allow: "GET, HEAD" } });
  }
  try {
    const url = new URL(req.url);
    const code = url.searchParams.get("code");
    const rawState = url.searchParams.get("state") || "";
    const advocate = (url.searchParams.get("advocate") || "").toLowerCase();
    const err = url.searchParams.get("error");

    if (err) {
      env.log("linkedin-oauth: consent denied", { error: err });
      return clearCookie(page("ההתחברות בוטלה", "לא אושרה הגישה ל-LinkedIn. אפשר לנסות שוב מהלינק שקיבלת.", false));
    }

    const cfg = await loadConfig(env);

    // Step 1: start — bounce to LinkedIn consent with a fresh CSRF nonce.
    if (!code) {
      const who = advocate || "natalia";
      if (!isKnownSlug(who)) {
        env.log("linkedin-oauth: unknown advocate slug on start", { slug: who.slice(0, 40) });
        return page("לינק לא תקין", "חסר מזהה שגריר/ה בלינק. פנו לאלון.", false);
      }
      return startRedirect(cfg, who, env.randomNonce());
    }

    // Step 2: callback — verify state + nonce, exchange, bind, store.
    const dot = rawState.indexOf(".");
    const who = (dot > 0 ? rawState.slice(0, dot) : rawState).toLowerCase();
    const nonce = dot > 0 ? rawState.slice(dot + 1) : "";
    if (!isKnownSlug(who)) {
      env.log("linkedin-oauth: callback with unknown state slug", { slug: who.slice(0, 40) });
      return clearCookie(page("לינק לא תקין", "הבקשה לא זוהתה. פנו לאלון.", false));
    }
    const cookieNonce = parseCookies(req.headers.get("cookie"))[COOKIE_NAME] || "";
    if (!nonce || !cookieNonce || !timingSafeEqual(nonce, cookieNonce)) {
      env.log("linkedin-oauth: state/nonce mismatch", { slug: who });
      return clearCookie(page(
        "ההתחברות פגה",
        "הבקשה לא תקפה או שעבר יותר מדי זמן. אפשר לנסות שוב מהלינק שקיבלת.",
        false,
      ));
    }

    const account = `li_${who}`;
    const display = displayFor(who);
    const tok = await exchangeCode(env, cfg, code);
    const urn = await memberUrn(env, tok.access_token);

    const bound = await existingMember(env, account);
    if (bound && bound !== urn) {
      env.log("linkedin-oauth: refused re-bind of connected advocate", { account, bound, attempted: urn });
      return clearCookie(page(
        "הלינק כבר בשימוש",
        "הלינק הזה כבר מחובר לחשבון LinkedIn אחר. אם החלפת חשבון, פנו לאלון כדי לאפס את החיבור.",
        false,
      ));
    }

    await storeToken(env, account, display, urn, tok);
    env.log("linkedin-oauth: connected", { account, member_urn: urn });

    return clearCookie(page(
      "מחובר! 🎉",
      `${display}, החיבור הושלם. <b>סיימת</b> — את לא צריכה לעשות שום דבר נוסף. מהיום אנחנו מנהלים את הכל בשבילך.`,
      true,
    ));
  } catch (e) {
    env.log("linkedin-oauth: failure", String(e).slice(0, 300));
    return clearCookie(page("משהו השתבש", "התחברות נכשלה. אפשר לנסות שוב, או לפנות לאלון.", false));
  }
}
