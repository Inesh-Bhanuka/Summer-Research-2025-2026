import smbus2
import time
import threading
import subprocess
import argparse
import json 

# Load data from json into config
def load_config(path="zcu102_config.json"):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find {path}")
        return None

config = load_config()

# Setup constants based of JSON data
BUS_NUMBER = config['board_meta']['i2c_bus_id']
VCCINT_RAIL = int(config['rails']['VCCINT']['i2c_address'], 16)
VCCBRAM_RAIL = int(config['rails']['VCCBRAM']['i2c_address'], 16)
VOLTAGE_RAIL = VCCINT_RAIL # Change this depending on what rail we want to look at, for our experiments we want VCCINT
READ_VOLTAGE_CMD = int(config['rails']['VCCINT']['commands']['read_vout'], 16)
READ_CURRENT_CMD = int(config['rails']['VCCINT']['commands']['read_iout'], 16)
SCALE_FACTOR = config['rails']['format']['scale_factor']
if VOLTAGE_RAIL == VCCINT_RAIL:
    DESTINATION_REGISTER = int(config['rails']['VCCINT']['commands']['vout_cmd'], 16)
    ZCU102_NOM = config['rails']['VCCINT']['limits']['max_voltage_v']
    LOWER_VOLTAGE_LIMIT = config['rails']['VCCINT']['limits']['min_voltage_v']
    UPPER_VOLTAGE_LIMIT = config['rails']['VCCINT']['limits']['max_voltage_v']
else:
    DESTINATION_REGISTER = int(config['rails']['VCCBRAM']['commands']['vout_cmd'], 16)
    ZCU102_NOM = config['rails']['VCCBRAM']['limits']['max_voltage_v']
    LOWER_VOLTAGE_LIMIT = config['rails']['VCCBRAM']['limits']['min_voltage_v']
    UPPER_VOLTAGE_LIMIT = config['rails']['VCCBRAM']['limits']['max_voltage_v']
NOMINAL_VOLTAGE = ZCU102_NOM

# This is to pass the argument to switch between power advantage and UART
parser = argparse.ArgumentParser(description='PA or UART')
parser.add_argument('--threaded', type=str, required=False, help='see source for details')
# parser.add_argument('--threaded', type=str, required=True, help='see source for details')
# if true, this --threaded argument will run in a way to allow UART to capture the output
# if false, this --threaded argument will run without being threaded to allow power advantage to capture the output

args = parser.parse_args()
print(f"Option: {args.threaded}")
if args.threaded:
    isThreaded = args.threaded.lower() == 'true'
    print(f"isThreaded: {isThreaded} {type(isThreaded)}")
else:
    isThreaded = False # default
# define out here
stop_event = threading.Event()

def readData(bus, device_address, location):
    try:
        # Read the data from the device
        data = bus.read_word_data(device_address, location)
        return data
    except OSError as e:
        print(f"Error reading from device at address {hex(device_address)}: {e}")
        return None

def readLoop(bus, location):
        alt = readData(bus, VOLTAGE_RAIL, location)
        if alt is not None:
            print(f"{location}: {hex(alt)} || {alt} Value: {alt/SCALE_FACTOR}V")

def readAll(bus, voltageLocation, currentLocation):
    alt = readData(bus, VOLTAGE_RAIL, voltageLocation)
    alt2 = readData(bus, VOLTAGE_RAIL, currentLocation)
    if alt is not None and alt2 is not None:
        print(f"Power: {alt/SCALE_FACTOR:.2f}V x {alt2/SCALE_FACTOR:.2f}A = {(alt/SCALE_FACTOR)*(alt2/SCALE_FACTOR):.2f}W")
        # print(f"Power: {alt/SCALE_FACTOR:.2f}V ({alt}) x {alt2/SCALE_FACTOR:.2f}A ({alt2})= {(alt/SCALE_FACTOR)*(alt2/SCALE_FACTOR):.2f}W") # debug


def getReadingsBus(busNumber, safe = True):
    # safe = True means that we are threading and safe = False means we are not
    bus = smbus2.SMBus(busNumber)
    if not safe:
        readAll(bus, READ_VOLTAGE_CMD, READ_CURRENT_CMD)
        return # we want to get out of here
    try:
        while not stop_event.is_set() and safe:
            readAll(bus, READ_VOLTAGE_CMD, READ_CURRENT_CMD)
            time.sleep(0.25)
    except KeyboardInterrupt:
        stop_event.set()

def runCommand(cmd, cwd):
    subprocess.run(cmd, shell=True, cwd=cwd)

def stop():
    stop_event.set()

