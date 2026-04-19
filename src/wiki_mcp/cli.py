from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TextIO

from wiki_mcp.demo import DEFAULT_DEMO_SEED_PATH
from wiki_mcp.runtime_protocol import (
    list_tools_payload,
    run_stdio_runtime,
    show_tool_payload,
)
from wiki_mcp.runtime_setup import (
    DEFAULT_POSTGRES_BOOTSTRAP_PATH,
    apply_postgres_bootstrap,
    run_mvp_seed_flow,
)
from wiki_mcp.server import StrataWikiServer, build_server
from wiki_mcp.worker import run_worker_once


ServerFactory = Callable[..., StrataWikiServer]
DatabaseBootstrapper = Callable[..., dict[str, object]]
MvpSeedRunner = Callable[..., dict[str, object]]
WorkerRunner = Callable[..., dict[str, object]]


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stratawiki",
        description="Local CLI for directly invoking the current StrataWiki tool surface.",
    )
    parser.add_argument(
        "--database-url",
        help="Optional PostgreSQL connection string. Defaults to DATABASE_URL or the local default.",
    )
    parser.add_argument(
        "--render-root",
        default="data",
        help="Render root passed into the StrataWiki bootstrap.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run against the local in-memory demo runtime instead of Postgres.",
    )
    parser.add_argument(
        "--seed-path",
        default=str(DEFAULT_DEMO_SEED_PATH),
        help="Seed path used by demo mode, demo-mvp, and seed-mvp.",
    )
    parser.add_argument(
        "--domain-pack-path",
        action="append",
        default=[],
        help="Path to a Domain Pack artifact to load during bootstrap. Repeat to load multiple packs.",
    )
    parser.add_argument(
        "--activate-domain-pack",
        action="append",
        default=[],
        help="Explicit active domain pack mapping in domain=version form. Repeat for multiple domains.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_tools = subparsers.add_parser("list-tools", help="List the currently registered tools.")
    list_tools.add_argument("--group", help="Optional tool group filter.")
    list_tools.add_argument(
        "--schemas",
        action="store_true",
        help="Emit the full exported schemas instead of the compact tool list.",
    )

    show_tool = subparsers.add_parser("show-tool", help="Show one exported tool schema.")
    show_tool.add_argument("name", help="Tool name to inspect.")

    call_tool = subparsers.add_parser("call", help="Call one tool with JSON arguments.")
    call_tool.add_argument("name", help="Tool name to invoke.")
    call_tool.add_argument("--args", default="{}", help="Inline JSON object of tool arguments.")
    call_tool.add_argument("--args-file", help="Path to a JSON file containing tool arguments.")
    call_tool.add_argument(
        "--envelope",
        action="store_true",
        help="Wrap the response in the registry ok/error envelope.",
    )

    init_db = subparsers.add_parser(
        "init-db",
        help="Apply the checked-in Postgres bootstrap SQL to the configured database.",
    )
    init_db.add_argument(
        "--bootstrap-sql",
        default=str(DEFAULT_POSTGRES_BOOTSTRAP_PATH),
        help="Path to the SQL file used to initialize the local Postgres schema.",
    )

    subparsers.add_parser(
        "seed-mvp",
        help="Load the sample MVP seed into the current runtime using the real storage path.",
    )
    subparsers.add_parser("demo-mvp", help="Run the Week 1 MVP flow locally with the demo seed in one process.")
    subparsers.add_parser(
        "serve",
        help="Start the long-lived stdio runtime for external clients.",
    )
    worker = subparsers.add_parser(
        "worker",
        help="Claim and process queued background jobs once.",
    )
    worker.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum queued jobs to claim in one run.",
    )
    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    server_factory: ServerFactory = build_server,
    database_bootstrapper: DatabaseBootstrapper = apply_postgres_bootstrap,
    mvp_seed_runner: MvpSeedRunner = run_mvp_seed_flow,
    worker_runner: WorkerRunner = run_worker_once,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    resolved_stdin = stdin or sys.stdin
    resolved_stdout = stdout or sys.stdout
    resolved_stderr = stderr or sys.stderr

    try:
        tool_arguments = _load_tool_arguments(args)
        active_domain_pack_versions = _parse_active_domain_pack_versions(
            args.activate_domain_pack
        )
    except ValueError as exc:
        parser.exit(2, f"{parser.prog}: error: {exc}\n")
        return 2

    if args.command == "seed-mvp" and args.demo:
        parser.exit(2, f"{parser.prog}: error: seed-mvp cannot be combined with --demo; use demo-mvp instead.\n")
        return 2
    if args.command == "init-db" and args.demo:
        parser.exit(2, f"{parser.prog}: error: init-db targets the Postgres runtime and cannot be combined with --demo.\n")
        return 2

    if args.command == "init-db":
        try:
            result = database_bootstrapper(
                database_url=args.database_url,
                bootstrap_sql_path=args.bootstrap_sql,
            )
        except Exception as exc:
            resolved_stderr.write(json.dumps({"ok": False, "error": exc.__class__.__name__, "message": str(exc)}) + "\n")
            return 1
        _write_json(resolved_stdout, result)
        return 0

    server = server_factory(
        database_url=args.database_url,
        render_root=Path(args.render_root),
        demo_mode=args.demo,
        seed_path=args.seed_path,
        domain_pack_paths=[Path(path) for path in args.domain_pack_path],
        active_domain_pack_versions=active_domain_pack_versions,
    )
    try:
        result: object
        if args.command == "list-tools":
            result = list_tools_payload(server, group=args.group, full_schemas=args.schemas)
        elif args.command == "show-tool":
            result = show_tool_payload(server, args.name)
        elif args.command == "call":
            result = server.call_tool_with_envelope(args.name, tool_arguments) if args.envelope else server.call_tool(args.name, tool_arguments)
        elif args.command == "seed-mvp":
            result = mvp_seed_runner(server, seed_path=args.seed_path)
        elif args.command == "demo-mvp":
            result = mvp_seed_runner(server, seed_path=args.seed_path)
        elif args.command == "serve":
            return run_stdio_runtime(server, stdin=resolved_stdin, stdout=resolved_stdout)
        elif args.command == "worker":
            result = worker_runner(server, limit=args.limit)
        else:
            raise ValueError(f"Unsupported command: {args.command}")
    except KeyError as exc:
        resolved_stderr.write(json.dumps({"ok": False, "error": str(exc)}) + "\n")
        return 1
    except Exception as exc:
        resolved_stderr.write(json.dumps({"ok": False, "error": exc.__class__.__name__, "message": str(exc)}) + "\n")
        return 1
    finally:
        server.close()

    _write_json(resolved_stdout, result)
    return 0


