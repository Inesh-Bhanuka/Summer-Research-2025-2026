import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

def generate_undervolt_plots(input_csv_path):
    # ==========================================
    # 1. PARSE FILENAME
    # ==========================================
    # Get the filename from the path (e.g., 'summary_ResNet18.csv')
    filename = os.path.basename(input_csv_path)
    
    # Remove extension
    name_without_ext = os.path.splitext(filename)[0]
    
    # Extract model name by removing 'summary_' prefix
    if name_without_ext.startswith('summary_'):
        model_name = name_without_ext.replace('summary_', '', 1)
    else:
        # Fallback if file doesn't match expected format
        model_name = name_without_ext
        
    print(f"Processing Model: {model_name}")

    # ==========================================
    # 2. LOAD AND TRANSFORM DATA
    # ==========================================
    print(f"Loading data from {input_csv_path}...")
    df = pd.read_csv(input_csv_path)

    # Transform units: Voltage -> mV, Accuracy -> %
    # We check columns to ensure safety
    if 'voltage' in df.columns and 'accuracy' in df.columns:
        df['Voltage (mV)'] = df['voltage'] * 1000
        df['Accuracy (%)'] = df['accuracy'] * 100
    else:
        print("Error: CSV must contain 'voltage' and 'accuracy' columns.")
        return

    # ==========================================
    # PLOTTING HELPER FUNCTION
    # ==========================================
    def create_single_plot(data, title_text, subtitle_text, x_lims, x_tick_step, output_filename):
        fig, ax = plt.subplots(figsize=(12, 6), facecolor='white')

        # Define Colors
        COLOR_BLUE = '#4285F4'
        COLOR_TITLE = '#5F6368'
        COLOR_SUBTITLE = '#9AA0A6'
        COLOR_GRID = '#E0E0E0'

        # Scatter Plot
        ax.scatter(data['Voltage (mV)'], data['Accuracy (%)'], color=COLOR_BLUE, s=50, zorder=3, clip_on=False)

        # Titles (Using extracted model name)
        ax.text(x=0.0, y=1.10, s=title_text, fontsize=20, color=COLOR_TITLE, 
                transform=ax.transAxes, ha='left', va='bottom')
        ax.text(x=0.0, y=1.03, s=subtitle_text, fontsize=12, color=COLOR_SUBTITLE, 
                transform=ax.transAxes, ha='left', va='bottom')

        # X-Axis Configuration
        ax.set_xlabel("Voltage (mV)", labelpad=15, color=COLOR_TITLE)
        ax.set_xlim(x_lims[0], x_lims[1]) 
        
        # Calculate ticks
        start, end = x_lims
        if start > end: # Decreasing voltage
            ticks = np.arange(start, end - 1, -x_tick_step)
        else:
            ticks = np.arange(start, end + 1, x_tick_step)
        ax.set_xticks(ticks)

        # Y-Axis Configuration
        ax.set_ylabel("Accuracy (%)", labelpad=15, color=COLOR_TITLE)
        ax.set_ylim(0, 118)
        ax.set_yticks(np.arange(0, 112.5 + 12.5, 12.5))

        # Grid and Styling
        ax.grid(True, color=COLOR_GRID, linestyle='-', linewidth=1.2, zorder=0)
        ax.set_axisbelow(True)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(COLOR_GRID)
        ax.spines['bottom'].set_color(COLOR_GRID)
        ax.tick_params(axis='both', which='major', labelsize=10, 
                       color=COLOR_GRID, labelcolor=COLOR_TITLE, pad=8)

        # Save Plot
        print(f"Saving plot to {output_filename}...")
        plt.subplots_adjust(top=0.88, bottom=0.15, left=0.08, right=0.95)
        plt.savefig(output_filename, dpi=150, bbox_inches='tight')
        plt.close(fig)

    # ==========================================
    # 3. GENERATE PLOTS
    # ==========================================
    
    # Plot 1: Overview
    # Filename format: {ModelName}_Overview.png
    create_single_plot(
        data=df,
        title_text=model_name,
        subtitle_text="Undervolt Results",
        x_lims=(851, 561),
        x_tick_step=10,
        output_filename=f"{model_name}_Overview.png"
    )

    # Plot 2: Critical Region
    # Filename format: {ModelName}_Critical_Region.png
    critical_data = df[(df['Voltage (mV)'] <= 600) & (df['Voltage (mV)'] >= 570)]
    
    create_single_plot(
        data=critical_data,
        title_text=model_name,
        subtitle_text="Undervolt Results (Critical Region)",
        x_lims=(600, 570),
        x_tick_step=1,
        output_filename=f"{model_name}_Critical_Region.png"
    )

if __name__ == "__main__":
    # Example usage
    # Ensure this file exists in your directory
    file_path = 'summary_SqueezeNet.csv'
    
    if os.path.exists(file_path):
        generate_undervolt_plots(file_path)
    else:
        print(f"File not found: {file_path}")