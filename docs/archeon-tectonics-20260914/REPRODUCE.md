# 复算与烘焙

可运行源程序在 `D:/SKBS/maps/archeon-atlas/src`，选中候选的完整数据在 `D:/SKBS/review/tectonics-20260914/strong-painted-v7`。Showheel 读取烘焙文件，计算缓存不放进网站目录。

启动本地画笔页面：运行 `tectonics-server.cjs`，打开 `http://127.0.0.1:8796/tectonics.html`。画笔可控制构造、弯折、岩浆响应、侵蚀、风化、风沙、坡面、岩体、土壤、植被投放和额外保护。旧场景保护不能被普通画笔解除。相同物理输入会复用缓存；只改侵蚀权重时可以复用构造基底。植被权重在真实气候就绪前只保存。

统一入口（以下的 Python 应为已配置的本地运行环境）：

```powershell
python maps/archeon-atlas/src/tectonics-pipeline.py --stage all --fidelity preview --region all --seed 5210914 --years 100000 --mask review/tectonics-20260914/preview-v2/masks --out review/tectonics-20260914/my-new-candidate
```

入口支持 `--region`、`--seed`、`--mask`、`--fault-density`、`--magmatic-intensity`、`--years`、`--out`。`--fidelity regional` 为约 2 km。每次入口调用先保存 mask 和源码快照。`all` 仅运行地貌、全球拼接、烘焙和检查，不会偷偷启动昂贵环流。

真实气候需先重启 Windows，再运行 `src/Setup-ArcheonClimate.ps1` 完成独立 ArcheonSim 环境。执行前使用准备好的 `request.json` 核对恒星辐射、温室气体和地形指纹；首先用一个 T21 候选检查，再决定保留哪些做 T42。

```powershell
python maps/archeon-atlas/src/tectonics-pipeline.py --stage climate --execute-climate --resolution T21 --co2 0.001 --seed 5210914 --out review/tectonics-20260914/strong-painted-v7
```

ExoPlaSim worker 的实际编译与运行仍待 Linux 启动验证；冷结果和未达到能量平衡的结果都会保留，不能用估计降水替换。生态阶段要求真实且平衡的结果：

```powershell
python maps/archeon-atlas/src/tectonics-pipeline.py --stage ecology --seed 5210914 --climate-folder review/tectonics-20260914/strong-painted-v7/climate/5210914/T21-co2-0.001 --mask review/tectonics-20260914/strong-painted-v7/applied-masks --out review/tectonics-20260914/strong-painted-v7
```

生长三倍仅改变潜在生长率，传播、养分、土层形成与故事时间没有乘三。CI 初始走廊是待比较的地理假说，未直接读取今天的植被图。后续实际生态分布、季节气候烘焙及反馈尚未完成验收。

`baked/manifest.json` 保存地形、法线、岩地材质和数值图的解码范围。高程为 uint16 PNG，范围 −4,096 至 16,384 m，约 0.3125 m 每级；这是编码精度，空间网格仍以各文件的 grid 为准。不要把预览插值当成更细网格的物理解算。
