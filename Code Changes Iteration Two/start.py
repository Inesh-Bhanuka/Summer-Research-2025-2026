import time
import argparse
import subprocess
import threading
import csv
import sys
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
            time.sleep(0.5) 

    def run_workload_sweep(self, workload_name, steps=25, step_size_v=0.01):
        """
        Runs the full Undervolting Experiment loop.
        """
        # Get model details via hardware abstraction class
        if workload_name not in self.hal.config.get('workloads', {}):
            print(f"Error: Workload '{workload_name}' not found in JSON.")
            print("Available workloads:", list(self.hal.config.get('workloads', {}).keys()))
            return

        job = self.hal.config['workloads'][workload_name]
        rail = job['target_rail']
        nominal_v = job['nominal_voltage']
        
        full_cmd = f"{job['executable']} {job['args']}"
        cwd = job['cwd']

        print(f"\n=== Starting Sweep: {workload_name} on {rail} ===")
        print(f"Base Command: {full_cmd}")
        print(f"Working Dir : {cwd}")

        current_v = nominal_v

        try:
            for i in range(steps + 1):
                print(f"\n--- Step {i}: Setting {current_v:.3f}V ---")
                
                # Set voltage via hardware abstraction layer
                if not self.hal.set_voltage(rail, current_v):
                    print("Aborting sweep due to voltage set failure (or safety limit).")
                    break
                
                time.sleep(0.5)

                # Initialize monitor thread
                self.stop_monitoring.clear()
                self.log_data = [] # Clear previous log
                monitor_thread = threading.Thread(target=self._monitor_loop, args=(rail,))
                monitor_thread.start()

                # Run model
                try:
                    print("Running model...")
                    
                    start_t = time.time()
                    result = subprocess.run(full_cmd, shell=True, cwd=cwd, check=False, capture_output=True, text=True)
                    duration = time.time() - start_t
                    
                    # Exit code -6 is SIGABRT (The GUI crash) ignore this crash
                    if result.returncode == 0 or result.returncode == -6:
                        status = "SUCCESS"
                        if result.returncode == -6:
                            status = "SUCCESS (GUI Crash Ignored)"
                        print(f"Result: {status} (Time: {duration:.2f}s)")
                        
                    else:
                        # Actual fail
                        print(f"Result: CRASH/FAIL (Exit Code {result.returncode})")
                        print(f"Stderr: {result.stderr}") 
                        break 

                except FileNotFoundError:
                    print(f"Result: ERROR (Executable not found in {cwd})")
                    break
                
                finally:
                    # Stop monitoring
                    self.stop_monitoring.set()
                    monitor_thread.join()
                    
                    # Store results
                    self._save_csv(workload_name, current_v, self.log_data)

                # Step down voltage
                current_v -= step_size_v

        except KeyboardInterrupt:
            print("\nTest Interrupted by User.")
        
        finally:
            print(f"\n=== Test Finished. Resetting {rail} to {nominal_v:.3f}V ===")
            self.hal.set_voltage(rail, nominal_v)

    def _save_csv(self, workload, voltage, data):
        filename = f"log_{workload}_{voltage:.3f}V.csv"
        if not data: 
            print("No data captured to save.")
            return
        
        keys = data[0].keys()
        try:
            with open(filename, 'w', newline='') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(data)
            print(f"Saved data to {filename}")
        except IOError as e:
            print(f"Error saving CSV: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FPGA Undervolting Framework")
    parser.add_argument("--config", type=str, default="board_data.json", help="Path to board config")
    parser.add_argument("--model", type=str, default="ResNet50", help="Workload name from JSON")
    parser.add_argument("--steps", type=int, default=25, help="Number of voltage steps")
    parser.add_argument("--step_size", type=float, default=0.01, help="Voltage step size (V)")
    
    args = parser.parse_args()

    runner = ExperimentRunner(args.config)
    runner.run_workload_sweep(args.model, steps=args.steps, step_size_v=args.step_size)