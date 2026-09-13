# Atheria 树冠与 Orun 迎风坡发布记录

本轮最终采用 Atheria v14：默认树木密度 1.7×，沿用地形 LOD 的面积混合，不增加独立树林 tiling 或规则细缝。城镇田野树位约 85% 分散、15% 成群；真实树冠先按房屋和通道边界裁切，再汇总到各级 LOD。

弱覆盖直接保留麦田、花田等承托面的颜色；树冠本色按生境变化，并带固定世界坐标的细微色差。相对 v13，生成树高降低 25%，区域范围为 4.5–15 米。远离居住核心的田野噪波贡献乘以 0.6，默认下该部分实际树冠面积减少约 31%；重新分配适宜空间后，全域覆盖仍达到固定旧基线的 1.7×。The Eyrie 精细模型保留独立细节。

Orun 的整条迎风崖壁、低地植被和汇向 Ishkar 的河网同步进入世界地图、Aethelgard、星球投影及导出图。水量收支、预计算加载、主河／城镇／路线保留检查均通过；地图检查确认 12,235 条生成河段最终接入 Ishkar。

## 验证

- `footprints-verification.json`：实际树冠多边形去重及承托面裁切；不以颜色或可见模型数量替代面积。
- `area-verification.json`、`canopy-verification.json`、`lod-verification.json`、`tint-verification.json`：密度 0、1、1.7、2.5、5，以及高矮、颜色、LOD 面积汇总。
- `browser-verification.json`、`packed-browser-verification.json`：近中远景、局部范围、复位、撤销、保存和旧方案载入；树木变化未改变房屋结果或触发房屋重算。
- 静态预览中的 `/api/editor/status` 404 是可选的本地编辑接口探测，页面正常回退为静态场景；单独记录，不作为地图资源加载失败。
- `compressed-verification.json`：全部压缩资源还原后与模型和数据源哈希一致，PNG 保持像素一致，中文与英文正文哈希保持一致。

## 打包

发布输出约 931.41 MB，低于已确认 1 GiB 配额的 90% 预算。新增浮点通道／字节重排与差分仅用于压缩，浏览器解码后恢复原始字节；没有量化、简化模型或降低图像质量。特殊浮点位模式以及不同解码布局的并发请求均有专门测试。

中文 Timelapse 原样同步到 `wwwroot/story.md`；英文稿保持原状。分支为 `codex/archeon-atlas`。Git 推送与实际部署状态另记于 `publication.json`。早先 v8／v12 文档保留阶段证据，Atheria 最终表现以本记录为准。
