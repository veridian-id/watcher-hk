# -*- encoding: utf-8 -*-

"""
KERI
testing watopnet.core.watching package

"""
import errno
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import MagicMock

import falcon
import pytest
from falcon import testing
from hio.base import doing
from keri import kering
from keri.app import habbing
from keri.core import eventing
from watopnet.core import basing
from watopnet.app import watching
from watopnet.app.watching import (
    CueDoer,
    ResponseDoer,
    Sentinal,
    States,
    Watcher,
    Watchery,
)

CONTROLLER_AID = "ENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZM4hbEI7nza"


def _bootClient(wty):
    app = falcon.App()
    app.add_route("/watchers", watching.WatcherCollectionEnd(wty=wty))
    return testing.TestClient(app)


@pytest.mark.parametrize(
    "body, description",
    [
        ([], "request body must be a JSON object"),
        ({"aid": 5}, "field 'aid' must be a string"),
        ({"aid": CONTROLLER_AID, "oobi": 5}, "field 'oobi' must be a string"),
        ({"aid": CONTROLLER_AID, "oobi": "ftp://example.com/oobi"}, "field 'oobi' must be an http or https URL"),
        ({"aid": CONTROLLER_AID, "oobi": "http:///oobi"}, "field 'oobi' must include a network location"),
    ],
)
def test_create_watcher_rejects_bad_input_before_provisioning(body, description):
    wty = MagicMock()

    response = _bootClient(wty).simulate_post("/watchers", json=body)

    assert response.status == falcon.HTTP_400
    assert response.json["description"] == description
    wty.createWatcher.assert_not_called()


def test_watcher_fd_exhaustion_detection_handles_oserror_and_lmdb_text():
    assert watching._isFdExhaustion(OSError(errno.EMFILE, "Too many open files"))
    assert watching._isFdExhaustion(RuntimeError("lmdb failure: Too many open files"))
    assert not watching._isFdExhaustion(RuntimeError("some other failure"))


def test_create_watcher_fd_exhaustion_returns_service_unavailable():
    wty = MagicMock()
    wty.createWatcher.side_effect = RuntimeError("lmdb failure: Too many open files")

    response = _bootClient(wty).simulate_post("/watchers", json={"aid": CONTROLLER_AID})

    assert response.status == falcon.HTTP_503
    assert response.json["title"] == "Watcher service unavailable"
    wty._logFdExhaustion.assert_called_once_with(CONTROLLER_AID)


def test_watchery_logs_fd_state_on_exhaustion(monkeypatch):
    logged = []
    monkeypatch.setattr(watching.logger, "exception", lambda msg: logged.append(msg))
    wty = SimpleNamespace(wats={"a": None, "b": None})

    watching.Watchery._logFdExhaustion(wty, CONTROLLER_AID)

    assert len(logged) == 1
    assert f"controller={CONTROLLER_AID} active_watchers=2" in logged[0]
    assert "fd_count=" in logged[0] and "fd_soft_limit=" in logged[0]


@pytest.mark.parametrize(("escrowTock", "expectedCount"), ((None, 2), ("1.0", 1)))
def test_escrow_doer_processes_escrows_at_configured_cadence(monkeypatch, escrowTock, expectedCount):
    monkeypatch.delenv("WATOPNET_ESCROW_TOCK", raising=False)
    if escrowTock is not None:
        monkeypatch.setenv("WATOPNET_ESCROW_TOCK", escrowTock)

    kvy, rvy, tvy, exc = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    doer = watching.EscrowDoer(kvy=kvy, rvy=rvy, tvy=tvy, exc=exc)

    doist = doing.Doist(tock=0.03125, limit=1.0, doers=[doer])
    doist.do()

    assert kvy.processEscrows.call_count == expectedCount
    assert rvy.processEscrowReply.call_count == expectedCount
    assert tvy.processEscrows.call_count == expectedCount
    assert exc.processEscrow.call_count == expectedCount


