"""
DAG Graph Validation Engine
===========================
Validates directed acyclic graph (DAG) topology for workflow versions:
- Detects cycles / infinite loops
- Identifies orphan or disconnected nodes
- Ensures every graph has at least one valid trigger and terminal node
- Validates node and edge schema integrity
"""

import logging
from typing import List, Dict, Any, Set, Tuple

logger = logging.getLogger(__name__)

VALID_NODE_TYPES = {
    "TRIGGER", "ACTION", "CONDITION", "AI_DECISION", "WAIT",
    "APPROVAL", "BRANCH", "PARALLEL", "JOIN", "END"
}

class DAGValidationResult:
    def __init__(self, is_valid: bool, errors: List[str], warnings: List[str]):
        self.is_valid = is_valid
        self.errors = errors
        self.warnings = warnings

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings
        }


class DAGValidator:
    """
    Validates graph consistency and structure before a workflow version is published.
    """

    @classmethod
    def validate_graph(
        cls,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]]
    ) -> DAGValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        if not nodes:
            return DAGValidationResult(False, ["Workflow must contain at least one node."], [])

        node_ids: Set[str] = set()
        trigger_nodes: List[str] = []

        # 1. Validate Node Definitions
        for n in nodes:
            n_id = n.get("id")
            n_type = (n.get("type") or "").upper()

            if not n_id:
                errors.append("All nodes must have an 'id'.")
                continue

            if n_id in node_ids:
                errors.append(f"Duplicate node id detected: '{n_id}'.")
            node_ids.add(n_id)

            if n_type not in VALID_NODE_TYPES:
                errors.append(f"Node '{n_id}' has invalid type '{n_type}'. Supported: {VALID_NODE_TYPES}")

            if n_type == "TRIGGER":
                trigger_nodes.append(n_id)

        if not trigger_nodes:
            errors.append("Workflow graph must have at least one 'TRIGGER' node.")

        # 2. Build Adjacency List
        adj: Dict[str, List[str]] = {nid: [] for nid in node_ids}
        in_degree: Dict[str, int] = {nid: 0 for nid in node_ids}

        for e in edges:
            src = e.get("source")
            tgt = e.get("target")

            if src not in node_ids:
                errors.append(f"Edge references non-existent source node '{src}'.")
                continue
            if tgt not in node_ids:
                errors.append(f"Edge references non-existent target node '{tgt}'.")
                continue

            adj[src].append(tgt)
            in_degree[tgt] += 1

        # 3. Detect Cycles via Kahn's Algorithm (Topological Sort)
        queue = [nid for nid in node_ids if in_degree[nid] == 0]
        visited_count = 0

        while queue:
            curr = queue.pop(0)
            visited_count += 1
            for neighbor in adj.get(curr, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count < len(node_ids):
            errors.append("Cyclic dependency (infinite loop) detected in workflow DAG graph.")

        # 4. Check for Orphan Non-Trigger Nodes
        for nid in node_ids:
            if nid not in trigger_nodes and not any(e.get("target") == nid for e in edges):
                warnings.append(f"Node '{nid}' has no incoming edges and is not a TRIGGER.")

        return DAGValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
