"""RAM-aware setup policy. Memory figures are conservative estimates, not benchmarks."""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ModelChoice:
    name: str
    minimum_ram_gib: float
    working_memory_gib: float  # Includes a small local speech model and 2K context.
    download_gb: float
    whisper: str


# Download sizes checked against Ollama's Qwen3 library on 2026-10-31.
# RAM thresholds are JARVIS policy, NOT official Ollama minimum requirements.
MODELS = (
    ModelChoice("qwen3:0.6b", 4, 2, 0.523, "tiny.en"),
    ModelChoice("qwen3:1.7b", 8, 3, 1.4, "tiny.en"),
    ModelChoice("qwen3:4b", 16, 5.5, 2.5, "base.en"),
    ModelChoice("qwen3:8b", 32, 9, 5.2, "base.en"),
)


@dataclass(frozen=True)
class Memory:
    total_gib: float | None
    available_gib: float | None


def detect_memory() -> Memory:
    try:
        import psutil
        memory = psutil.virtual_memory()
        return Memory(memory.total / 1024**3, memory.available / 1024**3)
    except (ImportError, OSError, RuntimeError, AttributeError):
        return Memory(None, None)


def choices_for(memory: Memory) -> list[ModelChoice]:
    total, available = memory.total_gib, memory.available_gib
    if total is None or not math.isfinite(total) or total <= 0:
        return []
    if available is not None and (not math.isfinite(available) or available < 0):
        return []
    # Leave 2 GiB for the OS, and 1 GiB of currently available RAM untouched.
    budget = min(total - 2, available - 1) if available is not None else total - 2
    return [model for model in MODELS
            if total >= model.minimum_ram_gib and budget >= model.working_memory_gib]


def describe(memory: Memory) -> str:
    if memory.total_gib is None:
        return "RAM detection unavailable. Re-run setup after installing psutil; no model is recommended yet."
    free = f"{memory.available_gib:.1f} GiB currently available" if memory.available_gib is not None else "available RAM unknown"
    lines = [f"Your computer: {memory.total_gib:.1f} GiB total RAM; {free}."]
    capacity_choices = choices_for(Memory(memory.total_gib, None))
    if capacity_choices:
        lines.append(f"Installed-RAM starting point: {capacity_choices[-1].name}; enough available memory is also needed.")
    choices = choices_for(memory)
    if choices:
        best = choices[-1]
        lines += [f"Recommended: {best.name} (about {best.download_gb:g} GB download).",
                  f"Local speech recognition: Whisper {best.whisper} (up to 0.2 GB extra).",
                  f"Download command: ollama pull {best.name}",
                  "Smaller options: " + (", ".join(m.name for m in choices[:-1]) or "none in this tier")]
    else:
        lines.append("No model fits the current memory budget. Close other apps and check again; under 4 GiB is not recommended for local voice AI.")
    lines.append("Estimates reserve memory for the OS and voice recognition at a 2,048-token context. CPU/GPU speed, other apps, and model changes affect performance; RAM alone does not guarantee fast replies.")
    return "\n".join(lines)
