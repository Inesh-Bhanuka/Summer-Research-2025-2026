import time
import argparse
import subprocess
import threading
import csv
import sys
import re
import os
from boardAbstraction import BoardHAL

class ExperimentRunner:
    def __init__(self, config_file):
        try:
            self.hal = BoardHAL(config_file)
        except Exception as e:
            print(f"Failed to initialize HAL: {e}")
            sys.exit(1)
            
        self.stop_monitoring = threading.Event()
        self.log_data = []

    def _monitor_loop(self, rail_name):
        """ Threaded function to log power during execution """
        while not self.stop_monitoring.is_set():
            data = self.hal.read_telemetry(rail_name)
            if data:
                data['timestamp'] = time.time()
                self.log_data.append(data)
            time.sleep(0.25)

    def run_workload_sweep(self, workload_name, steps=25, step_size_v=0.01):
        """
        Runs the full Undervolting Experiment loop.
        """
        # Get model from JSON
        if workload_name not in self.hal.workloads:
            print(f"Error: Workload '{workload_name}' not found in JSON.")
            return

        job = self.hal.workloads[workload_name]
        
        # Get desired rail and starting voltage
        rail = job.get('target_rail', 'VCCINT')
        if 'nominal_voltage' in job:
            nominal_v = job['nominal_voltage']
        elif rail in self.hal.rails:
            nominal_v = self.hal.rails[rail]['conf']['limits'].get('nominal', 0.85)
        else:
            print(f"Error: Could not determine nominal voltage for {rail}")
            return
        
        full_cmd = f"{job['executable']} {job['args']}"
        cwd = job['cwd']

        

        print(f"\n=== Starting Sweep: {workload_name} on {rail} ===")
        print(f"Cmd: {full_cmd}")

        print("Performing Warm-up run to cache model in RAM...")
        # Run the command once, but don't save the output
        subprocess.run(full_cmd, shell=True, cwd=cwd, check=False, 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print("Warm-up complete. Starting experiment loop...")

        min_v = self.hal.rails[rail]['conf']['limits'].get('min', 0.55)

        # Configuration for Increasing datapoints as voltage gets closer to the crash region
        fine_threshold = min_v + 0.02  # Trigger fine mode 0.2V before min
        fine_step = 0.001              # The smaller step size
        coarse_step = step_size_v      # Your standard 0.01V step

        current_v = nominal_v
        step_count = 0

        try:
            while current_v >= (min_v - 0.0001):
                print(f"\n--- Step {step_count}: Setting {current_v:.3f}V ---")
                accuracy_found = 0.0
                # Set Voltage
                if not self.hal.set_voltage(rail, current_v):
                    print("Aborting sweep due to voltage set failure.")
                    break
                
                time.sleep(1.0)

                # Start monitoring
                self.stop_monitoring.clear()
                self.log_data = []
                monitor_thread = threading.Thread(target=self._monitor_loop, args=(rail,))
                monitor_thread.start()

                # Run model
                try:
                    start_t = time.time()
                    result = subprocess.run(full_cmd, shell=True, cwd=cwd, check=False, capture_output=True, text=True)
                    duration = time.time() - start_t

                    # --- DEBUGGING START --- This can be used to figure out the correct regex needed for a model
                    #print("\n--- RAW OUTPUT FROM BOARD ---")
                    #print(result.stdout)
                    #print("--- RAW ERRORS FROM BOARD ---")
                    #print(result.stderr)
                    #print("-----------------------------")
                    # --- DEBUGGING END ---

                    # Combine both outputs just in case the accuracy is hidden in errors
                    full_output = result.stdout + result.stderr

                    # Get Custom Regex
                    custom_regex = job['regex']
                    
                    # Run dynamic search for the accuracy score which is dependent on the chosen model
                    match = re.search(custom_regex, full_output)

                    if match:
                        accuracy_found = float(match.group(1))
                    else:
                        print(f"WARNING: Could not find accuracy using pattern: {custom_regex}")
                        accuracy_found = 0.0
                    
                    # Handle Exit Codes (Ignoring -6 for GUI crash)
                    if result.returncode == 0 or result.returncode == -6:
                        status = "SUCCESS"
                        if result.returncode == -6:
                            status = "SUCCESS (GUI Ignored)"
                        
                        # Print Accuracy nicely
                        print(f"Result: {status} | Time: {duration:.2f}s | Accuracy: {accuracy_found:.6f}")
                        
                    else:
                        print(f"Result: CRASH (Exit Code {result.returncode})")
                    
                except Exception as e:
                    print(f"Execution Exception: {e}")
                    break
                
                finally:
                    # Stop monitoring
                    self.stop_monitoring.set()
                    monitor_thread.join()
                    for row in self.log_data:
                        row['accuracy'] = accuracy_found
                    self._save_csv(workload_name, current_v, self.log_data)
                    self.update_master_summary(workload_name, current_v, accuracy_found, status, duration)

                # Check if we are entering the danger zone
                if current_v <= fine_threshold:
                    current_step = fine_step
                    print(f"[Auto-Scaling] Fine Mode active. Decreasing by {fine_step}V")
                else:
                    current_step = coarse_step
                
                current_v -= current_step
                step_count += 1
                
                # Safety check to prevent infinite loops if something goes wrong
                if step_count > 500:
                    print("Safety Limit Reached (500 steps). Stopping.")
                    break

        except KeyboardInterrupt:
            print("\nTest Interrupted.")
        
        finally:
            print(f"\n=== Resetting {rail} to Nominal {nominal_v:.3f}V ===")
            self.hal.set_voltage(rail, nominal_v)

    def _save_csv(self, workload, voltage, data):
        """ Saves statistics of current voltage step to a csv"""
        filename = f"log_{workload}_{voltage:.3f}V.csv"
        if not data: return
        
        try:
            keys = data[0].keys()
            with open(filename, 'w', newline='') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(data)
            print(f"Saved: {filename}")
        except IOError as e:
            print(f"Error saving CSV: {e}")

    def update_master_summary(self, workload, voltage, accuracy, status, duration):
        """ Updates a master csv file with the current statistics of the voltage step for easier plotting"""
        filename = f"summary_{workload}.csv"
        
        # Calculate averages from the detailed log_data collected during this step
        if self.log_data:
            # FIX: Look for 'power_w' (from HAL) or fallback to 'power_watts'
            avg_power = sum(d.get('power_w', d.get('power_watts', 0.0)) for d in self.log_data) / len(self.log_data)
            
            # FIX: Look for 'current_a' (from HAL) or fallback to 'current_amps'
            avg_current = sum(d.get('current_a', d.get('current_amps', 0.0)) for d in self.log_data) / len(self.log_data)
        else:
            avg_power = 0.0
            avg_current = 0.0

        # Define columns (These are the Headers for the Excel/CSV file)
        fieldnames = ['timestamp', 'voltage', 'accuracy', 'status', 'duration', 'avg_power_watts', 'avg_current_amps']
        
        row = {
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'voltage': f"{voltage:.4f}",
            'accuracy': accuracy,
            'status': status,
            'duration': f"{duration:.2f}",
            'avg_power_watts': f"{avg_power:.4f}",  # Matches fieldname
            'avg_current_amps': f"{avg_current:.4f}" # Matches fieldname
        }

        # Append to file (Create header if file doesn't exist)
        file_exists = os.path.isfile(filename)
        with open(filename, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
            
        print(f"Summary updated: {filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="board_data.json")
    parser.add_argument("--model", default="ResNet18")
    parser.add_argument("--steps", type=int, default=27)
    parser.add_argument("--step_size", type=float, default=0.01)
    
    args = parser.parse_args()

    runner = ExperimentRunner(args.config)
    runner.run_workload_sweep(args.model, steps=args.steps, step_size_v=args.step_size)