def test_adding_watched(mockHelpingNowUTC):
    with (
        habbing.openHab(name="bob", salt=b"0123456789fedbob") as (bobHby, bobHab),
        habbing.openHab(name="eve", salt=b"0123456789fedeve") as (eveHby, eveHab),
        habbing.openHab(name="wan", transferable=False, salt=b"0123456789fedcba") as (
            watHby,
            watHab,
        ),
    ):
        assert bobHab.pre == "ENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZM4hbEI7nza"
        assert eveHab.pre == "ELiJTS4bBx5gZlT68OjBxFiirP0Qa2XQZ6V5cjHWQR0p"
        assert watHab.pre == "BGbLRtLXIslZvTfYz97dS9_EzQxp8kSTAMMtW-LmlXMI"

        db = basing.Baser(name="bob", temp=True)

        wty = Watchery(db=db, temp=True)
        watcher = Watcher(wty=wty, db=db, hby=watHby, hab=watHab, cid=bobHab.pre)

        # with trans cid for nel and eid for wat
        route = f"/watcher/{watHab.pre}/add"
        data = dict(cid=bobHab.pre, oid=eveHab.pre, oobi="http://localhost:2701/oobi")

        serder = eventing.reply(
            route=route,
            data=data,
        )
        ims = bobHab.endorse(serder)
        assert ims == (
            b'{"v":"KERI10JSON000152_","t":"rpy","d":"EK_hu3_toGjYLYqmHMeMAMdf'
            b'7FVlWHktd2P6nn8o2ad6","dt":"2021-01-01T00:00:00.000000+00:00","r'
            b'":"/watcher/BGbLRtLXIslZvTfYz97dS9_EzQxp8kSTAMMtW-LmlXMI/add","a'
            b'":{"cid":"ENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZM4hbEI7nza","oid":"E'
            b'LiJTS4bBx5gZlT68OjBxFiirP0Qa2XQZ6V5cjHWQR0p","oobi":"http://loca'
            b'lhost:2701/oobi"}}-VA0-FABENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZM4hb'
            b"EI7nza0AAAAAAAAAAAAAAAAAAAAAAAENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZ"
            b"M4hbEI7nza-AABAABMkyXJW9f-ZxfSmu7Wses7EPEe_c17TRFSW1d9At-RF4WKms"
            b"5lDCUrOooCi9Ndkan3UxtbKqG6oApOgsbPqUYI"
        )

        icp = bobHab.makeOwnInception()
        watcher.psr.parseOne(icp)
        assert bobHab.pre in watcher.hby.kevers

        watcher.psr.parseOne(ims)

        keys = (bobHab.pre, watHab.pre, eveHab.pre)

        saider = watcher.hby.db.wwas.get(keys=keys)
        assert saider.qb64 == serder.said

        observed = watcher.hby.db.obvs.get(keys=keys)
        assert observed.enabled is True


def test_sentinal_queries_witness_state_with_messenger(monkeypatch):
    class FakeStore:
        def __init__(self):
            self.values = {}

        def get(self, keys):
            return self.values.get(keys)

        def rem(self, keys):
            self.values.pop(keys, None)

        def put(self, keys, val):
            self.values[keys] = val

    class FakeWitnessQueryStore:
        def __init__(self):
            self.calls = []

        def pin(self, *, keys, val):
            self.calls.append((keys, val))

    knas = FakeStore()
    ksns = FakeStore()
    witq = FakeWitnessQueryStore()
    db = SimpleNamespace(knas=knas, ksns=ksns, witq=witq)

    query_calls = []

    class FakeKever:
        wits = ["WIT_1"]
        sn = 0

        @staticmethod
        def state():
            return "local-state"

    class FakeHab:
        pre = "WATCHER_AID"
        kever = FakeKever()

        @staticmethod
        def query(*, pre, src, route):
            query_calls.append((pre, src, route))
            return b"ksn-query"

    class FakeMessenger:
        def __init__(self):
            self.idle = False

            class Messages(list):
                def append(inner_self, item):
                    assert item == bytearray(b"ksn-query")
                    knas.put(("OBSERVED_AID", "WIT_1"), SimpleNamespace(qb64="SAID_1"))
                    ksns.put(("SAID_1",), "witness-state")
                    self.idle = True
                    super().append(item)

            self.msgs = Messages()

    monkeypatch.setattr(
        "watopnet.app.watching.agenting.messenger",
        lambda hab, wit: FakeMessenger(),
    )
    monkeypatch.setattr(
        Sentinal,
        "diffState",
        staticmethod(
            lambda wit, preksn, witksn: SimpleNamespace(
                wit=wit,
                state=States.even,
                sn=0,
                dig="DIG_1",
            )
        ),
    )

    sentinal = Sentinal(
        hby=SimpleNamespace(db=db, kevers={"OBSERVED_AID": FakeKever()}),
        hab=SimpleNamespace(pre=FakeHab.pre, db=db, kever=FakeHab.kever, query=FakeHab.query),
        oid="OBSERVED_AID",
        cid="CONTROLLER_AID",
        oobi="http://watcher.example/oobi",
        db=SimpleNamespace(witq=witq),
    )
    monkeypatch.setattr(sentinal, "extend", lambda doers: None)
    monkeypatch.setattr(sentinal, "remove", lambda doers: None)

    do = sentinal.watch(lambda: 0.0, tock=0.0)
    assert next(do) == 0.0
    with pytest.raises(StopIteration) as stop:
        next(do)

    assert stop.value.value is True
    assert query_calls == [("OBSERVED_AID", "WIT_1", "ksn")]
    assert len(witq.calls) == 1
    keys, query = witq.calls[0]
    assert keys == ("WATCHER_AID", "OBSERVED_AID", "WIT_1")
    assert query.response_received is True
    assert query.state == States.even
    assert query.keystate == "witness-state"


