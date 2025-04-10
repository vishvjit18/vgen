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