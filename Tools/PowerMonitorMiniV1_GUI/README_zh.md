> 固件需要升级到v1.0.0.3以上版本

## 如何校准电流
1. offset0,offset1的显示值和实际值设置为0。
2. 选取offset0，offset1点位，offset0需要小于offset1，例如1A和3A。
3. 电子负载设置为1A，万用表串联监测实际电流值并记录下该值(offset0 实际值)，同时记录电流表屏幕显示值或GUI界面输出数据的电流值(offset0 显示值)。
4. 电子负载设置为3A，万用表串联监测实际电流值并记录下该值(offset1 实际值)，同时记录电流表屏幕显示值或GUI界面输出数据的电流值(offset1 显示值)。
5. GUI界面输入offset0,offset1的显示值和实际值，点击应用按钮。
6. 电子负载设置任意电流，观察万用表和电流表屏幕显示值，看误差是否在1%以下。

![display](../Images/zh/PowerMonitorMiniV1_GUI_zh-CN.gif)
