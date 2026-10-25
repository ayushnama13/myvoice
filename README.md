# MyVoice CLI

A single-file Python CLI for voice cloning and text-to-speech synthesis using `moonshine_voice`.

## Quick start

```bash
cd ~/vscoder/Documents/vscode/myvoice
./myvoice record                       # read 12 sentences aloud (quiet room, normal voice)
./myvoice pick                         # listen to each clone, rate 1-5; best is saved
./myvoice say "I am calm and focused." --play
./myvoice night -f affirmations.txt --play   # edit affirmations.txt with your own lines
```

`./myvoice` uses the bundled `.venv`, so it works from any directory. The first
run downloads the ZipVoice models (~100 s, cached in `~/.cache/moonshine_voice`).
Synthesis runs on CPU at about 3x slower than real time, so render `night` once
and replay the WAV with `paplay out/night.wav`.

## Requirements

- Python 3.10+
- `numpy`, `moonshine_voice`
- Linux audio tools: `parecord`, `paplay` (PulseAudio / PipeWire)

## Commands

1. **`record [--redo]`**
   Record 12 reference sentences (~6-10s each). Skips existing samples unless `--redo` is specified. Redo (`r`) or quit (`q`) supported after each recording. Rejects recordings under 2 seconds.

2. **`pick [--no-play]`**
   Synthesize a test sentence using each recorded sample, play it (unless `--no-play`), ask for a 1-5 rating, and save the best sample index to `config.json`.

3. **`say TEXT | -f FILE [-o OUT.wav] [--speed S] [--play]`**
   Synthesize text or file input using the reference voice. Joins lines with 0.6s silence.

4. **`night -f FILE [--repeat N=3] [--gap SECONDS=4] [--speed 0.9] [-o out/night.wav] [--play]`**
   Render relaxation audio from a text file with customizable gaps and repetitions.
