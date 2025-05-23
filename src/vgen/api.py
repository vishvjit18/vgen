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

from vgen.crew import Vgen
from vgen.config import Target_Problem
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
            active_runs[self.run_id]["waiting_for_input"] = True
            active_runs[self.run_id]["last_update"] = datetime.now().isoformat()
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
                    subtask_crew = vgen_instance.subtask_crew()
                    subtask_outputs = subtask_crew.kickoff()
                    update_status("subtasks", "Subtasks complete", subtask_outputs)
                    
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
                
                if run_type in ["full", "iverilog"]:
                    # 5. Run Icarus Verilog simulation
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
                        update_status("error", "Failed to process simulation report")
                        active_runs[run_id]["status"] = "failed"
                        return
                    
                    # Check if design needs fixing
                    try:
                        with open('iverilog_report.json', 'r') as f:
                            iverilog_report = json.load(f)
                        design_suggestions_empty = iverilog_report.get('files', {}).get('design', {}).get('suggestions', '') == ''
                        
                        if not design_suggestions_empty:
                            # Run the design fixer crew
                            update_status("fixing", "Running design fixer crew")
                            design_fixer_crew = vgen_instance.Design_fixer_crew()
                            design_fixer_output = design_fixer_crew.kickoff()
                            update_status("fixing", "Design fixing complete", design_fixer_output)
                            
                            # Save the fixed design
                            vgen_instance._save_fixed_design_results([design_fixer_output])
                            update_status("fixing", "Fixed design saved")
                            
                            # Run simulation again
                            update_status("simulation", "Running second simulation")
                            simulation_output = icarus_crew.kickoff()
                            update_status("simulation", "Second simulation complete", simulation_output)
                    except Exception as e:
                        update_status("error", f"Error checking design suggestions: {str(e)}")
                        active_runs[run_id]["status"] = "failed"
                        return
                    
                    if run_type == "iverilog":
                        active_runs[run_id]["status"] = "completed"
                        return
                
                # Mark as complete
                active_runs[run_id]["status"] = "completed"
                update_status("complete", "Run completed successfully")
                
                # Read and return the final design file
                try:
                    design_file = "design.sv"
                    if os.path.exists(design_file):
                        with open(design_file, 'r') as f:
                            design_content = f.read()
                        update_status("result", "Final design content", design_content)
                except Exception as e:
                    update_status("error", f"Error reading final design: {str(e)}")
                
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