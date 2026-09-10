# 最新 SKBS 导入与无损发布

当前发布包为 **460,275,135 字节（460.28 MB）**。纳入发布的最新源文件约 1,047.33 MB；全部模型精度、顶点数据及正文均保留。这里的 MB 按 1,000,000 字节统计。

| 内容 | 最新源文件 | 发布资源 |
| --- | ---: | ---: |
| Atheria：最新 20 公里范围及活动数据 | 205.87 MB | 57.60 MB |
| 鹰巢 | 227.57 MB | 24.13 MB |
| 地图数据 | 218.48 MB | 60.67 MB |
| 地形图片 | 137.93 MB | 122.40 MB |
| 网站插图 | 254.11 MB | 191.71 MB |

## 已实现

- 从 `D:/SKBS/maps/archeon-atlas` 导入最新 3,117 项依赖。新增的 `transport.json` 已纳入文件名校验、导入、压缩和场景加载。
- 中文阅读文件逐字节同步自 `D:/SKBS/timelapse-skies_beyond_the_star.txt`，共 809,591 字节。英文阅读文件保留同步前的内容。
- `scripts/build-web.cjs` 从现有 Razor 页面生成 9 个静态页面，包括首页、Archeon、Gallery、About；随后建立独立发布目录。临时 .NET 构建产物位于系统临时目录。
- Atheria、鹰巢和地图数据存储为按内容哈希命名的 gzip 数据包。网站加载器逐块解压，校验压缩包哈希，支持共享请求、重试、取消和浏览器磁盘缓存。现代浏览器需支持 `DecompressionStream`；作者版原有离线文件不受影响。
- 58 张网站图片采用无损 WebP，其余图片保留更小的 PNG 或原格式。1,422 张参与处理的图片通过 RGBA 像素一致性检查；带 ICC、动画或高位深的特殊文件保留原件。
- 发布清单只选取当前导入清单中的地图文件，排除旧版遗留分块；不会同时发布压缩件与未压缩件。`wwwroot` 保留作者版，后续导入不会覆盖发布工具。
- 发布构建会在源结构发生不兼容变化时停止。模型和地图数据解压后的哈希必须与源文件完全一致。

## 本地使用

需要 Node.js 24 和 .NET 8 或兼容 SDK。安装图片处理依赖后，从仓库根目录运行：

```powershell
npm ci --prefix scripts/web-build --no-audit --no-fund
node scripts/import-archeon-atlas.cjs D:/SKBS/maps/archeon-atlas
node scripts/verify-archeon-atlas.cjs
node scripts/build-web.cjs
node scripts/verify-web.cjs
node scripts/serve-web.cjs dist-web 5290
```

输出目录必须为空。保留上一份目录作为回退副本，或通过 `--output` 指定新的目录；工具不会自动删除已有发布结果。默认报告位于 `docs/web-build-report.json`，包含每个源文件和输出文件的大小、哈希、压缩方式及预算差额。`--reuse-report` 与 `--reuse-output` 可复用源哈希和输出哈希都匹配的已验证图片。

压缩发布目录通过 HTTP/HTTPS 访问。原始地图数据的下载按钮由加载器还原文件后下载；直接将旧 JSON 路径当作独立 HTTP API 使用不属于此静态发布接口。

## Visual Studio / App Service 发布

实际生产目标是 Visual Studio 中的 `yl-portfolio - Web Deploy1.pubxml`，Azure App Service Windows，Shared D1 方案。门户确认文件存储额度为 1 GiB。Static Web Apps 是另一条工作流，其 250/500 MB 额度不适用于这个站点。

`Showheel.csproj` 导入 `scripts/optimized-publish.targets`，因此点击“发布”会自动生成并验证压缩资源。源模型仍留在作者目录，发布清单只包含压缩版本；最终 Web Deploy 阶段再校验一次，阻止原件被后续构建步骤加回。整个应用展开约 460.91 MB，真实 Web Deploy ZIP 已成功生成。发布目录超过确认额度的 90% 时自动停止。

该配置同步移除应用部署目录中多余的旧文件，并关闭服务器端 Web Deploy 自动备份以避免在同一额度内重复保存站点。首次替换前将线上站点备份到本机；不要把运行时用户上传的数据放在此部署目录。后续发布仍使用 Visual Studio 自己保存的凭据。

发布版 ASP.NET 通过 `showheel-web-routes.json` 提供原有页面路径、图片路径及原始 JSON/二进制路径；压缩数据响应携带 gzip 编码。未发布的作者版加载方式保持不变。

此前线上静态目录为 986.99 MiB，其中地图 694.93 MiB、图片 290.38 MiB，压缩目录为空；日志不足 1 MiB。根因是旧的未压缩资源仍在服务器，并非日志堆积。

原 Static Web Apps 工作流保留原分支触发规则；它的连接错误需单独处理，不作为 Visual Studio 发布验收结果。

## 验证记录

- 最新导入清单 3,117 项校验通过；再次核对 3,116 个仍可在 SKBS 找到的源文件，没有发现导入后的变化。此前已发布、源目录缺失的审计文档按导入器规则保留。
- 发布目录 1,706 个压缩数据包与 1,518 个其他资源校验通过；9 个页面依赖完整，中英文正文输出与各自源文件哈希相同。
- 浏览器验证覆盖首页、相册、About、独立中英文阅读器、世界及地区地图、Atheria 五个镜头、鹰巢、恒星系、Federation 和三维场景重复进入。
- 加载器测试通过：重复请求合并、取消其中一个订阅不影响另一个订阅、缓存复用、临时 503 恢复、损坏包拒绝。另验证了 Atheria 初始化期间离开后移除画布，并能再次进入。
- 本地复核中发现并修复相册中带括号文件名的编码链接问题，以及直接调用鹰巢入口时区域面板未关闭的问题。源模型与场景美术参数未改动。

本地发布包、详细清单和回归截图已生成；Azure 线上部署尚未完成。
