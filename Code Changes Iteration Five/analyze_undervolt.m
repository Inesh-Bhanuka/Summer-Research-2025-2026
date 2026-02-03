function analyze_undervolt(filename)
% ANALYZE_UNDERVOLT Generates Accuracy vs Power plots.
%   Usage: analyze_undervolt('summary_ResNet50.csv')
%
%   Updated: X-Axis is now reversed (High Power -> Low Power).

    % =========================================================================
    % 1. SETUP AND LOAD
    % =========================================================================
    arguments
        filename (1,1) string
    end

    if ~isfile(filename)
        error('Error: File "%s" not found.', filename);
    end

    [~, name, ~] = fileparts(filename);
    modelName = strrep(name, 'summary_', '');
    fprintf('------------------------------------------------\n');
    fprintf('Processing Model: %s\n', modelName);
    fprintf('------------------------------------------------\n');

    data = readtable(filename);
    
    % --- Extract Columns ---
    volt_mV = data.voltage * 1000;
    acc_pct = data.accuracy * 100;
    
    if ismember('avg_power_watts', data.Properties.VariableNames)
        pwr_W = data.avg_power_watts;
    else
        warning('Column "avg_power_watts" not found. Simulating dummy power.');
        pwr_W = (volt_mV / 850).^2 * 8; 
    end

    % =========================================================================
    % 2. DETECT RUNS (for coloring)
    % =========================================================================
    runID = ones(height(data), 1);
    currentRun = 1;
    v_raw = data.voltage;
    for i = 2:length(v_raw)
        if v_raw(i) > (v_raw(i-1) + 0.05) % Voltage jump > 50mV
            currentRun = currentRun + 1;
        end
        runID(i) = currentRun;
    end

    % =========================================================================
    % 3. ROBUST CRITICAL REGION & EFFICIENCY STATS
    % =========================================================================
    % --- A. Find Baseline Accuracy ---
    min_v = min(volt_mV);
    max_v = max(volt_mV);
    
    high_v_cutoff = min_v + (max_v - min_v) * 0.5;
    high_v_indices = volt_mV >= high_v_cutoff;
    
    if any(high_v_indices)
        baseline_acc = median(acc_pct(high_v_indices));
    else
        baseline_acc = max(acc_pct);
    end
    
    % --- B. Find Knee (Cliff) Voltage ---
    drop_threshold = baseline_acc - 5.0; 
    sorted_unique_v = sort(unique(volt_mV), 'descend');
    knee_voltage = min_v; 
    
    for i = 1:length(sorted_unique_v)
        v = sorted_unique_v(i);
        if min(acc_pct(volt_mV == v)) < drop_threshold
            knee_voltage = v;
            break;
        end
    end
    
    % --- C. Define Critical Voltage Limits ---
    crit_upper_v = ceil((knee_voltage + 20)/10) * 10;
    crit_upper_v = min(crit_upper_v, ceil(max_v/10)*10); 
    crit_lower_v = floor(min_v/10) * 10;
    
    fprintf('Critical Voltage Range Detected: %d mV to %d mV\n', crit_upper_v, crit_lower_v);

    % --- D. Calculate Power Stats ---
    get_pwr_at = @(v_target) median(pwr_W(abs(volt_mV - v_target) < 2));
    
    base_pwr = get_pwr_at(max_v);
    
    if knee_voltage == min_v && min_v < max_v
         crit_pwr = get_pwr_at(min_v); 
    else
         crit_pwr = get_pwr_at(knee_voltage);
    end

    end_pwr = get_pwr_at(min_v);

    gain_crit = (base_pwr - crit_pwr) / base_pwr * 100;
    gain_max  = (base_pwr - end_pwr)  / base_pwr * 100;

    fprintf('\n--- POWER CONSUMPTION STATS ---\n');
    fprintf('Base Power (at %.0f mV):       %.2f W\n', max_v, base_pwr);
    fprintf('Critical Power (at %.0f mV):   %.2f W\n', knee_voltage, crit_pwr);
    fprintf('Min Power (at %.0f mV):        %.2f W\n', min_v, end_pwr);
    
    fprintf('\n--- EFFICIENCY GAINS ---\n');
    fprintf('Gain at Critical Section:   %.2f%%\n', gain_crit);
    fprintf('Gain at End of Data:        %.2f%%\n', gain_max);
    fprintf('------------------------------------------------\n');


    % =========================================================================
    % 4. PLOTTING (ACCURACY VS POWER)
    % =========================================================================
    figName = [char(modelName) ' Power Efficiency'];
    f = figure('Name', figName, 'NumberTitle', 'off', ...
               'Color', 'w', 'Position', [100, 100, 1000, 600]);     
    tabGroup = uitabgroup(f);

    % --- TAB 1: GLOBAL POWER EFFICIENCY ---
    t1 = uitab(tabGroup, 'Title', 'Undervolting Results');
    
    create_power_plot(t1, pwr_W, acc_pct, runID, ...
        modelName, 'Accuracy as Power Decreases', ...
        'Undervolting Results');

    % --- TAB 2: CRITICAL REGION EFFICIENCY ---
    t2 = uitab(tabGroup, 'Title', 'Accuracy as Power Decreases');
    
    mask = (volt_mV <= crit_upper_v) & (volt_mV >= crit_lower_v);
    
    if sum(mask) > 0
        create_power_plot(t2, pwr_W(mask), acc_pct(mask), runID(mask), ...
            modelName, 'Accuracy as Power Decreases', ...
            sprintf('Critical Region Filtered for Voltage [%d mV - %d mV]', crit_upper_v, crit_lower_v));
    else
        uicontrol(t2, 'Style', 'text', 'String', 'No data in critical region', ...
            'Position', [100 100 200 20]);
    end

    % Save
    outputFilename = [char(modelName) '_Power_Efficiency.fig'];
    savefig(f, outputFilename);
    fprintf('Plot saved to %s\n', outputFilename);
