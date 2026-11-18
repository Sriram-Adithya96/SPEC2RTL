# Spec2RTL

Spec2RTL is a Python-based multi-agent workflow for turning a hardware specification document into a structured understanding, a component decomposition, canonical pseudocode, generated implementation code, and a static verification summary. The current implementation is centered on a LangGraph pipeline defined in `src/orchestrator.py` and uses LLM-backed agent calls through LangChain.

This repository is best understood as a forward-pass prototype: it loads a PDF or DOCX specification, extracts the relevant requirements, breaks the system into component descriptions, synthesizes pseudocode, generates code, and performs static verification. It does not currently implement the full reflection-and-repair loop described in the project concept documents.

## 1. Project Overview

The repository contains an end-to-end pipeline that processes a specification document in a staged way:

1. The input file is ingested and split into document chunks.
2. An Understanding Agent extracts the hardware requirements explicitly stated in the source text.
3. A Decomposer Agent turns the overall system into logical components and an implementation plan.
4. A Description Agent describes each component in structured form.
5. A Pseudocode Agent produces hardware-oriented pseudocode using a Grammar v1 schema.
6. A Code Generation Agent produces output code from the pseudocode and descriptions.
7. A Verification Agent performs static review against the original specification.

The compiled workflow is stored in a `StateGraph` object named `graph` in `src/orchestrator.py`. Each node returns partial state updates that are passed to the next node. All data is represented with Pydantic models defined in `src/schemas.py`.

## 2. Problem Statement

Hardware specifications are often long, semi-structured, and ambiguous. They may contain prose, tables, timing requirements, interface definitions, and constraints that are spread across the document. A single direct code-generation pass is prone to missing or misinterpreting required behavior.

This project tries to address that by separating the work into specialized stages:

- understanding the specification,
- decomposing the design into components,
- describing each component precisely,
- producing canonical pseudocode before final code generation,
- verifying the generated output against the source specification.

The implementation is intentionally conservative: the Understanding and Pseudocode agents are instructed to avoid inventing signals, widths, behaviors, or hardware facts that are not explicitly supported by the source specification.

## 3. Project Objectives

The repository aims to:

- ingest specification documents in PDF or DOCX format,
- preserve explicit specification evidence in structured output,
- break a larger hardware problem into smaller, tractable components,
- produce a hardware-oriented pseudocode representation before final code generation,
- enable static verification of generated code against the original specification,
- create a reusable agent-based workflow in Python using LangGraph and LangChain.

The codebase also contains deterministic validation logic for pseudocode syntax and structure in `src/agents/validate_pseudocode.py`. This validation is not a full compiler; it is a targeted grammar and structural check for the project’s canonical pseudocode format.

## 4. System Architecture

The current architecture is a single forward-pass state graph. The repository’s architecture document states that the graph is:

```text
START -> ingest -> understand -> decompose -> describe -> pseudocode
      -> generate -> verify -> END
```

This is the active graph in `src/orchestrator.py`.

The state is a `TypedDict` called `Spec2RTLState` and contains the following fields:

- `file_path`: input PDF or DOCX path
- `parent`: document chunks from ingestion
- `understanding`: structured specification understanding
- `decomposition`: component breakdown and implementation plan
- `descriptions`: list of component descriptions
- `pseudocode`: generated canonical pseudocode
- `generated_code`: generated code strings
- `generated_outputs`: structured code outputs
- `status`: pipeline status (`generated`, then `verified`)
- `verification`: static verification results
- `iteration`: reserved for future iterative repair

The active graph has no conditional edges, no repair loop, and no human approval gate. The architecture document explicitly notes that a reflection/fix loop is described conceptually but not connected to the compiled graph.

## 5. Agent Descriptions and Responsibilities

### 5.1 Understanding Agent

Location: `src/agents/understanding.py`

Role:
- reads the specification text chunks,
- extracts only explicitly stated facts,
- returns an `Understanding` model,
- preserves uncertainties and contradictions in the `ambiguities` field.

The prompt is intentionally strict: it forbids inventing signals, architectures, or requirements. If the source does not state something, it is reported as an ambiguity, not inferred.

