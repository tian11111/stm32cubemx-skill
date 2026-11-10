---
name: "stm32cubemx"
description: "Inspect STM32CubeMX, configure MCU pins and peripherals, and safely generate or regenerate projects with checked interactive commands and file verification."
---

# STM32CubeMX 工程配置与生成

## 适用场景
查找现有 STM32CubeMX 和固件包、分析或修改 `.ioc`、核验引脚与时钟、生成或重生成工程。按任务需要选步骤，不必每次运行全部探针。

## 前置条件
- 先读取目标 `.ioc`、工程结构和已有决定，确认 MCU、板卡、CubeMX/数据库版本和固件包；`.ioc` 的 `MxCube.Version` 只是记录值。
- 优先在完整工程的临时副本操作，保留 `.ioc`、`.mxproject`、用户代码、生成器文件和必要固件；记录文件哈希。修改实际工程前需具备用户授权并保留完整备份。
- 检查 `ProjectManager.DeletePrevious`、`BackupPrevious`、`KeepUserCode` 和 `UAScriptBeforePath` / `UAScriptAfterPath`；执行现有外部脚本须在用户授权范围内。
- 用户要求离线时，必须先由运行环境限制进程网络并隔离写入；Java 参数和本技能控制器本身都不是操作系统级沙箱。不擅自下载或安装依赖。

## 真实验证的闭环
1. 将现有工程复制到临时目录，记录生成前的文件清单和哈希。确认目标引脚空闲且属于用户要求。
2. **在同一次交互会话**加载副本、查询器件、修改引脚并回读。逐条确认成功后再发送 `project generate`；不要把修改步骤和重新加载旧 `.ioc` 的生成步骤拆成彼此无关的会话。
3. 对比前后引脚 CSV，核对生成 `.ioc` 和对应 C 源码；比较新增、删除、修改的文件及其他引脚、时钟。必要时在临时工程中用现有工具链构建。
4. 审阅差异后再依据用户授权处理实际工程；临时副本生成成功不代表空目录首次生成或实板行为已验证。

## 逐条执行与失败停止
本技能的 [scripts/cubemx_guard.py](scripts/cubemx_guard.py) 通过 `MX>` 提示符与 CubeMX 交互。它每次只发送一条命令；遇到 `KO`、不唯一或无法识别的状态、期望文本不符、指定错误文本、超时或进程异常时停止发送后续命令。启动后会记录事件与原始日志；输入校验或创建日志失败时可能没有事件文件。它拒绝嵌套 `script` 和手动 `exit`；停止后不会回滚已经写出的文件。分享日志前检查其中的路径和敏感内容。

`--launch` 是 JSON 对象，包含 `argv` 字符串数组、可选 `cwd` 和 `env`；启动命令必须进入交互式 `-i`。`--plan` 是 JSON 数组，每项包含一条 `command`，可选 `expect`、`reject` 字符串数组和秒数 `timeout`。下面仅示范已测的 F103 项目；应替换为实际临时副本的绝对路径和用户要求：

```json
[
  {"command":"config load \"C:/TEMP/ProbeF103/ProbeF103.ioc\""},
  {"command":"get mcu name","expect":["STM32F103C(8-B)Tx"]},
  {"command":"csv pinout \"C:/TEMP/pinout-before.csv\""},
  {"command":"set pin PA6 GPIO_Output"},
  {"command":"get signal PA6","expect":["PA6: GPIO_Output"]},
  {"command":"csv pinout \"C:/TEMP/pinout-after.csv\""},
  {"command":"get signal PA6","expect":["PA6: GPIO_Output"]},
  {"command":"project generate","timeout":90,"reject":["Problem in the project generation","Problem in the update of the project","Error in Project Generation","OutOfMemoryError","There is insufficient memory","FileNotFoundException"]}
]
```

使用现有 Python 标准库运行，日志和事件路径须是**不存在的新文件**：

