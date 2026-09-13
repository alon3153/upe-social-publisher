import json
import signal
import sys
import tempfile
import time
import types
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
             patch.object(e,'supa_register'), \
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
