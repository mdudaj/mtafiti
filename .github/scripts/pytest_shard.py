#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def stable_bucket(value: str, shard_count: int) -> int:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % shard_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests-root", required=True)
    parser.add_argument("--relative-to", default="")
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument("--exclude", action="append", default=[])
    args = parser.parse_args()

    tests_root = Path(args.tests_root)
    if not tests_root.exists():
        return 1
    if args.shard_index < 0 or args.shard_index >= args.shard_count:
        return 1

    relative_base = Path(args.relative_to) if args.relative_to else None
    candidates = sorted(tests_root.glob("test_*.py"))
    selected: list[str] = []
    for path in candidates:
        normalized = path.as_posix()
        if any(excluded in normalized for excluded in args.exclude):
            continue
        if stable_bucket(normalized, args.shard_count) == args.shard_index:
            if relative_base:
                selected.append(path.relative_to(relative_base).as_posix())
            else:
                selected.append(normalized)

    for item in selected:
        print(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
