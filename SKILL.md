---
name: "stm32cubemx"
description: "Use when STM32 work may change CubeMX-managed pins, peripheral initialization, clocks, DMA or interrupts; inspect and synchronize the affected .ioc and generated code, or explicitly report an unresolved mismatch."
---

# STM32CubeMX 工程配置与生成

## 适用场景
涉及可能由 CubeMX 管理的引脚、复用功能、外设初始化、时钟、DMA 或 NVIC 配置时使用，也适用于检查 `.ioc` 或生成工程。按任务需要选步骤，不必每次运行全部探针。

## 固件修改时的配置判断
1. 动手前确定受影响的工程与 `.ioc`，检查现有 `.ioc`、生成初始化代码、用户代码和硬件连接；一个工作区可能有多个独立工程，不能改错目标。
2. 判断需求是 CubeMX 管理的**初始配置**，还是运行时动态控制或用户代码。沿初始化、配置加载和重新配置的调用链检查实际生效的设置；运行时参数不一定需要修改 `.ioc`，不要为了形式同步而改变无关配置。
3. 若需要改变 CubeMX 管理的初始配置，优先通过 CubeMX 修改对应 `.ioc` 并回读，按任务授权和工程状态在临时副本生成、审阅差异后同步工程。不要只改生成代码就声称配置已完成；也不要把 `.ioc` 中的文本直接修改视为已通过 CubeMX 验证。
4. 核对目标引脚、外设模式、时钟及与任务相关的 DMA/NVIC，检查引脚冲突、其他外设、生成文件删除及用户代码保留；再执行与改动相关的构建或其他检查。若无法运行 CubeMX、回读或生成，保留证据并明确报告配置与生成代码是否仍未同步及剩余工作；不要用编译成功替代配置或实板验证。

需要快照、生成后检查或恢复副本时，使用[验收工作流](references/verification.md)；外设具体核对项见[外设检查清单](references/peripherals.md)。这些工具不会自动覆盖原工程。

需要复用本机已生成的 `FixedF103Patched` 基线时，可使用 [prepare_fixture.py](scripts/prepare_fixture.py) 复制基线与固件包并核对 SHA-256；没有基线而需重建该示例时，可使用 [bootstrap_fixture.py](scripts/bootstrap_fixture.py) 和已准备的 CubeMX 交互启动配置。两者仅用于该 F103 验证示例，不是任意工程生成器；前置条件、命令及首次生成限制见 [F103 示例准备](references/f103-fixture.md)。

## 任务输入与报告
- 按任务收集 MCU 或板卡、工程路径、期望更改、目标工具链和离线约束；已有工程以实际 `.ioc` 和文件为准。缺少影响操作的必要信息时先确认。
- 完成时报告实际更改的工程和配置、使用的 CubeMX 与工具链、执行的验证及结果、离线隔离是否得到验证，以及未覆盖的生成、构建或硬件边界。

## 前置条件
- 先读取目标 `.ioc`、工程结构和已有决定，确认 MCU、板卡、CubeMX/数据库版本和固件包；`.ioc` 的 `MxCube.Version` 只是记录值。
- 优先在完整工程的临时副本操作，保留 `.ioc`、`.mxproject`、用户代码、生成器文件和必要固件；记录文件哈希。修改实际工程前需具备用户授权并保留完整备份。
- 检查 `ProjectManager.DeletePrevious`、`BackupPrevious`、`KeepUserCode` 和 `UAScriptBeforePath` / `UAScriptAfterPath`；执行现有外部脚本须在用户授权范围内。
- 用户要求离线时，必须先由运行环境限制进程网络并隔离写入；无法验证所需隔离时不要启动 CubeMX。Java 参数和本技能控制器本身都不是操作系统级沙箱。不擅自下载或安装依赖。[Windows 实验性启动方案](references/offline-windows.md)可复用进程隔离，但需要预先准备应用副本和权限，不能自动证明文件或全部网络路径隔离。

## 真实验证的闭环
1. 将现有工程复制到临时目录，记录生成前的文件清单和哈希。根据需求确认目标资源的当前用途及冲突，不要假定引脚或外设空闲。
2. **在同一次 CubeMX 会话**加载副本并核对器件，先查询目标资源的当前配置、可用功能或模式，再按需求设置并回读；相关引脚、时钟、DMA 和中断按实际改动一并核对。CLI 命令或参数不确定时先查当前版本的帮助，必要时可使用 CubeMX 界面完成整个修改和生成，不要猜测或照搬其他芯片的值。无法确认设置或回读时停止并报告，不要声称同步完成。
3. 逐项确认成功后在该会话生成（CLI 使用 `project generate`），不要重新加载旧 `.ioc`。对比前后引脚 CSV，核对生成 `.ioc` 和对应 C 源码；比较新增、删除、修改的文件、用户代码及构建引用，检查无关配置是否变化。必要时在临时工程中用现有工具链构建。
4. 审阅差异后再依据用户授权处理实际工程；临时副本生成成功不代表空目录首次生成或实板行为已验证。

## 逐条执行与失败停止
本技能的 [scripts/cubemx_guard.py](scripts/cubemx_guard.py) 通过 `MX>` 提示符与 CubeMX 交互。它每次只发送一条命令；遇到 `KO`、不唯一或无法识别的状态、期望文本不符、指定错误文本、超时或进程异常时停止发送后续命令。启动后会记录事件与原始日志；输入校验或创建日志失败时可能没有事件文件。它拒绝嵌套 `script` 和手动 `exit`；停止后不会回滚已经写出的文件。分享日志前检查其中的路径和敏感内容。

