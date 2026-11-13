"""Cooperative-local SQLite journal and explicit local adapter boundary.

The controller accepts only host-constructed :class:`EffectAdapter` instances.
Input documents can select an adapter identity, but cannot import or construct an
adapter implementation.  The shipped adapters remain local and non-production.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
import sqlite3,os
from contextlib import contextmanager
from .common import *

JOURNAL_APP=0x4d4d4303
TARGET_APP=0x4d4d4353

class CrashInjected(BaseException):
    """Test-only process-boundary surrogate. Production code does not select it from data."""

class LostAcknowledgment(Exception):pass

@contextmanager
def connection(path,app,write=False):
    safe_database(path)
    con=None
    try:
        con=sqlite3.connect(Path(path).as_uri()+'?mode=rw',uri=True,isolation_level=None,timeout=3)
        require(con.execute('PRAGMA application_id').fetchone()[0]==app,'MMC_T3_DATABASE_FORMAT')
        con.execute('PRAGMA synchronous=FULL');con.execute('PRAGMA trusted_schema=OFF')
        con.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        yield con
        con.commit()
    except sqlite3.Error as exc:
        if con:con.rollback()
        error_code=getattr(exc,'sqlite_errorcode',None)
        concurrency=(type(error_code) is int and
                     error_code & 0xff in (sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED))
        raise MMCError('MMC_T3_CONCURRENT_DISPATCH' if concurrency else 'MMC_T3_DATABASE_ERROR',
                       detail=type(exc).__name__) from exc
    except BaseException:
        if con:con.rollback()
        raise
    finally:
        if con:con.close()

def create_db(path,app,sql):
    p=safe_database(path,True)
    fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    con=sqlite3.connect(p)
    try:
        con.execute('PRAGMA journal_mode=DELETE');con.execute('PRAGMA synchronous=FULL')
        con.execute(f'PRAGMA application_id={app}');con.executescript(sql);con.commit()
    finally:con.close()
    return p

class Journal:
    def __init__(self,path,policy_root,minimum=None):
        self.path=safe_database(path);hashhex(policy_root);self.policy_root=policy_root;self.minimum=clone(minimum) if minimum is not None else None
        if minimum is not None:closed(minimum,{'sequence','root'});integer(minimum['sequence'],1);hashhex(minimum['root'])
        with self.transaction() as con:self.events(con)
    @classmethod
    def create(cls,path,policy):
        from .statements import validate_policy
        p=validate_policy(policy)
        path=create_db(path,JOURNAL_APP,'CREATE TABLE events(sequence INTEGER PRIMARY KEY, raw BLOB NOT NULL);')
        # Genesis separately committed. A crash here leaves an invalid, explicitly refused database.
        with connection(path,JOURNAL_APP,True) as con:
            cls.append(con,[], 'GENESIS',{'policy':p})
        return cls(path,digest('policy',p))
    def transaction(self,write=False):return connection(self.path,JOURNAL_APP,write)
    def events(self,con):
        rows=con.execute('SELECT sequence,raw FROM events ORDER BY sequence LIMIT 4097').fetchall();require(0<len(rows)<=4096,'MMC_T3_JOURNAL_LIMIT')
        result=[];previous='0'*64
        for n,raw in rows:
            require(type(raw) is bytes,'MMC_T3_JOURNAL_ENCODING')
            r=decode(raw,canonical_only=True,limit=8*1024*1024);closed(r,{'sequence','previous','type','payload','root'})
            integer(r['sequence'],1);token(r['type'])
            require(n==r['sequence']==len(result)+1 and r['previous']==previous,'MMC_T3_JOURNAL_CHAIN')
            require(r['root']==digest('event',{k:r[k] for k in ('sequence','previous','type','payload')}),'MMC_T3_JOURNAL_HASH')
            result.append(r);previous=r['root']
        closed(result[0]['payload'],{'policy'})
        require(result[0]['type']=='GENESIS' and digest('policy',result[0]['payload']['policy'])==self.policy_root,'MMC_T3_JOURNAL_POLICY_PIN')
        if self.minimum:
            n=self.minimum['sequence'];require(len(result)>=n and result[n-1]['root']==self.minimum['root'],'MMC_T3_JOURNAL_ROLLBACK')
        return result
    @staticmethod
    def event(events,kind,payload):
        require(len(events)<4096,'MMC_T3_JOURNAL_LIMIT');token(kind)
        b={'sequence':len(events)+1,'previous':events[-1]['root'] if events else '0'*64,'type':kind,'payload':clone(payload)}
        return {**b,'root':digest('event',b)}
    @staticmethod
    def append(con,events,kind,payload):
        r=Journal.event(events,kind,payload)
        # The stored row is admitted only when the complete candidate history
        # still satisfies the canonical aggregate budget used by replay.
        canonical([*events,r])
        con.execute('INSERT INTO events VALUES (?,?)',(r['sequence'],canonical(r)))
        events.append(r)
        return r
    def export(self):
        with self.transaction() as con:return self.events(con)

class EffectAdapter(ABC):
    """Stable host effect ABI for controller-selected, non-production adapters."""

    identity: dict
    model_adapter: str

    @abstractmethod
    def descriptor(self):
        raise NotImplementedError

    @abstractmethod
    def snapshot(self,targets):
        raise NotImplementedError

    @abstractmethod
    def lookup(self,op_id,request_root):
        raise NotImplementedError

    @abstractmethod
    def apply(self,request,*,fault=None):
        raise NotImplementedError


def admit_adapter(adapter):
    """Admit a host-selected adapter object; never resolve one from input data."""
    require(isinstance(adapter,EffectAdapter),'MMC_T3_ADAPTER_UNSUPPORTED')
    require(type(adapter.identity) is dict,'MMC_T3_ADAPTER_IDENTITY')
    closed(adapter.identity,{'schema','id'});token(adapter.identity['id'])
    token(adapter.model_adapter)
    return adapter


class SimulatedStore(EffectAdapter):
    """Exact-version compare-and-set and idempotency ledger in ONE local transaction."""
    model_adapter='simulation.fixture'
    def __init__(self,path):
        self.path=safe_database(path)
        with connection(self.path,TARGET_APP) as con:
            row=con.execute('SELECT raw FROM meta').fetchone();require(row is not None and type(row[0]) is bytes,'MMC_T3_ADAPTER_IDENTITY')
            self.identity=decode(row[0])
        closed(self.identity,{'schema','id'});token(self.identity['id'])
        require(self.identity['schema']=='mmc.simulated-target.t3','MMC_T3_ADAPTER_IDENTITY')
    @classmethod
    def create(cls,path,adapter_id,states,*,floor=0,revoked=()):
        token(adapter_id);integer(floor);strings(sorted(revoked));require(type(states) is dict and 0<len(states)<=64,'MMC_T3_TARGETS')
        for k,v in states.items():token(k);token(v)
        p=create_db(path,TARGET_APP,'CREATE TABLE meta(raw BLOB NOT NULL); CREATE TABLE targets(id TEXT PRIMARY KEY, raw BLOB NOT NULL); CREATE TABLE effects(id TEXT PRIMARY KEY, raw BLOB NOT NULL);')
        with connection(p,TARGET_APP,True) as con:
            con.execute('INSERT INTO meta VALUES (?)',(canonical({'schema':'mmc.simulated-target.t3','id':adapter_id}),))
            for k,v in sorted(states.items()):con.execute('INSERT INTO targets VALUES (?,?)',(k,canonical({'state':v,'version':0,'floor':floor,'revoked':sorted(revoked)})))
        return cls(p)
    def descriptor(self):
        return {'schema':'mmc.adapter.t3','id':self.identity['id'],'mode':'SIMULATED_LOCAL_SQLITE','atomic_preconditions':True,'idempotency':'ATOMIC_LOCAL_LEDGER','production':False,'max_targets':64,'effect':'UPDATE_SIMULATED_ROWS','power_loss_qualification':'NOT_PERFORMED'}
    def snapshot(self,targets):
        strings(targets,64)
        with connection(self.path,TARGET_APP) as con:return self._snapshot(con,targets)
    @staticmethod
    def _snapshot(con,targets):
        rows={}
        for t in targets:
            r=con.execute('SELECT raw FROM targets WHERE id=?',(t,)).fetchone();require(r is not None,'MMC_T3_TARGET_MISSING',t)
            value=decode(bytes(r[0]),canonical_only=True);closed(value,{'state','version','floor','revoked'});token(value['state']);integer(value['version']);integer(value['floor']);strings(value['revoked'],128);rows[t]=value
        return rows
    def lookup(self,op_id,request_root):
        token(op_id);hashhex(request_root)
        with connection(self.path,TARGET_APP) as con:
            row=con.execute('SELECT raw FROM effects WHERE id=?',(op_id,)).fetchone()
            if row is None:return {'status':'ABSENT_FROM_LOCAL_LEDGER','effects':'NOT_RECORDED'}
            result=decode(bytes(row[0]),canonical_only=True)
            require(result['request_root']==request_root,'MMC_T3_IDEMPOTENCY_CONFLICT')
            return result
    def apply(self,request,*,fault=None):
        # Selected only by trusted test caller, never an observation or JSON field.
        require(fault in (None,'before','lost_ack','crash_after','partial'),'MMC_T3_FAULT_MODE')
        from .courts import validate_request
        validate_request(request)
        root=digest('request',request);op=request['operation_id']
        if fault=='before':return {'status':'NOT_APPLIED','request_root':root,'effects':'NONE_CONFIRMED'}
        with connection(self.path,TARGET_APP,True) as con:
            row=con.execute('SELECT raw FROM effects WHERE id=?',(op,)).fetchone()
            if row:
                result=decode(bytes(row[0]));require(result['request_root']==root,'MMC_T3_IDEMPOTENCY_CONFLICT');return result
            require(request['adapter']==self.descriptor(),'MMC_T3_ADAPTER_SUBSTITUTION')
            targets=request['scope']['targets'];actual=self._snapshot(con,targets)
            require(canonical(actual)==canonical(request['pre_state']),'MMC_T3_PRECONDITION_CHANGED')
            require(set(request['post_state'])==set(targets),'MMC_T3_TARGET_SCOPE')
            after={}
            for t in targets:
                before=actual[t];post=request['post_state'][t];closed(post,{'state','floor','revoked'})
                token(post['state']);integer(post['floor']);strings(post['revoked'],128)
                require(post['floor']>=before['floor'] and set(before['revoked'])<=set(post['revoked']),'MMC_T3_SECURITY_FLOOR')
                after[t]={**clone(post),'version':before['version']+1}
            selected=targets[:1] if fault=='partial' else targets
            for t in selected:con.execute('UPDATE targets SET raw=? WHERE id=?',(canonical(after[t]),t))
            result={'schema':'mmc.simulated-effect.t3','operation_id':op,'request_root':root,'status':'PARTIAL' if fault=='partial' else 'APPLIED','changed':selected,'post_state':self._snapshot(con,targets),'effects':'SIMULATED_ROWS_CHANGED','authority_effect':'NONE'}
            con.execute('INSERT INTO effects VALUES (?,?)',(op,canonical(result)))
        if fault=='lost_ack':raise LostAcknowledgment('Effect committed; response intentionally lost')
        if fault=='crash_after':raise CrashInjected('Effect committed before controller acknowledgment')
        return result
    def raise_security(self,targets,floor,revoked):
        """Explicit test/host management, not an input-document operation."""
        integer(floor);strings(revoked,128)
        with connection(self.path,TARGET_APP,True) as con:
            for t,v in self._snapshot(con,targets).items():
                require(floor>=v['floor'] and set(v['revoked'])<=set(revoked),'MMC_T3_SECURITY_FLOOR')
                con.execute('UPDATE targets SET raw=? WHERE id=?',(canonical({**v,'version':v['version']+1,'floor':floor,'revoked':revoked}),t))
