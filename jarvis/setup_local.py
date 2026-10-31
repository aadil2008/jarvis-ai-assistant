"""Interactive installer; nothing is downloaded until the user chooses yes."""
from __future__ import annotations

import argparse
import io
import os
from pathlib import Path
import shutil
import subprocess
import wave

from local_client import LocalClient, OLLAMA_URL
from local_settings import CONFIG_PATH, MODEL_DIR, save_settings
from local_setup import choices_for, describe, detect_memory
from router_client import RouterClientError


def disk_free(path: Path) -> float:
    while not path.exists():
        path = path.parent
    return shutil.disk_usage(path).free / 1024**3


def install(choice) -> None:
    executable = shutil.which("ollama")
    if not executable:
        raise RouterClientError("Install Ollama from https://ollama.com/download, open it, then run this setup again. No model was downloaded.")
    client = LocalClient({"model": choice.name, "whisper_model": choice.whisper})
    # A tags request checks the daemon without requiring the selected model yet.
    client._request("/api/tags", timeout=5)
    storage = Path(os.getenv("OLLAMA_MODELS", str(Path.home() / ".ollama" / "models"))).expanduser()
    if disk_free(storage) < choice.download_gb * 1.5 + 1 or disk_free(MODEL_DIR) < 1:
        raise RouterClientError("Not enough free disk space for the model download and speech files. Free space, then retry.")
    print(f"Downloading {choice.name}. Ollama shows progress below; interrupted downloads can be retried.")
    environment = dict(os.environ, OLLAMA_HOST=OLLAMA_URL)
    subprocess.run([executable, "pull", choice.name], env=environment, check=True, timeout=3600)

    print(f"Preparing offline speech recognition ({choice.whisper})...")
    from faster_whisper import WhisperModel
    from faster_whisper.utils import download_model
    path = MODEL_DIR / f"whisper-{choice.whisper}"
    download_model(choice.whisper, output_dir=str(path))
    speech = WhisperModel(str(path), device="cpu", compute_type="int8", local_files_only=True)
    # Exercise actual audio decoding/inference, not only loading model files.
    sample = io.BytesIO()
    with wave.open(sample, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0" * 16000)
    sample.seek(0)
    segments, _ = speech.transcribe(sample, language="en", beam_size=1)
    list(segments)
    del speech
    print("Checking a local AI reply...")
    client.health()
    client.chat("Say ready in one short sentence.", max_tokens=30)
    if not client.voice_ready():
        raise RouterClientError("Speech model files are incomplete. Re-run setup.")
    # Preserve any working configuration until all download/readiness checks pass.
    save_settings(choice.name)


def run_setup(*, recommend_only=False, input_fn=input) -> int:
    memory = detect_memory()
    print("\nJARVIS local voice setup\n")
    print(describe(memory))
    options = choices_for(memory)
    if recommend_only:
        return 0
    if not options:
        return 1
    print("\nChoose a model (smaller models generally reply faster):")
    for index, choice in enumerate(options, 1):
        suffix = " [recommended]" if choice == options[-1] else ""
        print(f"  {index}. {choice.name} - about {choice.download_gb:g} GB{suffix}")
    raw = input_fn(f"Model number [Enter = {len(options)}; q = cancel]: ").strip()
    if raw.lower() == "q":
        print("Cancelled. Existing settings are unchanged.")
        return 0
    try:
        index = int(raw or len(options)) - 1
        if index < 0 or index >= len(options):
            raise ValueError()
        choice = options[index]
    except ValueError:
        print("Invalid choice. Re-run setup to choose a listed model.")
        return 1
    print(f"\nDownload {choice.name} (~{choice.download_gb:g} GB) from Ollama and Whisper {choice.whisper} (up to 0.2 GB) from Hugging Face?")
    print("Internet is needed for this setup. Afterwards chat and voice recognition run on this computer, with no API key or cloud fallback.")
    if input_fn("Download and configure local mode? [y/N]: ").strip().lower() not in {"y", "yes"}:
        print("No downloads started and no settings changed. Run setup again when ready.")
        return 0
    try:
        install(choice)
    except (RouterClientError, OSError, subprocess.SubprocessError, ImportError) as exc:
        print(f"Setup incomplete: {exc}")
        print("Existing settings were preserved. Fix the problem above and re-run setup.")
        return 1
    except Exception:
        print("The speech-model download or loading check failed. Check internet access and free space, then re-run setup. Existing settings were preserved.")
        return 1
    print(f"\nReady: {choice.name} + offline Whisper {choice.whisper}. Settings saved to {CONFIG_PATH}.")
    print("Start JARVIS to talk. Allow microphone access when asked. Web searches and opening websites still require internet.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recommend and set up local JARVIS models")
    parser.add_argument("--recommend", action="store_true", help="show RAM recommendations without downloads or changes")
    args = parser.parse_args()
    try:
        raise SystemExit(run_setup(recommend_only=args.recommend))
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled; re-run it when ready.")
        raise SystemExit(1)
