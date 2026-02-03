import time
import argparse
import sys
from boardAbstraction import BoardHAL

class SystemMonitor:
    def __init__(self, config_path):
        # Initialize instance of Board Hardware Abstraction Layer Class for data collection
        try:
            self.hal = BoardHAL(config_path) 
        except Exception as e:
            print(f"Failed to initialize HAL: {e}")
            sys.exit(1)

    def monitor_loop(self, target_rail=None):
        print("Starting Monitor... (Press Ctrl+C to stop)")
        print("-" * 65)
        # Print header once
        print(f"{'RAIL NAME':<15} | {'VOLTAGE':<12} | {'CURRENT':<12} | {'POWER':<12}")
        print("-" * 65)
        
        try:
            while True:
                # Display desired rail
                if target_rail:
                    data = self.hal.read_telemetry(target_rail) # Get Voltage, Current and Power data
                    if data:
                        print(f"{target_rail:<15} : {data['voltage_v']:<6.3f} V    | {data['current_a']:<6.3f} mA    | {data['power_w']:<6.3f} mW")
                    else:
                        print(f"Rail '{target_rail}' not found or sensor unavailable.")
                        break
                
                # Display all rail data
                else:
                    print(f"--- Timestamp: {time.time():.2f} ---")
                    for rail in self.hal.config['rails']:
                        data = self.hal.read_telemetry(rail)
                        if data:
                             print(f"{rail:<15} : {data['voltage_v']:<6.3f} V    | {data['current_a']:<6.3f} A    | {data['power_w']:<6.3f} W")
                    print("") # Space between blocks
                
                # Update speed
                time.sleep(0.5) 

        except KeyboardInterrupt:
            print("\nMonitor Stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Universal Board Monitor")
    parser.add_argument("--config", default="board_data.json", help="Path to board config JSON")
    parser.add_argument("--rail", help="Specific rail to monitor (e.g., VCCINT)", default="VCCINT")
    
    args = parser.parse_args()
    
    monitor = SystemMonitor(args.config)
    monitor.monitor_loop(args.rail)