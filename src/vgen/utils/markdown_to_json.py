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
        
        # Debug output for troubleshooting
        print(f"Extracted JSON string (first 200 chars): {json_str[:200]}...")
        
        try:
            # Parse the JSON into a Python dictionary
            data = json.loads(json_str)
            
            # Write the cleaned JSON to output file (keep original keys)
            with open(output_json_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            print(f"Successfully processed {input_md_path} to {output_json_path}")
            return True
        except json.JSONDecodeError as je:
            # Special handling for JSON parsing errors
            print(f"JSON parsing error: {je}")
            print(f"Error at position {je.pos}, line: {je.lineno}, column: {je.colno}")
            print(f"Context: {json_str[max(0, je.pos-50):je.pos]}>>HERE<<{json_str[je.pos:je.pos+50]}")
            return False
        
    except Exception as e:
        print(f"Error processing files: {e}")
        return False