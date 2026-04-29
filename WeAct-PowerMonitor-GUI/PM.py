from PyQt5 import QtWidgets, QtCore, QtGui

class SettingsDialog(QtWidgets.QDialog):
	def __init__(self, parent, send_command_func, log_func):
		super().__init__(parent)
		self.setWindowTitle('Settings')
		self.send_command = send_command_func
		self.log = log_func
		self.init_ui()

	def init_ui(self):
		layout = QtWidgets.QFormLayout()

		# LCD Panel Type
		self.lcd_panel_combo = QtWidgets.QComboBox()
		self.lcd_panel_combo.addItems(['HAN', 'BOE'])
		layout.addRow('LCD Panel Type:', self.lcd_panel_combo)

		# Rshunt
		self.rshunt_spin = QtWidgets.QSpinBox()
		self.rshunt_spin.setRange(0, 255)
		layout.addRow('Current Rshunt (mΩ):', self.rshunt_spin)

		# PD PDO (id, voltage)
		self.pdo_id_spin = QtWidgets.QSpinBox()
		self.pdo_id_spin.setRange(1, 8)
		self.pdo_voltage_spin = QtWidgets.QSpinBox()
		self.pdo_voltage_spin.setRange(3000, 21000)
		pdo_layout = QtWidgets.QHBoxLayout()
		pdo_layout.addWidget(QtWidgets.QLabel('ID:'))
		pdo_layout.addWidget(self.pdo_id_spin)
		pdo_layout.addWidget(QtWidgets.QLabel('Voltage (mV):'))
		pdo_layout.addWidget(self.pdo_voltage_spin)
		layout.addRow('Set PD PDO:', pdo_layout)

		# Buttons
		btn_layout = QtWidgets.QHBoxLayout()
		self.read_btn = QtWidgets.QPushButton('Read')
		self.read_btn.clicked.connect(self.read_settings)
		self.write_btn = QtWidgets.QPushButton('Write')
		self.write_btn.clicked.connect(self.write_settings)
		self.close_btn = QtWidgets.QPushButton('Close')
		self.close_btn.clicked.connect(self.accept)
		btn_layout.addWidget(self.read_btn)
		btn_layout.addWidget(self.write_btn)
		btn_layout.addWidget(self.close_btn)
		layout.addRow(btn_layout)

		self.setLayout(layout)

	def read_settings(self):
		# Read LCD panel type
		resp = self.send_command(0x46, read_len=3)
		if resp and len(resp) >= 3 and resp[0] == 0xC6:
			val = resp[1]
			self.lcd_panel_combo.setCurrentIndex(val if val in (0, 1) else 0)
			self.log(f'Read LCD panel type: {val}')

		# Read Rshunt
		resp = self.send_command(0x47, read_len=3)
		if resp and len(resp) >= 3 and resp[0] == 0xC7:
			self.rshunt_spin.setValue(resp[1])
			self.log(f'Read Rshunt: {resp[1]}')

	def write_settings(self):
		# Write LCD panel type
		val = self.lcd_panel_combo.currentIndex()
		cmd = bytes([0x46, val, 0x0A])
		self.send_command_raw(cmd)
		self.log(f'Write LCD panel type: {val}')

		# Write Rshunt
		rshunt = self.rshunt_spin.value()
		cmd = bytes([0x47, rshunt, 0x0A])
		self.send_command_raw(cmd)
		self.log(f'Write Rshunt: {rshunt}')

		# Write PD PDO
		pdo_id = self.pdo_id_spin.value()
		voltage = self.pdo_voltage_spin.value()
		cmd = bytes([0x0A, pdo_id, voltage & 0xFF, (voltage >> 8) & 0xFF, 0x0A])
		self.send_command_raw(cmd)
		self.log(f'Write PD PDO: id={pdo_id}, voltage={voltage}')

	def send_command_raw(self, cmd_bytes):
		if self.send_command:
			self.send_command(-1, raw=cmd_bytes)

import sys
import serial
import serial.tools.list_ports
from PyQt5 import QtWidgets, QtCore


from PyQt5 import QtGui
import time
import collections

