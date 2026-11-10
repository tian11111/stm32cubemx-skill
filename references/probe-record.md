# CubeMX 探针记录

以下是历史实测摘要。原始日志、临时运行器、CubeMX 软件与固件包不在本仓库中，不能据此独立复现这些实验。各例均未验证实板。

## 已观察的行为

- Windows 上 CubeMX 6.18.1、F103：在已有工程的临时副本中，将 PA6 改为 `GPIO_Output`；同一交互会话回读并重生成后，`.ioc` 和 `gpio.c` 反映了修改，其他引脚信号与 RCC 参数未改变，工程构建成功。
- 无效引脚信号返回 `KO` 后，交互控制器没有发送后续生成命令；普通 CubeMX 批处理遇到 `KO` 则可能继续。控制器还经历过模拟异常测试。
- F103 时钟实验中，`clock set PLLMUL 8` 和 `9` 分别对应工具读数 64 MHz 和 72 MHz；C 宏形式曾返回 `KO`，`clock set hclk` 曾阻塞。不能将这些结果推广到所有器件或版本。
- Windows 上 CubeMX 6.18.1、F407：空目录生成返回 `OK`，但日志中 `syscalls.c`、`sysmem.c` 写入路径重复拼接了工程绝对路径，文件未生成。对临时程序副本的字节码检查发现 `MakefileGenerator.addGccSystemFiles` 无条件将工程路径拼在源码目录前；此处源码目录已经是绝对路径。相对工程路径的对照实验则在保存配置时出现空路径根异常。
- 对仅用于探针的临时 CubeMX 副本修正两处路径拼接后，F407 全新工程自动生成两份源码，并在无网络 capability 的 AppContainer 内以本机 Clang/LLD、GCC 库和临时兼容链接脚本构建成功。生成的 CMake 文件仍包含重复源文件条目及绝对路径。该临时补丁不在本仓库，不是通用修复；未验证原版生成器可一次完成生成，也未验证标准 GCC/Ninja 构建。
- 网络自检只覆盖本机回环及本机网卡测试端口：普通进程连接成功，零网络 capability 的 AppContainer 进程未连接成功。这不证明所有网络路径均已测试。Java 参数和交互控制器本身都不提供操作系统级网络隔离。

## 常规 Windows 交互启动模板

此模板仅展示控制器的 `launch.json` 格式，入口来自安装手册，**未在上述同等离线隔离条件下单独验证**；它不限制网络和磁盘写入。将路径替换为本机 CubeMX 的绝对路径，并按实际安装检查参数。

```json
{
  "argv": [
    "C:/PATH/TO/STM32CubeMX/jre/bin/java.exe",
    "-Dfile.encoding=UTF8",
    "--add-opens=java.desktop/java.awt=ALL-UNNAMED",
    "--add-exports=java.desktop/sun.awt=ALL-UNNAMED",
    "-Djavax.net.ssl.trustStoreType=WINDOWS-ROOT",
    "-jar",
    "C:/PATH/TO/STM32CubeMX/STM32CubeMX.exe",
    "-i"
  ],
  "cwd": "C:/PATH/TO/STM32CubeMX",
  "env": {}
}
```
