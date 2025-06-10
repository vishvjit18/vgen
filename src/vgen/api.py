from fastapi import FastAPI, HTTPException, BackgroundTasks, Body
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import os
import sys
import threading
import queue
from pathlib import Path
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime
import json
import logging
from contextlib import asynccontextmanager

from crewai import Agent, Crew, Process, Task
from vgen.crew import Vgen
from vgen.config import Target_Problem, set_target_problem, get_target_problem
from vgen.utils.markdown_to_json import process_markdown_to_json, process_iverilog_report_to_json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store active runs and their results
active_runs = {}
run_results = {}

# Dict to store input queues for processes waiting for human input
human_input_queues = {}

class CrewRunRequest(BaseModel):
    """Request model for creating a new crew run"""
    problem: str = Target_Problem
    run_type: str = "full"  # Options: full, planning, subtasks, merging, iverilog


class HumanInputRequest(BaseModel):
    """Request model for providing human input to a running process"""
    input: str = ""  # Empty string is equivalent to pressing Enter (accept)


# Custom stdin handler to intercept input requests
class InputHandler:
    def __init__(self, run_id):
        self.run_id = run_id
        self.queue = queue.Queue()
        human_input_queues[run_id] = self.queue
        self.original_stdin = sys.stdin
        
    def readline(self):
        # Update status to waiting for input
        if self.run_id in active_runs:
            # Check if pre_feedback_output.txt exists and read its content
            pre_feedback_content = None
            if os.path.exists("pre_feedback_output.txt"):
                try:
                    with open("pre_feedback_output.txt", "r") as f:
                        pre_feedback_content = f.read()
                except Exception as e:
                    logger.error(f"Error reading pre_feedback_output.txt: {str(e)}")
            
            active_runs[self.run_id]["waiting_for_input"] = True
            active_runs[self.run_id]["last_update"] = datetime.now().isoformat()
            
            # Add pre-feedback content to the outputs if available
            if pre_feedback_content:
                active_runs[self.run_id]["outputs"].append({
                    "stage": "pre_feedback",
                    "message": "AI's current output for review before providing feedback:",
                    "content": pre_feedback_content,
                    "timestamp": datetime.now().isoformat(),
                })
            
            active_runs[self.run_id]["outputs"].append({
                "stage": "human_input",
                "message": "Waiting for human input...",
                "timestamp": datetime.now().isoformat(),
            })
        
        # Wait for input from the queue
        try:
            user_input = self.queue.get()
            
            # Update status that input was received
            if self.run_id in active_runs:
                active_runs[self.run_id]["waiting_for_input"] = False
                active_runs[self.run_id]["last_update"] = datetime.now().isoformat()
                active_runs[self.run_id]["outputs"].append({
                    "stage": "human_input",
                    "message": f"Received human input: {user_input}",
                    "timestamp": datetime.now().isoformat(),
                })
            
            return user_input + "\n"
        except Exception as e:
            logger.error(f"Error getting human input: {str(e)}")
            return "\n"  # Return empty input as fallback