Information flow:
- Input: parent chunks from `ingest_spec()`
- Output: `Understanding` instance
- Next consumer: Decomposer Agent

### 5.2 Decomposer Agent

Location: `src/agents/decomposer.py`

Role:
- takes the structured understanding JSON,
- breaks the overall design into smaller logical components,
- produces a `DecompositionOutput` with components, interactions, and an implementation plan.

Information flow:
- Input: `Understanding`
- Output: `DecompositionOutput`
- Next consumer: Description Agent

### 5.3 Description Agent

Location: `src/agents/description.py`

Role:
- takes one component from the decomposition,
- produces a detailed description of that component,
- emits `DescriptionOutput` containing module purpose, inputs, outputs, constraints, behavior, and specification references.

This agent does not generate RTL code and is explicitly instructed not to invent signal names, widths, or behavior.

Information flow:
- Input: one component object from `decomposition.components`
- Output: one `DescriptionOutput` per component
- Next consumers: Pseudocode Agent and Code Generation Agent

### 5.4 Pseudocode Agent

Location: `src/agents/pseudocode.py`

Role:
- reconstructs the original specification text from parent chunks,
- combines it with the understanding, decomposition, and descriptions,
- emits `PseudocodeGenerationOutput` using the project’s canonical Grammar v1 format.

The model is expected to produce structured JSON, which is parsed and validated. The implementation includes a deterministic parser/validator in `src/agents/validate_pseudocode.py` and will print validation failures if blocking issues are detected, while still returning the output in the current implementation.

Information flow:
- Input: original specification text, `Understanding`, `DecompositionOutput`, list of `DescriptionOutput`
- Output: `PseudocodeGenerationOutput`
- Next consumer: Code Generation Agent

### 5.5 Code Generation Agent

Location: `src/agents/code.py`

Role:
- takes the pseudocode and all component descriptions,
- emits a `CodeOuput` object with a `component_name` and `code` field.

This repository’s active implementation uses the agent to generate a string of code, not a Verilog module or a compiled RTL artifact. The prompt states “generate RTL code,” but the actual code object is a Python code string with `component_name` and `assumptions` fields.

Information flow:
- Input: `PseudocodeGenerationOutput` and description list
- Output: `CodeOuput`
- Next consumer: Verification Agent

### 5.6 Verification Agent

Location: `src/agents/verification.py`

Role:
- takes the source specification chunks and the generated code,
- performs static review only,
- returns a `VerificationResult` with `valid`, `issues`, `suggestions`, and `reasoning`.

This agent does not execute the code, compile it, or perform simulation or formal verification.

Information flow:
- Input: original specification chunks and `CodeOuput`
- Output: `VerificationResult`
- Final state: `verification` in the graph state

### 5.7 Reflection Agent

Location: `src/agents/reflection.py`

Status:
- the file exists in the repository but is currently empty (`0` bytes),
- it is not connected to the active graph,
- the architecture document notes that reflection and repair are planned but not yet implemented.

This is a clear limitation of the current repository state.

## 6. End-to-End Workflow

The end-to-end flow is implemented in `src/orchestrator.py` and is essentially the following:

1. `ingest_node(state)`
   - calls `ingest_spec(file_path)`
   - loads PDF or DOCX
   - splits into `parent` chunks and child chunks
   - stores only `parent` in graph state

2. `understanding_node(state)`
   - calls `understand_specification(state["parent"])`
   - produces `understanding`

3. `decomposition_node(state)`
   - calls `decomposer(state["understanding"])`
   - produces `decomposition`

4. `description_node(state)`
   - iterates through each component in `decomposition.components`
   - calls `describe_component(component)` once per component
   - produces `descriptions`

5. `pseudocode_node(state)`
   - rebuilds the original specification from `parent[*].page_content`
   - calls `generate_pseudocode(...)`
   - produces `pseudocode`

6. `generation_node(state)`
   - calls `generate_code(pseudocode, descriptions)`
   - stores the resulting code in `generated_code`
   - sets `status` to `generated`

7. `verify_node(state)`
   - calls `verify_code(state["parent"], generated_output)` for each generated output
   - stores verification results in `verification`
   - sets `status` to `verified`

The graph is compiled with `StateGraph` and exposed as `graph`.

