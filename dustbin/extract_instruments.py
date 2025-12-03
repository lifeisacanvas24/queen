import json
import re
from typing import Any, Dict, List

# Define the input and output filenames
INPUT_FILE = 'complete.json'
EQ_FILE = 'all_eq.json'
FUTURES_FILE = 'all_fo.json'
OPTIONS_FILE = 'all_options.json'

def load_non_standard_json_file(filepath: str) -> List[Dict[str, Any]]:
    """Loads instruments from a non-standard file where multiple JSON objects
    are concatenated without being wrapped in a list or separated by commas.

    This function uses a regular expression to find all valid JSON objects
    in the file content and parses them one by one.
    """
    print(f"Reading data from {filepath}...")
    try:
        with open(filepath, encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Input file '{filepath}' not found.")
        return []

    # Regex to find all objects enclosed in balanced curly braces { ... }
    # This is a basic, non-robust way to find JSON objects. For production
    # code, a streaming JSON parser (like ijson) is recommended, but this
    # often works for simple instrument dumps.
    # We look for content starting with '{' and ending with '}'
    # The 's' flag ensures '.' matches newline characters.
    json_objects = re.findall(r'\{.*?\}', content, re.DOTALL)

    instruments = []

    for obj_str in json_objects:
        try:
            # Parse the extracted string into a Python dictionary
            instrument = json.loads(obj_str)
            instruments.append(instrument)
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse JSON object: {e}. Object skipped.")

    print(f"Successfully parsed {len(instruments)} instruments.")
    return instruments

def write_json_file(filepath: str, data: List[Dict[str, Any]]):
    """Writes a Python list of dictionaries to a file as a pretty-printed JSON array."""
    print(f"Writing {len(data)} items to {filepath}...")
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            # Write as a standard JSON array for easy loading later
            json.dump(data, f, indent=2)
    except OSError as e:
        print(f"Error writing to file {filepath}: {e}")

def process_instruments():
    """Main function to load, filter, and save the instrument data."""
    all_instruments = load_non_standard_json_file(INPUT_FILE)

    # Initialize the lists for the segregated data
    eq_instruments = []
    fo_futures = []
    fo_options = []

    # Define instrument types that classify as options
    OPTION_TYPES = {'CE', 'PE'} # Call and Put European

    # Iterate over all instruments and categorize them
    for instrument in all_instruments:
        segment = instrument.get('segment')
        instrument_type = instrument.get('instrument_type')

        if segment and 'EQ' in segment:
            # All Equity instruments (e.g., NSE_EQ, BSE_EQ)
            eq_instruments.append(instrument)

        elif segment == 'NSE_FO':
            if instrument_type in OPTION_TYPES:
                # Options (CE/PE)
                fo_options.append(instrument)
            elif instrument_type == 'FUT':
                # Futures (FUT)
                fo_futures.append(instrument)
            # You might add handling for other segment types here if needed

    # Write the segregated data to the output files
    write_json_file(EQ_FILE, eq_instruments)
    write_json_file(FUTURES_FILE, fo_futures)
    write_json_file(OPTIONS_FILE, fo_options)

    print("\nProcessing complete.")
    print(f"EQ Instruments saved to: {EQ_FILE}")
    print(f"FO Futures saved to: {FUTURES_FILE}")
    print(f"FO Options saved to: {OPTIONS_FILE}")

if __name__ == "__main__":
    process_instruments()
