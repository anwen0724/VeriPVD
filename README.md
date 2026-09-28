# VeriPVD

VeriPVD analyzes permission-related vulnerabilities in RTL source code. It builds a repository-level RTL graph, selects permission targets and chains, then extracts source context and analyzes it with a configured LLM.

## Structure

- `src/rtl_structure_graph/`: repository-level RTL graph.
- `src/permission_chain/`: target grouping, LLM screening, mechanism focuses, and chain graphs.
- `src/vulnerability_analysis/`: source contexts and finding analysis.
- `src/prompts/`: LLM prompts.
- `src/llm/`, `src/runtime/`, `src/scripts/`: model clients, run orchestration, and commands.
- `configs/`: YAML model and batch configuration.

## Usage

Install dependencies with `pip install -r requirements.txt`. Set the required API key in the environment or in a root-level `.env` file. Configure input and output paths in the YAML files for your RTL repository.

```bash
python src/scripts/build/build_rtl_structure_graph.py --repo <rtl-repository> --out <graph-output>
python src/scripts/run/run_permission_target_screening_batch.py --config configs/module2_v3_target_screening_deepseek_pilot.yaml
python src/scripts/run/run_ours_chain_context_batch.py --config configs/ours_chain_context_deepseek.yaml
```