## 7. Technologies and Libraries Used

The project depends on the following libraries as declared in `requirements.txt`:

- `langchain`
- `langchain-community`
- `langchain-openai`
- `langchain-text-splitters`
- `langchain-huggingface`
- `sentence-transformers`
- `torch`
- `python-dotenv`
- `docx2txt`
- `pymupdf`
- `qdrant-client`
- `langchain-qdrant`
- `langchain-openrouter`

The implementation also uses:

- LangGraph for the workflow graph (`StateGraph`)
- Pydantic for structured model validation (`src/schemas.py`)
- Document loaders from LangChain (`PyMuPDFLoader`, `Docx2txtLoader`)
- Recursive text splitting for chunking the specification
- Qdrant and embedding support in the vector-related modules (`src/vector_store.py`, `src/embeddings.py`)

The active runtime currently uses `ChatGroq` in `src/llm/llm.py` with `model="openai/gpt-oss-120b"` and `temperature=0`.

## 8. Project Directory Structure

```text
SPEC2RTL/
├── .env
├── .env.example
├── .gitignore
├── ARCHITECTURE.md
├── README.md
├── Spec2RTL-Agent-README.md
├── import.log
├── pyrightconfig.json
├── requirements.txt
├── traffic_light_controller.pdf
├── src/
│   ├── __init__.py
│   ├── embeddings.py
│   ├── ingestion.py
│   ├── llm/
│   │   └── llm.py
│   ├── orchestrator.py
│   ├── schemas.py
│   ├── toquery.py
│   ├── vector_store.py
│   └── agents/
│       ├── __init__.py
│       ├── code.py
│       ├── decomposer.py
│       ├── description.py
│       ├── pseudocode.py
│       ├── reflection.py
│       ├── understanding.py
│       ├── validate_pseudocode.py
│       └── verification.py
├── tests/
│   ├── test_description.py
│   └── test_embedding.py
├── test_llm_config.py
├── test_pseudocode_agent_prompt.py
├── test_validate_pseudocode.py
├── test_verification.py
└── outputs/
    └── pseudocode_raw.txt   (created at runtime when the pseudocode agent saves output)
```

The `outputs/` directory is not part of the source tree in the same way as the committed files; it is created by the pseudocode generation path when the model response is saved for debugging.

## 9. Installation and Setup

1. Create a Python environment.

```bash
python -m venv .venv
```

2. Activate the environment.

On POSIX shells:

```bash
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies.

```bash
pip install -r requirements.txt
```

4. Create a local environment file if you want to mirror the repository’s sample configuration.

```bash
copy .env.example .env
```

The repository contains an `.env.example` file with variables such as OpenRouter credentials and Qdrant settings, but the currently active `src/llm/llm.py` implementation does not read those values in the active `get_llm()` path.

## 10. Environment Variables and Configuration

The repository includes the following environment variables in `.env.example`:

- `SPEC2RTL_OPENROUTER_KEY`
- `SPEC2RTL_OPENROUTER_MODEL`
- `SPEC2RTL_OPENROUTER_UNDERSTANDING_MODEL`
- `SPEC2RTL_OPENROUTER_DECOMPOSER_MODEL`
- `SPEC2RTL_OPENROUTER_DESCRIPTION_MODEL`
- `SPEC2RTL_OPENROUTER_VERIFICATION_MODEL`
- `SPEC2RTL_OPENROUTER_PSEUDOCODE_MODEL`
- `SPEC2RTL_OPENROUTER_MAX_TOKENS`
- `SPEC2RTL_OPENROUTER_DESCRIPTION_MAX_TOKENS`
- `SPEC2RTL_OPENROUTER_DECOMPOSER_MAX_TOKENS`
- `QDRANT_URL`
- `QDRANT_API_KEY`

Important note:

- The file `src/llm/llm.py` contains a commented-out OpenRouter implementation and a currently active `ChatGroq` implementation.
- The active runtime path is:

```python
llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
)
```

- The vector store utilities in `src/vector_store.py` expect `QDRANT_URL` and `QDRANT_API_KEY` to be set, but they are not wired into the active graph execution in `src/orchestrator.py`.

## 11. How to Run the Project

There is no top-level CLI entrypoint or `main.py` in the repository. The active invocation pattern is programmatic and matches the architecture document example:

```python
from src.orchestrator import graph

