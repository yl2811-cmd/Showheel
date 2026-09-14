# 复算当前 Ishkar 连接候选

本轮使用独立目录 `review/tectonics-20260914/landscape-v14`。冻结的 v10、v12、v13 为只读来源。保留三个固定种子 5210914、5210915、5210916。

当前收尾沿用已保存的 v14 基底，不继续增加地貌源点。其后依次运行：

```text
python maps/archeon-atlas/src/landscape-connect.py --seed 5210914 --scenario all --cycles 80
python maps/archeon-atlas/src/landscape-connect.py --seed 5210915 --scenario baseline --cycles 80
python maps/archeon-atlas/src/landscape-connect.py --seed 5210916 --scenario baseline --cycles 80
python maps/archeon-atlas/src/landscape-water-tests.py
python maps/archeon-atlas/src/landscape-connect-verify.py
python maps/archeon-atlas/src/landscape-connect-export.py
```

如需局部水文网格对照，使用 `landscape-connect-detail.py --scenario baseline --grid-m 250`；Crestline 可追加 `--only crestline --grid-m 125` 和 `--grid-m 64`。各档读取同一 2 km 地形、相同父级降水、来水与 64 km 窗口，比较区使用同一 3 km 物理边带。细网格表示水文求解采样，不能据此声称原始地形已经具备相同精度。

每个输出保留父级高程指纹、参数、独立水量收支和季节收敛状态。重复执行只复用指纹一致且完整的结果。季节检验没有推进新的地质有效年；本轮输出不会标为新增 200 万年侵蚀结果。

本地镜像只复制预览实际引用的资产与复算资料，保留原始数值数组在 SKBS 的独立候选目录中。不压缩、不提交、不推送。
