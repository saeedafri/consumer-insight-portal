#!/usr/bin/env python3
"""Run bounded, offline probes on selected source; do not import the application.
Usage: python source_probes.py /path/to/extracted/repository --out source-probes.json
This is NOT a substitute for the repository test suite or a penetration test.
"""
from __future__ import annotations
import argparse, ast, hashlib, json
from datetime import datetime, timedelta, timezone
from pathlib import Path

def main() -> None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source',type=Path);ap.add_argument('--out',type=Path,default=Path('source-probes.json'))
    args=ap.parse_args();path=args.source/'app/core/auth.py'
    source=path.read_text();tree=ast.parse(source)
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'_session_is_live','_as_datetime'}]
    if len(selected)!=2:raise RuntimeError('Expected source functions not found; review source revision')
    ns={'datetime':datetime,'timezone':timezone,'Optional':__import__('typing').Optional,'text':lambda value:value}
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(path),'exec'),ns)
    class Connection:
        def __init__(self,row=None,error=False):self.row=row;self.error=error
        def __enter__(self):
            if self.error:raise RuntimeError('Simulated store unavailable')
            return self
        def __exit__(self,*_):return False
        def execute(self,*_,**__):return self
        def first(self):return self.row
    class Engine:
        def __init__(self,**kw):self.kw=kw
        def connect(self):return Connection(**self.kw)
    cases=[]
    for name,kw,expected in [
        ('store_exception',{'error':True},True),
        ('missing_session_row',{'row':None},True),
        ('revoked_session',{'row':(datetime.now(timezone.utc),datetime.now(timezone.utc)+timedelta(hours=1))},False),
        ('expired_session',{'row':(None,datetime.now(timezone.utc)-timedelta(hours=1))},False),
        ('live_session',{'row':(None,datetime.now(timezone.utc)+timedelta(hours=1))},True)]:
        ns['get_engine']=lambda role, settings=kw:Engine(**settings)
        actual=ns['_session_is_live']('synthetic-session-id')
        assert actual is expected,(name,actual)
        cases.append({'case':name,'actual_function_result':actual,'source_behavior_reproduced':actual is expected})
    members_a=[1,4];members_b=[2,3]
    report={'scope':'Selected AST-extracted functions with fake database; no full app or network',
            'auth_source_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'session_probes':cases,
            'interpretation':'Existing in-memory sessions can remain valid when lookup fails or row is absent; this does not demonstrate unauthenticated login bypass.',
            'cohort_signature_counterexample':{'before':members_a,'after':members_b,
                'same_count_and_sum':(len(members_a),sum(members_a))==(len(members_b),sum(members_b)),
                'sets_differ':set(members_a)!=set(members_b),
                'source':'app/data/cube.py:153-166',
                'limitation':'Mathematical counterexample to the signature, not an observed stale production cohort.'}}
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