def test_sentinal_waits_for_delayed_witness_state(monkeypatch):
    class FakeStore:
        def __init__(self):
            self.values = {}

        def get(self, keys):
            return self.values.get(keys)

        def rem(self, keys):
            self.values.pop(keys, None)

        def put(self, keys, val):
            self.values[keys] = val

    class FakeWitnessQueryStore:
        def __init__(self):
            self.calls = []

        def pin(self, *, keys, val):
            self.calls.append((keys, val))

    knas = FakeStore()
    ksns = FakeStore()
    witq = FakeWitnessQueryStore()
    db = SimpleNamespace(knas=knas, ksns=ksns, witq=witq)

    query_calls = []

    class FakeKever:
        wits = ["WIT_1"]
        sn = 0

        @staticmethod
        def state():
            return "local-state"

    class FakeHab:
        pre = "WATCHER_AID"
        kever = FakeKever()

        @staticmethod
        def query(*, pre, src, route):
            query_calls.append((pre, src, route))
            return b"ksn-query"

    class FakeMessenger:
        def __init__(self):
            self.idle = False

            class Messages(list):
                def append(inner_self, item):
                    assert item == bytearray(b"ksn-query")
                    self.idle = True
                    super().append(item)

            self.msgs = Messages()

    monkeypatch.setattr(
        "watopnet.app.watching.agenting.messenger",
        lambda hab, wit: FakeMessenger(),
    )
    monkeypatch.setattr(
        Sentinal,
        "diffState",
        staticmethod(
            lambda wit, preksn, witksn: SimpleNamespace(
                wit=wit,
                state=States.even,
                sn=0,
                dig="DIG_1",
            )
        ),
    )

    sentinal = Sentinal(
        hby=SimpleNamespace(db=db, kevers={"OBSERVED_AID": FakeKever()}),
        hab=SimpleNamespace(pre=FakeHab.pre, db=db, kever=FakeHab.kever, query=FakeHab.query),
        oid="OBSERVED_AID",
        cid="CONTROLLER_AID",
        oobi="http://watcher.example/oobi",
        db=SimpleNamespace(witq=witq),
    )
    monkeypatch.setattr(sentinal, "extend", lambda doers: None)
    monkeypatch.setattr(sentinal, "remove", lambda doers: None)

    do = sentinal.watch(lambda: 0.0, tock=0.0)
    assert next(do) == 0.0
    assert next(do) == 0.0

    knas.put(("OBSERVED_AID", "WIT_1"), SimpleNamespace(qb64="SAID_1"))
    ksns.put(("SAID_1",), "witness-state")

    with pytest.raises(StopIteration) as stop:
        next(do)

    assert stop.value.value is True
    assert query_calls == [("OBSERVED_AID", "WIT_1", "ksn")]
    assert len(witq.calls) == 1
    keys, query = witq.calls[0]
    assert keys == ("WATCHER_AID", "OBSERVED_AID", "WIT_1")
    assert query.response_received is True
    assert query.state == States.even
    assert query.keystate == "witness-state"


