> Firmware needs to be upgraded to version v1.0.0.3 or above.

## How to Calibrate Current
1. Set the displayed and actual values of offset0 and offset1 to 0.
2. Select the calibration points for offset0 and offset1, where offset0 must be less than offset1. For example, 1A and 3A.
3. Set the electronic load to 1A. Use a multimeter connected in series to measure and record the actual current (the offset0 actual value). At the same time, record the displayed current value on the ammeter screen or output from the GUI (the offset0 displayed value).
4. Set the electronic load to 3A. Use a multimeter connected in series to measure and record the actual current (the offset1 actual value). At the same time, record the displayed current value on the ammeter screen or output from the GUI (the offset1 displayed value).
5. Enter the displayed and actual values of offset0 and offset1 in the GUI, then click the "Apply" button.
6. Set the electronic load to an arbitrary current value. Compare the multimeter reading with the ammeter/GUI displayed value to verify that the error is within ±1%.

![display](../Images/en/PowerMonitorMiniV1_GUI_en.gif)
