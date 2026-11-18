
import os
import time
from dotenv import load_dotenv
from langsmith import Client, traceable

load_dotenv(override=True)

api_key = os.getenv("LANGSMITH_API_KEY")

if not api_key:
    raise ValueError("LANGSMITH_API_KEY not loaded")

PROJECT = "spec2rtl-development"

client = Client(api_key=api_key)

@traceable(
    name="SPEC2RTL-Understanding-Test",
    project_name=PROJECT,
    client=client
)
def understanding_agent(spec: str):
    return {
        "understanding": "Traffic light controller",
        "input_length": len(spec)
    }

result = understanding_agent(
    "Design a traffic light controller with red, yellow and green signals."
)

print("Function output:", result)

# Allow asynchronous trace submission
time.sleep(3)

# Verify directly through the LangSmith API
runs = list(
    client.list_runs(
        project_name=PROJECT,
        limit=10
    )
)

print("\nRuns found:", len(runs))

for run in runs:
    print(run.name, run.status, run.id)
