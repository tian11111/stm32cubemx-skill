# 快照、验收和构建

以下命令仅是工具接口，按实际系统替换路径；需要 Python 3.9 或更新版本。先阅读目标工程 `.ioc`、源码和硬件约束，明确实际期望值，不要照搬样例配置。

## 隔离副本

```text
python scripts/transaction.py create --source <工程目录> --workspace <不存在的独立目录>
python scripts/transaction.py diff --workspace <独立目录>
python scripts/transaction.py restore --workspace <独立目录> --destination <不存在的独立目录>
```

`create` 生成 `baseline`、`working` 和 SHA-256 文件清单；修改或生成只能在 `working` 中进行。创建时会比对复制前后的原工程和两份副本；拒绝符号链接或 Windows reparse point。`diff` 先核验基线，再报告新增、删除、修改的文件；`restore` 只恢复到全新目录。失败可能留下不完整目录供检查。工具不会应用或回滚到原工程：审阅差异并确认原工程没有并发变化后，按用户授权处理。它不保护快照清单免受恶意篡改，也不保证并发修改时的原子性。

## 明确的生成验收

保存 JSON 规格（相对路径均相对于工程根目录；`.ioc` 值与文件中的原始文本一致）：

```json
{
  "ioc": "FlightController.ioc",
  "ioc_values": {"PA9.Signal": "USART1_TX", "PA10.Signal": "USART1_RX"},
  "files": ["Core/Src/usart.c", "Core/Inc/usart.h"],
  "functions": [{"file": "Core/Src/usart.c", "name": "MX_USART1_UART_Init"}],
  "unchanged_ioc_prefixes": ["RCC.", "NVIC."],
  "user_code_files": ["Core/Src/usart.c"]
}
```

```text
python scripts/verify_project.py --project <工作副本> --baseline <基线> --spec <规格.json>
```

工具只检查显式要求的项，返回 JSON 和退出码；缺基线、缺文件、内容不符或 USER CODE 标记不匹配视为失败。函数仅作文本级定义检查，不是 C 解析或语义验证；`.ioc` 解析并非完整 Java properties 实现。未经列出的项没有验证，不能从通过结果推断接线、运行频率或硬件安全。

## 构建

在已审阅的工作副本里，根据工程实际 `CMakePresets.json` 和工具链选择构建命令；有 Debug 预设时可使用 `cmake --preset Debug` 和 `cmake --build --preset Debug -j 1`。CMake 配置过程会执行工程脚本，先检查来源；构建结果不能代替上面的配置验收或实板验证。`doctor.py` 可检查本机工具路径和版本，但不会启动 CubeMX，也不能证明固件包兼容或环境离线。
