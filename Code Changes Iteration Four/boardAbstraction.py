import smbus2
import json
import os
import glob
import math

class BoardHAL:
    def __init__(self, config_path):
        """
        Configuration-Driven FPGA Power HAL.
        All logic is derived strictly from the JSON configuration.
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file {config_path} not found.")

        with open(config_path, 'r') as f:
            self.full_config = json.load(f) # Get JSON information

        self.board_name = self.full_config.get('selected_board')
        if not self.board_name or self.board_name not in self.full_config['boards']:
            raise ValueError(f"Selected board '{self.board_name}' not found.")
        
        self.config = self.full_config['boards'][self.board_name]
        self.workloads = self.full_config.get('workloads', {})
        
        print(f"[HAL] Initializing {self.config.get('name', self.board_name)}...")

        self.rails = {}
        for r_name, r_conf in self.config['rails'].items():
            self.rails[r_name] = self._init_rail_controller(r_name, r_conf)

    def _init_rail_controller(self, name, conf):
        ctrl = {
            'name': name,
            'conf': conf,
            'type': conf.get('driver_type', 'sysfs_monitor'),
            'bus': None,
            'paths': {}
        }

        # Hardware Bus (PMBus / Raw I2C)
        if ctrl['type'] in ['pmbus', 'raw_i2c']:
            bus_id = conf['connection'].get('bus_id')
            if bus_id is None:
                raise ValueError(f"Rail '{name}' missing 'bus_id' in connection config.")
            try:
                ctrl['bus'] = smbus2.SMBus(bus_id)
            except Exception as e:
                print(f"[HAL] Warning: Failed to open I2C Bus {bus_id} for {name}: {e}")

        # Linux regulator (write)
        elif ctrl['type'] == 'sysfs_regulator':
            target = conf['connection'].get('regulator_name') 
            path = conf['connection'].get('sysfs_path')       
            
            # Prioritize auto-discovery if 'regulator_name' is provided
            if target:
                found_path = self._find_regulator_by_name(target)
                if found_path:
                    ctrl['paths']['microvolts'] = found_path
                else:
                    print(f"[HAL] Warning: Regulator named '{target}' not found via auto-discovery.")
            # Fallback to default path
            elif path:
                 if os.path.exists(path):
                     ctrl['paths']['microvolts'] = path
                 else:
                     print(f"[HAL] Warning: Hardcoded path '{path}' does not exist.")

        # Linux monitor (read only)
        elif ctrl['type'] == 'sysfs_monitor':
            match_name = conf['connection'].get('driver_match')
            base_search = conf['connection'].get('search_dir', "/sys/class/hwmon") # Default to std linux location
            
            found = False
            # Search for the sensor driver
            for hwmon in glob.glob(os.path.join(base_search, "hwmon*")):
                try:
                    with open(os.path.join(hwmon, "name"), 'r') as f:
                        if match_name in f.read().strip():
                            ctrl['paths']['root'] = hwmon
                            found = True
                            break
                except: continue
            if not found:
                print(f"[HAL] Warning: Monitor driver '{match_name}' not found.")

        return ctrl

    def read_telemetry(self, rail_name):
        """ Returns {'voltage_v': float, 'current_a': float, 'power_w': float} """
        if rail_name not in self.rails: return None
        c = self.rails[rail_name]
        v, i, p = 0.0, 0.0, 0.0

        try:
            # PMBus reading
            if c['type'] == 'pmbus' and c['bus']:
                addr = int(c['conf']['connection']['address'], 16)
                cmds = c['conf']['commands']
                fmt = c['conf']['format']

                # Voltage decoding
                raw_v = c['bus'].read_word_data(addr, int(cmds['read_voltage'], 16))
                
                if fmt.get('voltage_mode') == 'linear16_fixed':
                     scale = fmt.get('scale_factor')
                     v = raw_v / scale
                else:
                     v = self._decode_linear16(raw_v)

                # Current decoding
                if 'read_current' in cmds:
                    raw_i = c['bus'].read_word_data(addr, int(cmds['read_current'], 16))
                    
                    if fmt.get('current_mode') == 'linear11':
                        i = self._decode_linear11(raw_i)
                    elif fmt.get('current_mode') == 'linear16_fixed':
                        scale = fmt.get('current_scale_factor')
                        i = raw_i / scale
                    else:
                        i = 0.0 # Couldn't handle format

                p = v * i

            # SYSFS monitor reading
            elif c['type'] == 'sysfs_monitor' and 'root' in c['paths']:
                f_map = c['conf']['files']
                root = c['paths']['root']
                
                # Retrieve divisors from JSON
                v_div = f_map.get('voltage_div', 1.0)
                c_div = f_map.get('current_div', 1.0)
                p_div = f_map.get('power_div', 1.0)

                if 'voltage' in f_map:
                    with open(os.path.join(root, f_map['voltage']), 'r') as f:
                        v = float(f.read()) / v_div
                
                if 'current' in f_map:
                    with open(os.path.join(root, f_map['current']), 'r') as f:
                        i = float(f.read()) / c_div
                
                if 'power' in f_map:
                    with open(os.path.join(root, f_map['power']), 'r') as f:
                        p = float(f.read()) / p_div
                else:
                    p = v * i

            # SYSFS regulator reading (voltage)
            elif c['type'] == 'sysfs_regulator' and 'microvolts' in c['paths']:
                # Get unit division from JSON
                unit_div = c['conf']['format'].get('unit_div', 1000000.0) 
                
                with open(c['paths']['microvolts'], 'r') as f:
                    v = float(f.read()) / unit_div
                i = 0.0 
                p = 0.0

            return {"voltage_v": v, "current_a": i, "power_w": p}

        except Exception as e:
            return None

    def set_voltage(self, rail_name, voltage_v):
        if rail_name not in self.rails: return False
        c = self.rails[rail_name]
        
        # Bounds check
        lim = c['conf'].get('limits', {})
        if not (lim.get('min', 0.0) <= voltage_v <= lim.get('max', 99.0)):
            print(f"[HAL] Safety Trip: {voltage_v}V is outside limits for {rail_name}")
            return False

        try:
            # PMBus write
            if c['type'] == 'pmbus' and c['bus']:
                addr = int(c['conf']['connection']['address'], 16)
                cmd = int(c['conf']['commands']['set_voltage'], 16)
                fmt = c['conf']['format']

                if fmt.get('voltage_mode') == 'linear16_fixed':
                    scale = fmt.get('scale_factor')
                    raw_val = int(voltage_v * scale)
                else:
                    # Generic Linear16 encoding
                    raw_val = int(voltage_v * scale)

                c['bus'].write_word_data(addr, cmd, raw_val)
                return True

            # SYSFS regulator write
            elif c['type'] == 'sysfs_regulator' and 'microvolts' in c['paths']:
                unit_div = c['conf']['format'].get('unit_div', 1000000.0)
                raw_val = int(voltage_v * unit_div)
                
                with open(c['paths']['microvolts'], 'w') as f:
                    f.write(str(raw_val))
                return True

            # Raw I2C (VID) write
            elif c['type'] == 'raw_i2c' and c['bus']:
                addr = int(c['conf']['connection']['address'], 16)
                reg = int(c['conf']['commands']['voltage_reg'], 16)
                fmt = c['conf']['format']
                
                # VID: Value = (Target - Base) / Step
                base = fmt.get('base_v')
                step = fmt.get('step_v')
                
                if base is None or step is None:
                    print(f"[HAL] Error: 'base_v' or 'step_v' missing in JSON for {rail_name}")
                    return False

                if voltage_v < base: vid = 0
                else: vid = int(round((voltage_v - base) / step))
                
                # Write voltage
                c['bus'].write_byte_data(addr, reg, vid)
                
                # Trigger/Update register (Fully JSON driven)
                if 'update_reg' in c['conf']['commands']:
                    up_reg = int(c['conf']['commands']['update_reg'], 16)
                    up_val_str = c['conf']['commands'].get('update_value', '0x01')
                    up_val = int(up_val_str, 16)
                    
                    c['bus'].write_byte_data(addr, up_reg, up_val)
                
                return True

        except Exception as e:
            print(f"[HAL] Write failed on {rail_name}: {e}")
            return False
        
        return False

    # Helper functions
    def _find_regulator_by_name(self, target_name):
        base = "/sys/class/regulator"
        if not os.path.exists(base): return None
        for r in glob.glob(os.path.join(base, "regulator.*")):
            try:
                with open(os.path.join(r, "name"), 'r') as f:
                    if target_name.lower() in f.read().strip().lower():
                        return os.path.join(r, "microvolts")
            except: continue
        return None

    def _decode_linear11(self, raw_word):
        exp = (raw_word >> 11) & 0x1F
        if exp > 15: exp -= 32 
        mant = raw_word & 0x7FF
        if mant > 1023: mant -= 2048
        return mant * (2.0 ** exp)

    def _decode_linear16(self, raw_word, fixed_exp=-12):
        return raw_word * (2.0 ** fixed_exp)