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
    CMD_SYSTEM_RESET = 0x40
    CMD_SYSTEM_VERSION = 0x42
    CMD_SYSTEM_SERIAL_NUM = 0x43
    CMD_SYSTEM_FACTORY_RESET = 0x45
    CMD_SYSTEM_LCD_PANEL_TYPE = 0x46
    CMD_SYSTEM_CURRENT_RSHUNT = 0x47
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
            Command.CMD_SYSTEM_LCD_PANEL_TYPE: 3,
            Command.CMD_SYSTEM_CURRENT_RSHUNT: 3,
            Command.CMD_SYSTEM_VERSION: 0,
            Command.CMD_SYSTEM_SERIAL_NUM: 0,
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
                            Command.CMD_PD_PDO_PPS
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
    
    def send_command(self, cmd):
        """
        发送指令到设备
        Send a command to the device
        """
        try:
            self._send_queue.put(cmd, timeout=0.5)
        except Full:
            print("发送指令队列已满，指令丢弃 Command queue is full, command discarded")

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

        self._write_ok_event.clear()
        self.send_command(s)

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

        self._write_ok_event.clear()
        self.send_command(s)

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
        
        voltage,current,power = struct.unpack("IiI", self._read_result)
        return voltage,current,power
    
    def output_data_max(self):
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
        
        voltage,current,power = struct.unpack("IiI", self._read_result)
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
        
        maH,mwH = struct.unpack("II", self._read_result)
        return maH,mwH
    
    def uptime(self):
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
        uptime = struct.unpack("I", self._read_result)[0]
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

        self._write_ok_event.clear()
        self.send_command(s)

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
                "fixdata": [
                    {"voltage": 5000, "current": 3000},
                    {"voltage": 9000, "current": 2000}
                ]
            }
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
        result = {"count": 0, "fixdata": []}
        
        result["count"] = len(self._read_result)//4

        # 解析fixdata数组
        for i in range(result["count"]):
            # 每个fixdata元素占用4字节
            # voltage: 2字节，小端
            # current: 2字节，小端
            offset = i*4
            
            # 解析电压 (mV)
            voltage = struct.unpack("H", self._read_result[offset:offset+2])[0]
            
            # 解析电流 (mA)
            current = struct.unpack("H", self._read_result[offset+2:offset+4])[0]
            
            result["fixdata"].append({
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
                    {"voltage": 5000, "current": 3000},
                    {"voltage": 9000, "current": 2000}
                ]
            }
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
            minvoltage = struct.unpack("H", self._read_result[offset:offset+2])[0]
            maxvoltage = struct.unpack("H", self._read_result[offset+2:offset+4])[0]
            
            # 解析电流 (mA)
            maxcurrent = struct.unpack("H", self._read_result[offset+4:offset+6])[0]
            
            result["ppsdata"].append({
                "minvoltage": minvoltage,
                "maxvoltage": maxvoltage,
                "maxcurrent": maxcurrent
            })
        
        return result
    
    def pd_pdo_now(self):
        """
        获取当前PDO数据
        Get current PDO data
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
        voltage = struct.unpack("H", self._read_result[1:3])[0]
        
        return id, voltage
    
    def pd_pdo_set(self, id, voltage):
        """
        设置PDO数据
        Set PDO data
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
        
        self._read_ok_event.clear()
        self.send_command(s)

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
    print("system_version:",c.system_version())
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
        pd_pdo_fix = c.pd_pdo_fix_get()
        print("pd_pdo_fix:",pd_pdo_fix)

        pd_pdo_pps = c.pd_pdo_pps_get()
        print("pd_pdo_pps:",pd_pdo_pps)

        pdo_id,pdo_voltage = c.pd_pdo_now()
        print("pdo now: id:",pdo_id,"voltage:",pdo_voltage/1000,"V")

        c.pd_pdo_set(2, pd_pdo_fix['fixdata'][1]['voltage'])
        print("pd_pdo_set: id:",2,"voltage:",pd_pdo_fix['fixdata'][1]['voltage']/1000,"V")
        
        time.sleep(0.1)

        pdo_id,pdo_voltage = c.pd_pdo_now()
        print("pdo now: id:",pdo_id,"voltage:",pdo_voltage/1000,"V")

    #c.output_data_max_reset()
    
    # c.current_rshunt_set(5)
    # time.sleep(0.5)
    # print("Current_rshunt:",c.current_rshunt_get(), "ohm")

    # c.factory_reset()
    
    c.close()
    time.sleep(1)