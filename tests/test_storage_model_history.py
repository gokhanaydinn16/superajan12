from superajan12.storage import SQLiteStore


def test_model_status_history_records_registration_and_promotion(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "history.sqlite3")

    model_id = store.save_model_version(
        name="baseline",
        version="v1",
        status="candidate",
        notes="initial registration",
        change_reason="bootstrapped candidate",
        changed_by="test-suite",
    )
    store.save_model_version(
        name="baseline",
        version="v1",
        status="shadow",
        notes="paper sample reached",
        change_reason="promoted after paper evidence",
        changed_by="test-suite",
    )

    history = store.list_model_status_history(limit=10)

    assert model_id > 0
    assert len(history) == 2
    assert history[0]["from_status"] == "candidate"
    assert history[0]["to_status"] == "shadow"
    assert history[0]["changed_by"] == "test-suite"
    assert history[1]["from_status"] is None
    assert history[1]["to_status"] == "candidate"
