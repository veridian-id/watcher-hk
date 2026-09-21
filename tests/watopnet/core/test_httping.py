# -*- encoding: utf-8 -*-
"""
KERI
testing watopnet.core.httping module

"""
import datetime
from types import SimpleNamespace

import falcon
from falcon import testing

from watopnet.core import basing, httping


def _request(remote, headers=None):
    env = testing.create_environ(headers=headers or {})
    env["REMOTE_ADDR"] = remote  # hio's shape: the connection's (host, port)
    return falcon.Request(env)


def _response():
    return SimpleNamespace(complete=False, status=None)


def test_throttle_keys_on_peer_host_across_connections():
    db = basing.Baser(name="throttle-peer-host", temp=True)
    try:
        throttle = httping.Throttle(db=db)

        throttle.process_request(_request(("172.18.0.5", 51000)), _response())
        throttle.process_request(_request(("172.18.0.5", 51001)), _response())
        throttle.process_request(_request(("172.18.0.6", 51002)), _response())

        assert db.ips.get(keys=("172.18.0.5",)).count == 2
        assert db.ips.get(keys=("172.18.0.6",)).count == 1
        assert db.ips.get(keys=("1",)) is None
    finally:
        db.close(clear=True)


def test_throttle_ignores_forwarded_headers():
    db = basing.Baser(name="throttle-forwarded", temp=True)
    try:
        throttle = httping.Throttle(db=db)
        req = _request(("172.18.0.5", 51000), headers={"X-Forwarded-For": "203.0.113.10"})

        throttle.process_request(req, _response())

        assert db.ips.get(keys=("172.18.0.5",)).count == 1
        # the forwarded address is client-supplied, so it must not pick the bucket
        assert db.ips.get(keys=("203.0.113.10",)) is None
        assert db.ips.get(keys=("2",)) is None
    finally:
        db.close(clear=True)


def test_throttle_resets_count_after_window_rollover(monkeypatch):
    db = basing.Baser(name="throttle-rollover", temp=True)
    try:
        throttle = httping.Throttle(db=db)
        start = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
        times = iter([
            start,
            start + datetime.timedelta(seconds=1),
            start + httping.Throttle.Window + datetime.timedelta(seconds=1),
        ])
        monkeypatch.setattr(httping.helping, "nowUTC", lambda: next(times))

        for expected in (1, 2, 1):
            throttle.process_request(_request(("127.0.0.1", 50000)), _response())
            assert db.ips.get(keys=("127.0.0.1",)).count == expected
    finally:
        db.close(clear=True)


def test_throttle_rejects_over_limit(monkeypatch):
    db = basing.Baser(name="throttle-limit", temp=True)
    try:
        monkeypatch.setattr(httping.Throttle, "MaximumRequests", 2)
        throttle = httping.Throttle(db=db)

        for _ in range(2):
            rep = _response()
            throttle.process_request(_request(("127.0.0.1", 50000)), rep)
            assert rep.complete is False

        rep = _response()
        throttle.process_request(_request(("127.0.0.1", 50000)), rep)
        assert rep.complete is True
        assert rep.status == falcon.HTTP_TOO_MANY_REQUESTS
    finally:
        db.close(clear=True)
