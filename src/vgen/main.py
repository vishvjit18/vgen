import sys
import warnings
import json
from datetime import datetime
import os
from dotenv import load_dotenv  # Add this import
from vgen.utils.markdown_to_json import process_markdown_to_json, process_iverilog_report_to_json
from vgen.crew import Vgen
from vgen.config import Target_Problem
import glob
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
        'Target_Problem': Target_Problem
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
        
        # 4. Run the subtasks crew to generate individual Verilog modules
        print("\n==== RUNNING SUBTASKS CREW ====\n")
        subtask_crew = Vgen().subtask_crew()
        subtask_outputs = subtask_crew.kickoff()
        print(f"Completed subtasks: {subtask_outputs}")
        
        # 5. Run the merging crew to combine all the modules
        print("\n==== RUNNING MERGING CREW ====\n")
        crew2 = Vgen().merging_crew()
        merging_output = crew2.kickoff()
        print(merging_output)
        
        # 6. Save the merged result
        Vgen()._save_results([merging_output])
        
        # # 8. Generate testbench
        # print("\n==== GENERATING TESTBENCH ====\n")
        # testbench_crew = Vgen().testbench_crew()
        # testbench_output = testbench_crew.kickoff()
        # print(testbench_output)
        # # Save the testbench output using the new method
        # Vgen()._save_testbench_results([testbench_output])
        # print("\n==== TESTBENCH GENERATION COMPLETE ====\n")

        # 9. Run Icarus Verilog simulation
        print("\n==== RUNNING ICARUS VERILOG SIMULATION ====\n")
        icarus_crew = Vgen().icarus_crew()
        simulation_output = icarus_crew.kickoff()
        print(simulation_output)
        print("\n==== SIMULATION COMPLETE ====\n")
        
        input_md = 'iverilog_report.md'
        output_json = 'iverilog_report.json'

        #10.0
        print("\n==== PROCESSING MARKDOWN TO JSON ====\n")
        success = process_iverilog_report_to_json(input_md, output_json)
        if not success:
            raise Exception("Failed to process markdown output")
        
        # 10.1 Run the testbench fixer crew
        # print("\n==== RUNNING TESTBENCH FIXER CREW ====\n")
        # testbench_fixer_crew = Vgen().testbench_fixer_crew()
        # testbench_fixer_output = testbench_fixer_crew.kickoff()
        # print(testbench_fixer_output)
        
        # Save the fixed testbench using the clean_verilog_file function
        # Vgen()._save_fixed_testbench_results([testbench_fixer_output])
        # print("\n==== FIXED TESTBENCH SAVED ====\n")

        # 11. Run the testbench again
        # print("\n==== RUNNING ICARUS VERILOG SIMULATION ====\n")
        # Rerun_crew = Vgen().Rerun_crew()
        # Rerun_output = Rerun_crew.kickoff()
        # print(Rerun_output)
        # print("\n==== SIMULATION COMPLETE ====\n")

        # #Run the design fixer crew
        # print("\n==== RUNNING DESIGN FIXER CREW ====\n")
        # design_fixer_crew = Vgen().design_fixer_crew()
        # design_fixer_output = design_fixer_crew.kickoff()
        # print(design_fixer_output)
        
        # # Save the fixed testbench using the clean_verilog_file function
        # Vgen()._save_fixed_testbench_results([design_fixer_output])
        # print("\n==== FIXED DESIGN SAVED ====\n")

        print("\n==== CLEANING UP SUBTASK FILES ====\n")
        subtask_files = glob.glob("subtask_*.v")
        for file in subtask_files:
            try:
                os.remove(file)
                print(f"Removed: {file}")
            except Exception as e:
                print(f"Error removing {file}: {e}")
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
