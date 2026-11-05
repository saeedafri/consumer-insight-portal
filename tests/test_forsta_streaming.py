"""Source export parsing stays bounded without changing JSON values."""
from __future__ import annotations

import json
import tracemalloc

import pytest
import requests

from etl.forsta_client import ForstaClient, ForstaError


class Response:
    status_code = 200
    headers = {}

    def __init__(self, chunks):
        self.chunks = chunks
        self.closed = False

    def iter_content(self, chunk_size=65536):
        yield from self.chunks

    def json(self):
        return json.loads(b"".join(self.iter_content()))

    def close(self):
        self.closed = True


def client_response(monkeypatch, chunks, **kwargs):
    client = ForstaClient("example.invalid", "unit-test-key", **kwargs)
    response = Response(chunks)
    calls = []

    def get(url, **kw):
        calls.append((url, kw))
        return response

    monkeypatch.setattr(client.session, "get", get)
    return client, response, calls


def generated_export(count):
    yield b"["
    for n in range(count):
        yield (("," if n else "") + json.dumps({"record": n, "uuid": f"u{n}",
                                                "answer": "x" * 512})).encode()
    yield b"]"


def test_large_export_does_not_materialize_the_response(monkeypatch):
    client, response, calls = client_response(monkeypatch, generated_export(20000))
    tracemalloc.start()
    try:
        source = getattr(client, "iter_survey_data", client.survey_data)
        count = sum(1 for _ in source("selfserve/test", cond="qualified"))
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert count == 20000
    assert peak < 4 * 1024 * 1024, f"source decoding allocated {peak / 1024**2:.2f} MiB"
    assert calls[0][1]["stream"] is True
    assert calls[0][1]["params"] == {"format": "json", "cond": "qualified"}
    assert response.closed


@pytest.mark.parametrize("chunk_size", [1, 2, 3, 7, 64, 65536])
def test_chunks_preserve_all_json_types_and_bom(monkeypatch, chunk_size):
    rows = [{"record": 42, "uuid": "Üñî🌍", "text": "line1\nline2\"\\", "none": None,
             "bool": False, "float": 1.25, "nested": {"items": [1, "yes"]}}, {"record": "0007"}]
    payload = b"\xef\xbb\xbf \r\n" + json.dumps(rows, ensure_ascii=False).encode() + b"\t\n"
    client, response, _ = client_response(monkeypatch, (payload[i:i + chunk_size]
                                                        for i in range(0, len(payload), chunk_size)))
    assert list(client.iter_survey_data("/selfserve/test/")) == rows
    assert response.closed


def test_old_list_interface_is_preserved(monkeypatch):
    client, response, _ = client_response(monkeypatch, [b'[{"record":"001","status":3}]'])
    assert client.survey_data("test") == [{"record": "001", "status": 3}]
    assert response.closed


@pytest.mark.parametrize("payload", [b"", b" ", b"{}", b"null", b"[", b"[{", b"[{\"a\":true",
                                      b"[{},]", b"[1]", b"[{} {}]", b"[{}]junk", b"[{bad]",
                                      b'[{"a":"\xff"}]', b'[{"a":"\xe2\x82', b'[{"a": "\x01"}]'])
def test_invalid_or_truncated_export_fails_and_closes(monkeypatch, payload):
    client, response, _ = client_response(monkeypatch, (payload[i:i + 2] for i in range(0, len(payload), 2)))
    with pytest.raises(ForstaError):
        list(client.iter_survey_data("test"))
    assert response.closed


@pytest.mark.parametrize("payload", [b"[]", b" \r\n[\t ] \n"])
def test_empty_export(monkeypatch, payload):
    client, response, _ = client_response(monkeypatch, [payload])
    assert list(client.iter_survey_data("test")) == []
    assert response.closed


def test_early_close_releases_http_connection(monkeypatch):
    client, response, _ = client_response(monkeypatch, generated_export(100))
    stream = client.iter_survey_data("test")
    assert next(stream)["record"] == 0
    stream.close()
    assert response.closed


def test_body_interruption_is_not_retried_after_a_row(monkeypatch):
    def interrupted():
        yield b'[{"record":1},'
        raise requests.ConnectionError("disconnected")

    client, response, calls = client_response(monkeypatch, interrupted())
    stream = client.iter_survey_data("test")
    assert next(stream) == {"record": 1}
    with pytest.raises(requests.ConnectionError):
        next(stream)
    assert response.closed
    assert len(calls) == 1


def test_retryable_http_failure_closes_before_retry(monkeypatch):
    client, success, calls = client_response(monkeypatch, [b'[{}]'], max_retries=2)
    busy = Response([b"temporarily unavailable"])
    busy.status_code = 503
    responses = iter([busy, success])

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return next(responses)

    monkeypatch.setattr(client.session, "get", get)
    monkeypatch.setattr(client._get.retry, "wait", lambda state: 0)
    assert list(client.iter_survey_data("test")) == [{}]
    assert busy.closed and success.closed
    assert len(calls) == 2


@pytest.mark.parametrize("status", [400, 401, 403, 428, 429, 500])
def test_http_errors_close_the_response(monkeypatch, status):
    client, response, _ = client_response(monkeypatch, [b"error"], max_retries=1)
    response.status_code = status
    with pytest.raises(ForstaError):
        list(client.iter_survey_data("test"))
    assert response.closed
