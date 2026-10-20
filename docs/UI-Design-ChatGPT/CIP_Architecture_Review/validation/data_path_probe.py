#!/usr/bin/env python3
"""Synthetic local data-path experiment. NOT a UI/framework or Azure benchmark.
Run: python data_path_probe.py --out results.json --rows 1000000 --repeats 5
Requires pandas. Uses an isolated temporary SQLite DB; no customer data/network.
"""
from __future__ import annotations
import argparse, gc, json, os, pickle, platform, random, resource, sqlite3
import statistics, subprocess, sys, tempfile, time
from pathlib import Path

def worker(db_path: str, mode: str, repeats: int) -> dict:
    import pandas as pd
    baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    sql_all = 'select * from stores'
    sql_summary = ('select state, count(*) stores, sum(revenue) revenue, '
                   'sum(closed = 0) open from stores where sector = ? group by state')
    con = sqlite3.connect(db_path)
    elapsed = []
    for _ in range(repeats):
        gc.collect()
        start = time.perf_counter()
        if mode == 'full_dataframe':
            frame = pd.read_sql_query(sql_all, con)
            view = frame.loc[frame.sector == 'Apparel'].copy()
            view['open'] = (view.closed == 0).astype(int)
            result = view.groupby('state').agg(stores=('store_id','count'),
                                             revenue=('revenue','sum'), open=('open','sum')).reset_index()
        else:
            frame = pd.read_sql_query(sql_summary, con, params=('Apparel',))
            result = frame
        elapsed.append((time.perf_counter() - start) * 1000)
    serialized = pickle.dumps(frame, protocol=pickle.HIGHEST_PROTOCOL)
    copy_ms = []
    for _ in range(repeats):
        start=time.perf_counter(); clone=pickle.loads(serialized)
        copy_ms.append((time.perf_counter()-start)*1000); del clone
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    output = {'mode':mode,'repeats':repeats,'wall_ms_samples':elapsed,
              'median_wall_ms':statistics.median(elapsed),
              'input_rows_returned':len(frame),'result_rows':len(result),
              'frame_deep_bytes':int(frame.memory_usage(index=True,deep=True).sum()),
              'serialized_bytes':len(serialized), 'median_pickle_copy_ms':statistics.median(copy_ms),
              'process_baseline_peak_rss_kib':baseline, 'process_peak_rss_kib':peak,
              'pandas_version':pd.__version__,
              'result':result.sort_values('state').to_dict(orient='records')}
    con.close(); return output

def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('data-path-results.json'))
    parser.add_argument('--rows',type=int,default=1_000_000)
    parser.add_argument('--repeats',type=int,default=5)
    parser.add_argument('--worker',choices=['full_dataframe','sql_summary'])
    parser.add_argument('--db')
    args=parser.parse_args()
    if args.rows < 1 or args.repeats < 1: parser.error('rows and repeats must be positive')
    if args.worker:
        print(json.dumps(worker(args.db,args.worker,args.repeats)));return
    with tempfile.TemporaryDirectory(prefix='cip-synthetic-') as tmp:
        db_path=str(Path(tmp)/'synthetic.db'); con=sqlite3.connect(db_path)
        con.execute('create table stores (store_id int, retailer text, state text, sector text, opened int, closed int, sqft real, revenue real)')
        rnd=random.Random(1);retailers=[f'Retailer {i}' for i in range(400)]
        states=[f'S{i:02d}' for i in range(50)]
        sectors=['Apparel','Beauty','Grocery','Home','Electronics','Dollar','Department','Sporting']
        con.executemany('insert into stores values (?,?,?,?,?,?,?,?)',
            ((i,rnd.choice(retailers),rnd.choice(states),rnd.choice(sectors),rnd.randint(2015,2026),rnd.choice([0,0,0,1]),rnd.uniform(2e3,1.5e5),rnd.uniform(1e5,5e7)) for i in range(args.rows)))
        con.execute('create index ix_sector on stores(sector)');con.commit();con.close()
        outputs=[]
        for mode in ['full_dataframe','sql_summary']:
            run=subprocess.run([sys.executable,__file__,'--worker',mode,'--db',db_path,'--repeats',str(args.repeats)],capture_output=True,text=True,check=True)
            outputs.append(json.loads(run.stdout))
        left,right=(x['result'] for x in outputs)
        match=all(a['state']==b['state'] and a['stores']==b['stores'] and a['open']==b['open'] and abs(a['revenue']-b['revenue'])<=max(1e-6,abs(a['revenue'])*1e-12) for a,b in zip(left,right)) and len(left)==len(right)
        report={'scope':'Synthetic SQLite data-path experiment; no UI, no Streamlit, no network, no Azure, no concurrency',
                'python':platform.python_version(),'platform':platform.platform(),'logical_cpus_reported':os.cpu_count(),
                'rows':args.rows,'seed':1,'db_bytes':Path(db_path).stat().st_size,'results_equivalent':match,
                'measurements':outputs,'limitations':['Five local repetitions are not a stable p95 estimate.',
                'OS page cache is not flushed; order is full_dataframe then sql_summary.',
                'Peak RSS is process high-water mark including pandas and temporary copies, not per-user RAM.',
                'pickle copying illustrates a mechanism, not the Streamlit cache runtime.',
                'No framework performance ranking or production capacity can be inferred.']}
        args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2))
        print(json.dumps({k:v for k,v in report.items() if k!='measurements'},indent=2))
        for item in outputs:print(json.dumps({k:v for k,v in item.items() if k!='result'},indent=2))
        if not match:raise AssertionError('Summary results differ')
if __name__=='__main__':main()
