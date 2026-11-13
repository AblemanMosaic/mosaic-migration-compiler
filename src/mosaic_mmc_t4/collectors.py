"""Explicit host-owned collectors; never reachable through a document's data ABI.

Captured bytes/rows are observations, not authenticated truth or complete discovery.
All path/URL selection is a host call. No implicit signing, credential lookup or upload.
"""
from __future__ import annotations
import ipaddress
import os
from pathlib import Path
import sqlite3
import time
import urllib.parse
import urllib.request
from .common import *
from mosaic_mmc.cli import read_local

MAX_BYTES=1048576


def safe_path(root, relative):
    root=Path(root).absolute()
    require(type(relative) is str and relative and "\\" not in relative and ":" not in relative,
            "MMC_T4_PATH")
    parts=relative.split("/")
    require(not relative.startswith("/") and all(p not in ("",".","..") for p in parts),"MMC_T4_PATH")
    path=root.joinpath(*parts)
    for p in (path,*path.parents):
        require(not p.is_symlink() and not (hasattr(p,"is_junction") and p.is_junction()),"MMC_T4_PATH_LINK")
    require(root.is_dir() and path.is_relative_to(root),"MMC_T4_PATH_SCOPE")
    return path


def capture(kind,source_id,raw_value,*,raw_hashes,observed_at):
    token(source_id);integer(observed_at)
    return envelope("capture",{"schema":"mmc.capture.t4","kind":kind,"source_id":source_id,
        "observed_at":observed_at,"value":clone(raw_value),"raw_hashes":clone(raw_hashes),
        "evidence_label":"CAPTURED_UNAUTHENTICATED","coverage":"EXPLICIT_SELECTED_RESOURCES_ONLY",
        "effects":"HOST_SELECTED_READ","signature":"NOT_SIGNED","authority_effect":"NONE"})


class FileCollector:
    def __init__(self,root,source_id,names):
        token(source_id)
        require(type(names) is list and 0<len(names)<=128 and all(type(n) is str for n in names),"MMC_T4_FILE_SCOPE")
        require(len(names)==len(set(names)),"MMC_T4_FILE_SCOPE")
        self.root=Path(root).absolute();self.names=sorted(names);self.source_id=source_id
        for name in self.names:safe_path(self.root,name)
    def collect(self,*,observed_at):
        rows=[];total=0
        for name in self.names:
            p=safe_path(self.root,name);raw=read_local(str(p),limit=MAX_BYTES)
            total+=len(raw);require(total<=MAX_BYTES,"MMC_T4_COLLECTOR_LIMIT")
            rows.append({"path":name,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()})
        return capture("filesystem-inventory",self.source_id,{"files":rows},raw_hashes=rows,observed_at=observed_at)


