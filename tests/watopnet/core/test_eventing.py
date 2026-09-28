# -*- encoding: utf-8 -*-

"""
KERI
testing watopnet.core.eventing package

"""
import datetime

from keri import core
from keri.app import habbing
from keri.core import eventing, parsing, routing
from keri.help import helping

from watopnet.core import basing
from watopnet.core.eventing import PruningKevery

WES_SALT = core.Salter(raw=b'\x05\xaa\x8f-S\x9a\xe9\xfaU\x9c\x02\x9c\x9b\x08Hu').qb64
SALT = core.Salter(raw=b'0123456789abcdef').qb64


def _replyCounts(db):
    return tuple(
        sum(1 for _ in sub.getItemIter()) for sub in (db.rpys, db.sdts, db.scgs)
    )


def test_pruning_kevery_keeps_one_reply_per_source_across_polls():
    with (habbing.openHby(name="bob", base="test", salt=SALT) as bobHby,
          habbing.openHby(name="bam", base="test", salt=SALT) as bamHby,
          habbing.openHby(name="wes", base="test", salt=WES_SALT) as wesHby):
        wdb = basing.Baser(name="pruning", temp=True)

        wesHab = wesHby.makeHab(name="wes", isith='1', icount=1, transferable=False)
        bobHab = bobHby.makeHab(name="bob", isith='1', icount=1, transferable=True,
                                wits=[wesHab.pre])
        parsing.Parser().parse(ims=bytearray(bobHab.makeOwnEvent(sn=0)),
                               kvy=eventing.Kevery(db=wesHby.db), local=True)

        rtr = routing.Router()
        rvy = routing.Revery(db=bamHby.db, rtr=rtr)
        kvy = PruningKevery(wdb=wdb, db=bamHby.db, rvy=rvy, lax=True, local=False)
        kvy.registerReplyRoutes(router=rtr)

        ksr = wesHab.kevers[bobHab.pre].state()
        start = helping.nowUTC()
        saids = []
        for poll in range(4):
            stamp = helping.toIso8601(start + datetime.timedelta(seconds=poll))
            msg = wesHab.reply(route="/ksn/" + wesHab.pre, data=ksr._asdict(), stamp=stamp)
            saids.append(bytes(msg))
            parsing.Parser().parse(ims=bytearray(msg), kvy=kvy, rvy=rvy, local=True)
            assert _replyCounts(bamHby.db) == (1, 1, 1)

        assert wdb.krpy.get(keys=(bobHab.pre, wesHab.pre)) is not None
        assert bamHby.db.knas.get((bobHab.pre, wesHab.pre)).qb64 == bobHab.kever.serder.said


def test_pruning_kevery_keeps_a_reply_per_witness():
    with (habbing.openHby(name="bob", base="test", salt=SALT) as bobHby,
          habbing.openHby(name="bam", base="test", salt=SALT) as bamHby,
          habbing.openHby(name="wes", base="test", salt=WES_SALT) as wesHby,
          habbing.openHby(name="wil", base="test", salt=SALT) as wilHby):
        wdb = basing.Baser(name="pruning-pool", temp=True)

        wesHab = wesHby.makeHab(name="wes", isith='1', icount=1, transferable=False)
        wilHab = wilHby.makeHab(name="wil", isith='1', icount=1, transferable=False)
        bobHab = bobHby.makeHab(name="bob", isith='1', icount=1, transferable=True,
                                wits=[wesHab.pre, wilHab.pre])
        icp = bobHab.makeOwnEvent(sn=0)
        for hby in (wesHby, wilHby):
            parsing.Parser().parse(ims=bytearray(icp), kvy=eventing.Kevery(db=hby.db),
                                   local=True)

        rtr = routing.Router()
        rvy = routing.Revery(db=bamHby.db, rtr=rtr)
        kvy = PruningKevery(wdb=wdb, db=bamHby.db, rvy=rvy, lax=True, local=False)
        kvy.registerReplyRoutes(router=rtr)

        start = helping.nowUTC()
        for poll in range(3):
            for hab in (wesHab, wilHab):
                stamp = helping.toIso8601(start + datetime.timedelta(seconds=poll))
                ksr = hab.kevers[bobHab.pre].state()
                msg = hab.reply(route="/ksn/" + hab.pre, data=ksr._asdict(), stamp=stamp)
                parsing.Parser().parse(ims=bytearray(msg), kvy=kvy, rvy=rvy, local=True)

        assert _replyCounts(bamHby.db) == (2, 2, 2)
