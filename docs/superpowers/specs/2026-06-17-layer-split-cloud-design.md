# AI Image Layer Split Cloud Design

Date: 2026-06-17

## Decision

Build a separate layer-splitting workflow for AI art assets. The first shippable version is a local batch CLI that calls a cloud service, receives transparent PNG layers plus `manifest.json`, and packages each source image as a ZIP archive.

The cloud target is Alibaba Bailian / Alibaba Cloud. The implementation keeps the local CLI independent from a specific cloud provider by using a stable HTTP contract. If Bailian exposes Qwen-Image-Layered as a native API by implementation time, the cloud adapter can call that API directly. If it does not, the service will run Qwen-Image-Layered in a self-managed GPU container on Alibaba Cloud and expose the same HTTP contract to the CLI.

## Context

Pixelator is currently a Python CLI and PySide6 desktop tool for videos, GIFs, and images. It has a clean rendering pipeline, a queue-based GUI, and tests around CLI dispatch, GUI state, image IO, crop handling, palette handling, and render output. The layer-splitting feature should not change the existing pixel-art rendering workflow.

Qwen-Image-Layered is a suitable model family for this task because it decomposes one image into multiple semantically separated RGBA layers, supports variable layer counts, and supports recursive decomposition. It is heavy enough that bundling it into Pixelator would make the desktop package impractical. The model repository is large, and common setups require PyTorch, Diffusers, GPU runtime dependencies, and persistent model caching.

Alibaba Model Studio / Bailian provides model APIs and Qwen image generation or editing models, with API keys and region-specific endpoints. As of this design, the public official docs found during planning show Qwen-Image and Qwen-Image-Edit APIs, but not a public Qwen-Image-Layered API. Therefore the design explicitly supports both native Bailian APIs and a self-managed Alibaba Cloud GPU service.

References:

- Qwen-Image-Layered GitHub: https://github.com/QwenLM/Qwen-Image-Layered
- Qwen-Image-Layered model page: https://huggingface.co/Qwen/Qwen-Image-Layered
- Alibaba Model Studio overview: https://help.aliyun.com/zh/model-studio/what-is-model-studio
- Alibaba Qwen-Image API: https://help.aliyun.com/zh/model-studio/qwen-image-api
- Alibaba Qwen-Image-Edit API: https://www.alibabacloud.com/help/zh/model-studio/qwen-image-edit-api

## Goals

- Accept one image or a folder of supported image files.
- Submit each image to a cloud layer-splitting backend.
- Produce one ZIP per source image.
- Include transparent PNG layers, a composite preview, and `manifest.json` in each ZIP.
- Preserve enough placement metadata for UI or game code to recompose the original image.
- Keep Qwen and GPU dependencies out of the default Pixelator install.
- Leave the existing `pixelator` and `pixelator-gui` workflows unchanged.

## Non-Goals

- No Pixelator GUI integration in the first version.
- No local GPU inference path in the first version.
- No PSD export in the first version.
- No interactive layer editing in the first version.
- No automatic semantic correction or manual mask editor in the first version.

## User Workflow

The user runs a dedicated CLI command against an image or folder:

```powershell
pixelator-layer split .\inputs --out .\outputs\layers --endpoint https://layer-api.example.com
```

For each input image, the CLI writes:

```text
outputs/layers/
  character_001-layers.zip
  prop_shop_sign-layers.zip
```

Each ZIP contains:

```text
manifest.json
layers/
  layer_001.png
  layer_002.png
  layer_003.png
preview/
  composite.png
```

The transparent PNGs are cropped to their visible alpha bounds by default. `manifest.json` records the original canvas size, per-layer order, and `bbox` so a runtime can restore each layer to the correct position.

## Output Manifest

`manifest.json` uses this schema in the first version:

```json
{
  "schema_version": 1,
  "source": {
    "file_name": "character_001.png",
    "width": 1024,
    "height": 1024,
    "sha256": "source-image-hash"
  },
  "model": {
    "provider": "qwen-image-layered",
    "backend": "aliyun-self-hosted",
    "model_id": "Qwen/Qwen-Image-Layered"
  },
  "layers": [
    {
      "id": "layer_001",
      "name": "layer_001",
      "file": "layers/layer_001.png",
      "order": 0,
      "bbox": [0, 0, 1024, 1024],
      "width": 1024,
      "height": 1024,
      "opacity": 1.0,
      "blend_mode": "normal"
    }
  ],
  "preview": {
    "file": "preview/composite.png"
  }
}
```

Layer names are deterministic in the first version. If the backend can return semantic names reliably, they may be passed through after sanitization, but code must not depend on semantic labels being present.

## Local CLI Components

Add a new package area under `pixelator.layering`:

- `types.py`: dataclasses for layer metadata, manifests, job states, and backend errors.
- `archive.py`: writes ZIP files, validates required files, and normalizes paths.
- `client.py`: HTTP client for the cloud API, including retries, polling, downloads, and typed errors.
- `commands.py`: batch orchestration for image discovery, output naming, progress, and failure policy.
- `cli.py`: argparse entry point for `pixelator-layer`.

