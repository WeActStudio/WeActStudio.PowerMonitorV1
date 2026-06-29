[English version](./README.md)  
# 版本说明
**V1.0.1.0**
1. PD协议PPS和EPR AVS支持限流设置，配置界面下，长按K2键直至屏幕电流显示变成绿色，为限流设置，再次长按为电压设置；长按K2键直至屏幕显示`W.`后松开，为步长切换  
**<small>注意：限流效果由电源适配器决定，不同电源适配器的电流限制效果会有差异，例如限流设置为0.5A，实际1A才会触发保护</small>**
2. 修复QC协议无法申请9V电压的问题

**V1.0.0.3**
1. 增加电流2点校准功能，校准后误差小于±1%（需要使用上位机进行校准）
2. 调整CurrentLSB默认值，由0.1mA调整为0.3mA
3. INA226参数支持通讯配置
4. 优化串口通讯性能

**V1.0.0.2**
1. 修复电流校准小于-1.0mA后不显示负号的问题
2. 调整电流和功率校准范围，调整为±1.5mA,±15mW

**V1.0.0.1**
1. 修复设置界面屏幕亮度参数不保存的问题
2. 增加屏幕自动息屏功能Dis Auto Off，无操作10秒后自动息屏，单击任意键或通讯设置PD PDO亮屏
3. PD协议支持EPR Fixed和AVS，可申请28V电压，15V-28V 0.1V步进调压(36V挡位未做测试)
4. 通讯协议增加EPR AVS PDO数据读取和PD PDO数量读取

**V1.0.0.0**
1. 初始版本 Initial version

# Windows下怎样升级
1. 解压WeActStudio_Upgrade_Tool.zip
2. 运行WeActStudio_Upgrade_Tool.exe
3. 使用数据线连接设备
4. 选择fpk固件
5. 打开串口
6. 点击发送按钮，开始升级

# Linux、macOS或Windows下怎样升级
1. 解压WeActStudio_Upgrade_Tool_Python.zip
2. 使用数据线连接设备
3. 运行WeActStudio_Upgrade_Tool.py, 需要安装pyserial库  
示例：python WeActStudio_Upgrade_Tool.py firmware.fpk
4. 等待升级完成