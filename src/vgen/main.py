#!/usr/bin/env python
import sys
import warnings
import json
from datetime import datetime
import os
from dotenv import load_dotenv  # Add this import
from vgen.utils.markdown_to_json import process_markdown_to_json

# Load the environment variables from .env file
load_dotenv()
gemini_api_key = os.getenv('GEMINI_API_KEY')
os.environ["GEMINI_API_KEY"] = gemini_api_key

from vgen.crew import Vgen

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def run():
    """
    Run the crew and process its output markdown file.
    """
    inputs = {
        'Target_Problem': 'write a verilog code for a 4-bit adder',
    }
    
    try:
        # Run the crew (which saves its own .md file)
        crew = Vgen().crew()
        crew_output = crew.kickoff(inputs=inputs)
        print(crew_output)
        print(crew.usage_metrics)
        
        # 2. Define file paths (modify these to match your actual paths)
        input_md = 'high_level_planning_task.md'          # Path where crew saves its markdown
        output_json = 'cleaned.json'    # Path for cleaned output
        
        # 3. Process the markdown to cleaned JSON
        success = process_markdown_to_json(input_md, output_json)
        if not success:
            raise Exception("Failed to process markdown output")
            
        print("Crew execution and cleanup completed successfully")
        
    except Exception as e:
        raise Exception(f"An error occurred: {e}")


def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        "Target_Problem": "write a verilog code for a 4-bit adder"
    }
    try:
        Vgen().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        Vgen().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        "Target_Problem": "write a verilog code for a 4-bit adder",
        "current_year": str(datetime.now().year)
    }
    try:
        Vgen().crew().test(n_iterations=int(sys.argv[1]), openai_model_name=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")
