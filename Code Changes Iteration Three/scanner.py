import os
import glob
import time
import argparse

# Lookup table to map the cryptic chip names to human readable rail names
lookup = {
    "ina226_u16" : "VCC3V3",
    "ina226_u80" : "VCCAUX",
    "ina226_u93" : "VCCO_PSDDR_504",
    "ina226_u79" : "VCCINT",
    "ina226_u85" : "MGTRAVCC",
    "ina226_u15" : "VCCOPS3",
    "ina226_u78" : "VCCPSAUX",
    "ina226_u75" : "MGTAVTT",
    "ina226_u76" : "VCCPSINTFP",
    "ina226_u65" : "CADJ_FMC",
    "ina226_u84" : "VCC1V2",
    "ina226_u88" : "VCCOPS",
    "ina226_u81" : "VCCBRAM",
    "ina226_u86" : "MGTRAVTT",
    "ina226_u92" : "VCCPSDDRPLL",
    "ina226_u77" : "VCCPSINTLP",
    "ina226_u87" : "VCCPSPLL",
    "ina226_u74" : "MGTAVCC"
}

def read_file(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except:
        return None

def get_hwmon_path(sensor_name_key):
    # Finds the correct /sys/class/hwmon/ folder for a specific sensor name
    # We look through all hwmon folders to find the one matching our lookup key
    base_dir = "/sys/class/hwmon/"
    hwmon_dirs = glob.glob(base_dir + "hwmon*")
    
    for hwmon in hwmon_dirs:
        name = read_file(os.path.join(hwmon, "name"))
        if name == sensor_name_key:
            return hwmon
    return None

def print_sensor_values(hwmon):
    if not hwmon:
        return

    name = read_file(os.path.join(hwmon, "name"))
    rail_name = lookup.get(name, "Unknown Rail")

    # print(f"=== {rail_name} ({name}) ===") 

    # We specifically want Voltage and Power
    in_file = glob.glob(os.path.join(hwmon, "in*_input"))
    power_file = glob.glob(os.path.join(hwmon, "power*_input"))
    curr_file = glob.glob(os.path.join(hwmon, "curr*_input"))

    # Read Voltage (mV)
    volts = 0
    if in_file:
        val = read_file(in_file[0])
        if val: 
            volts = int(val)

    # Read Power (uW)
    power = 0
    if power_file:
        val = read_file(power_file[0])
        if val:
            power = int(val)
            
    # Read Current (mA)
    current = 0
    if curr_file:
        val = read_file(curr_file[0])
        if val:
            current = int(val)

    # Print in a nice single line format: "VCCINT: 850mV | 15000uW"
    print(f"{rail_name:<15} : {volts} mV | {current} mA | {power} uW")


def main():
    print("Starting Scanner Monitor...")
    print("Press Ctrl+C to stop.")
    print("------------------------------------------------")

    # The INA226 chip for VCCINT is usually 'ina226_u79'
    # Use the lookup table to verify this key if you change rails
    target_sensor = "ina226_u79" 
    
    # Locate the folder system path once
    hwmon_path = get_hwmon_path(target_sensor)
    
    if not hwmon_path:
        print(f"Error: Could not find sensor for {target_sensor}")
        print("Available sensors are:")
        base_dir = "/sys/class/hwmon/"
        hwmon_dirs = glob.glob(base_dir + "hwmon*")
        for h in hwmon_dirs:
            print(f" - {read_file(os.path.join(h, 'name'))}")
        return

    try:
        while True:
            print_sensor_values(hwmon_path)
            time.sleep(0.5) # Update every half second
    except KeyboardInterrupt:
        print("\nStopping monitor.")

if __name__ == "__main__":
    main()