from concurrent.futures import ThreadPoolExecutor

from backend.shared_limits import SharedLimits


def test_workers_share_per_client_and_global_login_limits(tmp_path):
    path = tmp_path / "limits.sqlite3"
    workers = [SharedLimits(path), SharedLimits(path)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda i: workers[i % 2].allow_login("client", 1, 3, 6), range(20)))
    assert sum(results) == 3
    for i in range(3):
        assert workers[i % 2].allow_login(f"client-{i}", 1, 3, 6)
    assert not workers[0].allow_login("another-client", 1, 3, 6)
    assert workers[1].allow_login("client", 2, 3, 6)


def test_worker_lease_expires_and_can_be_released_by_other_workers(tmp_path):
    path = tmp_path / "limits.sqlite3"
    first, second = SharedLimits(path), SharedLimits(path)
    lease = first.acquire("sockets", 1, 30, now=100)
    assert lease
    assert second.acquire("sockets", 1, 30, now=101) is None
    assert second.acquire("sources", 1, 30, now=101)
    assert second.renew(lease, 30, now=110)
    assert first.acquire("sockets", 1, 30, now=139) is None
    replacement = first.acquire("sockets", 1, 30, now=140)
    assert replacement
    assert not second.renew(lease, 30, now=140)
    second.release(replacement)
    assert first.acquire("sockets", 1, 30, now=141)
