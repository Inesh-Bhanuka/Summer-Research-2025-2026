function create_plots(filename)
% create_plots Creates plots from an undervolting CSV.
%   Usage: create_plots('summary_ResNet50.csv')
%
%   Updated with robust "Cliff Detection" to fix x-axis scaling issues.

    % =========================================================================
    % 1. VALIDATION AND SETUP
    % =========================================================================
    arguments
        filename (1,1) string
    end

    if ~isfile(filename)
        error('Error: File "%s" not found.', filename);
    end

    [~, name, ~] = fileparts(filename);
    modelName = strrep(name, 'summary_', '');
    fprintf('Processing Model: %s\n', modelName);

    data = readtable(filename);
    volt_mV = data.voltage * 1000;
    acc_pct = data.accuracy * 100;


    % =========================================================================
    % 2. DETECT SEPARATE TEST RUNS
    % =========================================================================
    runID = ones(height(data), 1);
    currentRun = 1;
    v_raw = data.voltage; 
    
    for i = 2:length(v_raw)
        % New run if voltage jumps > 50mV
        if v_raw(i) > (v_raw(i-1) + 0.05)
            currentRun = currentRun + 1;
        end
        runID(i) = currentRun;
    end
    fprintf('Detected %d distinct test run(s).\n', max(runID));


    % =========================================================================
    % 3. ROBUST CRITICAL REGION LOGIC (FIXED)
    % =========================================================================
    % Step 1: Establish a "Stable Baseline" accuracy
    % We look at the top 50% of the voltage range to determine "normal"
    min_v = min(volt_mV);
    max_v = max(volt_mV);
    range_v = max_v - min_v;
    high_v_cutoff = min_v + (range_v * 0.5);
    
    % Get accuracy of all points in the high voltage region
    high_v_accs = acc_pct(volt_mV >= high_v_cutoff);
    
    if isempty(high_v_accs)
        baseline_acc = max(acc_pct); % Fallback
    else
        baseline_acc = median(high_v_accs); % Use Median to ignore outliers
    end
    
    % Step 2: Define Threshold (5% absolute drop from baseline)
    % This ignores small noise and finds the actual cliff.
    drop_threshold = baseline_acc - 5.0; 
    
    % Step 3: Find the "Knee" (First voltage from top where acc < threshold)
    % We process sorted unique voltages to find the crossing point
    sorted_unique_v = sort(unique(volt_mV), 'descend');
    knee_voltage = min_v; % Default to bottom if no crash found
    
    for i = 1:length(sorted_unique_v)
        v = sorted_unique_v(i);
        % Check if ANY point at this voltage is below threshold
        % (Using min() here ensures we catch the first sign of instability)
        if min(acc_pct(volt_mV == v)) < drop_threshold
            knee_voltage = v;
            break;
        end
    end
    
    % Step 4: Set Limits with buffer
    % +20mV buffer above the knee, rounded to nearest 10
    crit_upper = ceil((knee_voltage + 20)/10) * 10;
    crit_lower = floor(min_v/10) * 10; % Bottom of dataset
    
    % Safety: Don't let upper limit exceed max voltage
    crit_upper = min(crit_upper, ceil(max_v/10)*10);

    crit_lims = [crit_upper, crit_lower];
    
    % Determine Tick Step
    if abs(crit_upper - crit_lower) <= 50
        crit_step = 1;
    else
        crit_step = 5;
    end
    
    fprintf('Baseline Acc: %.2f%%. Cliff detected at %d mV.\n', baseline_acc, knee_voltage);
    fprintf('Zoom View: %d mV to %d mV\n', crit_upper, crit_lower);


    % =========================================================================
    % 4. CREATE FIGURE AND TABS
    % =========================================================================
    figName = [char(modelName) ' Results'];
    f = figure('Name', figName, 'NumberTitle', 'off', ...
               'Color', 'w', 'Position', [100, 100, 1200, 600]);     
    tabGroup = uitabgroup(f);

    % --- TAB 1: OVERVIEW ---
    tab1 = uitab(tabGroup, 'Title', 'Overview');
    ov_upper = ceil(max(volt_mV)/10)*10;
    ov_lower = floor(min(volt_mV)/10)*10;
    
    create_tab_plot(tab1, volt_mV, acc_pct, runID, modelName, ...
        'Undervolt Results', [ov_upper, ov_lower], 10);

    % --- TAB 2: CRITICAL REGION ---
    tab2 = uitab(tabGroup, 'Title', 'Critical Region');
    in_view = (volt_mV <= crit_upper) & (volt_mV >= crit_lower);
    
    create_tab_plot(tab2, volt_mV(in_view), acc_pct(in_view), runID(in_view), ...
        modelName, 'Undervolt Results (Critical Region)', crit_lims, crit_step);

    % Save
    outputFilename = [char(modelName) '_Combined_Tabs.fig'];
    savefig(f, outputFilename);
    fprintf('Saved to %s\n', outputFilename);
