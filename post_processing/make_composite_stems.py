from __future__ import annotations

import os
import gc
import sys
import argparse
import warnings
from pathlib import Path
from typing import Optional, List, Tuple, Any

from core.schemas import Song
from core.helpers import (
    filename_to_song,
    song_to_filename,
    song_to_stem_filename,
)
from post_processing.copy_songs import extract_date_from_file, parse_date_str
from dotenv import load_dotenv

load_dotenv()

# Suppress TorchCodec UserWarnings regarding 'encoding' and 'bits_per_sample' parameters,
# which are handled automatically by TorchCodec AudioEncoder based on the .wav extension.
warnings.filterwarnings("ignore", category=UserWarning, message=r".*TorchCodec.*")
warnings.filterwarnings("ignore", category=UserWarning, message=r".*encoding.*parameter is not fully supported.*")
warnings.filterwarnings("ignore", category=UserWarning, message=r".*bits_per_sample.*parameter is not directly supported.*")

# Targets extracted from the fine-tuned 4-stem model (htdemucs_ft)
# Tuple format: (demucs_key, output_stem_label)
FT_TARGETS: List[Tuple[str, str]] = [
    ("vocals", "vocal"),
    ("drums", "drums"),
    ("bass", "bass"),
]

# Targets extracted from the 6-stem model (htdemucs_6s)
# Tuple format: (demucs_key, output_stem_label)
SIX_TARGETS: List[Tuple[str, str]] = [
    ("guitar", "guitar"),
    ("piano", "piano"),
    ("other", "other"),
]

ALL_COMPOSITE_STEMS: List[str] = ["vocal", "drums", "bass", "guitar", "piano", "other"]


def resolve_device(device: Optional[str] = None) -> str:
    """Resolves the computational device for Demucs models (mps, cuda, or cpu).
    
    Priority:
    1. Explicit device argument passed to function/CLI
    2. STEMS_DEVICE environment variable
    3. Auto-detected hardware acceleration (cuda -> mps -> cpu)
    """
    if device and str(device).strip():
        return str(device).strip()

    env_device = os.getenv("STEMS_DEVICE")
    if env_device and str(env_device).strip():
        return str(env_device).strip()

    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass

    return "cpu"


def resolve_song(song_input: str | Path | Song) -> Song:
    """Resolves a string, Path, or Song object into a canonical Song instance."""
    if isinstance(song_input, Song):
        return song_input
    parsed = filename_to_song(str(song_input))
    if parsed is not None:
        return parsed
    return Song(title=Path(str(song_input)).stem)


def check_stem_exists(output_dir: Path, song_name: str | Path | Song, stem_label: str) -> bool:
    """Checks if a stem file already exists in the destination folder, accommodating
    both singular 'vocal' and plural 'vocals' conventions, utilizing song_to_filename()
    and filename_to_song() to match canonical filenames.
    """
    song = resolve_song(song_name)
    candidates = [output_dir / f"{song_to_filename(song)} - {stem_label}.wav"]
    if stem_label == "vocal":
        candidates.append(output_dir / f"{song_to_filename(song)} - vocals.wav")
    elif stem_label == "vocals":
        candidates.append(output_dir / f"{song_to_filename(song)} - vocal.wav")

    # If the input was a string or Path whose raw stem differs from song_to_filename(song),
    # also check the raw stem to maintain full compatibility with legacy or non-canonical files
    if not isinstance(song_name, Song):
        raw_stem = Path(str(song_name)).stem
        if raw_stem and raw_stem != song_to_filename(song):
            candidates.append(output_dir / f"{raw_stem} - {stem_label}.wav")
            if stem_label == "vocal":
                candidates.append(output_dir / f"{raw_stem} - vocals.wav")
            elif stem_label == "vocals":
                candidates.append(output_dir / f"{raw_stem} - vocal.wav")

    return any(c.exists() for c in candidates)


