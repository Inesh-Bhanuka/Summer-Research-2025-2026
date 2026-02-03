# import numpy as np
# import matplotlib.pyplot as plt
#
#
# # Function to plot cosine graph between a and b
# def plot_cosine(a, b):
#     import copy
#     # Ensure a and b are between 0 and 1
#     if not (0 < a < 1 and 0 < b < 1):
#         raise ValueError("Both a and b must be between 0 and 1")
#
#     # Generate values between a and b
#     seconds = 250
#     total_numbers = seconds * 2
#
#     x_values = np.linspace(0, np.pi*6, total_numbers)  # 500 points between a and b for smooth curve
#     amplitude = (b-a)/2
#     offset = a + (b-a)/2
#     y_values = amplitude * np.cos(x_values)+offset
#     y_values_mock = y_values.copy()
#     # since we can only deal with a depth of 4096, we need it to constantly change
#     f = open("compendium.txt", "w")
#     for i in range(len(y_values)):
#         f.write(str(y_values[i]) + "\n")
#         y_values_mock[i] = y_values[i]*4096
#     f.close()
#     print(y_values_mock)
#     # Plot the graph
#     plt.plot(x_values, y_values, label=f'Cosine curve from {a} to {b}')
#     plt.title('Cosine Graph')
#     plt.xlabel('X values')
#     plt.ylabel('Cosine(X)')
#     plt.grid(True)
#     # plt.legend()
#     plt.show()
#
# # Example usage
# lower = 0.6
# upper = 0.85
# plot_cosine(lower, upper)


import re
import numpy as np
import matplotlib.pyplot as plt
NUMBER=20
history = np.array([0.0 for i in range(NUMBER)])
# history = [0 for i in range(20)]

# read the last line of the file
def get_last_line_large_file(filename):
    last_line = None
    with open(filename, 'r') as f:
        lines = f.readlines()
        last_line = lines[-5]
        print(last_line)
        # for line in f:
        #     last_line = line.strip()
    if last_line:
        return last_line
    else:
        print(f"Error reading: {filename}")
        return None

# # Initialize figure and plot
fig, ax = plt.subplots()
line, = ax.plot([], [], 'b-', lw=2)

# Set axis limits
ax.set_xlim(0, 2 * np.pi)
ax.set_ylim(0.5, 1)

# # Show the plot
plt.xlabel('Time')
plt.ylabel('Amplitude')
plt.title('Real-Time Sine Wave')
# plt.show()

while True:

    a = (get_last_line_large_file("log.txt"))
    pattern=r"Power: (\d*.\d*)V x (\d*.\d*)A = (\d*.\d*)W"

    match = re.match(pattern, a)
    if match:
        print(match.groups())
        history = np.roll(history, -1)
        history[-1] = (match.group(1))

    print(history)

    # Update plot data
    line.set_data(np.linspace(0, 5, NUMBER), history)

    # Redraw the plot
    plt.draw()

    # Pause to simulate real-time data plotting
    plt.pause(0.25)  # Control the update rate