Add a new console script:

```toml
pixelator-layer = "pixelator.layering.cli:main"
```

The existing `pixelator` command remains focused on media pixel-art rendering.

## CLI Behavior

Supported command:

```powershell
pixelator-layer split INPUT --out OUTPUT_DIR --endpoint ENDPOINT [options]
```

Options:

- `--api-key-env NAME`: reads the cloud API key from an environment variable. Default: `PIXELATOR_LAYER_API_KEY`.
- `--layers N`: requests a target layer count when the backend supports it.
- `--timeout SECONDS`: maximum wait per source image.
- `--poll-interval SECONDS`: polling interval for async jobs.
- `--overwrite`: replaces existing ZIP outputs.
- `--keep-workdir`: keeps downloaded raw artifacts for debugging.
- `--fail-fast`: stops the batch after the first failed image.

Default behavior continues after per-image failures and returns a non-zero exit code if any input failed.

## Cloud Service Contract

The local CLI talks to a provider-neutral HTTP API:

```http
POST /v1/layer-splits
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

Multipart fields:

- `image`: source image file.
- `request`: JSON object with `target_layers`, `crop_alpha`, and `zip_result`.

Response:

```json
{
  "job_id": "job_123",
  "status": "queued"
}
```

Polling:

```http
GET /v1/layer-splits/{job_id}
```

Response:

```json
{
  "job_id": "job_123",
  "status": "succeeded",
  "artifact_url": "https://...",
  "error": null
}
```

Artifact download:

```http
GET /v1/layer-splits/{job_id}/artifact
```

The artifact is a ZIP using the manifest structure above.

## Cloud Backend

The cloud service has three layers:

- API layer: FastAPI-compatible HTTP service, authentication, upload size limits, job creation, status polling, and artifact download.
- Worker layer: loads Qwen-Image-Layered once per GPU worker process and processes queued jobs.
- Storage layer: temporary input images and output ZIPs, stored either on local ephemeral disk for small deployments or OSS for production.

Deployment on Alibaba Cloud should prefer a GPU instance or container service where the Qwen model can stay loaded between jobs. The model cache and generated artifacts should be outside the container image so deployment updates do not redownload model weights.

## Bailian Integration Strategy

The implementation should use an adapter boundary:

- `NativeBailianLayerBackend`: calls a Bailian native Qwen-Image-Layered API if one is available and returns normalized artifacts.
- `SelfHostedQwenLayerBackend`: runs the official Qwen-Image-Layered pipeline inside the Alibaba Cloud GPU service.

Both adapters must produce identical ZIP and manifest output. The CLI only knows the stable service contract and does not know whether the cloud service used a native Bailian API or a self-hosted Qwen worker.

## Error Handling

Typed errors should be surfaced in CLI output and written to a batch summary:

- `AUTH_FAILED`: endpoint rejected the API key.
- `INPUT_TOO_LARGE`: image exceeds configured upload limits.
- `UNSUPPORTED_IMAGE`: image format cannot be decoded.
- `MODEL_UNAVAILABLE`: backend model is missing, loading, or failed to initialize.
- `JOB_TIMEOUT`: job did not finish within CLI timeout.
- `JOB_FAILED`: backend completed with a model or processing error.
- `ARTIFACT_INVALID`: ZIP or manifest is missing required files or fields.

The CLI should print a concise per-image status line and write `batch-summary.json` beside the ZIP outputs.

## Security And Operations

- Use HTTPS for all remote calls.
- Keep API keys in environment variables, never command history by default.
- Enforce upload size and image dimension limits on the service.
- Do not log raw image bytes, base64 image strings, or signed artifact URLs.
- Apply an artifact TTL so uploaded images and generated ZIPs expire automatically.
- Include `request_id` or `job_id` in all client-visible errors for support.

## Testing

Local tests:

- CLI argument parsing and output naming.
- Image folder discovery for supported formats.
- Manifest validation and deterministic JSON output.
- ZIP writer includes `manifest.json`, `layers/`, and `preview/composite.png`.
- Alpha cropping computes `bbox` correctly.
- HTTP client handles queued, running, succeeded, failed, timeout, auth failure, and invalid artifact responses.

Contract tests:

- A fake cloud server returns a generated ZIP and lets CLI tests verify end-to-end behavior without Qwen or GPU dependencies.
- A malformed ZIP from the fake server is rejected with `ARTIFACT_INVALID`.

Manual smoke test:

- Deploy the cloud service to Alibaba Cloud.
- Run one small PNG through `pixelator-layer split`.
- Verify the ZIP opens, transparent PNGs have valid alpha, `manifest.json` recomposes to the preview dimensions, and `batch-summary.json` marks the job as succeeded.

## Future Extensions

- GUI tab in Pixelator for layer splitting.
- PSD export.
- Recursive decomposition of a selected output layer.
- Optional semantic layer naming.
- Direct OSS input and output paths for large production batches.
- Local GPU backend for offline users.
