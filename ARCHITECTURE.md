# Spec2RTL Architecture

## 1. Purpose

Spec2RTL converts a hardware specification document into a structured
understanding, a component decomposition, component descriptions, canonical
pseudocode, generated implementation code, and a static verification report.
The executable workflow is defined in [`src/orchestrator.py`](src/orchestrator.py).

The current implementation is a single forward pass. It does not yet contain a
conditional verification loop, automatic repair step, or human approval gate.
Those capabilities are described in the project concept documents, but are not
connected to the compiled graph.

## 2. System context

```text
PDF/DOCX specification
          |
          v
   Document ingestion
          |
          v
  Understanding Agent
          |
          v
   Decomposer Agent
          |
          v
  Description Agent (once per component)
          |
          v
 Pseudocode Generation Agent
          |
          v
    Code Generation Agent
          |
          v
     Verification Agent
          |
          v
  Results and verification report
```

The workflow is built with LangGraph's `StateGraph`. `START` enters the
`ingest` node and `END` follows the `verify` node:

```text
START -> ingest -> understand -> decompose -> describe -> pseudocode
      -> generate -> verify -> END
```

There are no conditional edges in the current graph. Every successful node
executes exactly once, except that `describe` invokes its agent once for each
decomposed component and `verify` invokes its agent once for each generated
output.

## 3. Runtime entry point

The compiled graph is imported and invoked with an initial state containing a
`file_path`. A minimal invocation is:

```python
from src.orchestrator import graph

result = graph.invoke({
    "file_path": "/path/to/specification.pdf",
})
```

See [`test.py`](test.py) for the current example invocation.

The returned state contains the accumulated intermediate artifacts:

```text
understanding
decomposition
descriptions
pseudocode
generated_code
generated_outputs
status
verification
```

## 4. Shared workflow state

`Spec2RTLState` in [`src/orchestrator.py`](src/orchestrator.py) is the
LangGraph state contract:

| Field | Type | Producer | Purpose |
|---|---|---|---|
| `file_path` | `str` | caller | Input PDF or DOCX path |
| `parent` | `list` | `ingest` | Parent document chunks used as source evidence |
| `understanding` | `Understanding` | `understand` | Structured requirements extracted from the specification |
| `decomposition` | `DecompositionOutput` | `decompose` | Components, interactions, and implementation plan |
| `descriptions` | `list[DescriptionOutput]` | `describe` | One detailed description per component |
| `pseudocode` | `PseudocodeGenerationOutput` | `pseudocode` | System-level canonical hardware pseudocode |
| `generated_code` | `list[str]` | `generate` | Code strings exposed for consumers |
| `generated_outputs` | `list[CodeOuput]` | `generate` | Structured code output and assumptions |
| `status` | `str` | `generate`, `verify` | `"generated"` then `"verified"` |
| `verification` | `list[VerificationResult]` | `verify` | Static verification results |
| `iteration` | `int` | caller/consumer | Reserved for future iterative repair |

The state is accumulated by returning partial dictionaries from each node.
Nodes read only the fields produced by their predecessors, except for
`file_path`, which is supplied by the caller.

## 5. End-to-end workflow

### 5.1 Ingest the specification

**Node:** `ingest`  
**Implementation:** `ingest_node` in [`src/orchestrator.py`](src/orchestrator.py)  
**Helper:** [`src/ingestion.py`](src/ingestion.py)

`ingest_spec(file_path)` supports:

- `.pdf`, loaded with `PyMuPDFLoader`
- `.docx`, loaded with `Docx2txtLoader`

Unsupported extensions raise `ValueError("Unsupported file type")`.

The loader first creates parent chunks using
`RecursiveCharacterTextSplitter` with a 2,000-character chunk size and
200-character overlap. Each parent is then split into child chunks with a
700-character chunk size and 100-character overlap. Child metadata receives a
`parent_id` identifying its parent.

The node stores only `parent` in graph state. The `children` result is created
but currently discarded by `ingest_node`; vector retrieval is not part of the
compiled workflow.

