import serial.tools.list_ports
import serial
from typing import List
import threading

def filter_ports() -> List[serial.tools.list_ports.ListPortInfo]:
    ports = serial.tools.list_ports.comports()
    filtered_ports = []
    for port in ports:
        if "USB" in port.description or "Serial" in port.description:
            filtered_ports.append(port)
    return filtered_ports

def select_port(filtered_ports: List[serial.tools.list_ports.ListPortInfo]) -> serial.tools.list_ports.ListPortInfo:
    print("available ports:")
    for port in filtered_ports:
        i = filtered_ports.index(port) + 1
        print(f"{i} Port: {port.device}")
    selected_port = input("enter the number of the port you want to use: ")
    return filtered_ports[int(selected_port) -1]

def read_serial_settings() -> tuple[int, any, any, any, dict[str, bool], bool]: 
    try:
        speed = int(input("\nenter the baud rate (150-115200, 9600 is default): "))
        if speed < 150 or speed > 115200:
            speed = 9600
    except ValueError:
        print("defaulting to 9600")
        speed = 9600
            
    match input("\nenter the character size (7 or 8), 8 is default: ").strip():
        case "7":
            character_size = serial.SEVENBITS
        case "8":
            character_size = serial.EIGHTBITS
        case _:
            print("defaulting to 8 bit")
            character_size = serial.EIGHTBITS

    match input("\nenter the parity (N, E, O), N is default: ").strip().upper():
        case "N":
            parity = serial.PARITY_NONE
        case "E":
            parity = serial.PARITY_EVEN
        case "O":
            parity = serial.PARITY_ODD
        case _:
            print("defaulting to none")
            parity = serial.PARITY_NONE

    match input("\nenter the number of stop bits (1 or 2), 1 is default: ").strip():
        case "1":
            stop_bits = serial.STOPBITS_ONE
        case "2":
            stop_bits = serial.STOPBITS_TWO
        case _:
            print("defaulting to 1")
            stop_bits = serial.STOPBITS_ONE

    flow_mode = input("\nenter the flow control (N - none, H - hardware, S - software, M - manual), N is default: ").strip().upper()
    manual_mode = flow_mode == "M"
    match flow_mode:
        case "N":
            flow_kwargs = {"xonxoff": False, "rtscts": False, "dsrdtr": False}
        case "H":
            flow_kwargs = {"xonxoff": False, "rtscts": True, "dsrdtr": True}
        case "S":
            flow_kwargs = {"xonxoff": True, "rtscts": False, "dsrdtr": False}
        case "M":
            flow_kwargs = {"xonxoff": False, "rtscts": False, "dsrdtr": False}
        case _:
            print("invalid flow control, defaulting to none")
            flow_kwargs = {"xonxoff": False, "rtscts": False, "dsrdtr": False}
    
    return speed, character_size, parity, stop_bits, flow_kwargs, manual_mode


def serial_builder(port: serial.tools.list_ports.ListPortInfo) -> tuple[serial.Serial, bool]:
    speed, character_size, parity, stop_bits, flow_kwargs, manual_mode = read_serial_settings()
    device = serial.Serial(
        port.device,
        baudrate=speed,
        bytesize=character_size,
        parity=parity,
        stopbits=stop_bits,
        timeout=1,
        **flow_kwargs
    )
    if manual_mode:
        print("manual flow control enabled, use device.setXON() and device.setRTS() to control flow")
    return device, manual_mode

def manual_control_loop(ser):
    print("commands: rts on/off, dtr on/off, status, q")
    while True:
        cmd = input("manual> ").strip().lower()
        match cmd:
            case "rts on":
                ser.rts = True
            case "rts off":
                ser.rts = False
            case "dtr on":
                ser.dtr = True
            case "dtr off":
                ser.dtr = False
            case "status":
                print(f"RTS={ser.rts} DTR={ser.dtr} CTS={ser.cts} DSR={ser.dsr}")
            case "q":
                break    
    
def select_terminator() -> bytes:
    match input("\nenter the terminator (0 - none, 1 - CR, 2 - LF, 3 - CRLF, 4 - custom one character), LF is default: ").strip().upper():
        case "0":
            return b""
        case "1":
            return b"\r"
        case "2":
            return b"\n"
        case "3":
            return b"\r\n"
        case "4": 
            custom = input("enter the custom terminator (e.g. $): ")
            custom_processed = custom.encode('ascii').decode('unicode_escape')
            if len(custom_processed) == 0:
                print("invalid custom terminator, defaulting to LF")
                return b"\n"
            elif len(custom_processed) > 1:
                print("custom terminator max length is 1, string will be truncated to 1 character")
                return custom_processed[:1].encode('ascii')
            return custom_processed.encode('ascii')
        
        case _:
            print("invalid terminator, defaulting to none")
            return b"\n"

def write_loop(device: serial.Serial, text: str, terminator: bytes):
    try:
        data_byes = text.encode('ascii') + terminator
        device.write(data_byes)
    except serial.SerialException as e:
        print(f"error writing to serial port: {e}")

def read_thread(device: serial.Serial):
    while True:
        try:
            if device.in_waiting > 0 and device.is_open:
                data_bytes = device.read(device.in_waiting)
                data_decoded = data_bytes.decode('ascii', errors='ignore')
                print(f"r: {data_decoded}")
        except serial.SerialException:
            print("serial exception, stopping read thread")
            break

def main():
    filtered_ports = filter_ports()
    if not filtered_ports:
        print("no ports found")
        return
    selected_port = select_port(filtered_ports)
    print(f"selected port: {selected_port.device}")
    
    device, manual_mode = serial_builder(selected_port) # port is already opened by serial.Serial() constructor, so we can use it immediately
    print(device)
    if manual_mode:
        manual_control_loop(device)
    terminator = select_terminator()
    print(f"selected terminator: {terminator}")
    #device.open() # serial.Serial() already opens the port, so this is not needed
    threading.Thread(target=read_thread, args=(device,), daemon=True).start()
    print("you can start typing messages to send, type 'exit' to quit")
    while True:
        text = input()
        if text.lower() == "exit":
            break
        write_loop(device, text, terminator)
    device.close()

if __name__ == "__main__":
    main()

