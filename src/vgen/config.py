def clean_verilog_file(file_path, cleaned_file_path):
    """Remove unnecessary prefixes or non-Verilog text from the file."""
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()

        # Filter out lines that contain Markdown code block indicators or other non-Verilog text
        cleaned_lines = [line for line in lines if not line.strip().startswith('```')]

        # Write the cleaned content to a new file
        with open(cleaned_file_path, 'w') as f:
            f.writelines(cleaned_lines)

        print(f"Cleaned {file_path} successfully. Cleaned file saved as {cleaned_file_path}.")
    except Exception as e:
        print(f"Error cleaning {file_path}: {e}")
        exit(1)

Target_Problem = """Please act as a professional verilog designer.

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
 """