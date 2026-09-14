"""Prepare explicitly incomplete CO2/H2O circulation controls."""
import pathlib,sys,importlib,copy
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');E=importlib.import_module('tectonics-climate')
def prepare():
 config=copy.deepcopy(C.T.C);config['climate'].update(screenYears=10,model='ExoPlaSim CO2/H2O control only');C.write(C.WORK/'run-config.json',config)
 folder=E.prepare(C.WORK,5210914,'T21',.001);request=C.read(folder/'request.json');request['scope']='CO2/H2O-only control. SF6/N2O residual warming omitted. Never accepted for vegetation.';request['params']['timestep']=30;request['controlOnly']=True
 request.pop('fingerprint',None);request['fingerprint']=C.fingerprint(request);C.write(folder/'request.json',request)
 print(folder,flush=True);return folder
if __name__=='__main__':prepare()
