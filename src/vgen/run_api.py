import os
import sys
from dotenv import load_dotenv
import uvicorn

def run_api():
    """Run the FastAPI application"""
    # Load environment variables
    load_dotenv()
    
    # Set environment variables needed for CrewAI
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if gemini_api_key:
        os.environ["GEMINI_API_KEY"] = gemini_api_key
    
    # Run the API server with uvicorn
    uvicorn.run(
        "vgen.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["src/vgen"]
    )

if __name__ == "__main__":
    run_api() 