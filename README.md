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

生成后的显式验收、快照和构建检查见[验收工作流](references/verification.md)；TIM、I2C、USART 等场景的注意事项见[外设检查清单](references/peripherals.md)。`doctor.py` 是只读环境探测，不会自动安装工具或启动 CubeMX。

## F103 示例的固件路径

如果你已有 `FixedF103Patched` 示例的完整生成基线，可以用下列命令在**不存在的新目录**准备独立副本。需要自行提供 STM32Cube FW_F1 V1.8.7 固件包和基线；本仓库不包含它们。

```powershell
python scripts/prepare_fixture.py --baseline '<生成基线目录>' --firmware '<FW_F1_V1.8.7 目录>' --destination '<新工作目录>'
```

脚本校验版本、必要文件和基线中的相对路径，并复制文件到固定的 `output/FixedF103Patched` 与 `firmware-f1` 布局。它不会修改输入目录或启动 CubeMX；完整使用和限制见[探针记录](references/probe-record.md)。

在 Windows 和 CubeMX 6.18.1 的本机测试中，该布局通过加载、修改、重生成和验收。此前偶发的 `0xC0000008` 在 3 次版本查询、3 次重生成和 8 次带退出诊断的重生成中未再复现，**原因尚未确定**；这些通过结果不能排除偶发问题。相关生成验证使用了临时生成器路径修正，不代表未修改的 CubeMX 在所有机器上均可首次生成成功。

## 测试

在仓库根目录运行：

```powershell
python -m unittest discover -s tests -v
```

测试不能替代实际 CubeMX 生成、工具链构建或硬件验证。实测范围为 Windows 和 CubeMX 6.18.1；其他版本须先验证交互格式。

## 许可

本仓库暂未指定开源许可证；公开可见不等于授予开源使用权限。如需在法定默认权利之外复制、修改或再分发，请联系权利人。
