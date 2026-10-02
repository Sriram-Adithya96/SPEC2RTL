# Spec2RTL-Agent

## Automated Hardware RTL Generation from Complex Specifications Using LLM Agents

Spec2RTL-Agent is an AI-powered multi-agent system that converts complex hardware specification documents into RTL (Register Transfer Level) code.

The project is inspired by the research paper:

**"Spec2RTL-Agent: Automated Hardware Code Generation from Complex Specifications Using LLM Agent Systems."**

The main idea is:

> Specification PDF → Understand → Decompose → Generate Code → Verify → Reflect/Fix → Final RTL

Instead of asking a single LLM to directly generate hardware code, our system uses multiple specialized AI agents. Each agent performs a specific stage of the hardware development process.

---

## 🚀 Problem Statement

Hardware specifications can be long and difficult to understand.

A real hardware specification may contain:

- Text
- Tables
- Figures
- Equations
- Functional requirements
- Constraints
- Multiple hardware modules

Generating RTL directly from such specifications can result in incorrect or incomplete implementations.

### Traditional Approach

```text
Hardware Specification
        ↓
Human Engineer
        ↓
Architecture Design
        ↓
RTL Coding
        ↓
Testing
        ↓
Debugging
        ↓
Final RTL
```

This process requires significant human effort.

### Our Approach

```text
Hardware Specification
        ↓
AI Understanding
        ↓
Module Decomposition
        ↓
Implementation Planning
        ↓
RTL Generation
        ↓
Verification
        ↓
Reflection & Error Correction
        ↓
Final RTL
```

---

# 🎯 Project Goal

The goal of Spec2RTL-Agent is to automate most of the hardware implementation workflow using LLM agents.

The system should be able to:

1. Accept a hardware specification document.
2. Extract important requirements.
3. Understand the hardware functionality.
4. Break the design into smaller modules.
5. Create an implementation plan.
6. Generate RTL code.
7. Generate or use test cases.
8. Verify the generated RTL.
9. Detect errors.
10. Identify the likely source of errors.
11. Correct or regenerate the affected code.
12. Produce final RTL and a verification report.

---

# 🧠 Core Architecture

```text
                 Hardware Specification
                          │
                          ▼
                ┌───────────────────┐
                │ Document Parser   │
                └─────────┬─────────┘
                          │
                          ▼
                ┌───────────────────┐
                │ Understanding     │
                │ Agent             │
                └─────────┬─────────┘
                          │
                          ▼
                ┌───────────────────┐
                │ Decomposer Agent  │
                └─────────┬─────────┘
                          │
                          ▼
                 Implementation Plan
                          │
                          ▼
                ┌───────────────────┐
                │ Description Agent │
                └─────────┬─────────┘
                          │
                          ▼
                ┌───────────────────┐
                │ Coder Agent       │
                └─────────┬─────────┘
                          │
                          ▼
                    Generated RTL
                          │
                          ▼
                ┌───────────────────┐
                │ Verification      │
                │ Agent             │
                └─────────┬─────────┘
                          │
                    ┌─────┴─────┐
                    │           │
                   PASS        FAIL
                    │           │
                    ▼           ▼
               Final RTL   Reflection Agent
                                │
                                ▼
                           Error Analysis
                                │
                                ▼
                           Fix / Regenerate
                                │
                                └──────→ Verification
```

---

# 🤖 AI Agents

## 1. Understanding Agent

The Understanding Agent reads and analyzes the hardware specification.

It extracts information such as:

- Hardware purpose
- Inputs
- Outputs
- Functional requirements
- Constraints
- Modules
- Important equations
- Relevant tables and information

### Example

Input:

```text
Design an 8-bit ALU supporting
addition, subtraction, AND and OR.
```

Output:

```json
{
  "module": "ALU",
  "data_width": 8,
  "operations": [
    "ADD",
    "SUB",
    "AND",
    "OR"
  ]
}
```

---

## 2. Decomposer Agent

Large hardware systems should not be generated in one step.

The Decomposer Agent breaks the complete design into smaller sub-functions.

### Example

```text
CPU
├── Controller
├── ALU
├── Register File
├── Instruction Decoder
└── Memory Interface
```

Each module can then be implemented separately.

---

## 3. Description Agent

The Description Agent prepares structured information for each sub-function.

### Example

```json
{
  "module": "ALU",
  "inputs": ["A", "B", "opcode"],
  "outputs": ["result"],
  "functionality": [
    "Addition",
    "Subtraction",
    "AND",
    "OR"
  ]
}
```