result = graph.invoke({
    "file_path": "path/to/specification.pdf",
})
```

This returns the accumulated state, including the intermediate artifacts and verification results.

The repository also contains a smaller verification example script, `test_verification.py`, which accepts a PDF or DOCX specification path and performs a static review of a sample code string:

```bash
python test_verification.py "path/to/specification.pdf"
```

This is not the same as running the complete multi-agent pipeline, but it demonstrates the static verification path.

## 12. Testing

The repository includes several test modules, each covering a specific aspect of the implementation:

- `test_llm_config.py`
  - verifies OpenRouter free-model configuration rules and retry behavior
- `test_pseudocode_agent_prompt.py`
  - checks prompt text requirements for canonical pseudocode generation
- `test_validate_pseudocode.py`
  - validates grammar and structural rules for the pseudocode format
- `test_verification.py`
  - provides a verification command-line example
- `tests/test_description.py`
  - checks the Description Agent’s configuration and response contract
- `tests/test_embedding.py`
  - verifies that the embedding helper produces a 384-dimensional vector

The tests are mostly focused and configuration-oriented. They do not represent a complete end-to-end pipeline validation for arbitrary hardware specifications.

## 13. Example Input and Output

The repository's validator tests provide a concrete example of the project’s canonical pseudocode format. The following snippet is taken from the test fixtures in `test_validate_pseudocode.py`:

```text
MODULE counter
CLOCK clk EDGE RISING
INPUT rst_n
INPUT enable
OUTPUT count[7:0]
REG count_reg[7:0]

BLOCK COMBINATIONAL
  ASSIGN count = count_reg
END BLOCK

BLOCK CLOCKED CLOCK clk EDGE RISING
  RESET ASYNCHRONOUS SIGNAL rst_n ACTIVE_LOW VALUE 0
  IF rst_n == 0 THEN
    count_reg <= 8'b00000000
  ELSE
    IF enable == 1 THEN
      count_reg <= count_reg + 8'b00000001
    END IF
  END IF
END BLOCK
END MODULE
```

The schema for the verification output is defined in `src/schemas.py` as `VerificationResult`:

```json
{
  "valid": true,
  "issues": [],
  "suggestions": [],
  "reasoning": "Static review found no clear mismatch with the specification."
}
```

This is the exact structure used by the `verify_code()` agent, even though the specific verification text is generated dynamically by the model.

## 14. Current Limitations

The repository is a working prototype, but it has several important limitations that are visible in the actual code:

- Single forward pass only: there is no repair loop or iterative refinement step in the graph.
- No reflection agent integration: `src/agents/reflection.py` is empty, and the architecture document explicitly notes the missing repair flow.
- No human approval gate: the workflow proceeds from ingest to verification without an explicit approval step.
- `ingest_node` discards child chunks after creating them; vector retrieval is not part of the compiled graph.
- The active `get_llm()` implementation is fixed to Groq and does not use the environment-variable-based per-agent configuration from `.env.example`.
- The code generation path emits a code string rather than a verified end-to-end HDL artifact for a specific target language.
- Verification is static and uses the original specification as a textual reference; it does not compile, simulate, or formally prove the generated code.
- The project includes concept-level documentation that describes future capabilities not connected to the current implementation.

## 15. Future Improvements

The architecture document mentions several planned production improvements that are not yet wired into the compiled graph. These include:

- a verification loop with error-driven regeneration,
- an explicit reflection/fix step,
- human-in-the-loop approval or review,
- stronger linkage between source-chunk retrieval and agent context,
- better deterministic validation of generated pseudocode and code,
- expanded document handling and more robust evidence tracking.

In other words, the repository clearly contains a design for a more complete agentic workflow, but the currently active implementation is a documented and bounded forward-pass pipeline.

---

This repository should be read as a hardware-specification-to-structured-analysis workflow built around LangChain, LangGraph, Pydantic, and LLM-driven agents. The active code is the source of truth; concepts in the architecture documentation should be understood as design intent rather than currently active graph behavior.
