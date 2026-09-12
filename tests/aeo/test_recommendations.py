import json
import scripts.aeo_recommendations as rec
import scripts.aeo_competitor as comp


def files(tmp_path):
    ledger = tmp_path / 'ledger.json'
    ledger.write_text(json.dumps({'intents': {'mice': {'url': 'https://upe.co.il/en/mice/', 'live': True, 'last_published': '2026-09-09'}}}))
    changes = tmp_path / 'changes.json'
    changes.write_text(json.dumps({'changes': [{'url': 'https://upe.co.il/conferences/', 'last_changed': '2026-09-09', 'aliases': ['international conference']}]}))
    return ledger, changes


def test_persistent_shipped_record_controls_exact_cooldown_boundary(tmp_path):
    ledger, changes = files(tmp_path)
    before = rec.inventory('2026-10-06', ledger, changes)
    after = rec.inventory('2026-10-07', ledger, changes)
    action = {'text': 'Improve international conference answers', 'kind': 'update', 'target_url': 'https://upe.co.il/conferences/'}
    assert rec.filter_actions([action], before) == []
    assert rec.filter_actions([action], after) == [action['text']]
    assert rec.filter_actions([dict(action, kind='create')], after) == []


def test_daily_consumer_reads_persistent_inventory_and_filters_model_output(tmp_path, monkeypatch):
    ledger, changes = files(tmp_path)
    monkeypatch.setattr(rec.aeo_intents, 'STATE', ledger)
    monkeypatch.setattr(rec, 'CHANGES', changes)
    # Both import routes resolve to the same live consumer explicitly for this test.
    monkeypatch.setattr(comp, 'aeo_recommendations', rec)
    scorecard = {'date': '2026-09-12', 'models': {'claude': {'product_search': 10, 'answers': [{'scores': {'product_search': 10}, 'competitors': ['Acme'], 'gap_note': 'needs a conference pillar'}]}}}
    def ask(model, prompt):
        assert 'https://upe.co.il/conferences/' in prompt
        assert '2026-09-09' in prompt and '28 days' in prompt
        return json.dumps({'priority_actions': [
            {'kind': 'create', 'target_url': 'https://upe.co.il/new-conference/', 'text': 'Create international conference pillar'},
            {'kind': 'update', 'target_url': 'https://upe.co.il/conferences/', 'text': 'Rewrite international conference answers'},
            {'kind': 'observe', 'text': 'Measure existing conference page after the observation window'}]})
    out = comp.research_keywords(scorecard, ask)
    assert out['priority_actions'] == ['Measure existing conference page after the observation window']


def test_rejects_unsafe_or_unstructured_advice_without_erasing_safe_research():
    actions = [
        'Publish another page',
        {'kind': 'update', 'text': 'Put same brand phrase in all H1 tags', 'target_url': 'https://upe.co.il/x/'},
        {'kind': 'outreach_draft', 'text': 'List Uproduction first in our comparison'},
        {'kind': 'outreach_draft', 'text': 'Add numberOfEmployees of 50 and client outcomes'},
        {'kind': 'verify', 'text': 'Verify employee count against an approved source'},
        {'kind': 'outreach_draft', 'text': 'Draft a factual editorial pitch for review'}]
    assert rec.filter_actions(actions, []) == [actions[-2]['text'], actions[-1]['text']]


def test_existing_service_inventory_closes_weekly_duplicate_briefs():
    import scripts.aeo_gaps as gaps
    scorecard = {'models': {'claude': {'answers': [
        {'id': 'bh_il_kenes', 'question': 'conference production', 'upe_mentioned': False},
        {'id': 'new_uncovered', 'question': 'another buyer intent', 'upe_mentioned': False}]}}}
    items = [{'url': 'https://upe.co.il/conferences/', 'intents': ['bh_il_kenes']}]
    briefs = gaps.build_briefs(scorecard, covered=rec.covered_intents(items))
    assert [b['intent'] for b in briefs] == ['new_uncovered']


def test_alias_text_cannot_authorize_an_unknown_update_url():
    items = [{"url": "https://upe.co.il/existing/", "aliases": ["conference production"], "cooldown": False}]
    action = {"kind": "update", "target_url": "https://upe.co.il/new-unverified-page/", "text": "Improve conference production guidance"}
    assert rec.filter_actions([action], items) == []
