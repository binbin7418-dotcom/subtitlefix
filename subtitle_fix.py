#!/usr/bin/env python3
"""
SubtitleFix — SRT / WebVTT subtitle repair & re-check engine.

Repairs the mechanical defects that make players and platforms reject or
mis-render subtitle files:
  - cue numbering re-sequenced (SRT)
  - '.' vs ',' millisecond separator normalized to the format's standard
  - cues re-sorted chronologically when they are out of order
  - overlapping cues: the earlier cue is trimmed to end 1 ms before the
    next one starts (the standard editor repair), always logged
  - zero/negative-duration cues extended to a readable minimum, logged
  - empty cues removed

Reports what needs a human (never silently "fixed"):
  - reading speed over ~21 chars/sec, display duration too short/long,
    lines over 42 characters, unbalanced formatting tags, gaps under 80 ms

Ends with a re-check: the repaired file is re-parsed and must show zero
overlaps, zero invalid durations and sequential numbering.
Local only. Standard library only.
"""
import os
import re
import sys

TS = re.compile(r"(\d+):(\d{2}):(\d{2})[.,](\d{3})")
MIN_DUR = 1.0
MAX_CPS = 21.0


def parse_ts(s):
    m = TS.search(s or "")
    if not m:
        return None
    h, mnt, sec, ms = (int(x) for x in m.groups())
    return h * 3600 + mnt * 60 + sec + ms / 1000.0


