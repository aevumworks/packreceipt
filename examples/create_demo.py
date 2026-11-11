"""Create original, synthetic exhibition-design deliveries and their real reports."""

import argparse
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from packreceipt.__main__ import main


def write(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")


def poster(color, date):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="720" height="960" viewBox="0 0 720 960">
<rect width="720" height="960" fill="#eaf0f4"/><path d="M90 490Q360 110 630 490V720H90Z" fill="{color}"/>
<circle cx="360" cy="350" r="130" fill="#eaf0f4"/><path d="M90 720H630" stroke="#172d3d" stroke-width="3"/>
<g fill="#172d3d" font-family="sans-serif"><text x="80" y="100" font-size="22">FIELD NOTES / EXHIBITION</text>
<text x="80" y="805" font-size="48">Window Studies</text><text x="80" y="858" font-size="25">{date}</text>
<text x="80" y="910" font-size="16">PackReceipt original demo artwork</text></g></svg>'''


def run(args, expected=0):
    result = main([str(x) for x in args])
    if result != expected:
        raise RuntimeError(f"Expected exit {expected}, got {result}: {args}")


def create(output: Path):
    output.mkdir(parents=True, exist_ok=False)
    first = output / "展览视觉-v1"
    second = output / "展览视觉-v2"
    first.mkdir()
    write(first, "海报/主视觉.svg", poster("#547e9a", "2026.11.18 — 11.25"))
    write(first, "海报/符号.svg", '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M10 90V40Q50-15 90 40V90Z" fill="#172d3d"/></svg>\n')
    write(first, "文案/展览介绍.txt", "窗的练习\n展期：2026年11月18日至25日\n每天 10:00—18:00\n")
    write(first, "说明/使用说明.txt", "SVG 可编辑；海报画布 720×960。示例作品由 Aevum 原创。\n")
    write(first, "说明/许可.txt", "本示例文件采用 MIT 许可证，完整条款见项目根目录 LICENSE。\n")
    write(first, "色板/colors.txt", "Ink #172D3D\nPaper #EAF0F4\nBlue #547E9A\n")
    write(first, "草稿/旧标语.txt", "看见窗外，也看见自己。\n")
    shutil.copytree(first, second)
    write(second, "海报/主视觉.svg", poster("#476f89", "2026.11.20 — 11.27"))
    write(second, "文案/展览介绍.txt", "窗的练习\n展期：2026年11月20日至27日\n每天 10:00—18:00\n周五延长至 20:00。\n")
    (second / "海报/符号.svg").rename(second / "海报/窗形标志.svg")
    (second / "草稿/旧标语.txt").unlink()
    write(second, "文案/社交平台短句.txt", "留一扇窗，给日常以外的风景。\n")
    bad = output / "收到的交付包"
    shutil.copytree(second, bad)
    (bad / "说明/使用说明.txt").unlink()
    shutil.copyfile(first / "海报/主视觉.svg", bad / "海报/主视觉.svg")
    write(bad, "临时备注.txt", "待整理\n")
    good = output / "核对后的交付包"
    shutil.copytree(second, good)
    run(["scan", first, "--out", output / "v1.json"])
    run(["scan", second, "--out", output / "v2.json"])
    run(["compare", output / "v1.json", output / "v2.json", "--html", output / "comparison.html", "--json", output / "comparison.json", "--lang", "zh"], 1)
    run(["verify", output / "v2.json", bad, "--html", output / "verification-failed.html", "--json", output / "verification-failed.json", "--lang", "zh"], 1)
    run(["verify", output / "v2.json", good, "--html", output / "verification-passed.html", "--json", output / "verification-passed.json", "--lang", "zh"])
    run(["compare", output / "v1.json", output / "v2.json", "--html", output / "comparison-en.html"] , 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    create(parser.parse_args().output)