def save_audio_stem(out_file: Path | str, tensor: Any, sample_rate: int = 44100) -> None:
    """Saves an audio tensor to a .wav file natively.
    Calls torchaudio.save(out_file, tensor, sample_rate) without unsupported encoding
    parameters, allowing the backend (such as TorchCodec) to automatically infer
    audio format and encoding settings from the tensor dtype and .wav file extension.
    If torchaudio/torchcodec is unavailable, falls back to the standard library wave module.
    """
    import torchaudio

    try:
        torchaudio.save(str(out_file), tensor, sample_rate)
        return
    except Exception as e:
        if "torchcodec" not in str(e).lower() and "save_with_torchcodec" not in str(e).lower():
            raise

    # Fallback: Save directly via standard library 'wave' module
    try:
        import wave
        import numpy as np

        audio_cpu = tensor.detach().cpu() if hasattr(tensor, "detach") else tensor
        audio_np = audio_cpu.numpy() if hasattr(audio_cpu, "numpy") else np.asarray(audio_cpu)
        audio_np = np.clip(audio_np, -1.0, 1.0)
        int16_data = (audio_np * 32767).astype(np.int16)

        if int16_data.ndim == 2:
            channels, samples = int16_data.shape
            if channels <= 8 and samples > channels:
                int16_data = int16_data.T
            num_channels = int16_data.shape[1] if int16_data.ndim == 2 else 1
        else:
            num_channels = 1

        with wave.open(str(out_file), "wb") as wf:
            wf.setnchannels(num_channels)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(int16_data.tobytes())
        return
    except Exception as fb_err:
        raise RuntimeError(
            f"❌ Error saving audio stem to {out_file}: TorchCodec is required for torchaudio.save, "
            "and fallback failed. Please install torchcodec via: pip install torchcodec"
        ) from fb_err


