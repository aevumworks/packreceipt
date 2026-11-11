"""Build a dependency-free zipapp and a source/example bundle."""

import hashlib
from pathlib import Path
import shutil
import tempfile
import zipapp
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"


def main():
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    app = dist / f"packreceipt-{VERSION}.pyz"
    with tempfile.TemporaryDirectory(prefix="packreceipt-build-") as temp:
        stage = Path(temp)
        shutil.copytree(ROOT / "packreceipt", stage / "packreceipt", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (stage / "__main__.py").write_text("from packreceipt.__main__ import main\nraise SystemExit(main())\n", encoding="utf-8")
        zipapp.create_archive(stage, target=app, compressed=True)
    bundle = dist / f"packreceipt-{VERSION}.zip"
    included = [ROOT / "README.md", ROOT / "README.zh-CN.md", ROOT / "LICENSE", ROOT / "CHANGELOG.md"]
    for folder in ("packreceipt", "scripts", "tests", "examples", "docs"):
        included.extend(path for path in (ROOT / folder).rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc")
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(app, f"packreceipt-{VERSION}/{app.name}")
        for path in sorted(included):
            archive.write(path, f"packreceipt-{VERSION}/{path.relative_to(ROOT).as_posix()}")
    checksums = "\n".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in (app, bundle)) + "\n"
    (dist / "SHA256SUMS.txt").write_text(checksums, encoding="utf-8")
    print(checksums, end="")


if __name__ == "__main__":
    main()
