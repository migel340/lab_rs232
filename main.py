from __future__ import annotations

import queue
import threading
import time
from typing import Optional

from backend import RS232Backend

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QSizePolicy,
        QTabWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
)



class RS232CommunicatorWindow(QMainWindow):
    def __init__(self) -> None:
        if QMainWindow is None:
            raise RuntimeError(
                "PySide6 is not available in this Python environment. Install dependencies from requirements.txt."
            )

        super().__init__()
        self.setWindowTitle("RS232 Communicator")
        self.resize(1100, 780)

        self.message_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.backend = RS232Backend(
            on_received=self._enqueue_received,
            on_sent=self._enqueue_sent,
            on_status=self._enqueue_status,
        )

        self.port_combo: Optional[QComboBox] = None  # type: ignore[name-defined]
        self.baud_edit: Optional[QLineEdit] = None  # type: ignore[name-defined]
        self.data_bits_combo: Optional[QComboBox] = None  # type: ignore[name-defined]
        self.parity_combo: Optional[QComboBox] = None  # type: ignore[name-defined]
        self.stop_bits_combo: Optional[QComboBox] = None  # type: ignore[name-defined]
        self.flow_combo: Optional[QComboBox] = None  # type: ignore[name-defined]
        self.terminator_combo: Optional[QComboBox] = None  # type: ignore[name-defined]
        self.custom_terminator_edit: Optional[QLineEdit] = None  # type: ignore[name-defined]
        self.status_label: Optional[QLabel] = None  # type: ignore[name-defined]
        self.rts_check: Optional[QCheckBox] = None  # type: ignore[name-defined]
        self.dtr_check: Optional[QCheckBox] = None  # type: ignore[name-defined]
        self.cts_label: Optional[QLabel] = None  # type: ignore[name-defined]
        self.dsr_label: Optional[QLabel] = None  # type: ignore[name-defined]
        self.manual_box: Optional[QGroupBox] = None  # type: ignore[name-defined]
        self.message_edit: Optional[QPlainTextEdit] = None  # type: ignore[name-defined]
        self.hex_edit: Optional[QPlainTextEdit] = None  # type: ignore[name-defined]
        self.autodetect_thread: Optional[threading.Thread] = None  # type: ignore[name-defined]
        self.sent_text: Optional[QTextEdit] = None  # type: ignore[name-defined]
        self.received_text: Optional[QTextEdit] = None  # type: ignore[name-defined]
        self._connected = False

        self._build_ui()
        self.refresh_ports()

        self.queue_timer = QTimer(self)
        self.queue_timer.timeout.connect(self.process_queue)
        self.queue_timer.start(50)

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(12)

        connection_box = QGroupBox("Connection")
        connection_layout = QGridLayout(connection_box)
        connection_layout.setHorizontalSpacing(10)
        connection_layout.setVerticalSpacing(8)

        connection_layout.addWidget(QLabel("Port"), 0, 0)
        self.port_combo = QComboBox()
        self.port_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        connection_layout.addWidget(self.port_combo, 0, 1, 1, 3)

        right_top_buttons = QVBoxLayout()
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_ports)
        right_top_buttons.addWidget(refresh_button)

        self.autodetect_button = QPushButton("Auto Detect")
        self.autodetect_button.clicked.connect(self.run_autodetect)
        right_top_buttons.addWidget(self.autodetect_button)

        ping_button = QPushButton("Send Ping")
        ping_button.clicked.connect(lambda: self.send_message("ping"))
        right_top_buttons.addWidget(ping_button)

        connect_button = QPushButton("Connect")
        connect_button.clicked.connect(self.connect_device)
        right_top_buttons.addWidget(connect_button)

        disconnect_button = QPushButton("Disconnect")
        disconnect_button.clicked.connect(self.disconnect_device)
        right_top_buttons.addWidget(disconnect_button)

        right_top_buttons.addStretch(1)

        connection_layout.addLayout(right_top_buttons, 0, 4, 6, 1)

        connection_layout.addWidget(QLabel("Baud rate"), 1, 0)
        self.baud_edit = QLineEdit("9600")
        connection_layout.addWidget(self.baud_edit, 1, 1)

        connection_layout.addWidget(QLabel("Data bits"), 1, 2)
        self.data_bits_combo = QComboBox()
        self.data_bits_combo.addItems(["7", "8"])
        self.data_bits_combo.setCurrentText("8")
        connection_layout.addWidget(self.data_bits_combo, 1, 3)

        connection_layout.addWidget(QLabel("Parity"), 2, 0)
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(["None", "Even", "Odd"])
        self.parity_combo.setCurrentText("None")
        connection_layout.addWidget(self.parity_combo, 2, 1)

        connection_layout.addWidget(QLabel("Stop bits"), 2, 2)
        self.stop_bits_combo = QComboBox()
        self.stop_bits_combo.addItems(["1", "2"])
        self.stop_bits_combo.setCurrentText("1")
        connection_layout.addWidget(self.stop_bits_combo, 2, 3)

        connection_layout.addWidget(QLabel("Flow control"), 3, 0)
        self.flow_combo = QComboBox()
        self.flow_combo.addItems(["None", "Hardware", "Software", "Manual"])
        self.flow_combo.setCurrentText("None")
        self.flow_combo.currentTextChanged.connect(self._on_flow_control_changed)
        connection_layout.addWidget(self.flow_combo, 3, 1)

        connection_layout.addWidget(QLabel("Terminator"), 3, 2)
        self.terminator_combo = QComboBox()
        self.terminator_combo.addItems(["NONE", "CR", "LF", "CRLF", "CUSTOM"])
        self.terminator_combo.setCurrentText("LF")
        self.terminator_combo.currentTextChanged.connect(self._on_terminator_changed)
        connection_layout.addWidget(self.terminator_combo, 3, 3)

        connection_layout.addWidget(QLabel("Custom terminator"), 4, 0)
        self.custom_terminator_edit = QLineEdit()
        self.custom_terminator_edit.setMaximumWidth(100)
        self.custom_terminator_edit.setEnabled(False)
        connection_layout.addWidget(self.custom_terminator_edit, 4, 1)

        self.status_label = QLabel("Disconnected")
        connection_layout.addWidget(self.status_label, 5, 0, 1, 4)

        root_layout.addWidget(connection_box)

        self.manual_box = QGroupBox("Manual Control (RTS/DTR)")
        manual_layout = QHBoxLayout(self.manual_box)
        self.rts_check = QCheckBox("RTS (out)")
        self.rts_check.stateChanged.connect(self.apply_manual_lines)
        manual_layout.addWidget(self.rts_check)
        self.dtr_check = QCheckBox("DTR (out)")
        self.dtr_check.stateChanged.connect(self.apply_manual_lines)
        manual_layout.addWidget(self.dtr_check)
        manual_layout.addSpacing(20)
        self.cts_label = QLabel("○ CTS: OFF")
        self.cts_label.setStyleSheet("color: gray; font-weight: bold;")
        manual_layout.addWidget(self.cts_label)
        self.dsr_label = QLabel("○ DSR: OFF")
        self.dsr_label.setStyleSheet("color: gray; font-weight: bold;")
        manual_layout.addWidget(self.dsr_label)
        manual_layout.addStretch(1)
        self.manual_box.setEnabled(False)
        root_layout.addWidget(self.manual_box)

        send_box = QGroupBox("Send Message")
        send_layout = QVBoxLayout(send_box)
        send_layout.setContentsMargins(8, 8, 8, 8)
        send_layout.setSpacing(8)
        send_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        send_box.setMaximumHeight(230)
        
        # Tab widget for text/binary modes
        mode_tabs = QTabWidget()
        mode_tabs.setMaximumHeight(190)
        mode_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # Text mode tab
        text_tab = QWidget()
        text_layout = QVBoxLayout(text_tab)
        text_layout.setContentsMargins(8, 8, 8, 8)
        text_layout.setSpacing(8)
        self.message_edit = QPlainTextEdit()
        self.message_edit.setPlaceholderText("Type text to send...")
        self.message_edit.setMaximumHeight(96)
        editor_style = (
            "QPlainTextEdit {"
            "background-color: #1f1f1f;"
            "color: #f2f2f2;"
            "border: 1px solid #444;"
            "border-radius: 6px;"
            "padding: 6px;"
            "selection-background-color: #2b6cb0;"
            "}"
        )
        self.message_edit.setStyleSheet(editor_style)
        text_layout.addWidget(self.message_edit)
        text_buttons_layout = QHBoxLayout()
        text_buttons_layout.setSpacing(8)
        send_text_button = QPushButton("Send")
        send_text_button.clicked.connect(self.send_current_message)
        send_text_button.setMinimumHeight(30)
        text_buttons_layout.addWidget(send_text_button)
        text_buttons_layout.addStretch(1)
        text_layout.addLayout(text_buttons_layout)
        mode_tabs.addTab(text_tab, "Text")
        
        # Binary mode tab
        binary_tab = QWidget()
        binary_layout = QVBoxLayout(binary_tab)
        binary_layout.setContentsMargins(8, 8, 8, 8)
        binary_layout.setSpacing(8)
        
        # Hex editor
        self.hex_edit = QPlainTextEdit()
        self.hex_edit.setPlaceholderText("Enter hex bytes: 48 65 6C 6C 6F\nOr: 48656C6C6F\nSpaces/newlines optional")
        self.hex_edit.setMaximumHeight(96)
        self.hex_edit.setStyleSheet(editor_style)
        binary_layout.addWidget(self.hex_edit, 0)
        
        # Binary buttons
        binary_buttons_layout = QHBoxLayout()
        binary_buttons_layout.setSpacing(8)
        send_binary_button = QPushButton("Send Binary")
        send_binary_button.clicked.connect(self.send_binary_data)
        send_binary_button.setMinimumHeight(30)
        binary_buttons_layout.addWidget(send_binary_button)
        
        load_file_button = QPushButton("Load File")
        load_file_button.clicked.connect(self.load_binary_file)
        load_file_button.setMinimumHeight(30)
        binary_buttons_layout.addWidget(load_file_button)
        binary_buttons_layout.addStretch(1)
        
        binary_layout.addLayout(binary_buttons_layout)
        binary_layout.addStretch(1)
        mode_tabs.addTab(binary_tab, "Binary")
        
        send_layout.addWidget(mode_tabs)
        root_layout.addWidget(send_box)

        logs_layout = QHBoxLayout()

        sent_box = QGroupBox("Sent messages")
        sent_layout = QVBoxLayout(sent_box)
        self.sent_text = QTextEdit()
        self.sent_text.setReadOnly(True)
        sent_layout.addWidget(self.sent_text)
        logs_layout.addWidget(sent_box, 1)

        received_box = QGroupBox("Received messages")
        received_layout = QVBoxLayout(received_box)
        self.received_text = QTextEdit()
        self.received_text.setReadOnly(True)
        received_layout.addWidget(self.received_text)
        logs_layout.addWidget(received_box, 1)

        root_layout.addLayout(logs_layout, 1)

        self._set_connected_state(False)

    def _set_connected_state(self, connected: bool) -> None:
        self._connected = connected
        # Enable widgets that should be active only when connected
        for widget in (self.message_edit, self.rts_check, self.dtr_check):
            if widget is not None:
                widget.setEnabled(connected)

        # Disable/enable connection parameter widgets while connected to avoid
        # confusing the user (they must disconnect to change port/baud/etc.)
        for param_widget in (
            self.port_combo,
            self.baud_edit,
            self.data_bits_combo,
            self.parity_combo,
            self.stop_bits_combo,
            self.flow_combo,
            self.terminator_combo,
            self.custom_terminator_edit,
        ):
            if param_widget is not None:
                param_widget.setEnabled(not connected)

        # Disable auto-detect while connected as well
        if hasattr(self, "autodetect_button") and self.autodetect_button is not None:
            self.autodetect_button.setEnabled(not connected)

        self._refresh_manual_controls_enabled()

    def refresh_ports(self) -> None:
        if self.port_combo is None:
            return
        ports = self.backend.list_ports()
        self.port_combo.clear()
        self.port_combo.addItems(ports)
        if ports and self.port_combo.currentIndex() < 0:
            self.port_combo.setCurrentIndex(0)

    def _selected_port_name(self) -> str:
        if self.port_combo is None:
            raise ValueError("Port selector is not available")
        value = self.port_combo.currentText().strip()
        if not value:
            raise ValueError("Select a port first")
        return value.split(" - ", 1)[0]

    def _read_settings(self) -> tuple[int, int, str, str, str, str, str]:
        if self.baud_edit is None or self.data_bits_combo is None or self.parity_combo is None:
            raise RuntimeError("GUI is not initialized")
        try:
            baud_rate = int(self.baud_edit.text().strip())
        except ValueError:
            baud_rate = 9600

        data_bits = 7 if self.data_bits_combo.currentText() == "7" else 8
        parity = self.parity_combo.currentText().strip()[0].upper() if self.parity_combo is not None else "N"
        stop_bits = self.stop_bits_combo.currentText().strip() if self.stop_bits_combo is not None else "1"
        
        # Map display text to flow control codes
        flow_text = self.flow_combo.currentText().strip().lower() if self.flow_combo is not None else "none"
        flow_map = {"none": "N", "hardware": "H", "software": "S", "manual": "M"}
        flow_mode = flow_map.get(flow_text, "N")
        
        terminator_mode = self.terminator_combo.currentText().strip().upper() if self.terminator_combo is not None else "LF"
        custom_terminator = self.custom_terminator_edit.text().strip() if self.custom_terminator_edit is not None else ""
        return baud_rate, data_bits, parity, stop_bits, flow_mode, terminator_mode, custom_terminator

    def connect_device(self) -> None:
        try:
            port_name = self._selected_port_name()
            baud_rate, data_bits, parity, stop_bits, flow_mode, terminator_mode, custom_terminator = self._read_settings()
            self.backend.connect(
                port_name=port_name,
                baud_rate=baud_rate,
                data_bits=data_bits,
                parity_name=parity,
                stop_bits_value=stop_bits,
                flow_mode=flow_mode,
                terminator_mode=terminator_mode,
                custom_terminator=custom_terminator,
            )
            self._set_connected_state(True)
        except Exception as exc:
            QMessageBox.critical(self, "Connection error", str(exc))
            self._set_connected_state(False)

    def disconnect_device(self) -> None:
        self.backend.disconnect()
        self._set_connected_state(False)
        if self.cts_label is not None:
            self.cts_label.setText("○ CTS: OFF")
            self.cts_label.setStyleSheet("color: gray; font-weight: bold;")
        if self.dsr_label is not None:
            self.dsr_label.setText("○ DSR: OFF")
            self.dsr_label.setStyleSheet("color: gray; font-weight: bold;")

    def run_autodetect(self) -> None:
        """Start auto-detect in a background thread."""
        # Don't run auto-detect while already connected
        if self._connected:
            QMessageBox.warning(self, "Auto-detect", "Disconnect first before auto-detect")
            return
        try:
            port_name = self._selected_port_name()
        except ValueError as exc:
            QMessageBox.warning(self, "Port Error", str(exc))
            return
        
        if self.autodetect_thread is not None and self.autodetect_thread.is_alive():
            QMessageBox.warning(self, "Auto-detect", "Auto-detect already running")
            return
        
        # Run auto-detect in background thread
        self.autodetect_thread = threading.Thread(
            target=self._autodetect_worker, args=(port_name,), daemon=True
        )
        self.autodetect_thread.start()

    def _autodetect_worker(self, port_name: str) -> None:
        """Worker thread for auto-detect."""
        try:
            result = self.backend.auto_detect(port_name)
            if result:
                if self.baud_edit is not None:
                    self.baud_edit.setText(str(result.get("baud_rate", "9600")))
                self._enqueue_status("Auto-detect complete! Connecting...")
                time.sleep(0.5)
                # Auto-connect
                self.connect_device()
            else:
                self._enqueue_status("Auto-detect failed")
        except Exception as exc:
            self._enqueue_status(f"Auto-detect error: {exc}")

    def _on_terminator_changed(self) -> None:
        """Enable custom terminator field only when CUSTOM is selected."""
        if self.terminator_combo is None or self.custom_terminator_edit is None:
            return
        is_custom = self.terminator_combo.currentText().strip().upper() == "CUSTOM"
        self.custom_terminator_edit.setEnabled(is_custom)
        if not is_custom:
            self.custom_terminator_edit.clear()

    def _on_flow_control_changed(self) -> None:
        """Enable Manual Control section only when 'Manual' flow control is selected."""
        self._refresh_manual_controls_enabled()

    def _refresh_manual_controls_enabled(self) -> None:
        """Enable RTS/DTR controls only when connected and Manual flow control is selected."""
        if self.flow_combo is None or self.manual_box is None:
            return
        is_manual = self._connected and self.flow_combo.currentText().strip().lower() == "manual"
        self.manual_box.setEnabled(is_manual)

    def apply_manual_lines(self) -> None:
        try:
            if self.rts_check is None or self.dtr_check is None:
                return
            self.backend.set_manual_lines(self.rts_check.isChecked(), self.dtr_check.isChecked())
        except Exception as exc:
            self._enqueue_received(f"Manual control error: {exc}")

    def send_current_message(self) -> None:
        if self.message_edit is None:
            return
        self.send_message(self.message_edit.toPlainText().strip())

    def send_message(self, text: str) -> None:
        if not text:
            return
        if self.backend.device is None or not self.backend.device.is_open:
            QMessageBox.warning(self, "Connection", "Connect to a serial port first")
            return

        try:
            self.backend.send_message(text)
            if self.message_edit is not None:
                self.message_edit.clear()
        except Exception as exc:
            self._enqueue_received(f"Send error: {exc}")

    def send_binary_data(self) -> None:
        """Send data from hex editor."""
        if self.hex_edit is None:
            return
        
        hex_text = self.hex_edit.toPlainText().strip()
        if not hex_text:
            QMessageBox.warning(self, "Input", "Enter hex bytes first")
            return
        
        if self.backend.device is None or not self.backend.device.is_open:
            QMessageBox.warning(self, "Connection", "Connect to a serial port first")
            return
        
        try:
            # Parse hex input (spaces and newlines allowed)
            hex_str = hex_text.replace(" ", "").replace("\n", "").replace("\r", "")
            if len(hex_str) % 2 != 0:
                QMessageBox.warning(self, "Input Error", "Hex string must have even number of characters")
                return
            
            payload = bytes.fromhex(hex_str)
            self.backend.send_binary(payload)
            self.hex_edit.clear()
        except ValueError as exc:
            QMessageBox.critical(self, "Hex Parse Error", f"Invalid hex input: {exc}")
        except Exception as exc:
            self._enqueue_received(f"Send error: {exc}")

    def load_binary_file(self) -> None:
        """Load binary file and display as hex."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Binary File", "", "All Files (*)"
        )
        if not file_path:
            return
        
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            
            if self.backend.device is None or not self.backend.device.is_open:
                QMessageBox.warning(self, "Connection", "Connect to a serial port first")
                return
            
            self.backend.send_binary(data)
            hex_preview = data[:32].hex(" ")  # Preview first 32 bytes
            if len(data) > 32:
                hex_preview += f"... (+{len(data) - 32} bytes)"
            self._enqueue_received(f"[File sent: {file_path} - {len(data)} bytes]\n{hex_preview}")
        except Exception as exc:
            QMessageBox.critical(self, "File Error", f"Cannot load file: {exc}")

    def append_sent(self, text: str) -> None:
        if self.sent_text is None:
            return
        self.sent_text.append(text)

    def append_received(self, text: str) -> None:
        if self.received_text is None:
            return
        self.received_text.append(text)

    def _enqueue_sent(self, text: str) -> None:
        self.message_queue.put(("sent", text))

    def _enqueue_received(self, text: str) -> None:
        self.message_queue.put(("received", text))

    def _enqueue_status(self, text: str) -> None:
        self.message_queue.put(("status", text))

    def process_queue(self) -> None:
        while True:
            try:
                kind, text = self.message_queue.get_nowait()
            except queue.Empty:
                break

            if kind == "sent":
                self.append_sent(text)
            elif kind == "received":
                self.append_received(text)
            elif kind == "status" and self.status_label is not None:
                self.status_label.setText(text)
        
        self.update_line_status()

    def update_line_status(self) -> None:
        """Update CTS/DSR indicator labels."""
        if self.cts_label is None or self.dsr_label is None:
            return
        
        cts = self.backend.get_cts()
        dsr = self.backend.get_dsr()
        
        if cts:
            self.cts_label.setText("● CTS: ON")
            self.cts_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.cts_label.setText("○ CTS: OFF")
            self.cts_label.setStyleSheet("color: gray; font-weight: bold;")
        
        if dsr:
            self.dsr_label.setText("● DSR: ON")
            self.dsr_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.dsr_label.setText("○ DSR: OFF")
            self.dsr_label.setStyleSheet("color: gray; font-weight: bold;")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.backend.disconnect()
        if event is not None:
            event.accept()
        super().closeEvent(event)


def main() -> None:
    if QApplication is None:
        print("PySide6 is not available in this Python environment.")
        print("Install the dependencies from requirements.txt or use a different interpreter.")
        return

    app = QApplication([])
    window = RS232CommunicatorWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
    