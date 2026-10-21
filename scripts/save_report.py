#!/usr/bin/env python3
"""Save an already open, fully generated Chaoxing report; no task mutations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid

from agent_browser import run_agent


REPORT_MARKER = "以下是根据您的学习情况生成的质量评估报告"


def parse_report(body: str) -> tuple[str, dict]:
    report = body.rsplit(REPORT_MARKER, 1)[-1].strip()
    scores = re.findall(r"综合评估得\s*(\d+)\s*分", report)
    points = re.findall(r"本次学习共\s*(\d+)个知识点", report)
    if "学习质量评估报告" not in report or "重新练习" not in report:
        raise ValueError("The report is not open or has not finished generating.")
    if len(scores) != 1 or len(points) != 1:
        raise ValueError("Expected one complete report with one score and knowledge-point count.")
    score, count = int(scores[0]), int(points[0])
    if not 0 <= score <= 100 or count <= 0:
        raise ValueError("Report score or knowledge-point count is outside the expected range.")
    return report + "\n", {"score": score, "knowledge_points": count}


def capture_report(session: str, prefix: Path, binary: str | None, overwrite: bool) -> dict:
    prefix = prefix.expanduser().resolve()
    targets = {ext: Path(str(prefix) + ext) for ext in (".txt", ".png", ".json")}
    if not overwrite and any(path.exists() for path in targets.values()):
        raise FileExistsError("Report output already exists; choose a new prefix or use --overwrite.")
    result = run_agent(
        session, ["eval", "document.body.innerText"], binary=binary, capture=True, timeout=40
    )
    if result.returncode:
        raise RuntimeError(f"Reading report failed (exit {result.returncode}); inspect current page.")
    body = json.loads(result.stdout.decode("utf-8-sig"))
    if not isinstance(body, str):
        raise ValueError("CLI eval did not return a JSON string. Inspect current CLI output format.")
    report, metadata = parse_report(body)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    temporary_png = prefix.with_name(prefix.name + ".capture-" + uuid.uuid4().hex + ".png")
    try:
        shot = run_agent(
            session, ["screenshot", str(temporary_png)], binary=binary, capture=True, timeout=40
        )
        if shot.returncode or not temporary_png.is_file() or temporary_png.stat().st_size == 0:
            raise RuntimeError("Screenshot failed; report capture is incomplete. Inspect current page.")
        # Do not emit success records if CLI did not produce the requested screenshot.
        temporary_png.replace(targets[".png"])
        targets[".txt"].write_text(report, encoding="utf-8")
        metadata.update({
            "session": session,
            "report_text": str(targets[".txt"]),
            "report_screenshot": str(targets[".png"]),
        })
        targets[".json"].write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finally:
        temporary_png.unlink(missing_ok=True)
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--bin", dest="binary")
    parser.add_argument("--output-prefix", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        metadata = capture_report(args.session, args.output_prefix, args.binary, args.overwrite)
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Report not saved: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
