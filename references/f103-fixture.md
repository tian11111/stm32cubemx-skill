# F103 固定示例准备

这两个脚本仅用于 `FixedF103Patched` 验证示例，不包含 ST 固件、CubeMX 或生成工程，也不修改 CubeMX 安装。需要 Python 3.9+ 和本机合法取得的 STM32Cube FW_F1 V1.8.7。目标目录必须不存在且与输入目录分离；失败时保留部分目录和日志，不自动删除。

## 已有生成基线

```text
python scripts/prepare_fixture.py --baseline <已有 FixedF103Patched 基线> --firmware <F1 V1.8.7 目录> --destination <新目录>
```

脚本检查目标 `.ioc` 的 MCU、PA5 及固件相对路径；复制前后检查基线与固件源文件清单和 SHA-256，并比较目标清单及哈希。它拒绝链接和 reparse point；快照不是并发修改的原子锁。

## 没有基线时重建

先准备**实际可用的 CubeMX 6.18.1 交互启动 JSON**：格式见[探针记录](probe-record.md)，应启动 `-i`，并根据任务要求预先验证网络与写入隔离。常规模板不提供隔离；[Windows 实验性方案](offline-windows.md)需要单独准备权限和应用副本。不要指向真实工程或自动修改 CubeMX 安装。

```text
python scripts/bootstrap_fixture.py --firmware <F1 V1.8.7 目录> --launch <已准备的 launch.json> --destination <新目录>
```

脚本复制并核对固件包，使用 `cubemx_guard.py` 依次检查版本、加载 F103、设置并回读 PA5、生成 CMake 工程，再检查 `.ioc`、关键文件和 GPIO 初始化函数。结果、计划与原始日志保存在新目录；非零退出或指定错误会使操作失败。通过只表示明确列出的检查通过，**不表示构建、实板或隔离已验证**。

Windows 本机 CubeMX 6.18.1 的未修改生成器曾因重复路径而缺失 `sysmem.c`、`syscalls.c`。真实首次重建成功的探针使用了临时副本中的生成器路径修正；本仓库不包含该修正，也不会自动应用。若原版遇到上述错误，保留日志并停止，不要补造成功。其他版本需要先验证，不应放宽版本检查。

生成前后固件文件的 SHA-256 清单会比较；本流程不保证捕获扫描之间发生又恢复的短暂并发修改。目标工程需按[验收工作流](verification.md)进一步核对和编译。
