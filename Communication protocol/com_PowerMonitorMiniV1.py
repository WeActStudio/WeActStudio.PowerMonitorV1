import serial
import time
import threading
from queue import Queue, Empty, Full
from enum import IntEnum
import traceback
import struct

class Command(IntEnum):
    CMD_WHO_AM_I = 0x01
    CMD_OUTPUT_DATA = 0x02
    CMD_OUTPUT_DATA_MAX = 0x03
    CMD_MAH_MWH = 0X04
    CMD_UPTIME = 0x05
    CMD_OUTPUT_DATA_MAX_RESET = 0x06
    CMD_INPUT_TYPE = 0x07
    CMD_PD_PDO_FIX = 0x08
    CMD_PD_PDO_PPS = 0x09
    CMD_PD_PDO = 0x0A
    CMD_PD_PDO_AVS = 0x0B
    CMD_PD_PDO_NUM= 0x0C
    CMD_PD_PDO2 = 0x0D
    CMD_SYSTEM_RESET = 0x40
    CMD_SYSTEM_VERSION = 0x42
    CMD_SYSTEM_SERIAL_NUM = 0x43
    CMD_SYSTEM_FACTORY_RESET = 0x45
    CMD_SYSTEM_LCD_PANEL_TYPE = 0x46
    CMD_SYSTEM_CURRENT_RSHUNT = 0x47
    CMD_SYSTEM_CURRENT_OFFSET = 0x48
    CMD_SYSTEM_INA226_CONFIG = 0x49
    CMD_END = 0x0A
    CMD_READ = 0x80

    @property
    def READ_LENGTH(self):
        return {
            Command.CMD_WHO_AM_I: 0,
            Command.CMD_OUTPUT_DATA: 14,
            Command.CMD_OUTPUT_DATA_MAX: 14,
            Command.CMD_MAH_MWH: 10,
            Command.CMD_UPTIME: 6,
            Command.CMD_INPUT_TYPE: 3,
            Command.CMD_PD_PDO_FIX: 0,
            Command.CMD_PD_PDO_PPS: 0,
            Command.CMD_PD_PDO: 5,
            Command.CMD_PD_PDO_AVS: 0,
            Command.CMD_PD_PDO_NUM: 5,
            Command.CMD_PD_PDO2: 7,
            Command.CMD_SYSTEM_LCD_PANEL_TYPE: 3,
            Command.CMD_SYSTEM_CURRENT_RSHUNT: 3,
            Command.CMD_SYSTEM_VERSION: 0,
            Command.CMD_SYSTEM_SERIAL_NUM: 0,
            Command.CMD_SYSTEM_CURRENT_OFFSET: 22,
            Command.CMD_SYSTEM_INA226_CONFIG: 5,
        }.get(self, 0)
    
LCD_PANEL_TYPE = {
    1: "BOE",
    0: "HAN",
}

INPUT_TYPE = {
    0: "Initialization",
    1: "PD",
    2: "QC",
    3: "DC",
    4: "Initialization",
}

