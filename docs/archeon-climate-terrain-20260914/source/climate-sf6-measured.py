"""Audit public PTB SF6 measurements; never promote room-temperature data to a full GCM table."""
import pathlib,sys,importlib,zipfile,io,re
sys.path.insert(0,str(pathlib.Path(__file__).parent));C=importlib.import_module('climate-terrain-common');np=C.np
OUT=C.TASK/'runtime/ptb-sf6';EXPECTED='bfa3f228a09cfd7044a388a7a073b593b33d3696252cb3b3e8df76a37b73a490'

def audit():
    source=OUT/'source.zip'
    if C.sha(source)!=EXPECTED:raise ValueError('PTB source differs from published SHA256')
    rows=[];transmission=[];avogadro=6.02214076e23;column_molecules=110000/9.610517/.02875*avogadro
    with zipfile.ZipFile(source) as archive:
        for name in archive.namelist():
            if pathlib.PurePosixPath(name).name!=name:raise ValueError('Unexpected nested archive entry')
            raw=archive.read(name);dest=OUT/'measured'/name;dest.parent.mkdir(exist_ok=True);dest.write_bytes(raw)
            if not name.endswith('.dat'):continue
            lines=[line.strip() for line in raw.decode().splitlines() if line.strip()]
            a=np.loadtxt(io.StringIO('\n'.join(lines[2:])))
            if a.shape[1]!=3 or not np.isfinite(a).all() or np.any(np.diff(a[:,0])<=0) or np.any(a[:,2]<0):raise ValueError('Invalid measured spectrum '+name)
            pressure=float(re.search(r'_([0-9.]+)Torr',name).group(1))*133.322368
            # Preserve signed noise and its expanded uncertainty. Only the
            # demonstration transmission clips negative central absorption.
            sigma=a[:,1]*1e-4;uncertainty=a[:,2]*1e-4;wn=a[:,0]*100
            C.save_array(dest.with_suffix('.npy'),np.column_stack([wn,sigma,uncertainty]))
            row={'file':name,'sha256':C.sha(dest),'temperatureK':296.05,'pressurePa':pressure,'wavenumberMinCm1':float(a[0,0]),'wavenumberMaxCm1':float(a[-1,0]),'samples':len(a),'negativeNoiseSamples':int((sigma<0).sum()),'integratedSignedCrossSectionMPerMolecule':float(np.trapezoid(sigma,wn)),'originalUnits':['cm-1','cm2 molecule-1','cm2 molecule-1'],'convertedUnits':['m-1','m2 molecule-1','m2 molecule-1']}
            rows.append(row)
            for ppb in [0,.1,.4,1,10]:
                n=column_molecules*ppb*1e-9;tau=np.maximum(0,sigma)*n;tr=np.exp(-tau)
                if np.any(tr<0) or np.any(tr>1) or (ppb==0 and not np.all(tr==1)):raise ValueError('Beer-Lambert zero/positivity regression failed')
                transmission.append({'file':name,'ppbv':ppb,'minimumTransmission':float(tr.min()),'maximumOpticalDepth':float(tau.max()),'equivalentWidthM1':float(np.trapezoid(1-tr,wn))})
    manifest={'sourceDOI':'10.7795/720.20231027','sourceURL':'https://oar.ptb.de/resources/show/10.7795/720.20231027','license':'CC BY 4.0','attribution':'Lüttschwager (Domanskaya), Berezkin, Li, Bohlius, Kim, Harrison and Ebert (PTB, 2023)','archiveSha256':EXPECTED,'spectra':rows,'measuredSpectrumAuditPassed':len(rows)==16,'roomTemperatureTransmissionTestsPassed':True,
              'columnDemonstration':'Monochromatic pure-absorber transmission at measured conditions; excludes gas overlap, thermal emission and vertical temperature variation. Not a radiative-convective climate column.',
              'temperatureCoverageK':[296.05,296.05],'missing':['cold upper-atmosphere temperature coverage','full pressure-temperature table','background gas overlap and continuum comparison','SOCRATES correlated-k generation and column transfer regression'],
              'radiationValidationPassed':False,'formalClimateReady':False}
    C.write(OUT/'manifest.json',manifest);C.write(OUT/'transmission-check.json',{'cases':transmission,'temperatureFitClaimed':False})
    print({'measuredSpectra':len(rows),'hashPassed':True,'radiationValidationPassed':False});return manifest

if __name__=='__main__':audit()
