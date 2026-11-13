"""Product inventory, operation discovery, and explicit local qualification probes."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from mosaic_mmc import canonical, MMCError
from .integrations import probe_cmba_agent, probe_semcrys, probe_ucm, verify_cmba_wheel
from .disposable import run_disposable_migration
from .product import capabilities, integration_status
from .surface import operation_catalogue
from .protocol import dispatch, exported_schemas, protocol_manifest, refusal as agent_refusal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mmc-product", description="MMC current product and integration surface")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("capabilities")
    sub.add_parser("operations")
    sub.add_parser("protocol")
    schema = sub.add_parser("schema"); schema.add_argument("which", choices=("request", "response", "all"))
    request = sub.add_parser("request"); request.add_argument("path")
    sub.add_parser("integrations")
    cmba = sub.add_parser("verify-cmba-wheel"); cmba.add_argument("wheel")
    cmba_run = sub.add_parser("probe-cmba"); cmba_run.add_argument("wheel")
    ucm = sub.add_parser("probe-ucm"); ucm.add_argument("source"); ucm.add_argument("--contract", required=True)
    semcrys = sub.add_parser("probe-semcrys"); semcrys.add_argument("source")
    sub.add_parser("verify-disposable-migration")
    sub.add_parser("verify-target-migration")
    sub.add_parser("transport")
    args = parser.parse_args(argv)
    try:
        if args.command == "capabilities": result = capabilities()
        elif args.command == "operations": result = protocol_manifest()
        elif args.command == "protocol": result = protocol_manifest()
        elif args.command == "schema":
            schemas = exported_schemas()
            result = schemas if args.which == "all" else schemas[args.which]
        elif args.command == "request":
            from mosaic_mmc.cli import read_local
            raw = read_local(args.path, limit=8 * 1024 * 1024)
            if len(raw) > 8 * 1024 * 1024: raise MMCError("MMC_T7_AGENT_REQUEST_LIMIT")
            from mosaic_mmc import decode
            result = dispatch(decode(raw, limit=8 * 1024 * 1024))
            sys.stdout.buffer.write(canonical(result) + b"\n")
            return 0 if result["ok"] else 2
        elif args.command == "integrations": result = integration_status()
        elif args.command == "verify-cmba-wheel": result = verify_cmba_wheel(args.wheel)
        elif args.command == "probe-cmba": result = probe_cmba_agent(args.wheel)
        elif args.command == "probe-ucm": result = probe_ucm(args.source, args.contract)
        elif args.command == "probe-semcrys": result = probe_semcrys(args.source)
        elif args.command == "transport":
            from .transport import transport_manifest
            result = transport_manifest()
        elif args.command == "verify-target-migration":
            from .target_qualification import run_target_qualification
            result = run_target_qualification()
        else: result = run_disposable_migration()
        sys.stdout.buffer.write(canonical(result) + b"\n")
        return 0
    except (OSError, RuntimeError) as error:
        refusal = MMCError("MMC_T7_LOCAL_PROBE_FAILED", detail=type(error).__name__)
        body = agent_refusal(refusal) if getattr(args, "command", None) == "request" else {"schema": "mmc.product-refusal.v1", "error": refusal.record(), "authority_effect": "NONE"}
        sys.stdout.buffer.write(canonical(body) + b"\n")
        return 2
    except MMCError as error:
        body = agent_refusal(error) if getattr(args, "command", None) == "request" else {"schema": "mmc.product-refusal.v1", "error": error.record(), "authority_effect": "NONE"}
        sys.stdout.buffer.write(canonical(body) + b"\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