class PowerMonitorGUI(QtWidgets.QWidget):
	def __init__(self):
		super().__init__()
		self.setWindowTitle('WeAct PowerMonitor (by @A8tor)')
		self.serial_port = None
		self.timer = QtCore.QTimer()
		self.timer.timeout.connect(self.read_values)
		self.read_interval_ms = 1
		self.current_history = []  # Без ограничения длины
		self.time_history = []  # Без ограничения длины
		self.start_time = None  # Время старта автообновления
		self.init_ui()
		self.resize(1500, 800)


	def init_ui(self):
		import pyqtgraph as pg
		main_layout = QtWidgets.QVBoxLayout()

		# --- Верх: настройки компорта ---
		port_layout = QtWidgets.QHBoxLayout()
		self.port_combo = QtWidgets.QComboBox()
		self.refresh_ports()
		self.baudrate_combo = QtWidgets.QComboBox()
		baudrates = ['9600', '19200', '38400', '57600', '115200']
		self.baudrate_combo.addItems(baudrates)
		self.baudrate_combo.setCurrentText('115200')
		self.connect_btn = QtWidgets.QPushButton('Connect')
		self.connect_btn.clicked.connect(self.toggle_connection)
		self.refresh_btn = QtWidgets.QPushButton('Refresh')
		self.refresh_btn.clicked.connect(self.refresh_ports)
		port_layout.addWidget(QtWidgets.QLabel('Port:'))
		port_layout.addWidget(self.port_combo)
		port_layout.addWidget(QtWidgets.QLabel('Baudrate:'))
		port_layout.addWidget(self.baudrate_combo)
		port_layout.addWidget(self.connect_btn)
		port_layout.addWidget(self.refresh_btn)
		# Обернуть port_layout в QWidget для задания фиксированной ширины
		port_widget = QtWidgets.QWidget()
		port_widget.setLayout(port_layout)
		port_widget.setFixedWidth(600)  # Подобрать ширину под поля
		main_layout.addWidget(port_widget, alignment=QtCore.Qt.AlignLeft)

		# --- Средняя часть: значения слева, график справа ---
		middle_layout = QtWidgets.QHBoxLayout()
		values_layout = QtWidgets.QVBoxLayout()

		# Текущие значения — компактно, QFormLayout
		form = QtWidgets.QFormLayout()
		self.voltage_field = QtWidgets.QLineEdit(); self.voltage_field.setReadOnly(True)
		self.current_field = QtWidgets.QLineEdit(); self.current_field.setReadOnly(True)
		self.power_field = QtWidgets.QLineEdit(); self.power_field.setReadOnly(True)
		self.mah_field = QtWidgets.QLineEdit(); self.mah_field.setReadOnly(True)
		self.mwh_field = QtWidgets.QLineEdit(); self.mwh_field.setReadOnly(True)
		self.uptime_field = QtWidgets.QLineEdit(); self.uptime_field.setReadOnly(True)
		for field in [self.voltage_field, self.current_field, self.power_field, self.mah_field, self.mwh_field, self.uptime_field]:
			field.setFixedWidth(90)
		form.addRow('Voltage (V):', self.voltage_field)
		form.addRow('Current (A):', self.current_field)
		form.addRow('Power (W):', self.power_field)
		form.addRow('mAh:', self.mah_field)
		form.addRow('mWh:', self.mwh_field)
		form.addRow('Uptime (s):', self.uptime_field)
		values_layout.addLayout(form)

		# Кнопки под значениями (вертикально)
		cmd_layout = QtWidgets.QVBoxLayout()
		self.auto_btn = QtWidgets.QPushButton('Auto Read')
		self.auto_btn.setCheckable(True)
		self.auto_btn.toggled.connect(self.toggle_auto_read)
		self.reset_max_btn = QtWidgets.QPushButton('Reset Max')
		self.reset_max_btn.clicked.connect(self.reset_max)
		self.system_reset_btn = QtWidgets.QPushButton('System Reset')
		self.system_reset_btn.clicked.connect(self.system_reset)
		self.settings_btn = QtWidgets.QPushButton('Settings')
		self.settings_btn.clicked.connect(self.open_settings)
		cmd_layout.addWidget(self.auto_btn)
		cmd_layout.addWidget(self.reset_max_btn)
		cmd_layout.addWidget(self.system_reset_btn)
		cmd_layout.addWidget(self.settings_btn)
		cmd_layout.addStretch(1)  # Кнопки прижаты к верху
		values_layout.addLayout(cmd_layout)


		# График справа
		import pyqtgraph as pg
		self.current_plot = pg.PlotWidget()
		self.current_plot.setBackground('w')
		self.current_plot.showGrid(x=True, y=True)
		self.current_plot.setLabel('left', 'Current (A)')
		self.current_plot.setLabel('bottom', 'Time (s)')
		self.current_curve = self.current_plot.plot([], pen=pg.mkPen('b', width=2), symbol=None)

		# Курсор для отображения значения при наведении
		self.vLine = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('g', width=1, style=QtCore.Qt.DashLine))
		self.hLine = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('g', width=1, style=QtCore.Qt.DashLine))
		self.current_plot.addItem(self.vLine, ignoreBounds=True)
		self.current_plot.addItem(self.hLine, ignoreBounds=True)
		self.label = pg.TextItem('', anchor=(0,1), color='k')
		self.current_plot.addItem(self.label)
		self.current_plot.scene().sigMouseMoved.connect(self.on_mouse_moved)

		middle_layout.addLayout(values_layout, 0)
		middle_layout.addWidget(self.current_plot, 1)
		# Логи справа от графика
		log_layout = QtWidgets.QVBoxLayout()
		log_label = QtWidgets.QLabel('Log:')
		self.log_text = QtWidgets.QTextEdit()
		self.log_text.setReadOnly(True)
		self.log_text.setFixedWidth(200)
		log_layout.addWidget(log_label)
		log_layout.addWidget(self.log_text)
		middle_layout.addLayout(log_layout, 2)
		main_layout.addLayout(middle_layout, 1)

		# Средний ток под кнопкой Settings
		self.avg_current_label = QtWidgets.QLabel('Average Current: -')
		cmd_layout.insertWidget(cmd_layout.count()-1, self.avg_current_label)
		self.current_plot.sigRangeChanged.connect(self.update_avg_current)

		self.setLayout(main_layout)

	def refresh_ports(self):
		self.port_combo.clear()
		ports = serial.tools.list_ports.comports()
		for port in ports:
			self.port_combo.addItem(port.device)

	def toggle_connection(self):
		if self.serial_port and self.serial_port.is_open:
			self.serial_port.close()
			self.serial_port = None
			self.connect_btn.setText('Connect')
			self.log('Disconnected.')
			# Stop polling when disconnected
			self.timer.stop()
			self.auto_btn.setChecked(False)
			self.auto_btn.setText('Auto Read')
		else:
			port = self.port_combo.currentText()
			baudrate = int(self.baudrate_combo.currentText())
			try:
				self.serial_port = serial.Serial(port, baudrate, timeout=1)
				self.connect_btn.setText('Disconnect')
				self.log(f'Connected to {port} at {baudrate} baud.')
			except Exception as e:
				self.log(f'Error: {e}')
    

	def send_command(self, cmd, read_len=0, raw=None):
		if not self.serial_port or not self.serial_port.is_open:
			return None
		if raw is not None:
			cmd_bytes = raw
		else:
			cmd_bytes = bytes([cmd | 0x80, 0x0A])
		self.serial_port.reset_input_buffer()
		self.serial_port.write(cmd_bytes)
		# QtCore.QThread.msleep(10)
		resp = self.serial_port.read_all()
		if read_len > 0 and len(resp) < read_len:
			more = self.serial_port.read(read_len - len(resp))
			resp += more
		# Не логировать циклические чтения (0x82, 0x84, 0x85)
		skip_log = False
		if raw is None and (cmd | 0x80) in (0x82, 0x84, 0x85):
			skip_log = True
		if not skip_log:
			self.log(f'Sent: {cmd_bytes.hex()}  Resp: {resp.hex()}')
		return resp


	def read_values(self):
		if self.start_time is None:
			self.start_time = time.time()
		output = self.read_output_data()
		mah_mwh = self.read_mah_mwh()
		uptime = self.read_uptime()
		now = time.time() - self.start_time
		if output:
			voltage, current, power = output
			self.voltage_field.setText(f'{voltage/1000:.3f}')
			self.current_field.setText(f'{current/10000:.4f}')
			self.power_field.setText(f'{power/1000:.3f}')
			self.current_history.append(current/10000)
			self.time_history.append(now)
		else:
			self.voltage_field.setText('')
			self.current_field.setText('')
			self.power_field.setText('')
		if mah_mwh:
			mah, mwh = mah_mwh
			self.mah_field.setText(str(mah))
			self.mwh_field.setText(str(mwh))
		else:
			self.mah_field.setText('')
			self.mwh_field.setText('')
		if uptime is not None:
			self.uptime_field.setText(str(uptime))
		else:
			self.uptime_field.setText('')
		# Обновление графика тока
		if hasattr(self, 'current_curve'):
			self.current_curve.setData(self.time_history, self.current_history)
		self.update_avg_current()

	def on_mouse_moved(self, pos):
		vb = self.current_plot.getViewBox()
		mouse_point = vb.mapSceneToView(pos)
		x = mouse_point.x()
		y = mouse_point.y()
		self.vLine.setPos(x)
		self.hLine.setPos(y)
		# Найти ближайшую точку
		if len(self.time_history) > 0:
			times = self.time_history
			currents = self.current_history
			idx = min(range(len(times)), key=lambda i: abs(times[i] - x))
			if 0 <= idx < len(currents):
				val = currents[idx]
				if abs(val) >= 1:
					val_str = f"{val:.4f} A"
				elif abs(val) >= 0.001:
					val_str = f"{val*1000:.2f} mA"
				else:
					val_str = f"{val*1_000_000:.1f} uA"
				self.label.setText(f"t={times[idx]:.1f}s\nI={val_str}")
				self.label.setPos(times[idx], currents[idx])
			else:
				self.label.setText("")

	def update_avg_current(self):
		# Получить видимый диапазон X
		view_range = self.current_plot.viewRange()
		x_min, x_max = view_range[0]
		times = self.time_history
		currents = self.current_history
		values = [curr for t, curr in zip(times, currents) if x_min <= t <= x_max]
		if values:
			avg = sum(values) / len(values)
			self.avg_current_label.setText(f"Average Current: {avg:.4f} A")
		else:
			self.avg_current_label.setText("Average Current: -")
	def toggle_auto_read(self, checked):
		if checked:
			if not self.serial_port or not self.serial_port.is_open:
				self.log('Not connected!')
				self.auto_btn.setChecked(False)
				return
			# Сброс времени и истории
			self.start_time = None
			self.current_history.clear()
			self.time_history.clear()
			self.current_curve.setData([], [])
			self.timer.start(self.read_interval_ms)
			self.auto_btn.setText('Stop Auto')
			self.current_plot.enableAutoRange('xy', True)
		else:
			self.timer.stop()
			self.auto_btn.setText('Auto Read')

	# show_current_graph удалён, график будет встроен

	def open_settings(self):
		dlg = SettingsDialog(self, self.send_command, self.log)
		dlg.exec_()


	def read_output_data(self):
		# CMD_OUTPUT_DATA = 0x02, ответ: 0x82 + 12 байт (V, I, P)
		resp = self.send_command(0x02, read_len=13)
		if resp and len(resp) >= 13 and resp[0] == 0x82:
			voltage = int.from_bytes(resp[1:5], 'little', signed=False)
			current = int.from_bytes(resp[5:9], 'little', signed=True)
			power = int.from_bytes(resp[9:13], 'little', signed=True)
			return voltage, current, power
		return None


	def read_mah_mwh(self):
		# CMD_MAH_MWH = 0x04, ответ: 0x84 + 8 байт (mAh, mWh)
		resp = self.send_command(0x04, read_len=9)
		if resp and len(resp) >= 9 and resp[0] == 0x84:
			mah = int.from_bytes(resp[1:5], 'little', signed=False)
			mwh = int.from_bytes(resp[5:9], 'little', signed=False)
			return mah, mwh
		return None


	def read_uptime(self):
		# CMD_UPTIME = 0x05, ответ: 0x85 + 4 байта (uptime)
		resp = self.send_command(0x05, read_len=5)
		if resp and len(resp) >= 5 and resp[0] == 0x85:
			uptime = int.from_bytes(resp[1:5], 'little', signed=False)
			return uptime
		return None


	def reset_max(self):
		resp = self.send_command(0x06)
		self.log(f'Sent reset max. Response: {resp.hex() if resp else "None"}')


	def system_reset(self):
		resp = self.send_command(0x45)
		self.log(f'Sent system factory reset. Response: {resp.hex() if resp else "None"}')
	def log(self, text):
		self.log_text.append(f'{time.strftime("%H:%M:%S")} {text}')


	# CRC8 не используется, команды завершаются 0x0A

def main():
	app = QtWidgets.QApplication(sys.argv)
	gui = PowerMonitorGUI()
	gui.show()
	sys.exit(app.exec_())

if __name__ == '__main__':
	main()
