"""Command-line and interactive TUI for batch decompression."""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Iterable

SUPPORTED_EXTENSIONS = sorted(
    {ext.lower() for _, exts, _ in shutil.get_unpack_formats() for ext in exts},
    key=len,
    reverse=True,
)


@dataclass
class ExtractionPlan:
    input_dir: Path
    output_dir: Path
    recursive: bool
    on_existing: str
    dry_run: bool
    pattern: str


@dataclass
class ExtractionResult:
    extracted: int
    skipped: int
    failed: int


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Automatic batch decompression tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=dedent(
            """
            Examples:
              unzip_cx --input downloads --output extracted
              unzip_cx --input . --recursive --on-existing overwrite
            """
        ),
    )
    parser.add_argument("--input", "-i", type=Path, help="Directory containing archives")
    parser.add_argument("--output", "-o", type=Path, help="Base directory for extraction")
    parser.add_argument(
        "--recursive", "-r", action="store_true", help="Scan subdirectories"
    )
    parser.add_argument(
        "--pattern",
        default="*",
        help="Glob pattern to filter files before archive detection",
    )
    parser.add_argument(
        "--on-existing",
        choices=["ask", "skip", "overwrite", "rename"],
        default="ask",
        help="How to handle existing destination folders",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without extracting")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Force interactive prompts",
    )
    return parser


def print_header() -> None:
    print("=" * 68)
    print("UNZIP_CX — Automatic Batch Decompression")
    print("=" * 68)
    print("Supported formats:")
    print("  " + ", ".join(SUPPORTED_EXTENSIONS))
    print()


def prompt(text: str, default: str | None = None) -> str:
    if default:
        value = input(f"{text} [{default}]: ").strip()
        return value or default
    return input(f"{text}: ").strip()


def prompt_yes_no(text: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        value = input(f"{text} ({suffix}): ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Please enter y or n.")


def prompt_choice(text: str, choices: Iterable[str], default: str) -> str:
    choice_list = "/".join(choices)
    while True:
        value = prompt(f"{text} ({choice_list})", default)
        if value in choices:
            return value
        print(f"Please choose one of: {', '.join(choices)}")


def normalize_path(value: str, fallback: Path) -> Path:
    cleaned = value.strip()
    if not cleaned:
        return fallback
    return Path(cleaned).expanduser().resolve()


def archive_stem(path: Path) -> str:
    name = path.name
    lower_name = name.lower()
    for ext in SUPPORTED_EXTENSIONS:
        if lower_name.endswith(ext):
            return name[: -len(ext)]
    return path.stem


def collect_archives(plan: ExtractionPlan) -> list[Path]:
    glob = plan.input_dir.rglob if plan.recursive else plan.input_dir.glob
    candidates = [p for p in glob(plan.pattern) if p.is_file()]
    archives: list[Path] = []
    for path in candidates:
        lower_name = path.name.lower()
        if any(lower_name.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
            archives.append(path)
    return sorted(archives)


def ensure_destination(dest: Path, on_existing: str) -> Path | None:
    if not dest.exists():
        dest.mkdir(parents=True, exist_ok=True)
        return dest

    if on_existing == "skip":
        return None

    if on_existing == "overwrite":
        for child in dest.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        return dest

    if on_existing == "rename":
        counter = 1
        while True:
            candidate = dest.parent / f"{dest.name}_{counter}"
            if not candidate.exists():
                candidate.mkdir(parents=True, exist_ok=True)
                return candidate
            counter += 1

    return None


def handle_existing_dest(
    dest: Path, on_existing: str
) -> tuple[Path | None, str]:
    if not dest.exists() or on_existing != "ask":
        return ensure_destination(dest, on_existing), on_existing

    print(f"Destination already exists: {dest}")
    choice = prompt_choice(
        "Choose action",
        ["skip", "overwrite", "rename", "skip-all", "overwrite-all", "rename-all"],
        "skip",
    )
    if choice.endswith("-all"):
        resolved = choice.replace("-all", "")
        return ensure_destination(dest, resolved), resolved
    return ensure_destination(dest, choice), on_existing


def extract_archives(plan: ExtractionPlan, archives: list[Path]) -> ExtractionResult:
    extracted = skipped = failed = 0
    on_existing = plan.on_existing

    for idx, archive in enumerate(archives, start=1):
        stem = archive_stem(archive)
        dest = plan.output_dir / stem
        resolved_dest, on_existing = handle_existing_dest(dest, on_existing)
        if resolved_dest is None:
            skipped += 1
            print(f"[{idx}/{len(archives)}] Skipped {archive.name}")
            continue

        if plan.dry_run:
            extracted += 1
            print(f"[{idx}/{len(archives)}] (dry-run) {archive.name} -> {resolved_dest}")
            continue

        try:
            shutil.unpack_archive(str(archive), str(resolved_dest))
            extracted += 1
            print(f"[{idx}/{len(archives)}] Extracted {archive.name}")
        except (shutil.ReadError, ValueError, OSError) as exc:
            failed += 1
            print(f"[{idx}/{len(archives)}] Failed {archive.name}: {exc}")

    return ExtractionResult(extracted=extracted, skipped=skipped, failed=failed)


def interactive_plan() -> ExtractionPlan:
    print_header()
    current = Path.cwd()
    input_dir = normalize_path(prompt("Input folder", str(current)), current)
    output_default = input_dir / "extracted"
    output_dir = normalize_path(prompt("Output folder", str(output_default)), output_default)
    recursive = prompt_yes_no("Scan subfolders", default=False)
    pattern = prompt("File glob pattern", "*")
    on_existing = prompt_choice(
        "If destination exists",
        ["ask", "skip", "overwrite", "rename"],
        "ask",
    )
    dry_run = prompt_yes_no("Dry run (preview only)", default=False)

    print("\nReview configuration:")
    print(f"  Input:       {input_dir}")
    print(f"  Output:      {output_dir}")
    print(f"  Recursive:   {recursive}")
    print(f"  Pattern:     {pattern}")
    print(f"  On existing: {on_existing}")
    print(f"  Dry run:     {dry_run}")
    if not prompt_yes_no("Proceed", default=True):
        print("Cancelled.")
        sys.exit(0)

    return ExtractionPlan(
        input_dir=input_dir,
        output_dir=output_dir,
        recursive=recursive,
        on_existing=on_existing,
        dry_run=dry_run,
        pattern=pattern,
    )


def plan_from_args(args: argparse.Namespace) -> ExtractionPlan:
    input_dir = args.input or Path.cwd()
    output_dir = args.output or (input_dir / "extracted")
    return ExtractionPlan(
        input_dir=input_dir.expanduser().resolve(),
        output_dir=output_dir.expanduser().resolve(),
        recursive=args.recursive,
        on_existing=args.on_existing,
        dry_run=args.dry_run,
        pattern=args.pattern,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    interactive = args.interactive or not (args.input or args.output)
    plan = interactive_plan() if interactive else plan_from_args(args)

    if not plan.input_dir.exists():
        print(f"Input directory not found: {plan.input_dir}")
        return 2

    archives = collect_archives(plan)
    if not archives:
        print("No supported archives found.")
        return 0

    plan.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Found {len(archives)} archives. Starting extraction...\n")
    result = extract_archives(plan, archives)

    print("\nSummary:")
    print(f"  Extracted: {result.extracted}")
    print(f"  Skipped:   {result.skipped}")
    print(f"  Failed:    {result.failed}")
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
