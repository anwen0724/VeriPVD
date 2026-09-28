# VeriPVD

VeriPVD is an RTL security analysis tool focused on permission-related vulnerabilities in Verilog and SystemVerilog designs. It helps identify cases where authorization, privilege, lock, or debug controls fail to protect security-sensitive state and operations, including cases where the relevant logic spans multiple modules.

## Architecture

```mermaid
flowchart LR
    RTL["RTL repository<br/>.v / .sv / .vh"]

    subgraph M1["1. RTL Structure Graph"]
        Scan["Scan and extract RTL structures"] --> Graph["RTL graph"]
    end

    subgraph M2["2. Permission Chain"]
        Groups["Build target groups"] --> Screen["LLM target screening"]
        Screen --> Focus["Mechanism focuses"]
        Focus --> Chains["Permission chain graphs"]
    end

    subgraph M3["3. Vulnerability Analysis"]
        Context["Extract source contexts"] --> Analyze["LLM chain analysis"]
        Analyze --> Findings["Findings and evidence"]
    end

    RTL --> Scan
    Graph --> Groups
    RTL --> Groups
    Graph --> Focus
    Graph --> Chains
    Chains --> Context
    RTL --> Context
```

## Structure

- `src/rtl_structure_graph/`: repository-level RTL graph.
- `src/permission_chain/`: target grouping, screening, mechanism focuses, and chain graphs.
- `src/vulnerability_analysis/`: source contexts and findings.
- `src/runtime/`: one runner per module.
- `src/scripts/`: single-input and batch command-line entry points.
- `src/llm/`, `src/prompts/`: model clients and prompts.
- `configs/config.yaml`: inputs, model, output root, and module settings.

## Run

Install dependencies with `pip install -r requirements.txt`. Set the model API key in the environment or a root-level `.env` file. Fill in `inputs[].rtl_dir` and `llm.model` in `configs/config.yaml`; relative paths are resolved from the project root. Run the modules in order:

```bash
python src/scripts/run_single.py --module rtl_structure_graph --scope example
python src/scripts/run_single.py --module permission_chain --scope example
python src/scripts/run_single.py --module vulnerability_analysis --scope example
```

For every configured input, use `python src/scripts/run_batch.py --module MODULE`, where `MODULE` is one of the three names above. Both scripts accept `--config PATH`. Results are saved under `output_dir/<scope_id>/`, with one directory per module.