def test_sentinal_pins_unresolved_witness_endpoint_without_crashing(monkeypatch):
    class FakeWitnessQueryStore:
        def __init__(self):
            self.calls = []

        def pin(self, *, keys, val):
            self.calls.append((keys, val))

    witq = FakeWitnessQueryStore()

    class FakeKever:
        wits = ["WIT_1"]
        sn = 0

        @staticmethod
        def state():
            return "local-state"

    query_calls = []

    class FakeHab:
        pre = "WATCHER_AID"
        db = SimpleNamespace(
            knas=SimpleNamespace(get=lambda keys: None, rem=lambda keys: None),
            ksns=SimpleNamespace(rem=lambda keys: None),
        )
        kever = FakeKever()

        @staticmethod
        def query(*, pre, src, route):
            query_calls.append((pre, src, route))
            return b"ksn-query"

    def fake_messenger(hab, wit):
        raise kering.ConfigurationError(
            f"unable to find a valid endpoint for witness={wit}"
        )

    monkeypatch.setattr("watopnet.app.watching.agenting.messenger", fake_messenger)

    sentinal = Sentinal(
        hby=SimpleNamespace(kevers={"OBSERVED_AID": FakeKever()}),
        hab=FakeHab(),
        oid="OBSERVED_AID",
        cid="CONTROLLER_AID",
        oobi="http://watcher.example/oobi",
        db=SimpleNamespace(witq=witq),
    )
    monkeypatch.setattr(sentinal, "extend", lambda doers: None)
    monkeypatch.setattr(sentinal, "remove", lambda doers: None)

    do = sentinal.watch(lambda: 0.0, tock=0.0)
    assert next(do) == 0.0
    with pytest.raises(StopIteration) as stop:
        next(do)

    assert stop.value.value is True
    assert query_calls == []
    assert len(witq.calls) == 1
    keys, query = witq.calls[0]
    assert keys == ("WATCHER_AID", "OBSERVED_AID", "WIT_1")
    assert query.response_received is False
    assert query.state == States.unresponsive
    assert query.error == "Missing witness endpoint: unable to find a valid endpoint for witness=WIT_1"


def test_watcher_pushes_ksn_for_observed_aid(mockHelpingNowUTC):
    with (
        habbing.openHab(name="bob", salt=b"0123456789fedbob") as (bobHby, bobHab),
        habbing.openHab(name="eve", salt=b"0123456789fedeve") as (eveHby, eveHab),
        habbing.openHab(name="wan", transferable=False, salt=b"0123456789fedcba") as (
            watHby,
            watHab,
        ),
    ):
        db = basing.Baser(name="wan", temp=True)
        wty = Watchery(db=db, temp=True)
        watcher = Watcher(wty=wty, db=db, hby=watHby, hab=watHab, cid=bobHab.pre)

        cueDoer = next(d for d in watcher.doers if isinstance(d, CueDoer))
        responseDoer = next(d for d in watcher.doers if isinstance(d, ResponseDoer))

        watcher.psr.parseOne(bobHab.makeOwnInception())

        add = eventing.reply(
            route=f"/watcher/{watHab.pre}/add",
            data=dict(
                cid=bobHab.pre, oid=eveHab.pre, oobi="http://localhost:2701/oobi"
            ),
        )
        watcher.psr.parseOne(bobHab.endorse(add))
        assert watHby.db.obvs.get(keys=(bobHab.pre, watHab.pre, eveHab.pre)).enabled

        watcher.psr.parseOne(eveHab.makeOwnInception())

        cueDoer.recur()
        responseDoer.recur()

        assert len(watcher.poster.evts) == 1
        evt = watcher.poster.evts.popleft()
        assert evt["dest"] == bobHab.pre
        assert evt["topic"] == "reply"
        assert evt["hab"] is watHab
        assert evt["serder"].ked["r"] == f"/ksn/{watHab.pre}"
        assert evt["serder"].ked["a"]["i"] == eveHab.pre
        assert evt["serder"].ked["a"]["d"] == eveHab.kever.serder.said
        assert evt["attachment"]