This structured information is passed to the coding stage.

---

## 4. Coder Agent

The Coder Agent generates the hardware implementation.

For our prototype, the primary target will be:

- Verilog
- SystemVerilog

### Example

```verilog
module ALU(
    input [7:0] A,
    input [7:0] B,
    input [1:0] opcode,
    output reg [7:0] result
);

always @(*) begin
    case(opcode)
        2'b00: result = A + B;
        2'b01: result = A - B;
        2'b10: result = A & B;
        2'b11: result = A | B;
    endcase
end

endmodule
```

---

## 5. Verification Agent

Generated RTL must be tested.

The Verification Agent checks whether the implementation satisfies the specification.

```text
Generated RTL
      ↓
Generate Testbench
      ↓
Run Simulation
      ↓
Compare Expected vs Actual
      ↓
PASS / FAIL
```

### Example

```text
Input:
A = 5
B = 3
Operation = ADD

Expected:
8

Actual:
8

Result:
PASS
```

---

## 6. Reflection Agent

If verification fails, the Reflection Agent investigates the error.

Possible causes:

```text
1. Incorrect specification understanding
2. Incorrect implementation plan
3. Error in a previous module
4. Error in the current module
5. Insufficient information
```

The Reflection Agent decides what should happen next.

```text
Verification Failure
        ↓
Reflection Agent
        │
        ├── Wrong instruction
        │       ↓
        │   Revise plan
        │
        ├── Previous module error
        │       ↓
        │   Revisit module
        │
        ├── Current module error
        │       ↓
        │   Regenerate module
        │
        └── Unknown error
                ↓
          Human intervention
```

---

# 🔄 Complete Workflow

Consider a user uploading:

```text
FIFO_Specification.pdf
```

The specification contains:

```text
Data width: 8 bits
Depth: 16 entries

Operations:
- Write
- Read

Signals:
- clk
- reset
- write_en
- read_en
- data_in
- data_out
- full
- empty
```

### Step 1 — Understand

The AI identifies:

```text
Hardware: FIFO
Data width: 8 bits
Depth: 16
```

### Step 2 — Decompose

```text
1. Memory
2. Write pointer
3. Read pointer
4. Full logic
5. Empty logic
```

### Step 3 — Create Implementation Plan

```text
Create memory
Create write logic
Create read logic
Create status flags
Connect modules
```

### Step 4 — Generate RTL

The Coder Agent generates the Verilog/SystemVerilog implementation.

### Step 5 — Verify

The system generates/runs tests:

```text
Write data
Read data
Check output
Check empty flag
Check full flag
Reset FIFO
```

### Step 6 — Reflect

Suppose:

```text
Expected: empty = 1
Actual:   empty = 0
```

The Reflection Agent analyzes the failure.

### Step 7 — Fix

The incorrect logic is regenerated or corrected.

### Step 8 — Verify Again

```text
All tests passed
```

### Final Output

```text
Final RTL
Testbench
Verification Report
Error/Fix History
Implementation Summary
```

---

# 🏗️ Proposed Technology Stack

## Frontend

- React.js
- Vite
- Tailwind CSS
- Axios

## Backend

- Python
- FastAPI

## AI

- LLM API
- Agent orchestration
- Prompt engineering
- Structured JSON outputs

## Document Processing

- PDF text extraction
- OCR for scanned documents
- Document chunking
- Table/figure processing where required

## Hardware

- Verilog/SystemVerilog
- RTL testbenches
- RTL simulation tools

## Optional Advanced Layer

- C/C++
- High-Level Synthesis (HLS)
- Hardware optimization

## Database

Optional for the MVP.

Can later store:

- Projects
- Specifications
- Generated RTL
- Test cases
- Verification results
- Agent execution history

---

# 🖥️ Proposed User Interface

The application will provide a simple dashboard.

```text
┌────────────────────────────────────────────┐
│              Spec2RTL-Agent                │
├────────────────────────────────────────────┤
│                                            │
│   Upload Hardware Specification            │
│                                            │
│          [ Upload PDF ]                    │
│                                            │
│          [ Generate RTL ]                  │
│                                            │
├────────────────────────────────────────────┤
│ AI PROCESS                                 │
│                                            │
│ ✓ Document understood                      │
│ ✓ Modules identified                       │
│ ✓ Architecture generated                   │
│ ✓ RTL generated                            │
│ ✓ Verification completed                   │
│                                            │
├────────────────────────────────────────────┤
│ Generated RTL                              │
│                                            │
│ module FIFO (...);                         │
│ ...                                        │
│                                            │
│ [Download RTL]                             │
└────────────────────────────────────────────┘
```

