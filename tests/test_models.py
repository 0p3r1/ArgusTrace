from datetime import datetime, timezone

from argustrace.core.models import Finding, Status


def test_status_has_exactly_three_values():
    assert {s.value for s in Status} == {"FOUND", "NOT_FOUND", "ERROR"}


def test_finding_defaults():
    finding = Finding(
        entity="alice",
        entity_type="username",
        source="test",
        status=Status.NOT_FOUND,
    )
    assert finding.url is None
    assert finding.evidence == {}
    assert isinstance(finding.timestamp, datetime)
    assert finding.timestamp.tzinfo == timezone.utc


def test_finding_evidence_defaults_are_independent():
    a = Finding(entity="a", entity_type="username", source="s", status=Status.FOUND)
    b = Finding(entity="b", entity_type="username", source="s", status=Status.FOUND)
    a.evidence["x"] = 1
    assert b.evidence == {}


def test_finding_serializes_status_as_plain_string():
    finding = Finding(
        entity="alice",
        entity_type="username",
        source="test",
        status=Status.ERROR,
    )
    dumped = finding.model_dump(mode="json")
    assert dumped["status"] == "ERROR"
