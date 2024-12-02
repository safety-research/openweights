import re

import numpy as np
import pandas as pd
import seaborn as sns
from dotenv import load_dotenv
from matplotlib import pyplot as plt

from openweights import OpenWeights


def flatten(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, dict):
            field = flatten(value)
            for subkey, subvalue in field.items():
                result[f"{key}.{subkey}"] = subvalue
        else:
            result[key] = value
    return result

def unflatten(row):
    result = {}
    for key, value in row.items():
        parts = key.split('.')
        current = result
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
    return convert_to_standard_types(result)

def convert_to_standard_types(obj):
    if isinstance(obj, dict):
        return {k: convert_to_standard_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_standard_types(item) for item in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, bytes):
        try:
            return obj.decode('utf-8')  # Attempt to decode as UTF-8
        except UnicodeDecodeError:
            return obj.hex()  # Fallback: represent as hex string
    elif isinstance(obj, tuple):
        return list(obj)  # Convert tuples to lists
    else:
        return obj

def forwardfill(sorted_rows, columns=['data.step']):
    current = {}
    updated_rows = []
    for row in sorted_rows:
        row = dict(current, **row)
        current = {col: row[col] for col in columns}
        updated_rows.append(row)
    return updated_rows


def matches(pattern, string):
    pattern = pattern.replace('*', '.*')
    return re.match(pattern, string)

def resolve(df, columns):
    if isinstance(columns, list):
        resolved = []
        for col in columns:
            resolved += resolve(df, col)
        return resolved
    columns = [col for col in df.columns if matches(columns, col)]
    return columns

