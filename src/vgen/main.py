import sys
import warnings
import json
from datetime import datetime
import os
from dotenv import load_dotenv  # Add this import
from vgen.utils.markdown_to_json import process_markdown_to_json
from vgen.crew import Vgen

# Load the environment variables from .env file
load_dotenv()
gemini_api_key = os.getenv('GEMINI_API_KEY')
os.environ["GEMINI_API_KEY"] = gemini_api_key

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

def run():
    """
    Run the planning crew, convert the result to JSON,
    and then execute the Verilog conversion crew.
    """
    inputs = {
        'Target_Problem': """Please act as a professional verilog designer.

Implement a module of an 8-bit adder with multiple bit-level adders in combinational logic. 

Module name:  
    adder_8bit               
Input ports:
    a[7:0]: 8-bit input operand A.
    b[7:0]: 8-bit input operand B.
    cin: Carry-in input.
Output ports:
    sum[7:0]: 8-bit output representing the sum of A and B.
    cout: Carry-out output.

Implementation:
The module utilizes a series of bit-level adders (full adders) to perform the addition operation.

Give me the complete code.
 """,
    }

    try:
        # 1. Run the high-level planning crew
        print("\n==== RUNNING PLANNING CREW ====\n")
        crew1 = Vgen().crew1()
        crew1_output = crew1.kickoff(inputs=inputs)
        print(crew1_output)
        print(crew1.usage_metrics)

        input_md = 'high_level_planning_task.md'
        output_json = 'verilog_task.json'

        # 2. Process the markdown into structured subtasks (JSON)
        print("\n==== PROCESSING MARKDOWN TO JSON ====\n")
        success = process_markdown_to_json(input_md, output_json)
        if not success:
            raise Exception("Failed to process markdown output")

        # 3. Now that JSON exists, create Vgen instance
        vgen = Vgen()
        
        # 4. Run the subtasks crew to generate individual Verilog modules
        print("\n==== RUNNING SUBTASKS CREW ====\n")
        subtask_crew = vgen.subtask_crew()
        subtask_outputs = subtask_crew.kickoff()
        print(f"Completed subtasks: {subtask_outputs}")
        
        # 5. Run the merging crew to combine all the modules
        print("\n==== RUNNING MERGING CREW ====\n")
        merging_crew = vgen.merging_crew()
        merging_output = merging_crew.kickoff()
        print(merging_output)
        
        # 6. Save the merged result
        vgen._save_results([merging_output])
        
        # 7. Generate testbench
        print("\n==== GENERATING TESTBENCH ====\n")
        testbench_crew = vgen.testbench_crew()
        testbench_output = testbench_crew.kickoff()
        print(testbench_output)
        print("\n==== TESTBENCH GENERATION COMPLETE ====\n")

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
