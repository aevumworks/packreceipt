"""python -m packreceipt (also used by the portable zipapp)."""

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .core import ReceiptError, compare, load_manifest, scan
from .report import render


def write_text(path: Path, content: str, force: bool) -> None:
    # Exclusive create prevents accidental replacement; --force is explicit.
    with path.open("w" if force else "x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def check_outputs(paths: list[Path], inputs: list[Path], root: Path | None, force: bool) -> None:
    resolved = [path.resolve() for path in paths]
    if len(set(resolved)) != len(resolved):
        raise ReceiptError("Output paths must be different.")
    for path, target in zip(paths, resolved):
        if target in {item.resolve() for item in inputs}:
            raise ReceiptError("An output must not replace an input manifest.")
        if root is not None and target.is_relative_to(root.resolve()):
            raise ReceiptError("Save outputs outside the scanned folder.")
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ReceiptError("An output must be a regular file path.")
        if path.exists() and not force:
            raise ReceiptError(f"Output exists: {path}. Choose a new path or use --force.")
        if not path.parent.is_dir():
            raise ReceiptError(f"Output parent directory does not exist: {path.parent}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local delivery-folder receipts and readable comparison reports.")
    parser.add_argument("--version", action="version", version=f"PackReceipt {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    scan_parser = sub.add_parser("scan", help="Hash a folder into a SHA-256 manifest.")
    scan_parser.add_argument("folder", type=Path)
    scan_parser.add_argument("--out", required=True, type=Path)
    scan_parser.add_argument("--label", help="Public folder label (defaults to folder name).")
    scan_parser.add_argument("--force", action="store_true")
    compare_parser = sub.add_parser("compare", help="Compare two saved manifests.")
    compare_parser.add_argument("before", type=Path)
    compare_parser.add_argument("after", type=Path)
    verify_parser = sub.add_parser("verify", help="Hash a received folder and compare with a saved receipt.")
    verify_parser.add_argument("manifest", type=Path)
    verify_parser.add_argument("folder", type=Path)
    for command in (compare_parser, verify_parser):
        command.add_argument("--html", required=True, type=Path)
        command.add_argument("--json", type=Path, dest="json_out")
        command.add_argument("--lang", choices=("en", "zh"), default="en")
        command.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "scan":
            if args.label is not None and not args.label.strip():
                raise ReceiptError("Label must not be empty.")
            check_outputs([args.out], [], args.folder, args.force)
            manifest = scan(args.folder, args.label)
            write_text(args.out, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", args.force)
            print(f"Scanned {len(manifest['files'])} files -> {args.out}")
            return 0
        outputs = [args.html] + ([args.json_out] if args.json_out else [])
        inputs = [args.before, args.after] if args.command == "compare" else [args.manifest]
        check_outputs(outputs, inputs, args.folder if args.command == "verify" else None, args.force)
        before = load_manifest(inputs[0])
        after = load_manifest(args.after) if args.command == "compare" else scan(args.folder)
        result = compare(before, after, mode=args.command)
        # Render before creating any output so a rendering error cannot leave a partial report.
        html = render(result, args.lang)
        write_text(args.html, html, args.force)
        if args.json_out:
            write_text(args.json_out, json.dumps(result, ensure_ascii=False, indent=2) + "\n", args.force)
        print(" | ".join(f"{key}: {value}" for key, value in result["counts"].items()))
        print(f"HTML report -> {args.html}")
        return 0 if result["matches"] else 1
    except (ReceiptError, OSError, UnicodeError) as error:
        print(f"PackReceipt: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
