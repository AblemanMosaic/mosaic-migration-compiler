"""Create-only local JSON export with a separate one-use host approval.

Not an organizational authorization ceremony or protection against hostile host code.
"""
from __future__ import annotations
import os
import re
import stat
import time
import secrets
from pathlib import Path
from .common import *

class _Approval: pass

class LocalExport:
    def __init__(self,directory,*,state_token=lambda:None,clock=time.monotonic):
        self.directory=Path(directory).absolute();self.state_token=state_token;self.clock=clock
        self._pending=None;self._approval=None;self._directory_identity=self._check_directory()
    def _check_directory(self):
        p=self.directory
        require(p.is_dir(),"MMC_T4_EXPORT_DIRECTORY")
        for a in (p,*p.parents):
            require(not a.is_symlink() and not(hasattr(a,"is_junction") and a.is_junction()),"MMC_T4_EXPORT_LINK")
        s=p.stat();return s.st_dev,s.st_ino
    def cancel(self):self._pending=None;self._approval=None
    def prepare(self,value,name,*,ttl=30):
        self.cancel();integer(ttl,1,300)
        require(type(name) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}\.json',name) is not None and '..' not in name,"MMC_T4_EXPORT_NAME")
        require(name.split('.')[0].upper() not in {'CON','PRN','AUX','NUL',*['COM'+str(i) for i in range(1,10)],*['LPT'+str(i) for i in range(1,10)]},"MMC_T4_EXPORT_NAME")
        require(type(value) is dict,"MMC_T4_EXPORT_SHAPE")
        schema=value.get('schema') if 'schema' in value else value.get('body',{}).get('schema')
        require(schema in {'mmc.workspace.t4','mmc.work-order.t4','mmc.view.t4','mmc.submission-review.t4','mmc.integration-handoff.t4','mmc.capture.t4'},"MMC_T4_EXPORT_KIND")
        raw=canonical(value,limit=MAX_INPUT)
        require(self._check_directory()==self._directory_identity,"MMC_T4_EXPORT_REPLACED")
        require(not os.path.lexists(self.directory/name),"MMC_T4_EXPORT_EXISTS")
        # Nondeterminism belongs to this explicit host action, never the pure evaluation core.
        body={'schema':'mmc.export-plan.t4','name':name,'directory':str(self.directory),
              'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'ttl_seconds':ttl,
              'state_root':digest('context',self.state_token()),'nonce':secrets.token_hex(16),
              'privacy':'PLAINTEXT_MAY_CONTAIN_PRIVATE_DATA','host_effect':'CREATE_LOCAL_FILE','authority_effect':'NONE'}
        plan=envelope('export',body)
        self._pending=(raw,plan,self.clock()+ttl)
        return clone(plan)
    def _check(self):
        require(self._pending is not None,"MMC_T4_EXPORT_NO_PLAN")
        raw,plan,deadline=self._pending;b=plan['body']
        require(self.clock()<deadline,"MMC_T4_EXPORT_EXPIRED")
        require(self._check_directory()==self._directory_identity,"MMC_T4_EXPORT_REPLACED")
        require(digest('context',self.state_token())==b['state_root'],"MMC_T4_EXPORT_STATE_CHANGED")
        require(not os.path.lexists(self.directory/b['name']),"MMC_T4_EXPORT_EXISTS")
        return raw,plan,deadline
    def approve(self,expected_plan_root):
        raw,p,d=self._check();require(p['root']==expected_plan_root,"MMC_T4_EXPORT_PLAN_PIN")
        self._approval=_Approval();return self._approval
    def commit(self,approval):
        require(self._approval is not None and approval is self._approval,"MMC_T4_EXPORT_APPROVAL")
        try:raw,p,deadline=self._check()
        except BaseException:self.cancel();raise
        # Consume before any filesystem mutation, even if it later fails.
        self.cancel();b=p['body'];final=self.directory/b['name']
        temporary=self.directory/('.mmc-t4-'+secrets.token_hex(16)+'.tmp');installed=False;warnings=[]
        try:
            fd=os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,'O_BINARY',0),0o600)
            with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            require(self.clock()<deadline,"MMC_T4_EXPORT_EXPIRED")
            require(self._check_directory()==self._directory_identity,"MMC_T4_EXPORT_REPLACED")
            require(digest('context',self.state_token())==b['state_root'],"MMC_T4_EXPORT_STATE_CHANGED")
            try:os.link(temporary,final)
            except FileExistsError as e:raise MMCError('MMC_T4_EXPORT_EXISTS') from e
            except OSError as e:raise MMCError('MMC_T4_EXPORT_INSTALL_UNSUPPORTED',detail=type(e).__name__) from e
            installed=True
            try:
                from mosaic_mmc.cli import read_local
                require(read_local(str(final),limit=MAX_INPUT)==raw,'MMC_T4_EXPORT_READBACK')
            except Exception as e:warnings.append('READBACK_INDETERMINATE:'+type(e).__name__)
            if os.name=='posix':
                try:
                    fd=os.open(self.directory,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
                    try:os.fsync(fd)
                    finally:os.close(fd)
                except OSError:warnings.append('DIRECTORY_DURABILITY_NOT_ESTABLISHED')
        except MMCError:raise
        except OSError as exc:
            if installed:warnings.append('POST_INSTALL_IO:'+type(exc).__name__)
            else:raise MMCError('MMC_T4_EXPORT_IO',detail=type(exc).__name__) from exc
        finally:
            try:temporary.unlink(missing_ok=True)
            except OSError:
                if installed:warnings.append('STAGING_CLEANUP_FAILED')
        return {'schema':'mmc.export-result.t4','status':'LOCAL_FILE_CREATED' if not warnings else 'LOCAL_FILE_CREATED_WITH_UNCERTAINTY',
                'plan_root':p['root'],'name':b['name'],'sha256':b['sha256'],'warnings':warnings,
                'host_effect':'CREATE_LOCAL_FILE','signature':'NOT_SIGNED','authority_effect':'NONE'}