### 5.2 Understand the specification

**Node:** `understand`  
**Implementation:** `understanding_node` in
[`src/orchestrator.py`](src/orchestrator.py)  
**Agent:** [`src/agents/understanding.py`](src/agents/understanding.py)

The Understanding Agent receives the parent `Document` chunks and returns an
`Understanding` Pydantic model containing:

- system purpose
- explicitly named major components
- inputs and outputs
- functional requirements
- constraints
- ambiguities and conflicts

The prompt makes the original specification authoritative. The agent must not
invent signals, widths, timing, architecture, or behavior, and must preserve
ambiguities instead of resolving them.

### 5.3 Decompose the design

**Node:** `decompose`  
**Implementation:** `decomposition_node` in
[`src/orchestrator.py`](src/orchestrator.py)  
**Agent:** [`src/agents/decomposer.py`](src/agents/decomposer.py)

The Decomposer Agent receives the `Understanding` model serialized as JSON.
It returns a `DecompositionOutput` containing:

- `components`: logical hardware components with purpose, inputs, and outputs
- `interactions`: relationships between components
- `implementation_plan`: ordered implementation steps

This stage changes the granularity of the design from system-level requirements
to implementable component boundaries.

### 5.4 Describe each component

**Node:** `describe`  
**Implementation:** `description_node` in
[`src/orchestrator.py`](src/orchestrator.py)  
**Agent:** [`src/agents/description.py`](src/agents/description.py)

The node iterates over `decomposition.components` and calls
`describe_component(component)` once per component. The calls are sequential.
Each result is a `DescriptionOutput` containing:

- module name and purpose
- input and output signal records
- state elements
- constraints
- behavior
- specification references

The description prompt forbids generating RTL and instructs the agent not to
invent signal names, widths, or behavior.

### 5.5 Generate canonical pseudocode

**Node:** `pseudocode`  
**Implementation:** `pseudocode_node` in
[`src/orchestrator.py`](src/orchestrator.py)  
**Agent:** [`src/agents/pseudocode.py`](src/agents/pseudocode.py)

The node reconstructs the original specification text by joining
`parent[*].page_content` with blank lines. It passes that primary evidence,
the `Understanding`, the decomposition, and all component descriptions to
`generate_pseudocode`.

The pseudocode agent returns `PseudocodeGenerationOutput`:

- `module_name`
- `objective`
- `inputs`
- `outputs`
- `pseudocode`
- `assumptions`
- `unresolved_issues`

The prompt defines SPEC2RTL Grammar v1. Its rules cover module declarations,
signals, registers, states, combinational blocks, clocked blocks, reset
metadata, assignments, control structures, and explicit unresolved entries.
The original specification remains the primary source of truth; derived
context must not add unsupported hardware facts.

The module also contains deterministic response parsing and validation helpers
for malformed JSON and pseudocode structure. These helpers are available to
callers, but `pseudocode_node` currently calls `generate_pseudocode` directly
and does not invoke `validate_pseudocode_detailed` as a graph node.

### 5.6 Generate implementation code

**Node:** `generate`  
**Implementation:** `generation_node` in
[`src/orchestrator.py`](src/orchestrator.py)  
**Agent:** [`src/agents/code.py`](src/agents/code.py)

The Code Generation Agent receives the structured pseudocode and all component
descriptions. It returns one `CodeOuput` object containing:

- `component_name`
- `code`
- `assumptions`

The node stores the result in both output collections:

```python
"generated_code": [result.code]
"generated_outputs": [result]
```

It also sets `status` to `"generated"`. Although the surrounding project calls
the target RTL, the current schema and verification prompt refer to generated
Python code; consumers should treat the exact emitted language as a current
implementation detail until the contract is aligned.

### 5.7 Verify generated code

**Node:** `verify`  
**Implementation:** `verify_node` in
[`src/orchestrator.py`](src/orchestrator.py)  
**Agent:** [`src/agents/verification.py`](src/agents/verification.py)

