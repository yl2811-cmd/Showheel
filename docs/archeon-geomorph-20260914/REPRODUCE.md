# 地貌复算

入口：D:/SKBS/maps/archeon-atlas/src/tectonics-pipeline.py。Python 使用已验证的本地 runtime；Landlab 2.11.0 在 review/foundation-20260914/deps。所有阶段都在独立 --out 目录生成候选。

```powershell
$env:PYTHONUTF8='1'
$p='C:/Users/yl281/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $p maps/archeon-atlas/src/tectonics-pipeline.py --stage mesorelief --region all --years 2000000 --out review/tectonics-20260914/new-geomorph-trial --mask review/tectonics-20260914/evolution-geomorph-v10/applied-masks
& $p maps/archeon-atlas/src/tectonics-pipeline.py --stage geomorph-detail --out review/tectonics-20260914/new-geomorph-trial --mask review/tectonics-20260914/evolution-geomorph-v10/applied-masks
& $p maps/archeon-atlas/src/tectonics-ishkar-coast.py --work review/tectonics-20260914/new-geomorph-trial --history antecedent --formation 12000000 --runoff 0.3 --grid-m 2000 --dt 3125 --halfwidth 480000
& $p maps/archeon-atlas/src/tectonics-pipeline.py --stage evolution-bake --out review/tectonics-20260914/new-geomorph-trial
```

画笔入口：http://127.0.0.1:8796/evolution.html。启动本地 tectonics-server.cjs 后，先选择区域和过程，在右图绘制；保存后另存候选。保留半径、柔边、权重、擦除、撤销与导出。过程 mask 会冻结到每次 job；网站镜像可读烘焙结果，模拟服务仍在本地。

当前精确候选的源代码快照、素材指纹、冻结基底、mask、区域参数、各层时间记录与父级文件指纹都在本地研究目录。每次复算保留旧目录；父级变化后重新生成相关下游和细部。不要将历史试验的河槽直接按格点贴进正式大陆，也不要通过强制填洼把失败河道改成成功。

多种历史和精度的运行组合见本地 run-coast-final.py；失败结果与最细网格的对照必须一起阅读。重新选择细部时会检查实际中心和父级指纹，避免继续复用旧地点的结果。
