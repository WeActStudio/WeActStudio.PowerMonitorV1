import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

import serial
import serial.tools.list_ports
import threading
import traceback
import time
import queue

from com_PowerMonitorMiniV1 import com_PowerMonitorMiniV1, INPUT_TYPE

import sys
import os

def resource_path(relative_path):
    """获取资源绝对路径，打包后也能找到"""
    try:
        # PyInstaller 打包后会创建这个临时文件夹
        base_path = sys._MEIPASS
    except Exception:
        # 开发时直接用当前路径
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class PowerMonitorMiniV1_GUI:
    def __init__(self):
        self.comlist = []
        self.ser = serial.Serial()
        self.thread_status = 0
        self.com_task_step = 0

        self.queue_device_send = queue.Queue()
        self.queue_device_recv = queue.Queue()

        self.maintk = tk.Tk()
        self.maintk.title("WeAct Studio Power Monitor Mini V1 GUI")
        self.maintk.iconbitmap(resource_path("logo.ico"))
        self.maintk.geometry("800x770")
        self.maintk.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.frame_base = ttk.Frame(self.maintk)
        self.frame_base.grid(row=0, column=0, columnspan=3, sticky=tk.N + tk.W + tk.E)

        self.frame_com = ttk.Frame(self.frame_base)
        self.frame_com.grid(row=0, column=0, sticky=tk.N + tk.W + tk.E)

        # 打开串口按钮
        self.comopenflagstr = tk.StringVar()
        self.comopenflagstr.set("port is unavailable")
        self.comlabelname = tk.Label(self.frame_com, textvariable=self.comopenflagstr)
        self.comopenbtnstr = tk.StringVar()
        self.comopenbtnstr.set("Open")
        self.btnopencom = ttk.Button(
            self.frame_com, textvariable=self.comopenbtnstr, command=self.btn_com_open
        )

        # 串口刷新
        self.btncom_reflash = ttk.Button(
            self.frame_com, text="Refresh", command=self.btn_com_reflash
        )

        # 端口号
        self.labelport = tk.Label(self.frame_com, text="Port:")
        self.comportvar = tk.StringVar()
        self.comportCombobox = ttk.Combobox(
            self.frame_com, textvariable=self.comportvar
        )
        # 获取存在的端口号
        self.comlist = self.com_port_reflash()
        self.comportCombobox["value"] = tuple(self.comlist[1])
        if len(self.comlist[0]) == 0:
            self.btnopencom["state"] = "disabled"
            self.comportvar.set("")
        else:
            self.btnopencom["state"] = "normal"
            self.comportCombobox.current(0)
        self.comportCombobox.bind("<<ComboboxSelected>>", self.comportCombobox_selected)
        self.comportCombobox["state"] = "readonly"

        # 波特率
        self.labelbps = tk.Label(self.frame_com, text="Baud Rate:")
        self.combpsvar = tk.StringVar()
        self.combpscombobox = ttk.Combobox(self.frame_com, textvariable=self.combpsvar)
        self.combpscombobox["value"] = [
            "9600",
            "19200",
            "38400",
            "57600",
            "115200",
            "230400",
            "460800",
        ]
        self.combpscombobox.current(0)

        self.com_with_crc_check = tk.BooleanVar()
        self.com_with_crc_checkbutton = ttk.Checkbutton(
            self.frame_com, text="Enable CRC", variable=self.com_with_crc_check
        )
        self.comportCombobox_selected()

        self.comlabelname.grid(row=0, column=0)
        self.btncom_reflash.grid(row=0, column=1)
        self.btnopencom.grid(row=0, column=2)
        self.labelport.grid(row=1, column=0)
        self.comportCombobox.grid(
            row=1, column=1, columnspan=2, padx=1, pady=1, sticky=tk.E + tk.W
        )
        self.labelbps.grid(row=2, column=0, padx=1, pady=1, sticky=tk.W)
        self.combpscombobox.grid(
            row=2, column=1, columnspan=2, padx=1, pady=1, sticky=tk.E + tk.W
        )
        self.com_with_crc_checkbutton.grid(
            row=3, column=0, columnspan=2, padx=1, pady=1, sticky=tk.W
        )

        sep = ttk.Separator(self.frame_com, orient="horizontal")
        sep.grid(row=4, column=0, columnspan=3, padx=1, pady=1, sticky=tk.E + tk.W)

        self.frame_device_info = ttk.Frame(self.frame_base)
        self.frame_device_info.grid(row=0, column=1, sticky=tk.N + tk.W)

        self.label_device_info = tk.Label(
            self.frame_device_info, text="Device Name:", anchor=tk.W
        )
        self.label_device_info.grid(row=0, column=0, sticky=tk.W)
        self.label_device_info_value = tk.Label(
            self.frame_device_info, text="", width=40, anchor=tk.W
        )
        self.label_device_info_value.grid(row=0, column=1, sticky=tk.W)

        self.label_device_sn = tk.Label(
            self.frame_device_info, text="Serial Number:", anchor=tk.W
        )
        self.label_device_sn.grid(row=1, column=0, sticky=tk.W)
        self.label_device_sn_value = tk.Label(self.frame_device_info, text="")
        self.label_device_sn_value.grid(row=1, column=1, sticky=tk.W)

        self.label_device_soft_version = tk.Label(
            self.frame_device_info, text="Software Version:", anchor=tk.W
        )
        self.label_device_soft_version.grid(row=2, column=0, sticky=tk.W)
        self.label_device_soft_version_value = tk.Label(self.frame_device_info, text="")
        self.label_device_soft_version_value.grid(row=2, column=1, sticky=tk.W)

        self.label_device_rshunt = tk.Label(
            self.frame_device_info, text="Sample Resistance:", anchor=tk.W
        )
        self.label_device_rshunt.grid(row=3, column=0, sticky=tk.W)
        self.label_device_rshunt_value = tk.Label(self.frame_device_info, text="")
        self.label_device_rshunt_value.grid(row=3, column=1, sticky=tk.W)

        self.label_device_input_type = tk.Label(
            self.frame_device_info, text="Input Type:", anchor=tk.W
        )
        self.label_device_input_type.grid(row=4, column=0, sticky=tk.W)
        self.label_device_input_type_value = tk.Label(self.frame_device_info, text="")
        self.label_device_input_type_value.grid(row=4, column=1, sticky=tk.W)

        self.frame_ouput_display = ttk.Frame(self.maintk)
        self.frame_ouput_display.grid(row=1, column=0, rowspan=3, sticky=tk.N + tk.W)

        self.frame_output_data = ttk.Frame(self.frame_ouput_display)
        self.frame_output_data.grid(
            row=1, column=0, rowspan=2, sticky=tk.N + tk.W + tk.E, padx=5
        )
        self.label_output_data = tk.Label(
            self.frame_output_data, text="Output Data", font=("Arial", 12, "bold")
        )
        self.label_output_data.grid(row=0, column=0, sticky=tk.W)
        self.label_output_voltage = tk.Label(
            self.frame_output_data, text="Voltage", anchor=tk.W
        )
        self.label_output_voltage.grid(row=1, column=0, sticky=tk.W)
        self.label_output_voltage_value = tk.Label(
            self.frame_output_data, text="", font=("Arial", 24)
        )
        self.label_output_voltage_value.grid(row=2, column=0, sticky=tk.W)

        self.label_output_current = tk.Label(
            self.frame_output_data, text="Current", anchor=tk.W
        )
        self.label_output_current.grid(row=3, column=0, sticky=tk.W)
        self.label_output_current_value = tk.Label(
            self.frame_output_data, text="", font=("Arial", 24)
        )
        self.label_output_current_value.grid(row=4, column=0, sticky=tk.W)

        self.label_output_power = tk.Label(
            self.frame_output_data, text="Power", anchor=tk.W
        )
        self.label_output_power.grid(row=5, column=0, sticky=tk.W)
        self.label_output_power_value = tk.Label(
            self.frame_output_data, text="", font=("Arial", 24)
        )
        self.label_output_power_value.grid(row=6, column=0, sticky=tk.W)

        sep = ttk.Separator(self.frame_output_data, orient="horizontal")
        sep.grid(row=7, column=0, padx=1, pady=1, sticky=tk.E + tk.W)

        self.frame_output_data_max = ttk.Frame(self.frame_ouput_display)
        self.frame_output_data_max.grid(
            row=3, column=0, rowspan=2, sticky=tk.N + tk.W + tk.E, padx=5
        )
        self.label_output_data_max = tk.Label(
            self.frame_output_data_max,
            text="Max Output Data",
            font=("Arial", 12, "bold"),
        )
        self.label_output_data_max.grid(row=0, column=0, sticky=tk.W)
        self.btn_output_data_max_reset = ttk.Button(
            self.frame_output_data_max,
            text="Reset",
            command=self.btn_output_data_max_reset,
        )
        self.btn_output_data_max_reset.grid(row=0, column=1, sticky=tk.W)
        self.label_output_data_max_voltage = tk.Label(
            self.frame_output_data_max, text="Max Voltage", anchor=tk.W
        )
        self.label_output_data_max_voltage.grid(
            row=1, column=0, columnspan=2, sticky=tk.W
        )
        self.label_output_data_max_voltage_value = tk.Label(
            self.frame_output_data_max, text="", font=("Arial", 24), anchor=tk.W
        )
        self.label_output_data_max_voltage_value.grid(
            row=2, column=0, columnspan=2, sticky=tk.W
        )
        self.label_output_data_max_current = tk.Label(
            self.frame_output_data_max, text="Max Current", anchor=tk.W
        )
        self.label_output_data_max_current.grid(
            row=3, column=0, columnspan=2, sticky=tk.W
        )
        self.label_output_data_max_current_value = tk.Label(
            self.frame_output_data_max, text="", font=("Arial", 24), anchor=tk.W
        )
        self.label_output_data_max_current_value.grid(
            row=4, column=0, columnspan=2, sticky=tk.W
        )
        self.label_output_data_max_power = tk.Label(
            self.frame_output_data_max, text="Max Power", anchor=tk.W
        )
        self.label_output_data_max_power.grid(
            row=5, column=0, columnspan=2, sticky=tk.W
        )
        self.label_output_data_max_power_value = tk.Label(
            self.frame_output_data_max, text="", font=("Arial", 24), anchor=tk.W
        )
        self.label_output_data_max_power_value.grid(
            row=6, column=0, columnspan=2, sticky=tk.W
        )

        self.frame_mah_mwh_uptime = ttk.Frame(self.frame_ouput_display)
        self.frame_mah_mwh_uptime.grid(
            row=5, column=0, rowspan=2, sticky=tk.N + tk.W + tk.E, padx=5
        )
        self.label_mah_mwh_uptime = tk.Label(
            self.frame_mah_mwh_uptime, text="Energy Data", font=("Arial", 12, "bold")
        )
        self.label_mah_mwh_uptime.grid(row=0, column=0, sticky=tk.W)
        self.label_mah_value = tk.Label(
            self.frame_mah_mwh_uptime, text="x mAh", font=("Arial", 24)
        )
        self.label_mah_value.grid(row=1, column=0, sticky=tk.W)
        self.label_mwh_value = tk.Label(
            self.frame_mah_mwh_uptime, text="x mWh", font=("Arial", 24)
        )
        self.label_mwh_value.grid(row=2, column=0, sticky=tk.W)
        sep = ttk.Separator(self.frame_mah_mwh_uptime, orient="horizontal")
        sep.grid(row=3, column=0, padx=1, pady=1, sticky=tk.E + tk.W)
        self.label_uptime = tk.Label(
            self.frame_mah_mwh_uptime, text="Uptime", font=("Arial", 12, "bold")
        )
        self.label_uptime.grid(row=4, column=0, sticky=tk.W)
        self.label_uptime_value = tk.Label(
            self.frame_mah_mwh_uptime, text="x s", font=("Arial", 18)
        )
        self.label_uptime_value.grid(row=5, column=0, sticky=tk.W)

        self.frame_config = ttk.Frame(self.maintk)
        self.frame_config.grid(row=1, column=1, sticky=tk.N + tk.W + tk.E, padx=5)
        self.frame_pd = ttk.Frame(self.frame_config)
        self.frame_pd.grid(
            row=1, column=1, columnspan=2, sticky=tk.N + tk.W + tk.E, padx=5
        )
        self.label_pd = tk.Label(
            self.frame_pd, text="PD Protocol Config", font=("Arial", 12, "bold")
        )
        self.label_pd.grid(row=0, column=0, sticky=tk.W)
        self.tree_pd = ttk.Treeview(
            self.frame_pd,
            columns=(
                "ID",
                "Type",
                "Min Voltage",
                "Max Voltage",
                "Max Current",
                "Max Power",
            ),
            show="headings",
            height=10,
        )
        self.tree_pd.heading("ID", text="ID")
        self.tree_pd.heading("Type", text="Type")
        self.tree_pd.heading("Max Voltage", text="Max Voltage(mV)")
        self.tree_pd.heading("Min Voltage", text="Min Voltage(mV)")
        self.tree_pd.heading("Max Current", text="Max Current(mA)")
        self.tree_pd.heading("Max Power", text="Max Power(W)")
        self.tree_pd.column("ID", width=40, anchor="center", stretch=False)
        self.tree_pd.column("Type", width=60, anchor="center", stretch=False)
        self.tree_pd.column("Max Voltage", width=110, anchor="center", stretch=False)
        self.tree_pd.column("Min Voltage", width=110, anchor="center", stretch=False)
        self.tree_pd.column("Max Current", width=110, anchor="center", stretch=False)
        self.tree_pd.column("Max Power", width=100, anchor="center", stretch=False)
        self.tree_pd.grid(row=1, column=0, columnspan=8, sticky=tk.N + tk.W + tk.E)
        self.label_pd_id_set = tk.Label(self.frame_pd, text="ID Set")
        self.label_pd_id_set.grid(row=2, column=0, sticky=tk.W)
        self.combobox_pd_id_set = ttk.Combobox(
            self.frame_pd,
            values=["0", "1", "2", "3", "4", "5", "6", "7"],
            state="readonly",
            width=10,
        )
        self.combobox_pd_id_set.grid(row=3, column=0, sticky=tk.W, padx=1)
        self.combobox_pd_id_set.bind(
            "<<ComboboxSelected>>", self.combobox_pd_id_set_click
        )
        self.label_pd_voltage_set = tk.Label(self.frame_pd, text="Voltage Set(mV)")
        self.label_pd_voltage_set.grid(row=2, column=1, sticky=tk.W)
        self.combobox_pd_voltage_set = ttk.Combobox(
            self.frame_pd,
            values="",
            width=10,
            validate="key",
            validatecommand=(self.maintk.register(self.only_digit), "%S"),
        )
        self.combobox_pd_voltage_set.grid(row=3, column=1, sticky=tk.W, padx=1)
        self.btn_pd_refresh = ttk.Button(
            self.frame_pd, text="Refresh", command=self.btn_pd_refresh_click
        )
        self.btn_pd_refresh.grid(row=3, column=2, sticky=tk.W, padx=1)
        self.btn_pd_apply = ttk.Button(
            self.frame_pd, text="Apply", command=self.btn_pd_apply_click
        )
        self.btn_pd_apply.grid(row=3, column=3, sticky=tk.W, padx=1)
        self.combobox_pd_id_set["state"] = "disabled"
        self.combobox_pd_voltage_set["state"] = "disabled"
        self.btn_pd_refresh["state"] = "disabled"
        self.btn_pd_apply["state"] = "disabled"

        self.frame_ina226_config = ttk.Frame(self.frame_config)
        self.frame_ina226_config.grid(
            row=2, column=1, columnspan=2, sticky=tk.N + tk.W + tk.E, padx=5
        )
        self.label_ina226_config = tk.Label(
            self.frame_ina226_config, text="INA226 Config", font=("Arial", 12, "bold")
        )
        self.label_ina226_config.grid(row=0, column=0, columnspan=3, sticky=tk.W)
        self.label_ina226_vbusct = tk.Label(self.frame_ina226_config, text="vbusct")
        self.label_ina226_vbusct.grid(row=1, column=1, sticky=tk.W)
        self.label_ina226_vshct = tk.Label(self.frame_ina226_config, text="vshct")
        self.label_ina226_vshct.grid(row=1, column=0, sticky=tk.W)
        self.label_ina226_avg = tk.Label(self.frame_ina226_config, text="avg")
        self.label_ina226_avg.grid(row=1, column=2, sticky=tk.W)
        self.label_ina226_current_lsb = tk.Label(
            self.frame_ina226_config, text="current_lsb"
        )
        self.label_ina226_current_lsb.grid(row=1, column=3, sticky=tk.W)
        self.combobox_ina226_vbusct = ttk.Combobox(
            self.frame_ina226_config,
            values=com_PowerMonitorMiniV1.ina226_vbusct_vshct_str,
            state="readonly",
            width=10,
        )
        self.combobox_ina226_vbusct.grid(row=2, column=1, sticky=tk.W, padx=1)
        self.combobox_ina226_vshct = ttk.Combobox(
            self.frame_ina226_config,
            values=com_PowerMonitorMiniV1.ina226_vbusct_vshct_str,
            state="readonly",
            width=10,
        )
        self.combobox_ina226_vshct.grid(row=2, column=0, sticky=tk.W, padx=1)
        self.combobox_ina226_avg = ttk.Combobox(
            self.frame_ina226_config,
            values=com_PowerMonitorMiniV1.ina226_avg_value,
            state="readonly",
            width=10,
        )
        self.combobox_ina226_avg.grid(row=2, column=2, sticky=tk.W, padx=1)
        self.combobox_ina226_current_lsb = ttk.Combobox(
            self.frame_ina226_config,
            values=[f"{i/10:.1f}mA" for i in range(1, 11, 1)],
            state="readonly",
            width=10,
        )
        self.combobox_ina226_current_lsb.grid(row=2, column=3, sticky=tk.W, padx=1)
        self.btn_ina226_reflash = ttk.Button(
            self.frame_ina226_config, text="Refresh", command=self.btn_ina226_reflash
        )
        self.btn_ina226_reflash.grid(row=3, column=2, padx=1, pady=1)
        self.btn_ina226_apply = ttk.Button(
            self.frame_ina226_config, text="Apply", command=self.btn_ina226_apply
        )
        self.btn_ina226_apply.grid(row=3, column=3, padx=1, pady=1)
        self.label_ina226_current_offset = tk.Label(
            self.frame_ina226_config,
            text="Current Offset Unit: 0.1mA",
            font=("Arial", 12, "bold"),
            anchor=tk.W,
        )
        self.label_ina226_current_offset.grid(
            row=4, column=0, columnspan=4, sticky=tk.W
        )
        self.label_ina226_current_offset0_display = tk.Label(
            self.frame_ina226_config, text="offset0 Display", anchor=tk.W
        )
        self.label_ina226_current_offset0_display.grid(row=5, column=0, sticky=tk.W)
        self.label_ina226_current_offset0_actual = tk.Label(
            self.frame_ina226_config, text="offset0 Actual", anchor=tk.W
        )
        self.label_ina226_current_offset0_actual.grid(row=5, column=1, sticky=tk.W)
        self.label_ina226_current_offset1_display = tk.Label(
            self.frame_ina226_config, text="offset1 Display", anchor=tk.W
        )
        self.label_ina226_current_offset1_display.grid(row=5, column=2, sticky=tk.W)
        self.label_ina226_current_offset1_actual = tk.Label(
            self.frame_ina226_config, text="offset1 Actual", anchor=tk.W
        )
        self.label_ina226_current_offset1_actual.grid(row=5, column=3, sticky=tk.W)
        self.entry_ina226_current_offset0_display = ttk.Entry(
            self.frame_ina226_config,
            width=10,
            validate="key",
            validatecommand=(self.maintk.register(self.only_digit), "%S"),
        )
        self.entry_ina226_current_offset0_display.grid(
            row=6, column=0, sticky=tk.W + tk.E, padx=1
        )
        self.entry_ina226_current_offset0_actual = ttk.Entry(
            self.frame_ina226_config,
            width=10,
            validate="key",
            validatecommand=(self.maintk.register(self.only_digit), "%S"),
        )
        self.entry_ina226_current_offset0_actual.grid(
            row=6, column=1, sticky=tk.W + tk.E, padx=1
        )
        self.entry_ina226_current_offset1_display = ttk.Entry(
            self.frame_ina226_config,
            width=10,
            validate="key",
            validatecommand=(self.maintk.register(self.only_digit), "%S"),
        )
        self.entry_ina226_current_offset1_display.grid(
            row=6, column=2, sticky=tk.W + tk.E, padx=1
        )
        self.entry_ina226_current_offset1_actual = ttk.Entry(
            self.frame_ina226_config,
            width=10,
            validate="key",
            validatecommand=(self.maintk.register(self.only_digit), "%S"),
        )
        self.entry_ina226_current_offset1_actual.grid(
            row=6, column=3, sticky=tk.W + tk.E, padx=1
        )
        self.label_ina226_current_offset_zero = tk.Label(
            self.frame_ina226_config, text="Zero Offset", anchor=tk.W
        )
        self.label_ina226_current_offset_zero.grid(row=7, column=0, sticky=tk.W)
        self.combobox_ina226_current_offset_zero = ttk.Combobox(
            self.frame_ina226_config,
            values=[f"{i/10:.1f}mA" for i in range(-15, 16, 1)],
            state="readonly",
            width=10,
        )
        self.combobox_ina226_current_offset_zero.grid(
            row=8, column=0, sticky=tk.W + tk.E, padx=1
        )
        self.btn_ina226_current_offset_reflash = ttk.Button(
            self.frame_ina226_config,
            text="Refresh",
            command=self.btn_ina226_current_offset_reflash,
        )
        self.btn_ina226_current_offset_reflash.grid(row=8, column=2, padx=1, pady=1)
        self.btn_ina226_current_offset_apply = ttk.Button(
            self.frame_ina226_config,
            text="Apply",
            command=self.btn_ina226_current_offset_apply,
        )
        self.btn_ina226_current_offset_apply.grid(row=8, column=3, padx=1, pady=1)

        self.maintk.mainloop()

    def only_digit(self, char):
        return char in "0123456789"

    def set_entry_value(self, entry, value):
        entry.config(validate="none")
        entry.delete(0, tk.END)
        entry.insert(0, value)
        entry.config(validate="key")

    def btn_com_reflash(self):
        self.comlist = self.com_port_reflash()
        self.comportCombobox["value"] = tuple(self.comlist[1])
        if len(self.comlist[0]) == 0:
            self.btnopencom["state"] = "disabled"
            self.comportvar.set("")
        else:
            self.btnopencom["state"] = "normal"
            self.comportCombobox.current(0)
        self.comportCombobox_selected()

    def btn_com_open(self):
        if self.thread_status == 0:
            self.thread_status = 1
            self.run_com_task()
        else:
            self.thread_status = 2

        # print(self.comlist[0][self.comportCombobox.current()],self.comlist[2][self.comportCombobox.current()], self.combpsvar.get())
        pass

    def com_port_reflash(self):
        port_list = list(serial.tools.list_ports.comports())
        comlist = []
        comlist.append(list())
        comlist.append(list())
        comlist.append(list())
        if len(port_list) == 0:
            print("No available ports")
        else:
            print(port_list[0][0])
            for i in range(0, len(port_list)):
                plist_com = list(port_list[i])
                print(plist_com)
                comlist[0].append(plist_com[0])
                comlist[1].append(plist_com[0] + " " + plist_com[1])
                if len(plist_com) > 2:
                    comlist[2].append(plist_com[2])
                else:
                    comlist[2].append("")
                # comlist.append(plist_com)
        return comlist

    def comportCombobox_selected(self, event=None):
        if (
            len(self.comlist[2]) > 0
            and "USB VID:PID=1A86:FE0C SER=B1"
            in self.comlist[2][self.comportCombobox.current()]
        ):
            self.com_with_crc_check.set(False)
            self.com_with_crc_checkbutton["state"] = "disabled"
            self.combpscombobox["state"] = "disabled"
        else:
            self.com_with_crc_check.set(True)
            self.com_with_crc_checkbutton["state"] = "normal"
            self.combpscombobox["state"] = "readonly"

    def btn_output_data_max_reset(self):
        if self.thread_status == 1:
            self.queue_device_recv.put(("output_data_max_reset", None))
        pass

    def btn_ina226_reflash(self):
        if self.thread_status == 1:
            self.combobox_ina226_current_lsb["state"] = "disabled"
            self.combobox_ina226_vbusct["state"] = "disabled"
            self.combobox_ina226_vshct["state"] = "disabled"
            self.combobox_ina226_avg["state"] = "disabled"

            self.queue_device_recv.put(("ina226_reflash", None))
        pass

    def btn_ina226_apply(self):
        if self.thread_status == 1:
            vbusct = self.combobox_ina226_vbusct.current()
            vshct = self.combobox_ina226_vshct.current()
            avg = self.combobox_ina226_avg.current()
            current_lsb = self.combobox_ina226_current_lsb.current() + 1
            # print(vbusct, vshct, avg, current_lsb)
            self.queue_device_recv.put(
                ("ina226_apply", (vbusct, vshct, avg, current_lsb))
            )
        pass

    def btn_ina226_current_offset_reflash(self):
        if self.thread_status == 1:
            self.entry_ina226_current_offset0_display["state"] = "disabled"
            self.entry_ina226_current_offset0_actual["state"] = "disabled"
            self.entry_ina226_current_offset1_display["state"] = "disabled"
            self.entry_ina226_current_offset1_actual["state"] = "disabled"
            self.combobox_ina226_current_offset_zero["state"] = "disabled"

            self.queue_device_recv.put(("ina226_current_offset_reflash", None))

        pass

    def btn_ina226_current_offset_apply(self):
        if self.thread_status == 1:
            try:
                current_offset0_display = int(
                    self.entry_ina226_current_offset0_display.get()
                )
                current_offset0_actual = int(
                    self.entry_ina226_current_offset0_actual.get()
                )
                current_offset1_display = int(
                    self.entry_ina226_current_offset1_display.get()
                )
                current_offset1_actual = int(
                    self.entry_ina226_current_offset1_actual.get()
                )
                current_offset_zero = int(
                    self.combobox_ina226_current_offset_zero.current() - 15
                )
                if current_offset0_display not in range(-100000, 100001):
                    messagebox.showerror(
                        "Error", "offset0 display value out of the range"
                    )
                    return
                if current_offset0_actual not in range(-100000, 100001):
                    messagebox.showerror(
                        "Error", "offset0 actual value out of the range"
                    )
                    return
                if current_offset1_display not in range(-100000, 100001):
                    messagebox.showerror(
                        "Error", "offset1 display value out of the range"
                    )
                    return
                if current_offset1_actual not in range(-100000, 100001):
                    messagebox.showerror(
                        "Error", "offset1 actual value out of the range"
                    )
                    return
                if current_offset_zero not in range(-15, 16):
                    messagebox.showerror("Error", "offset zero out of the range")
                    return
            except Exception as e:
                messagebox.showerror("Error", str(e))
                return

            current_offset = (
                current_offset0_display,
                current_offset0_actual,
                current_offset1_display,
                current_offset1_actual,
                current_offset_zero,
            )
            self.queue_device_recv.put(("ina226_current_offset_apply", current_offset))
        pass

    def btn_pd_refresh_click(self):
        if self.thread_status == 1:
            self.queue_device_recv.put(("pd_refresh", None))
        pass

    def btn_pd_apply_click(self):
        if self.thread_status == 1:
            pdo_id = self.combobox_pd_id_set.current() + 1
            pdo_voltage = int(self.combobox_pd_voltage_set.get())
            self.queue_device_recv.put(("pd_apply", (pdo_id, pdo_voltage)))
        pass

    def combobox_pd_id_set_click(self, event=None, pdo_voltage=None):
        children = self.tree_pd.get_children()
        row = self.tree_pd.item(children[self.combobox_pd_id_set.current()])["values"]
        self.combobox_pd_voltage_set.config(validate="none")
        if row[1] == "fixed":
            self.combobox_pd_voltage_set.set(row[3])
            self.combobox_pd_voltage_set["state"] = "disabled"
            self.combobox_pd_voltage_set.unbind("<KeyRelease>")
        else:
            if row[1] == "pps":
                combobox_values = [f"{i:d}" for i in range(row[2], row[3] + 20, 20)]
            else:
                combobox_values = [f"{i:d}" for i in range(row[2], row[3] + 100, 100)]
            self.combobox_pd_voltage_set.config(values=combobox_values)
            if pdo_voltage is not None:
                current = combobox_values.index(str(pdo_voltage))
                self.combobox_pd_voltage_set.current(current)
            else:
                self.combobox_pd_voltage_set.current(0)
            self.combobox_pd_voltage_set["state"] = "readonly"
        self.combobox_pd_voltage_set.config(validate="key")

    def run_com_task(self):
        if self.com_task_step == 0:
            self.com_task_step = 1
            self.comopenflagstr.set("port is open")
            self.comopenbtnstr.set("Close")
            self.btncom_reflash["state"] = "disabled"
            self.comportCombobox["state"] = "disabled"
            self.combpscombobox["state"] = "disabled"
            self.com_with_crc_checkbutton["state"] = "disabled"
        elif self.com_task_step == 1:
            th = threading.Thread(target=self.run_device_task, daemon=True)
            th.start()
            self.com_task_step = 2

        else:
            while True:
                try:
                    data = self.queue_device_send.get_nowait()
                    if data[0] == "error":
                        messagebox.showerror("Error", data[1])
                    elif data[0] == "who_am_i":
                        self.label_device_info_value.config(text=data[1])
                    elif data[0] == "system_serial_num":
                        self.label_device_sn_value.config(text=data[1])
                    elif data[0] == "system_version":
                        self.label_device_soft_version_value.config(text=data[1])
                    elif data[0] == "rshunt":
                        self.label_device_rshunt_value.config(text=str(data[1]) + "mΩ")
                    elif data[0] == "input_type":
                        self.label_device_input_type_value.config(text=data[1])
                    elif data[0] == "output_data":
                        self.label_output_voltage_value.config(
                            text=str(f"{data[1][0]/1000:.3f}V")
                        )
                        self.label_output_current_value.config(
                            text=str(f"{data[1][1]/10000:.4f}A")
                        )
                        self.label_output_power_value.config(
                            text=str(f"{data[1][2]/1000:.3f}W")
                        )
                    elif data[0] == "output_data_max":
                        self.label_output_data_max_voltage_value.config(
                            text=str(f"{data[1][0]/1000:.3f}V")
                        )
                        self.label_output_data_max_current_value.config(
                            text=str(f"{data[1][1]/10000:.4f}A")
                        )
                        self.label_output_data_max_power_value.config(
                            text=str(f"{data[1][2]/1000:.3f}W")
                        )
                    elif data[0] == "maH_mwH":
                        self.label_mah_value.config(text=str(data[1][0]) + "mAh")
                        self.label_mwh_value.config(text=str(data[1][1]) + "mWh")
                    elif data[0] == "uptime":
                        self.label_uptime_value.config(text=str(data[1]) + "s")
                    elif data[0] == "ina226_config":
                        self.combobox_ina226_current_lsb["state"] = "readonly"
                        self.combobox_ina226_vbusct["state"] = "readonly"
                        self.combobox_ina226_vshct["state"] = "readonly"
                        self.combobox_ina226_avg["state"] = "readonly"
                        self.combobox_ina226_current_lsb.current(
                            data[1]["currentLSB"] - 1
                        )
                        self.combobox_ina226_avg.current(data[1]["reg"]["avg"])
                        self.combobox_ina226_vbusct.current(data[1]["reg"]["vbusct"])
                        self.combobox_ina226_vshct.current(data[1]["reg"]["vshct"])
                    elif data[0] == "ina226_current_offset":
                        self.entry_ina226_current_offset0_display["state"] = "normal"
                        self.entry_ina226_current_offset0_actual["state"] = "normal"
                        self.entry_ina226_current_offset1_display["state"] = "normal"
                        self.entry_ina226_current_offset1_actual["state"] = "normal"
                        self.combobox_ina226_current_offset_zero["state"] = "readonly"

                        self.set_entry_value(
                            self.entry_ina226_current_offset0_display,
                            data[1][0]["display"],
                        )
                        self.set_entry_value(
                            self.entry_ina226_current_offset0_actual,
                            data[1][0]["actual"],
                        )
                        self.set_entry_value(
                            self.entry_ina226_current_offset1_display,
                            data[1][1]["display"],
                        )
                        self.set_entry_value(
                            self.entry_ina226_current_offset1_actual,
                            data[1][1]["actual"],
                        )
                        self.combobox_ina226_current_offset_zero.current(
                            data[1][2] + 15
                        )

                    elif data[0] == "frame_pd_remove":
                        self.frame_pd.grid_remove()
                    elif data[0] == "pd_pdo_tree_clean":
                        self.tree_pd.delete(*self.tree_pd.get_children())
                    elif data[0] == "pd_pdo_tree_add":
                        if data[1] == "fixed":
                            for pdo in data[2]["fixeddata"]:
                                self.tree_pd.insert(
                                    "",
                                    "end",
                                    values=(
                                        len(self.tree_pd.get_children()) + 1,
                                        data[1],
                                        "",
                                        pdo["voltage"],
                                        pdo["current"],
                                        "",
                                    ),
                                )
                        elif data[1] == "pps":
                            for pdo in data[2]["ppsdata"]:
                                self.tree_pd.insert(
                                    "",
                                    "end",
                                    values=(
                                        len(self.tree_pd.get_children()) + 1,
                                        data[1],
                                        pdo["minvoltage"],
                                        pdo["maxvoltage"],
                                        pdo["maxcurrent"],
                                        "",
                                    ),
                                )
                        elif data[1] == "avs":
                            for pdo in data[2]["avsdata"]:
                                self.tree_pd.insert(
                                    "",
                                    "end",
                                    values=(
                                        len(self.tree_pd.get_children()) + 1,
                                        data[1],
                                        pdo["minvoltage"],
                                        pdo["maxvoltage"],
                                        "",
                                        pdo["maxpower"],
                                    ),
                                )
                    elif data[0] == "pd_pdo_tree_over":
                        self.combobox_pd_id_set.config(
                            values=[
                                i + 1 for i in range(len(self.tree_pd.get_children()))
                            ]
                        )
                    elif data[0] == "pd_pdo_now":
                        self.combobox_pd_id_set.current(data[1][0] - 1)
                        self.combobox_pd_id_set_click(pdo_voltage=data[1][1])
                        self.combobox_pd_id_set["state"] = "readonly"
                        self.btn_pd_refresh["state"] = "normal"
                        self.btn_pd_apply["state"] = "normal"
                        pass

                except queue.Empty:
                    break

        if self.thread_status != 0:
            self.maintk.after(100, self.run_com_task)
        else:
            self.comopenflagstr.set("port is closed")
            self.comopenbtnstr.set("Open")
            self.com_task_step = 0
            self.btncom_reflash["state"] = "normal"
            self.comportCombobox["state"] = "readonly"
            self.combpscombobox["state"] = "readonly"
            self.comportCombobox_selected()
            self.label_device_info_value.config(text="")
            self.label_device_sn_value.config(text="")
            self.label_device_soft_version_value.config(text="")
            self.label_device_rshunt_value.config(text="")
            self.label_device_input_type_value.config(text="")
            self.frame_pd.grid()

    def run_device_task(self):
        try:
            com_port = str(self.comlist[0][self.comportCombobox.current()])
            baudrate = int(self.combpsvar.get())
            crc_check = self.com_with_crc_check.get()
            print(com_port, baudrate, crc_check)
            self.device = com_PowerMonitorMiniV1(
                port=com_port, baudrate=baudrate, use_crc8=crc_check
            )

            who_am_i = self.device.who_am_i()
            self.queue_device_send.put(("who_am_i", who_am_i))

            sn = self.device.system_serial_num()
            self.queue_device_send.put(("system_serial_num", sn))

            soft_version = self.device.system_version()
            self.queue_device_send.put(("system_version", soft_version))

            rshunt = self.device.current_rshunt_get()
            self.queue_device_send.put(("rshunt", rshunt))

            input_type = INPUT_TYPE.get(self.device.input_type_get(), "Unknown")
            self.queue_device_send.put(("input_type", input_type))
            retry_count = 0
            while input_type == "Initialization":
                input_type = INPUT_TYPE.get(self.device.input_type_get(), "Unknown")
                self.queue_device_send.put(("input_type", input_type))
                time.sleep(1)
                retry_count += 1
                if retry_count > 2:
                    messagebox.showerror("Error", "input type get failed")
                    self.thread_status = 0
                    self.device.close()
                    return

            ina226_config = self.device.ina226_config_get()
            self.queue_device_send.put(("ina226_config", ina226_config))

            current_offset0, current_offset1, current_zero = (
                self.device.current_offset_get()
            )
            self.queue_device_send.put(
                (
                    "ina226_current_offset",
                    (current_offset0, current_offset1, current_zero),
                )
            )

            def device_get_pd_data():
                if input_type == "PD":
                    fixed_num, pps_num, avs_num = self.device.pd_pdo_num()
                    self.queue_device_send.put(("pd_pdo_tree_clean", None))
                    if fixed_num > 0:
                        pd_pdo_fix = self.device.pd_pdo_fix_get()
                        self.queue_device_send.put(
                            ("pd_pdo_tree_add", "fixed", pd_pdo_fix)
                        )
                    if pps_num > 0:
                        pd_pdo_pps = self.device.pd_pdo_pps_get()
                        self.queue_device_send.put(
                            ("pd_pdo_tree_add", "pps", pd_pdo_pps)
                        )
                    if avs_num > 0:
                        pd_pdo_avs = self.device.pd_pdo_avs_get()
                        self.queue_device_send.put(
                            ("pd_pdo_tree_add", "avs", pd_pdo_avs)
                        )
                    self.queue_device_send.put(("pd_pdo_tree_over", None))
                    pdo_id, pdo_voltage = self.device.pd_pdo_now()
                    self.queue_device_send.put(("pd_pdo_now", (pdo_id, pdo_voltage)))
                else:
                    self.queue_device_send.put(("frame_pd_remove", None))

            device_get_pd_data()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", "COM port open failed\n" + str(e))
            self.thread_status = 0
            self.device.close()
            return

        time_tick_output_data = 0.1
        time_output_data_last = time.time()

        time_tick_output_data_max = 1
        time_output_data_max_last = time.time()

        time_tick_mah_mwh_uptime = 1
        time_mah_mwh_uptime_last = time.time()

        error_count = 0
        while True:
            try:
                data = self.queue_device_recv.get(timeout=0.05)
                if data[0] == "ina226_reflash":
                    ina226_config = self.device.ina226_config_get()
                    self.queue_device_send.put(("ina226_config", ina226_config))
                elif data[0] == "ina226_apply":
                    vbusct, vshct, avg, current_lsb = data[1]
                    self.device.ina226_config_set(
                        currentLSB=current_lsb, vbusct=vbusct, vshct=vshct, avg=avg
                    )
                    time.sleep(0.01)
                elif data[0] == "output_data_max_reset":
                    self.device.output_data_max_reset()
                    time.sleep(0.01)
                elif data[0] == "ina226_current_offset_reflash":
                    current_offset0, current_offset1, current_zero = (
                        self.device.current_offset_get()
                    )
                    self.queue_device_send.put(
                        (
                            "ina226_current_offset",
                            (current_offset0, current_offset1, current_zero),
                        )
                    )
                elif data[0] == "ina226_current_offset_apply":
                    (
                        current_offset0_display,
                        current_offset0_actual,
                        current_offset1_display,
                        current_offset1_actual,
                        current_offset_zero,
                    ) = data[1]
                    self.device.current_offset_set(
                        offset0_display=current_offset0_display,
                        offset0_actual=current_offset0_actual,
                        offset1_display=current_offset1_display,
                        offset1_actual=current_offset1_actual,
                        zero_offset=current_offset_zero,
                    )
                    time.sleep(0.01)
                elif data[0] == "pd_refresh":
                    device_get_pd_data()
                elif data[0] == "pd_apply":
                    pdo_id, pdo_voltage = data[1]
                    self.device.pd_pdo_set(id=pdo_id, voltage=pdo_voltage)
                    time.sleep(0.01)

            except queue.Empty:
                pass
            except Exception as e:
                traceback.print_exc()
                self.queue_device_send.put(("error", str(e)))

            try:
                time_now = time.time()
                if time_now - time_output_data_last >= time_tick_output_data:
                    time_output_data_last = time_now
                    voltage, current, power = self.device.output_data()
                    self.queue_device_send.put(
                        ("output_data", (voltage, current, power))
                    )
                    error_count = 0
                if time_now - time_output_data_max_last >= time_tick_output_data_max:
                    time_output_data_max_last = time_now
                    voltage, current, power = self.device.output_data_max()
                    self.queue_device_send.put(
                        ("output_data_max", (voltage, current, power))
                    )
                    error_count = 0
                if time_now - time_mah_mwh_uptime_last >= time_tick_mah_mwh_uptime:
                    time_mah_mwh_uptime_last = time_now
                    maH, mwH = self.device.maH_mwH()
                    self.queue_device_send.put(("maH_mwH", (maH, mwH)))
                    self.queue_device_send.put(("uptime", self.device.uptime()))
                    error_count = 0
            except Exception as e:
                traceback.print_exc()
                error_count += 1
                if error_count >= 3:
                    self.queue_device_send.put(("error", str(e)))
                    self.thread_status = 2
            if self.thread_status == 2:
                self.device.close()
                print("device closed")
                break

        self.thread_status = 0
        print("thread quit")

    def on_closing(self):
        if self.thread_status != 0:
            self.thread_status = 2
        timeout = 10
        start_time = time.time()
        while self.thread_status != 0:
            timeout -= time.time() - start_time
            if timeout <= 0:
                break
            time.sleep(0.1)
            pass
        self.maintk.destroy()

if __name__ == "__main__":
    app = PowerMonitorMiniV1_GUI()