`--launch` 是 JSON 对象，包含 `argv` 字符串数组、可选 `cwd` 和 `env`；启动命令必须进入交互式 `-i`。`--plan` 是 JSON 数组，每项包含一条 `command`，可选 `expect`、`reject` 字符串数组和秒数 `timeout`。在同一会话加载临时副本、核对 MCU、导出修改前后引脚、设置并回读信号，全部成功后才生成；[F103 计划示例](references/f103-plan.md)展示具体命令，应替换为实际路径和用户要求。

使用现有 Python 标准库运行，日志和事件路径须是**不存在的新文件**：

```powershell
$Python = '<本机 Python.exe 的绝对路径>'
$SkillDir = '<本技能目录>'
$TaskDir = '<临时目录>'
& $Python "$SkillDir/scripts/cubemx_guard.py" --launch "$TaskDir/launch.json" --plan "$TaskDir/plan.json" --events "$TaskDir/events.json" --transcript "$TaskDir/transcript.log"
if ($LASTEXITCODE -ne 0) { throw 'CubeMX command failed; inspect events and transcript' }
```

控制器依赖 Windows 上 CubeMX 6.18.1 实测的提示符与 `OK`/`KO` 格式；使用其他版本前先验证这些格式，无法确认时停止。`FileNotFoundException` 是针对 F4 日志的防漏检查，仍须检查文件；生成成功的实测包含此条件，但尚未用真实异常验证它能停止生成。启动模板及隔离限制见[探针记录](references/probe-record.md)和[实验性离线方案](references/offline-windows.md)；常规模板不会自动断网。

提示符之后可能还有异步输出；控制器只能检查已收到的内容，不能保证捕获发送下一条命令之后才到达的错误。生成后必须核对完整日志与实际文件，不得只凭交互状态认定生成完整。
可按需使用 `--settle-seconds` 等待提示符后的静默期、`--log-reject <文本>` 在退出后扫描完整日志；它们都不能保证捕获任意延迟的错误。

## 配置、时钟和输出检查
- `load <mcu>` 或 `loadboard <board> <nomode|allmodes>` 后，用 `get mcu name` 核对；先 `get functions <pin>`、`get modes <peripheral>`，再 `set mode`、`set pin`，并用 `get signal`、`get mode active` 回读。
- 时钟可通过 `get ip parameters RCC PLLMUL`、`get ip parameters RCC SYSCLKFreq_VALUE` 查询；F103 的 `clock set PLLMUL 8` 和 `9` 仅是已测示例，须按实际配置选值。工具值并不证明实板频率。
- 生成前检查本地固件与目标工具链。对于目标工程已有配置，用 `project generate`；新目录按目标 MCU 配置后生成。逐项核对 `.ioc`、源码、`Drivers` 和生成器引用的文件是否存在，再检查完整文件差异及必要的构建产物；`OK` 不等于生成完整。
- Windows 上如 Ninja 或 ARM GCC 未在 `PATH`，先检查工程的 CMake preset、工具链文件及其中指定的工具是否可用；不要仅凭 `PATH` 判定缺失。当临时项目提供对应的 Debug preset 时，可执行 `cmake --preset Debug` 与 `cmake --build --preset Debug -j 1`。不要把 CMake 编译器识别用 `.bin` 误认为固件。

## 常见失败与恢复
- CubeMX 可能自动检查更新；要求离线时先限制网络。不要把 Java 安全管理器或代理设置当作完整的操作系统网络隔离。
- 命令 `KO` 后批处理仍可能继续，不能仅依靠进程退出码；使用逐条交互并设置读回条件。遇到超时或生成错误，保留部分文件和日志，不自动重试或覆盖原工程。
- 输入非法引脚信号时先查询 `get functions <pin>`。F103 上 `clock set PLLMUL RCC_PLL_MUL9` 曾返回 `KO`；`clock set hclk 72000000` 曾阻塞，不能视为已验证用法。
- 导入时若出现 `VP_RIF_VS_RIF1` 或 RCC `FamilyName`、`MCOFreq_Value`、`USBFreq_Value` 提示，保存日志并核对设备和时钟；本次未查明原因。`nomode` 不保证引脚 CSV 为空。
- F4 离线探针的空目录生成日志包含重复拼接的绝对路径和 `sysmem.c`、`syscalls.c` 的 `FileNotFoundException`，但命令仍返回 `OK`；先检查文件是否确实生成。6.18.1 临时副本的字节码显示生成器将工程路径无条件拼在已是绝对路径的源码目录前；在临时副本修正后，首次生成和兼容构建通过，详见[探针记录](references/probe-record.md)。该补丁只覆盖探针条件，不是通用修复，也未安装到 CubeMX。相对工程路径则在本次探针中触发空路径根异常。`KeepUserCode=true` 不保证区外内容或其他文件不变。

## 证据与限制
[探针记录](references/probe-record.md) 保存 F103、F407 的生成实验及 G0、L4 的配置回读结果；G0/L4 尚未验证代码生成、构建或实板，F4 构建使用临时生成器修正和工具链适配。
