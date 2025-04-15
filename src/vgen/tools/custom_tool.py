from crewai.tools import tool
import subprocess

@tool
def run_icarus_verilog(verilog_file: str, testbench_file: str) -> str:
    """
    Compiles and runs a Verilog testbench using Icarus Verilog (iverilog + vvp).
    Also provides the contents of the source files for reference.
    
    Inputs:
    - verilog_file: Path to the Verilog design file (.v)
    - testbench_file: Path to the testbench file (.v)
    
    Output:
    - File contents and simulation output, or an error message
    """
    result_output = ""
    
    # Add the file contents to the output
    try:
        with open(verilog_file, 'r') as f:
            design_content = f.read()
            result_output += f"### Design File ({verilog_file}) ###\n{design_content}\n\n"
    except Exception as e:
        result_output += f"Error reading design file {verilog_file}: {str(e)}\n\n"
        
    try:
        with open(testbench_file, 'r') as f:
            testbench_content = f.read()
            result_output += f"### Testbench File ({testbench_file}) ###\n{testbench_content}\n\n"
    except Exception as e:
        result_output += f"Error reading testbench file {testbench_file}: {str(e)}\n\n"
    
    # Now run the simulation
    result_output += "### Simulation Results ###\n"
    try:
        # Compile Verilog and testbench
        compile_result = subprocess.run(
            ["iverilog", "-g2012", "-o", "testbench_out", verilog_file, testbench_file],
            capture_output=True,
            text=True
        )
        
        # Check if compilation succeeded
        if compile_result.returncode != 0:
            return result_output + f"Compilation Error:\n{compile_result.stderr.strip()}"
            
        # Run the compiled simulation
        sim_result = subprocess.run(["vvp", "testbench_out"], capture_output=True, text=True)
        
        if sim_result.returncode == 0:
            result_output += sim_result.stdout
            if sim_result.stderr:
                result_output += f"\nWarnings:\n{sim_result.stderr}"
        else:
            result_output += f"Simulation Error:\n{sim_result.stderr.strip()}"
            
        return result_output

    except subprocess.CalledProcessError as e:
        return result_output + f"Error during simulation: {e.stderr.strip()}"
    except Exception as e:
        return result_output + f"Unexpected error: {str(e)}"
