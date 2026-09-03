from __future__ import annotations

import argparse
import datetime as dt
import os
import platform
import re
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus, urlparse

try:
    import pyautogui
except Exception:
    pyautogui = None

try:
    import pyttsx3
except Exception:
    pyttsx3 = None

try:
    import speech_recognition as sr
except Exception:
    sr = None

from brain import Brain
from explorer import Explorer
from router_client import RouterClientError


ASSISTANT_NAME = "Jarvis"
BASE_DIR = Path(__file__).resolve().parent
SYSTEM = platform.system()
SILENT = os.getenv("JARVIS_SILENT", "").lower() in {"1", "true", "yes"}
SHOW_ROUTE = os.getenv("JARVIS_SHOW_ROUTE", "").lower() in {"1", "true", "yes"}

WEBSITES = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "google drive": "https://drive.google.com",
    "drive": "https://drive.google.com",
    "google classroom": "https://classroom.google.com",
    "classroom": "https://classroom.google.com",
}

MAC_APP_ALIASES = {
    "calendar": "Calendar",
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "finder": "Finder",
    "notes": "Notes",
    "notion": "Notion",
    "notion calendar": "Notion Calendar",
    "safari": "Safari",
    "settings": "System Settings",
    "system settings": "System Settings",
    "terminal": "Terminal",
    "textedit": "TextEdit",
}


def init_voice_engine():
    if SYSTEM == "Darwin" or pyttsx3 is None:
        return None
    try:
        driver = "sapi5" if SYSTEM == "Windows" else None
        engine = pyttsx3.init(driver) if driver else pyttsx3.init()
        voices = engine.getProperty("voices")
        if voices:
            engine.setProperty("voice", voices[0].id)
        engine.setProperty("rate", 170)
        return engine
    except Exception:
        return None


VOICE_ENGINE = init_voice_engine()


def speak(text: str) -> None:
    print(f"{ASSISTANT_NAME}: {text}")
    if SILENT:
        return

    try:
        spoken = text_for_speech(text)
        if not spoken:
            return
        if SYSTEM == "Darwin" and shutil.which("say"):
            subprocess.run(["say", spoken], check=False)
        elif VOICE_ENGINE is not None:
            VOICE_ENGINE.say(spoken)
            VOICE_ENGINE.runAndWait()
    except Exception:
        pass


def text_for_speech(text: str, max_characters: int = 500) -> str:
    """Turn display text into a short, natural spoken response."""
    had_code = bool(re.search(r"```.*?```", text, flags=re.DOTALL))
    cleaned = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    cleaned = re.sub(r"[`*_#>|]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if had_code:
        cleaned = f"{cleaned} I've displayed the code on screen.".strip()
    if len(cleaned) <= max_characters:
        return cleaned
    shortened = cleaned[:max_characters].rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{shortened}. I've displayed the rest on screen."


def take_voice_command(brain: Brain) -> tuple[str | None, bool]:
    """Capture microphone audio and transcribe it through the private router."""
    if sr is None:
        speak("Voice recognition is not installed. Run the setup file first.")
        return None, True

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    try:
        with sr.Microphone() as source:
            print("Listening...")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=6, phrase_time_limit=12)
        query = brain.transcribe(audio.get_wav_data(convert_rate=16_000, convert_width=2))
        print(f"You: {query}")
        return query.strip(), False
    except sr.WaitTimeoutError:
        print("No speech detected.")
    except RouterClientError as exc:
        speak(f"Speech recognition is unavailable. {exc}")
        return None, True
    except (AttributeError, OSError) as exc:
        speak(f"Microphone unavailable: {exc}")
        return None, True
    return None, False


def help_text() -> str:
    return (
        "Commands:\n"
        "- open <app, website, or file>\n"
        "- find <file>\n"
        "- search <topic> or search <topic> on YouTube\n"
        "- check my calendar\n"
        "- time, date, screenshot, minimize, volume up/down, mute\n"
        "- ask a question naturally\n"
        "- mode text or mode voice\n"
        "- check\n"
        "- quit"
    )


def normalize_command(raw: str) -> str:
    command = raw.strip()
    command = re.sub(r"^(?:hey\s+)?jarvis[,:]?\s*", "", command, flags=re.IGNORECASE)
    command = re.sub(r"^hey[,:]?\s+", "", command, flags=re.IGNORECASE)
    command = re.sub(
        r"^(?:(?:can|could|would|will)\s+you|i\s+want\s+you\s+to)\s+",
        "",
        command,
        flags=re.IGNORECASE,
    )
    command = re.sub(r"^please\s+", "", command, flags=re.IGNORECASE)
    command = re.sub(r"\s+please[.!?]?\s*$", "", command, flags=re.IGNORECASE)
    return command.strip()


