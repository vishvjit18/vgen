import sys
import warnings
import json
from datetime import datetime
import os
from dotenv import load_dotenv  # Add this import
from vgen.utils.markdown_to_json import process_markdown_to_json, process_iverilog_report_to_json
from vgen.crew import Vgen
from vgen.config import Target_Problem, get_target_problem
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
        'Target_Problem': get_target_problem()
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
        print("\n==== PROCESSING MARKDOWN TO JSON ====\n")
        success = process_markdown_to_json(input_md, output_json)
        if not success:
            raise Exception("Failed to process markdown output")
        
        # 2. Run the subtasks crew to generate individual Verilog modules
        print("\n==== RUNNING SUBTASKS CREW ====\n")
        subtask_crew = Vgen().subtask_crew()
        subtask_outputs = subtask_crew.kickoff()
        print(f"Completed subtasks: {subtask_outputs}")
        
        # 3. Run the merging crew to combine all the modules
        print("\n==== RUNNING MERGING CREW ====\n")
        crew2 = Vgen().merging_crew()
        merging_output = crew2.kickoff()
        print(merging_output)
        Vgen()._save_results([merging_output])
        
        # 4. Generate testbench
        print("\n==== GENERATING TESTBENCH ====\n")
        testbench_crew = Vgen().testbench_crew()
        testbench_output = testbench_crew.kickoff()
        print(testbench_output)
        Vgen()._save_testbench_results(testbench_output)
        print("\n==== TESTBENCH GENERATION COMPLETE ====\n")

        # 5. Run Icarus Verilog simulation
        # Repeat the fixer logic 4 times
        for iteration in range(1, 5):
            print(f"\n==== ITERATION {iteration} ====\n")
            
            # Run Icarus Verilog simulation
            print(f"\n==== RUNNING ICARUS VERILOG SIMULATION - {iteration} ====\n")
            icarus_crew = Vgen().icarus_crew()
            simulation_output = icarus_crew.kickoff()
            print(simulation_output)
            print("\n==== SIMULATION COMPLETE ====\n")
            
            # Process markdown to JSON
            input_md = 'iverilog_report.md'
            output_json = 'iverilog_report.json'
            print("\n==== PROCESSING MARKDOWN TO JSON ====\n")
            success = process_iverilog_report_to_json(input_md, output_json)
            if not success:
                raise Exception("Failed to process markdown output")
            
            # Check suggestions and decide which fixer crews to run
            try:
                with open('iverilog_report.json', 'r') as f:
                    iverilog_report = json.load(f)
                # Try both possible spellings of suggestions field  
                design_suggestions = iverilog_report.get('files', {}).get('design', {}).get('suggesstions', '')
                if not design_suggestions:  # If empty, try alternate spelling
                    design_suggestions = iverilog_report.get('files', {}).get('design', {}).get('suggestions', '')
                
                testbench_suggestions = iverilog_report.get('files', {}).get('testbench', {}).get('suggesstions', '')
                if not testbench_suggestions:  # If empty, try alternate spelling
                    testbench_suggestions = iverilog_report.get('files', {}).get('testbench', {}).get('suggestions', '')
                design_suggestions_empty = design_suggestions == ''
                testbench_suggestions_empty = testbench_suggestions == ''
                
                # Debug prints
                print(f"DEBUG - Iteration {iteration}:")
                print(f"  Design suggestions: '{design_suggestions}'")
                print(f"  Testbench suggestions: '{testbench_suggestions}'")
                print(f"  Design suggestions empty: {design_suggestions_empty}")
                print(f"  Testbench suggestions empty: {testbench_suggestions_empty}")
                
            except Exception as e:
                print(f"Error reading iverilog_report.json: {e}")
                design_suggestions_empty = False
                testbench_suggestions_empty = False
            
            print(f"DEBUG - Entering conditional check for iteration {iteration}")
            
            if design_suggestions_empty and testbench_suggestions_empty:
                # Both design and testbench are clean
                print(f"DEBUG - Both clean path taken for iteration {iteration}")
                design_file = "design.sv"
                try:
                    if os.path.exists(design_file):
                        with open(design_file, 'r') as f:
                            design_content = f.read()
                        print(f"\n=== Final Design Content - Iteration {iteration} - Both Clean ===")
                        print(design_content)
                        break  # Exit the loop if both are clean
                    else:
                        print(f"Error: {design_file} not found")
                except Exception as e:
                    print(f"Error reading results: {e}")
            
            else:
                # Either one or both have suggestions - run appropriate fixer crews
                print(f"DEBUG - Fixer path taken for iteration {iteration}")
                crews_to_run = []
                
                if not design_suggestions_empty:
                    crews_to_run.append("design")
                    print(f"Design has suggestions in iteration {iteration}")
                
                if not testbench_suggestions_empty:
                    crews_to_run.append("testbench")
                    print(f"Testbench has suggestions in iteration {iteration}")
                
                print(f"DEBUG - Crews to run: {crews_to_run}")
                
                # Run design fixer if needed
                if "design" in crews_to_run:
                    print(f"DEBUG - About to run design fixer crew for iteration {iteration}")
                    print(f"\n==== RUNNING DESIGN FIXER CREW - Iteration {iteration} ====\n")
                    design_fixer_crew = Vgen().Design_fixer_crew()
                    design_fixer_output = design_fixer_crew.kickoff()
                    print(design_fixer_output)
                    Vgen()._save_fixed_design_results([design_fixer_output])
                    print("\n==== FIXED DESIGN SAVED ====\n")
                
                # Run testbench fixer if needed
                if "testbench" in crews_to_run:
                    print(f"DEBUG - About to run testbench fixer crew for iteration {iteration}")
                    print(f"\n==== RUNNING TESTBENCH FIXER CREW - Iteration {iteration} ====\n")
                    # Uncomment when testbench fixer crew is available
                    testbench_fixer_crew = Vgen().testbench_fixer_crew()
                    testbench_fixer_output = testbench_fixer_crew.kickoff()
                    print(testbench_fixer_output)
                    Vgen()._save_testbench_results([testbench_fixer_output])
                    print("Testbench fixer crew placeholder - implement when available")
                    print("\n==== FIXED TESTBENCH SAVED ====\n")
                
                # If this is the last iteration and still have suggestions
                if iteration == 4:
                    print("Reached maximum iterations. Some suggestions may still remain.")
                    design_file = "design.sv"
                    try:
                        if os.path.exists(design_file):
                            with open(design_file, 'r') as f:
                                design_content = f.read()
                            print(f"\n=== Final Design Content - Iteration {iteration} ===")
                            print(design_content)
                        else:
                            print(f"Error: {design_file} not found")
                    except Exception as e:
                        print(f"Error reading results: {e}")

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
    try:
        Vgen().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], )

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
    Test the crew execution with 3 repetitions of suggestion-based fixer logic.
    """

    try:
        # 4. Generate testbench
        print("\n==== GENERATING TESTBENCH ====\n")
        testbench_crew = Vgen().testbench_crew()
        testbench_output = testbench_crew.kickoff()
        print(testbench_output)
        Vgen()._save_testbench_results(testbench_output)
        print("\n==== TESTBENCH GENERATION COMPLETE ====\n")
        # 5. Run Icarus Verilog simulation
        print("\n==== RUNNING ICARUS VERILOG SIMULATION - 1 ====\n")
        icarus_crew = Vgen().icarus_crew()
        simulation_output = icarus_crew.kickoff()
        print(simulation_output)
        print("\n==== SIMULATION COMPLETE ====\n")
        input_md = 'iverilog_report.md'
        output_json = 'iverilog_report.json'
        print("\n==== PROCESSING MARKDOWN TO JSON ====\n")
        success = process_iverilog_report_to_json(input_md, output_json)
        if not success:
            raise Exception("Failed to process markdown output")


    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")
