# Whisper Model Optimization for Low-Resource VPS
Created: 2026-02-22

## 核心发现
在 4GB 或更低内存的 CPU-Only VPS 上，运行 `medium` 或更大型号的 Faster-Whisper 模型会导致严重的 Swap 换入换出，使处理速度下降 10 倍以上。

## 优化配置
- **模型规格**：首选 `small`。其内存占用约 500MB，推理速度快，且对清晰语音的转录质量与 medium 几乎一致。
- **量化加速**：
  - `compute_type="int8"`：CPU 运行必选。将权重从 float32 压缩到 int8，不仅内存占用减半，吞吐量还能提升 2-3 倍。
- **并发控制**：
  - `beam_size=5` (默认值，不建议在弱机上加大)。
  - 严禁在同一台机器上开启多个并发进程。

## 运维建议
1. 使用 `top` 监控，若 `RES` 占用超过物理内存 80% 或 `wa` (IO wait) 过高，应立即降级模型。
2. 在 `.env` 中锁定 `WHISPER_MODEL_SIZE`，由 Ops Hub 统一分发。
