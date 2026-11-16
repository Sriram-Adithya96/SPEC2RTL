# AGENTS.md

## 1. Project Overview

Spec2RTL-Agent is a multi-agent AI system that processes hardware specification documents and progressively converts their requirements into structured hardware implementation plans.

The long-term goal is to generate correct RTL code from complex hardware specifications.

The current development milestone ends at **pseudocode generation**.

The immediate objective is to build a reliable pipeline that transforms a hardware specification into a verified, structured implementation plan and corresponding pseudocode.

Do not implement downstream code-generation or hardware-synthesis stages unless explicitly requested.

## 2. Current Scope

The current pipeline includes:

1. Document ingestion.
2. Specification understanding.
3. Hardware decomposition.
4. Component description.
5. Description verification.
6. Reflection and correction.
7. Implementation-plan validation.
8. Pseudocode generation.
9. Final structured output.

The pipeline must preserve the original specification's requirements and clearly identify missing or ambiguous information.

### Out of Scope for the Current Milestone

Do not implement the following as part of the current milestone:

- Python implementation generation.
- C++ implementation generation.
- Verilog or SystemVerilog generation.
- RTL simulation or hardware verification.
- High-level synthesis.
- Hardware optimization.

These are potential future development stages.

## 3. Core Development Principles

### 3.1 Specification Is the Source of Truth

All generated outputs must be grounded in the uploaded specification.

Never invent:

- Signal names.
- Signal widths.
- Input or output ports.
- Clock frequencies.
- Reset polarity or behavior.
- Timing constraints.
- Protocol requirements.
- Hardware components.
- Functional requirements.
- Algorithmic behavior not supported by the specification.

If required information is missing, explicitly mark it as:

`NOT SPECIFIED: <item>`

If requirements conflict, record the conflict and identify the affected requirement.

Do not silently choose one interpretation.

### 3.2 Preserve Traceability

Every important requirement should remain traceable to its source.

Where available, preserve:

- Original page numbers.
- Section identifiers.
- Table or figure references.
- Relevant source text.
- Requirement identifiers.

Do not fabricate source references.

If source-location metadata is unavailable, explicitly represent that limitation.

### 3.3 Prefer Structured Outputs

Use Pydantic models for outputs passed between agents.

Avoid relying on unstructured natural-language responses when a structured schema is appropriate.

Validate agent outputs before passing them to downstream stages.

Keep schemas consistent with their agent prompts and function signatures.

Do not introduce duplicate or conflicting schema definitions.

### 3.4 Separate Responsibilities

Each agent should have one clearly defined responsibility.

An agent must not silently perform the responsibilities of later stages.

In particular:

- The Understanding Agent extracts facts and requirements.
- The Decomposer Agent organizes the design into components and implementation steps.
- The Description Agent describes one component using the supplied evidence.
- The Verification Agent checks whether a description is supported by the specification.
- The Reflection Agent corrects identified problems without changing unrelated, correct information.
- The Pseudocode Generator converts verified implementation instructions into pseudocode.

Do not generate RTL in any of these agents during the current milestone.

## 4. Agent Responsibilities

### 4.1 Understanding Agent

Input:
- Extracted specification text and available source metadata.

Output:
- System purpose.
- Explicitly identified components.
- Inputs and outputs.
- Functional requirements.
- Constraints.
- Ambiguities and missing information.

Requirements:

- Preserve signal names, widths, units, timing values, and protocol names exactly.
- Distinguish explicit requirements from interpretations.
- Record contradictions instead of resolving them.
- Do not design new components or invent implementation details.
- Do not generate pseudocode or RTL.

### 4.2 Decomposer Agent

Input:
- Structured understanding output.

Output:
- Component list.
- Component purposes.
- Explicitly supported component interfaces.
- Component interactions.
- Ordered implementation plan.
- Dependencies between implementation steps.

Requirements:

