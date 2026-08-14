// Approve / reject a queued post from the daily approval email.
//
// This source was missing from the repo until 14.08.2026 — it existed only as a
// deployed function, so a bug in it could not be reviewed or fixed from here.
// Keep this file in sync with what is deployed on project nlcbjhpfneutjuscqkjx.
import { createClient } from 'jsr:@supabase/supabase-js@2';

const supabase = createClient(
  Deno.env.get('SUPABASE_URL')!,
  Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
);

const NET: Record<string,string> = { facebook:'Facebook', instagram:'Instagram', linkedin:'LinkedIn', tiktok:'TikTok' };
const PAGE = 'https://alon3153.github.io/upe-social-publisher/r.html';

function redirect(s: string, net = '', day: string | number = ''): Response {
  const loc = `${PAGE}?s=${s}&net=${encodeURIComponent(net)}&day=${day}`;
  return new Response(null, { status: 302, headers: { Location: loc } });
}

Deno.serve(async (req) => {
  const url = new URL(req.url);
  const action = (url.searchParams.get('action') || 'approve').toLowerCase();
  const token = url.searchParams.get('token');

  // ── Batch approve: approve every still-pending post for a given day ──
  if (action === 'approve_all') {
    const day = url.searchParams.get('day');
    if (!day || !token) return redirect('err');
    const { data: rows } = await supabase.from('post_approvals').select('*').eq('day', day);
    if (!rows || rows.length === 0) return redirect('err');
    // token must match one row from this day's batch (proves email receipt)
    if (!rows.some((r: any) => r.token === token)) return redirect('err');
    // Only pending rows. Excluding published/approved is not enough: it let
    // `rejected` through, so one "approve all" click revived posts Alon had
    // explicitly declined (seen 14.08.2026 on days 9101/9102/9103).
    const ids = rows
      .filter((r: any) => r.status === 'pending')
      .map((r: any) => r.id);
    if (ids.length > 0) {
      await supabase.from('post_approvals')
        .update({ status: 'approved', approved_at: new Date().toISOString() })
        .in('id', ids);
    }
    return redirect('all', '', day);
  }

  // ── Single post approve / reject (unchanged) ──
  const id = url.searchParams.get('id');
  if (!id || !token) return redirect('err');
  const { data: row } = await supabase.from('post_approvals').select('*').eq('id', id).maybeSingle();
  if (!row || row.token !== token) return redirect('err');
  const net = NET[row.network] || row.network;
  if (row.status === 'published') return redirect('pub', net, row.day);
  if (row.status === 'approved' && action === 'approve') return redirect('dup', net, row.day);
  if (action === 'reject') {
    await supabase.from('post_approvals').update({ status: 'rejected' }).eq('id', id);
    return redirect('rej', net, row.day);
  }
  await supabase.from('post_approvals').update({ status: 'approved', approved_at: new Date().toISOString() }).eq('id', id);
  return redirect('ok', net, row.day);
});