end


% =========================================================================
% LOCAL PLOTTING FUNCTION
% =========================================================================
function create_power_plot(parent, x_pwr, y_acc, runs, titleT, mainT, subT)
    ax = axes('Parent', parent);
    axes(ax); hold on;
    
    colors = [0.259 0.522 0.957; 0.859 0.267 0.216; 0.957 0.650 0.050; 0.059 0.616 0.345];
    
    u_runs = unique(runs);
    handles = []; labels = {};
    for i = 1:length(u_runs)
        rid = u_runs(i);
        mask = runs == rid;
        c = colors(mod(rid-1,4)+1, :);
        h = scatter(x_pwr(mask), y_acc(mask), 60, c, 'filled', 'MarkerFaceAlpha', 0.8);
        handles = [handles, h]; %#ok<AGROW>
        labels{end+1} = sprintf('Run %d', rid); %#ok<AGROW>
    end
    
    grid on; box off;
    ax.GridColor = [0.9 0.9 0.9];
    ax.FontSize = 10;
    
    % --- REVERSE X-AXIS ---
    % High Power (Left) -> Low Power (Right)
    set(ax, 'XDir', 'reverse'); 
    
    xlabel('Power (Watts)', 'Color', [0.3 0.3 0.3], 'FontSize', 11);
    ylabel('Accuracy (%)', 'Color', [0.3 0.3 0.3], 'FontSize', 11);
    
    axis tight;
    xl = xlim; 
    % When reversed, xl(1) is actually the larger number mathematically in some contexts,
    % but standard min/max logic applies. We just add padding.
    xlim([min(xl)*0.95, max(xl)*1.05]);
    ylim([0, 115]); 
    
    text(0, 1.12, char(titleT), 'Units','normalized', 'FontSize',18, 'Color',[0.3 0.3 0.3], 'FontWeight', 'bold');
    text(0, 1.07, char(mainT), 'Units','normalized', 'FontSize',14, 'Color',[0.4 0.4 0.4]);
    text(0, 1.03, char(subT), 'Units','normalized', 'FontSize',10, 'Color',[0.6 0.6 0.6]);
    
    if ~isempty(handles)
        legend(handles, labels, 'Location', 'southeast', 'Box', 'off');
    end
    
    ax.Position = [0.08 0.15 0.88 0.70]; 
end