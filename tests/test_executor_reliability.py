import json
import signal
import sys
import tempfile
import time
import types
import urllib.error
from pathlib import Path
from unittest.mock import patch
from scripts import executor as e


def test_hard_deadline_interrupts_action_and_restores_signal():
    old=signal.getsignal(signal.SIGALRM)
    with patch.object(e,'run_agent',side_effect=lambda it: time.sleep(0.2)):
        result=e.bounded_agent({'id':'x'},0.02)
    assert result['error']=='action deadline exceeded'
    assert signal.getsignal(signal.SIGALRM)==old
    assert signal.getitimer(signal.ITIMER_REAL)[0]==0


def test_first_success_survives_next_action_failure():
    inits={k:{'id':k,'title':k,'history':[]} for k in ('a','b')}
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);state=root/'state';path=state/'initiatives.json'
        def action(it, seconds):
            assert seconds <= e.ACTION_SECONDS
            if it['id']=='b':
                assert json.loads(path.read_text())['a']['revisions']==1
                raise RuntimeError('unexpected failure with private contents')
            return {'deliverable_md':'draft','summary':'prepared','ready_for_approval':True}
        with patch.multiple(e,ROOT=root,STATE_DIR=state,INIT_PATH=path,DELIV_DIR=root/'deliverables',API_KEY='test'), \
             patch.object(e,'load_initiatives',return_value=inits), \
             patch.object(e,'sync_backlog',return_value=(inits,None)), \
             patch.object(e,'load_approvals',return_value=set()), \
             patch.object(e,'supa_fetch_approved',return_value=(set(),set())), \
             patch.object(e,'pick_to_advance',return_value=list(inits.values())), \
             patch.object(e,'bounded_agent',side_effect=action), \
             patch.object(e,'supa_register',return_value=True), \
             patch.object(e,'render_html',return_value='draft digest'), \
             patch.dict(sys.modules,{'daily_email':types.SimpleNamespace(send_graph_html=lambda *a:(True,'mocked'))}), \
             patch.object(sys,'argv',['executor.py']):
            assert e.main()==1
        feed=json.loads((root/'reports/executor.json').read_text())
        assert feed['advanced']==1 and feed['attempted']==2
        assert feed['complete'] is False and feed['status']=='partial'
        assert 'private contents' not in path.read_text()
        assert json.loads(path.read_text())['a']['status']=='awaiting_approval'


def test_checkpoint_does_not_claim_running_action_completed():
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        with patch.multiple(e,ROOT=root,STATE_DIR=root/'state',INIT_PATH=root/'state/initiatives.json'):
            e.checkpoint({},[],0,2,active_id='draft-1')
        feed=json.loads((root/'reports/executor.json').read_text())
        assert feed['active_id']=='draft-1' and not feed['complete']
        assert feed['advanced']==0 and feed['status']=='partial'


def test_no_api_key_is_failure():
    with patch.object(e,'API_KEY',''),patch.object(sys,'argv',['executor.py']):
        assert e.main()==1


def test_drafting_completion_does_not_claim_delivery_success():
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        with patch.multiple(e,ROOT=root,STATE_DIR=root/'state',INIT_PATH=root/'state/initiatives.json'):
            e.checkpoint({},[('draft',{})],1,1,finished=True,postprocessing='failed')
        feed=json.loads((root/'reports/executor.json').read_text())
        assert feed['drafting_complete'] is True
        assert feed['complete'] is False and feed['status']=='partial'
        assert feed['postprocessing']=='failed'


def test_zero_planned_is_measured_complete_without_notification():
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        with patch.multiple(e,ROOT=root,STATE_DIR=root/'state',INIT_PATH=root/'state/initiatives.json'):
            e.checkpoint({},[],0,0,finished=True,postprocessing='not_needed')
        assert json.loads((root/'reports/executor.json').read_text())['complete'] is True


def _item(iid, **extra):
    base={'id':iid,'title':iid,'history':[],'status':'todo','priority':'P1','revisions':0,'consecutive_failures':0}
    base.update(extra)
    return base


def _ok(**extra):
    res={'deliverable_md':'draft','summary':'prepared','ready_for_approval':True}
    res.update(extra)
    return res