def main() -> None:
    raise SystemExit(run_cli())


def _load_tool_arguments(args: argparse.Namespace) -> dict[str, object] | None:
    if args.command != "call":
        return None
    if args.args_file:
        return _load_json_file(args.args_file)
    return _load_json_text(args.args)


def _load_json_file(path_text: str) -> dict[str, object]:
    try:
        raw_text = Path(path_text).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Failed to read JSON file {path_text!r}: {exc}") from exc
    return _parse_json_object(raw_text, source=path_text)


def _load_json_text(raw_text: str) -> dict[str, object]:
    return _parse_json_object(raw_text, source="--args")


def _parse_json_object(raw_text: str, *, source: str) -> dict[str, object]:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON from {source}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON arguments from {source} must decode to an object.")
    return payload
def _write_json(stream: TextIO, payload: object) -> None:
    json.dump(payload, stream, indent=2, sort_keys=True)
    stream.write("\n")


def _parse_active_domain_pack_versions(raw_values: Sequence[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in raw_values:
        if "=" not in item:
            raise ValueError(
                "--activate-domain-pack entries must use domain=version format."
            )
        domain, pack_version = item.split("=", 1)
        normalized_domain = domain.strip()
        normalized_version = pack_version.strip()
        if not normalized_domain or not normalized_version:
            raise ValueError(
                "--activate-domain-pack entries must use domain=version format."
            )
        mapping[normalized_domain] = normalized_version
    return mapping


if __name__ == "__main__":
    main()
