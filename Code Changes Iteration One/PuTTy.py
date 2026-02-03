import serial
import serial.tools.list_ports
import threading
import sys
import time


def list_ports():
    ports = serial.tools.list_ports.comports()
    print("Available Ports:")
    for i, port in enumerate(ports):
        print(f" {i + 1}: {port.device} - {port.description}")
    return ports


def read_from_port(ser, stop_event):
    while not stop_event.is_set():
        try:
            data = None
            if ser.in_waiting:
                data = ser.readline().decode('utf-8', errors='ignore').strip()
            if data:
                print(f"\r{data}\n> ", end='')
                f = open("log.txt", "a")
                f.write(data + '\n') # add a newline
                f.close()

        except (serial.SerialException, OSError) as e:
            print(f"\nConnection lost: {e}")
            stop_event.set()  # Signal main thread to reconnect
            break
        except Exception as e:
            print(f"\nUnexpected read error: {e}")
            stop_event.set()
            break


def connect(port, baud_rate):
    while True:
        try:
            ser = serial.Serial(port, baud_rate, timeout=1)
            print(f"Connected to {port} at {baud_rate} baud.")
            return ser
        except Exception as e:
            print(f"Trying to reconnect... ({e})")
            time.sleep(3)


def main():
    ports = list_ports()
    if not ports:
        print("No serial ports found.")
        sys.exit(0)
    choice = int(input("Choose port number: ")) - 1
    try:
        baud_rate = int(input("Enter baud rate (default 115200): ") or "115200")
    except ValueError:
        print(f"Invalid baud rate entered. Using 115200 instead")
        baud_rate = 115200 # set default
    port = ports[choice].device

    stop_event = threading.Event()
    ser = connect(port, baud_rate)
    threading.Thread(target=read_from_port, args=(ser, stop_event), daemon=True).start()
    print("Type messages. Ctrl + C to exit.")
    while True:
        try:
            if stop_event.is_set():
                ser.close()
                print("Reconnecting after disconnect...")
                stop_event.clear()
                threading.Thread(target=read_from_port, args=(ser, stop_event), daemon=True).start()
            data = input("> ")
            ser.write((data + "\n").encode('utf-8'))
        except KeyboardInterrupt:
            f = input("Are you sure you want to exit the program? [y/N]")
            f = f.lower()
            if f == "y":
                ser.close()
                break
            else:
                # send a Ctrl + C
                ser.write(b'\x03')
        except (serial.SerialException, OSError) as e:
            print(f"\n Send error: {e}")
            stop_event.set()
        except Exception as e:
            print(f"Unexpected send error: {e}")
            stop_event.set()


if __name__ == "__main__":
    main()