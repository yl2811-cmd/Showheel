"""Transparent compositional and terrain-load screening, not interior inversion."""
import json,pathlib,sys,importlib,argparse
sys.path.insert(0,str(pathlib.Path(__file__).parent));T=importlib.import_module('tectonics-model');np=T.np

def interior(config):
    p=config['planet'];r=config['radiusM'];G=6.67430e-11;mass=p['gravityMs2']*r*r/G;volume=4*np.pi*r**3/3;rho=mass/volume
    rows=[]
    for mantle in [4000,4500,5000]:
      for core in [10500,11500,12500]:
        fvol=(rho-mantle)/(core-mantle);fmass=fvol*core/rho;rc=r*fvol**(1/3);d=r-rc
        # Rayleigh is a scaling diagnostic only. Temperature, viscosity, water
        # and plate yielding are independently varied, never inferred from rho.
        rays=[mantle*p['gravityMs2']*3e-5*delta*d**3/(1e-6*eta) for delta,eta in [(1000,1e22),(1500,1e21),(2000,1e20)]]
        rows.append({'assumedCoreMeanKgM3':core,'assumedMantleMeanKgM3':mantle,'coreMassFraction':fmass,'coreRadiusFraction':rc/r,'mantleThicknessKm':d/1000,'rayleighScreen':rays})
    f=p['coreMassFraction'];rc=(mass*f/(p['coreDensityKgM3']*volume))**(1/3)*r
    implied=mass*(1-f)/(volume-4*np.pi*rc**3/3)
    return {'massKg':mass,'meanDensityGcm3':rho/1000,'escapeSpeedMs':np.sqrt(2*p['gravityMs2']*r),'referenceCoreMassFraction':f,'referenceImpliedMantleMeanKgM3':implied,'compositionScreens':rows,'scope':'Uniform-reservoir mass balance and Rayleigh scaling; no pressure-dependent equation of state fit or mantle flow solution','unresolved':['42–47% manuscript core mass fraction needs an equation-of-state check; not silently replaced by 80%.','Mean density does not establish U/Th/K abundance, core cooling power, magnetic moment or reversal rate.','Thin mantle does not imply fast convection: Rayleigh depends on thickness cubed as well as viscosity and thermal forcing.','Seven parent plates are geographic constraints. Fault density and displacement are independent prescribed scenarios.','Double-moon tidal power remains unquantified; no free heat source is added.']}

def run(work):
    c=json.loads((work/'run-config.json').read_text()) if (work/'run-config.json').exists() else T.C
    report={'interior':interior(c),'terrain':[],'references':['https://agupubs.onlinelibrary.wiley.com/doi/10.1002/2015GC006210','https://arxiv.org/abs/2011.04791','https://science.nasa.gov/venus/venus-facts/']}
    from scipy.ndimage import maximum_filter,minimum_filter,label
    for region in c['regions']:
      for seed in c['seeds']:
        folder=work/region/str(seed)
        if not (folder/'height.npy').exists():continue
        g=json.loads((work/region/'grid.json').read_text());dx=g['stepM'];z=np.load(folder/'height.npy');base=np.load(work/region/'revised.npy');kind=np.load(folder/'kind.npy');land=(kind>=30)&(kind!=80)&(kind!=200)
        relief=maximum_filter(z,size=max(3,round(160000/dx)))-minimum_filter(z,size=max(3,round(160000/dx)))
        new=(z-base>1500)&land;high=new&(z>3000);labs,n=label(high);sizes=np.bincount(labs.ravel())*dx**2/1e6
        slopes=np.hypot(*np.gradient(z,dx));change=np.maximum(z-base,0)
        # Airy estimate is conditional, with explicit shallow mantle/crust
        # densities; the global mean mantle density is not used at the Moho.
        root=change*2950/(3350-2950)
        report['terrain'].append({'region':region,'seed':seed,'peakM':float(z[land].max()),'p99HeightM':float(np.percentile(z[land],99)),'maxReliefWithin160kmM':float(relief[land].max()),'newAreaAbove3kmKm2':float(high.sum()*dx**2/1e6),'largeNewMassifs':int(np.count_nonzero(sizes[1:]>10000)),'maxResolvedSlope':float(slopes[land].max()),'p99NewOverburdenMPa':float(np.percentile(change[land]*2950*c['planet']['gravityMs2']/1e6,99)),'p99ConditionalAiryRootKm':float(np.percentile(root[land],99)/1000),'loadStatus':'Screening only; subgrid cliffs need the 250 m / 64 m solver, not a coarse-grid stability pass'})
    T.savejson(work/'physical-screen.json',report)
    print(json.dumps({'density':report['interior']['meanDensityGcm3'],'terrainCases':len(report['terrain'])}))
    return report

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=pathlib.Path,default=T.WORK);a=ap.parse_args();run(a.work)