- Keep the decomposition consistent with the specification.
- Do not invent components or interfaces.
- Identify dependencies between components.
- Flag unresolved architectural decisions.
- Do not assume that every system requires the same component structure.

### 4.3 Description Agent

Input:
- One component and its supporting specification information.

Output:
- Component name.
- Purpose.
- Inputs.
- Outputs.
- State elements when explicitly specified or adequately supported.
- Constraints.
- Functional behavior.
- Source references.

Requirements:

- Describe only the supplied component.
- Preserve exact interface details.
- Do not invent widths, reset values, or behavior.
- Keep prompt instructions consistent with the Pydantic schema.
- Clearly distinguish state elements from internal combinational signals.

### 4.4 Verification Agent

Input:
- Relevant source specification evidence.
- Component description.

Output:
- Verification status.
- Issues.
- Suggested corrections.
- Reasoning and supporting evidence.

Requirements:

- Perform specification-based textual verification.
- Identify unsupported claims, contradictions, and missing requirements.
- Do not claim that code has been compiled or simulated when it has not.
- Do not modify the component description.
- Distinguish a verified claim from a claim that cannot be established using the available evidence.

A passing textual review does not prove hardware correctness.

### 4.5 Reflection Agent

Input:
- Original specification evidence.
- Current component description.
- Verification issues.

Output:
- Corrected component description.
- A record of changes made.

Requirements:

- Fix only identified issues.
- Preserve information that is already correct.
- Do not invent requirements to satisfy verification.
- Do not remove unresolved ambiguities silently.
- Re-verify the corrected description.
- Use a configurable maximum retry count.
- Report unresolved issues when the retry limit is reached.

### 4.6 Pseudocode Generator

Input:
- Verified component descriptions.
- Validated implementation plan.
- Explicit functional requirements and constraints.

Output:
- Structured pseudocode for each component or implementation step.
- Clear operation order.
- Conditional logic and iteration where supported by the requirements.
- Data dependencies.
- Relevant assumptions or unresolved questions.
- Links to the requirements that support the pseudocode.

Requirements:

- Do not generate Python, C++, Verilog, or SystemVerilog.
- Do not introduce behavior that is absent from the verified inputs.
- Preserve specified operation ordering and timing-related requirements.
- Flag missing information that prevents a complete algorithm.
- Do not confuse algorithmic pseudocode with a complete cycle-accurate hardware design.
- Make the output understandable and reviewable by a human engineer.

## 5. Pipeline Orchestration

Keep the main workflow in a dedicated orchestration module rather than embedding the entire workflow inside individual agents.

The orchestration layer should:

1. Validate the input document.
2. Run document ingestion.
3. Invoke the Understanding Agent.
4. Validate the understanding output.
5. Invoke the Decomposer Agent.
6. Validate the decomposition.
7. Describe the required components.
8. Verify each component description against relevant specification evidence.
9. Invoke reflection for failed descriptions.
10. Re-verify corrected descriptions.
11. Stop retries after a configurable limit.
12. Validate the implementation plan.
13. Generate pseudocode only from sufficiently verified inputs.
14. Produce a final report containing results and unresolved issues.

If a stage fails, return a clear error and preserve useful diagnostic information.

Do not silently continue using invalid or incomplete outputs.

## 6. Document Processing

Supported document formats must match the actual implementation.

Currently, the ingestion layer supports PDF and DOCX files.

When modifying document processing:

- Preserve source metadata where possible.
- Keep document chunking deterministic and testable.
- Avoid losing important signal definitions or constraints across chunk boundaries.
- Consider how tables, equations, figures, and scanned pages affect information extraction.
- Do not claim OCR or multimodal extraction is supported unless implemented and tested.
- Keep document extraction separate from agent reasoning.

Treat retrieval and vector search as optional capabilities unless the current workflow explicitly requires them.

## 7. Schemas and Data Contracts

Use Pydantic models for agent inputs and outputs.

When changing a schema:

