def module_id(module_name: str) -> str:
    return f"module:{module_name}"


def instance_id(parent_module: str, instance_name: str) -> str:
    return f"instance:{parent_module}.{instance_name}"


def signal_id(module_name: str, signal_name: str) -> str:
    return f"signal:{module_name}.{signal_name}"


def stmt_id(module_name: str, line_start: int, kind: str) -> str:
    return f"stmt:{module_name}:{line_start}:{kind}"


def edge_id(edge_type: str, number: int) -> str:
    return f"edge:{edge_type}:{number}"
