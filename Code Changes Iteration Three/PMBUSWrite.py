
#imports
import time
import smbus2

# defines
# Input output readings, these need to be confirmed
VOUT_LOCATION = 0
IOUT_LOCATION = 0
VIN_LOCATION = 0x16
IIN_LOCATION = 0x17 # Doesn't exist?
DEVICE_ADDRESS = 0x13  # Example device address, change as needed
BUS_ADDRESS = 0


# Power calcuulations
# Power = Voltage * Current

# efficiency = Power out / Power in

# PMBus is little ndian

# exit()
def findDevices():
    bus = smbus2.SMBus(4) # Not sure if we will change 1
    print("Scanning for devices")
    devices = []
    for address in range(0x03, 0x20):
        try:
            bus.write_quick(address) # Check if the device is present
            devices.append(address)
            print(f"Device found at address: {hex(address)}")
        except (OSError, IOError):
            # Device not found, continue scanning
            continue
    bus.close()
    print("Try again")
    for bus_num in range(0, 23):
        try:
            bus = smbus2.SMBus(bus_num)
            bus.write_quick(0x1A)
            print(f"Found device at 0x1A on bus {bus_num}")
        except:
            continue

    return devices

def read_data(bus, device_address, location):
    try:
        # Read the data from the device
        data = bus.read_word_data(device_address, location)
        return data
    except OSError as e:
        print(f"Error reading from device at address {hex(device_address)}: {e}")
        return None

def write_data(bus, device_address, location, data):
    try:
        bus.write_word_data(device_address, location, data)
        return True
    except OSError as e:
        print(f"Error writing to device at address {hex(device_address)}: {e}")
        return False

def test():
    # find the buses that are available
    device_list = findDevices()

    if not device_list:
        print("No devices found.")
        exit(1)


    # working buses? a, b. 10, 11, 13, 14, 15, 16, 17, 18, 1a, 1b, 1d

    # we have at least one device
    print(f"Found {len(device_list)} devices.")
    for device in device_list:
        print(f"Device address: {hex(device)}")
    exit()

# test() # uncomment when checking the bus
# selecting the first device
bus = smbus2.SMBus(4)

# we want the bus at 0x13 and 0x14 which translate to 0x40 and 0x41 respectively??
# vccintbus = smbus2.SMBus(4)
# vbrambus = smbus2.SMBus(0x14)
def setVoltage(bus, address, destination, voltageDecimal):
    """
    :param bus: The bus that the sensor is connected to
    :param address: The address of the rail that we want to read
    :param destination: The actual value inside the rail (See datasheet)
    :param voltageDecimal: The voltage to be written to the rail AS A DECIMAL
    :return: None
    """

    # voltageDecimal # This needs to be converted to a value between 0 and 4096 and written into hex
    if voltageDecimal < 0 or voltageDecimal > 1: # out of bounds
        raise Exception(f"Voltage must be between 0 and 1, entered voltage: {voltageDecimal}")

    try:
        bus.write_word_data(address, destination, (int(voltageDecimal*4096)))
        return True
    except OSError as e:
        print(f"Error writing to device at address {hex(address)}: {e}")
        return False

setVoltage(smbus2.SMBus(4), 0x13, 0x21, 0.85)  # reset back to normal

print("Logging data...")
count = 1 # only run the script for ~ 10s
while count > 0:

    # print(f"{hex(VOUT_LOCATION)}: {read_data(bus,DEVICE_ADDRESS,0x8B)}")
    # for location in range(0xFF):
    #     try:
    #         alt = read_data(bus, 0x13, location) # This is a 12-bit ADC reading
    #         print(f"0x13 at location ({hex(location)}): {hex(alt)} || {alt}")
    #     except Exception as e:
    #         # print(f"Error reading from device at location {hex(location)}: {e}")
    #         continue

    def rloop(bus, location):
        alt = read_data(bus, 0x13, location)
        if alt is not None:
            print(f"{location}: {hex(alt)} || {alt}")

    # attempting to write

    # write_data(bus, 0x13, 0x21, 0x0800) # down by literally nothing
    time.sleep(1) # delay
    rloop(bus,0x8B) # VOutmode
    rloop(bus,0x8C) # VOUTCommand
    rloop(bus,0x24) # VOUTMax
    rloop(bus,0x8b) # Read VOUT


    # write_data(bus, 0x13, 0x21, 0xd99) # just a little under nominal
    print("Done")
    for i in range(20):
        time.sleep(0.25)
        balt = read_data(bus, 0x13, 0x8C)
        if balt is not None:
            print(f"{hex(balt)}")
    # every other value increment 1
    # hardset(bus)
    # we need to check if the readings are valid
    # power_out = None
    # power_in = None
    # if v_out_reading is None or i_out_reading is None:
    #     print("Error reading output data")
    # else:
    #     power_out = v_out_reading * i_out_reading # calculate instantaneous power out


    # if v_in_reading is None or i_in_reading is None:
    #    print("Error reading data from device.")
    # else:
    #    power_in = v_in_reading * i_in_reading # calculate instantaneous power in


    # if power_out is not None and power_in is not None: # we had a successful read
    #    efficiency = (power_out / power_in) * 100
    #    print(f"Efficiency: {efficiency:.2f}%")

    # else:
    #    print("Error calculating efficiency: Check above for details.")

    # we can print out everything regardless This doesn't consider
    # print(f"Efficiency: {efficiency:.2f}% | Vout: {v_out_reading}V | Iout: {i_out_reading}A | Vin: {v_in_reading}V | Iin: {i_in_reading}A | Pout: {power_out}W | Pin: {power_in}W")
    time.sleep(0.25) # wait for 1 second before the next reading
    count-=1