class com_PowerMonitorMiniV1:
    def __init__(self, port, baudrate=115200, timeout=1, queue_maxsize=100, use_crc8=False):
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        if not self.ser.is_open:
            raise Exception(f"无法打开串口 Unable to open serial port {port}")
        time.sleep(0.1)
        self._stop_event = threading.Event()
        self._read_ok_event = threading.Event()
        self._write_ok_event = threading.Event()
        self._read_result = None
        self._read_thread = threading.Thread(target=self._read_serial, daemon=True)
        self._read_thread.start()
        self._send_queue = Queue(maxsize=queue_maxsize)
        self._send_thread = threading.Thread(target=self._send_commands, daemon=True)
        self._send_thread.start()
        self._use_crc8 = use_crc8

    def _read_serial(self):
        """
        线程函数，持续读取串口数据
        Thread function, continuously read serial port data
        """
        buffer = bytearray()
        time_last = time.time()
        while not self._stop_event.is_set():
            try:
                if self.ser.in_waiting:
                    buffer += self.ser.read(self.ser.in_waiting)
                    time_last = time.time()

                    while len(buffer) > 0:
                        if (buffer[0] & 0x7F) in [
                            Command.CMD_WHO_AM_I, 
                            Command.CMD_SYSTEM_VERSION,
                            Command.CMD_SYSTEM_SERIAL_NUM,
                            Command.CMD_PD_PDO_FIX,
                            Command.CMD_PD_PDO_PPS,
                            Command.CMD_PD_PDO_AVS
                        ]:
                            if len(buffer) > 1 and buffer[1] == len(buffer) - 3:
                                end_pos = 3 + buffer[1]
                                frame = buffer[:end_pos]
                                buffer = buffer[end_pos+1:]
                                # Check CRC if enabled
                                if self._use_crc8 and len(frame) > 1:
                                    # Extract data without CRC
                                    data = frame[:-1]
                                    received_crc = frame[-1]
                                    calculated_crc = self.calculate_crc8(data)
                                    
                                    if received_crc != calculated_crc:
                                        print(f"CRC校验失败 CRC check failed. Received: {received_crc:02X}, Calculated: {calculated_crc:02X}")
                                        buffer = bytearray()
                                        break
                                    
                                    self._read_result = data[2:]
                                else:
                                    self._read_result = frame[2:-1]
                                    
                                self._read_ok_event.set()
                            else:
                                break
                        else:
                            cmd = buffer[0] & 0x7F
                            try:
                                if Command(cmd).READ_LENGTH == 0:
                                    break
                            except:
                                break
                            if len(buffer) >= Command(cmd).READ_LENGTH:
                                frame = buffer[:Command(cmd).READ_LENGTH]
                                if self._use_crc8:
                                    # Extract data without CRC
                                    data = frame[:-1]
                                    received_crc = frame[-1]
                                    calculated_crc = self.calculate_crc8(data)
                                    
                                    if received_crc != calculated_crc:
                                        print(f"CRC校验失败 CRC check failed. Received: {received_crc:02X}, Calculated: {calculated_crc:02X}")
                                        buffer = bytearray()
                                        break  # Skip this frame
                                    
                                    self._read_result = data[1:]
                                else:
                                    self._read_result = frame[1:-1]
                                
                                self._read_ok_event.set()
                                buffer = buffer[Command(cmd).READ_LENGTH:]
                            else:
                                break
                else:
                    if time.time() - time_last > 0.05:
                        buffer = bytearray()
                        time_last = time.time()

                time.sleep(0.01)
            
            except serial.SerialException as e:
                print(f"串口断开连接 Serial port disconnected: {e}")
                traceback.print_exc()
                self.ser.close()
                return
            except Exception as e:
                print(f"读取串口数据时出错 Error reading serial port data: {e}")
                traceback.print_exc()
                buffer = bytearray()

    def _send_commands(self):
        """
        线程函数，处理队列中的指令发送，队列空闲时每隔 100ms 发送坐标查询命令
        Thread function, handle command sending in the queue, and send coordinate query commands every 100ms when the queue is idle
        """
        while not self._stop_event.is_set():
            try:
                # 持续处理队列中的所有命令
                while True:
                    w_data = self._send_queue.get_nowait()
                    self.ser.write(w_data)
                    self._write_ok_event.set()
            except Empty:
                time.sleep(0.1)
            except serial.SerialException as e:
                print(f"串口断开连接 Serial port disconnected: {e}")
                traceback.print_exc()
                self.ser.close()
                return
            except Exception as e:
                print(f"发送指令时出错 Error sending command: {e}")
                pass
    
    def send_command(self, cmd, wait=False):
        """
        发送指令到设备
        Send a command to the device
        """
        self._write_ok_event.clear()
        try:
            self._send_queue.put(cmd, timeout=0.5)
        except Full:
            print("发送指令队列已满，指令丢弃 Command queue is full, command discarded")
        if wait and not self._write_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for send command")
            raise ValueError("Timeout waiting for send command")

    def who_am_i(self):
        s = bytearray()
        s.append(Command.CMD_WHO_AM_I | Command.CMD_READ)
        
        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self._read_ok_event.clear()
        self.send_command(s)
        if not self._read_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for response")
            return None
        return self._read_result.decode('utf-8')
    
    def system_version(self):
        s = bytearray()
        s.append(Command.CMD_SYSTEM_VERSION | Command.CMD_READ)
        
        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self._read_ok_event.clear()
        self.send_command(s)
        if not self._read_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for response")
            return None
        return self._read_result.decode('utf-8')
    
    def system_serial_num(self):
        s = bytearray()
        s.append(Command.CMD_SYSTEM_SERIAL_NUM | Command.CMD_READ)
        
        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self._read_ok_event.clear()
        self.send_command(s)
        if not self._read_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for response")
            return None
        return self._read_result.decode('utf-8')
    
    def factory_reset(self):
        s = bytearray()
        s.append(Command.CMD_SYSTEM_FACTORY_RESET)
        
        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self.send_command(s, True)

    def current_rshunt_get(self):
        s = bytearray()
        s.append(Command.CMD_SYSTEM_CURRENT_RSHUNT | Command.CMD_READ)
        
        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self._read_ok_event.clear()
        self.send_command(s)
        if not self._read_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for response")
            return None
        return int(self._read_result[0])

    def current_rshunt_set(self, value):
        s = bytearray()
        s.append(Command.CMD_SYSTEM_CURRENT_RSHUNT)
        if value < 0 or value > 255:
            raise ValueError("Current RSHUNT value must be between 0 and 255")
        s.append(value)
        
        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self.send_command(s, True)

    def current_offset_get(self):
        """
        获取电流偏移
        Get current offset
        offset0: {"display": int, "actual": int}
        offset1: {"display": int, "actual": int}
        zero_offset: int
        """
        s = bytearray()
        s.append(Command.CMD_SYSTEM_CURRENT_OFFSET | Command.CMD_READ)
        
        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self._read_ok_event.clear()
        self.send_command(s)
        if not self._read_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for response")
            return None

        value = struct.unpack("<iiiii", self._read_result)
        offset0 = {"display": value[0], "actual": value[1]}
        offset1 = {"display": value[2], "actual": value[3]}
        zero_offset = int(value[4])
        return offset0,offset1,zero_offset
    
    def current_offset_set(self, offset0_display, offset0_actual, offset1_display, offset1_actual, zero_offset):
        """
        设置电流偏移，offset1必须大于offset0，且为同为正数或负数
        Set current offset, offset0 must be greater than offset1, and must be the same sign
        offset0_display: ±1000000, unit: 0.1mA
        offset0_actual: ±1000000, unit: 0.1mA
        offset1_display: ±1000000, unit: 0.1mA
        offset1_actual: ±1000000, unit: 0.1mA
        zero_offset: ±15, unit: 0.1mA
        """
        if offset0_display < -1000000 or offset0_display > 1000000:
            raise ValueError("offset0_display must be between -1000000 and 1000000")
        if offset0_actual < -1000000 or offset0_actual > 1000000:
            raise ValueError("offset0_actual must be between -1000000 and 1000000")
        if offset1_display < -1000000 or offset1_display > 1000000:
            raise ValueError("offset1_display must be between -1000000 and 1000000")
        if offset1_actual < -1000000 or offset1_actual > 1000000:
            raise ValueError("offset1_actual must be between -1000000 and 1000000")
        if zero_offset < -15 or zero_offset > 15:
            raise ValueError("zero_offset must be between -15 and 15")
        
        s = bytearray()
        s.append(Command.CMD_SYSTEM_CURRENT_OFFSET)
        data = struct.pack("<iiiii", offset0_display, offset0_actual, offset1_display, offset1_actual, zero_offset)
        s += data

        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self.send_command(s, True)

    def ina226_config_get(self):
        """
        获取INA226配置
        Get INA226 configuration
        "currentLSB": unit: 0.1mA
        """
        s = bytearray()
        s.append(Command.CMD_SYSTEM_INA226_CONFIG | Command.CMD_READ)

        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self._read_ok_event.clear()
        self.send_command(s)
        if not self._read_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for response")
            return None
        
        currentLSB, config_reg = struct.unpack("<BH", self._read_result)

        vshct   = (config_reg >> 3)  & 0x07   # bit3-5
        vbusct  = (config_reg >> 6)  & 0x07   # bit6-8
        avg     = (config_reg >> 9)  & 0x07   # bit9-11

        return {
            "currentLSB": currentLSB,
            "reg_value": config_reg,
            "reg":{
                "vshct": vshct,
                "vbusct": vbusct,
                "avg": avg,
            }
        }
    
    def ina226_config_set(self,currentLSB=3,vshct=3,vbusct=3,avg=5):
        """
        设置INA226配置
        Set INA226 configuration
        currentLSB: 1-10, unit: 0.1mA
        vshct: 0-7
        vbusct: 0-7
        avg: 0-7
        """
        if currentLSB < 1 or currentLSB > 10:
            raise ValueError("currentLSB must be between 1 and 10")
        if vshct < 0 or vshct > 7:
            raise ValueError("vshct must be between 0 and 7")
        if vbusct < 0 or vbusct > 7:
            raise ValueError("vbusct must be between 0 and 7")
        if avg < 0 or avg > 7:
            raise ValueError("avg must be between 0 and 7")
        s = bytearray()
        s.append(Command.CMD_SYSTEM_INA226_CONFIG)
        data = struct.pack("<BH", currentLSB, (0 << 0) | (vshct << 3) | (vbusct << 6) | (avg << 9) | (4 << 12) | 0)
        s += data

        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self.send_command(s, True)

    ina226_vbusct_vshct_str = [
        "140uS",
        "204uS",
        "332uS",
        "588uS",
        "1.1ms",
        "2.116ms",
        "4.156ms",
        "8.244ms",
    ]

    ina226_avg_value = [
        1, 4, 16, 64, 128, 256, 512, 1024
    ]

    def ina226_vbusct_vshct_str_get(self,value):
        return self.ina226_vbusct_vshct_str[value]
    
    def ina226_vbusct_vshct_value_get(self,vbusct_str):
        return self.ina226_vbusct_vshct_str.index(vbusct_str)
    
    def ina226_avg_get(self,avg):
        return self.ina226_avg_value[avg]
    
    def ina226_avg_value_get(self,avg_str):
        return self.ina226_avg_value.index(avg_str)
    
    def ina226_currentLSB_str_get(self,value):
        return f"{value*0.1:.1f}mA"
    
    def ina226_currentLSB_value_get(self, currentLSB_str):
        num_str = currentLSB_str.replace("mA", "")
        value = float(num_str)
        return int(value / 0.1)

    def lcd_panel_get(self):
        s = bytearray()
        s.append(Command.CMD_SYSTEM_LCD_PANEL_TYPE | Command.CMD_READ)
        
        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self._read_ok_event.clear()
        self.send_command(s)
        if not self._read_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for response")
            return None
        return int(self._read_result[0])
    
    def output_data(self):
        """
        获取当前输出数据
        Get current output data
        unit: mV, 0.1mA, mW
        """
        s = bytearray()
        s.append(Command.CMD_OUTPUT_DATA | Command.CMD_READ)
        
        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self._read_ok_event.clear()
        self.send_command(s)
        if not self._read_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for response")
            return None
        
        voltage,current,power = struct.unpack("<IiI", self._read_result)
        return voltage,current,power
    
    def output_data_max(self):
        """
        获取最大输出数据
        Get maximum output data
        unit: mV, 0.1mA, mW
        """
        s = bytearray()
        s.append(Command.CMD_OUTPUT_DATA_MAX | Command.CMD_READ)
        
        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self._read_ok_event.clear()
        self.send_command(s)
        if not self._read_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for response")
            return None
        
        voltage,current,power = struct.unpack("<IiI", self._read_result)
        return voltage,current,power
    
    def maH_mwH(self):
        s = bytearray()
        s.append(Command.CMD_MAH_MWH | Command.CMD_READ)
        
        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self._read_ok_event.clear()
        self.send_command(s)
        if not self._read_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for response")
            return None
        
        maH,mwH = struct.unpack("<II", self._read_result)
        return maH,mwH
    
    def uptime(self):
        """
        获取运行时间
        Get uptime
        unit: seconds
        """
        s = bytearray()
        s.append(Command.CMD_UPTIME | Command.CMD_READ)
        
        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self._read_ok_event.clear()
        self.send_command(s)
        if not self._read_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for response")
            return None
        uptime = struct.unpack("<I", self._read_result)[0]
        return uptime
    
    def output_data_max_reset(self):
        s = bytearray()
        s.append(Command.CMD_OUTPUT_DATA_MAX_RESET)
        
        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self.send_command(s, True)

    def input_type_get(self):
        s = bytearray()
        s.append(Command.CMD_INPUT_TYPE | Command.CMD_READ)
        
        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self._read_ok_event.clear()
        self.send_command(s)
        if not self._read_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for response")
            return None
        input_type = int(self._read_result[0])
        return input_type

    def pd_pdo_fix_get(self):
        """
        获取PDO固定数据
        Get PDO fixed data
        
        Returns:
            dict: 包含count和fixdata列表的数据结构
            Example:
            {
                "count": 2,
                "fixeddata": [
                    {"voltage": 5000, "current": 3000},
                    {"voltage": 9000, "current": 2000}
                ]
            }
        unit: mV, mA
        """
        s = bytearray()
        s.append(Command.CMD_PD_PDO_FIX | Command.CMD_READ)
        
        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self._read_ok_event.clear()
        self.send_command(s)
        if not self._read_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for response")
            return None
        
        # 确保_read_result有足够的数据
        if len(self._read_result) < 1:
            print("PDO数据格式错误: 数据长度不足 PDO data format error: insufficient data length")
            return None
        
        # 解析数据
        result = {"count": 0, "fixeddata": []}
        
        result["count"] = len(self._read_result)//4

        # 解析fixdata数组
        for i in range(result["count"]):
            # 每个fixdata元素占用4字节
            # voltage: 2字节，小端
            # current: 2字节，小端
            offset = i*4
            
            # 解析电压 (mV)
            voltage = struct.unpack("<H", self._read_result[offset:offset+2])[0]
            
            # 解析电流 (mA)
            current = struct.unpack("<H", self._read_result[offset+2:offset+4])[0]
            
            result["fixeddata"].append({
                "voltage": voltage,
                "current": current
            })
        
        return result
    
    def pd_pdo_pps_get(self):
        """
        获取PDO PPS数据
        Get PDO PPS data
        
        Returns:
            dict: 包含count和ppsdata列表的数据结构
            Example:
            {
                "count": 2,
                "ppsdata": [
                    {"minvoltage": 5000, "maxvoltage": 9000, "maxcurrent": 3000},
                    {"minvoltage": 9000, "maxvoltage": 15000, "maxcurrent": 2000}
                ]
            }
        unit: mV, mA
        """
        s = bytearray()
        s.append(Command.CMD_PD_PDO_PPS | Command.CMD_READ)

        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self._read_ok_event.clear()
        self.send_command(s)
        if not self._read_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for response")
            return None
        
        # 确保_read_result有足够的数据
        if len(self._read_result) < 1:
            print("PDO数据格式错误: 数据长度不足 PDO data format error: insufficient data length")
            return None
        
        # 解析数据
        result = {"count": 0, "ppsdata": []}
        
        result["count"] = len(self._read_result)//6

        # 解析ppsdata数组
        for i in range(result["count"]):
            # 每个ppsdata元素占用4字节
            # minvoltage: 2字节，小端
            # maxvoltage: 2字节，小端
            # maxcurrent: 2字节，小端
            offset = i*6
            
            # 解析电压 (mV)
            minvoltage = struct.unpack("<H", self._read_result[offset:offset+2])[0]
            maxvoltage = struct.unpack("<H", self._read_result[offset+2:offset+4])[0]
            
            # 解析电流 (mA)
            maxcurrent = struct.unpack("<H", self._read_result[offset+4:offset+6])[0]
            
            result["ppsdata"].append({
                "minvoltage": minvoltage,
                "maxvoltage": maxvoltage,
                "maxcurrent": maxcurrent
            })
        
        return result
    
    def pd_pdo_avs_get(self):
        """
        获取PDO AVS数据
        Get PDO AVS data
        
        Returns:
            dict: 包含count和avsdata列表的数据结构
            Example:
            {
                "count": 2,
                "avsdata": [
                    {"minvoltage": 15000, "maxvoltage": 28000, "maxpower": 240},
                    {"minvoltage": 15000, "maxvoltage": 36000, "maxpower": 240}
                ]
            }
        unit: mV, W
        """
        s = bytearray()
        s.append(Command.CMD_PD_PDO_AVS | Command.CMD_READ)

        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self._read_ok_event.clear()
        self.send_command(s)
        if not self._read_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for response")
            return None
        
        # 确保_read_result有足够的数据
        if len(self._read_result) < 1:
            print("PDO数据格式错误: 数据长度不足 PDO data format error: insufficient data length")
            return None
        
        # 解析数据
        result = {"count": 0, "avsdata": []}
        
        result["count"] = len(self._read_result)//6

        # 解析ppsdata数组
        for i in range(result["count"]):
            # 每个avsdata元素占用4字节
            # minvoltage: 2字节，小端 2byte little endian
            # maxvoltage: 2字节，小端 2byte little endian
            # maxpower: 2字节，小端 2byte little endian
            offset = i*6
            
            # 解析电压 (mV)
            minvoltage = struct.unpack("<H", self._read_result[offset:offset+2])[0]
            maxvoltage = struct.unpack("<H", self._read_result[offset+2:offset+4])[0]
            
            # 解析功率 (W)
            maxpower = struct.unpack("<H", self._read_result[offset+4:offset+6])[0]
            
            result["avsdata"].append({
                "minvoltage": minvoltage,
                "maxvoltage": maxvoltage,
                "maxpower": maxpower
            })
        
        return result

    def pd_pdo_num(self):
        """
        获取PDO数量
        Get PDO number
        """
        s = bytearray()
        s.append(Command.CMD_PD_PDO_NUM | Command.CMD_READ)

        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self._read_ok_event.clear()
        self.send_command(s)
        if not self._read_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for response")
            return None
        
        # 确保_read_result有足够的数据
        if len(self._read_result) != 3:
            print("PDO数据格式错误: 数据长度不足 PDO data format error: insufficient data length")
            return None
        
        fixed_num = int(self._read_result[0])
        pps_num = int(self._read_result[1])
        avs_num = int(self._read_result[2])
        
        return fixed_num, pps_num, avs_num
    
    def pd_pdo_now(self):
        """
        获取当前PDO数据
        Get current PDO data
        id: 1-11
        voltage unit: mV
        """
        s = bytearray()
        s.append(Command.CMD_PD_PDO | Command.CMD_READ)

        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self._read_ok_event.clear()
        self.send_command(s)
        if not self._read_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for response")
            return None
        
        # 确保_read_result有足够的数据
        if len(self._read_result) != 3:
            print("PDO数据格式错误: 数据长度不足 PDO data format error: insufficient data length")
            return None
        

        id = int(self._read_result[0])
        voltage = struct.unpack("<H", self._read_result[1:3])[0]
        
        return id, voltage

    def pd_pdo_now2(self):
        """
        获取当前PDO数据
        Get current PDO data
        id: 1-11
        voltage unit: mV
        current unit: mA
        """
        s = bytearray()
        s.append(Command.CMD_PD_PDO2 | Command.CMD_READ)

        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)

        self._read_ok_event.clear()
        self.send_command(s)
        if not self._read_ok_event.wait(timeout=1.0):  # 等待1秒超时
            print("等待响应超时 Timeout waiting for response")
            return None
        
        # 确保_read_result有足够的数据
        if len(self._read_result) != 5:
            print("PDO数据格式错误: 数据长度不足 PDO data format error: insufficient data length")
            return None

        id = int(self._read_result[0])
        voltage, current = struct.unpack("<HH", self._read_result[1:5])
        
        return id, voltage, current
    
    def pd_pdo_set(self, id, voltage):
        """
        设置PDO数据
        Set PDO data
        id: 1-11
        voltage unit: mV
        """
        s = bytearray()
        s.append(Command.CMD_PD_PDO)
        s.append(id)
        s.append(voltage & 0xFF)
        s.append(voltage >> 8)
        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)
        
        self.send_command(s, True)
    
    def pd_pdo_set2(self, id, voltage, current):
        """
        设置PDO数据
        Set PDO data
        id: 1-11
        voltage unit: mV
        current unit: mA
        """
        s = bytearray()
        s.append(Command.CMD_PD_PDO2)
        s.append(id)
        s.append(voltage & 0xFF)
        s.append(voltage >> 8)
        s.append(current & 0xFF)
        s.append(current >> 8)
        # Add CRC if enabled
        if self._use_crc8:
            crc = self.calculate_crc8(s)
            s.append(crc)
        else:
            s.append(Command.CMD_END)
        
        self.send_command(s, True)

    def close(self):
        """
        关闭串口连接并停止读取线程和发送线程
        Close the serial port connection and stop the reading thread and the sending thread
        """
        self._stop_event.set()
        if self._read_thread.is_alive():
            self._read_thread.join()
        if self._send_thread.is_alive():
            self._send_thread.join()
        if self.ser.is_open:
            self.ser.close()
    
    def is_open(self):
        return self.ser.is_open
    
    @staticmethod
    def calculate_crc8(data):
        """
        Calculate CRC-8 checksum using polynomial 0x31 (x^8 + x^5 + x^4 + 1)
        with initial value 0xFF and bit-by-bit processing algorithm
        
        Args:
            data: Bytes or bytearray to calculate CRC for
            
        Returns:
            CRC-8 checksum as an integer
        """
        crc = 0xFF  # Initial value
        polynomial = 0x31  # x^8 + x^5 + x^4 + 1
        
        for byte in data:
            crc ^= byte  # XOR with the current byte
            for _ in range(8):  # Process each bit
                if crc & 0x80:  # If the most significant bit is set
                    crc = (crc << 1) ^ polynomial
                else:
                    crc <<= 1
                crc &= 0xFF  # Ensure CRC remains 8-bit
        
        return crc

