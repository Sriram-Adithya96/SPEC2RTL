import os
from dotenv import load_dotenv
from langsmith import traceable

load_dotenv(override=True)

@traceable(name="SPEC2RTL-Understanding-Test")
def understanding_agent(spec: str):
    print("Executing Understanding Agent...")

    return {
        "understanding": "Traffic light controller",
        "status": "success"
    }

result = understanding_agent(
    "Design a traffic light controller."
)

print(result)