import re


def is_progress_line(line):
    """
    Check if a line is likely a progress indicator that should be skipped
    """
    # Common patterns in progress lines
    progress_patterns = [
        r'⠋|⠙|⠹|⠸|⠼|⠴|⠦|⠧|⠇|⠏',  # Spinner characters
        r'\[#*\s*\]',  # Progress bars
        r'idealTree:.*',  # npm specific progress
        r'reify:.*',  # npm specific progress
        r'\([^)]*\)\s*�[⠀-⣿]',  # Progress with spinner
    ]
    
    return any(re.search(pattern, line) for pattern in progress_patterns)


def clean_ansi(text):
    # Step 1: Remove ANSI escape sequences
    ansi_escape = re.compile(r'''
        \x1B  # ESC
        (?:   # 7-bit C1 Fe (except CSI)
            [@-Z\\-_]
        |     # or [ for CSI
            \[
            [0-?]*  # parameter bytes
            [ -/]*  # intermediate bytes
            [@-~]   # final byte
        )
    ''', re.VERBOSE)
    
    text = ansi_escape.sub('', text)
    
    # Step 2: Split into lines and process terminal control characters
    lines = text.splitlines()
    screen = []
    current_line = ""
    
    for line in lines:
        # Handle carriage return (simulate line overwrites)
        if '\r' in line:
            parts = line.split('\r')
            # Process each part
            for part in parts:
                # Handle backspaces in this part
                while '\x08' in part:
                    part = re.sub(r'.\x08', '', part, 1)
                
                # Overwrite current line from the start
                current_line = part
        else:
            # Handle backspaces
            while '\x08' in line:
                line = re.sub(r'.\x08', '', line, 1)
            current_line = line
        
        # Only add non-empty lines that aren't just progress indicators
        if current_line.strip() and not is_progress_line(current_line):
            screen.append(current_line)
    
    # Remove duplicate consecutive lines
    unique_lines = []
    prev_line = None
    for line in screen:
        if line != prev_line:
            unique_lines.append(line)
            prev_line = line
    
    # If we have 0 lines because all where progress lines, return the last one
    if not unique_lines:
        return current_line
    
    # Join lines and clean up any remaining control characters
    cleaned_output = '\n'.join(unique_lines) + '\n'
    return cleaned_output