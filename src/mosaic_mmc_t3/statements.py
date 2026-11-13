"""Explicit P-256/SHA256 evidence profile. Private keys never enter public records."""
from .common import *

ALG='ECDSA-P256-SHA256-DER-LOW-S'
ORDER=0xffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551

def backend():
    try:
        from cryptography.hazmat.primitives.asymmetric import ec,utils
        from cryptography.hazmat.primitives import hashes,serialization
        from cryptography.exceptions import InvalidSignature,UnsupportedAlgorithm
        return ec,utils,hashes,serialization,InvalidSignature,UnsupportedAlgorithm
    except ImportError as exc:raise MMCError('MMC_T3_SIGNING_DEPENDENCY') from exc

def public_hex(key):
    ec,_,_,ser,_,_=backend()
    require(isinstance(key,ec.EllipticCurvePrivateKey) and key.curve.name=='secp256r1','MMC_T3_KEY_TYPE')
    return key.public_key().public_bytes(ser.Encoding.X962,ser.PublicFormat.CompressedPoint).hex()

def public_key(value):
    require(type(value) is str and re.fullmatch(r'0[23][0-9a-f]{64}',value) is not None,'MMC_T3_PUBLIC_KEY')
    ec,*_=backend()
    try:return ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(),bytes.fromhex(value))
    except ValueError as exc:raise MMCError('MMC_T3_PUBLIC_KEY') from exc

def body_shape(b):
    closed(b,{'schema','kind','signer','migration','plan_root','policy_root','transition','cohort','targets','issued_at','expires_at','sequence','payload'})
    require(b['schema']=='mmc.statement.t3' and b['kind'] in ('observation','approval'),'MMC_T3_STATEMENT_KIND')
    public_key(b['signer'])
    for k in ('migration','transition','cohort'):token(b[k])
    for k in ('plan_root','policy_root'):hashhex(b[k])
    strings(b['targets'],64)
    for k in ('issued_at','expires_at','sequence'):integer(b[k])
    require(b['issued_at']<b['expires_at'],'MMC_T3_INTERVAL')
    p=b['payload']
    if b['kind']=='observation':
        closed(p,{'claim','subject','value','coverage','members','method','evidence_class'})
        for k in ('claim','subject','method'):token(p[k])
        require(p['evidence_class'] in ('OBSERVATION','ENFORCEMENT','COVERAGE','TEST_RESULT'),'MMC_T3_EVIDENCE_CLASS')
        require(p['coverage'] in ('COMPLETE','PARTIAL','UNKNOWN'),'MMC_T3_COVERAGE');strings(p['members'],512)
    else:
        closed(p,{'request_root','context_root','jurisdiction','decision'})
        hashhex(p['request_root']);hashhex(p['context_root']);token(p['jurisdiction'])
        require(p['decision'] in ('ALLOW','DENY'),'MMC_T3_DECISION')
    canonical(b,limit=2*1024*1024)
    return b

def seal(body,key):
    b=clone(body);require(b.get('signer')==public_hex(key),'MMC_T3_SIGNER_MISMATCH');body_shape(b)
    ec,utils,hashes,_,_,unsupported=backend()
    message=b'MMC/T3/SIGNED-STATEMENT\0'+canonical(b)
    try:sig=key.sign(message,ec.ECDSA(hashes.SHA256(),deterministic_signing=True))
    except unsupported as exc:raise MMCError('MMC_T3_DETERMINISTIC_SIGNING_UNSUPPORTED') from exc
    r,s=utils.decode_dss_signature(sig);sig=utils.encode_dss_signature(r,min(s,ORDER-s))
    rec={'body':b,'algorithm':ALG,'signature':sig.hex()};return {**rec,'root':digest('statement',rec)}

def verify(record):
    closed(record,{'body','algorithm','signature','root'})
    require(record['algorithm']==ALG,'MMC_T3_ALGORITHM');b=body_shape(record['body'])
    require(type(record['signature']) is str and re.fullmatch('[0-9a-f]{16,144}',record['signature']) is not None and len(record['signature'])%2==0,'MMC_T3_SIGNATURE')
    require(record['root']==digest('statement',{k:record[k] for k in ('body','algorithm','signature')}),'MMC_T3_STATEMENT_ROOT')
    ec,utils,hashes,_,invalid,_=backend()
    try:
        raw=bytes.fromhex(record['signature']);r,s=utils.decode_dss_signature(raw)
        require(1<=r<ORDER and 1<=s<=ORDER//2 and utils.encode_dss_signature(r,s)==raw,'MMC_T3_SIGNATURE_ENCODING')
        public_key(b['signer']).verify(raw,b'MMC/T3/SIGNED-STATEMENT\0'+canonical(b),ec.ECDSA(hashes.SHA256()))
    except MMCError:raise
    except (ValueError,invalid) as exc:raise MMCError('MMC_T3_SIGNATURE') from exc
    return clone(b)

def validate_policy(value):
    p=clone(value)
    closed(p,{'schema','observers','jurisdictions','max_age','max_clock_uncertainty','minimum_sequence','revoked_keys','max_attempts'})
    require(p['schema']=='mmc.reader-policy.t3','MMC_T3_POLICY')
    integer(p['max_age'],1,86400);integer(p['max_clock_uncertainty'],0,86400);integer(p['minimum_sequence']);integer(p['max_attempts'],1,3)
    require(type(p['observers']) is list and 0<len(p['observers'])<=64,'MMC_T3_OBSERVERS')
    seen=set()
    for o in p['observers']:
        closed(o,{'key','claims','subjects','cohorts','methods','classes','authorities'});public_key(o['key'])
        require(o['key'] not in seen,'MMC_T3_DUPLICATE_KEY');seen.add(o['key'])
        for f in ('claims','subjects','cohorts','methods','classes','authorities'):strings(o[f],512);require(bool(o[f]),'MMC_T3_EMPTY_SCOPE')
    require(type(p['jurisdictions']) is list and 0<len(p['jurisdictions'])<=32,'MMC_T3_JURISDICTIONS');seen=set()
    for j in p['jurisdictions']:
        closed(j,{'id','keys','threshold'});token(j['id']);require(j['id'] not in seen,'MMC_T3_DUPLICATE_JURISDICTION');seen.add(j['id'])
        require(type(j['keys']) is list and 0<len(j['keys'])<=32,'MMC_T3_KEYS')
        for k in j['keys']:public_key(k)
        require(j['keys']==sorted(set(j['keys'])),'MMC_T3_KEYS')
        integer(j['threshold'],1,len(j['keys']))
    require(type(p['revoked_keys']) is list and len(p['revoked_keys'])<=128,'MMC_T3_REVOKED_KEYS')
    for k in p['revoked_keys']:public_key(k)
    require(p['revoked_keys']==sorted(set(p['revoked_keys'])),'MMC_T3_REVOKED_KEYS')
    p['observers']=sorted(p['observers'],key=lambda x:x['key']);p['jurisdictions']=sorted(p['jurisdictions'],key=lambda x:x['id'])
    return p
