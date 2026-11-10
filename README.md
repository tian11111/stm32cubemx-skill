# STM32CubeMX Skill

面向 Codex 的 STM32CubeMX 配置与代码生成技能，包含逐条检查交互命令的 Python 控制器和本地探针结果摘要。

## 安装

目标目录不存在时，将本仓库克隆到 Codex 的技能目录，目录名使用 `stm32cubemx`：

```powershell
git clone https://github.com/tian11111/stm32cubemx-skill.git "$env:USERPROFILE\.codex\skills\stm32cubemx"
```

如果本机已安装该目录，不能直接用上述 clone 命令覆盖；先检查现有内容并备份，再选择单独目录克隆或自行处理更新。重新加载 Codex 后，按需调用 `$stm32cubemx`。需要已安装的 STM32CubeMX、Python 3 和目标器件所需的本地固件包；构建还需兼容的本机工具链。本仓库不分发 ST 软件、固件包或探针补丁。

使用入口和控制器计划格式见 [SKILL.md](SKILL.md)，历史实测边界及启动模板见 [探针记录](references/probe-record.md)。操作前备份工程，先在临时副本验证。控制器不会隔离网络、回滚文件或验证硬件。

Windows 用户可参考[实验性离线启动方案](references/offline-windows.md)。它需要自行准备独立的应用副本和目录权限，不能保证完整文件隔离；仓库不包含已经配置好的 CubeMX 运行副本。

## 测试

在仓库根目录运行：

```powershell
python -m unittest discover -s tests -v
```

测试不能替代实际 CubeMX 生成、工具链构建或硬件验证。实测范围为 Windows 和 CubeMX 6.18.1；其他版本须先验证交互格式。

## 许可

本仓库暂未指定开源许可证；公开可见不等于授予开源使用权限。如需在法定默认权利之外复制、修改或再分发，请联系权利人。