```powershell
$Python = '<本机 Python.exe 的绝对路径>'
$SkillDir = '<本技能目录>'
$TaskDir = '<临时目录>'
& $Python "$SkillDir/scripts/cubemx_guard.py" --launch "$TaskDir/launch.json" --plan "$TaskDir/plan.json" --events "$TaskDir/events.json" --transcript "$TaskDir/transcript.log"
if ($LASTEXITCODE -ne 0) { throw 'CubeMX command failed; inspect events and transcript' }
```

控制器依赖 CubeMX 6.18.1 实测的提示符与 `OK`/`KO` 格式；其他版本出现不同格式时应停下核实。`FileNotFoundException` 是针对 F4 日志的防漏检查，仍须检查文件；生成成功的实测包含此条件，但尚未用真实异常验证它能停止生成。启动模板及隔离限制见[探针记录](references/probe-record.md)。模板不会自动断网，历史探针使用的临时隔离运行器未包含在本仓库中。

## 配置、时钟和输出检查
- `load <mcu>` 或 `loadboard <board> <nomode|allmodes>` 后，用 `get mcu name` 核对；先 `get functions <pin>`、`get modes <peripheral>`，再 `set mode`、`set pin`，并用 `get signal`、`get mode active` 回读。
- 时钟可通过 `get ip parameters RCC PLLMUL`、`get ip parameters RCC SYSCLKFreq_VALUE` 查询；F103 的 `clock set PLLMUL 8` 和 `9` 仅是已测示例，须按实际配置选值。工具值并不证明实板频率。
- 生成前检查本地固件与目标工具链。对于目标工程已有配置，用 `project generate`；新目录按目标 MCU 配置后生成。逐项核对 `.ioc`、源码、`Drivers` 和生成器引用的文件是否存在，再检查完整文件差异及必要的构建产物；`OK` 不等于生成完整。
- Windows 上如 Ninja 或 ARM GCC 未在 `PATH`，使用本机已有工具链；当临时项目提供对应的 Debug preset 时，可执行 `cmake --preset Debug` 与 `cmake --build --preset Debug -j 1`。不要把 CMake 编译器识别用 `.bin` 误认为固件。

## 常见失败与恢复
- CubeMX 可能自动检查更新；要求离线时先限制网络。不要把 Java 安全管理器或代理设置当作完整的操作系统网络隔离。
- 命令 `KO` 后批处理仍可能继续，不能仅依靠进程退出码；使用逐条交互并设置读回条件。遇到超时或生成错误，保留部分文件和日志，不自动重试或覆盖原工程。
- 输入非法引脚信号时先查询 `get functions <pin>`。F103 上 `clock set PLLMUL RCC_PLL_MUL9` 曾返回 `KO`；`clock set hclk 72000000` 曾阻塞，不能视为已验证用法。
- 导入时若出现 `VP_RIF_VS_RIF1` 或 RCC `FamilyName`、`MCOFreq_Value`、`USBFreq_Value` 提示，保存日志并核对设备和时钟；本次未查明原因。`nomode` 不保证引脚 CSV 为空。
- F4 离线探针的空目录生成日志包含重复拼接的绝对路径和 `sysmem.c`、`syscalls.c` 的 `FileNotFoundException`，但命令仍返回 `OK`；先检查文件是否确实生成。6.18.1 临时副本的字节码显示生成器将工程路径无条件拼在已是绝对路径的源码目录前；在临时副本修正后，首次生成和兼容构建通过，详见[探针记录](references/probe-record.md)。该补丁只覆盖探针条件，不是通用修复，也未安装到 CubeMX。相对工程路径则在本次探针中触发空路径根异常。`KeepUserCode=true` 不保证区外内容或其他文件不变。

## 证据与限制
[探针记录](references/probe-record.md) 保存 F103 重生成闭环、失败停止及 F407 从零配置、生成缺陷和临时修正后的离线构建证据；F4 使用临时 Clang/LLD 兼容适配，未验证未修改生成器的一次性生成或实板运行。
