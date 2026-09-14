import sys,importlib
sys.path.insert(0,'D:/SKBS/maps/archeon-atlas/src');X=importlib.import_module('tectonics-cycle');T=X.T;np=T.np;E=importlib.import_module('tectonics-evolution-export');plt=E.plt
cases=[('erosion-only','orun-scarp-250m','Orun 主崖'),('erosion-only','marneth-scarp-250m','Marneth 山带'),('episodic','duskreach-layered-scarp-250m','Duskreach 分层台地'),('episodic','vorhan-layered-scarp-250m','Vorhan 倾斜山地')]
for aspect in ['metres','one-to-one']:
    fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained',facecolor='#eee8d9')
    for ax,(mode,id,title) in zip(axes.flat,cases):
        folder=X.DEFAULT/mode/'refined'/id;g=X.read(folder/'grid.json');a=np.load(folder/'initial.npy');b=np.load(folder/'height.npy');r,c=np.unravel_index(np.argmax(abs(a-b)[8:-8,8:-8]),a[8:-8,8:-8].shape);r+=8;x=np.arange(g['width'])*g['stepM']/1000
        for year,col in [(0,'#8b9c92'),(100000,'#477d82'),(500000,'#bd9757'),(2000000,'#56392e')]:
            path=folder/f'height-{year}.npy'
            if path.exists():ax.plot(x,np.load(path)[r]/(1000 if aspect=='one-to-one' else 1),label='初始' if year==0 else f'{year/10000:g}万年',color=col,lw=1.2)
        ax.set(title=title,xlabel='水平距离 / km',ylabel='海拔 / '+('km' if aspect=='one-to-one' else 'm'));ax.legend(fontsize=8);ax.grid(alpha=.15)
        if aspect=='one-to-one':ax.set_aspect('equal',adjustable='box')
    fig.suptitle('同一位置的有效模型年对照 · '+('水平与垂直 1×' if aspect=='one-to-one' else '纵轴按各局部范围；经过窗口内部最大变化处'),fontsize=13);fig.savefig(T.ROOT/'foundation/erosion'/('profiles-'+aspect+'.png'),dpi=150);plt.close(fig)
