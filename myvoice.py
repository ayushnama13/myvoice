#!/usr/bin/env python3
import argparse
import datetime
import glob
import json
import os
import signal
import subprocess
import sys
import time
import wave

import numpy as np

SENTENCES = [
    "The morning sun rose slowly over the quiet mountains, casting a golden glow across the valley.",
    "Technology continues to evolve rapidly, transforming how we communicate, work, and live every day.",
    "Reading a good book in a cozy armchair on a rainy afternoon is one of life's simple pleasures.",
    "Exploring new hiking trails allows you to discover breathtaking views and reconnect with nature.",
    "Listening to the gentle sound of ocean waves crashing against the shore brings a deep sense of calm.",
    "Learning a new language opens up windows to different cultures, perspectives, and ways of thinking.",
    "Preparing a warm, homemade meal from scratch is both a creative outlet and a rewarding experience.",
    "A consistent daily mindfulness practice helps reduce stress and brings clarity to a busy mind.",
    "Stargazing on a clear, dark night reminds us of the immense scale and wonder of the universe.",
    "Building strong and meaningful relationships requires patience, active listening, and genuine empathy.",
    "Setting clear personal goals provides direction and purpose as we navigate our personal journeys.",
    "Music has the unique power to evoke powerful memories and uplift our spirits in difficult times."
]

def save_wav(path, pcm, sr):
    audio = np.array(pcm, dtype=np.float32)
    audio = np.clip(audio, -1.0, 1.0)
    audio_int16 = (audio * 32767).astype(np.int16)
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio_int16.tobytes())

def load_tts(ref=None):
    if not os.path.isdir("samples") or not glob.glob("samples/*.wav"):
        print("Error: run: python myvoice.py record first", file=sys.stderr)
        sys.exit(1)
    
    ref_idx = ref
    if ref_idx is None:
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r") as f:
                    data = json.load(f)
                    ref_idx = data.get("ref")
            except Exception:
                pass
        
        if ref_idx is None:
            wavs = sorted(glob.glob("samples/*.wav"))
            best_wav = None
            max_dur = -1.0
            for w in wavs:
                try:
                    with wave.open(w, 'rb') as wf:
                        dur = wf.getnframes() / wf.getframerate()
                        if dur > max_dur:
                            max_dur = dur
                            base = os.path.basename(w)
                            ref_idx = int(base.split('.')[0])
                except Exception:
                    pass
            if ref_idx is None:
                ref_idx = 0
    
    wav_path = f"samples/{ref_idx:02d}.wav"
    txt_path = f"samples/{ref_idx:02d}.txt"
    if not os.path.exists(wav_path) or not os.path.exists(txt_path):
        print(f"Error: reference sample {ref_idx:02d} (.wav or .txt) not found.", file=sys.stderr)
        sys.exit(1)
    
    with open(txt_path, "r") as f:
        transcript = f.read().strip()
    
    print(f"Loading TTS and cloning from {wav_path} (transcript: \"{transcript}\")...")
    from moonshine_voice import TextToSpeech
    tts = TextToSpeech().language("en_us").cloning()
    tts.load()
    tts.clone_from(wav_path, transcript=transcript)
    return tts

def cmd_record(args):
    os.makedirs("samples", exist_ok=True)
    for i, sentence in enumerate(SENTENCES):
        wav_path = f"samples/{i:02d}.wav"
        txt_path = f"samples/{i:02d}.txt"
        
        if os.path.exists(wav_path) and os.path.exists(txt_path) and not args.redo:
            print(f"[{i+1}/12] Skipping existing sample {i:02d}.wav (use --redo to re-record)")
            continue
        
        while True:
            print(f"\n--- Sentence {i+1}/12 ---")
            print(f"  \"{sentence}\"")
            input("Press Enter to start recording...")
            
            proc = subprocess.Popen([
                "parecord", "--channels=1", "--rate=24000", "--format=s16le", "--file-format=wav", wav_path
            ])
            
            time.sleep(1.0)  # parecord needs ~1 s to start capturing
            input(">>> SPEAK NOW. Press Enter when finished.")
            proc.send_signal(signal.SIGINT)
            proc.wait()
            
            duration = 0.0
            try:
                with wave.open(wav_path, 'rb') as wf:
                    duration = wf.getnframes() / wf.getframerate()
            except Exception:
                pass
            
            if duration < 2.0:
                print(f"Recording too short ({duration:.1f}s). Must be at least 2 seconds. Please try again.")
                continue
            
            print(f"Recorded successfully ({duration:.1f}s).")
            ans = input("Press Enter to continue, 'r' to redo, 'q' to quit: ").strip().lower()
            if ans == 'q':
                sys.exit(0)
            elif ans == 'r':
                continue
            else:
                with open(txt_path, "w") as f:
                    f.write(sentence)
                print(f"Saved {wav_path} and {txt_path}")
                break

