# Energy Efficient Solutions in Hardware for Machine Learning

This research looks into the possible power gains from applying undervolting techniques on FPGAs. The performance is evaluated by running AI models (ResNet18, ResNet50 and SqueezeNet) at each voltage step, summarizing power gains and accuracy changes. This project has fully analyzed the power gains and voltage margins where accuracy starts to vary for the Zynq ZCU102 Evaluation Board. Alongside the ZCU102 board, preliminary research was done around the use of the Kria KV260 Vision AI Starter Kit, being able to run AI models, but not able to perform undervolting. The end goal of this research was to establish a framework where any FPGA board could be effectively analyzed the by the code within this repository and output key statistics regarding power and accuracy. However, further testing is needed to achieve this.

---

## 📂 Project Structure

Below is an overview of the repository's organization and the purpose of each file.

### 🔄 Iteration One
* **Code Changes Iteration One/**
    This iteration brings out the board specific meta data and organizes it into a .json file. The python scripts were adapted to reference the json file so ideally, the board can be changed easily without changing each of the scripts.

    * `board_data.json` - A central configuration file containing metadata for the Zynq UltraScale+ (ZCU102) board. It defines I2C addresses, voltage limits, and monitoring driver paths for various power rails (like VCCINT and VCCBRAM), as well as workload paths for models like ResNet50 and SqueezeNet.
    * `PMBus.py` - The main execution script for power experiments. It supports undervolting loops, real-time power monitoring (Voltage x Current), and automated workload execution based on the configurations in board_data.json
    * `PBMUSWrite.py` - A low-level utility used for scanning the I2C bus to find connected devices and performing direct write operations to PMBus registers.
    * `PuTTy.py` - A monitoring tool that interfaces with the Linux hwmon system to read and print real-time sensor values (Voltage, Current, and Power) for specific hardware rails like VCCINT.
    * `scanner.py` - A serial communication utility that replicates basic PuTTY functionality. It handles connecting to serial ports, reading device output, and automatically logging that data to log.txt for later analysis.
    * `scripting.py` - A visualization script used to generate real-time plots. It parses log files (like log.txt) to create live graphs of power metrics and can generate "compendium" data files for voltage testing.
    * `setup.py` - A board-side initialization script that configures the static IP address
    * `startup.py` - A simple utility script to launch the PyCharm IDE from a specific local directory.
    * `upload.py` - An automated deployment script that uses scp and pexpect to push updated Python scripts and configuration files from a local machine to the target development board. It includes SHA-256 hashing to verify file integrity.

### 🔄 Iteration Two
* **Code Changes Iteration Two/**
    This iteration builds on the previous idea of generalizing code, converting scripts into three main python classes, providing scalability.

    * `board_data.json` - A central configuration file containing metadata for the Zynq UltraScale+ (ZCU102) board. It defines I2C addresses, voltage limits, and monitoring driver paths for various power rails (like VCCINT and VCCBRAM), as well as workload paths for models like ResNet50 and SqueezeNet.
    * `monitor.py` - A universal board monitoring utility that utilizes the HAL. It provides a real-time terminal dashboard showing Voltage (V), Current (A), and Power (W) for specific rails (like VCCINT) or a summary of all available rails on the board.
    * `boardAbstraction.py` - Contains the BoardHAL (Hardware Abstraction Layer) class. This is the core engine that translates high-level Python commands into low-level hardware actions, handling I2C bus communication for voltage control and scanning /sys/class/hwmon to discover power sensors dynamically.
    * `start.py` - The main experiment orchestration script. It manages the "Undervolting Sweep" process by iteratively lowering rail voltages, launching Vitis-AI workloads in sub-processes, and logging telemetry data to CSV files for performance analysis.

### 🔄 Iteration Three
* **Code Changes Iteration Three/**
    The primary shift in this set of files is the transition from a single-board hardcoded setup to a multi-board modular architecture. The board_data.json file was restructured to house multiple board definitions (like the Kria KV260) within a single file. Correspondingly, boardAbstraction.py was rewritten as a more robust class-based HAL that selects and initializes only the drivers required for the "selected board". Additionally, the monitoring and experiment scripts (monitor.py and start.py) were updated to be completely board-agnostic, relying entirely on the HAL to handle the differences between PMBus and SysFS hardware interfaces.

    * `board_data.json` - Acts as a multi-board hardware registry. It now supports multiple hardware platforms (e.g., ZCU102 and KV260) by organizing them into a boards list and uses a selected_board key to define the active configuration.
    * `monitor.py` - A board-agnostic monitoring utility that uses the HAL to provide a real-time CLI dashboard. It can monitor a specific power rail or list telemetry for every rail defined for the currently selected board.
    * `boardAbstraction.py` - A revised Hardware Abstraction Layer (HAL) that dynamically initializes rail controllers based on the selected board. It supports a variety of driver types, including PMBus over I2C, raw I2C, and Linux SysFS monitors or regulators.
    * `start.py` - The experiment orchestration script that manages automated "Undervolting Sweeps." It coordinates voltage adjustments via the HAL, launches AI workloads, and captures time-stamped telemetry data into CSV files for later analysis.

### 🔄 Iteration Four
* **Code Changes Iteration Four/**
    Key Changes:

    Strict Data-Logic Separation: Unlike the previous versions which had some board-specific logic in the Python code, this version is entirely configuration-driven. The HAL (boardAbstraction.py) no longer assumes what a board looks like; it builds its internal map entirely from board_data.json.

    Advanced PMBus Support: The addition of _decode_linear11 and linear16_fixed logic allows the system to interface with a much wider variety of industrial power controllers that use non-standard bit-packing for telemetry.

    Enhanced Safety & Precision: New fields like slew_wait_ms in the JSON ensure the software waits for hardware voltages to stabilize before running workloads, and a more robust safety-trip check prevents the software from ever requesting a voltage outside of the hardware's safe operating range.

    Flexible Driver Interface: The architecture now supports sysfs_regulator and update_reg commands, allowing it to control power on modern Linux-based systems (like the Kria SOM) just as easily as legacy I2C-based boards.

    * `board_data.json` - The project's configuration backbone. It uses a highly granular schema to define multiple boards, mapping specific hardware rails to their driver types (e.g., pmbus, sysfs_regulator, sysfs_monitor). It includes precise data formats (like linear11 vs linear16), safety limits, and workload execution parameters.
    * `monitor.py` - A clean command-line interface utility that uses the HAL to provide real-time power telemetry. It supports monitoring either the entire board or a specific rail, displaying voltage, current, and power consumption with a high update frequency.
    * `boardAbstraction.py` - A sophisticated Hardware Abstraction Layer (HAL) that is now fully configuration-driven. It dynamically initializes rail controllers and decodes complex PMBus telemetry formats (Linear11/16) based on the JSON definitions. It handles the low-level logic for writing to I2C registers and interacting with Linux regulators.
    * `start.py` - The experiment automation engine. It orchestrates "Undervolting Sweeps" by lowering rail voltages in defined steps, executing AI workloads (like ResNet50), and capturing high-resolution power data into CSV files for analysis.

### 🔄 Iteration Five
* **Code Changes Iteration Five/**
    MatLab scripts were developed to easily take CSV data that was generated during the run and create matlab plots using them.
    
    * `analyze_undervolt.m` - A specialized analysis script that generates Accuracy vs. Power plots. It features a reversed X-axis (High Power to Low Power) to visualize how model performance degrades as power consumption is reduced, allowing for easy identification of the optimal "efficiency sweet spot."
    * `create_plots.m` - The primary visualization tool for undervolting results. It processes experiment summary CSVs to create high-quality plots of Accuracy vs. Voltage. It includes "Cliff Detection" logic to automatically identify the critical voltage point where the FPGA hardware or AI model begins to fail.

### 🔄 Iteration Six
* **Code Changes Iteration Six/**
    This iteration is incomplete. There have been a large amount of changes as the intention was to first get the KV260 undervolting process working as well as the AI models running alongside it before making sure the framework idea remains effective. Upto this point, the KV260 is unable to be undervolted, as the voltage current and power rails for the VCCINT rail on the board seem to be read only. It is more than reasonable to not begin using this version of the code and instead start from the Iteration Five code as that is more stable and should work immediately with the ZCU102 board. This iteration needs further work before being able to effectively undervolt the KV260 and maintain the framework aspect in terms of being able to run the ZCU102 as well.
    
    * `board_data.json` - The most advanced version of the configuration registry. It now includes multi-board support for the Kria KV260, adding definitions for specialized driver types like da9062_buck. It also introduces a regex field for each workload, allowing the automation script to dynamically parse accuracy results from different console outputs.
    * `boardAbstraction.py` - A hardened Hardware Abstraction Layer that now includes a Native I2C fallback driver (LinuxI2C). This allows the HAL to function on systems where the smbus2 library is unavailable. It features expanded support for custom register writes, including "trigger/update" registers required by certain PMIC (Power Management IC) controllers.
    * `start.py` - The primary experiment engine. This version introduces automated result parsing using the regex patterns defined in the JSON. After each undervolting step, it extracts accuracy metrics directly from the workload's output and appends them to a persistent summary CSV, creating a complete dataset for the MATLAB analysis tools.
    * `monitor.py` - The real-time telemetry dashboard. It has been updated to be more resilient, using safe .get() calls to prevent script crashes if a specific board sensor fails to return a value for voltage, current, or power.

    These are test scripts used in the setup of the KV260 board and are not part of the actual project, nor have any applicable use, they were just produced for research purposes.
    * `fake_runner.py` - Images, icons, or static resources.
    * `kv260_pmic_discovery.sh` - Images, icons, or static resources.
    * `runner.py` - Images, icons, or static resources.
    * `scan_bus.py` - Images, icons, or static resources.
    * `test.sh` - Images, icons, or static resources.

### 🐛 Bugs Experienced
* **Bugs**
    * A bug came up in which the code would crash immediately after the first voltage level. This was because the AI models bring up an image using a GUI image which could not done on the PC. To fix this, a warning was implemented to detect this error and instead continue, but notify the user that it occurred.

    * Another issue that arose was that the monitoring script output was overwriting itself, so it became difficult to observe changes in the power statistics. To fix this, I made the monitoring loop print out each new set of statistics on a new line.

    * Another issue that came up was that the ssh suddenly became inaccessible. This issue produced a 'permission denied' error which was misleading as the problem was actually that the sshd dropbear server was down. To fix it, I used the following commands to check and start sshd dropbear:
        * `sudo systemctl status sshd`
        * `sudo systemctl start dropbear`
        * `sudo systemctl enable dropbear`

---

## 🚀 Getting Started

### Prerequisites
* DPU Linux Image with Vitis AI on SD card of the FPGA

### Installation
1. Clone the repository:
   ```bash
   git clone [https://github.com/Inesh-Bhanuka/Summer-Research-2025-2026.git)

### Setup and Usage
* Setup serial and ethernet connections
    * Connect both serial and ethernet cables to PC and board
    * Open a terminal and run `sudo screen /dev/ttyUSB0 (for KV260: /dev/ttyUSB1) 115200`
    * Turn on board, should see the boot sequence through the serial monitor
    * Once fully started up: 
        * ZCU102
            * In serial monitor: `ifconfig eth0 192.168.9.2 netmask 255.255.255.0 up`
            * In Linux terminal: `sudo ip addr flush dev enx08beac2470a1` (enx08beac2470a1 is the device name)
                                 `sudo ip addr add 192.168.9.1/24 dev enx08beac2470a1`
                                 `sudo ip link set enx08beac2470a1 up`
                                  Test with `ping 192.168.9.2`
                                  Open ssh using `ssh root@192.168.9.2`
        * KV260
            * In serial monitor: `ip link set eth0 up`
            * In Linux terminal: `sudo nmcli con add type ethernet ifname enx08beac2470a1 ipv4.method shared con-name fpga-shared` 
                                 `sudo nmcli con up fpga-shared`
                                 Test with `ping google.com` on board
                                 Open ssh using `ssh root@10.42.0.240`

    * Adding files to board
        * `scp "(filepath)/FILENAME" root@192.168.9.2:/home/root` (or `root@10.42.0.240`)

    * Usage
        Make sure that the files have added to the board (`start.py`, `monitor.py`, `boardAbstraction.py` and `board_data.json`) as well as Vitis-AI preloaded models. The filepaths for the AI models stored within the `board_data.json` file may differ so make sure to update these in the `Workloads` section of the `.json` file.

        * To run the experiment begin by starting the monitoring script in either the serial or ssh terminal: `python3 monitor.py` by default this will monitor the VCCINT rail if possible
        * In the other terminal (ssh or serial) run `python3 start.py` if you wish to change the model add the `--model` argument, for example `python3 start.py --model ResNet50`

    * Getting log results onto PC
        * `scp "root@192.168.9.2:~/log_*.csv .` (or `root@10.42.0.240`)
        * `scp "root@192.168.9.2:~/summary_*.csv .` (or `root@10.42.0.240`)

    * Removing log results off Board
        * `ssh root@192.168.9.2 "rm ~/log_*.csv"` (or `root@10.42.0.240`)
        * `ssh root@192.168.9.2 "rm ~/summary_*.csv"` (or `root@10.42.0.240`)

    * Plots
        * Open MatLab with the MatLab scripts and csv files all in the same working directory. Run each of the scripts with the csv file as an input and plots will be automatically generated and stored in the working directory.

