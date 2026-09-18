import gzip
import json

import httpx
import pytest

from inequality_map.download import Downloader, read_payload, validate_csv, wb_page


def downloader(tmp_path, handler, attempts=2):
    return Downloader(tmp_path, {"attempts": attempts, "timeout_seconds": 1,
        "world_bank": {"base_url": "https://example.test/", "per_page": 1}}, httpx.Client(transport=httpx.MockTransport(handler)))


def test_pagination_and_immutable_resume(tmp_path):
    calls = []
    def handler(req):
        page = int(req.url.params["page"])
        calls.append(page)
        return httpx.Response(200, json=[{"page": page, "pages": 2, "total": 2}, [{"id": page}]])
    d = downloader(tmp_path, handler)
    items, rows = d.pages("catalog", "country", "countries")
    assert rows == [{"id": 1}, {"id": 2}]
    assert calls == [1, 2]
    assert d.pages("catalog", "country", "countries")[1] == rows
    assert calls == [1, 2]
    assert json.loads(read_payload(tmp_path, items[0]))[0]["page"] == 1


def test_retry_failure_then_success(tmp_path, monkeypatch):
    monkeypatch.setattr("inequality_map.download.time.sleep", lambda _: None)
    calls = []
    def handler(req):
        calls.append(req)
        return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, text="country;variable\nBR;x\n")
    d = downloader(tmp_path, handler)
    item = d.fetch("test", "https://example.test/test", "wid", "data", validate_csv(["country", "variable"]))
    assert item["attempts"] == 2
    assert len(calls) == 2


def test_bounded_failure_and_corruption(tmp_path, monkeypatch):
    monkeypatch.setattr("inequality_map.download.time.sleep", lambda _: None)
    d = downloader(tmp_path, lambda req: httpx.Response(500))
    with pytest.raises(RuntimeError):
        d.fetch("bad", "https://example.test/bad", "wid", "data")
    assert not list(tmp_path.rglob("*.part"))
    d.client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, text="ok")))
    item = d.fetch("good", "https://example.test/good", "wid", "data")
    (tmp_path/item["path"]).write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="Immutable"):
        d.fetch("good", "https://example.test/good", "wid", "data")


def test_api_errors_and_truncation(tmp_path):
    with pytest.raises(ValueError):
        wb_page(b'[{"message":[{"id":"120"}]}]')
    d = downloader(tmp_path, lambda req: httpx.Response(200, json=[{"page": 1, "pages": 1, "total": 2}, [{"id": 1}]]))
    with pytest.raises(ValueError, match="truncated"):
        d.pages("test", "country", "countries")


def test_html_is_not_csv(tmp_path, monkeypatch):
    monkeypatch.setattr("inequality_map.download.time.sleep", lambda _: None)
    d = downloader(tmp_path, lambda req: httpx.Response(200, text="<html>maintenance</html>"))
    with pytest.raises(RuntimeError, match="Unexpected CSV"):
        d.fetch("bad", "https://example.test/bad", "wid", "data", validate_csv(["country", "variable"]))