1. Search for all usages of the model.
2. Update the relevant agent prompt.
3. Update the function signature if necessary.
4. Update orchestration code.
5. Update tests and example data.
6. Check serialization and deserialization.

Avoid duplicate schema definitions.

Do not change public function names or field names unnecessarily.

If a change is required, update all callers and tests consistently.

## 8. LLM Configuration and Reliability

Use the existing centralized LLM configuration in `src/llm/llm.py`.

Do not create independent hardcoded API configurations inside individual agents.

Requirements:

- Load API keys from environment variables.
- Never hardcode secrets.
- Never print API keys or expose them in errors.
- Handle API failures and malformed responses.
- Validate structured model outputs.
- Keep prompts focused on the agent's responsibility.
- Avoid unnecessary repeated LLM calls.
- Do not assume that a model's textual response is automatically correct.

Keep credentials out of source control.

Update `.env.example` when required configuration changes.

## 9. Error Handling and Logging

Provide actionable error messages for:

- Unsupported file formats.
- Empty documents.
- Document extraction failures.
- Invalid structured outputs.
- Missing required configuration.
- LLM API failures.
- Verification failures.
- Exhausted reflection retries.
- Missing or contradictory specification requirements.

Log the pipeline stage and relevant error context.

Do not log secrets or unnecessarily expose complete sensitive documents.

Preserve intermediate results when useful for debugging.

## 10. Testing Requirements

Write unit tests for deterministic logic and agent configuration.

Mock external LLM and database calls in unit tests.

Keep optional live LLM integration tests separate from ordinary unit tests.

Test at least:

- Empty and unsupported document inputs.
- Preservation of explicit signal names and widths.
- Missing and contradictory requirements.
- Structured-output validation.
- Component decomposition.
- Description verification.
- Reflection corrections.
- Retry-limit behavior.
- Pseudocode generation from verified descriptions.
- Prevention of unsupported assumptions.
- End-to-end pipeline behavior using mocked agents.

Do not claim a test passed unless it was actually executed.

Run the relevant tests after modifying code.

## 11. Dependencies and Configuration

Keep `requirements.txt` synchronized with actual imports.

Do not add a dependency without a clear purpose.

Before introducing a new package, check whether an existing dependency already provides the required functionality.

Document all required environment variables in `.env.example`.

Do not make the application depend on unused API keys or external services.

Keep optional vector-database functionality separate from the minimum viable pipeline.

## 12. Coding Conventions

- Follow existing Python conventions.
- Use descriptive function and variable names.
- Add type annotations to public functions.
- Keep functions focused and reasonably small.
- Remove unused imports and duplicate code.
- Prefer explicit error handling over silent fallback behavior.
- Avoid unnecessary abstractions and dependencies.
- Keep prompts readable and maintainable.
- Reuse existing schemas when appropriate.
- Avoid changing unrelated files during a focused task.

## 13. Documentation

Update documentation when architecture, schemas, dependencies, configuration, or execution instructions change.

Document:

- Current implemented features.
- Current development milestone.
- Agent responsibilities.
- Data flow between agents.
- Required environment variables.
- Installation and test commands.
- Known limitations.
- Features that are planned but not implemented.

Clearly distinguish existing functionality from future plans.

## 14. Instructions for AI Coding Agents

Before making changes:

1. Inspect the relevant source files.
2. Trace the affected functions, schemas, prompts, and tests.
3. Identify the smallest change that solves the problem.
4. Follow the current milestone and architecture.
5. Avoid duplicating existing functionality.

After making changes:

1. Review all affected callers.
2. Update relevant tests and documentation.
3. Run the available checks.
4. Report what changed.
5. Report which tests passed or failed.
6. Identify any remaining limitations.

Do not rewrite the entire repository when a targeted change is sufficient.

Do not claim a feature is implemented merely because a prompt or placeholder exists.

**Current milestone boundary: specification ingestion → understanding → decomposition → description → verification/reflection → implementation plan → pseudocode.**