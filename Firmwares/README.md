[中文版本](./README_zh.md)  
# Release Notes
**V1.0.0.0**
1. Initial version.

**V1.0.0.1**
1. Fix the issue where the screen brightness parameters in the settings interface are not saved.
2. Add the function of automatic screen sleep(Dis Auto Off). The screen will automatically turn off after 10 seconds of no operation. Press any key or set the communication settings to PD PDO to display the screen.
3. The PD protocol supports EPR Fixed and AVS. A 28V voltage can be applied. The voltage range is 15V - 28V with a 0.1V step adjustment (the 36V gear has not been tested).
4. Communication protocol increases EPR AVS PDO data reading and PD PDO number reading.

**V1.0.0.2**
1. Fix the issue where the negative sign is not displayed for current calibration less than -1.0mA.
2. Adjust the current and power calibration ranges to ±1.5mA, ±15mW.

**V1.0.0.3**
1. Added two-point current calibration function, calibration error within ±1% (calibration via upper computer required)
2. Default CurrentLSB adjusted from 0.1mA to 0.3mA
3. Support communication configuration for INA226 parameters
4. Optimize serial port communication performance

# How to Upgrade, Windows
1. Extract WeActStudio_Upgrade_Tool.zip
2. Run WeActStudio_Upgrade_Tool.exe
3. Connect the device using a data cable
4. Select the fpk firmware
5. Open the serial port
6. Click the "Send" button to start the upgrade

# How to Upgrade, Linux , macOS or Windows
1. Extract WeActStudio_Upgrade_Tool_Python.zip
2. Connect the device using a data cable
3. Run WeActStudio_Upgrade_Tool.py, need to install pyserial library  
Example: python WeActStudio_Upgrade_Tool.py firmware.fpk
4. Wait for the upgrade to complete.
