
from src.llm.llm import get_llm

llm = get_llm()

print("LLM initialized successfully!")

response = llm.invoke(
    "Return a valid JSON object with one key named message "
    "and value Hello SPEC2RTL."
)

print("Model response:")
print(response.content)
