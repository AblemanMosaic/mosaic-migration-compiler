"""Prospective effort accounting. Structural validity is not observed independence or benefit."""
from pathlib import Path
import argparse, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.common import read_json, canonical, require
ACTIVITIES={'setup','modeling','adaptation','coding','debugging','review','supervision','testing'}
FIELDS={'participant','arm','task','sequence','activity','event','time_seconds'}

def summarize(design, events):
    require(type(design) is dict and design.get('schema')=='mmc.study-design.t6','MMC_T6_STUDY_DESIGN')
    require(design.get('primary_study')=='NOT_PERFORMED' and design.get('authority_effect')=='NONE','MMC_T6_STUDY_CLAIM')
    require(type(events) is list and len(events)<=10000,'MMC_T6_STUDY_LIMIT')
    state={};open_spans={};totals={};arms={}
    for e in events:
        require(type(e) is dict and set(e)==FIELDS,'MMC_T6_EVENT_FIELDS')
        for k in ('participant','arm','task','activity','event'):
            require(type(e[k]) is str and 0<len(e[k])<=80,'MMC_T6_EVENT_TYPE')
        require(e['arm'] in ('conventional','mmc') and e['task'] in design['stages'] and e['activity'] in ACTIVITIES and e['event'] in ('start','stop'),'MMC_T6_EVENT_ENUM')
        require(type(e['sequence']) is int and e['sequence']>=0 and type(e['time_seconds']) is int and 0<=e['time_seconds']<2**63,'MMC_T6_EVENT_NUMBER')
        who=e['participant'];seq,clock=state.get(who,(-1,0))
        require(e['sequence']==seq+1 and e['time_seconds']>=clock,'MMC_T6_EVENT_ORDER')
        require(who not in arms or arms[who]==e['arm'],'MMC_T6_ARM_SWITCH')
        arms[who]=e['arm'];state[who]=(e['sequence'],e['time_seconds'])
        if e['event']=='start':
            require(who not in open_spans,'MMC_T6_OVERLAPPING_EFFORT');open_spans[who]=e
        else:
            require(who in open_spans,'MMC_T6_UNPAIRED_STOP');start=open_spans.pop(who)
            require(start['task']==e['task'] and start['activity']==e['activity'],'MMC_T6_SPAN_MISMATCH')
            key=(who,e['arm'],e['task'],e['activity']);totals[key]=totals.get(key,0)+e['time_seconds']-start['time_seconds']
    rows=[dict(zip(('participant','arm','task','activity'),k),reported_seconds=v) for k,v in sorted(totals.items())]
    return {'schema':'mmc.effort-accounting.t6','status':'PREPARED_NOT_PERFORMED' if not events else 'SUPPLIED_ACCOUNTING_ONLY',
            'events':len(events),'completed_spans':sum(1 for e in events if e['event']=='stop'),
            'rows':rows,'open_spans':sorted(open_spans),'incomplete_accounting':bool(open_spans),
            'authentication':'NOT_ESTABLISHED','participant_independence':'NOT_ESTABLISHED',
            'primary_study':'NOT_PERFORMED','productivity_savings':'NOT_ESTABLISHED','economic_break_even':'NOT_ESTABLISHED','authority_effect':'NONE'}

def reject_primary_claim(value):
    expected={'primary_study':'NOT_PERFORMED','productivity_savings':'NOT_ESTABLISHED','economic_break_even':'NOT_ESTABLISHED','independent_participants':'NOT_OBSERVED','authority_effect':'NONE'}
    require(canonical(value)==canonical(expected),'MMC_T6_UNSUPPORTED_RESEARCH_CLAIM')
    return {'status':'PRIMARY_STUDY_BLOCKED',**expected}

def main():
    p=argparse.ArgumentParser();p.add_argument('--design',required=True);p.add_argument('--events',required=True);a=p.parse_args()
    print(canonical(summarize(read_json(a.design),read_json(a.events))).decode())
if __name__=='__main__':
    from mosaic_mmc import MMCError
    try:main()
    except MMCError as e:print(canonical({'status':'REFUSED','error':e.record()}).decode());raise SystemExit(2)