def cmd_pick(args):
    wavs = sorted(glob.glob("samples/*.wav"))
    if not wavs:
        print("Error: run: python myvoice.py record first", file=sys.stderr)
        sys.exit(1)
    
    os.makedirs("out", exist_ok=True)
    test_sentence = "The quick brown fox jumps over the lazy dog."
    best_i = None
    max_rating = -1
    
    from moonshine_voice import TextToSpeech
    print("Loading TTS engine...")
    tts = TextToSpeech().language("en_us").cloning()
    tts.load()
    
    for w in wavs:
        base = os.path.basename(w)
        i_str = base.split('.')[0]
        try:
            i = int(i_str)
        except ValueError:
            continue
        txt_path = f"samples/{i:02d}.txt"
        if not os.path.exists(txt_path):
            continue
        
        print(f"\nEvaluating sample {i:02d}...")
        with open(txt_path, "r") as f:
            transcript = f.read().strip()
        
        print(f"Cloning from {w}...")
        tts.clone_from(w, transcript=transcript)
        
        print(f"Synthesizing test sentence: \"{test_sentence}\" (~3x slower than realtime)...")
        pcm, sr = tts.synthesize(test_sentence, speed=1.0)
        
        out_path = f"out/pick_{i:02d}.wav"
        save_wav(out_path, pcm, sr)
        print(f"Saved: {out_path}")
        
        if not args.no_play:
            print("Playing test audio...")
            subprocess.run(["paplay", out_path])
        
        try:
            rating = int(input(f"Rate sample {i:02d} (1-5): "))
        except ValueError:
            rating = 1
        
        if rating > max_rating:
            max_rating = rating
            best_i = i
    
    if best_i is not None:
        config = {"ref": best_i}
        with open("config.json", "w") as f:
            json.dump(config, f, indent=2)
        print(f"\nBest sample index saved to config.json: {config}")
    else:
        print("No valid samples evaluated.")

def cmd_say(args):
    text_content = ""
    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: file '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r") as f:
            text_content = f.read()
    elif args.text:
        text_content = " ".join(args.text)
    
    if not text_content.strip():
        print("Error: text is empty.", file=sys.stderr)
        sys.exit(1)
    
    lines = [l.strip() for l in text_content.splitlines() if l.strip()]
    if not lines:
        print("Error: text is empty.", file=sys.stderr)
        sys.exit(1)
    
    tts = load_tts()
    
    all_audio = []
    sr = 24000
    silence_06 = None
    
    for idx, line in enumerate(lines):
        print(f"Synthesizing [{idx+1}/{len(lines)}]: \"{line}\" (~3x slower than realtime)...")
        pcm, sample_rate = tts.synthesize(line, speed=args.speed)
        sr = sample_rate
        all_audio.append(np.array(pcm, dtype=np.float32))
        
        if idx < len(lines) - 1:
            if silence_06 is None:
                silence_06 = np.zeros(int(sr * 0.6), dtype=np.float32)
            all_audio.append(silence_06)
    
    if all_audio:
        combined = np.concatenate(all_audio)
    else:
        combined = np.array([], dtype=np.float32)
    
    os.makedirs("out", exist_ok=True)
    out_path = args.out
    if not out_path:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = f"out/say_{ts}.wav"
    
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    save_wav(out_path, combined, sr)
    print(f"Saved: {out_path}")
    
    if args.play:
        print("Playing audio...")
        subprocess.run(["paplay", out_path])