def test_watcher_drops_response_for_unresolved_dest(mockHelpingNowUTC):
    with (
        habbing.openHab(name="bob", salt=b"0123456789fedbob") as (bobHby, bobHab),
        habbing.openHab(name="eve", salt=b"0123456789fedeve") as (eveHby, eveHab),
        habbing.openHab(name="wan", transferable=False, salt=b"0123456789fedcba") as (
            watHby,
            watHab,
        ),
    ):
        db = basing.Baser(name="wan", temp=True)
        wty = Watchery(db=db, temp=True)
        watcher = Watcher(wty=wty, db=db, hby=watHby, hab=watHab, cid=bobHab.pre)

        responseDoer = next(d for d in watcher.doers if isinstance(d, ResponseDoer))

        rpy = eventing.reply(
            route=f"/ksn/{watHab.pre}", data=asdict(eveHab.kever.state())
        )
        watcher.responses.append(
            dict(kin="reply", src=watHab.pre, dest=bobHab.pre, serder=rpy)
        )

        responseDoer.recur()

        assert not watcher.responses
        assert not watcher.poster.evts


def test_diff_state_uses_ksn_sequence_and_validates_aid():
    ours = Sentinal.diffState(
        "WIT_1",
        SimpleNamespace(i="AID_1", s="5", d="DIG_5"),
        SimpleNamespace(i="AID_1", s="6", f="2", d="DIG_6"),
    )
    assert ours.state == States.ahead
    assert ours.sn == 6
    assert ours.dig == "DIG_6"

    # first-seen ordinal runs past sn after a recovery rotation; only sn is comparable
    even = Sentinal.diffState(
        "WIT_1",
        SimpleNamespace(i="AID_1", s="5", d="DIG_5"),
        SimpleNamespace(i="AID_1", s="5", f="7", d="DIG_5"),
    )
    assert even.state == States.even

    with pytest.raises(ValueError):
        Sentinal.diffState(
            "WIT_1",
            SimpleNamespace(i="AID_1", s="5", d="DIG_5"),
            SimpleNamespace(i="AID_2", s="5", f="5", d="DIG_5"),
        )


def test_sentinal_records_invalid_witness_ksn_and_checks_the_rest(monkeypatch):
    class FakeStore:
        def __init__(self):
            self.values = {}

        def get(self, keys):
            return self.values.get(keys)

        def rem(self, keys):
            self.values.pop(keys, None)

        def put(self, keys, val):
            self.values[keys] = val

    class FakeWitnessQueryStore:
        def __init__(self):
            self.calls = []

        def pin(self, *, keys, val):
            self.calls.append((keys, val))

    knas = FakeStore()
    ksns = FakeStore()
    witq = FakeWitnessQueryStore()
    db = SimpleNamespace(knas=knas, ksns=ksns, witq=witq)

    class FakeKever:
        wits = ["WIT_1", "WIT_2"]
        sn = 0

        @staticmethod
        def state():
            return SimpleNamespace(i="OBSERVED_AID", s="0", d="DIG_0")

    class FakeMessenger:
        def __init__(self, wit):
            self.idle = False
            outer = self

            class Messages(list):
                def append(inner_self, item):
                    knas.put(("OBSERVED_AID", wit), SimpleNamespace(qb64=f"SAID_{wit}"))
                    other = "WRONG_AID" if wit == "WIT_1" else "OBSERVED_AID"
                    ksns.put((f"SAID_{wit}",), SimpleNamespace(i=other, s="0", d="DIG_0"))
                    outer.idle = True
                    super().append(item)

            self.msgs = Messages()

    monkeypatch.setattr("watopnet.app.watching.agenting.messenger", lambda hab, wit: FakeMessenger(wit))

    sentinal = Sentinal(
        hby=SimpleNamespace(db=db, kevers={"OBSERVED_AID": FakeKever()}),
        hab=SimpleNamespace(pre="WATCHER_AID", db=db, kever=FakeKever(), query=lambda **kwa: b"ksn-query"),
        oid="OBSERVED_AID",
        cid="CONTROLLER_AID",
        oobi="http://watcher.example/oobi",
        db=SimpleNamespace(witq=witq),
    )
    monkeypatch.setattr(sentinal, "extend", lambda doers: None)
    monkeypatch.setattr(sentinal, "remove", lambda doers: None)

    do = sentinal.watch(lambda: 0.0, tock=0.0)
    assert next(do) == 0.0
    with pytest.raises(StopIteration) as stop:
        next(do)

    assert stop.value.value is True
    (_, first), (_, second) = witq.calls[:2]
    assert first.wit == "WIT_1"
    assert first.response_received is False
    assert first.error.startswith("Invalid key state notice from witness:")
    assert second.wit == "WIT_2"
    assert second.response_received is True
    assert second.state == States.even