def parse_local_intent(raw: str) -> tuple[str, str]:
    """Classify commands that can be completed safely on the local computer."""
    command = normalize_command(raw)
    lower = command.casefold().strip(" .!?")

    if lower in {"quit", "exit", "stop", "power down", "goodbye"}:
        return "quit", ""
    if lower in {"help", "what can you do", "show commands"}:
        return "help", ""
    if lower in {"time", "what time is it", "tell me the time", "current time"}:
        return "time", ""
    if lower in {
        "date",
        "what is the date",
        "what's the date",
        "what day is it",
        "today's date",
        "tell me the date",
        "tell me the date today",
        "tell me today's date",
    }:
        return "date", ""
    if lower in {
        "check my calendar",
        "look at my calendar",
        "look for calendar",
        "show my calendar",
        "what's on my calendar",
        "what is on my calendar",
        "read my calendar",
        "calendar events",
        "today's events",
    }:
        return "calendar", ""
    if lower in {"screenshot", "take a screenshot", "capture the screen"}:
        return "screenshot", ""
    if lower in {"minimize", "minimize this", "minimize the window"}:
        return "minimize", ""
    if lower in {"volume up", "turn the volume up", "increase the volume"}:
        return "volume up", ""
    if lower in {"volume down", "turn the volume down", "decrease the volume"}:
        return "volume down", ""
    if lower in {"mute", "mute the volume", "mute my mac", "mute my computer"}:
        return "mute", ""
    if lower in {"check", "system check", "run a system check", "diagnostics"}:
        return "check", ""
    if lower in {"look at the app", "look at app", "open the app", "open app"}:
        return "clarify app", ""

    mode_match = re.match(r"^(?:switch to |use |mode )(text|voice)(?: mode)?$", lower)
    if mode_match:
        return "mode", mode_match.group(1)

    open_match = re.match(r"^(?:open|launch|start)(?: up)?\s+(.+)$", command, flags=re.IGNORECASE)
    if open_match:
        target = re.sub(r"\s+for me[.!?]?\s*$", "", open_match.group(1), flags=re.IGNORECASE)
        target = re.sub(r"^the\s+", "", target, flags=re.IGNORECASE)
        return "open", target.strip()

    find_match = re.match(
        r"^(?:find|locate)(?:\s+the)?(?:\s+file)?\s+(.+)$",
        command,
        flags=re.IGNORECASE,
    )
    if find_match:
        target = re.sub(r"\s+for me[.!?]?\s*$", "", find_match.group(1), flags=re.IGNORECASE)
        return "find", target.strip()

    search_match = re.match(r"^(?:search|look up|google)\s+(.+)$", command, flags=re.IGNORECASE)
    if search_match:
        return "search", search_match.group(1).strip()

    visit_match = re.match(r"^(?:go to|visit)\s+(.+)$", command, flags=re.IGNORECASE)
    if visit_match:
        return "open", visit_match.group(1).strip()

    if lower.startswith("ask "):
        return "chat", command.split(" ", 1)[1].strip()
    return "chat", command


def open_path(path: str | Path) -> None:
    resolved = str(Path(path).expanduser())
    if SYSTEM == "Windows":
        os.startfile(resolved)  # type: ignore[attr-defined]
    elif SYSTEM == "Darwin":
        subprocess.run(["open", resolved], check=True)
    else:
        subprocess.run(["xdg-open", resolved], check=True)


