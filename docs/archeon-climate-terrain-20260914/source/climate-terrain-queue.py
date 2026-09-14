"""Resumeable, bounded matrix; failed candidates remain in their own folders."""
import pathlib,sys,importlib,time,traceback,gc,argparse,subprocess
sys.path.insert(0,str(pathlib.Path(__file__).parent));D=importlib.import_module('climate-terrain');C=D.C
def run(seed_only=None):
 rows=[];selected={};start=time.time()
 statusfile=C.WORK/(f'study-status-{seed_only}.json' if seed_only else 'study-status.json')
 for seed in [seed_only] if seed_only else C.CFG['seeds']:
  for mode in C.CFG['modes']:
   for scenario in ['baseline','dry','wet']:
    for region in ['keld','vorhan-duskreach']:
     for gain in C.CFG['enhancementLevels']:
      if (C.WORK/'STOP').exists():raise InterruptedError('Study paused by STOP file')
      D.coarse(region,seed,mode,scenario,gain)
      specs=[s for s in C.CFG['provinces'] if s['region']==region or (region=='vorhan-duskreach' and s['region'] in ['vorhan','duskreach'])]
      for spec in specs:
       key=f'{spec["id"]}/{seed}/{mode}/{scenario}'
       if key in selected:continue
       folder=D.regional(spec,seed,mode,scenario,gain)
       report=C.read(folder/'simulation.json');retention=C.read(folder/'retention.json')
       passed=report['passed'] and report['storyGeographyPassed'] and report['waterConvergence']['passed'] and not retention['renewalNeeded'] and retention['quietAreaRetention']>=.85
       rows.append({'key':key,'gain':gain,'path':str(folder),'passed':passed,'simulationPassed':report['passed'],'waterConverged':report['waterConvergence']['passed'],'retained':not retention['renewalNeeded']})
       if passed:selected[key]=gain
       C.write(statusfile,{'status':'running','started':start,'completed':rows,'selected':selected,'climateReady':False})
       gc.collect()
      if all(f'{s["id"]}/{seed}/{mode}/{scenario}' in selected for s in specs):break
 # Fine windows use their selected parent and the same physical crop.
 for key,gain in selected.items():
  sid,seed,mode,scenario=key.split('/');spec=next(s for s in C.CFG['provinces'] if s['id']==sid)
  if (C.WORK/'STOP').exists():raise InterruptedError('Study paused by STOP file')
  D.regional(spec,int(seed),mode,scenario,gain,detail=True)
  gc.collect()
 C.write(statusfile,{'status':'geological matrix complete','started':start,'finished':time.time(),'completed':rows,'selected':selected,'climateReady':False})
def parallel():
 jobs=[]
 for seed in C.CFG['seeds']:
  log=(C.WORK/f'terrain-{seed}.log').open('a',encoding='utf8')
  p=subprocess.Popen([sys.executable,'-X','utf8',__file__,'--seed',str(seed)],stdout=log,stderr=subprocess.STDOUT);jobs.append((seed,p,log))
 C.write(C.WORK/'workers.json',{'workers':[{'seed':s,'pid':p.pid} for s,p,f in jobs]})
 while any(p.poll() is None for s,p,f in jobs):
  records=[C.read(C.WORK/f'study-status-{s}.json') for s,p,f in jobs if (C.WORK/f'study-status-{s}.json').exists()]
  C.write(C.WORK/'study-status.json',{'status':'running','workers':[{'seed':s,'pid':p.pid,'exitCode':p.poll()} for s,p,f in jobs],'completed':[r for v in records for r in v['completed']],'selected':{k:g for v in records for k,g in v['selected'].items()},'climateReady':False})
  time.sleep(15)
 for s,p,f in jobs:f.close()
 records=[C.read(C.WORK/f'study-status-{s}.json') for s,p,f in jobs if (C.WORK/f'study-status-{s}.json').exists()]
 C.write(C.WORK/'study-status.json',{'status':'geological matrix complete' if all(p.returncode==0 for s,p,f in jobs) else 'worker failed','workers':[{'seed':s,'exitCode':p.returncode} for s,p,f in jobs],'completed':[r for v in records for r in v['completed']],'selected':{k:g for v in records for k,g in v['selected'].items()},'climateReady':False})
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--seed',type=int);a.add_argument('--parallel',action='store_true');q=a.parse_args()
 try:parallel() if q.parallel else run(q.seed)
 except Exception as e:
  C.write(C.WORK/f'queue-failure-{q.seed or "main"}.json',{'error':str(e),'traceback':traceback.format_exc(),'time':time.time()});raise