end


% =========================================================================
% LOCAL PLOTTING FUNCTION
% =========================================================================
function create_tab_plot(parentTab, x_data, y_data, group_ids, titleText, subtitleText, x_lims, x_step)
    ax = axes('Parent', parentTab);
    axes(ax); 
    
    colors = [0.259 0.522 0.957; ... 
              0.859 0.267 0.216; ... 
              0.957 0.650 0.050; ... 
              0.059 0.616 0.345; ... 
              0.671 0.278 0.737; ... 
              0.000 0.737 0.831];    

    hold on;
    present_runs = unique(group_ids);
    plot_handles = [];
    legend_labels = {};
    
    for i = 1:length(present_runs)
        r_id = present_runs(i);
        idx = group_ids == r_id;
        color_idx = mod(r_id - 1, size(colors, 1)) + 1;
        
        h = scatter(x_data(idx), y_data(idx), 70, colors(color_idx, :), 'filled', ...
            'MarkerFaceAlpha', 0.8);
        plot_handles = [plot_handles, h]; %#ok<AGROW> 
        legend_labels{end+1} = sprintf('Run %d', r_id); %#ok<AGROW> 
    end
    
    color_title = [95, 99, 104] / 255;      
    color_subtitle = [154, 160, 166] / 255; 
    color_grid = [224, 224, 224] / 255;     

    ax.XColor = color_title;
    ax.YColor = color_title;
    ax.FontSize = 10;
    ax.LineWidth = 1;
    grid on;
    ax.GridColor = color_grid;
    ax.GridAlpha = 1; 
    box off; 
    
    xlabel('Voltage (mV)', 'Color', color_title, 'FontSize', 11);
    
    sorted_lims = sort(x_lims);
    xlim(sorted_lims);
    if x_lims(1) > x_lims(2)
        set(ax, 'XDir', 'reverse'); 
    else
        set(ax, 'XDir', 'normal');
    end
    
    % Ensure ticks don't crash if step is 0 or range is weird
    if x_step > 0 && diff(sorted_lims) > 0
        xticks(sorted_lims(1):x_step:sorted_lims(2));
    end

    ylabel('Accuracy (%)', 'Color', color_title, 'FontSize', 11);
    ylim([0 118]);
    yticks(0:12.5:112.5);
    
    text(0, 1.10, char(titleText), 'Units', 'normalized', ...
        'FontSize', 20, 'Color', color_title, 'FontWeight', 'normal');
    text(0, 1.04, char(subtitleText), 'Units', 'normalized', ...
        'FontSize', 12, 'Color', color_subtitle);
    
    if ~isempty(plot_handles)
        lgd = legend(plot_handles, legend_labels, 'Location', 'southwest');
        lgd.Box = 'off';
        lgd.TextColor = color_title;
        lgd.FontSize = 9;
    end
    
    ax.Position = [0.08 0.15 0.90 0.73];
    hold off;
end