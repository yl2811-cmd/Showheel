# 本地复算

使用已保存的 Python 运行环境及 review/foundation-20260914/deps 中的 Landlab 2.11.0。基准位于 archives/geomorph-v10-before-erosion；不得用旧 v7 起点重复叠加抬升。

统一入口 tectonics-pipeline.py 支持 cycle、cycle-detail、cycle-bake、cycle-verify，另有受保护地貌与近岸试算入口。运行参数登记 --region、--seed、--mode、--mask、--base-study、--years、--out。

本轮原始结果在 review/tectonics-20260914/erosion-v12。固定种子 5210914、5210915、5210916；时间 0、100000、500000、2000000 有效模型年。Orun/Marneth 另保存10000年；缓地细化仅运行100000年。

冻结画笔在 erosion-applied-masks-20260914。parent-boundary.json 保存父级高度、流量和泥沙的逐期指纹；refinement-config.json 与 detail-plan.json 保存选中窗口。父级任一相关字段改变后应重算依赖窗口。界面画笔另存的候选有独立 job 目录，不回写旧结果。

原始几何、基底重建、素材贡献、后续抬升、侵蚀、沉积、土层和砂质覆盖分开保存。地质有效年不改写为小说年代。
