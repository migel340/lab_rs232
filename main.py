from ctypes import sizeof

import serial.tools.list_ports
import serial

def filter_ports() -> list:
    ports = serial.tools.list_ports.comports()
    filtered_ports = []
    for port in ports:
        if "USB" in port.description or "Serial" in port.description:
            filtered_ports.append(port)
    return filtered_ports

def select_port(filtered_ports: list) -> str:
    print("available ports:")
    for port in filtered_ports:
        i = filtered_ports.index(port) + 1
        print(f"{i} Port: {port.device}")
    selected_port = input("enter the number of the port you want to use: ")
    return filtered_ports[int(selected_port) -1]


def main():
    filtered_ports = filter_ports()
    if not filtered_ports:
        print("no ports found")
        return
    selected_port = select_port(filtered_ports)
    print(f"selected port: {selected_port.device}")
    

    
if __name__ == "__main__":
    main()