For every item in `generated_outputs`, the node calls
`verify_code(parent, generated_output)`. The verification agent receives:

- the complete original specification text from the parent chunks
- generated code
- component name
- generation assumptions

Verification is static review only. The agent does not execute, compile,
simulate, or formally verify the generated code. It returns a
`VerificationResult`:

- `valid`
- `issues`
- `suggestions`
- `reasoning`

After all outputs are reviewed, the node sets `status` to `"verified"` and the
graph terminates.

## 6. Agent and model boundary

The agent modules create LangChain agents with structured Pydantic response
formats. They obtain their model from [`src/llm/llm.py`](src/llm/llm.py).
The active provider is `ChatGroq` with:

```text
model: openai/gpt-oss-120b
temperature: 0
```

Credentials and provider configuration are loaded from the environment through
`python-dotenv`; secrets are not stored in the repository.

The agents are intentionally narrow:

```text
Understanding  -> extract and organize
Decomposer    -> split and plan
Description   -> detail one component
Pseudocode    -> express the whole design canonically
Code          -> generate one implementation
Verification  -> compare implementation with source evidence
```

No agent in the compiled path has tools configured. All inter-stage data is
passed as serialized Pydantic data or document text.

## 7. Data model relationships

The models in [`src/schemas.py`](src/schemas.py) form a pipeline:

```text
Understanding
      |
      v
DecompositionOutput
      |
      v
DescriptionOutput[] ----+
                        |
Understanding ----------+--> PseudocodeGenerationOutput
DecompositionOutput ----+             |
                                      v
                              CodeOuput
                                      |
                                      v
                              VerificationResult
```

`VerificationResult`, `DescriptionRevisionInput`, and `ImplementationPlan`
also provide contracts for future refinement workflows. They are not currently
used to create graph edges in `orchestrator.py`.

## 8. Supporting modules outside the graph

The repository includes building blocks that are not currently wired into the
compiled workflow:

- [`src/agents/validate_pseudocode.py`](src/agents/validate_pseudocode.py)
  provides deterministic Grammar v1 parsing and semantic validation.
- [`src/agents/reflection.py`](src/agents/reflection.py) is reserved for
  reflection-driven correction when verification fails.
- [`src/vector_store.py`](src/vector_store.py) can create a Qdrant-backed
  `spec2rtl` collection using 1,024-dimensional embeddings.
- [`src/embeddings.py`](src/embeddings.py) provides embedding configuration.
- [`src/toquery.py`](src/toquery.py) formats an `Understanding` object as text.

The current ingestion path creates child chunks suitable for retrieval, but no
child chunks are inserted into Qdrant and no retriever is called by the graph.

## 9. Error and boundary behavior

Errors are surfaced rather than converted into successful-looking results:

- unsupported document types raise `ValueError`
- empty or malformed pseudocode model responses raise `ValueError`
- missing required pseudocode fields raise `ValueError`
- missing Qdrant configuration raises `ValueError`
- agent invocation failures propagate through the graph

Because the graph has no recovery edges, a failure stops the invocation. A
verification result with `valid=False` is data in the returned state; it does
not automatically trigger regeneration.

## 10. Current limitations and next extension points

The architecture is ready for the following additions, but they require
explicit graph changes:

1. Add a pseudocode validation node after pseudocode generation and route
   blocking grammar issues back to pseudocode generation.
2. Add conditional verification edges for `valid=True` and `valid=False`.
3. Use the reflection agent to classify failures and revise the relevant
   artifact.
4. Preserve and use `children` for retrieval-backed evidence selection.
5. Add compilation, simulation, or formal checks if executable RTL validation
   is required.
6. Align `CodeOuput` and verification terminology with the actual target
   language and RTL deliverable.
7. Replace the reserved `iteration` field with an explicit bounded retry
   policy if iterative repair is introduced.

Any extension should preserve the source-of-truth rule: the original
specification must remain authoritative, and unsupported behavior must remain
explicitly unresolved rather than silently inferred.