def generate_composite_stems_for_file(
    input_file: str | Path,
    output_base_dir: str | Path,
    device: Optional[str] = None,
    overwrite: bool = False,
    separator_ft: Optional[Any] = None,
    separator_6s: Optional[Any] = None,
    song: Optional[Song] = None,
) -> Path:
    """Generates composite hybrid stems for a single audio file:
    - Vocals, Drums, and Bass extracted from htdemucs_ft
    - Guitar, Piano, and Other extracted from htdemucs_6s
    
    Output directory:
        output_base_dir / f"{song_to_filename(song)} - Stems"
    Stem files:
        f"{song_to_filename(song)} - {stem}.wav"
    """
    try:
        import demucs.api
        import torchaudio
    except ImportError as err:
        raise ImportError(
            f"Required audio stem separation packages are not available: {err}. "
            "Please install demucs, torchaudio, torch, numpy, and torchcodec (e.g. pip install demucs torchaudio torch numpy torchcodec)."
        ) from err

    input_path = Path(input_file)
    song_obj = song or resolve_song(input_path.name)
    output_dir = Path(output_base_dir) / f"{song_to_filename(song_obj)} - Stems"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check if all composite stems already exist
    all_exist = all(check_stem_exists(output_dir, song_obj, stem) for stem in ALL_COMPOSITE_STEMS)
    if all_exist and not overwrite:
        print(f"Skipping (composite stems already exist): {song_to_filename(song_obj)}")
        return output_dir

    print("=" * 60)
    print(f"🎛️ Generating Composite Stems: {song_to_filename(song_obj)}")
    print("=" * 60)

    resolved_device = resolve_device(device)
    print(f"  -> Acceleration Device: {resolved_device}")

    # Determine which passes need to run
    ft_needed = overwrite or any(
        not check_stem_exists(output_dir, song_obj, out_label) 
        for _, out_label in FT_TARGETS
    )
    six_needed = overwrite or any(
        not check_stem_exists(output_dir, song_obj, out_label) 
        for _, out_label in SIX_TARGETS
    )

    # ==========================================
    # PASS 1: High-Fidelity Rhythm Section (FT)
    # ==========================================
    if ft_needed:
        print("\n  -> Pass 1: Loading htdemucs_ft (Vocals, Drums, Bass)...")
        ft_sep = separator_ft
        created_ft = False
        if ft_sep is None:
            ft_sep = demucs.api.Separator(model="htdemucs_ft", device=resolved_device)
            created_ft = True

        sample_rate = getattr(ft_sep, "samplerate", 44100)
        print("     Extracting Vocals, Drums, and Bass...")
        _, separated_ft = ft_sep.separate_audio_file(str(input_path))

        for demucs_key, stem_label in FT_TARGETS:
            if demucs_key in separated_ft:
                out_file = output_dir / f"{song_to_filename(song_obj)} - {stem_label}.wav"
                if not out_file.exists() or overwrite:
                    save_audio_stem(out_file, separated_ft[demucs_key], sample_rate)
                    print(f"     ✅ Saved: {out_file.name} (htdemucs_ft)")
                else:
                    print(f"     ⏩ Skipped (already exists): {out_file.name}")

        # Clear fine-tuned model and audio tensors from unified/GPU memory
        if created_ft:
            del ft_sep
        del separated_ft
        gc.collect()
    else:
        print("\n  -> Pass 1 (htdemucs_ft): Rhythm section stems already exist. Skipping.")

    # ==========================================
    # PASS 2: Chordal Instruments (6S)
    # ==========================================
    if six_needed:
        print("\n  -> Pass 2: Loading htdemucs_6s (Guitar, Piano, Other)...")
        six_sep = separator_6s
        created_six = False
        if six_sep is None:
            six_sep = demucs.api.Separator(model="htdemucs_6s", device=resolved_device)
            created_six = True

        sample_rate = getattr(six_sep, "samplerate", 44100)
        print("     Extracting Guitar, Piano, and Other...")
        _, separated_6s = six_sep.separate_audio_file(str(input_path))

        for demucs_key, stem_label in SIX_TARGETS:
            if demucs_key in separated_6s:
                out_file = output_dir / f"{song_to_filename(song_obj)} - {stem_label}.wav"
                if not out_file.exists() or overwrite:
                    save_audio_stem(out_file, separated_6s[demucs_key], sample_rate)
                    print(f"     ✅ Saved: {out_file.name} (htdemucs_6s)")
                else:
                    print(f"     ⏩ Skipped (already exists): {out_file.name}")

        # Clear 6-stem model and audio tensors from unified/GPU memory
        if created_six:
            del six_sep
        del separated_6s
        gc.collect()
    else:
        print("\n  -> Pass 2 (htdemucs_6s): Chordal instrument stems already exist. Skipping.")

    print(f"\n✅ Finished composite stems for: {song_to_filename(song_obj)}")
    print(f"   Destination: {output_dir}\n")
    return output_dir


