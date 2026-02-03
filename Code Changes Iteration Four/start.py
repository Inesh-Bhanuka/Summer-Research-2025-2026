import time
import argparse
import subprocess
import threading
import csv
import sys
from boardAbstraction import BoardHAL

class ExperimentRunner:
    def __init__(self, config_file):
        # Initialize instance of Board Hardware Abstraction Layer Class for undervolting experiments
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
            data = self.hal.read_telemetry(rail_name) # Get voltage, Current and Power data from BoardHAL class
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

        current_v = nominal_v

        try:
            for i in range(steps + 1):
                print(f"\n--- Step {i}: Setting {current_v:.3f}V ---")
                
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
                    
                    status = "SUCCESS" if result.returncode == 0 else f"FAIL ({result.returncode})"
                    print(f"Run Status: {status} | Duration: {duration:.2f}s")
                    
                except Exception as e:
                    print(f"Execution Exception: {e}")
                    break
                
                finally:
                    # Stop monitoring
                    self.stop_monitoring.set()
                    monitor_thread.join()
                    self._save_csv(workload_name, current_v, self.log_data)

                # Step down
                current_v -= step_size_v

        except KeyboardInterrupt:
            print("\nTest Interrupted.")
        
        finally:
            print(f"\n=== Resetting {rail} to Nominal {nominal_v:.3f}V ===")
            self.hal.set_voltage(rail, nominal_v)

    def _save_csv(self, workload, voltage, data):
        filename = f"log_{workload}_{voltage:.3f}V.csv"
        if not data: return
        
        # Create a csv and save data and timestamp into it
        try:
            keys = data[0].keys()
            with open(filename, 'w', newline='') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(data)
            print(f"Saved: {filename}")
        except IOError as e:
            print(f"Error saving CSV: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="board_data.json")
    parser.add_argument("--model", default="ResNet50")
    parser.add_argument("--steps", type=int, default=25)
    parser.add_argument("--step_size", type=float, default=0.01)
    
    args = parser.parse_args()

    runner = ExperimentRunner(args.config)
    runner.run_workload_sweep(args.model, steps=args.steps, step_size_v=args.step_size)