def parse_version(ver_str: str):
    # 1. 去除v前缀
    s = ver_str.lstrip("vV")
    # 2. 切掉下划线后缀
    s = s.split("_")[0]
    # 3. 按点分割，转整数列表
    parts = []
    for p in s.split("."):
        if p.isdigit():
            parts.append(int(p))
        else:
            return None
    return parts

def ver_gt(ver_a: str, ver_b: str) -> bool:
    """判断Compare ver_a > ver_b"""
    a = parse_version(ver_a)
    b = parse_version(ver_b)
    if a is None or b is None:
        raise ValueError("版本号格式错误 Version number format error: invalid version number")
    # 补齐长度，短版本后面补0
    max_len = max(len(a), len(b))
    a += [0] * (max_len - len(a))
    b += [0] * (max_len - len(b))
    return a > b

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        port = sys.argv[1]
        if len(sys.argv) > 2 and sys.argv[2] == "crc8":
            use_crc8 = True
        else:
            use_crc8 = False
    else:
        print("请输入串口端口号 Please enter the serial port number")
        print("可选参数 Optional parameter: crc8")
        print("示例: python com_PowerMonitorMiniV1.py COM19 crc8")
        exit(1)
        
    print(f"use crc8 使用CRC8: {use_crc8}")
    c = com_PowerMonitorMiniV1(port, baudrate=9600, use_crc8=use_crc8)

    print("who_am_i:",c.who_am_i())
    version = c.system_version()
    print("system_version:",version)
    print("system_serial_num:",c.system_serial_num())
    print("Current_rshunt:",c.current_rshunt_get(), "ohm")
    print("LCD_panel:",LCD_PANEL_TYPE.get(c.lcd_panel_get(), "Unknown"))
    
    voltage,current,power = c.output_data()
    print("Voltage:",voltage/1000,"V")
    print("Current:",current/10000,"A")
    print("Power:",power/1000,"W")

    voltage,current,power = c.output_data_max()
    print("Voltage_max:",voltage/1000,"V")
    print("Current_max:",current/10000,"A")
    print("Power_max:",power/1000,"W")

    maH,mwH = c.maH_mwH()
    print("maH:",maH,"mAh")
    print("mwH:",mwH,"mWh")
    print("uptime:",c.uptime(),"s")

    input_type = c.input_type_get()
    print("Input_type:",INPUT_TYPE.get(input_type, "Unknown"))

    if INPUT_TYPE.get(input_type) == "PD":
        fixed_num, pps_num, avs_num = c.pd_pdo_num()
        print("fixed_num:",fixed_num,"pps_num:",pps_num,"avs_num:",avs_num)

        if fixed_num:
            pd_pdo_fix = c.pd_pdo_fix_get()
            print("pd_pdo_fix:",pd_pdo_fix)

        if pps_num:
            pd_pdo_pps = c.pd_pdo_pps_get()
            print("pd_pdo_pps:",pd_pdo_pps)

        if avs_num:
            pd_pdo_avs = c.pd_pdo_avs_get()
            print("pd_pdo_avs:",pd_pdo_avs)
        

        if ver_gt(version, "v1.0.0.3"):
            print("pd_pdo_set2")
            pdo_id,pdo_voltage,current = c.pd_pdo_now2()
            print("pdo now2: id:",pdo_id,"voltage:",pdo_voltage/1000,"V","current:",current/1000,"A")
            c.pd_pdo_set2(2, pd_pdo_fix['fixeddata'][1]['voltage'],pd_pdo_fix['fixeddata'][1]['current'])
        else:
            pdo_id,pdo_voltage = c.pd_pdo_now()
            print("pdo now: id:",pdo_id,"voltage:",pdo_voltage/1000,"V")
            c.pd_pdo_set(2, pd_pdo_fix['fixeddata'][1]['voltage'])

        print("pd_pdo_set: id:",2,"voltage:",pd_pdo_fix['fixeddata'][1]['voltage']/1000,"V")
        
        time.sleep(0.1)

        pdo_id,pdo_voltage = c.pd_pdo_now()
        print("pdo now: id:",pdo_id,"voltage:",pdo_voltage/1000,"V")

    current_offset0,current_offset1,current_zero = c.current_offset_get()
    print("offset0 display:",current_offset0["display"]/10000,"A","actual:",current_offset0["actual"]/10000,"A")
    print("offset1 display:",current_offset1["display"]/10000,"A","actual:",current_offset1["actual"]/10000,"A")
    print("zero :",current_zero/10000,"A")
    
    # c.current_offset_set(5110,5073,10155,10080,0)

    ina226_config = c.ina226_config_get()
    print("ina226_config:",ina226_config)
    print("ina226_currentLSB_str:",c.ina226_currentLSB_str_get(ina226_config["currentLSB"]))
    print("ina226_reg_vshct:",c.ina226_vbusct_vshct_str_get(ina226_config["reg"]["vshct"]))
    print("ina226_reg_vbusct:",c.ina226_vbusct_vshct_str_get(ina226_config["reg"]["vbusct"]))
    print("ina226_reg_avg:",c.ina226_avg_get(ina226_config["reg"]["avg"]))

    # c.ina226_config_set(currentLSB=2,vbusct=2,avg=4,vshct=4)

    #c.output_data_max_reset()
    
    # c.current_rshunt_set(5)
    # time.sleep(0.5)
    # print("Current_rshunt:",c.current_rshunt_get(), "ohm")

    # c.factory_reset()
    
    time.sleep(1)
    c.close()
    time.sleep(1)