"""Offline regression cases: stream completion is required before advancing."""
import io
import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from scripts import executor as e


def stream(events):
    return io.BytesIO(b''.join(('event: '+event['type']+'\ndata: '+json.dumps(event,ensure_ascii=False)+'\n\n').encode() for event in events))


def complete(text='טיוטה מלאה'):
    return [
        {'type':'message_start','message':{'role':'assistant'}},
        {'type':'content_block_start','index':0,'content_block':{'type':'server_tool_use','id':'tool1'}},
        {'type':'content_block_delta','index':0,'delta':{'type':'input_json_delta','partial_json':'{"query": "test"}'}},
        {'type':'content_block_stop','index':0},
        {'type':'ping'},
        {'type':'content_block_start','index':1,'content_block':{'type':'text','text':''}},
        {'type':'content_block_delta','index':1,'delta':{'type':'text_delta','text':text}},
        {'type':'content_block_delta','index':1,'delta':{'type':'citations_delta','citation':{}}},
        {'type':'content_block_stop','index':1},
        {'type':'message_delta','delta':{'stop_reason':'end_turn'}},
        {'type':'message_stop'},
    ]


def test_search_pings_and_hebrew_text_complete_without_tool_payloads():
    assert e.read_message_stream(stream(complete())) == {'content':[{'type':'text','text':'טיוטה מלאה'}],'stop_reason':'end_turn'}


@pytest.mark.parametrize('reason',['max_tokens','pause_turn','tool_use',None])
def test_truncated_or_continuation_response_is_not_a_finished_draft(reason):
    events=complete(); events[-2]['delta']['stop_reason']=reason
    with pytest.raises(e.StreamFailure,match='incomplete message'):
        e.read_message_stream(stream(events))


def test_disconnected_partial_text_is_not_success():
    with pytest.raises(e.StreamFailure,match='disconnected'):
        e.read_message_stream(stream(complete()[:-1]))


def test_provider_error_is_not_a_draft_and_does_not_echo_private_message():
    events=complete()[:-1]+[{'type':'error','error':{'message':'PRIVATE_INPUT'}}]
    with pytest.raises(e.StreamFailure) as err:
        e.read_message_stream(stream(events))
    assert 'PRIVATE_INPUT' not in str(err.value)


def test_malformed_event_rejected():
    with pytest.raises(e.StreamFailure,match='malformed'):
        e.read_message_stream(io.BytesIO(b'data: {no}\n\n'))


def test_unclosed_text_block_rejected_even_with_message_stop():
    events=complete(); events.pop(-3)
    with pytest.raises(e.StreamFailure,match='incomplete'):
        e.read_message_stream(stream(events))


def test_run_agent_requests_stream_and_parses_metadata(tmp_path):
    body='Ready draft\n```json\n{"summary":"prepared","ready_for_approval":true}\n```'
    def request(req,timeout):
        assert json.loads(req.data)['stream'] is True
        assert timeout == 90
        return stream(complete(body))
    with patch.object(e,'DELIV_DIR',tmp_path),patch.object(e.urllib.request,'urlopen',side_effect=request):
        result=e.run_agent({'id':'one','kind':'seo','channel':'site','priority':'P1','title':'Test'})
    assert result['deliverable_md']=='Ready draft'
    assert result['ready_for_approval'] is True


def test_hard_deadline_still_bounds_a_stream_with_continuous_pings(tmp_path):
    class SlowStream:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def __iter__(self):
            while True:
                time.sleep(0.005)
                yield b'data: {"type":"ping"}\n'
                yield b'\n'
    with patch.object(e,'DELIV_DIR',tmp_path),patch.object(e.urllib.request,'urlopen',return_value=SlowStream()):
        result=e.bounded_agent({'id':'one'},0.025)
    assert result == {'error':'action deadline exceeded'}
