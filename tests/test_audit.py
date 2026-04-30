import json

from superajan12.audit import AuditLogger


def test_audit_logger_writes_jsonl(tmp_path) -> None:
    path = tmp_path / "audit" / "events.jsonl"
    logger = AuditLogger(path)

    logger.record("test.event", {"ok": True})

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event_type"] == "test.event"
    assert event["payload"] == {"ok": True}
