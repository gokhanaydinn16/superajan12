from superajan12.storage import SQLiteStore


def test_execution_storage_persists_session_and_latest_veto(tmp_path) -> None:
    sqlite_path = tmp_path / "execution.sqlite3"
    store = SQLiteStore(sqlite_path)

    store.save_execution_session(
        session_id="sess-1",
        connected=False,
        cancel_on_disconnect_supported=True,
        cancel_on_disconnect_armed=True,
        stale_data_locked=True,
        disconnect_reason="socket dropped",
        open_order_count=2,
    )
    store.record_execution_veto(
        scope="live_execution",
        vetoes=("stale-data lock blocks execution", "hard open-position cap reached"),
    )

    session = store.latest_execution_session()
    veto = store.latest_execution_veto("live_execution")

    assert session is not None
    assert session["session_id"] == "sess-1"
    assert session["connected"] is False
    assert session["cancel_on_disconnect_armed"] is True
    assert session["stale_data_locked"] is True
    assert session["open_order_count"] == 2
    assert veto is not None
    assert veto["vetoes"] == [
        "stale-data lock blocks execution",
        "hard open-position cap reached",
    ]
