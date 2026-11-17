import publish_approved as pa


def test_future_row_is_held_and_due_rows_pass():
    assert pa._not_due({"scheduled_date": "2026-11-20"}, "2026-11-17")
    assert not pa._not_due({"scheduled_date": "2026-11-17"}, "2026-11-17")
    assert not pa._not_due({"scheduled_date": "2026-11-01T00:00:00"}, "2026-11-17")
    assert not pa._not_due({"scheduled_date": None}, "2026-11-17")
    assert not pa._not_due({}, "2026-11-17")
