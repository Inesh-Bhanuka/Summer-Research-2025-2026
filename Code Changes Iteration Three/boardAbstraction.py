import smbus2
import json
import os
import glob
import sys

class BoardHAL:
    def __init__(self, config_path):
        """
        Initializes the Board Hardware Abstraction Layer.
        Reads the 'selected_board' from JSON and initializes only those rails.
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file {config_path} not found.")

        with open(config_path, 'r') as f:
            self.full_config = json.load(f)

        # Load desired board config
        self.board_name = self.full_config.get('selected_board')
        if not self.board_name or self.board_name not in self.full_config['boards']:
            raise ValueError(f"Selected board '{self.board_name}' not found in 'boards' list.")
        
        self.config = self.full_config['boards'][self.board_name]
        self.workloads = self.full_config.get('workloads', {})
        
        print(f"[HAL] Initializing HAL for: {self.config.get('name', self.board_name)}")

        # Initialize controllers for each rail
        self.rails = {}
        for r_name, r_conf in self.config['rails'].items():
            self.rails[r_name] = self._init_rail_controller(r_name, r_conf)

    def _init_rail_controller(self, name, conf):
        """Internal helper to setup specific drivers for a rail"""
        controller = {
            'name': name,
            'conf': conf,
            'type': conf.get('driver_type', 'sysfs_monitor'),
            'bus': None,
            'hwmon_path': None,
            'regulator_path': None
        }

        # Setup I2C (PMBus / Raw)
        if controller['type'] in ['pmbus', 'raw_i2c']:
            bus_id = conf['connection'].get('bus_id', 4) # Default to 4
            try:
                controller['bus'] = smbus2.SMBus(bus_id)
            except Exception as e:
                print(f"[HAL] Warning: Could not open I2C Bus {bus_id} for {name}: {e}")

        # Setup SYSFS monitor (Kria)
        elif controller['type'] == 'sysfs_monitor':
            target = conf['connection'].get('driver_match')
            glob_pattern = conf['connection'].get('sysfs_glob')
            found = False
            for f in glob.glob(glob_pattern):
                try:
                    with open(f, 'r') as file:
                        if target in file.read().strip():
                            controller['hwmon_path'] = os.path.dirname(f)
                            found = True
                            break
                except: continue
            if not found:
                print(f"[HAL] Warning: Sensor driver '{target}' not found for {name}")

        # Setup SYSFS regulator (Kria)
        elif controller['type'] == 'sysfs_regulator':
            path = conf['connection'].get('sysfs_path')
            if os.path.exists(path):
                controller['regulator_path'] = path
            else:
                print(f"[HAL] Warning: Regulator path {path} not found for {name}")

        return controller

    def read_telemetry(self, rail_name):
        """
        Reads voltage/current/power.
        Returns dict: {'voltage_v': float, 'current_a': float, 'power_w': float}
        """
        if rail_name not in self.rails:
            print(f"[HAL] Error: Rail {rail_name} not found.")
            return None
        
        c = self.rails[rail_name]
        v, i, p = 0.0, 0.0, 0.0

        try:
            # PMBus read
            if c['type'] == 'pmbus' and c['bus']:
                addr = int(c['conf']['connection']['address'], 16)
                scale = c['conf']['format']['scale_factor']
                cmds = {k: int(v, 16) for k, v in c['conf']['commands'].items()}
                
                raw_v = c['bus'].read_word_data(addr, cmds['read_voltage'])
                raw_i = c['bus'].read_word_data(addr, cmds['read_current'])
                v = raw_v / scale
                i = raw_i / scale
                p = v * i

            # Raw I2C read
            elif c['type'] == 'raw_i2c' and c['bus']:
                addr = int(c['conf']['connection']['address'], 16)
                scale = c['conf']['format'].get('scale_factor', 1.0)
                cmds = {k: int(v, 16) for k, v in c['conf']['commands'].items()}
                
                v = c['bus'].read_word_data(addr, cmds['read_voltage']) / scale
                if 'read_current' in cmds:
                    i = c['bus'].read_word_data(addr, cmds['read_current']) / scale
                p = v * i

            # SYSFS monitor read
            elif c['type'] == 'sysfs_monitor' and c['hwmon_path']:
                files = c['conf']['files']
                div = files.get('scale_div', 1.0)
                
                # Voltage
                with open(os.path.join(c['hwmon_path'], files['voltage']), 'r') as f:
                    v = float(f.read()) / div
                
                # Current
                with open(os.path.join(c['hwmon_path'], files['current']), 'r') as f:
                    i = float(f.read()) / div
                
                # Power (Try direct file, else calc)
                if 'power' in files and os.path.exists(os.path.join(c['hwmon_path'], files['power'])):
                    with open(os.path.join(c['hwmon_path'], files['power']), 'r') as f:
                        # Power is usually mW, so divide by 1,000,000
                        p = float(f.read()) / 1000000.0
                else:
                    p = v * i

            # SYSFS regulator read
            elif c['type'] == 'sysfs_regulator' and c['regulator_path']:
                with open(c['regulator_path'], 'r') as f:
                    v = float(f.read()) / 1000000.0
                i = 0.0
                p = 0.0

            return {"voltage_v": v, "current_a": i, "power_w": p}

        except Exception as e:
            return None

    def set_voltage(self, rail_name, voltage_v):
        """
        Sets the voltage safely for any supported type.
        """
        if rail_name not in self.rails:
            print(f"[HAL] Error: Rail {rail_name} unknown.")
            return False

        c = self.rails[rail_name]
        
        # Check read only
        if c['conf'].get('read_only', True):
            print(f"[HAL] Blocked: {rail_name} is Read-Only.")
            return False

        # Safety limits
        limits = c['conf'].get('limits', {})
        min_v = limits.get('min', 0.0)
        max_v = limits.get('max', 99.0)
        
        if not (min_v <= voltage_v <= max_v):
            print(f"[HAL] Safety Trip: {voltage_v}V out of bounds ({min_v}-{max_v}V).")
            return False

        try:
            # PMBus / Raw I2C write
            if c['type'] in ['pmbus', 'raw_i2c'] and c['bus']:
                addr = int(c['conf']['connection']['address'], 16)
                cmd = int(c['conf']['commands']['set_voltage'], 16)
                scale = c['conf']['format']['scale_factor']
                
                raw_val = int(voltage_v * scale)
                c['bus'].write_word_data(addr, cmd, raw_val)
                return True

            # SYSFS regulator write
            elif c['type'] == 'sysfs_regulator' and c['regulator_path']:
                microvolts = int(voltage_v * 1000000)
                with open(c['regulator_path'], 'w') as f:
                    f.write(str(microvolts))
                return True
            
            else:
                print(f"[HAL] Error: Driver type '{c['type']}' does not support writing.")
                return False

        except Exception as e:
            print(f"[HAL] Write Failed on {rail_name}: {e}")
            return False