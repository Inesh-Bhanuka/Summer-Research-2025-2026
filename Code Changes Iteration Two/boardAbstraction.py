import smbus2
import json
import os
import glob

class BoardHAL:
    def __init__(self, config_path):
        """
        Initializes the Board Hardware Abstraction Layer.
        :param config_path: Path to the board-specific JSON config.
        """
        # Load JSON data
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file {config_path} not found.")

        with open(config_path, 'r') as f:
            self.config = json.load(f)

        # Initialize I2C Bus for Voltage Control
        self.bus_id = self.config['board_meta'].get('i2c_bus_id', 4)
        try:
            self.bus = smbus2.SMBus(self.bus_id)
            # Check if bus is acessible
            print(f"[HAL] Connected to I2C Bus {self.bus_id}")
        except Exception as e:
            print(f"[HAL] WARNING: Could not open I2C Bus {self.bus_id}. Voltage control will fail. {e}")
            self.bus = None

        # 2. Map SysFS Paths for Monitoring
        self.monitor_paths = self._discover_sensors()

    def _discover_sensors(self):
        """
        Scans Linux /sys/class/hwmon to find the drivers matching the JSON config.
        """
        mapping = {}
        # Get all hwmon directories
        directory = glob.glob("/sys/class/hwmon/hwmon*")
        
        # Pre-load all driver names to avoid opening files repeatedly
        system_sensors = {}
        for folder in directory:
            try:
                name_path = os.path.join(folder, 'name')
                with open(name_path, 'r') as f:
                    driver_name = f.read().strip()
                system_sensors[folder] = driver_name
            except IOError:
                continue

        # Match JSON rails to System Sensors
        for rail_name, rail_data in self.config['rails'].items():
            mon_config = rail_data.get('monitoring', {})
            search_str = mon_config.get('driver_name_match', '')
            fallback = mon_config.get('fallback_sysfs_path')
            
            found = False
            
            # Match by Driver Name (e.g. "ina226_u79")
            if search_str:
                for folder, driver_name in system_sensors.items():
                    if search_str == driver_name:
                        mapping[rail_name] = folder
                        found = True
                        break
            
            # Fallback Path (e.g. "/sys/class/hwmon/hwmon2")
            if not found and fallback and os.path.exists(fallback):
                mapping[rail_name] = fallback
                print(f"[HAL] Used fallback path for {rail_name}: {fallback}")
                found = True
            
            if found:
                pass
            else:
                # Only warn if missing address that JSON has
                if 'i2c_address' in rail_data:
                    print(f"[HAL] WARNING: No sensor path found for {rail_name}")

        return mapping

    def set_voltage(self, rail_name, voltage_v):
        """
        Sets the voltage for a specific rail via I2C.
        """
        # Safety checks
        if not self.bus:
            print("[HAL] Error: I2C Bus not initialized.")
            return False
        if rail_name not in self.config['rails']:
            print(f"[HAL] Error: Rail '{rail_name}' not defined in config.")
            return False

        rail = self.config['rails'][rail_name]
        
        # Check if this rail actually supports control
        if 'i2c_address' not in rail:
            print(f"[HAL] Error: Rail '{rail_name}' is monitoring-only (no I2C address).")
            return False

        # Voltage limits
        limits = rail.get('limits', {})
        min_v = limits.get('min_voltage_v', 0.0)
        max_v = limits.get('max_voltage_v', 1.0) # Default safe max

        if not (min_v <= voltage_v <= max_v):
            print(f"[HAL] SAFETY TRIP: {voltage_v}V is outside allowed range ({min_v}-{max_v}V) for {rail_name}")
            return False

        # Calculate register value
        fmt = rail.get('format', {})
        scale = fmt.get('scale_factor', 4096)
        raw_val = int(voltage_v * scale)
        
        # Write new voltage
        try:
            addr = int(rail['i2c_address'], 16)
            cmd_str = rail.get('commands', {}).get('vout_cmd', '0x21')
            cmd = int(cmd_str, 16)
            
            self.bus.write_word_data(addr, cmd, raw_val)
            return True
        except ValueError:
            print(f"[HAL] Config Error: Invalid hex string for address/command on {rail_name}")
            return False
        except IOError as e:
            print(f"[HAL] I2C Write Failed on {rail_name}: {e}")
            return False

    def read_telemetry(self, rail_name):
        """
        Reads voltage/current from SysFS (Monitoring).
        Returns dict: {'voltage_v': float, 'current_a': float, 'power_w': float}
        """
        if rail_name not in self.monitor_paths:
            return None
        
        path = self.monitor_paths[rail_name]
        try:
            mv = 0.0
            ma = 0.0
            
            # Find Voltage File
            in_files = glob.glob(os.path.join(path, "in*_input"))
            if in_files:
                with open(in_files[0], 'r') as f:
                    mv = float(f.read())

            # Find Current File
            curr_files = glob.glob(os.path.join(path, "curr*_input"))
            if curr_files:
                with open(curr_files[0], 'r') as f:
                    ma = float(f.read())
            
            # Calculate Power (if power*_input file exists, use it, otherwise calc)
            pwr_files = glob.glob(os.path.join(path, "power*_input"))
            if pwr_files:
                 with open(pwr_files[0], 'r') as f:
                    uw = float(f.read())
                    power_w = uw / 1e6
            else:
                power_w = (mv * ma) / 1e6

            return {
                "voltage_v": mv / 1000.0,
                "current_a": ma / 1000.0,
                "power_w": power_w
            }
        except Exception:
            return None