def test_delete_watcher_forgets_it_and_stops_doers_before_closing_db():
    calls = []
    watcher = SimpleNamespace(cid="CID", hby=SimpleNamespace(close=lambda clear: calls.append(("close", clear))))
    wty = SimpleNamespace(
        wats={"EID": watcher},
        db=SimpleNamespace(wats=MagicMock(), cids=MagicMock()),
        remove=lambda doers: calls.append(("remove", doers)),
    )

    Watchery.deleteWatcher(wty, "EID")

    assert "EID" not in wty.wats
    assert calls == [("remove", [watcher]), ("close", True)]
    with pytest.raises(ValueError):
        Watchery.deleteWatcher(wty, "EID")


def test_sentinal_recovers_from_the_ahead_witness(monkeypatch):
    class FakeStore:
        def __init__(self):
            self.values = {}

        def get(self, keys):
            return self.values.get(keys)

        def rem(self, keys):
            self.values.pop(keys, None)

        def put(self, keys, val):
            self.values[keys] = val

    knas = FakeStore()
    ksns = FakeStore()
    witq = SimpleNamespace(pin=lambda **kwa: None)
    db = SimpleNamespace(knas=knas, ksns=ksns, witq=witq)

    class FakeKever:
        wits = ["WIT_1", "WIT_2"]
        sn = 0

        @staticmethod
        def state():
            # first-seen ordinal ahead of sn, as after a recovery rotation
            return SimpleNamespace(i="OBSERVED_AID", s="0", f="3", d="DIG_0")

    class FakeMessenger:
        def __init__(self, wit):
            self.idle = False
            outer = self

            class Messages(list):
                def append(inner_self, item):
                    knas.put(("OBSERVED_AID", wit), SimpleNamespace(qb64=f"SAID_{wit}"))
                    ksns.put((f"SAID_{wit}",), wit)
                    outer.idle = True
                    super().append(item)

            self.msgs = Messages()

    monkeypatch.setattr("watopnet.app.watching.agenting.messenger", lambda hab, wit: FakeMessenger(wit))
    monkeypatch.setattr(
        Sentinal,
        "diffState",
        staticmethod(lambda wit, preksn, witksn: SimpleNamespace(
            wit=wit,
            state=States.ahead if wit == "WIT_2" else States.even,
            sn=2 if wit == "WIT_2" else 0,
            dig="DIG_2" if wit == "WIT_2" else "DIG_0",
        )),
    )

    kevers = {"OBSERVED_AID": FakeKever()}
    sentinal = Sentinal(
        hby=SimpleNamespace(db=db, kevers=kevers),
        hab=SimpleNamespace(pre="WATCHER_AID", db=db, kever=FakeKever(), kevers=kevers, query=lambda **kwa: b"ksn-query"),
        oid="OBSERVED_AID",
        cid="CONTROLLER_AID",
        oobi="http://watcher.example/oobi",
        db=SimpleNamespace(witq=witq),
    )
    extended = []
    monkeypatch.setattr(sentinal, "extend", lambda doers: extended.extend(doers))
    monkeypatch.setattr(sentinal, "remove", lambda doers: None)

    do = sentinal.watch(lambda: 0.0, tock=0.0)
    assert next(do) == 0.0
    with pytest.raises(StopIteration):
        next(do)

    recovery = [doer for doer in extended if isinstance(doer, watching.querying.SeqNoQuerier)]
    assert len(recovery) == 1
    assert recovery[0].fn == 4
    assert recovery[0].sn == 2
    query = recovery[0].witq.msgs[0]
    assert query["wits"] == ["WIT_2"]
    assert query["q"] == {"s": "2", "fn": "4"}
