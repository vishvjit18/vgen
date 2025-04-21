import json
import re
import os

def process_markdown_to_json(input_md_path, output_json_path):
    """
    Processes a markdown file with JSON content to clean JSON output.
    
    Args:
        input_md_path (str): Path to input markdown file
        output_json_path (str): Path for output JSON file
    """
    try:
        # Verify input file exists
        if not os.path.exists(input_md_path):
            raise FileNotFoundError(f"Input file not found: {input_md_path}")

        # Read the markdown file
        with open(input_md_path, 'r') as f:
            markdown_content = f.read()

        # Extract the JSON part by removing markdown code blocks
        json_str = re.sub(r'^```json\s*|```\s*$', '', markdown_content, flags=re.DOTALL).strip()
        
        # Parse the JSON into a Python dictionary
        data = json.loads(json_str)
        
        # Clean each source field in the Sub-Task entries
        for task in data['Sub-Task']:
            source = task['source']
            # Remove Verilog code block markers
            cleaned_source = re.sub(r'```verilog|```', '', source).strip()
            task['source'] = cleaned_source
        
        # Write the cleaned JSON to output file
        with open(output_json_path, 'w') as f:
            json.dump(data, f, indent=2)
            
        print(f"Successfully processed {input_md_path} to {output_json_path}")
        return True
        
    except Exception as e:
        print(f"Error processing files: {e}")
        return False

def process_iverilog_report_to_json(input_md_path, output_json_path):
    """
    Processes an iverilog report markdown file with JSON content to clean JSON output.
    
    Args:
        input_md_path (str): Path to input markdown file with iverilog report
        output_json_path (str): Path for output JSON file
    """
    try:
        # Verify input file exists
        if not os.path.exists(input_md_path):
            raise FileNotFoundError(f"Input file not found: {input_md_path}")

        # Read the markdown file
        with open(input_md_path, 'r') as f:
            markdown_content = f.read()

        # Extract the JSON part by removing markdown code blocks
        # The iverilog report is enclosed in ```json and ``` markers
        json_str = re.sub(r'^```json\s*|```\s*$', '', markdown_content, flags=re.DOTALL).strip()
        
        # Parse the JSON into a Python dictionary
        data = json.loads(json_str)
        
        # No need to clean Sub-Task entries as they don't exist in this format
        # Instead, we'll ensure the suggestions field has proper formatting
        
        # Check if files and testbench exist (defensive programming)
        if 'files' in data:
            if 'testbench' in data['files'] and 'suggesstions' in data['files']['testbench']:
                # Fix typo in key name if present (suggesstions -> suggestions)
                suggestions = data['files']['testbench'].pop('suggesstions', None)
                if suggestions is not None:
                    data['files']['testbench']['suggestions'] = suggestions
            
            if 'design' in data['files'] and 'suggesstions' in data['files']['design']:
                # Fix typo in key name if present (suggesstions -> suggestions)
                suggestions = data['files']['design'].pop('suggesstions', None)
                if suggestions is not None:
                    data['files']['design']['suggestions'] = suggestions
        
        # Write the cleaned JSON to output file
        with open(output_json_path, 'w') as f:
            json.dump(data, f, indent=2)
            
        print(f"Successfully processed {input_md_path} to {output_json_path}")
        return True
        
    except Exception as e:
        print(f"Error processing files: {e}")
        return False