def compare(df, groupby='params.*', x='params.learning_rate', y='outputs.eval_loss', 
           subplot_rows='params.epochs', subplot_cols='model', 
           x_scale='log', y_scale='linear', font_size=18, ignore=['params.meta.*', 'params.finetuned_model_id']):
    """
    Take a dataframe and group it based on columns that match the `groupby` pattern, except when columns are used for x or y.
    Each group then produces one graph based on the x and y columns.
    All graphs are plotted in the same plot, unless subplot_rows and/or subplot_cols are specified.
    When they are specified, we create a figure with multiple subplots and use the values of these rows as 
    row or column headings (row headings: on the left side vertically, column headings: on the top).
    
    Improvements:
    - Shared x and y axis limits across all subplots
    - Consistent font sizes and styling
    - Detailed subplot and legend configuration
    """
    # Only group by the essential varying parameters
    groupby_cols = [col for col in resolve(df, groupby) if col not in [x, y, subplot_cols, subplot_rows] + resolve(df, ignore)]
    # Remove cols that have a single unique value - handle json/list columns
    groupby_cols = [col for col in groupby_cols if  len(df[col].apply(str).unique()) > 1]

    print(f"\nGrouping by: {groupby_cols}")
    
    # Get unique values for subplot rows and columns
    row_values = sorted(df[subplot_rows].unique()) if subplot_rows else [None]
    col_values = sorted(df[subplot_cols].unique()) if subplot_cols else [None]
    
    n_rows = len(row_values)
    n_cols = len(col_values)
    
    # Define font sizes with larger values
    label_fontsize = font_size
    title_fontsize = font_size + 4
    legend_fontsize = font_size + 2
    column_title_fontsize = font_size + 4
    row_label_fontsize = font_size + 2
    suptitle_fontsize = font_size + 6
    
    # Create figure and subplots with adjusted margins for row labels and column titles
    fig_width = 6 * n_cols + 3  # Increased base width
    fig_height = 5 * n_rows + 2  # Increased base height
    fig, axes = plt.subplots(n_rows, n_cols, 
                             figsize=(fig_width, fig_height),
                             squeeze=False)
    
    # Prepare for shared axis limits
    x_min, x_max = np.inf, -np.inf
    y_min, y_max = np.inf, -np.inf
    
    # Flatten axes for easy iteration if there's only one row or column
    axes = axes if n_rows > 1 and n_cols > 1 else axes.reshape(n_rows, n_cols)
    
    # Collect all unique group labels across the entire dataframe for consistent coloring
    if groupby_cols:
        groups = df.groupby(groupby_cols)
        group_keys = groups.size().reset_index()[groupby_cols].apply(tuple, axis=1).tolist()
    else:
        group_keys = [None]
    
    # Create a color palette
    num_groups = len(group_keys)
    palette = sns.color_palette("tab10", num_groups)  # Adjust palette as needed
    color_mapping = {group: palette[i % len(palette)] for i, group in enumerate(group_keys)}
    
    # To collect legend handles and labels
    legend_handles = []
    legend_labels = []
    
    # First pass: determine global x and y limits
    for i, row_val in enumerate(row_values):
        for j, col_val in enumerate(col_values):
            # Filter data for this subplot
            mask = pd.Series(True, index=df.index)
            if subplot_rows:
                mask &= (df[subplot_rows] == row_val)
            if subplot_cols:
                mask &= (df[subplot_cols] == col_val)
            subplot_data = df[mask]
            
            # Update global min and max
            x_min = min(x_min, subplot_data[x].min())
            x_max = max(x_max, subplot_data[x].max())
            y_min = min(y_min, subplot_data[y].min())
            y_max = max(y_max, subplot_data[y].max())
    
    # Second pass: actually plot the data
    for i, row_val in enumerate(row_values):
        for j, col_val in enumerate(col_values):
            ax = axes[i, j]
            
            # Filter data for this subplot
            mask = pd.Series(True, index=df.index)
            if subplot_rows:
                mask &= (df[subplot_rows] == row_val)
            if subplot_cols:
                mask &= (df[subplot_cols] == col_val)
            subplot_data = df[mask]
            
            # Plotting
            if groupby_cols:
                groups = subplot_data.groupby(groupby_cols)
                
                for name, group in groups:
                    if not isinstance(name, tuple):
                        name = (name,)
                    
                    # Sort by x value
                    group = group.sort_values(by=x)
                    
                    # Create label from the groupby parameters
                    param_values = [f"{col.split('.')[-1]}={val}" for col, val in zip(groupby_cols, name)]
                    label = ', '.join(param_values)
                    
                    # Assign color based on group
                    color = color_mapping[tuple(name)]
                    
                    # Plot the group
                    line, = ax.plot(group[x], group[y], 'o-', label=label, color=color, markersize=8)
                    
                    # Collect handles and labels for the legend
                    if label not in legend_labels:
                        legend_handles.append(line)
                        legend_labels.append(label)
            else:
                # If no groups, just plot the data
                subplot_data = subplot_data.sort_values(by=x)
                ax.plot(subplot_data[x], subplot_data[y], 'o-', color='blue', markersize=8)
            
            # Set scales (before setting limits to ensure correct scaling)
            ax.set_xscale(x_scale)
            ax.set_yscale(y_scale)
            
            # Set shared axis limits (handle different scales carefully)
            if x_scale == 'log':
                ax.set_xlim(x_min * 0.9, x_max * 1.1)
            else:
                ax.set_xlim(x_min - (x_max - x_min) * 0.05, x_max + (x_max - x_min) * 0.05)
            
            if y_scale == 'log':
                ax.set_ylim(y_min * 0.9, y_max * 1.1)
            else:
                ax.set_ylim(y_min - (y_max - y_min) * 0.05, y_max + (y_max - y_min) * 0.05)

            # Column titles
            if i == 0 and col_val is not None:
                ax.set_title(str(col_val), fontsize=column_title_fontsize)

            # Row labels
            if j == 0 and row_val is not None:
                ax.set_ylabel(f"{subplot_rows}={row_val}", fontsize=row_label_fontsize)

            # X-axis labels
            if i == len(row_values) - 1:
                ax.set_xlabel(x, fontsize=label_fontsize)
            
            # Adjust tick parameters
            ax.tick_params(axis='both', which='major', labelsize=label_fontsize - 2)
    
    # Add a shared legend
    if legend_handles:
        fig.legend(legend_handles, legend_labels, 
                   loc='lower center', 
                   bbox_to_anchor=(0.5, -0.1),  # Adjust this to position the legend
                   ncol=min(len(legend_labels), 5),  # Spread out legend if many labels
                   fontsize=legend_fontsize)
    
    # Super title with increased font size
    plt.suptitle(f"{x} vs {y}", fontsize=suptitle_fontsize)
    
    # Adjust layout to make room for the legend
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])  # Leave space for the legend
    
    return fig