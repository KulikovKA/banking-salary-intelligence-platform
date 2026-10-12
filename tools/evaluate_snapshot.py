"""Offline evaluation and private inventory; no ingestion, publication or provider calls."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from evaluation.audit import write_private_audit  # noqa: E402
from evaluation.diagnostics import diagnose_research  # noqa: E402
from evaluation.engine import run_comparison  # noqa: E402
from evaluation.io import load_gold, load_observations, write_json  # noqa: E402
from evaluation.metrics import evaluate, markdown  # noqa: E402
from evaluation.schema import ObservedComparison  # noqa: E402

from app.parsing.runner import BoundedParseError  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit", help="private paths/metadata; output MUST remain outside Git")
    audit.add_argument("--env-file", type=Path, required=True)
    audit.add_argument("--root", type=Path, action="append", required=True)
    audit.add_argument("--output", type=Path, required=True)
    diagnostic = sub.add_parser("diagnose", help="admitted local research smoke; private output")
    diagnostic.add_argument("--file", type=Path, required=True)
    diagnostic.add_argument(
        "--bank", choices=("sber", "vtb", "alfa", "kuban_credit"), required=True
    )
    diagnostic.add_argument("--private-output", type=Path, required=True)
    diagnostic.add_argument("--allow-local-research-diagnostic", action="store_true")
    for name in ("run", "compare"):
        run = sub.add_parser(name)
        run.add_argument("--gold", type=Path, required=True)
        run.add_argument("--gold-sha256", required=True)
        run.add_argument("--observations", type=Path, required=True)
        run.add_argument("--output", type=Path, required=True)
        run.add_argument(
            "--allow-real-local-output",
            action="store_true",
            help="only after storage/reuse admission; output stays private",
        )
    args = parser.parse_args(argv)
    try:
        if args.command == "diagnose":
            summary = diagnose_research(
                args.file,
                args.bank,
                args.private_output,
                admitted=args.allow_local_research_diagnostic,
            )
            print(json.dumps(summary, sort_keys=True))
            return 0 if summary["parse_status"] == "ok" else 1
        if args.command == "audit":
            # Require an ignored local directory; never write private reports into owned PR paths.
            if ".local" not in args.output.resolve().parts:
                raise ValueError("PRIVATE_AUDIT_REQUIRES_LOCAL_DIRECTORY")
            report = write_private_audit(args.env_file, args.root, args.output)
            print(f"Inventory: {len(report['files'])} files; private audit saved.")
            return 0
        gold, digest = load_gold(args.gold, args.gold_sha256)
        observed = load_observations(args.observations)
        # Validate binding before invoking the comparison service or writing anything.
        evaluate(gold, observed, digest)
        if gold.corpus_kind == "real" and (
            not args.allow_real_local_output or ".local" not in args.output.resolve().parts
        ):
            raise ValueError("REAL_OUTPUT_REQUIRES_ADMISSION_AND_PRIVATE_LOCAL_DIRECTORY")
        if args.command == "compare":
            if observed.mode != "synthetic_engine":
                raise ValueError("COMPARE_REQUIRES_SYNTHETIC_ENGINE_MODE")
            observed = observed.model_copy(
                update={
                    "comparisons": tuple(
                        ObservedComparison(id=case.id, result=run_comparison(gold, case))
                        for case in gold.comparisons
                    )
                }
            )
        result = evaluate(gold, observed, digest)
        result["observations_sha256"] = hashlib.sha256(args.observations.read_bytes()).hexdigest()
        result["effective_observations_sha256"] = hashlib.sha256(
            json.dumps(
                observed.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        write_json(args.output.with_suffix(".json"), result)
        args.output.with_suffix(".md").write_text(markdown(result), encoding="utf-8")
        print(f"Scored {gold.corpus_kind}: {len(result['missing'])} missing observations.")
        return int(
            bool(result["missing"])
            or any(metric["status"] == "FAIL" for metric in result["metrics"].values())
        )
    except (OSError, ValueError, ValidationError, BoundedParseError) as exc:
        # Do not print validation payloads, private contents or connection strings.
        code = str(exc) if type(exc) is ValueError and str(exc).isupper() else type(exc).__name__
        print(f"Evaluation refused: {code}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
