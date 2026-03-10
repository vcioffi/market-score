from __future__ import annotations

from src.llm.fallback import parse_json_from_model_output


def test_parse_json_from_model_output_accepts_plain_json_object() -> None:
    payload = parse_json_from_model_output('{"a": 1, "b": "x"}')
    assert payload == {"a": 1, "b": "x"}


def test_parse_json_from_model_output_accepts_wrapped_text() -> None:
    raw = "analysis intro\n```json\n{\"k\": 42}\n```\ntrailing"
    payload = parse_json_from_model_output(raw)
    assert payload == {"k": 42}


def test_parse_json_from_model_output_rejects_non_object_json() -> None:
    try:
        parse_json_from_model_output("[1, 2, 3]")
    except ValueError as exc:
        assert "not an object" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected ValueError for non-object JSON output")
