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

Target_Problem = """Please act as a professional Verilog designer.

Implement a module of a 4-bit comparator with multiple bit-level comparators in combinational logic.

Module name:  
    comparator_4bit               
Input ports:
    A [3:0]: First 4-bit input operand (binary number to compare).
    B [3:0]: Second 4-bit input operand (binary number to compare).
Output ports:
    A_greater: 1-bit output indicating if A is greater than B.
    A_equal: 1-bit output indicating if A is equal to B.
    A_less: 1-bit output indicating if A is less than B.

Implementation:
Comparison Logic: The module compares the two 4-bit binary numbers A and B using combinational logic.
- A subtraction operation is performed: A - B. The result of this subtraction helps determine whether A is greater than, equal to, or less than B.
- Carry Generation: If a borrow occurs during the subtraction, A is less than B (A_less).
- If no borrow occurs and the result of subtraction is non-zero, A is greater than B (A_greater).
- If A and B are equal, the result of subtraction is zero (A_equal).

Output Encoding: The outputs (A_greater, A_equal, A_less) are mutually exclusive, ensuring only one of the three outputs is high (1) at any given time.

Give me the complete code.
 """