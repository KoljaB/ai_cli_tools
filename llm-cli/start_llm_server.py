import os
import sys
import subprocess

def main():
    # Get the current script's directory (should be llm-cli)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Move one directory up to access the venv
    root_dir = os.path.dirname(script_dir)
    os.chdir(root_dir)
    
    # Path to the virtual environment
    venv_path = os.path.join(root_dir, 'venv')
    
    # Path to the Python interpreter in the virtual environment
    if sys.platform == "win32":
        python_path = os.path.join(venv_path, 'Scripts', 'python.exe')
    else:
        python_path = os.path.join(venv_path, 'bin', 'python')
    
    # Change back to the llm-cli directory
    os.chdir(script_dir)
    
    # Prepare the command to run llm_server.py with all provided arguments
    command = [python_path, 'llm_server.py'] + sys.argv[1:]

    # Start the LLM server
    print("Starting LLM server...")
    print(f"Command: {command}")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error starting LLM server: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: Could not find Python interpreter at {python_path}")
        print("Make sure the virtual environment is set up correctly.")
        sys.exit(1)

if __name__ == "__main__":
    main()
