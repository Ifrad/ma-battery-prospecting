import httpx
import pytest

from prospect.ingest.client import USER_AGENT, Client


def make_client(statuses, sleeps, **kwargs):
    """Client whose transport answers with `statuses` in order."""
    calls = []

    def handler(request):
        calls.append(request)
        status = statuses[min(len(calls), len(statuses)) - 1]
        return httpx.Response(status, json={"ok": status == 200})

    client = Client(
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
        clock=lambda: 0.0,
        **kwargs,
    )
    return client, calls


def test_retries_server_errors_then_succeeds():
    client, calls = make_client([503, 429, 200], [])
    assert client.get("https://example.test/a").json() == {"ok": True}
    assert len(calls) == 3


def test_does_not_retry_client_errors():
    client, calls = make_client([404], [])
    with pytest.raises(httpx.HTTPStatusError):
        client.get("https://example.test/a")
    assert len(calls) == 1


def test_gives_up_after_attempts():
    client, calls = make_client([500], [], attempts=3)
    with pytest.raises(httpx.HTTPStatusError):
        client.get("https://example.test/a")
    assert len(calls) == 3


def test_retries_network_errors():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("down", request=request)
        return httpx.Response(200)

    client = Client(transport=httpx.MockTransport(handler), sleep=lambda s: None)
    assert client.get("https://example.test/a").status_code == 200
    assert len(calls) == 2


def test_sends_user_agent_and_params():
    client, calls = make_client([200], [])
    client.get("https://example.test/q", params={"where": "1=1"})
    assert calls[0].headers["User-Agent"] == USER_AGENT
    assert calls[0].url.params["where"] == "1=1"


def test_waits_between_requests():
    sleeps = []
    client, _ = make_client([200], sleeps, delay=2.0)
    client.get("https://example.test/1")
    assert sleeps == []
    client.get("https://example.test/2")
    assert sleeps == [2.0]