def _run(tmp, inits, agent, *, register=True, email=(True,'mocked'), pick=None, mono=None):
    root=Path(tmp)
    state=root/'state'
    path=state/'initiatives.json'
    patches=[
        patch.multiple(e,ROOT=root,STATE_DIR=state,INIT_PATH=path,DELIV_DIR=root/'deliverables',API_KEY='test'),
        patch.object(e,'load_initiatives',return_value=inits),
        patch.object(e,'sync_backlog',return_value=(inits,None)),
        patch.object(e,'load_approvals',return_value=set()),
        patch.object(e,'supa_fetch_approved',return_value=(set(),set())),
        patch.object(e,'bounded_agent',side_effect=agent),
        patch.object(e,'supa_register',return_value=register),
        patch.dict(sys.modules,{'daily_email':types.SimpleNamespace(send_graph_html=lambda *a: email)}),
        patch.object(sys,'argv',['executor.py']),
    ]
    if pick is not None:
        patches.append(patch.object(e,'pick_to_advance',return_value=pick))
    if mono is not None:
        patches.append(patch.object(e.time,'monotonic',side_effect=mono))
    for item in patches:
        item.start()
    try:
        code=e.main()
    finally:
        for item in reversed(patches):
            item.stop()
    feed=json.loads((root/'reports/executor.json').read_text())
    saved=json.loads(path.read_text())
    return code, feed, saved


def test_two_failures_flag_needs_attention_and_success_resets_the_counter():
    it=_item('a',status='in_progress')
    e.record_failure(it)
    assert it['consecutive_failures']==1 and it['status']=='in_progress'
    e.record_failure(it)
    assert it['consecutive_failures']==2 and it['status']=='needs_attention'
    e.record_success(it)
    assert it['consecutive_failures']==0


def test_pick_skips_flagged_drafts(tmp_path):
    items={
        'flagged':_item('flagged',status='needs_attention',consecutive_failures=2,priority='P0'),
        'counted':_item('counted',status='in_progress',consecutive_failures=2,priority='P0'),
        'open':_item('open',priority='P2'),
    }
    with patch.object(e,'STATE_DIR',tmp_path):
        assert [x['id'] for x in e.pick_to_advance(items,set(),6)]==['open']


def test_sync_does_not_clear_needs_attention(tmp_path):
    recs=tmp_path/'recommendations.json'
    recs.write_text(json.dumps({'recommendations':[{
        'action':'rewritten executive posting','action_key':'linkedin-executive-advocacy',
        'channel':'linkedin','priority':'P0'}]}))
    stuck=_item('ba5e2d8e',status='needs_attention',consecutive_failures=13,priority='P0',
                action_key='linkedin-executive-advocacy',channel='linkedin')
    with patch.object(e,'RECS_PATH',recs):
        result, error=e.sync_backlog({'ba5e2d8e':stuck})
    assert error is None
    assert result['ba5e2d8e']['status']=='needs_attention'
    assert result['ba5e2d8e']['consecutive_failures']==13


def test_email_summary_names_items_that_need_alon():
    html=e.render_html({'x':_item('x',title='Stuck draft',status='needs_attention',consecutive_failures=2,priority='P0')},[])
    assert "Alon's attention" in html
    assert 'needs_attention' in html
    assert '>x<' in html


def test_seeded_linkedin_draft_is_flagged_not_superseded():
    inits=json.loads(e.INIT_PATH.read_text())
    item=inits['ba5e2d8e']
    assert item['status']=='needs_attention'
    assert item['consecutive_failures']>=2
    verified=json.loads((e.STATE_DIR/'council_verified_actions.json').read_text())
    assert 'ba5e2d8e' not in verified.get('superseded_initiatives',{})
    chosen=e.pick_to_advance(inits,set(),50)
    assert all(it['id']!='ba5e2d8e' for it in chosen)


def test_second_deadline_flags_and_a_later_run_skips_it(tmp_path):
    it=_item('a',status='in_progress',consecutive_failures=1,priority='P0')
    code, feed, saved=_run(tmp_path,{'a':it},lambda it, seconds:{'error':'action deadline exceeded'},pick=[it])
    assert code==1
    assert saved['a']['consecutive_failures']==2
    assert saved['a']['status']=='needs_attention'
    assert feed['advanced']==0 and feed['attempted']==1
    with patch.object(e,'STATE_DIR',tmp_path):
        assert e.pick_to_advance(saved,set(),6)==[]


def test_deadline_on_already_flagged_item_does_not_fail_the_run(tmp_path):
    it=_item('a',status='needs_attention',consecutive_failures=2,priority='P0')
    code, feed, saved=_run(tmp_path,{'a':it},lambda it, seconds:{'error':'action deadline exceeded'},pick=[it])
    assert code==0
    assert saved['a']['consecutive_failures']==3
    assert saved['a']['status']=='needs_attention'
    assert feed['attempted']==1 and feed['advanced']==0
    assert feed['postprocessing']=='not_needed'


