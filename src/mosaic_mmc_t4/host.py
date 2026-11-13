"""Explicit trusted-host seams. Not reachable from the data ABI or an opened document."""
from .common import *
from .views import snapshot, reader_for_sample, assess_view
from .work import review_submission


class AgentHost:
    """Evidence-only journal admission. Never approves or invokes a target adapter."""
    def __init__(self, controller):
        from mosaic_mmc_t3.controller import Controller
        require(type(controller) is Controller, "MMC_T4_CONTROLLER_TYPE")
        self.controller = controller

    @staticmethod
    def _snapshot(state, migration, transition):
        require(migration in state["migrations"], "MMC_T4_MIGRATION_MISSING")
        m=state["migrations"][migration]
        return snapshot(m["plan"],state["policy"],migration,transition,m["observations"],
                        floor=state["floor"],revoked=state["revoked"],head=state["head"])

    def capture(self, migration, transition):
        state=self.controller.replay()["projection"]
        return self._snapshot(state,migration,transition)

    def admit(self, migration, transition, reader, work_order, submission, *, expected_head, expected_work_root):
        """Caller deliberately authorizes an evidence write, with exact-head CAS."""
        require(expected_head is not None, "MMC_T4_HEAD_REQUIRED")
        submission=clone(submission);work_order=clone(work_order);reader=clone(reader)
        c=self.controller
        with c.journal.transaction(True) as con:
            events,state=c._load(con,expected_head)
            m=c._migration(state,migration)
            require(m["status"]=="ACTIVE", "MMC_T4_MIGRATION_NOT_ACTIVE")
            s=self._snapshot(state,migration,transition)
            review=review_submission(s,reader,work_order,submission,expected_work_root=expected_work_root)
            require(review["body"]["status"]=="ELIGIBLE_FOR_HOST_EVIDENCE_ADMISSION", "MMC_T4_SUBMISSION_NOT_ADMISSIBLE")
            if m["pending"]:
                o=state["operations"][m["pending"]]
                require(o["status"] in ("PREPARED","APPROVED","NOT_APPLIED"), "MMC_T4_UNRESOLVED_EFFECT")
                c._append(con,events,"CANCELLED",{"operation_id":m["pending"],"reason":"AGENT_EVIDENCE_CHANGED"})
            require(len(m["observations"])<256,"MMC_T4_RECORD_LIMIT")
            c._append(con,events,"OBSERVED",{"migration":migration,"record":clone(submission["record"])})
            head={"sequence":events[-1]["sequence"],"root":events[-1]["root"]}
        return {"schema":"mmc.agent-admission.t4","status":"SIGNED_OBSERVATION_STORED",
                "record_root":submission["record"]["root"],"review_root":review["root"],"head":head,
                "host_effect":"APPEND_EVIDENCE_TO_LOCAL_JOURNAL","target_effect":"NOT_EXECUTED",**BOUNDARY}


class ReadSession:
    """Host-enrolled, exact-resource reads for one pinned work order.

    The work document does not grant I/O authority: the host must separately supply
    fixed collector objects, its accepted work root and a current-snapshot callback.
    """
    def __init__(self,work_order,*,expected_work_root,sources,current_snapshot_root):
        from .collectors import FileCollector,JsonFileCollector,SQLiteCollector,HttpCollector
        from .work import _resources
        hashhex(expected_work_root)
        require(work_order.get('root')==expected_work_root,'MMC_T4_WORK_PIN')
        w=unwrap('work',work_order);require(w.get('schema')=='mmc.work-order.t4','MMC_T4_WORK_SCHEMA')
        resources=_resources(w['allowed_reads'])
        require(type(sources) is dict and set(sources)=={r['id'] for r in resources},'MMC_T4_READ_ENROLLMENT')
        for source in sources.values():
            require(type(source) in (FileCollector,JsonFileCollector,SQLiteCollector,HttpCollector),'MMC_T4_COLLECTOR_TYPE')
        require(callable(current_snapshot_root),'MMC_T4_SNAPSHOT_CALLBACK')
        self.work=clone(w);self.sources=dict(sources);self.pins={r['id']:r['root'] for r in resources}
        self.current_snapshot_root=current_snapshot_root;self.reads=0
    def read(self,resource_id,*,time):
        from mosaic_mmc_t3.common import clock
        lo,hi=clock(time);token(resource_id)
        require(resource_id in self.sources,'MMC_T4_READ_SCOPE')
        require(self.work['issued_at']<=lo and hi<self.work['expires_at'],'MMC_T4_WORK_EXPIRED')
        require(self.current_snapshot_root()==self.work['snapshot_root'],'MMC_T4_READ_SNAPSHOT_CHANGED')
        require(self.reads<16,'MMC_T4_READ_BUDGET');self.reads+=1
        result=self.sources[resource_id].collect(observed_at=time['now'])
        body=unwrap('capture',result)
        require(hashlib.sha256(canonical(body['value'])).hexdigest()==self.pins[resource_id],'MMC_T4_READ_CONTENT_CHANGED')
        require(self.current_snapshot_root()==self.work['snapshot_root'],'MMC_T4_READ_SNAPSHOT_CHANGED')
        return result
