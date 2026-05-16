import serial.tools.list_ports
import serial
from typing import List

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


def serial_builder(port: serial.tools.list_ports.ListPortInfo) -> serial.Serial:
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
    
def main():
    filtered_ports = filter_ports()
    if not filtered_ports:
        print("no ports found")
        return
    selected_port = select_port(filtered_ports)
    print(f"selected port: {selected_port.device}")
    
    device, manual_mode = serial_builder(selected_port)
    print(device)
    if manual_mode:
        manual_control_loop(device)


if __name__ == "__main__":
    main()