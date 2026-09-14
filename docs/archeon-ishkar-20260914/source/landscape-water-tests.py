"""Regression cases for the dry-basin and actual-lake-floor fixes."""
import sys,pathlib,importlib,json
sys.path.insert(0,str(pathlib.Path(__file__).parent));H=importlib.import_module('landscape-water');np=H.np

def tests():
 result=H.tests();n=25;yy,xx=np.indices((n,n));z=np.full((n,n),24.,float);z[3:22,3:22]=3.+abs(xx[3:22,3:22]-12)*.5+abs(yy[3:22,3:22]-12)*.3;z[-1]=0.;z[:,12]=np.minimum(z[:,12],18.)
 land=np.ones_like(z,bool);tp=H.topology(z,land,100.);basin=tp['basin'];soil=np.zeros_like(z);allow=np.ones(z.size);zero=np.zeros_like(z);q=np.full(z.size,1e8)
 dry=H.transport(z,soil,tp['order'],tp['bed-receiver'],q,allow,np.full(z.size,1e-6),100.,20.,zero,basin,tp['representative'],tp['starts'],tp['nodes'],tp['spill'],zero.ravel())
 dry_cut=float(dry[2].ravel()[basin>=0].max(initial=0));assert dry_cut>0,'Exposed potential lake basins must remain erodible'
 depth=np.where(z<6,6-z,0.);influx=zero.copy();influx[4,12]=1000.
 wet=H.transport(z,soil,tp['order'],tp['receiver'],q,allow,np.full(z.size,1e-6),100.,10.,influx,basin,tp['representative'],tp['starts'],tp['nodes'],tp['spill'],depth.ravel())
 assert wet[2][depth>.05].max(initial=0)==0,'Submerged bed must not use terrestrial stream-power incision'
 assert abs(wet[6])/max(1,influx.sum()*10,wet[4])<1e-7
 climate={'rain':np.full(z.shape,1.5),'temperature':np.zeros_like(z)};cycle=H.run(z,land,100.,climate,cycles=4,converge=True,max_cycles=160)
 assert cycle['convergence']['passed'],cycle['convergence']
 rerun=H.run(z,land,100.,climate,cycles=6,initial_depth=cycle['lake-depth'],converge=True,max_cycles=20)
 assert np.max(abs(rerun['lake-depth']-cycle['lake-depth']))<.02
 result.update({'dryBasinIncisionM':dry_cut,'periodicConvergence':cycle['convergence'],'restartLevelDifferenceM':float(abs(rerun['lake-depth']-cycle['lake-depth']).max()),'submergedFluvialIncisionM':float(wet[2][depth>.05].max(initial=0))})
 return result
if __name__=='__main__':print(json.dumps(tests(),indent=2))