def open_url(url: str, browser: str | None = None) -> bool:
    try:
        if SYSTEM == "Darwin" and browser:
            app_name = MAC_APP_ALIASES.get(browser.casefold(), browser)
            result = subprocess.run(
                ["open", "-a", app_name, url],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return result.returncode == 0
        return bool(webbrowser.open(url))
    except (OSError, subprocess.SubprocessError):
        return False


def looks_like_website(value: str) -> bool:
    candidate = value.strip()
    if candidate.startswith(("http://", "https://")):
        return True
    parsed = urlparse(f"https://{candidate}")
    return bool(parsed.hostname and "." in parsed.hostname and " " not in candidate)


def website_url(value: str) -> str:
    candidate = value.strip()
    return candidate if candidate.startswith(("http://", "https://")) else f"https://{candidate}"


def handle_search(request: str) -> str:
    cleaned = request.strip().rstrip(".?!")
    browser = None
    browser_match = re.search(
        r"\s+(?:in|using)\s+(?:the\s+)?(Safari|Chrome|Google Chrome)$",
        cleaned,
        re.IGNORECASE,
    )
    if browser_match:
        browser = browser_match.group(1)
        cleaned = cleaned[: browser_match.start()].strip()

    youtube_for = re.match(r"^youtube\s+for\s+(.+)$", cleaned, re.IGNORECASE)
    on_youtube = re.match(r"^(.+?)\s+on\s+youtube$", cleaned, re.IGNORECASE)
    if youtube_for or on_youtube:
        query = (youtube_for or on_youtube).group(1).strip()  # type: ignore[union-attr]
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        opened = open_url(url, browser)
        return f"Searching YouTube for {query}." if opened else "I could not open the YouTube search."

    google_for = re.match(r"^(?:google\s+)?for\s+(.+)$", cleaned, re.IGNORECASE)
    if google_for:
        cleaned = google_for.group(1).strip()

    known_website = WEBSITES.get(cleaned.casefold())
    if known_website:
        opened = open_url(known_website, browser)
        return f"Opening {cleaned}." if opened else f"I could not open {cleaned}."

    if looks_like_website(cleaned):
        opened = open_url(website_url(cleaned), browser)
        return f"Opening {cleaned}." if opened else f"I could not open {cleaned}."

    url = f"https://www.google.com/search?q={quote_plus(cleaned)}"
    opened = open_url(url, browser)
    return f"Searching the web for {cleaned}." if opened else "I could not open the web search."


def open_application(name: str) -> bool:
    cleaned = name.strip()
    if not cleaned:
        return False
    try:
        if SYSTEM == "Darwin":
            app_name = MAC_APP_ALIASES.get(cleaned.casefold(), cleaned)
            result = subprocess.run(
                ["open", "-a", app_name],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return result.returncode == 0
        if SYSTEM == "Windows":
            result = subprocess.run(
                ["cmd", "/c", "start", "", cleaned],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return result.returncode == 0
        result = subprocess.run(
            ["gtk-launch", cleaned],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def ensure_index(explorer: Explorer, state: dict[str, bool]) -> None:
    if not state["ready"]:
        explorer.scan_files()
        state["ready"] = True


def find_target(target: str, explorer: Explorer, state: dict[str, bool]) -> str:
    ensure_index(explorer, state)
    path = explorer.find_file(target)
    return path or ""


def handle_open(target: str, explorer: Explorer, state: dict[str, bool]) -> str:
    cleaned = re.sub(r"^the\s+", "", target.strip(), flags=re.IGNORECASE)
    if not cleaned:
        return "Tell me what to open."

    website = WEBSITES.get(cleaned.casefold())
    if website:
        return f"Opening {cleaned}." if open_url(website) else f"I could not open {cleaned}."

    if looks_like_website(cleaned):
        return f"Opening {cleaned}." if open_url(website_url(cleaned)) else f"I could not open {cleaned}."

    possible_path = Path(cleaned).expanduser()
    if possible_path.exists():
        try:
            open_path(possible_path)
            return f"Opening {possible_path.name}."
        except Exception as exc:
            return f"I found it, but could not open it: {exc}"

    if open_application(cleaned):
        return f"Opening {cleaned}."

    path = find_target(cleaned, explorer, state)
    if not path:
        return f"I could not find an application or file named {cleaned}."
    try:
        open_path(path)
        return f"Opening {Path(path).name}."
    except Exception as exc:
        return f"I found {Path(path).name}, but could not open it: {exc}"


def take_screenshot() -> str:
    pictures = Path.home() / "Pictures"
    pictures.mkdir(exist_ok=True)
    path = pictures / f"screenshot_{dt.datetime.now():%Y%m%d_%H%M%S}.png"
    try:
        if SYSTEM == "Darwin" and Path("/usr/sbin/screencapture").exists():
            subprocess.run(["/usr/sbin/screencapture", "-x", str(path)], check=True)
        elif pyautogui is not None:
            pyautogui.screenshot(str(path))
        else:
            return "Screenshot support is not available."
        return f"Screenshot saved as {path.name} in Pictures."
    except Exception as exc:
        return f"Screenshot failed: {exc}"


def minimize_window() -> str:
    try:
        if SYSTEM == "Darwin":
            subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to keystroke "m" using command down'],
                check=True,
            )
        elif pyautogui is not None:
            pyautogui.hotkey("win", "d")
        else:
            return "Window control is not available."
        return "Window minimized."
    except Exception as exc:
        return f"Could not minimize the window: {exc}"


def change_volume(command: str) -> str:
    try:
        if SYSTEM == "Darwin":
            scripts = {
                "volume up": "set volume output volume ((output volume of (get volume settings)) + 10)",
                "volume down": "set volume output volume ((output volume of (get volume settings)) - 10)",
                "mute": "set volume with output muted",
            }
            subprocess.run(["osascript", "-e", scripts[command]], check=True)
        elif pyautogui is not None:
            keys = {"volume up": "volumeup", "volume down": "volumedown", "mute": "volumemute"}
            count = 3 if command != "mute" else 1
            for _ in range(count):
                pyautogui.press(keys[command])
        else:
            return "Volume control is not available."
        return f"Executed {command}."
    except Exception as exc:
        return f"Volume control failed: {exc}"


def calendar_summary() -> str:
    if SYSTEM != "Darwin":
        return "Reading calendar events is currently available on macOS only."

    script = r'''
tell application "Calendar"
    set dayStart to current date
    set time of dayStart to 0
    set dayEnd to dayStart + (1 * days)
    set eventLines to {}
    repeat with calendarItem in calendars
        set matchingEvents to (every event of calendarItem whose start date < dayEnd and end date > dayStart)
        repeat with eventItem in matchingEvents
            set eventTitle to summary of eventItem
            if allday event of eventItem then
                set eventTime to "all day"
            else
                set eventTime to time string of (start date of eventItem)
            end if
            set end of eventLines to eventTime & " — " & eventTitle
        end repeat
    end repeat
    if (count of eventLines) is 0 then return ""
    set AppleScript's text item delimiters to linefeed
    return eventLines as text
end tell
'''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"I could not read Calendar: {exc}"

    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "permission was denied"
        return f"I could not read Calendar because {detail}. Allow Calendar access in Privacy & Security, then try again."
    events = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not events:
        return "You have no events in Apple Calendar today."
    if len(events) == 1:
        return f"You have one event today: {events[0]}."
    return "Today's events are: " + "; ".join(events) + "."


def diagnostic_text(brain: Brain) -> str:
    microphone_status = "installed" if sr is not None else "not installed"
    router_status = "ready" if brain.router_is_ready() else f"offline ({brain.last_error})"
    return (
        f"System: {SYSTEM}. Microphone capture: {microphone_status}. "
        f"Multi-model router and Whisper: {router_status}. Local commands: ready."
    )


def current_time_text() -> str:
    current = dt.datetime.now()
    hour = current.strftime("%I").lstrip("0") or "0"
    return f"{hour}:{current:%M %p}"


def run(start_mode: str = "text") -> None:
    brain = Brain()
    explorer = Explorer()
    explorer_state = {"ready": False}
    mode = start_mode

    speak("Jarvis is ready.")
    if mode == "voice" and sr is None:
        speak("Voice recognition is not installed, so I am starting in text mode.")
        mode = "text"
    speak("Say or type help to see commands.")

    while True:
        if mode == "voice":
            captured, should_fallback = take_voice_command(brain)
            if should_fallback:
                mode = "text"
                speak("Switching to text mode. You can type mode voice to try again.")
                continue
            query = captured or ""
            if not query:
                continue
        else:
            try:
                query = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                query = "quit"

        if not query:
            continue
        intent, payload = parse_local_intent(query)

        if intent == "quit":
            speak("Powering down.")
            return
        if intent == "help":
            speak(help_text())
        elif intent == "mode":
            if payload == "voice" and sr is None:
                speak("Voice recognition is not installed. Run setup first.")
            else:
                mode = payload
                speak(f"Input mode set to {mode}.")
        elif intent == "open":
            speak(handle_open(payload, explorer, explorer_state))
        elif intent == "find":
            path = find_target(payload, explorer, explorer_state)
            speak(f"I found it at {path}" if path else f"I could not find {payload}.")
        elif intent == "search":
            speak(handle_search(payload))
        elif intent == "calendar":
            speak(calendar_summary())
        elif intent == "time":
            speak(f"The time is {current_time_text()}.")
        elif intent == "date":
            speak(f"Today is {dt.datetime.now():%A, %B %d, %Y}.")
        elif intent == "screenshot":
            speak(take_screenshot())
        elif intent == "minimize":
            speak(minimize_window())
        elif intent in {"volume up", "volume down", "mute"}:
            speak(change_volume(intent))
        elif intent == "check":
            speak(diagnostic_text(brain))
        elif intent == "clarify app":
            speak("Which app should I open? For example, say open Notion Calendar or open Safari.")
        else:
            answer = brain.ask(payload)
            speak(answer)
            if SHOW_ROUTE and brain.last_route:
                print(f"[Router: {brain.last_route} → {brain.last_model}]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Jarvis voice and desktop assistant")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--voice", action="store_true", help="start in voice mode")
    mode.add_argument("--text", action="store_true", help="start in text mode")
    parser.add_argument("--silent", action="store_true", help="disable spoken output")
    parser.add_argument("--diagnose", action="store_true", help="show readiness and exit")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.silent:
        SILENT = True
    if args.diagnose:
        print(diagnostic_text(Brain()))
        raise SystemExit(0)
    run(start_mode="voice" if args.voice else "text")