def make_composite_stems(
    src_dir: str,
    dest_dir: str,
    device: Optional[str] = None,
    target_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    overwrite: bool = False
) -> List[str]:
    """Generates composite 6-track stems (Vocals, Drums, Bass, Guitar, Piano, Other)
    from source .wav files in src_dir (typically VERIFIED_AUDIO_DIR) into dest_dir (STEMS_DIR).
    
    Filters files optionally by target_date (YYYY-MM-DD) or date range (start_date to end_date).
    Each song outputs into its own dedicated subfolder:
        {dest_dir}/{song_filename} - Stems/
    With individual .wav stem files:
        {song_filename} - vocal.wav
        {song_filename} - drums.wav
        {song_filename} - bass.wav
        {song_filename} - guitar.wav
        {song_filename} - piano.wav
        {song_filename} - other.wav
    """
    if not os.path.exists(src_dir):
        print(f"❌ Error: Source directory does not exist: {src_dir}")
        return []

    try:
        import demucs.api
        import torchaudio
    except ImportError as err:
        print(f"❌ Error: Demucs or PyTorch is not installed ({err}).")
        print("Please install Demucs and PyTorch: pip install demucs torchaudio torch numpy torchcodec")
        return []

    os.makedirs(dest_dir, exist_ok=True)

    if target_date:
        print(f"Filtering for date: {target_date}")
    elif start_date and end_date:
        print(f"Filtering for timeframe: {start_date} to {end_date} (inclusive)")

    # Find all .wav files in the source directory
    wav_files = [f for f in os.listdir(src_dir) if f.lower().endswith(".wav")]
    if not wav_files:
        print(f"No .wav files found in {src_dir}.")
        return []

    target_dt = parse_date_str(target_date)
    start_dt = parse_date_str(start_date)
    end_dt = parse_date_str(end_date)

    src_path = Path(src_dir)
    filtered_wav_files: List[str] = []
    for audio_file in sorted(wav_files):
        file_path = src_path / audio_file
        file_dt = extract_date_from_file(file_path, src_path)
        if file_dt is None:
            song_candidate = filename_to_song(audio_file)
            if song_candidate and song_candidate.date:
                file_dt = parse_date_str(song_candidate.date)

        if target_dt is not None:
            if file_dt is None or file_dt.date() != target_dt.date():
                continue
        elif start_dt is not None and end_dt is not None:
            if file_dt is None or not (start_dt.date() <= file_dt.date() <= end_dt.date()):
                continue

        filtered_wav_files.append(audio_file)

    if not filtered_wav_files:
        if target_dt or (start_dt and end_dt):
            print(f"No .wav files matching the specified date(s) found in {src_dir}.")
        else:
            print(f"No .wav files found in {src_dir}.")
        return []

    print(f"Found {len(filtered_wav_files)} audio file(s). Generating composite stems...")

    processed_dirs: List[str] = []
    for audio_file in filtered_wav_files:
        input_audio_path = os.path.join(src_dir, audio_file)
        try:
            song_obj = resolve_song(audio_file)
            out_dir = generate_composite_stems_for_file(
                input_file=input_audio_path,
                output_base_dir=dest_dir,
                device=device,
                overwrite=overwrite,
                song=song_obj,
            )
            processed_dirs.append(str(out_dir))
        except Exception as e:
            print(f"❌ Error generating composite stems for {audio_file}: {e}")

    print("=" * 60)
    print("All composite stems generated successfully!")
    print("=" * 60)
    return processed_dirs


def main(cli_args: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate composite stems (htdemucs_ft + htdemucs_6s) from verified recordings."
    )
    parser.add_argument(
        "--src-dir",
        default=os.getenv("VERIFIED_AUDIO_DIR", os.path.join(os.getcwd(), "verified_audio")),
        help="Source directory containing verified .wav audio files."
    )
    parser.add_argument(
        "--dest-dir",
        default=os.getenv("STEMS_DIR", os.path.join(os.getenv("VERIFIED_AUDIO_DIR", os.path.join(os.getcwd(), "verified_audio")), "Stems")),
        help="Destination directory for output stems."
    )
    parser.add_argument(
        "--date",
        help="Process only recordings for a specific date (YYYY-MM-DD)."
    )
    parser.add_argument(
        "--start-date",
        help="Start date for date range filter (YYYY-MM-DD)."
    )
    parser.add_argument(
        "--end-date",
        help="End date for date range filter (YYYY-MM-DD)."
    )
    parser.add_argument(
        "--device",
        help="Acceleration device to use (mps, cuda, or cpu). Auto-detects if omitted."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Force re-generation and overwrite existing stem files."
    )

    if cli_args is not None:
        args = parser.parse_args(cli_args)
    else:
        args = parser.parse_args()

    if args.date and (args.start_date or args.end_date):
        print("❌ Error: Cannot provide both --date and a date range (--start-date / --end-date).")
        sys.exit(1)

    if (args.start_date and not args.end_date) or (args.end_date and not args.start_date):
        print("❌ Error: Both --start-date and --end-date must be provided together.")
        sys.exit(1)

    make_composite_stems(
        src_dir=args.src_dir,
        dest_dir=args.dest_dir,
        device=args.device,
        target_date=args.date,
        start_date=args.start_date,
        end_date=args.end_date,
        overwrite=args.overwrite
    )


if __name__ == "__main__":
    main()
