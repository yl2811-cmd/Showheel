"""Shared immutable inputs for the v15 terrain and climate study."""
from pathlib import Path
import sys,json,hashlib,importlib,os
ROOT=Path(__file__).resolve().parents[1]
TASK=ROOT.parents[1]/'review/climate-terrain-20260914'
WORK=Path(os.environ.get('ARCHEON_STUDY_WORK',str(TASK))).resolve()
if not WORK.is_relative_to(TASK):raise ValueError('Study work must remain inside the task directory')
sys.path.insert(0,str(ROOT/'src'))
T=importlib.import_module('tectonics-model');np=T.np
CFG=json.loads((ROOT/'data/climate-terrain.json').read_text(encoding='utf8'))
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 q=p.with_name(p.name+'.partial');q.write_text(json.dumps(v,ensure_ascii=False,indent=2,default=T.json_scalar),encoding='utf8');q.replace(p)
def fingerprint(v):return hashlib.sha256(json.dumps(v,sort_keys=True,default=T.json_scalar).encode()).hexdigest()
def request_fingerprint(request):
 payload={k:v for k,v in request.items() if k!='fingerprint'};actual=fingerprint(payload)
 if request.get('fingerprint',actual)!=actual:raise ValueError('Request contents do not match embedded fingerprint')
 return actual
def save_array(p,a):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.with_suffix('.partial').open('wb') as f:np.save(f,a,allow_pickle=False)
 p.with_suffix('.partial').replace(p)
def sources():
 return {p.name:sha(p) for p in (ROOT/'src').glob('climate-*.py')}
