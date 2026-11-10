# F103 交互计划示例

这是 Windows 上 CubeMX 6.18.1 的已有工程临时副本重生成计划示例。替换为实际临时副本的绝对路径和用户要求；先确认目标引脚空闲。每项成功后才发送下一项，生成后仍需检查文件和差异。

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

控制器使用方法和验证边界见 [SKILL.md](../SKILL.md) 与[探针记录](probe-record.md)。
