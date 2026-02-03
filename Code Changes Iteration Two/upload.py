import subprocess
import sys
import os
import pexpect

import hashlib

def hash_file(filepath): # GPT function, used to check that the file is the same
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):  # Read in chunks
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()

# Example usage
file_path = "Part-4-project/PMBus.py"
print(f"SHA-256: {hash_file(file_path)}")

def upload_to_board(lst):
    # All lists follow the form (repeat)
    # 1. Source location
    # 2. user (default = root)
    # 3. board_ip
    # 4. destination (default = "/home/root"
    fileLocationLocal = lst[0]
    usr = lst[1]
    ipAddress = lst[2]
    dest = lst [3]

    # check 1
    if not os.path.isfile(fileLocationLocal): # if it is not a file
        print(f"The file {fileLocationLocal} does not exist")
        return # reject

    # check 2
    # this one we skip
    if usr is None:
        usr = "root" # default
    # check 3
    #temp func, will rewrite
    if not ping_host(ipAddress):
        print(f"Ping failed at: {ipAddress}")
        return # reject

    # check 4
    # this one we skip
    print("All checks passed")

    # if all pass, then we can run the scp command
    cmd = f"scp {fileLocationLocal} {usr}@{ipAddress}:{dest}"
    print(cmd)

    try:
        print(f"Executing command: {cmd}")

        child = pexpect.spawn(cmd)
        child.expect('password:')
        child.sendline('root')
        for line in child: # progress bar
            print(f"Line: {line.decode('utf-8').strip()}")

        print("Copied successfully")

        print(f"Current Hash of {fileLocationLocal}:")
        print(hash_file(fileLocationLocal))
    except Exception as e:
        print(f"Error: {e}")


def ping_host(host, count=1, timeout=2):
    try:
        # Ping command depends on platform; this works on Linux/macOS
        result = subprocess.run(
            ["ping", "-c", str(count), "-W", str(timeout), host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0 # success
    except Exception:
        return False

# Example usage:
if __name__ == "__main__":

    board_ip = "192.168.9.2"

    # All lists follow the form
    # 1. Source location
    # 2. user (default = root)
    # 3. board_ip (defined above, otherwise defaults 192.168.9.2)
    # 4. destination (default = "/home/root"
    PMBuslst = ["/home/bkha345/Desktop/Scripts/Part-4-project/PMBus.py", "root", board_ip, "/home/root"]
    upload_to_board(PMBuslst)
    PMBUSWritelst = ["/home/bkha345/Desktop/Scripts/Part-4-project/PMBUSWrite.py", "root", board_ip, "/home/root"]
    upload_to_board(PMBUSWritelst)
    # Resnet18 = ["/home/bkha345/Desktop/Vitis-AI/resnet18.tar", "root", board_ip, "/home/root"]
    # upload_to_board(Resnet18)
    setuplst = ["/home/bkha345/Desktop/Scripts/Part-4-project/setup.py", "root", board_ip, "/home/root"]
    upload_to_board(setuplst)
    compendium = ["/home/bkha345/Desktop/Scripts/Part-4-project/compendium.txt", "root", board_ip, "/home/root"]
    upload_to_board(compendium)