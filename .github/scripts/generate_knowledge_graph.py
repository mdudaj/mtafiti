#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from knowledge_graph_lib import build_argument_parser, build_bundle, check_bundle, write_bundle


def main() -> int:
    parser = build_argument_parser()
    parser.description = "Generate or verify repository knowledge graph artifacts."
    parser.add_argument("--check", action="store_true", help="Fail if generated outputs differ from committed files.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    bundle = build_bundle(root)

    if args.check:
        drifted = check_bundle(root, bundle)
        if drifted:
            print("Knowledge graph artifacts are out of date:")
            for path in drifted:
                print(f"- {path}")
            return 1
        print("Knowledge graph artifacts are up to date.")
        return 0

    write_bundle(root, bundle)
    print("Knowledge graph artifacts generated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
