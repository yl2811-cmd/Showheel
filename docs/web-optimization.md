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

## 发布仍需处理的事项

1. 最近的 Azure Actions 错误为：`No matching Static Web App was found or the api key was invalid.` 浏览器中的 Azure 门户尚未登录，尚不能核实目标网站、档位及部署令牌。保留原密钥名称 `AZURE_STATIC_WEB_APPS_API_TOKEN_LEMON_TREE_0DC0E5510`，没有写入或展示密钥值。
2. 远端默认分支为 `codex/archeon-atlas`；原工作流仅监听 `main`，远端当前没有 `main`。按本次约定保留原生产触发规则，推送当前分支不会自动上线。
3. 需要依据 Azure 实际单环境额度设置仓库变量 `SWA_QUOTA_MB`。工作流必须确认额度且低于额度的 90% 才允许发布。当前档位未确认，默认 250 MB 只用于保守测算，不代表已确认订阅。

按十进制 500 MB 额度计算，90% 预算为 450 MB，当前仍差 **10.28 MB**；按 250 MB 额度计算，90% 预算为 225 MB，仍差 **235.28 MB**。未自动降画质、付费升级或迁移资源。工作流只上传 `dist-web`，不再直接上传整个 `wwwroot`。

## 验证记录

- 最新导入清单 3,117 项校验通过；再次核对 3,116 个仍可在 SKBS 找到的源文件，没有发现导入后的变化。此前已发布、源目录缺失的审计文档按导入器规则保留。
- 发布目录 1,706 个压缩数据包与 1,518 个其他资源校验通过；9 个页面依赖完整，中英文正文输出与各自源文件哈希相同。
- 浏览器验证覆盖首页、相册、About、独立中英文阅读器、世界及地区地图、Atheria 五个镜头、鹰巢、恒星系、Federation 和三维场景重复进入。
- 加载器测试通过：重复请求合并、取消其中一个订阅不影响另一个订阅、缓存复用、临时 503 恢复、损坏包拒绝。另验证了 Atheria 初始化期间离开后移除画布，并能再次进入。
- 本地复核中发现并修复相册中带括号文件名的编码链接问题，以及直接调用鹰巢入口时区域面板未关闭的问题。源模型与场景美术参数未改动。

本地发布包、详细清单和回归截图已生成；Azure 线上部署尚未完成。
