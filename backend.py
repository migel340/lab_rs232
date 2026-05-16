from __future__ import annotations

import threading
import time
from typing import Callable

import serial
import serial.tools.list_ports


ReceivedCallback = Callable[[str], None]
StatusCallback = Callable[[str], None]

# Popular baud rates for auto-detect
COMMON_BAUDS = [300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 28800, 38400, 57600, 115200]


class RS232Backend:
    def __init__(
        self,
        on_received: ReceivedCallback | None = None,
        on_sent: ReceivedCallback | None = None,
        on_status: StatusCallback | None = None,
    ) -> None:
        self.on_received = on_received or (lambda message: None)
        self.on_sent = on_sent or (lambda message: None)
        self.on_status = on_status or (lambda message: None)

        self.device: serial.Serial | None = None
        self.reader_thread: threading.Thread | None = None
        self.terminator = b"\n"
        self.ping_sent_time: float | None = None
        self.ping_timer_obj: threading.Timer | None = None
        self._stop_event = threading.Event()
        self._write_lock = threading.Lock()

    @staticmethod
    def list_ports() -> list[str]:
        ports = []
        for port in serial.tools.list_ports.comports():
            if "USB" in port.description or "Serial" in port.description:
                ports.append(f"{port.device} - {port.description}")
        return ports

    def connect(
        self,
        port_name: str,
        baud_rate: int,
        data_bits: int,
        parity_name: str,
        stop_bits_value: str,
        flow_mode: str,
        terminator_mode: str,
        custom_terminator: str,
    ) -> None:
        if self.device is not None and self.device.is_open:
            raise RuntimeError("Already connected")

        parity_map = {
            "N": serial.PARITY_NONE,
            "E": serial.PARITY_EVEN,
            "O": serial.PARITY_ODD,
        }

        if flow_mode == "H":
            flow_kwargs = {"xonxoff": False, "rtscts": True, "dsrdtr": True}
        elif flow_mode == "S":
            flow_kwargs = {"xonxoff": True, "rtscts": False, "dsrdtr": False}
        else:  # "N" (None) or "M" (Manual) - no automatic flow control
            flow_kwargs = {"xonxoff": False, "rtscts": False, "dsrdtr": False}

        self.terminator = self._terminator_bytes(terminator_mode, custom_terminator)
        self.device = serial.Serial(
            port_name,
            baudrate=baud_rate,
            bytesize=serial.SEVENBITS if data_bits == 7 else serial.EIGHTBITS,
            parity=parity_map.get(parity_name.upper(), serial.PARITY_NONE),
            stopbits=serial.STOPBITS_TWO if stop_bits_value == "2" else serial.STOPBITS_ONE,
            timeout=1,
            **flow_kwargs,
        )
        self._stop_event.clear()
        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.reader_thread.start()
        self.on_status(f"Connected to {port_name}")

    def disconnect(self) -> None:
        self._stop_event.set()
        self._cancel_ping_timer()
        if self.device is not None:
            try:
                self.device.close()
            except Exception:
                pass
        self.device = None
        self.ping_sent_time = None
        self.on_status("Disconnected")

    def set_manual_lines(self, rts: bool, dtr: bool) -> None:
        if self.device is None or not self.device.is_open:
            return
        self.device.rts = rts
        self.device.dtr = dtr

    def get_cts(self) -> bool:
        """Get current CTS (Clear To Send) input line state."""
        if self.device is None or not self.device.is_open:
            return False
        try:
            return bool(self.device.cts)
        except Exception:
            return False

    def get_dsr(self) -> bool:
        """Get current DSR (Data Set Ready) input line state."""
        if self.device is None or not self.device.is_open:
            return False
        try:
            return bool(self.device.dsr)
        except Exception:
            return False

    def auto_detect(self, port_name: str) -> dict | None:
        """Auto-detect baud rate and serial parameters.
        
        Returns dict with 'baud_rate' if successful, None if detection fails.
        Also calls on_status callback with progress updates.
        """
        if self.device is not None and self.device.is_open:
            self.on_status("Disconnect first before auto-detect")
            return None
        
        self.on_status("Starting auto-detect...")
        time.sleep(0.5)
        
        for baud in COMMON_BAUDS:
            self.on_status(f"Testing {baud} baud...")
            try:
                test_device = serial.Serial(
                    port_name,
                    baudrate=baud,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0.5,
                    xonxoff=False,
                    rtscts=False,
                    dsrdtr=False,
                )
                
                # Send test character (U = 0x55 = 01010101)
                test_device.write(b"U")
                time.sleep(0.3)
                
                # Try to read response
                response = test_device.read(10)
                if response:
                    # Check if we got reasonable ASCII
                    try:
                        decoded = response.decode("ascii", errors="ignore").strip()
                        if decoded and any(c.isalnum() or c in "U\r\n" for c in decoded):
                            self.on_status(f"✓ Found! Baud rate: {baud}")
                            time.sleep(0.3)
                            test_device.close()
                            return {"baud_rate": baud}
                    except Exception:
                        pass
                
                test_device.close()
                time.sleep(0.1)
            except Exception as exc:
                self.on_status(f"Error testing {baud}: {exc}")
                continue
        
        self.on_status("Auto-detect failed. Try manual settings.")
        return None

    def send_message(self, text: str) -> None:
        if not text:
            return
        if self.device is None or not self.device.is_open:
            raise RuntimeError("Connect to a serial port first")

        if text == "ping":
            if self.ping_timer_obj is not None:
                raise RuntimeError("Already waiting for pong")
            self.ping_sent_time = time.perf_counter()
            timeout_seconds = self.device.timeout if getattr(self.device, "timeout", None) else 2.0
            self.ping_timer_obj = threading.Timer(timeout_seconds, self._on_ping_timeout)
            self.ping_timer_obj.start()

        payload = text.encode("ascii", errors="ignore") + self.terminator
        with self._write_lock:
            self.device.write(payload)
        self.on_sent(text)

    def send_binary(self, data: bytes) -> None:
        """Send raw binary data."""
        if not data:
            return
        if self.device is None or not self.device.is_open:
            raise RuntimeError("Connect to a serial port first")
        
        payload = data + self.terminator
        with self._write_lock:
            self.device.write(payload)
        hex_preview = data[:16].hex(" ")
        if len(data) > 16:
            hex_preview += f"... (+{len(data) - 16} bytes)"
        self.on_sent(f"[binary: {hex_preview}]")

    def _on_ping_timeout(self) -> None:
        self.ping_timer_obj = None
        self.ping_sent_time = None
        self.on_received("Ping timeout: no pong received")

    def _cancel_ping_timer(self) -> None:
        if self.ping_timer_obj is not None:
            try:
                self.ping_timer_obj.cancel()
            except Exception:
                pass
        self.ping_timer_obj = None

    def _read_loop(self) -> None:
        buffer = bytearray()
        while not self._stop_event.is_set() and self.device is not None and self.device.is_open:
            try:
                waiting = self.device.in_waiting
                if waiting > 0:
                    buffer.extend(self.device.read(waiting))
                    while self.terminator and self.terminator in buffer:
                        raw_message, remainder = buffer.split(self.terminator, 1)
                        buffer = bytearray(remainder)
                        
                        # Try to decode as ASCII, but if it fails or contains non-printable chars, use hex
                        try:
                            decoded = raw_message.decode("ascii").strip()
                            is_binary = not all(32 <= ord(c) < 127 or c in "\t\n\r" for c in decoded)
                        except UnicodeDecodeError:
                            is_binary = True
                            decoded = None
                        
                        if is_binary or decoded is None:
                            hex_str = raw_message.hex(" ")
                            message = f"[HEX: {hex_str}]"
                        else:
                            message = decoded
                        
                        if not message:
                            continue
                        
                        # Check for ping/pong using raw decoded string
                        if decoded is not None:
                            if decoded == "ping":
                                self._write_raw(b"pong" + self.terminator)
                            elif decoded == "pong":
                                elapsed = None
                                if self.ping_sent_time is not None:
                                    elapsed = time.perf_counter() - self.ping_sent_time
                                self._cancel_ping_timer()
                                self.ping_sent_time = None
                                if elapsed is not None:
                                    self.on_received(f"Ping time: {elapsed:.3f} seconds")
                                else:
                                    self.on_received("Received pong with no pending ping")
                        self.on_received(message)
                time.sleep(0.01)
            except serial.SerialException as exc:
                self.on_received(f"Serial error: {exc}")
                break
            except Exception as exc:
                self.on_received(f"Reader error: {exc}")
                break

    def _write_raw(self, payload: bytes) -> None:
        if self.device is None or not self.device.is_open:
            return
        with self._write_lock:
            self.device.write(payload)

    @staticmethod
    def _terminator_bytes(mode: str, custom_terminator: str) -> bytes:
        selection = mode.strip().upper()
        if selection == "NONE":
            return b""
        if selection == "CR":
            return b"\r"
        if selection == "LF":
            return b"\n"
        if selection == "CRLF":
            return b"\r\n"
        custom = custom_terminator.encode("ascii", errors="ignore").decode("unicode_escape")
        if len(custom) == 1:
            return custom.encode("ascii")
        return b"\n"