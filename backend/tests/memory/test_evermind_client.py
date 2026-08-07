from backend.memory.evermind import EverOSMemory


def _configured_memory(monkeypatch) -> EverOSMemory:
    monkeypatch.setenv("EVEROS_BASE_URL", "http://fake-everos.test")
    monkeypatch.setenv("EVEROS_API_KEY", "test-key")
    monkeypatch.setenv("EVEROS_NAMESPACE", "testns")
    return EverOSMemory()


def test_unconfigured_client_returns_defaults_without_network(monkeypatch):
    monkeypatch.delenv("EVEROS_API_KEY", raising=False)
    monkeypatch.delenv("EVEROS_BASE_URL", raising=False)
    memory = EverOSMemory()

    assert memory.health() == {"ok": False, "detail": "EVEROS_API_KEY/EVEROS_BASE_URL not set"}
    profile = memory.get_profile("alice")
    assert profile.specialty is None
    assert profile.conditions_explored == []
    assert memory.seen_pmids("alice") == set()


def test_get_profile_namespaces_by_user(monkeypatch):
    memory = _configured_memory(monkeypatch)
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(memory, "_request", lambda method, path, **kw: calls.append((method, path)) or None)

    memory.get_profile("alice")
    memory.get_profile("bob")

    assert calls == [("GET", "/v1/profile/testns:alice"), ("GET", "/v1/profile/testns:bob")]
    assert calls[0][1] != calls[1][1]


def test_thread_namespace_includes_session(monkeypatch):
    memory = _configured_memory(monkeypatch)
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(memory, "_request", lambda method, path, **kw: calls.append((method, path)) or None)

    memory.get_thread("alice", "sess-1")

    assert calls == [("GET", "/v1/thread/testns:alice:sess-1")]


def test_get_profile_returns_empty_default_on_miss(monkeypatch):
    memory = _configured_memory(monkeypatch)
    monkeypatch.setattr(memory, "_request", lambda *a, **kw: None)

    profile = memory.get_profile("alice")

    assert profile.user_id == "alice"
    assert profile.specialty is None
    assert profile.conditions_explored == []
    assert profile.query_count == 0
    assert profile.distilled_context == ""


def test_user_a_never_reads_user_bs_profile(monkeypatch):
    memory = _configured_memory(monkeypatch)
    store = {
        "/v1/profile/testns:alice": {"specialty": "neuroradiology"},
        "/v1/profile/testns:bob": {"specialty": "oncology"},
    }
    monkeypatch.setattr(memory, "_request", lambda method, path, **kw: store.get(path))

    assert memory.get_profile("alice").specialty == "neuroradiology"
    assert memory.get_profile("bob").specialty == "oncology"


def test_forget_deletes_profile_and_evicts_seen_cache(monkeypatch):
    memory = _configured_memory(monkeypatch)
    deleted: list[str] = []

    def fake_request(method, path, **kw):
        if method == "DELETE":
            deleted.append(path)
            return {}
        if method == "GET":
            return {"pmids": []}
        return None

    monkeypatch.setattr(memory, "_request", fake_request)
    memory.seen_pmids("alice")  # populate the cache
    memory.forget("alice")

    assert deleted == ["/v1/namespace/testns:alice"]
    assert "alice" not in memory._seen_cache


def test_record_papers_shown_evicts_seen_cache_so_next_read_is_fresh(monkeypatch):
    memory = _configured_memory(monkeypatch)
    responses = iter([{"pmids": ["1"]}, {"pmids": ["1", "2"]}])

    def fake_request(method, path, **kw):
        if method == "GET":
            return next(responses)
        return {}

    monkeypatch.setattr(memory, "_request", fake_request)

    assert memory.seen_pmids("alice") == {"1"}
    memory.record_papers_shown("alice", "sess-1", ["2"])
    assert memory.seen_pmids("alice") == {"1", "2"}


def test_seen_pmids_cache_expires_after_ttl(monkeypatch):
    memory = _configured_memory(monkeypatch)
    call_count = {"n": 0}

    def fake_request(method, path, **kw):
        call_count["n"] += 1
        return {"pmids": ["1"]}

    monkeypatch.setattr(memory, "_request", fake_request)

    clock = {"t": 0.0}
    monkeypatch.setattr("backend.memory.evermind.time.monotonic", lambda: clock["t"])

    memory.seen_pmids("alice")
    clock["t"] += 30  # still within the 60s TTL
    memory.seen_pmids("alice")
    assert call_count["n"] == 1

    clock["t"] += 40  # 70s elapsed total, past the TTL
    memory.seen_pmids("alice")
    assert call_count["n"] == 2