---

# 📁 Project Structure

```text
Spec2RTL-Agent/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── App.jsx
│   │
│   └── package.json
│
├── backend/
│   ├── agents/
│   │   ├── understanding_agent.py
│   │   ├── decomposer_agent.py
│   │   ├── description_agent.py
│   │   ├── coder_agent.py
│   │   ├── verifier_agent.py
│   │   └── reflection_agent.py
│   │
│   ├── document/
│   │   ├── pdf_parser.py
│   │   └── chunker.py
│   │
│   ├── verification/
│   │   ├── testbench_generator.py
│   │   └── simulator.py
│   │
│   ├── api/
│   │   └── routes.py
│   │
│   ├── orchestrator.py
│   └── main.py
│
├── generated/
│   ├── rtl/
│   ├── testbenches/
│   └── reports/
│
├── specifications/
│
├── tests/
│
├── .env.example
├── .gitignore
└── README.md
```

---

# 🚧 Development Plan

## Phase 1 — Document Processing

- [ ] PDF upload
- [ ] PDF text extraction
- [ ] Document chunking
- [ ] Requirement extraction

## Phase 2 — Understanding

- [ ] Understanding Agent
- [ ] Decomposer Agent
- [ ] Structured implementation plan

## Phase 3 — RTL Generation

- [ ] Description Agent
- [ ] Coder Agent
- [ ] Verilog/SystemVerilog generation

## Phase 4 — Verification

- [ ] Testbench generation
- [ ] RTL simulation
- [ ] Verification report
- [ ] Pass/fail detection

## Phase 5 — Reflection

- [ ] Reflection Agent
- [ ] Error analysis
- [ ] Code regeneration
- [ ] Re-verification loop

## Phase 6 — Web Application

- [ ] React dashboard
- [ ] Agent progress display
- [ ] RTL viewer
- [ ] Verification results
- [ ] Download generated files

## Phase 7 — Evaluation

- [ ] Test with multiple specifications
- [ ] Measure RTL correctness
- [ ] Measure verification success
- [ ] Measure number of correction iterations
- [ ] Measure human intervention
- [ ] Measure execution time

---

# 📊 Evaluation Metrics

The system can be evaluated using:

- RTL functional correctness
- Number of successful test cases
- Verification success rate
- Number of correction iterations
- Human interventions required
- Code generation success rate
- Processing time
- LLM/API cost

The original research paper reports up to 75% fewer human interventions compared with existing approaches. Our implementation will report its own experimental results rather than assuming or reproducing those results.

---

# 🔮 Future Enhancements

Possible future improvements:

- Multi-modal specification understanding
- Scanned PDF support
- Figure and diagram understanding
- Table extraction
- RAG over hardware documentation
- Automatic architecture diagrams
- Verilog/SystemVerilog support
- VHDL support
- Multiple LLM providers
- Advanced RTL simulation
- HLS integration
- PPA analysis
- Hardware optimization
- Human-in-the-loop approval
- Project/version history

---

# 📚 Research Reference

This project is inspired by:

**Spec2RTL-Agent: Automated Hardware Code Generation from Complex Specifications Using LLM Agent Systems**

The research system proposes three major capabilities:

1. Iterative understanding and reasoning
2. Progressive coding and prompt optimization
3. Adaptive reflection

It also uses code optimization and HLS conversion to obtain RTL.

Our project is a practical prototype inspired by these concepts. It is **not intended to be an exact reproduction of the original research implementation or its industrial tooling**.

---

# 💡 Core Idea

The entire project can be summarized as:

```text
              SPECIFICATION
                    ↓
              UNDERSTAND
                    ↓
              DECOMPOSE
                    ↓
                 PLAN
                    ↓
                 CODE
                    ↓
                VERIFY
                    ↓
             ┌──────┴──────┐
             │             │
           PASS           FAIL
             │             │
             ↓             ↓
         FINAL RTL     REFLECT
                           ↓
                         FIX
                           │
                           └──────→ VERIFY
```

> **Spec2RTL-Agent is a multi-agent AI system that converts complex hardware specifications into verified RTL through automated understanding, decomposition, code generation, verification, reflection, and correction.**
