from crewai.tools import tool
import subprocess
import json
from datetime import datetime
import pytz  # You'll need to install this package if not already installed
import re
import os

@tool
def run_icarus_verilog(verilog_file: str, testbench_file: str) -> str:
    """
    Compiles and runs a Verilog testbench using Icarus Verilog (iverilog + vvp).
    Also provides the contents of the source files for reference.
    
    Inputs:
    - verilog_file: Path to the Verilog design file (.v)
    - testbench_file: Path to the testbench file (.v)
    
    Output:
    - Structured JSON with file contents, compilation status, and simulation results
    """
    # Function to get current time in Indian Standard Time
    def get_india_time():
        india_tz = pytz.timezone('Asia/Kolkata')
        return datetime.now(india_tz).isoformat()
    
    file_contents = {}
    
    # Try to read design file
    try:
        with open(verilog_file, 'r') as f:
            file_contents["design"] = {
                "file": verilog_file,
                "content": f.read(),
                "suggesstions": ""  # Initialize with empty suggestions, note double 's' to match tasks.yaml
            }
    except Exception as e:
        result = {
            "status": "error",
            "stage": "file_reading",
            "file": verilog_file,
            "message": f"Error reading design file: {str(e)}",
            "timestamp": get_india_time()
        }
        
        output_json = json.dumps(result, indent=2)
        output_filename = f"logs/iverilog_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs("logs", exist_ok=True)
        with open(output_filename, 'w') as f:
            f.write(output_json)
            
        return output_json
        
    # Try to read testbench file
    try:
        with open(testbench_file, 'r') as f:
            file_contents["testbench"] = {
                "file": testbench_file,
                "content": f.read(),
                "suggesstions": ""  # Initialize with empty suggestions, note double 's' to match tasks.yaml
            }
    except Exception as e:
        result = {
            "status": "error",
            "stage": "file_reading",
            "file": testbench_file,
            "message": f"Error reading testbench file: {str(e)}",
            "timestamp": get_india_time()
        }
        
        output_json = json.dumps(result, indent=2)
        output_filename = f"logs/iverilog_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs("logs", exist_ok=True)
        with open(output_filename, 'w') as f:
            f.write(output_json)
            
        return output_json
    
    # Now run the simulation
    try:
        # Compile Verilog and testbench
        compile_result = subprocess.run(
            ["iverilog", "-g2012", "-o", "testbench_out", verilog_file, testbench_file],
            capture_output=True,
            text=True
        )
        
        # Check if compilation succeeded
        if compile_result.returncode != 0:
            # Determine which file has the error by analyzing the error message
            error_log = compile_result.stderr.strip()
            
            # Extract filenames without path for matching
            design_file_name = verilog_file.split('/')[-1]
            testbench_file_name = testbench_file.split('/')[-1]
            
            # Check which file is mentioned in the error log
            problematic_file = design_file_name  # Default
            if testbench_file_name in error_log:
                problematic_file = testbench_file_name
            
            result = {
                "status": "error",
                "stage": "compilation",
                "file": problematic_file,
                "message": f"Compilation failed",
                "log": error_log,
                "files": file_contents,
                "timestamp": get_india_time()
            }
            
            output_json = json.dumps(result, indent=2)
            output_filename = f"logs/iverilog_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            os.makedirs("logs", exist_ok=True)
            with open(output_filename, 'w') as f:
                f.write(output_json)
                
            return output_json
            
        # Run the compiled simulation
        sim_result = subprocess.run(["vvp", "testbench_out"], capture_output=True, text=True)
        
        result = {
            "timestamp": get_india_time(),
            "files": file_contents
        }
        
        if sim_result.returncode == 0:
            result["status"] = "success"
            result["stage"] = "simulation"
            result["output"] = sim_result.stdout
            if sim_result.stderr:
                result["warnings"] = sim_result.stderr
        else:
            # For simulation errors, try to determine which file is problematic
            error_log = sim_result.stderr.strip()
            design_file_name = verilog_file.split('/')[-1]
            testbench_file_name = testbench_file.split('/')[-1]
            
            problematic_file = design_file_name  # Default
            if testbench_file_name in error_log:
                problematic_file = testbench_file_name
                
            result["status"] = "error"
            result["stage"] = "simulation"
            result["file"] = problematic_file
            result["message"] = "Simulation failed"
            result["log"] = error_log
            
        output_json = json.dumps(result, indent=2)
        output_filename = f"logs/iverilog_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs("logs", exist_ok=True)
        with open(output_filename, 'w') as f:
            f.write(output_json)
            
        return output_json

    except subprocess.SubprocessError as e:
        # Handle subprocess exceptions (command not found, etc.)
        result = {
            "status": "error",
            "stage": "process",
            "message": f"Subprocess error: {str(e)}",
            "timestamp": get_india_time()
        }
        
        output_json = json.dumps(result, indent=2)
        output_filename = f"logs/iverilog_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs("logs", exist_ok=True)
        with open(output_filename, 'w') as f:
            f.write(output_json)
            
        return output_json
        
    except Exception as e:
        # Handle any other unexpected exceptions
        result = {
            "status": "error",
            "stage": "unknown",
            "message": f"Unexpected error: {str(e)}",
            "timestamp": get_india_time()
        }
        
        output_json = json.dumps(result, indent=2)
        output_filename = f"logs/iverilog_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs("logs", exist_ok=True)
        with open(output_filename, 'w') as f:
            f.write(output_json)
            
        return output_json

# Internal tracker to keep per-agent usage state
_agent_usage_tracker = {}

@tool
def save_output_tool(response: str, agent_name: str = "default-agent") -> str:
    """
    Saves the raw output to a file during task execution.
    This tool can only be used once per agent.

    Args:
        response: The response or partial result to save
        agent_name: The name or ID of the agent (must be passed explicitly)

    Returns:
        The same response, or a warning if already used by the agent.
    """
    if _agent_usage_tracker.get(agent_name, False):
        return f"⚠️ This tool can only be used once per agent. Agent '{agent_name}' has already used it."

    # Mark as used
    _agent_usage_tracker[agent_name] = True

    # Save to file
    with open("pre_feedback_output.txt", "w", encoding="utf-8") as f:
        f.write(response)

    return response