class JsonFileCollector:
    def __init__(self,root,name,source_id):
        self.path=safe_path(root,name);self.source_id=token(source_id)
    def collect(self,*,observed_at):
        raw=read_local(str(self.path),limit=MAX_BYTES);value=decode(raw,limit=MAX_BYTES)
        return capture("json-file",self.source_id,value,raw_hashes=[{"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)}],observed_at=observed_at)


class SQLiteCollector:
    """Fixed read-only table contract; no caller-supplied SQL or database extensions."""
    def __init__(self,path,source_id):
        p=Path(path).absolute()
        safe_path(p.parent,p.name)
        require(p.is_file() and p.stat().st_size<=32*1024*1024,"MMC_T4_DATABASE_SIZE")
        self.path=p;self.source_id=token(source_id)
    def collect(self,*,observed_at):
        safe_path(self.path.parent,self.path.name)
        # This adapter qualifies quiescent local DELETE-journal fixtures, not arbitrary WAL hosts.
        require(not any(Path(str(self.path)+s).exists() for s in ("-wal","-shm","-journal")),"MMC_T4_DATABASE_NOT_QUIESCENT")
        before=self.path.stat();con=None
        try:
            con=sqlite3.connect(self.path.as_uri()+"?mode=ro",uri=True,timeout=1,isolation_level=None)
            con.execute("PRAGMA query_only=ON");con.execute("PRAGMA trusted_schema=OFF")
            budget=[0]
            def progress():
                budget[0]+=1;return 1 if budget[0]>1000 else 0
            con.set_progress_handler(progress,100)
            con.execute("BEGIN")
            table=con.execute("SELECT type,sql FROM sqlite_master WHERE name=?",("mmc_observations",)).fetchone()
            require(table is not None and table[0]=="table" and "VIRTUAL" not in table[1].upper(),"MMC_T4_DATABASE_SCHEMA")
            require([x[1] for x in con.execute('PRAGMA table_info("mmc_observations")')]==["id","value"],"MMC_T4_DATABASE_SCHEMA")
            found=con.execute('SELECT id,value FROM "mmc_observations" ORDER BY id LIMIT 513').fetchall()
            require(len(found)<=512,"MMC_T4_ROW_LIMIT")
            rows=[];seen=set();total=0
            for key,raw in found:
                token(key);require(key not in seen,"MMC_T4_ROW_DUPLICATE");seen.add(key)
                require(type(raw) is str,"MMC_T4_ROW_TYPE")
                b=raw.encode("utf-8");total+=len(b);require(total<=MAX_BYTES,"MMC_T4_COLLECTOR_LIMIT")
                rows.append({"id":key,"value":decode(b,limit=MAX_BYTES),"sha256":hashlib.sha256(b).hexdigest()})
            con.rollback()
        except MMCError:raise
        except (sqlite3.Error,OSError,UnicodeError) as exc:raise MMCError("MMC_T4_SQLITE_READ",detail=type(exc).__name__) from exc
        finally:
            if con:con.close()
        after=self.path.stat()
        require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),"MMC_T4_SOURCE_CHANGED")
        return capture("sqlite-rows",self.source_id,{"rows":rows},raw_hashes=[{"id":r["id"],"sha256":r["sha256"]} for r in rows],observed_at=observed_at)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise MMCError("MMC_T4_HTTP_REDIRECT")


class HttpCollector:
    """Exact host-selected public URL. No proxies, auth headers, cookies or redirects.

    Socket timeout and between-read deadline are not a hostile-OS hard wall-clock sandbox.
    """
    def __init__(self,url,source_id,*,allow_loopback_http=False,timeout_seconds=3):
        require(type(url) is str and len(url)<=2048,"MMC_T4_URL")
        u=urllib.parse.urlsplit(url)
        require(u.scheme in ("http","https") and u.hostname and not u.username and not u.password and not u.fragment,
                "MMC_T4_URL")
        require(not any(c in url for c in ("\r","\n","\t"," ")),"MMC_T4_URL")
        if u.scheme=="http":
            try:local=ipaddress.ip_address(u.hostname).is_loopback
            except ValueError:local=False
            require(allow_loopback_http is True and local,"MMC_T4_HTTP_LOOPBACK_ONLY")
        require(type(allow_loopback_http) is bool,"MMC_T4_TYPE")
        integer(timeout_seconds,1,10)
        self.url=url;self.source_id=token(source_id);self.timeout=timeout_seconds
    def collect(self,*,observed_at):
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),_NoRedirect())
        started=time.monotonic();parts=[];size=0
        try:
            req=urllib.request.Request(self.url,method="GET",headers={"Accept":"application/json","Accept-Encoding":"identity"})
            with opener.open(req,timeout=self.timeout) as response:
                require(response.status==200 and response.geturl()==self.url,"MMC_T4_HTTP_STATUS")
                require(response.headers.get_content_type()=="application/json","MMC_T4_HTTP_TYPE")
                require(response.headers.get("Content-Encoding","identity")=="identity","MMC_T4_HTTP_ENCODING")
                length=response.headers.get("Content-Length")
                if length is not None:require(length.isdecimal() and int(length)<=MAX_BYTES,"MMC_T4_COLLECTOR_LIMIT")
                while True:
                    require(time.monotonic()-started<=self.timeout,"MMC_T4_HTTP_DEADLINE")
                    chunk=response.read(min(65536,MAX_BYTES+1-size))
                    if not chunk:break
                    parts.append(chunk);size+=len(chunk);require(size<=MAX_BYTES,"MMC_T4_COLLECTOR_LIMIT")
        except MMCError:raise
        except Exception as exc:
            # External I/O/parsers have varied documented exception types. No untyped adapter error escapes.
            raise MMCError("MMC_T4_HTTP_READ",detail=type(exc).__name__) from exc
        raw=b"".join(parts);value=decode(raw,limit=MAX_BYTES)
        return capture("http-json",self.source_id,value,raw_hashes=[{"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}],observed_at=observed_at)


@typed
def assess_record(kind,value,expected):
    """Pure interpretation of supplied repository/release/deployment snapshots."""
    require(kind in ("repository","release","deployment"),"MMC_T4_RECORD_KIND")
    canonical(value,limit=MAX_BYTES);canonical(expected,limit=MAX_BYTES)
    if kind=="repository":
        closed(value,{"schema","revision","files"});closed(expected,{"revision"})
        require(value["schema"]=="mmc.repository-record.t4","MMC_T4_RECORD_SCHEMA");token(value["revision"]);token(expected["revision"])
        require(type(value["files"]) is list and len(value["files"])<=512,"MMC_T4_ROW_LIMIT")
        seen=set()
        for r in value["files"]:
            closed(r,{"path","bytes","sha256"});text(r["path"],1024);hashhex(r["sha256"]);integer(r["bytes"])
            require(r["path"] not in seen,"MMC_T4_ROW_DUPLICATE");seen.add(r["path"])
        ok=value["revision"]==expected["revision"];details={"files":len(seen)}
    elif kind=="release":
        closed(value,{"schema","artifact_root","source_root","toolchain_root"})
        closed(expected,{"artifact_root","source_root","toolchain_root"})
        require(value["schema"]=="mmc.release-record.t4","MMC_T4_RECORD_SCHEMA")
        for k,v in expected.items():hashhex(v);hashhex(value[k])
        ok=all(value[k]==v for k,v in expected.items());details={"fields":sorted(expected)}
    else:
        closed(value,{"schema","cohort","instances"});closed(expected,{"cohort","version","instance_ids"})
        require(value["schema"]=="mmc.deployment-record.t4","MMC_T4_RECORD_SCHEMA");token(value["cohort"]);token(expected["cohort"]);token(expected["version"])
        require(type(expected["instance_ids"]) is list and len(expected["instance_ids"])<=512,"MMC_T4_ROW_LIMIT")
        for key in expected["instance_ids"]:token(key)
        require(len(expected["instance_ids"])==len(set(expected["instance_ids"])),"MMC_T4_ROW_DUPLICATE")
        require(type(value["instances"]) is list and len(value["instances"])<=512,"MMC_T4_ROW_LIMIT")
        seen=set();bad=[]
        for r in value["instances"]:
            closed(r,{"id","version","ready"});token(r["id"]);token(r["version"]);require(type(r["ready"]) is bool,"MMC_T4_TYPE")
            require(r["id"] not in seen,"MMC_T4_ROW_DUPLICATE");seen.add(r["id"])
            if r["version"]!=expected["version"] or not r["ready"]:bad.append(r["id"])
        ok=not bad and seen==set(expected["instance_ids"]) and value["cohort"]==expected["cohort"]
        details={"incompatible":sorted(bad),"missing":sorted(set(expected["instance_ids"])-seen),"extra":sorted(seen-set(expected["instance_ids"]))}
    return {"schema":"mmc.record-assessment.t4","kind":kind,"status":"MATCH_FOR_SUPPLIED_RECORDS" if ok else "CONTRADICTED",
        "details":details,"evidence_label":"COMPUTED_OVER_UNAUTHENTICATED_INPUT","live_discovery":"NOT_PERFORMED","effects":"NOT_EXECUTED",**BOUNDARY}


def descriptors():
    return [
      {"id":"filesystem","mode":"EXPLICIT_HOST_READ","scope":"Listed local regular files only"},
      {"id":"sqlite","mode":"EXPLICIT_HOST_READ","scope":"Quiescent fixed mmc_observations table"},
      {"id":"http","mode":"EXPLICIT_HOST_GET","scope":"Exact URL, no credentials/proxy/redirect; loopback-only HTTP"},
      *[{"id":x,"mode":"PURE_SUPPLIED_SNAPSHOT","scope":"No live service discovery"} for x in ("repository","release","deployment","jobs")]]
