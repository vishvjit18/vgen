from crewai.tools import tool
import subprocess

@tool
def run_icarus_verilog(verilog_file: str, testbench_file: str) -> str:
    """
    Compiles and runs a Verilog testbench using Icarus Verilog (iverilog + vvp).
    
    Inputs:
    - verilog_file: Path to the Verilog design file (.v)
    - testbench_file: Path to the testbench file (.v)
    
    Output:
    - Simulation output, or an error message
    """
    try:
        # Compile Verilog and testbench
        subprocess.run(
            ["iverilog", "-g2012", "-o", "testbench_out", verilog_file, testbench_file],
            check=True,
            capture_output=True,
            text=True
        )
        # Run the compiled simulation
        result = subprocess.run(["vvp", "testbench_out"], check=True, capture_output=True, text=True)
        return result.stdout

    except subprocess.CalledProcessError as e:
        return f"Error during simulation: {e.stderr.strip()}"
