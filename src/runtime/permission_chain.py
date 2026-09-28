from __future__ import annotations

from typing import Any

from llm.langchain_models import LangChainModelConfig, create_chat_model
from permission_chain.chain_graphs.config import PermissionChainGraphConfig
from permission_chain.chain_graphs.pipeline import build_permission_chain_graphs
from permission_chain.mechanism_focuses.pipeline import build_permission_mechanism_focuses
from permission_chain.target_groups import PermissionTargetGroupConfig, build_permission_target_groups
from permission_chain.target_screening import PermissionTargetScreeningConfig, run_permission_target_screening
from runtime import ensure_model_output, model_settings, scope_paths


def run(config: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
    repo, output = scope_paths(config, scope)
    graph_path = output / "rtl_structure_graph" / "rtl_structure_graph.json"
    if not graph_path.is_file():
        raise FileNotFoundError(f"Run rtl_structure_graph first: {graph_path}")
    module = config.get("permission_chain", {})
    screening = module.get("target_screening", {})
    model = model_settings(config)
    module_output = output / "permission_chain"
    ensure_model_output(module_output, model, "screening_batch_checkpoint.jsonl")
    groups = build_permission_target_groups(
        graph_path,
        repo,
        module_output,
        PermissionTargetGroupConfig(**module.get("target_groups", {})),
    )
    chat_model = create_chat_model(
        LangChainModelConfig(
            provider=model["provider"],
            model=model["model"],
            temperature=float(screening.get("temperature", 0.2)),
            max_tokens=int(screening.get("max_tokens", 8192)),
            request_timeout=screening.get("request_timeout", 600),
        )
    )
    screening_fields = PermissionTargetScreeningConfig.__dataclass_fields__
    screening_config = PermissionTargetScreeningConfig(
        **{key: value for key, value in screening.items() if key in screening_fields}
    )
    screened = run_permission_target_screening(
        groups_path=groups["groups_path"],
        contexts_path=groups["contexts_path"],
        output_dir=module_output,
        chat_model=chat_model,
        provider=model["provider"],
        model=model["model"],
        model_id=str(model["model"]),
        config=screening_config,
    )
    focuses = build_permission_mechanism_focuses(
        graph_path,
        module_output / "retained_permission_target_groups.json",
        module_output,
    )
    chains = build_permission_chain_graphs(
        graph_path,
        module_output / "permission_mechanism_focuses.json",
        repo,
        module_output,
        PermissionChainGraphConfig(**module.get("chain_graphs", {})),
    )
    return {
        "scope_id": scope["scope_id"],
        "target_groups": groups,
        "target_screening": screened,
        "mechanism_focuses": focuses,
        "chain_graphs": chains,
    }
