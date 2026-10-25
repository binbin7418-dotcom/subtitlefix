# SubtitleFix — SRT / WebVTT Repair & Re-Check

Players and platforms reject or mis-render subtitle files for mechanical
reasons: wrong millisecond separators, overlapping cues, scrambled numbering. SubtitleFix repairs those, warns about the
readability problems only a human can judge, then **re-parses the repaired
file** to prove it is mechanically sound. 100% local.

## What it fixes on its own
- Timestamp separator normalized to the format standard (`,` for SRT, `.` for WebVTT)
- Cues re-sorted chronologically; SRT cue numbers re-sequenced
- Overlapping cues trimmed (earlier cue ends 1 ms before the next starts) — logged
- Zero/negative-duration cues extended to a readable minimum — logged
- Empty cues removed

## What it reports, but never rewrites
- Reading speed over ~21 chars/sec; cues under 0.8 s or over 7 s
- Lines over 42 characters; unbalanced <i>/<b>/<u> tags; gaps under 80 ms
Your wording is yours — SubtitleFix never edits text.

## Verified behaviour
On a seeded 5-cue SRT with dot separators, an overlap, a zero-duration cue
and an empty cue: 4 repairs applied; the re-parse of the output showed
0 overlaps and 0 invalid durations (verdict PASS), with 8 readability
warnings itemized for the author.

## Run from source
```
python subtitle_fix.py captions.srt output_folder
```
Writes `<name>_fixed.srt` (or `.vtt`) and `fix_report.md`. Standard library only.
The Windows app wraps the same engine.
