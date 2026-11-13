import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from mosaic_mmc import MMCError, canonical
from mosaic_mmc_t3.controller import Controller, _effect_result, project
from mosaic_mmc_t3.storage import Journal
from tests_t3.helpers import Env, TIME, observations


def extend(events, kind, payload, count):
    result=list(events)
    for _ in range(count):
        result.append(Journal.event(result,kind,payload))
    return result


def greatest_passing(base, kind, payload, probe, maximum=4090):
    maximum=min(maximum,4095-len(base))
    all_events=extend(base,kind,payload,maximum)
    low,high=0,maximum
    while low<high:
        middle=(low+high+1)//2
        try:
            probe(all_events[:len(base)+middle])
            low=middle
        except MMCError:
            high=middle-1
    return all_events[:len(base)+low]


def replace_events(path, events):
    connection=sqlite3.connect(path)
    try:
        connection.execute('DELETE FROM events')
        connection.executemany('INSERT INTO events VALUES (?,?)',
                               [(event['sequence'],canonical(event)) for event in events])
        connection.commit()
    finally:
        connection.close()


class JournalCapacityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env=Env(self.temp.name)

    def reopen(self):
        return Controller(self.env.controller.journal.path,
                          expected_policy_root=self.env.controller.journal.policy_root)

    def test_aggregate_capacity_refuses_atomically_and_remains_replayable(self):
        base=self.env.controller.journal.export()
        payload={'floor':4,'revoked':['revoked.key']}
        events=greatest_passing(base,'FLOOR_RAISED',payload,project)
        candidate=events+[Journal.event(events,'FLOOR_RAISED',payload)]
        with self.assertRaisesRegex(MMCError,'NODE_LIMIT'):
            project(candidate)
        replace_events(self.env.controller.journal.path,events)
        controller=self.reopen()
        before=controller.replay()['projection']['head']
        with self.assertRaisesRegex(MMCError,'JOURNAL_CAPACITY'):
            controller.raise_floor(4,['revoked.key'])
        self.assertEqual(controller.replay()['projection']['head'],before)
        self.assertEqual(self.reopen().replay()['projection']['head'],before)

    def test_effect_reservation_refuses_before_adapter_apply(self):
        request=self.env.prepare()
        self.env.approve(request)
        base=self.env.controller.journal.export()
        duplicate={'migration':self.env.mid,'record':observations(self.env.plan)[0]}

        def dispatched(events):
            intent=Journal.event(events,'DISPATCHED',
                                 {'operation_id':request['operation_id'],'time':TIME})
            project(events+[intent])

        events=greatest_passing(base,'OBSERVED',duplicate,dispatched)
        intent=Journal.event(events,'DISPATCHED',
                             {'operation_id':request['operation_id'],'time':TIME})
        dispatched_events=events+[intent]
        project(dispatched_events)  # The intent alone still fits.
        partial=Journal.event(dispatched_events,'OUTCOME',
                              {'operation_id':request['operation_id'],
                               'result':_effect_result(request,'PARTIAL')})
        partial_events=dispatched_events+[partial]
        applied=Journal.event(partial_events,'OUTCOME',
                              {'operation_id':request['operation_id'],
                               'result':_effect_result(request,'APPLIED')})
        with self.assertRaises(MMCError):
            project(partial_events+[applied])

        replace_events(self.env.controller.journal.path,events)
        controller=self.reopen()
        before=controller.replay()['projection']['head']
        target_before=self.env.store.snapshot(request['scope']['targets'])
        with patch.object(self.env.store,'apply',wraps=self.env.store.apply) as apply:
            with self.assertRaisesRegex(MMCError,'JOURNAL_CAPACITY'):
                controller.commit(request['operation_id'],self.env.store,TIME)
            apply.assert_not_called()
        self.assertEqual(self.env.store.snapshot(request['scope']['targets']),target_before)
        self.assertEqual(controller.replay()['projection']['head'],before)
        self.assertEqual(self.reopen().replay()['projection']['head'],before)


if __name__=='__main__':
    unittest.main()
