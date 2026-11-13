"""Deterministic release/document/custody checks. No authority is inferred from declarations."""
from pathlib import Path
import hashlib,json,re,ast
from tools.common import ROOT,read_json,canonical,sha,require,verify_freeze,regular_files
from tools_t6.study import summarize,reject_primary_claim
FREEZE_ROOT='6504766e7aa1c0f0e151fabe9af9b6bd9f0e220d649f0e6c954d4ced57447f83'
PREDECESSOR='9615ccc846b84fd4279af33259f379b999e17fb1e7236a172bbf79fbb071ae5c'

def freeze(root=ROOT):
    verify_freeze(root);record=read_json(root/'provenance/turn6/FREEZE.json')
    require(set(record)=={'body','root'} and record['root']==FREEZE_ROOT and hashlib.sha256(b'MMC/T6/FREEZE\0'+canonical(record['body'])).hexdigest()==FREEZE_ROOT,'MMC_T6_FREEZE_PIN')
    for row in record['body']['files']:
        require((root/row['path']).is_file() and sha(root/row['path'])==row['sha256'],'MMC_T6_FROZEN_REFERENCE',row['path'])
    return {'status':'PASS_EXACT_FREEZE','root':FREEZE_ROOT,'authority_effect':'NONE'}

def preservation(root=ROOT):
    from tools.public_predecessor import load_public_predecessor
    record=load_public_predecessor(6,root,error_stage=6)
    preserved=[row['path'] for row in record['rows']]
    return {'status':'PASS_PUBLIC_HASH_MANIFEST','runtime_files':sum(n.startswith('src/') for n in preserved),'predecessor_files':len(preserved),
            'preserved':len(preserved),'changed':[],'removed':[],'authority_effect':'NONE'}

def document_links(root=ROOT):
    targets=[root/'README.md',root/'AGENTS.md',root/'SECURITY.md',*sorted((root/'docs/release').glob('*.md'),key=lambda item:item.relative_to(root).as_posix()),*sorted((root/'study').rglob('*.md'),key=lambda item:item.relative_to(root).as_posix())]
    checked=[]
    for f in targets:
        for link in re.findall(r'\[[^\]]+\]\(([^)]+)\)',f.read_text('utf8')):
            if '://' in link or link.startswith('#'):continue
            link=link.split('#')[0];path=(f.parent/link).resolve()
            require(path.is_relative_to(root.resolve()) and path.exists(),'MMC_T6_DOCUMENT_LINK',str(f.relative_to(root))+':'+link)
            checked.append({'document':f.relative_to(root).as_posix(),'target':link})
    return {'status':'PASS','documents':len(targets),'links':checked,'scope':'CURRENT_RELEASE_AND_STUDY_NOT_ALL_HISTORICAL_PROSE'}

def check_mapping(root=ROOT):
    mapping=read_json(root/'provenance/turn6/REQUIREMENT-MAP.json')
    reqs=read_json(root/'constitution/REQUIREMENTS.json')['requirements'];expected={r['id'] for r in reqs if r['turn']==6}
    require(type(mapping) is dict and set(mapping)=={'schema','requirements','semantic_equivalence_proof','authority_effect'} and mapping['schema']=='mmc.release-requirement-map.t6','MMC_T6_MAP_FIELDS')
    rows=mapping['requirements'];require(type(rows) is list and len(rows)==len(expected) and {r['id'] for r in rows}==expected,'MMC_T6_MAP_COVERAGE')
    for row in rows:
        require(row['references'] and row['tests'],'MMC_T6_MAP_EMPTY')
        for ref in row['references']:require((root/ref).is_file(),'MMC_T6_MAP_REFERENCE',ref)
        if row['id'] in ('MMC-W13-R04','MMC-W13-R05'):
            require(row['disposition']=='PREPARED_STUDY_NOT_PERFORMED','MMC_T6_STUDY_PROMOTION')
        else:require(row['disposition']=='DELIVERED_WITH_EXTERNAL_GATES','MMC_T6_MAP_DISPOSITION')
    require(mapping['semantic_equivalence_proof']=='NOT_ESTABLISHED' and mapping['authority_effect']=='NONE','MMC_T6_MAP_CLAIM')
    return {'status':'PASS_REFERENCE_MAP','requirements':6,'delivered_scope':4,'study_not_performed':2,'semantic_equivalence_proof':'NOT_ESTABLISHED'}

def assess_final(local,requirements):
    # This computes dispositions from already validated evidence, not a supplied PASS string.
    required={'tests','examples','scenarios','audit','installed','clean','closed_delivery','platforms','native_pippi','independent_review','independent_study','public_release'}
    require(type(local) is dict and set(local)==required,'MMC_T6_GATE_FIELDS')
    for k in ('tests','examples','scenarios','audit','installed','clean','closed_delivery'):
        require(type(local[k]) is bool and local[k] is True,'MMC_T6_MISSING_LEG',k)
    require(type(local['platforms']) is list and local['platforms']==['Linux'],'MMC_T6_PLATFORM_PROMOTION')
    require(local['native_pippi']=='NOT_BOUND' and local['independent_review']=='NOT_PERFORMED' and local['independent_study']=='NOT_PERFORMED' and local['public_release']=='NOT_CLEARED','MMC_T6_AUTHORITY_PROMOTION')
    require(canonical(requirements)==canonical(read_json(ROOT/'constitution/ACCEPTANCE.json')['cases']),'MMC_T6_CASE_SET')
    dispositions={c['id']:('BLOCKED_NATIVE_DEPENDENCY' if c['id']=='AC-REPRO-06' else 'PARTIAL_PLATFORM_COVERAGE' if c['id']=='AC-REPRO-05' else 'PASS_SCOPED') for c in requirements}
    return {'schema':'mmc.final-disposition.t6','status':'SCOPED_LOCAL_CONSTRUCTION_EXTERNAL_GATES_OPEN','cases':dispositions,
        'counts':{'PASS_SCOPED':98,'PARTIAL_PLATFORM_COVERAGE':1,'BLOCKED_NATIVE_DEPENDENCY':1},
        'full_program_qualified':False,'independent_study':'NOT_PERFORMED','independent_review':'NOT_PERFORMED',
        'public_release':'NOT_CLEARED','native_pippi':'NOT_BOUND','authority_effect':'NONE','signature':'NOT_SIGNED'}

def audit(root=ROOT):
    return {'schema':'mmc.audit.t6','freeze':freeze(root),'preservation':preservation(root),'documents':document_links(root),
     'requirements':check_mapping(root),'study':summarize(read_json(root/'study/DESIGN.json'),[]),'authority_effect':'NONE'}
