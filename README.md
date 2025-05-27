# VGen CrewAI API

This project provides a FastAPI application for streaming responses from CrewAI runs.

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Make sure you have Icarus Verilog installed:

```bash
sudo apt-get install iverilog
```

3. Set up your environment variables in a `.env` file:

```
GEMINI_API_KEY=your_gemini_api_key_here
```

## Running the API

Run the FastAPI application with:

```bash
python -m vgen.run_api
```

This will start the server on http://localhost:8000.

## API Endpoints

- `GET /`: HTML interface for interacting with the API
- `POST /run`: Create a new run
  - Request body:
    ```json
    {
      "problem": "Your Verilog problem statement here",
      "run_type": "full" // Options: full, planning, subtasks, merging, iverilog
    }
    ```
  - Response:
    ```json
    {
      "run_id": "run_YYYYMMDD_HHMMSS",
      "status": "starting",
      "message": "Run run_YYYYMMDD_HHMMSS started"
    }
    ```

- `GET /run/{run_id}`: Get the status of a specific run
- `GET /run/{run_id}/stream`: Stream updates from a specific run (SSE)
- `GET /runs`: List all runs

## Web Interface

The API includes a web interface for creating and monitoring runs. Access it by opening http://localhost:8000 in your browser.

## Example Usage

### Using the API directly

```python
import requests
import json

# Start a new run
response = requests.post(
    "http://localhost:8000/run",
    json={
        "problem": "Please act as a professional Verilog designer...",
        "run_type": "full"
    }
)

run_id = response.json()["run_id"]
print(f"Run started with ID: {run_id}")

# Get status updates
status_response = requests.get(f"http://localhost:8000/run/{run_id}")
print(json.dumps(status_response.json(), indent=2))
```

### Streaming updates

To stream updates, you can use Server-Sent Events (SSE) in JavaScript:

```javascript
const eventSource = new EventSource(`http://localhost:8000/run/${runId}/stream`);

eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log(data);
};
```

## Notes

- The CrewAI runs can take several minutes to complete
- The API supports different run types for different parts of the process
- All output is streamed in real-time