#Application Lifespan & Static Files
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Ensure directories exist
    os.makedirs(".crew", exist_ok=True)
    os.makedirs(".crew/logs", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    yield
    # Shutdown


app = FastAPI(lifespan=lifespan)

# Get the directory of the current file
current_dir = Path(__file__).parent

# Mount the static directory
app.mount("/static", StaticFiles(directory=str(current_dir / "static")), name="static")


@app.get("/")
async def root():
    """Serve the HTML interface"""
    return FileResponse(current_dir / "static" / "index.html")


@app.post("/run")
async def create_run(request: CrewRunRequest, background_tasks: BackgroundTasks):
    """Create a new crew run with the specified problem"""
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Update target problem if different from current one
    if request.problem != get_target_problem():
        set_target_problem(request.problem)
    
    # Store run info
    active_runs[run_id] = {
        "status": "starting",
        "problem": request.problem,
        "type": request.run_type,
        "start_time": datetime.now().isoformat(),
        "last_update": datetime.now().isoformat(),
        "outputs": [],
        "waiting_for_input": False
    }
    
    # Start the background task
    background_tasks.add_task(run_crew, run_id, request.problem, request.run_type)
    
    return {
        "run_id": run_id,
        "status": "starting",
        "message": f"Run {run_id} started"
    }


@app.post("/run/{run_id}/input")
async def provide_human_input(run_id: str, input_request: HumanInputRequest = Body(...)):
    """Provide human input to a running process"""
    if run_id not in active_runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    if run_id not in human_input_queues:
        raise HTTPException(status_code=400, detail=f"Run {run_id} is not waiting for input")
    
    if not active_runs[run_id]["waiting_for_input"]:
        raise HTTPException(status_code=400, detail=f"Run {run_id} is not currently waiting for input")
    
    # Add the input to the queue for the process to consume
    try:
        human_input_queues[run_id].put(input_request.input)
        return {"status": "success", "message": "Input provided successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to provide input: {str(e)}")


@app.get("/run/{run_id}")
async def get_run_status(run_id: str):
    """Get the status of a specific run"""
    if run_id not in active_runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    return active_runs[run_id]


@app.get("/run/{run_id}/stream")
async def stream_run_updates(run_id: str):
    """Stream updates from a specific run"""
    if run_id not in active_runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    async def event_generator():
        last_idx = 0
        while True:
            if run_id in active_runs:
                status = active_runs[run_id]
                
                # Send any new outputs
                if len(status["outputs"]) > last_idx:
                    for output in status["outputs"][last_idx:]:
                        yield f"data: {json.dumps(output)}\n\n"
                    last_idx = len(status["outputs"])
                
                # Special case for waiting for input
                if status.get("waiting_for_input", False):
                    yield f"data: {json.dumps({'status': 'waiting_for_input', 'message': 'Waiting for human input'})}\n\n"
                
                # Check if the run is complete
                if status["status"] == "completed" or status["status"] == "failed":
                    yield f"data: {json.dumps({'status': status['status'], 'message': 'Run complete'})}\n\n"
                    break
                    
                await asyncio.sleep(1)
            else:
                # Run was removed or doesn't exist
                yield f"data: {json.dumps({'status': 'error', 'message': 'Run not found'})}\n\n"
                break
                
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@app.get("/runs")
async def list_runs():
    """List all runs"""
    return {
        "runs": list(active_runs.keys()),
        "details": active_runs
    }


async def run_crew(run_id: str, problem_statement: str, run_type: str):
    """Run the CrewAI process in the background"""
    try:
        vgen_instance = Vgen()
        inputs = {
            'Target_Problem': problem_statement
        }
        
        active_runs[run_id]["status"] = "running"
        
        # Function to update status
        def update_status(stage: str, message: str, output: Any = None):
            timestamp = datetime.now().isoformat()
            active_runs[run_id]["status"] = "running"
            active_runs[run_id]["current_stage"] = stage
            active_runs[run_id]["last_update"] = timestamp
            
            update = {
                "stage": stage,
                "message": message,
                "timestamp": timestamp,
            }
            
            if output:
                if hasattr(output, 'raw_output'):
                    update["output"] = str(output.raw_output)
                else:
                    update["output"] = str(output)
                    
            active_runs[run_id]["outputs"].append(update)
            logger.info(f"Run {run_id} - {stage}: {message}")
        
        # Setup input handler to intercept stdin
        input_handler = InputHandler(run_id)
        
        # Use a separate thread to run the CrewAI process with redirected stdin
        def run_process_with_input_handler():
            # Save original stdin
            original_stdin = sys.stdin
            
            try:
                # Replace stdin with our input handler
                sys.stdin = input_handler
                
                # Now run the actual process
                if run_type in ["full", "planning"]:
                    # 1. Run the high-level planning crew
                    update_status("planning", "Starting planning crew")
                    crew1 = vgen_instance.crew1()
                    crew1_output = crew1.kickoff(inputs=inputs)
                    update_status("planning", "Planning complete", crew1_output)
                    
                    # Process the planning output
                    input_md = 'high_level_planning_task.md'
                    output_json = 'verilog_task.json'
                    update_status("processing", "Processing markdown to JSON")
                    success = process_markdown_to_json(input_md, output_json)
                    
                    if not success:
                        update_status("error", "Failed to process markdown output")
                        active_runs[run_id]["status"] = "failed"
                        return
                    
                    if run_type == "planning":
                        active_runs[run_id]["status"] = "completed"
                        return
                
                if run_type in ["full", "subtasks"]:
                    # 2. Run the subtasks crew
                    update_status("subtasks", "Running subtasks crew")
                    
                    # Get the subtasks data
                    subtasks = vgen_instance._load_subtasks()
                    update_status("subtasks", f"Found {len(subtasks)} subtasks to process")
                    
                    # Create individual tasks for manual tracking
                    verilog_agent = vgen_instance.verilog_agent()
                    task_template = vgen_instance._load_task_template()
                    
                    # Run subtasks individually
                    all_outputs = []
                    
                    for i, sub in enumerate(subtasks):
                        subtask_name = f"verilog_subtask_{i+1}"
                        update_status("subtask", f"Processing subtask {i+1}/{len(subtasks)}: {subtask_name}")
                        
                        # Create a small crew for just this one task
                        single_task = Task(
                            name=subtask_name,
                            description=task_template['description'].format(content=sub['content'], source=sub['source']),
                            expected_output=task_template['expected_output'],
                            agent=verilog_agent,
                            human_input=False,
                            output_file=f"subtask_{i+1}.v"
                        )
                        
                        # Create a micro-crew for just this task
                        micro_crew = Crew(
                            agents=[verilog_agent],
                            tasks=[single_task],
                            process=Process.sequential,
                            verbose=True
                        )
                        
                        # Execute the task via the crew
                        task_output = micro_crew.kickoff()
                        all_outputs.append(task_output)
                        
                        # Read the output file for this subtask
                        subtask_file = f"subtask_{i+1}.v"
                        try:
                            if os.path.exists(subtask_file):
                                with open(subtask_file, "r") as f:
                                    subtask_content = f.read()
                                update_status("subtask_result", f"Completed subtask {i+1}/{len(subtasks)}", subtask_content)
                            else:
                                update_status("subtask_error", f"Output file for subtask {i+1} not found")
                        except Exception as e:
                            update_status("subtask_error", f"Error reading subtask {i+1} file: {str(e)}")
                    
                    # Aggregate all outputs for final reporting
                    update_status("subtasks", "All subtasks complete")
                    
                    if run_type == "subtasks":
                        active_runs[run_id]["status"] = "completed"
                        return
                
                if run_type in ["full", "merging"]:
                    # 3. Run the merging crew
                    update_status("merging", "Running merging crew")
                    crew2 = vgen_instance.merging_crew()
                    merging_output = crew2.kickoff()
                    update_status("merging", "Merging complete", merging_output)
                    
                    # Save the results
                    vgen_instance._save_results([merging_output])
                    update_status("merging", "Results saved")
                    
                    if run_type == "merging":
                        active_runs[run_id]["status"] = "completed"
                        return
                    
                if run_type in ["full", "testbench"]:
                    # 4. Run the testbench crew
                    update_status("testbench", "Running testbench crew")
                    testbench_crew = vgen_instance.testbench_crew()
                    testbench_output = testbench_crew.kickoff()
                    update_status("testbench", "Testbench complete", testbench_output)
                    
                    # Save the results
                    vgen_instance._save_testbench_results([testbench_output])
                    update_status("testbench", "Results saved")
                    
                    if run_type == "testbench":
                        active_runs[run_id]["status"] = "completed"
                        return
                
                if run_type in ["full", "iverilog"]:
                    # 5. Run Icarus Verilog simulation - first run
                    update_status("simulation", "Running Icarus Verilog simulation")
                    icarus_crew = vgen_instance.icarus_crew()
                    simulation_output = icarus_crew.kickoff()
                    update_status("simulation", "Simulation complete", simulation_output)
                    
                    # Process the simulation output
                    input_md = 'iverilog_report.md'
                    output_json = 'iverilog_report.json'
                    update_status("processing", "Processing simulation report")
                    success = process_iverilog_report_to_json(input_md, output_json)
                    
                    if not success:
                        update_status("error", "Failed to process markdown output")
                        active_runs[run_id]["status"] = "failed"
                        return
                    
                    # FIRST CONDITIONAL CHECK
                    try:
                        with open('iverilog_report.json', 'r') as f:
                            iverilog_report = json.load(f)
                        design_suggestions_empty = iverilog_report.get('files', {}).get('design', {}).get('suggestions', '') == ''
                    except Exception as e:
                        update_status("error", f"Error reading iverilog_report.json: {e}")
                        design_suggestions_empty = False  # Default to original behavior if file can't be read
                        
                    if design_suggestions_empty:
                        design_file = "design.sv"
                        try:
                            # Read and display design file content
                            if os.path.exists(design_file):
                                with open(design_file, 'r') as f:
                                    design_content = f.read()
                                update_status("result", "Final design content (Original)", design_content)
                            else:
                                update_status("error", f"Error: {design_file} not found")
                        except Exception as e:
                            update_status("error", f"Error reading results: {e}")
                    else:
                        # Design has suggestions - FIRST DESIGN FIXER
                        update_status("fixing", "Design has suggestions. Running DESIGN FIXER CREW - 1")
                        design_fixer_crew = vgen_instance.Design_fixer_crew()
                        design_fixer_output = design_fixer_crew.kickoff()
                        update_status("fixing", "Design fixing complete", design_fixer_output)
                        
                        # Save the fixed design
                        vgen_instance._save_fixed_design_results([design_fixer_output])
                        update_status("fixing", "Fixed design saved")
                        
                        # Run simulation again - SECOND SIMULATION
                        update_status("simulation", "Running Icarus Verilog simulation - 2")
                        simulation_output = icarus_crew.kickoff()
                        update_status("simulation", "Second simulation complete", simulation_output)
                        
                        # Process the second simulation output
                        input_md = 'iverilog_report.md'
                        output_json = 'iverilog_report.json'
                        update_status("processing", "Processing second simulation report")
                        success = process_iverilog_report_to_json(input_md, output_json)
                        if not success:
                            update_status("error", "Failed to process simulation report")
                            active_runs[run_id]["status"] = "failed"
                            return
                        
                        # SECOND CONDITIONAL CHECK
                        try:
                            with open('iverilog_report.json', 'r') as f:
                                iverilog_report = json.load(f)
                            design_suggestions_empty = iverilog_report.get('files', {}).get('design', {}).get('suggestions', '') == ''
                        except Exception as e:
                            update_status("error", f"Error reading iverilog_report.json: {e}")
                            design_suggestions_empty = False
                            
                        if design_suggestions_empty:
                            design_file = "design.sv"
                            try:
                                # Read and display design file content
                                if os.path.exists(design_file):
                                    with open(design_file, 'r') as f:
                                        design_content = f.read()
                                    update_status("result", "Final design content (FIXER CREW - 1)", design_content)
                                else:
                                    update_status("error", f"Error: {design_file} not found")
                            except Exception as e:
                                update_status("error", f"Error reading results: {e}")
                        else:
                            # Design still has suggestions - SECOND DESIGN FIXER
                            update_status("fixing", "Design has suggestions. Running DESIGN FIXER CREW - 2")
                            design_fixer_crew = vgen_instance.Design_fixer_crew()
                            design_fixer_output = design_fixer_crew.kickoff()
                            update_status("fixing", "Second design fixing complete", design_fixer_output)
                            
                            # Save the fixed design
                            vgen_instance._save_fixed_design_results([design_fixer_output])
                            update_status("fixing", "Second fixed design saved")
                            
                            # Run simulation again - THIRD SIMULATION
                            update_status("simulation", "Running Icarus Verilog simulation - 3")
                            simulation_output = icarus_crew.kickoff()
                            update_status("simulation", "Third simulation complete", simulation_output)
                            
                            # Process the third simulation output
                            input_md = 'iverilog_report.md'
                            output_json = 'iverilog_report.json'
                            update_status("processing", "Processing third simulation report")
                            success = process_iverilog_report_to_json(input_md, output_json)
                            if not success:
                                update_status("error", "Failed to process simulation report")
                                active_runs[run_id]["status"] = "failed"
                                return
                            
                            # THIRD CONDITIONAL CHECK
                            try:
                                with open('iverilog_report.json', 'r') as f:
                                    iverilog_report = json.load(f)
                                design_suggestions_empty = iverilog_report.get('files', {}).get('design', {}).get('suggestions', '') == ''
                            except Exception as e:
                                update_status("error", f"Error reading iverilog_report.json: {e}")
                                design_suggestions_empty = False
                                
                            if design_suggestions_empty:
                                design_file = "design.sv"
                                try:
                                    # Read and display design file content
                                    if os.path.exists(design_file):
                                        with open(design_file, 'r') as f:
                                            design_content = f.read()
                                        update_status("result", "Final design content (FIXER CREW - 2)", design_content)
                                    else:
                                        update_status("error", f"Error: {design_file} not found")
                                except Exception as e:
                                    update_status("error", f"Error reading results: {e}")
                            else:
                                # Design still has suggestions - THIRD DESIGN FIXER
                                update_status("fixing", "Design has suggestions. Running DESIGN FIXER CREW - 3")
                                design_fixer_crew = vgen_instance.Design_fixer_crew()
                                design_fixer_output = design_fixer_crew.kickoff()
                                update_status("fixing", "Third design fixing complete", design_fixer_output)
                                
                                # Save the fixed design
                                vgen_instance._save_fixed_design_results([design_fixer_output])
                                update_status("fixing", "Third fixed design saved")
                                
                                # Run simulation again - FOURTH SIMULATION
                                update_status("simulation", "Running Icarus Verilog simulation - 4")
                                simulation_output = icarus_crew.kickoff()
                                update_status("simulation", "Fourth simulation complete", simulation_output)
                                
                                # Process the fourth simulation output
                                input_md = 'iverilog_report.md'
                                output_json = 'iverilog_report.json'
                                update_status("processing", "Processing fourth simulation report")
                                success = process_iverilog_report_to_json(input_md, output_json)
                                if not success:
                                    update_status("error", "Failed to process simulation report")
                                    active_runs[run_id]["status"] = "failed"
                                    return
                                
                                # FOURTH CONDITIONAL CHECK
                                try:
                                    with open('iverilog_report.json', 'r') as f:
                                        iverilog_report = json.load(f)
                                    design_suggestions_empty = iverilog_report.get('files', {}).get('design', {}).get('suggestions', '') == ''
                                except Exception as e:
                                    update_status("error", f"Error reading iverilog_report.json: {e}")
                                    design_suggestions_empty = False
                                    
                                if design_suggestions_empty:
                                    design_file = "design.sv"
                                    try:
                                        # Read and display design file content
                                        if os.path.exists(design_file):
                                            with open(design_file, 'r') as f:
                                                design_content = f.read()
                                            update_status("result", "Final design content (FIXER CREW - 3)", design_content)
                                        else:
                                            update_status("error", f"Error: {design_file} not found")
                                    except Exception as e:
                                        update_status("error", f"Error reading results: {e}")
                                else:
                                    # Give up message from main.py
                                    update_status("error", "I can't crack it. Guess it's your turn to shine, Sherlock! Best of luck! 🥹🥹")
                    
                    # Clean up subtask files
                    import glob
                    subtask_files = glob.glob("subtask_*.v")
                    for file in subtask_files:
                        try:
                            os.remove(file)
                        except Exception as e:
                            logger.error(f"Error removing {file}: {e}")
                    
                    if run_type == "iverilog":
                        active_runs[run_id]["status"] = "completed"
                        return
                
                # Mark as complete
                active_runs[run_id]["status"] = "completed"
                update_status("complete", "Run completed successfully")
                
            except Exception as e:
                logger.error(f"Error in run {run_id}: {str(e)}", exc_info=True)
                if run_id in active_runs:
                    active_runs[run_id]["status"] = "failed"
                    active_runs[run_id]["error"] = str(e)
                    active_runs[run_id]["outputs"].append({
                        "stage": "error",
                        "message": f"Run failed: {str(e)}",
                        "timestamp": datetime.now().isoformat(),
                    })
            finally:
                # Restore original stdin
                sys.stdin = original_stdin
                
                # Clean up
                if run_id in human_input_queues:
                    del human_input_queues[run_id]
        
        # Start the process in a thread
        process_thread = threading.Thread(target=run_process_with_input_handler)
        process_thread.daemon = True
        process_thread.start()
            
    except Exception as e:
        logger.error(f"Error starting run {run_id}: {str(e)}", exc_info=True)
        if run_id in active_runs:
            active_runs[run_id]["status"] = "failed"
            active_runs[run_id]["error"] = str(e)
            active_runs[run_id]["outputs"].append({
                "stage": "error",
                "message": f"Run failed: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            }) 