# 图层拆分阿里云部署说明

## 工具目标

`pixelator-layer` 用于把本地 AI 美术图片上传到图层拆分服务。云端服务接收图片后，调用图层拆分后端生成多张 PNG 图层，并把图层、`manifest.json` 和合成预览图打包成 ZIP 返回给本地命令行。

本地命令行和云端服务之间保持同一套 HTTP 合约：本地只关心上传图片、轮询任务、下载产物；服务端可以在不改变 CLI 的情况下切换 mock、原生 API 或自托管 Qwen 后端。

## 推荐路线

上线前优先检查阿里百炼是否已经提供 `Qwen/Qwen-Image-Layered` 的原生 API。如果百炼已开放该模型的图层拆分能力，建议在服务端新增 native backend，由服务端调用百炼 API，继续复用当前 `pixelator-layer` 的 HTTP 合约。这样本地 CLI 不需要变化，也可以减少自维护 GPU、模型缓存和推理依赖的运维成本。

## 当前可落地路线

如果百炼暂未提供 `Qwen/Qwen-Image-Layered` 原生 API，可以在阿里云 GPU ECS、ACK 或容器服务中自托管模型。服务镜像安装 Pixelator 的 `layer-cloud` 依赖和 Qwen 推理依赖，启动 `pixelator-layer-service`，再通过反向代理或网关对外提供 HTTPS。

百炼仍然可以作为后续模型网关或账号体系的一部分保留：只要服务端继续接受同一套上传、任务状态和 ZIP 下载接口，本地 `pixelator-layer split` 的调用方式不需要调整。

## 本地验证命令

在 PowerShell 中安装开发和云服务依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,layer-cloud]"
```

启动本地服务终端：

```powershell
$env:PIXELATOR_LAYER_SERVICE_TOKEN = "替换为强随机token"
.\.venv\Scripts\pixelator-layer-service.exe
```

另开一个 PowerShell 终端，设置客户端密钥并提交图片：

```powershell
$env:PIXELATOR_LAYER_API_KEY = "替换为强随机token"
.\.venv\Scripts\pixelator-layer.exe split .\samples\hero.png --endpoint http://127.0.0.1:8000 --out .\out
```

验证完成后，输出目录会生成 `hero-layers.zip` 和 `batch-summary.json`。检查 ZIP 内是否包含 `manifest.json`、`preview/composite.png` 和 `layers/` 下的 PNG 图层。

## 云端环境变量

云端服务至少配置以下环境变量：

| 变量 | 说明 |
| --- | --- |
| `PIXELATOR_LAYER_SERVICE_TOKEN` | 服务端 Bearer token，必须使用强随机值，并通过密钥管理或容器环境变量注入。 |
| `PIXELATOR_LAYER_SERVICE_PORT` | 服务监听端口，默认可由平台或反向代理映射。 |
| `PIXELATOR_LAYER_SERVICE_MAX_UPLOAD_MB` | 单张上传图片大小限制，用于控制带宽、磁盘和推理风险。 |
| `PIXELATOR_LAYER_BACKEND` | 后端选择。缺省或 `mock` 使用 mock；`qwen-self-hosted` 或 `aliyun-self-hosted` 使用自托管 Qwen 后端。 |

客户端使用 `PIXELATOR_LAYER_API_KEY` 发送同一个 token。

## Qwen GPU 依赖和模型缓存

默认 Pixelator 桌面包不包含 Qwen 推理所需的重依赖。自托管镜像需要单独安装 CUDA PyTorch、最新版 Diffusers、Transformers、Accelerate 和 Pillow，并确保 CUDA、驱动、PyTorch 与 GPU 实例规格匹配。

服务端默认自托管后端会使用 Diffusers 的 `QwenImageLayeredPipeline`。请安装已经包含该类的最新版或源码版 Diffusers；如果当前稳定版尚未发布该类，需要从官方源码或对应模型说明中指定的版本构建。

建议把 Hugging Face 或模型缓存目录挂载到持久化磁盘，避免容器重启后重复下载权重。也可以按企业网络策略提前把 `Qwen/Qwen-Image-Layered` 权重同步到内网镜像或模型缓存盘。

空间预留建议：

| 用途 | 保守建议 |
| --- | --- |
| 仓库与服务代码 | 很小，通常不足 1GB。 |
| Python 环境 | 预留数 GB，取决于 CUDA PyTorch 版本和镜像层。 |
| Qwen 权重与模型缓存 | 至少预留 30-50GB。 |
| 生产临时 ZIP、上传文件、日志和缓存余量 | 建议整体 80GB+，并结合并发量继续上调。 |

## 安全与运维

- 对公网访问必须放在 HTTPS 之后，建议使用阿里云 SLB、API 网关、Nginx 或 Ingress 做 TLS 终止。
- `PIXELATOR_LAYER_SERVICE_TOKEN` 必须是强随机 token，不要写入仓库、镜像层或日志。
- 服务日志不要记录图片内容、图片二进制、完整提示词或用户敏感路径；只记录任务编号、状态、耗时和必要错误。
- 通过 `PIXELATOR_LAYER_SERVICE_MAX_UPLOAD_MB` 控制上传大小，并在网关层同步配置请求体限制。
- 定期清理上传文件、临时 ZIP 和过期任务产物，避免磁盘被耗尽。
- GPU 实例成本较高，开发环境建议手动启停，生产环境按任务队列、并发和空闲时间设置伸缩或定时释放策略。
- 如果使用 ACK 或容器服务，建议把模型缓存盘和工作目录分开挂载，便于清理临时产物而不影响权重缓存。

## 验证清单

- 本地 mock 服务可通过 `pixelator-layer split` 生成 ZIP。
- 自托管 Qwen 镜像能成功加载 `Qwen/Qwen-Image-Layered`，并且首次加载后的模型缓存位于持久化磁盘。
- 云端健康检查、上传接口、任务状态接口和产物下载接口均通过 HTTPS 可访问。
- 未设置或设置错误 token 时，接口返回未授权错误。
- 超过 `PIXELATOR_LAYER_SERVICE_MAX_UPLOAD_MB` 的图片会被拒绝。
- 下载的 ZIP 能通过 `manifest.json` 找到所有 PNG 图层和预览图。
- 产物过期清理任务已启用，并在测试环境验证不会删除仍在运行的任务文件。
- GPU 利用率、显存、磁盘使用量、请求耗时和错误率已接入监控。
