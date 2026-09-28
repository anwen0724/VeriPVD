from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = SRC_ROOT.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from llm.langchain_models import LangChainModelConfig, create_chat_model
from vulnerability_analysis.chain_context_analysis.config import ChainContextAnalysisConfig
from vulnerability_analysis.chain_context_analysis.pipeline import run_chain_context_analysis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Retry only failed Module-3 chain analyses into an independent audit directory.")
    parser.add_argument("--contexts", required=True)
    parser.add_argument("--diagnostics", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=32768)
    parser.add_argument("--request-timeout", type=float, default=600)
    parser.add_argument("--max-attempts", type=int, default=2)
    args = parser.parse_args(argv)

    contexts_path = _resolve(args.contexts)
    diagnostics_path = _resolve(args.diagnostics)
    output_dir = _resolve(args.output_dir)
    contexts_doc = json.loads(contexts_path.read_text(encoding="utf-8"))
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    failed_ids = {
        str(item.get("chain_id", ""))
        for item in diagnostics.get("per_chain", [])
        if item.get("status") == "llm_failed"
    }
    retry_chains = [chain for chain in contexts_doc.get("chains", []) if str(chain.get("chain_id", "")) in failed_ids]
    if not retry_chains:
        print("[retry-chain-context] no failed chains", flush=True)
        return 0
    retry_doc = {
        "graph_id": contexts_doc.get("graph_id", ""),
        "schema_version": contexts_doc.get("schema_version", "0.1"),
        "chains": retry_chains,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    retry_contexts = output_dir / "retry_permission_chain_contexts.json"
    retry_contexts.write_text(json.dumps(retry_doc, ensure_ascii=False, indent=2), encoding="utf-8")

    chat_model = create_chat_model(
        LangChainModelConfig(
            provider=args.provider,
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            request_timeout=args.request_timeout,
        )
    )
    summary = run_chain_context_analysis(
        retry_contexts,
        _resolve(args.repo_root),
        output_dir,
        chat_model,
        ChainContextAnalysisConfig(max_llm_attempts=args.max_attempts),
    )
    (output_dir / "retry_metadata.json").write_text(
        json.dumps(
            {
                "source_contexts": str(contexts_path),
                "source_diagnostics": str(diagnostics_path),
                "failed_chain_ids": sorted(failed_ids),
                "provider": args.provider,
                "model": args.model,
                "max_attempts": args.max_attempts,
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[retry-chain-context] chains={len(retry_chains)} output={output_dir}", flush=True)
    return 0


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


if __name__ == "__main__":
    raise SystemExit(main())
