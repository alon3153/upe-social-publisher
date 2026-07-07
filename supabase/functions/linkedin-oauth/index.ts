// linkedin-oauth — one-click LinkedIn connect for advocates.
// Flow:
//   GET ?advocate=natalia            -> 302 redirect to LinkedIn consent (state=natalia)
//   GET ?code=...&state=natalia      -> exchange code, fetch member URN, store token, show success
// No copy-paste, no terminal. Advocate clicks the link once and is done forever.
// verify_jwt = off (public link).
//
// Config (client id/secret/redirect) is read from the service-role-only table
// public.app_secrets, so no dashboard env-secrets step is required. SUPABASE_URL
// and SUPABASE_SERVICE_ROLE_KEY are auto-injected by the Supabase runtime.

const SB_URL = Deno.env.get("SUPABASE_URL")!;
const SB_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

// Use only scopes already authorized on the app (no openid → no business-email
// verification wall). r_basicprofile lets /v2/me return the member id.
const SCOPES = "w_member_social r_basicprofile";

const ADVOCATES: Record<string, string> = {
  natalia: "נטליה",
  danielle: "דניאל",
};

async function loadConfig() {
  const r = await fetch(
    `${SB_URL}/rest/v1/app_secrets?select=key,value&key=in.(linkedin_client_id,linkedin_client_secret,linkedin_oauth_redirect)`,
    { headers: { apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}` } },
  );
  if (!r.ok) throw new Error(`config load ${r.status}: ${await r.text()}`);
  const rows: Array<{ key: string; value: string }> = await r.json();
  const m: Record<string, string> = {};
  for (const row of rows) m[row.key] = row.value;
  const cid = m["linkedin_client_id"], csec = m["linkedin_client_secret"], redir = m["linkedin_oauth_redirect"];
  if (!cid || !csec || !redir) throw new Error("missing linkedin config in app_secrets");
  return { cid, csec, redir };
}

function page(title: string, body: string, ok = true): Response {
  const color = ok ? "#1a7f4b" : "#b00020";
  const html = `<!doctype html><html dir="rtl" lang="he"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title}</title></head>
<body style="font-family:Arial,Helvetica,sans-serif;direction:rtl;text-align:center;background:#faf8f3;padding:40px 20px;">
<div style="max-width:460px;margin:0 auto;background:#fff;border-radius:16px;padding:32px;box-shadow:0 4px 20px rgba(0,0,0,.08);">
<div style="font-size:48px;margin-bottom:12px;">${ok ? "✅" : "⚠️"}</div>
<h1 style="color:${color};font-size:22px;margin:0 0 12px;">${title}</h1>
<p style="color:#444;font-size:16px;line-height:1.6;">${body}</p>
</div></body></html>`;
  return new Response(html, { status: 200, headers: { "Content-Type": "text/html; charset=utf-8" } });
}

async function exchangeCode(cfg: { cid: string; csec: string; redir: string }, code: string) {
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    redirect_uri: cfg.redir,
    client_id: cfg.cid,
    client_secret: cfg.csec,
  });
  const r = await fetch("https://www.linkedin.com/oauth/v2/accessToken", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!r.ok) throw new Error(`token exchange ${r.status}: ${await r.text()}`);
  return await r.json();
}

async function memberUrn(token: string): Promise<string> {
  // /v2/me works with r_basicprofile (no openid needed). Returns the member id.
  const r = await fetch("https://api.linkedin.com/v2/me", {
    headers: { Authorization: `Bearer ${token}`, "X-Restli-Protocol-Version": "2.0.0" },
  });
  if (!r.ok) throw new Error(`me ${r.status}: ${await r.text()}`);
  const info = await r.json();
  if (!info.id) throw new Error("no id in /v2/me");
  return `urn:li:person:${info.id}`;
}

async function storeToken(account: string, display: string, urn: string, tok: any) {
  const expires = new Date(Date.now() + (tok.expires_in ?? 5184000) * 1000).toISOString();
  const row = {
    account, display_name: display, member_urn: urn,
    access_token: tok.access_token, refresh_token: tok.refresh_token ?? "",
    expires_at: expires, updated_at: new Date().toISOString(),
  };
  const r = await fetch(`${SB_URL}/rest/v1/linkedin_advocate_tokens?on_conflict=account`, {
    method: "POST",
    headers: {
      apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}`,
      "Content-Type": "application/json", Prefer: "resolution=merge-duplicates",
    },
    body: JSON.stringify(row),
  });
  if (!r.ok) throw new Error(`supabase upsert ${r.status}: ${await r.text()}`);
}

Deno.serve(async (req) => {
  try {
    const url = new URL(req.url);
    const code = url.searchParams.get("code");
    const state = (url.searchParams.get("state") || "").toLowerCase();
    const advocate = (url.searchParams.get("advocate") || "").toLowerCase();
    const err = url.searchParams.get("error");

    if (err) {
      return page("ההתחברות בוטלה", "לא אושרה הגישה ל-LinkedIn. אפשר לנסות שוב מהלינק שקיבלת.", false);
    }

    const cfg = await loadConfig();

    // Step 1: start — bounce to LinkedIn consent.
    if (!code) {
      const who = advocate || "natalia";
      if (!ADVOCATES[who]) return page("לינק לא תקין", "חסר מזהה שגריר/ה בלינק. פנו לאלון.", false);
      const auth = new URL("https://www.linkedin.com/oauth/v2/authorization");
      auth.searchParams.set("response_type", "code");
      auth.searchParams.set("client_id", cfg.cid);
      auth.searchParams.set("redirect_uri", cfg.redir);
      auth.searchParams.set("scope", SCOPES);
      auth.searchParams.set("state", who);
      return Response.redirect(auth.toString(), 302);
    }

    // Step 2: callback — exchange + store.
    const who = state || "natalia";
    const display = ADVOCATES[who] || who;
    const tok = await exchangeCode(cfg, code);
    const urn = await memberUrn(tok.access_token);
    await storeToken(`li_${who}`, display, urn, tok);

    return page(
      "מחובר! 🎉",
      `${display}, החיבור הושלם. <b>סיימת</b> — את לא צריכה לעשות שום דבר נוסף. מהיום אנחנו מנהלים את הכל בשבילך.`,
      true,
    );
  } catch (e) {
    return page("משהו השתבש", `התחברות נכשלה. אפשר לנסות שוב, או לפנות לאלון.<br><small>${String(e).slice(0, 140)}</small>`, false);
  }
});