def undervoltingLoop(initialvoltage, cwd, cmd, iter, step):
    volt = initialvoltage
    for _ in range(iter):
        print("==============================")
        print(f"Voltage: {volt:.2f}")
        print("==============================")
        setVoltage(smbus2.SMBus(BUS_NUMBER), VOLTAGE_RAIL, DESTINATION_REGISTER, volt) #COMMENT OUT IF DONT WANT TO UNDERVOLT
        runCommand(cmd, cwd)
        volt -= step
    setVoltage(smbus2.SMBus(BUS_NUMBER), VOLTAGE_RAIL, DESTINATION_REGISTER, NOMINAL_VOLTAGE) # reset back to normal
    stop()

def runCompendium():

    # open file
    f=open("compendium.txt","r")
    for v in f:
        # for each line in the file read and set the voltage to it
        setVoltage(smbus2.SMBus(BUS_NUMBER), VOLTAGE_RAIL, DESTINATION_REGISTER, float(v.strip()))  # reset back to normal
        time.sleep(0.5) # change as needed
    f.close()

    setVoltage(smbus2.SMBus(BUS_NUMBER), VOLTAGE_RAIL, DESTINATION_REGISTER, NOMINAL_VOLTAGE) # reset back to normal
    stop()

def runWorkload(model_name):
    # Check for Compendium case as this is handled differently
    if model_name == "Compendium":
        runCompendium()
        return

    # Get the model details from the JSON
    if model_name not in config['workloads']:
        print(f"Error: Model {model_name} not found in config!")
        return

    job = config['workloads'][model_name]
    
    # Construct the path depending on chosen model
    cwd = job['cwd']
    cmd = f"{job['executable']} {job['args']}"
    
    # Set experiment parameters, SHOULD MOVE INTO JSON?
    NUM_STEPS = 2
    STEP_SIZE = 0.01
    
    # Run
    start_voltage = job.get('nominal_voltage', NOMINAL_VOLTAGE)
    undervoltingLoop(start_voltage, cwd=cwd, cmd=cmd, iter=NUM_STEPS, step=STEP_SIZE)

def setVoltage(bus, address, destination, voltageDecimal):
    # This needs to be converted to a value and written into hex, the conversion is dependent on the mode of the board from JSON
    if voltageDecimal < LOWER_VOLTAGE_LIMIT or voltageDecimal > UPPER_VOLTAGE_LIMIT: # out of bounds
        raise Exception(f"Voltage must be between {LOWER_VOLTAGE_LIMIT} and {UPPER_VOLTAGE_LIMIT}, entered voltage: {voltageDecimal}")
    try:
        bus.write_word_data(address, destination, (int(voltageDecimal*SCALE_FACTOR)))
        return True
    except OSError as e:
        print(f"Error writing to device at address {hex(address)}: {e}")
        return False

def selectedModel(model_name, threaded=False):
    # Simplified method of calling models depending on whether it was a threaded call or not
    def task():
        runWorkload(model_name)

    if threaded:
        return task # Lets the Thread call the function instead 
    else:
        task() # Run it immediately if not threaded

def main():
    # Get models from JSON 
    available_models = list(config['workloads'].keys())
    available_models.append("Compendium") # Special Case

    print("=======================")
    print("=== Model Selection ===")
    for index, name in enumerate(available_models):
        print(f"{index + 1}. {name}") # Print each model in a list format
    print("=======================")
    
    default_model = "SqueezeNet" 
    
    # Get user input
    model_choice = input(f"Please select a number or press Enter for {default_model}: ")
    
    if model_choice.isdigit():
        idx = int(model_choice) - 1
        if 0 <= idx < len(available_models):
            model = available_models[idx]
        else:
            raise Exception(f"{model_choice} is an invalid choice")
    else:
        model = default_model

    print("==============================")
    print(f"=== Using Model: {model} ===")
    print("==============================")
    
    setVoltage(smbus2.SMBus(BUS_NUMBER), VOLTAGE_RAIL, DESTINATION_REGISTER, NOMINAL_VOLTAGE)
    
    if isThreaded:
        # shellThread = threading.Thread(target=runCommand, args=(shellCommand,directory,))
        monitorThread = threading.Thread(target=getReadingsBus, args=(BUS_NUMBER, True,), daemon=True)
        shellThread = threading.Thread(target=selectedModel(model, threaded=True), daemon=True)
        print("Threads started")
        monitorThread.start()
        shellThread.start()
        try:
            while monitorThread.is_alive() or shellThread.is_alive():
                monitorThread.join(timeout=1)
                shellThread.join(timeout=1)

        except KeyboardInterrupt:
            print("Shutting down")
            # end all other processes
            setVoltage(smbus2.SMBus(BUS_NUMBER), VOLTAGE_RAIL, DESTINATION_REGISTER, NOMINAL_VOLTAGE)  # reset back to normal
            exit(1)
    else: # not threaded
        print("Running the selected model")
        selectedModel(model)

    print("==============================")
    print("==========Finished============")
    print("==============================")

if __name__ == "__main__":
    main()
