# This file is used just for any setup the board may require
import subprocess
# set the ip of the board to 192.168.9.2
import hashlib

def hash_file(filepath): # GPT function, used to check that the file is the same
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):  # Read in chunks
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


ip = "192.168.9.2"
print(f"Configuring ip to {ip}")
subprocess.run(f"ifconfig eth0 {ip}", shell = True)
print(f"Configured ip")

# check the current version of the PMBus script
file_path = "PMBus.py"
print(f"SHA-256 PMBus: {hash_file(file_path)}")
# check the current version of the PMBusWrite script
file_path = "PMBUSWrite.py"
print(f"SHA-256 PMBUSWrite: {hash_file(file_path)}")
# End Of Program
print("==============")
print("Setup Complete")
print("==============")