def test_non_deadline_failure_still_fails_the_run_when_already_flagged(tmp_path):
    it=_item('a',status='needs_attention',consecutive_failures=2)
    code, feed, saved=_run(tmp_path,{'a':it},lambda it, seconds:{'error':'anthropic 500'},pick=[it])
    assert code==1
    assert saved['a']['consecutive_failures']==3
    assert feed['complete'] is False


def test_success_resets_consecutive_failures_and_parks_for_approval(tmp_path):
    it=_item('a',status='in_progress',consecutive_failures=1)
    code, feed, saved=_run(tmp_path,{'a':it},lambda it, seconds:_ok(),pick=[it])
    assert code==0
    assert saved['a']['consecutive_failures']==0
    assert saved['a']['status']=='awaiting_approval'
    assert feed['advanced']==1 and feed['complete'] is True


def test_short_budget_defers_every_unstarted_draft(tmp_path):
    inits={k:_item(k) for k in ('a','b','c')}
    started=[]
    def mono():
        mono.n+=1
        if mono.n==1:
            return 0.0
        return float(e.RUN_SECONDS-e.ACTION_SECONDS+1)
    mono.n=0
    code, feed, saved=_run(tmp_path,inits,lambda it, seconds: started.append(it['id']) or _ok(),mono=mono)
    assert started==[]
    assert code==0
    assert feed['deferred']==3 and feed['attempted']==0 and feed['advanced']==0
    assert feed['complete'] is True
    for item in saved.values():
        assert item['history']==[]
        assert item['consecutive_failures']==0
        assert item['status']=='todo'


def test_last_draft_with_a_short_slot_is_deferred_not_failed(tmp_path):
    first=_item('first',priority='P0')
    last=_item('last',priority='P1')
    calls={'n':0}
    def mono():
        calls['n']+=1
        if calls['n']<=2:
            return 0.0
        return float(e.RUN_SECONDS-140)
    started=[]
    def agent(it, seconds):
        started.append((it['id'], seconds))
        return _ok()
    code, feed, saved=_run(tmp_path,{'first':first,'last':last},agent,mono=mono)
    assert code==0
    assert started==[('first', e.ACTION_SECONDS)]
    assert feed['deferred']==1 and feed['attempted']==1 and feed['advanced']==1
    assert saved['first']['status']=='awaiting_approval'
    assert saved['last']['history']==[] and saved['last']['status']=='todo'
    assert feed['complete'] is True


def test_skipped_needs_attention_item_does_not_fail_a_successful_run(tmp_path):
    stuck=_item('stuck',status='needs_attention',consecutive_failures=4,priority='P0')
    other=_item('other',priority='P1',consecutive_failures=1)
    started=[]
    def agent(it, seconds):
        started.append(it['id'])
        return _ok()
    code, feed, saved=_run(tmp_path,{'stuck':stuck,'other':other},agent)
    assert code==0
    assert started==['other']
    assert saved['stuck']['status']=='needs_attention'
    assert saved['stuck']['consecutive_failures']==4
    assert saved['other']['consecutive_failures']==0
    assert saved['other']['status']=='awaiting_approval'
    assert "Alon's attention" in e.render_html(saved,[])


def test_registration_or_email_failure_fails_the_run(tmp_path):
    it=_item('a')
    code, feed, saved=_run(tmp_path,{'a':it},lambda it, seconds:_ok(),register=False,pick=[it])
    assert code==1 and feed['postprocessing']=='failed'
    assert saved['a']['status']=='awaiting_approval'
    other=tmp_path/'email'
    other.mkdir()
    code, feed, saved=_run(other,{'a':_item('a')},lambda it, seconds:_ok(),email=(False,'down'),pick=[_item('a')])
    assert code==1 and feed['postprocessing']=='failed'


def test_redraft_max_tokens_is_about_10000():
    assert e.REDRAFT_MAX_TOKENS==10000
    assert '10000' in e.__doc__
    seen={}
    def urlopen(req, timeout=None):
        seen['body']=json.loads(req.data.decode())
        raise urllib.error.URLError('offline')
    with patch.object(e.urllib.request,'urlopen',urlopen), patch.object(e.time,'sleep',lambda *_a, **_k: None):
        result=e.run_agent({'id':'x','kind':'recommendation','channel':'linkedin','priority':'P0','title':'t'})
    assert seen['body']['max_tokens']==10000
    assert 'offline' in result['error']
