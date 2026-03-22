"""
StableArch Council - Entry Point
==================================
One-click launch for the multi-agent ARB package generation system.
Context: M&T Bank Cari deposit platform on the Cari Network / ZKsync Prividium.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
DDA <-> CDA flow: fiat in DDA triggers CDA mint; CDA burn triggers fiat back to DDA.

Usage:
    python run.py
    python run.py --topic "Fireblocks custody integration review for Cari deposits (CDA)"
    python run.py --output docs/arb_package.md
    python run.py --quiet
"""

from __future__ import annotations

import argparse
import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "StableArch Council -- Multi-Agent ARB Package Generator\n"
            "M&T Bank | Cari Network | ZKsync Prividium"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help=(
            "Optional review topic or scenario. "
            'Example: "Fireblocks custody integration review for Cari deposits (CDA)"'
        ),
    )
    parser.add_argument(
        "--output",
        type=str,
        default="docs/arb_package_output.md",
        help="Output file path for the ARB package (default: docs/arb_package_output.md)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress verbose agent output",
    )
    parser.add_argument(
        "--guardrails-only",
        action="store_true",
        help="Run only the regulatory guardrail checks against an existing document",
    )
    parser.add_argument(
        "--input-file",
        type=str,
        default=None,
        help="Input file for --guardrails-only mode",
    )

    args = parser.parse_args()

    if args.guardrails_only:
        _run_guardrails_only(args.input_file)
        return

    # Import here so missing deps are caught with a helpful message
    try:
        from crew import run_council
    except ImportError as e:
        print(f"Error: Missing dependency -- {e}")
        print("Run: pip install -r requirements.txt")
        sys.exit(1)

    print("=" * 70)
    print("STABLEARCH COUNCIL")
    print("Multi-Agent Architecture Review Board Package Generator")
    print("M&T Bank | Cari Network | ZKsync Prividium")
    print("=" * 70)

    if args.topic:
        print(f"\nReview Topic: {args.topic}")
    print(f"Output File:  {args.output}")
    print(f"Verbose:      {not args.quiet}")
    print("-" * 70)

    result = run_council(
        topic=args.topic,
        verbose=not args.quiet,
        output_file=args.output,
    )

    print("\n" + "=" * 70)
    print("ARB PACKAGE GENERATION COMPLETE")
    print(f"Output saved to: {args.output}")
    print("=" * 70)


def _run_guardrails_only(input_file: str | None) -> None:
    """Run regulatory guardrail checks against an existing document."""
    from guardrails import run_guardrail_checks

    if not input_file:
        print("Error: --input-file required with --guardrails-only")
        sys.exit(1)

    if not os.path.exists(input_file):
        print(f"Error: File not found: {input_file}")
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8") as f:
        document = f.read()

    report = run_guardrail_checks(document)
    print(report.summary())

    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
