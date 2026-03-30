#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from knowledge_graph_lib import build_argument_parser, query_nodes, summarize_graph


def main() -> int:
    parser = build_argument_parser()
    parser.description = (
        "Query generated knowledge graph data without requiring external dependencies."
    )
    parser.add_argument(
        "--type",
        dest="node_type",
        help="Filter by node type, e.g. Skill or UIComponent.",
    )
    parser.add_argument("--text", help="Full-text search across node metadata.")
    parser.add_argument(
        "--relationship",
        help="Filter nodes that have an outgoing relationship of this type.",
    )
    parser.add_argument(
        "--target",
        help="Target node id for relationship filtering, e.g. framework:django_material.",
    )
    parser.add_argument(
        "--report",
        choices=["layers", "dependencies", "behavioral"],
        help="Return a graph summary instead of raw node matches.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if args.report:
        print(json.dumps(summarize_graph(root, args.report), indent=2))
        return 0

    results = query_nodes(
        root,
        node_type=args.node_type,
        text=args.text,
        relationship=args.relationship,
        target=args.target,
    )
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