def cmd_night(args):
    if not os.path.exists(args.file):
        print(f"Error: file '{args.file}' not found.", file=sys.stderr)
        sys.exit(1)
    with open(args.file, "r") as f:
        text_content = f.read()
    
    lines = [l.strip() for l in text_content.splitlines() if l.strip()]
    if not lines:
        print("Error: text file is empty.", file=sys.stderr)
        sys.exit(1)
    
    if not args.out:
        args.out = "out/night.wav"
    tts = load_tts()
    
    block_audio = []
    sr = 24000
    gap_silence = None
    
    for idx, line in enumerate(lines):
        print(f"Synthesizing night line [{idx+1}/{len(lines)}]: \"{line}\"...")
        pcm, sample_rate = tts.synthesize(line, speed=args.speed)
        sr = sample_rate
        block_audio.append(np.array(pcm, dtype=np.float32))
        
        if idx < len(lines) - 1:
            if gap_silence is None:
                gap_silence = np.zeros(int(sr * args.gap), dtype=np.float32)
            block_audio.append(gap_silence)
    
    if block_audio:
        single_block = np.concatenate(block_audio)
    else:
        single_block = np.array([], dtype=np.float32)
    
    repeats = []
    repeat_gap = np.zeros(int(sr * args.gap), dtype=np.float32) if sr else np.zeros(int(24000 * args.gap), dtype=np.float32)
    for r_idx in range(args.repeat):
        repeats.append(single_block)
        if r_idx < args.repeat - 1:
            repeats.append(repeat_gap)
    
    if repeats:
        final_audio = np.concatenate(repeats)
    else:
        final_audio = single_block
    
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    save_wav(args.out, final_audio, sr)
    print(f"Saved: {args.out}")
    
    if args.play:
        print("Playing night audio...")
        subprocess.run(["paplay", args.out])

def main():
    parser = argparse.ArgumentParser(description="MyVoice CLI: Voice cloning and text-to-speech")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # record
    record_parser = subparsers.add_parser("record", help="Record reference sentences")
    record_parser.add_argument("--redo", action="store_true", help="Re-record existing samples")
    record_parser.set_defaults(func=cmd_record)
    
    # pick
    pick_parser = subparsers.add_parser("pick", help="Pick the best reference sample")
    pick_parser.add_argument("--no-play", action="store_true", help="Do not play test audio with paplay")
    pick_parser.set_defaults(func=cmd_pick)
    
    # say
    say_parser = subparsers.add_parser("say", help="Synthesize text or file")
    say_parser.add_argument("text", nargs="*", help="Text to speak")
    say_parser.add_argument("-f", "--file", help="Input text file")
    say_parser.add_argument("-o", "--out", help="Output WAV path")
    say_parser.add_argument("--speed", type=float, default=1.0, help="Speech speed")
    say_parser.add_argument("--play", action="store_true", help="Play audio with paplay")
    say_parser.set_defaults(func=cmd_say)
    
    # night
    night_parser = subparsers.add_parser("night", help="Render nighttime relaxation audio from file")
    night_parser.add_argument("-f", "--file", required=True, help="Input text file")
    night_parser.add_argument("--repeat", type=int, default=3, help="Repeat count")
    night_parser.add_argument("--gap", type=float, default=4.0, help="Gap in seconds between lines")
    night_parser.add_argument("--speed", type=float, default=0.9, help="Speech speed")
    night_parser.add_argument("-o", "--out", default=None, help="Output WAV path (default: out/night.wav)")
    night_parser.add_argument("--play", action="store_true", help="Play audio with paplay")
    night_parser.set_defaults(func=cmd_night)
    
    args = parser.parse_args()
    if getattr(args, "speed", 1.0) <= 0:
        parser.error("--speed must be > 0")
    if getattr(args, "repeat", 1) < 1:
        parser.error("--repeat must be >= 1")
    if getattr(args, "gap", 0.0) < 0:
        parser.error("--gap must be >= 0")
    for attr in ("file", "out"):
        if getattr(args, attr, None):
            setattr(args, attr, os.path.abspath(getattr(args, attr)))
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    args.func(args)

if __name__ == "__main__":
    main()
