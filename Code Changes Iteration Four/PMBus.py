import smbus2
import time
import threading
import subprocess
import argparse

# constants
BUS_NUMBER = 4
VCCINT_RAIL = 0x13
VCCBRAM_RAIL = 0x14
VOLTAGE_RAIL = VCCINT_RAIL
DESTINATION_REGISTER = 0x21
ZCU102_NOM = 0.85
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

def readLoop(bus, rail, location):
        alt = readData(bus, VOLTAGE_RAIL, location)
        if alt is not None:
            print(f"{location}: {hex(alt)} || {alt} Value: {alt/4096}V")

def readAll(bus, voltageLocation, currentLocation):
    alt = readData(bus, VOLTAGE_RAIL, voltageLocation)
    alt2 = readData(bus, VOLTAGE_RAIL, currentLocation)
    if alt is not None and alt2 is not None:
        print(f"Power: {alt/4096:.2f}V x {alt2/4096:.2f}A = {(alt/4096)*(alt2/4096):.2f}W")
        # print(f"Power: {alt/4096:.2f}V ({alt}) x {alt2/4096:.2f}A ({alt2})= {(alt/4096)*(alt2/4096):.2f}W") # debug


def getReadingsBus(busNumber, safe = True):
    # safe = True means that we are threading and safe = False means we are not
    bus = smbus2.SMBus(busNumber)
    if not safe:
        readAll(bus, 0x8B, 0x8C)
        return # we want to get out of here
    try:
        while not stop_event.is_set() and safe:
            readAll(bus, 0x8B, 0x8C)
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
        # setVoltage(smbus2.SMBus(BUS_NUMBER), VOLTAGE_RAIL, DESTINATION_REGISTER, volt)
        runCommand(cmd, cwd)
        volt -= step
    setVoltage(smbus2.SMBus(4), VOLTAGE_RAIL, DESTINATION_REGISTER, NOMINAL_VOLTAGE) # reset back to normal
    stop()

def runResNet18():
    # hypothetically this does the same
    cwd = "./Vitis-AI/examples/vai_library/samples/classification"
    ResNet18Command = "./test_jpeg_classification resnet18_pt ~/Vitis-AI/examples/vai_library/samples/classification/images/002.JPEG"
    NUM_STEPS = 2
    step = 0.01
    undervoltingLoop(NOMINAL_VOLTAGE, cwd=cwd, cmd = ResNet18Command, iter=NUM_STEPS, step=step)

def runResNet50():
    # hypothetically this does the same
    cwd = "./Vitis-AI/examples/vai_runtime/resnet50"
    resnet50cmd = "./resnet50 /usr/share/vitis_ai_library/models/resnet50/resnet50.xmodel"
    NUM_STEPS = 2
    step = 0.01
    undervoltingLoop(NOMINAL_VOLTAGE, cwd=cwd, cmd = resnet50cmd, iter=NUM_STEPS, step=step)

def runSqueezeNet():
    # hypothetically this does the same
    cwd = "./Vitis-AI/examples/vai_runtime/squeezenet_pytorch"
    SqueezeNetcmd = "./squeezenet_pytorch /usr/share/vitis_ai_library/models/squeezenet_pt/squeezenet_pt.xmodel"
    NUM_STEPS = 2
    step = 0.01
    undervoltingLoop(NOMINAL_VOLTAGE, cwd=cwd, cmd = SqueezeNetcmd, iter=NUM_STEPS, step=step)

def runInception():
    # hypothetically this does the same
    cwd = "./Vitis-AI/examples/vai_runtime/inception_v1_mt_py"
    Inceptioncmd = "/usr/bin/python3 inception_v1.py 1 /usr/share/vitis_ai_library/models/inception_v1_tf/inception_v1_tf.xmodel"
    NUM_STEPS = 2
    step = 0.01
    undervoltingLoop(NOMINAL_VOLTAGE, cwd=cwd, cmd = Inceptioncmd, iter=NUM_STEPS, step=step)

def runCompendium():

    # open file
    f=open("compendium.txt","r")
    for v in f:
        # for each line in the file read and set the voltage to it
        setVoltage(smbus2.SMBus(4), VOLTAGE_RAIL, DESTINATION_REGISTER, float(v.strip()))  # reset back to normal
        time.sleep(0.5) # change as needed
    f.close()

    setVoltage(smbus2.SMBus(4), VOLTAGE_RAIL, DESTINATION_REGISTER, NOMINAL_VOLTAGE) # reset back to normal
    stop()

def setVoltage(bus, address, destination, voltageDecimal):
    # This needs to be converted to a value between 0 and 4096 and written into hex
    if voltageDecimal < 0 or voltageDecimal > 1: # out of bounds
        raise Exception(f"Voltage must be between 0 and 1, entered voltage: {voltageDecimal}")
    try:
        bus.write_word_data(address, destination, (int(voltageDecimal*4096)))
        return True
    except OSError as e:
        print(f"Error writing to device at address {hex(address)}: {e}")
        return False

def selectedModel(model, threaded=False):
    if threaded:
        if model=="ResNet50":
            return runResNet50
        elif model=="ResNet18":
            return runResNet18
        elif model=="SqueezeNet":
            return runSqueezeNet
        elif model=="Inception":
            return runInception
        elif model=="Compendium":
            return runCompendium
    else:
        if model=="ResNet50":
            return runResNet50()
        elif model=="ResNet18":
            return runResNet18()
        elif model=="SqueezeNet":
            return runSqueezeNet()
        elif model=="Inception":
            return runInception()
        elif model=="Compendium":
            return runCompendium()


    raise Exception(f"Model {model} not supported")

def main():

    defaultmodel = "SqueezeNet"

    print("=======================")
    print("=== Model Selection ===")
    print("1. ResNet-50   ")
    print("2. ResNet-18   ")
    print("3. SqueezeNet  ")
    print("4. Inception   ")
    print("5. Compendium  ")
    print("=======================")
    modelchoice = input(f"Please select a model number or \"\" to use {defaultmodel}: ")
    if modelchoice.isnumeric(): # if it is numeric
        mchoice = int(modelchoice)
        if mchoice == 1:
            model = "ResNet50"
        elif mchoice == 2:
            model = "ResNet18"
        elif mchoice == 3:
            model = "SqueezeNet"
        elif mchoice == 4:
            model = "Inception"
        elif mchoice == 5:
            model = "Compendium"
        else:
            raise Exception(f"{mchoice} is an invalid choice")
    else: # if it is not numeric (either blank or other input)
        print(f"Using default model: {defaultmodel}")
        model = defaultmodel

    print("==============================")
    print(f"=== Using Model: {model} ===")
    print("==============================")
    shellCommand = "./test_performance_facedetect densebox_320_320 test_performance_facedetect.list -t 3 -s 20" # run with 3 threads for 20 seconds

    setVoltage(smbus2.SMBus(BUS_NUMBER), VOLTAGE_RAIL, DESTINATION_REGISTER, NOMINAL_VOLTAGE)
    directory = "./Vitis-AI/examples/vai_library/samples/facedetect"

    if isThreaded:
        # shellThread = threading.Thread(target=runCommand, args=(shellCommand,directory,))
        monitorThread = threading.Thread(target=getReadingsBus, args=(4, True,), daemon=True)
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
            setVoltage(smbus2.SMBus(4), VOLTAGE_RAIL, DESTINATION_REGISTER, NOMINAL_VOLTAGE)  # reset back to normal
            exit(1)
    else: # not threaded
        print("Running the selected model")
        selectedModel(model)

    print("==============================")
    print("==========Finished============")
    print("==============================")

if __name__ == "__main__":
    main()
