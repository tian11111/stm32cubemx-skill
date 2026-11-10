# Windows 实验性离线启动方案

`scripts/offline_run.ps1` 复用 AppContainer 零 capability 令牌启动 `cubemx_guard.py` 的目标进程。目标进程在恢复前检查令牌；它和子进程置于关闭时终止的 Job。profile、临时 launcher 和临时启动 JSON 在正常或可捕获错误退出时清理。不会修改防火墙或 ACL，也不自动准备 CubeMX。

**边界：**零 capability 不等于文件系统沙箱；目标可能访问既有 ACL 允许的其他位置，也不能仅凭令牌证明所有网络路径被阻断。必须先自行验证隔离；若用户要求隔离写入，也须由运行环境另行实现并验证。强制结束 PowerShell 或系统崩溃时，profile 及临时文件可能残留，应先核实名称和所有权再清理。不要将实际工程目录赋予此 profile 权限。

## 准备

1. 准备专用临时工作目录、Python 3、.NET Framework C# 编译器、相应固件包以及**能够在 AppContainer 下运行的 CubeMX 副本**。仓库不含 ST 软件或其修改文件。此前环境需要临时 home/tmp、内存 preferences、JNA/SQLite 库及应用 classpath 的特定适配；普通安装的通用准备步骤尚未验证。无法准备或验证时停止。
2. 选一个尚不存在的唯一 profile 名称，运行 `powershell -NoProfile -File .\scripts\offline_profile_sid.ps1 -ProfileName <名称>` 取得 Windows 派生的 AppContainer SID，并仅在专用临时副本范围内预设必要的目录权限。启动脚本不设置 ACL。不要授权真实工程目录，也不要改变系统防火墙。SID 派生只查询，不创建 profile。
3. 分别验证普通进程与隔离进程对本机测试端口的连接、目录内正常写入和禁止写入的目标路径。此前仅测试了本机回环和本机网卡端口；不同机器需自行核验。
4. 按 [探针记录](probe-record.md) 的格式准备 `launch.json` 和 `plan.json`，让 `launch.argv[0]` 为目标 Java 的绝对路径，后续参数实际进入 CubeMX `-i`，并在模板中显式设置临时 HOME、TEMP 等。模板 `cwd` 只作用于 launcher；目标进程工作目录固定为目标可执行文件所在目录。保存原始日志前检查敏感信息。

示例只展示调用格式，所有占位符都需要替换：

```powershell
& .\scripts\offline_run.ps1 `
  -WorkDir 'C:\TEMP\cube-probe' `
  -ProfileName '<唯一的新 profile 名称>' `
  -ProfileSid '<该名称派生且已预授权的 SID>' `
  -Python 'C:\PATH\python.exe' `
  -Launch 'C:\TEMP\cube-probe\launch.json' `
  -Plan 'C:\TEMP\cube-probe\plan.json' `
  -Events 'C:\TEMP\cube-probe\events.json' `
  -Transcript 'C:\TEMP\cube-probe\transcript.log'
if ($LASTEXITCODE -ne 0) { throw 'Offline run failed; inspect logs and cleanup' }
```

`Events` 和 `Transcript` 必须为不存在的文件。检查 transcript 中 `[offline-token] appcontainer=1 capabilities=0`、逐条响应、退出码及实际生成文件。受控探针显示该令牌通过本机两个端口测试，不代表其他网络路径或未测试的系统均受限。首次运行前应使用无副作用的版本查询和本机测试端口验证，而非直接生成实际工程。