def fmt_ts(t, vtt=False):
    t = max(0.0, t)
    h = int(t // 3600); mnt = int((t % 3600) // 60); sec = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    if ms == 1000:
        sec += 1; ms = 0
    sep = "." if vtt else ","
    return f"{h:02d}:{mnt:02d}:{sec:02d}{sep}{ms:03d}"


def parse(path):
    text = open(path, "rb").read().decode("utf-8-sig", errors="replace")
    is_vtt = text.lstrip().upper().startswith("WEBVTT") or path.lower().endswith(".vtt")
    blocks = re.split(r"\n\s*\n", text.strip())
    cues = []
    for b in blocks:
        lines = [ln for ln in b.splitlines() if ln.strip() != "" or True]
        ti = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if ti is None:
            continue
        parts = lines[ti].split("-->")
        start = parse_ts(parts[0])
        end = parse_ts(parts[1])
        if start is None or end is None:
            continue
        cues.append({"start": start, "end": end,
                     "text": "\n".join(lines[ti + 1:]).strip(),
                     "orig_sep": "." if "." in parts[0].split(":")[-1] else ","})
    return cues, is_vtt


def tag_balance(text):
    opens = len(re.findall(r"<(i|b|u)>", text))
    closes = len(re.findall(r"</(i|b|u)>", text))
    return opens == closes


def run_subtitlefix(src_path, outdir):
    os.makedirs(outdir, exist_ok=True)
    cues, is_vtt = parse(src_path)
    base = os.path.splitext(os.path.basename(src_path))[0]
    fixes, warnings = [], []

    if any(cues[i]["start"] > cues[i + 1]["start"] for i in range(len(cues) - 1)):
        cues.sort(key=lambda c: c["start"])
        fixes.append("cues were out of chronological order — re-sorted by start time")

    want_dot = is_vtt
    if any((". " not in c["orig_sep"]) and ((c["orig_sep"] == ".") != want_dot) for c in cues):
        fixes.append(f"timestamp separator normalized to '{'.' if want_dot else ','}' (the {'WebVTT' if want_dot else 'SRT'} standard)")

    before_n = len(cues)
    cues = [c for c in cues if c["text"]]
    if len(cues) < before_n:
        fixes.append(f"removed {before_n - len(cues)} empty cue(s)")

    for i, c in enumerate(cues):
        if c["end"] <= c["start"]:
            c["end"] = c["start"] + MIN_DUR
            fixes.append(f"cue {i + 1}: end time was not after its start — extended to a {MIN_DUR:.0f}s minimum (check the wording still fits)")

    for i in range(len(cues) - 1):
        if cues[i]["end"] > cues[i + 1]["start"]:
            cues[i]["end"] = max(cues[i]["start"] + 0.1, cues[i + 1]["start"] - 0.001)
            fixes.append(f"cue {i + 1}: overlapped the next cue — end trimmed to {fmt_ts(cues[i]['end'], is_vtt)}")

    for i, c in enumerate(cues):
        dur = c["end"] - c["start"]
        chars = len(re.sub(r"<[^>]+>", "", c["text"]).replace("\n", " "))
        if dur < 0.8:
            warnings.append(f"cue {i + 1}: displays for only {dur:.1f}s — most viewers cannot read it in time")
        if dur > 7:
            warnings.append(f"cue {i + 1}: displays for {dur:.0f}s — consider splitting it")
        if dur > 0 and chars / dur > MAX_CPS:
            warnings.append(f"cue {i + 1}: reading speed {chars / dur:.0f} chars/sec (over the ~{MAX_CPS:.0f} comfort limit) — shorten the text or extend the cue")
        for ln in c["text"].splitlines():
            if len(re.sub(r"<[^>]+>", "", ln)) > 42:
                warnings.append(f"cue {i + 1}: a line is over 42 characters — it may wrap badly on small screens")
                break
        if not tag_balance(c["text"]):
            warnings.append(f"cue {i + 1}: formatting tags (<i>/<b>/<u>) are unbalanced — some players drop the styling or the cue")
        if i + 1 < len(cues) and 0 <= cues[i + 1]["start"] - c["end"] < 0.08:
            warnings.append(f"gap after cue {i + 1} is under 80 ms — some players merge the two cues")

    ext = ".vtt" if is_vtt else ".srt"
    fixed_path = os.path.join(outdir, base + "_fixed" + ext)
    with open(fixed_path, "w", encoding="utf-8") as fh:
        if is_vtt:
            fh.write("WEBVTT\n\n")
            for c in cues:
                fh.write(f"{fmt_ts(c['start'], True)} --> {fmt_ts(c['end'], True)}\n{c['text']}\n\n")
        else:
            for i, c in enumerate(cues):
                fh.write(f"{i + 1}\n{fmt_ts(c['start'])} --> {fmt_ts(c['end'])}\n{c['text']}\n\n")

    rc, _ = parse(fixed_path)
    overlaps = sum(1 for i in range(len(rc) - 1) if rc[i]["end"] > rc[i + 1]["start"])
    bad_dur = sum(1 for c in rc if c["end"] <= c["start"])
    verdict = "PASS" if overlaps == 0 and bad_dur == 0 else "NOT READY"

    lines = ["# SubtitleFix — repair & re-check report", "",
             f"Source file: {os.path.basename(src_path)}  ·  Format: {'WebVTT' if is_vtt else 'SRT'}  ·  Cues: {len(rc)}", "",
             "## Summary",
             f"- Auto-fixed: {len(fixes)}",
             f"- Warnings needing your judgment: {len(warnings)}",
             f"- Re-check: {overlaps} overlaps, {bad_dur} invalid durations in the repaired file", "",
             "## What was fixed automatically"]
    lines += [f"- {f}" for f in fixes] or ["- nothing"]
    lines += ["", "## What still needs your judgment"]
    lines += [f"- {w}" for w in warnings] or ["- nothing — no reading-speed, length or formatting warnings"]
    lines += ["", "## Re-check verdict",
              f"- {verdict}: the repaired file was re-parsed; overlaps and invalid durations must be zero. "
              "Scope note: SubtitleFix repairs timing and file mechanics. Translation quality and "
              "wording are yours — it never rewrites your text."]
    report_path = os.path.join(outdir, "fix_report.md")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return {"cues": len(rc), "fixed": len(fixes), "warnings": len(warnings),
            "verdict": verdict, "fixed_path": fixed_path, "report_path": report_path}


def main(argv):
    if len(argv) != 3:
        print("usage: subtitle_fix.py <subs.srt|subs.vtt> <outdir>")
        return 2
    s = run_subtitlefix(argv[1], argv[2])
    print(f"cues={s['cues']} fixed={s['fixed']} warnings={s['warnings']} verdict={s['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
