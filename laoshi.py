#!/usr/bin/env python3
import requests
import argparse
import tempfile # Will be used differently or less
import os
import logging # For underlying libraries, not primary UI
from playsound import playsound
import csv
import random
import sys
import readchar # Added for arrow key input
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.theme import Theme
from rich.prompt import Prompt, Confirm
from rich.style import Style
from rich.padding import Padding
from rich.align import Align

# --- Configuration ---
KOKORO_API_BASE_URL = "http://localhost:8880"
KOKORO_SPEECH_ENDPOINT = f"{KOKORO_API_BASE_URL}/v1/audio/speech"
DEFAULT_KOKORO_VOICE = "zf_xiaoxiao"
DEFAULT_KOKORO_LANG_CODE = "z"
DEFAULT_KOKORO_SPEED = 1.0
SLOWER_KOKORO_SPEED = 0.7 # Slower speed for better clarity
EXTRA_SLOW_KOKORO_SPEED = 0.5 # Extra slow speed for very clear pronunciation

# Audio Filename Suffixes for different speeds
DEFAULT_SPEED_SUFFIX = "_default"
SLOWER_SPEED_SUFFIX = "_slow"
EXTRA_SLOW_SPEED_SUFFIX = "_slower"

# Speed configurations for dictation pro
SPEED_CONFIGURATIONS = [
    {"value": EXTRA_SLOW_KOKORO_SPEED, "suffix": EXTRA_SLOW_SPEED_SUFFIX, "display_name": f"x{EXTRA_SLOW_KOKORO_SPEED}"},
    {"value": SLOWER_KOKORO_SPEED, "suffix": SLOWER_SPEED_SUFFIX, "display_name": f"x{SLOWER_KOKORO_SPEED}"},
    {"value": DEFAULT_KOKORO_SPEED, "suffix": DEFAULT_SPEED_SUFFIX, "display_name": f"x{DEFAULT_KOKORO_SPEED}"},
]

AUDIO_DIR = "audio" # Base audio directory
AUDIO_CHAR_DIR = os.path.join(AUDIO_DIR, "characters") # For word audio
AUDIO_PRO_DIR = os.path.join(AUDIO_DIR, "pro")       # For sentence audio
VOCAB_FILE = "vocabulary.csv"
VOCAB_FIELDS = ["character", "pinyin", "character_meaning", "audio_file_name"]
SENTENCES_FILE = "sentences.csv" # New CSV for sentences
SENTENCES_FIELDS = ["sentence_text", "audio_file_name"] # Fields for sentences.csv

# --- Rich Console Setup for Hacker UI ---
custom_theme = Theme({
    "default": "bright_green on black",
    "prompt": "bright_yellow on black",
    "prompt.choices": "cyan on black",
    "prompt.default": "bright_cyan on black",
    "title": "bold bright_green on black",
    "error": "bold bright_red on black",
    "warning": "yellow on black",
    "info": "bright_cyan on black",
    "highlight": "black on bright_green",
    "border": "green on black",
    "disabled": "dim green on black",
    "large_char": Style(bold=True) # Approximation, actual size depends on terminal
})
console = Console(theme=custom_theme, style="default")

# --- Setup Logging (for library/deep debug if needed) ---
logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(module)s - %(message)s', level=logging.WARNING)
# ARGS will be defined in main

# --- Kokoro TTS Function (Adapted from previous version) ---
def generate_tts_audio(text_input, voice, lang_code, speed, debug_mode=False):
    """
    Calls the Kokoro TTS API to generate audio from text.
    Returns:
        bytes: The audio content in MP3 format, or None if an error occurred.
    """
    payload = {
        "model": "kokoro",
        "input": text_input,
        "voice": voice,
        "response_format": "mp3",
        "download_format": "mp3",
        "speed": speed,
        "stream": False,
        "return_download_link": False,
        "lang_code": lang_code,
        "normalization_options": {
            "normalize": True, "unit_normalization": False, "url_normalization": True,
            "email_normalization": True, "optional_pluralization_normalization": True,
            "phone_normalization": True
        }
    }

    if debug_mode:
        console.print(f"[DEBUG] Kokoro TTS Request: {KOKORO_SPEECH_ENDPOINT}", style="dim cyan")
        console.print(f"[DEBUG] Kokoro TTS Payload: {payload}", style="dim cyan")
    try:
        response = requests.post(KOKORO_SPEECH_ENDPOINT, json=payload, timeout=60)
        if debug_mode:
            console.print(f"[DEBUG] Kokoro Response Status Code: {response.status_code}", style="dim cyan")

        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '').lower()
            if 'audio/mpeg' in content_type or 'application/octet-stream' in content_type or not content_type:
                if debug_mode:
                    console.print("Kokoro TTS: Successfully received audio data.", style="info")
                return response.content
            else:
                console.print(f"[WARNING] Kokoro TTS: Received unexpected Content-Type: {content_type}. Response: {response.text[:200]}", style="warning")
                return None
        else:
            error_details = response.text
            try:
                error_json = response.json()
                error_details = error_json.get('detail', error_details)
            except ValueError:
                pass 
            console.print(f"[ERROR] Kokoro TTS API Error (Status {response.status_code}): {error_details}", style="error")
            return None
    except requests.exceptions.RequestException as e:
        console.print(f"[ERROR] Kokoro TTS Request failed: {e}", style="error")
        return None

# --- Vocabulary Management ---
def sanitize_filename(name):
    """Removes or replaces characters not suitable for filenames."""
    name = name.replace(" ", "_")
    return "".join(c for c in name if c.isalnum() or c in ['_', '-']).rstrip()

def load_vocab(debug_mode=False):
    """Loads vocabulary from the CSV file."""
    if not os.path.exists(VOCAB_FILE):
        return []
    try:
        with open(VOCAB_FILE, 'r', encoding='utf-8', newline='') as f:
            # Ensure all fields are present for robust loading, provide defaults if necessary
            reader = csv.DictReader(f)
            vocab = []
            for row in reader:
                # Ensure all expected keys are present, defaulting to None or empty string if not
                # This helps with partially migrated CSVs, though ideally, migration is complete.
                entry = {field: row.get(field) for field in VOCAB_FIELDS}
                vocab.append(entry)
            if debug_mode:
                console.print(f"[DEBUG] Loaded {len(vocab)} entries from {VOCAB_FILE}", style="dim cyan")
            return vocab
    except Exception as e:
        console.print(f"[ERROR] Could not load vocabulary from {VOCAB_FILE}: {e}", style="error")
        return []

def save_vocab_entry(character, pinyin, character_meaning, audio_file_name, debug_mode=False):
    """Saves a single vocabulary entry to the CSV file."""
    file_exists = os.path.exists(VOCAB_FILE)
    try:
        with open(VOCAB_FILE, 'a', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=VOCAB_FIELDS)
            if not file_exists or os.path.getsize(VOCAB_FILE) == 0:
                writer.writeheader()
            writer.writerow({
                "character": character,
                "pinyin": pinyin,
                "character_meaning": character_meaning,
                "audio_file_name": audio_file_name
            })
            if debug_mode:
                console.print(f"[DEBUG] Saved entry: {character}, {pinyin}, {character_meaning}, {audio_file_name}", style="dim cyan")
    except Exception as e:
        console.print(f"[ERROR] Could not save vocabulary entry to {VOCAB_FILE}: {e}", style="error")

def load_sentences(debug_mode=False):
    """Loads sentences from the sentences.csv file."""
    if not os.path.exists(SENTENCES_FILE):
        return []
    try:
        with open(SENTENCES_FILE, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            sentences = []
            for row in reader:
                entry = {field: row.get(field) for field in SENTENCES_FIELDS}
                sentences.append(entry)
            if debug_mode:
                console.print(f"[DEBUG] Loaded {len(sentences)} sentences from {SENTENCES_FILE}", style="dim cyan")
            return sentences
    except Exception as e:
        console.print(f"[ERROR] Could not load sentences from {SENTENCES_FILE}: {e}", style="error")
        return []

def save_sentence_entry(sentence_text, audio_file_name, debug_mode=False):
    """Saves a single sentence entry to the sentences.csv file."""
    file_exists = os.path.exists(SENTENCES_FILE)
    try:
        with open(SENTENCES_FILE, 'a', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=SENTENCES_FIELDS)
            if not file_exists or os.path.getsize(SENTENCES_FILE) == 0:
                writer.writeheader()
            writer.writerow({
                "sentence_text": sentence_text,
                "audio_file_name": audio_file_name
            })
            if debug_mode:
                console.print(f"[DEBUG] Saved sentence entry: {sentence_text}, {audio_file_name}", style="dim cyan")
    except Exception as e:
        console.print(f"[ERROR] Could not save sentence entry to {SENTENCES_FILE}: {e}", style="error")


def ensure_audio_files_exist(args):
    """Checks vocabulary for missing audio files and attempts to generate them at multiple speeds."""
    console.print(Panel("Checking Word Audio File Integrity (Multi-Speed)...", title="[title]System Check (Words)[/title]", border_style="border"), style="title")
    vocab = load_vocab(args.debug)
    if not vocab:
        console.print("[INFO] Word vocabulary is empty. No audio files to check.", style="info")
        return

    items_all_speeds_found = 0
    items_had_missing_speeds = 0 # Counts items for which at least one speed was missing and generation was attempted/needed
    individual_files_generated = 0
    individual_files_failed_generation = 0
    skipped_incomplete_csv = 0

    speeds_to_generate = {
        DEFAULT_SPEED_SUFFIX: args.kokoro_speed,
        SLOWER_SPEED_SUFFIX: SLOWER_KOKORO_SPEED,
        EXTRA_SLOW_SPEED_SUFFIX: EXTRA_SLOW_KOKORO_SPEED
    }

    for entry in vocab:
        character = entry.get('character')
        base_audio_file_name = entry.get('audio_file_name') 

        if not character or not base_audio_file_name:
            if args.debug:
                console.print(f"[DEBUG] Skipping entry with missing character or base_audio_file_name: {entry}", style="dim cyan")
            skipped_incomplete_csv +=1
            continue

        base_name_no_ext, ext = os.path.splitext(base_audio_file_name)
        if not ext: 
            ext = ".mp3"
            # base_audio_file_name = base_name_no_ext + ext # CSV stores base, so this isn't strictly needed here

        all_speeds_present_for_this_item = True
        generation_attempted_for_this_item = False

        for suffix, speed_value in speeds_to_generate.items():
            specific_audio_filename = f"{base_name_no_ext}{suffix}{ext}"
            audio_path = os.path.join(AUDIO_CHAR_DIR, specific_audio_filename)

            if not os.path.exists(audio_path):
                all_speeds_present_for_this_item = False
                generation_attempted_for_this_item = True # Mark that we will attempt generation
                
                console.print(f"[WARNING] Missing audio for '{character}' (speed {suffix}, file: {specific_audio_filename}). Generating...", style="warning")
                audio_data = generate_tts_audio(character, args.kokoro_voice, args.kokoro_lang, speed_value, args.debug)
                
                if audio_data:
                    try:
                        os.makedirs(os.path.dirname(audio_path), exist_ok=True) # Ensure dir exists
                        with open(audio_path, "wb") as f:
                            f.write(audio_data)
                        console.print(f"[INFO] Generated: {audio_path}", style="info")
                        individual_files_generated += 1
                    except Exception as e:
                        console.print(f"[ERROR] Could not save {audio_path}: {e}", style="error")
                        individual_files_failed_generation += 1
                else:
                    console.print(f"[ERROR] Failed to generate audio for '{character}' (speed {suffix}).", style="error")
                    individual_files_failed_generation += 1
        
        if all_speeds_present_for_this_item:
            items_all_speeds_found += 1
        elif generation_attempted_for_this_item: # If not all present AND we tried to generate
            items_had_missing_speeds +=1


    summary_messages = [
        f"Word Audio File Check Complete (Multi-Speed):",
        f"  - Items with all audio speeds already present: {items_all_speeds_found}",
        f"  - Items that had missing speed(s) (generation attempted): {items_had_missing_speeds}",
        f"  - Total individual audio files successfully generated: {individual_files_generated}",
        f"  - Total individual audio files failed to generate/save: {individual_files_failed_generation}"
    ]
    if skipped_incomplete_csv > 0:
        summary_messages.append(f"  - Skipped (incomplete CSV data): {skipped_incomplete_csv}")

    console.print(Panel("\n".join(summary_messages), title="[title]Word Audio Check Summary[/title]", border_style="border"), style="info")


def ensure_sentence_audio_files_exist(args):
    """Checks sentence vocabulary for missing audio files and attempts to generate them at multiple speeds."""
    console.print(Panel("Checking Sentence Audio File Integrity (Multi-Speed)...", title="[title]System Check (Sentences)[/title]", border_style="border"), style="title")
    sentences = load_sentences(args.debug)
    if not sentences:
        console.print("[INFO] Sentence vocabulary is empty. No audio files to check.", style="info")
        return

    items_all_speeds_found = 0
    items_had_missing_speeds = 0
    individual_files_generated = 0
    individual_files_failed_generation = 0
    skipped_incomplete_csv = 0

    speeds_to_generate = {
        DEFAULT_SPEED_SUFFIX: args.kokoro_speed,
        SLOWER_SPEED_SUFFIX: SLOWER_KOKORO_SPEED,
        EXTRA_SLOW_SPEED_SUFFIX: EXTRA_SLOW_KOKORO_SPEED
    }

    for entry in sentences:
        sentence_text = entry.get('sentence_text')
        base_audio_file_name = entry.get('audio_file_name')

        if not sentence_text or not base_audio_file_name:
            if args.debug:
                console.print(f"[DEBUG] Skipping sentence entry with missing text or base_audio_file_name: {entry}", style="dim cyan")
            skipped_incomplete_csv +=1
            continue

        base_name_no_ext, ext = os.path.splitext(base_audio_file_name)
        if not ext: ext = ".mp3"

        all_speeds_present_for_this_item = True
        generation_attempted_for_this_item = False

        for suffix, speed_value in speeds_to_generate.items():
            specific_audio_filename = f"{base_name_no_ext}{suffix}{ext}"
            audio_path = os.path.join(AUDIO_PRO_DIR, specific_audio_filename)

            if not os.path.exists(audio_path):
                all_speeds_present_for_this_item = False
                generation_attempted_for_this_item = True
                console.print(f"[WARNING] Missing audio for sentence '{sentence_text[:30]}...' (speed {suffix}, file: {specific_audio_filename}). Generating...", style="warning")
                
                audio_data = generate_tts_audio(sentence_text, args.kokoro_voice, args.kokoro_lang, speed_value, args.debug)
                
                if audio_data:
                    try:
                        os.makedirs(os.path.dirname(audio_path), exist_ok=True) # Ensure dir exists
                        with open(audio_path, "wb") as f:
                            f.write(audio_data)
                        console.print(f"[INFO] Generated: {audio_path}", style="info")
                        individual_files_generated += 1
                    except Exception as e:
                        console.print(f"[ERROR] Could not save {audio_path}: {e}", style="error")
                        individual_files_failed_generation += 1
                else:
                    console.print(f"[ERROR] Failed to generate audio for sentence '{sentence_text[:30]}...' (speed {suffix}).", style="error")
                    individual_files_failed_generation += 1
        
        if all_speeds_present_for_this_item:
            items_all_speeds_found += 1
        elif generation_attempted_for_this_item:
            items_had_missing_speeds +=1

    summary_messages = [
        f"Sentence Audio File Check Complete (Multi-Speed):",
        f"  - Items with all audio speeds already present: {items_all_speeds_found}",
        f"  - Items that had missing speed(s) (generation attempted): {items_had_missing_speeds}",
        f"  - Total individual audio files successfully generated: {individual_files_generated}",
        f"  - Total individual audio files failed to generate/save: {individual_files_failed_generation}"
    ]
    if skipped_incomplete_csv > 0:
        summary_messages.append(f"  - Skipped (incomplete CSV data): {skipped_incomplete_csv}")

    console.print(Panel("\n".join(summary_messages), title="[title]Sentence Audio Check Summary[/title]", border_style="border"), style="info")


def update_word_vocab_interactive(args):
    """Handles interactive word vocabulary update, generating audio at multiple speeds."""
    console.print(Panel("Update Word Vocabulary", title="[title]Mode[/title]", border_style="border"), style="title")
    console.print("Enter word vocabulary items on one line, separated by ';'. Each item uses '|' as a field separator.", style="default")
    console.print("Format for each item: ", style="default", end="")
    console.print("chinese_character|pinyin|character_meaning|base_audio_filename_idea", style="highlight")
    console.print("Example (multiple entries on one line):", style="default")
    console.print("你好|nǐ hǎo|hello|hello_audio;学|xué|to study|study_audio", style="info")
    console.print("Type 'done' or 'exit' on a new line when finished.", style="default")

    existing_vocab = load_vocab(args.debug)
    speeds_to_generate = {
        DEFAULT_SPEED_SUFFIX: args.kokoro_speed,
        SLOWER_SPEED_SUFFIX: SLOWER_KOKORO_SPEED,
        EXTRA_SLOW_SPEED_SUFFIX: EXTRA_SLOW_KOKORO_SPEED
    }

    while True:
        try:
            user_input_line = Prompt.ask(Text("New word entries (char|pin|mean|audio_idea;...) or 'done'", style="prompt")).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nWord vocabulary update cancelled.", style="warning")
            return

        if user_input_line.lower() in ["done", "exit", "quit"]:
            break
        if not user_input_line:
            continue

        entries_on_line = [e.strip() for e in user_input_line.split(';') if e.strip()]

        if not entries_on_line:
            continue

        for entry_str in entries_on_line:
            parts = [p.strip() for p in entry_str.split('|')]
            if len(parts) != 4:
                console.print(f"[WARNING] Invalid format for entry: '{entry_str}'. Expected 4 parts separated by '|', got {len(parts)}. Skipping.", style="warning")
                continue

            char, pinyin, character_meaning, base_audio_name_idea = parts

            is_duplicate = any(voc_entry.get('character') == char for voc_entry in existing_vocab)
            if is_duplicate:
                console.print(f"[INFO] Character '{char}' already exists. Skipping.", style="info")
                continue

            console.print(f"Processing: [highlight]{char}[/] ([italic]{pinyin}[/]) - '{character_meaning}' (Audio idea: {base_audio_name_idea})", style="default")
            
            base_filename_sanitized = sanitize_filename(base_audio_name_idea)
            pinyin_sanitized = sanitize_filename(pinyin) if pinyin else "unknown_pinyin"
            
            current_audio_filenames_in_csv = {entry.get('audio_file_name') for entry in existing_vocab}
            # This is the base filename that will be stored in the CSV, e.g., "hello_audio.mp3"
            final_base_audio_filename_for_csv = f"{base_filename_sanitized}.mp3"
            counter = 1
            while final_base_audio_filename_for_csv in current_audio_filenames_in_csv:
                final_base_audio_filename_for_csv = f"{base_filename_sanitized}_{pinyin_sanitized}_{counter}.mp3"
                counter += 1

            all_speeds_generated_successfully = True
            generated_paths_for_this_item = []
            # base_name_no_ext_for_saving is the CSV filename without .mp3
            base_name_no_ext_for_saving, ext_for_saving = os.path.splitext(final_base_audio_filename_for_csv)
            if not ext_for_saving: ext_for_saving = ".mp3" # Should always have .mp3 due to above logic

            os.makedirs(AUDIO_CHAR_DIR, exist_ok=True) # Ensure directory exists

            for suffix, speed_value in speeds_to_generate.items():
                # This is the actual filename on disk, e.g., "hello_audio_default.mp3"
                specific_audio_filename_to_save = f"{base_name_no_ext_for_saving}{suffix}{ext_for_saving}"
                audio_filepath = os.path.join(AUDIO_CHAR_DIR, specific_audio_filename_to_save)
                
                console.print(f"  Generating audio for '{char}' (speed {suffix})...", style="dim default")
                audio_data = generate_tts_audio(char, args.kokoro_voice, args.kokoro_lang, speed_value, args.debug)

                if audio_data:
                    try:
                        with open(audio_filepath, "wb") as f:
                            f.write(audio_data)
                        console.print(f"  Audio for '{char}' (speed {suffix}) saved to: [info]{audio_filepath}[/]", style="default")
                        generated_paths_for_this_item.append(audio_filepath)
                    except Exception as e:
                        console.print(f"  [ERROR] Could not save audio file {audio_filepath} for '{char}' (speed {suffix}): {e}", style="error")
                        all_speeds_generated_successfully = False
                        break 
                else:
                    console.print(f"  [WARNING] Failed to generate audio for '{char}' (speed {suffix}).", style="warning")
                    all_speeds_generated_successfully = False
                    break
            
            if all_speeds_generated_successfully:
                save_vocab_entry(char, pinyin, character_meaning, final_base_audio_filename_for_csv, args.debug)
                existing_vocab.append({
                    "character": char, "pinyin": pinyin, 
                    "character_meaning": character_meaning, "audio_file_name": final_base_audio_filename_for_csv
                })
                console.print(f"Successfully added '{char}' to vocabulary with all audio speeds.", style="info")
            else:
                console.print(f"[WARNING] Failed to generate all audio speeds for '{char}'. Entry not saved. Cleaning up partial files...", style="warning")
                for path_to_delete in generated_paths_for_this_item:
                    try:
                        if os.path.exists(path_to_delete):
                           os.remove(path_to_delete)
                           console.print(f"  Deleted partially generated file: {path_to_delete}", style="dim warning")
                    except OSError as e_del:
                        console.print(f"  [ERROR] Could not delete partially generated file {path_to_delete}: {e_del}", style="error")
                        
    console.print("Word vocabulary update complete.", style="title")


def update_sentence_vocab_interactive(args):
    """Handles interactive sentence vocabulary update, generating audio at multiple speeds."""
    console.print(Panel("Update Sentence Vocabulary", title="[title]Mode[/title]", border_style="border"), style="title")
    console.print("Enter sentence items on one line, separated by ';'. Each item uses '|' as a field separator.", style="default")
    console.print("Format for each item: ", style="default", end="")
    console.print("sentence_text|base_audio_filename_idea", style="highlight")
    console.print("Example (multiple entries on one line):", style="default")
    console.print("你好吗|how_are_you_audio;谢谢你|thank_you_audio", style="info")
    console.print("The 'base_audio_filename_idea' is used to generate the actual .mp3 filename (e.g., how_are_you_audio.mp3 in CSV).", style="info")
    console.print("Type 'done' or 'exit' on a new line when finished.", style="default")

    existing_sentences = load_sentences(args.debug)
    speeds_to_generate = {
        DEFAULT_SPEED_SUFFIX: args.kokoro_speed,
        SLOWER_SPEED_SUFFIX: SLOWER_KOKORO_SPEED,
        EXTRA_SLOW_SPEED_SUFFIX: EXTRA_SLOW_KOKORO_SPEED
    }

    while True:
        try:
            user_input_line = Prompt.ask(Text("New sentence entries (sentence|audio_idea;...) or 'done'", style="prompt")).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nSentence vocabulary update cancelled.", style="warning")
            return

        if user_input_line.lower() in ["done", "exit", "quit"]:
            break
        if not user_input_line:
            continue

        entries_on_line = [e.strip() for e in user_input_line.split(';') if e.strip()]

        if not entries_on_line:
            continue

        for entry_str in entries_on_line:
            parts = [p.strip() for p in entry_str.split('|')]
            if len(parts) != 2:
                console.print(f"[WARNING] Invalid format for entry: '{entry_str}'. Expected 2 parts separated by '|', got {len(parts)}. Skipping.", style="warning")
                continue

            sentence_text, base_audio_name_idea = parts

            is_duplicate = any(sent_entry.get('sentence_text') == sentence_text for sent_entry in existing_sentences)
            if is_duplicate:
                console.print(f"[INFO] Sentence '{sentence_text[:30]}...' already exists. Skipping.", style="info")
                continue
            
            console.print(f"Processing sentence: [highlight]{sentence_text[:50]}...[/] (Audio idea: {base_audio_name_idea})", style="default")

            base_filename_sanitized = sanitize_filename(base_audio_name_idea)
            current_audio_filenames_in_csv = {entry.get('audio_file_name') for entry in existing_sentences}
            final_base_audio_filename_for_csv = f"{base_filename_sanitized}.mp3"
            counter = 1
            while final_base_audio_filename_for_csv in current_audio_filenames_in_csv:
                final_base_audio_filename_for_csv = f"{base_filename_sanitized}_{counter}.mp3" # Simpler unique name for sentences
                counter += 1

            all_speeds_generated_successfully = True
            generated_paths_for_this_item = []
            base_name_no_ext_for_saving, ext_for_saving = os.path.splitext(final_base_audio_filename_for_csv)
            if not ext_for_saving: ext_for_saving = ".mp3"

            os.makedirs(AUDIO_PRO_DIR, exist_ok=True) # Ensure directory exists

            for suffix, speed_value in speeds_to_generate.items():
                specific_audio_filename_to_save = f"{base_name_no_ext_for_saving}{suffix}{ext_for_saving}"
                audio_filepath = os.path.join(AUDIO_PRO_DIR, specific_audio_filename_to_save)

                console.print(f"  Generating audio for sentence (speed {suffix})...", style="dim default")
                audio_data = generate_tts_audio(sentence_text, args.kokoro_voice, args.kokoro_lang, speed_value, args.debug)

                if audio_data:
                    try:
                        with open(audio_filepath, "wb") as f:
                            f.write(audio_data)
                        console.print(f"  Audio for sentence (speed {suffix}) saved to: [info]{audio_filepath}[/]", style="default")
                        generated_paths_for_this_item.append(audio_filepath)
                    except Exception as e:
                        console.print(f"  [ERROR] Could not save audio file {audio_filepath} for sentence (speed {suffix}): {e}", style="error")
                        all_speeds_generated_successfully = False
                        break 
                else:
                    console.print(f"  [WARNING] Failed to generate audio for sentence (speed {suffix}).", style="warning")
                    all_speeds_generated_successfully = False
                    break
            
            if all_speeds_generated_successfully:
                save_sentence_entry(sentence_text, final_base_audio_filename_for_csv, args.debug)
                existing_sentences.append({
                    "sentence_text": sentence_text, "audio_file_name": final_base_audio_filename_for_csv
                })
                console.print(f"Successfully added sentence '{sentence_text[:30]}...' to vocabulary with all audio speeds.", style="info")
            else:
                console.print(f"[WARNING] Failed to generate all audio speeds for sentence '{sentence_text[:30]}...'. Entry not saved. Cleaning up partial files...", style="warning")
                for path_to_delete in generated_paths_for_this_item:
                    try:
                        if os.path.exists(path_to_delete):
                            os.remove(path_to_delete)
                            console.print(f"  Deleted partially generated file: {path_to_delete}", style="dim warning")
                    except OSError as e_del:
                        console.print(f"  [ERROR] Could not delete partially generated file {path_to_delete}: {e_del}", style="error")

    console.print("Sentence vocabulary update complete.", style="title")


# --- UI Functions ---
def clear_screen():
    """Clears the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_main_menu(selected_index=0):
    """Displays the main menu and returns the user's choice using arrow keys."""
    clear_screen()
    console.print(Panel("AI Chinese Language Assistant", title="[title]Main Menu[/title]", border_style="border", expand=False), justify="center")

    options = ["Dictation", "Dictation Pro", "Update Vocabulary", "Exit"] # Added "Update Vocabulary"
    current_selection = 0 # Reset to 0 or manage selected_index if passed

    while True:
        _clear_and_redraw_menu_options(options, current_selection, "Main Menu") # Pass menu title

        key = readchar.readkey()

        if key == readchar.key.UP:
            current_selection = (current_selection - 1 + len(options)) % len(options)
        elif key == readchar.key.DOWN:
            current_selection = (current_selection + 1) % len(options)
        elif key == readchar.key.ENTER:
            if current_selection == 0:
                return "dictation"
            elif current_selection == 1:
                return "dictation_pro"
            elif current_selection == 2:
                return "update_vocab" # New return value
            elif current_selection == 3:
                return "exit"
        elif key.lower() == 'q':
            return "exit"

def _clear_and_redraw_menu_options(options, selected_index, menu_title="Main Menu"): # Added menu_title parameter
    """Helper to clear and redraw menu options. Assumes title is already printed."""
    clear_screen()
    # Use the passed menu_title
    console.print(Panel(f"AI Chinese Language Assistant", title=f"[title]{menu_title}[/title]", border_style="border", expand=False), justify="center")

    for i, option in enumerate(options):
        if i == selected_index:
            console.print(Align.center(Padding(f"> {option} <", (1, 2), style="highlight")))
        else:
            console.print(Align.center(Padding(f"  {option}  ", (1, 2), style="default")))

    console.print("\nUse [yellow]↑/↓[/yellow] to navigate, [yellow]Enter[/yellow] to select, or ([yellow]q[/yellow])uit", style="prompt")


def display_dictation_start_screen(): # Retained for "Dictation" mode
    """Displays the start screen for dictation mode."""
    clear_screen()
    console.print(Panel("Dictation Practice", title="[title]Mode[/title]", border_style="border"), style="title")
    return Confirm.ask("Ready to start dictation practice?", default=True, console=console)

def display_dictation_pro_start_options(num_sentences):
    """Displays a start screen for Dictation Pro with 'Ready' and 'Go Back' options."""
    clear_screen()
    title_text = f"Dictation Pro: {num_sentences} sentences available." if num_sentences > 0 else "Dictation Pro (No sentences loaded)"
    
    options = ["Ready to Start", "Go Back to Main Menu"]
    current_selection = 0

    while True:
        clear_screen() 
        console.print(Panel(title_text, title="[title]Dictation Pro[/title]", border_style="border", expand=False), justify="center")
        console.print(Align.center(Padding("Are you ready to begin?", (1,2), style="default")))

        for i, option in enumerate(options):
            if i == current_selection:
                console.print(Align.center(Padding(f"> {option} <", (1, 2), style="highlight")))
            else:
                console.print(Align.center(Padding(f"  {option}  ", (1, 2), style="default")))
        
        console.print("\nUse [yellow]↑/↓[/yellow] to navigate, [yellow]Enter[/yellow] to select.", style="prompt")
        console.print("You can also press [yellow]q[/yellow] to go back at any time.", style="prompt")


        key = readchar.readkey()

        if key == readchar.key.UP:
            current_selection = (current_selection - 1 + len(options)) % len(options)
        elif key == readchar.key.DOWN:
            current_selection = (current_selection + 1) % len(options)
        elif key == readchar.key.ENTER:
            if current_selection == 0: # Ready
                clear_screen() 
                return "ready"
            elif current_selection == 1: # Go Back
                clear_screen()
                return "go_back"
        elif key.lower() == 'q': 
            clear_screen()
            return "go_back"


def display_listening_prompt(character_meaning, progress_text=""): 
    """Shows a prompt indicating audio is playing and instruction to reveal character."""
    clear_screen()
    panel_title = "[title]Listening...[/title]"
    if progress_text:
        panel_title = f"[title]Listening... ({progress_text})[/title]"
        
    content = f"Listen for the Chinese word for:\n\n[highlight]{character_meaning}[/]\n\nPress [yellow]Enter[/yellow] to see the character."
    console.print(Panel(content, title=panel_title, border_style="border", expand=False), justify="center")

def display_listening_prompt_pro(info_text="Listen to the sentence", progress_text="", speed_display_name=""): 
    """Shows a prompt indicating audio is playing for a sentence, including speed info."""
    clear_screen()
    panel_title = "[title]Listening (Pro Mode)...[/title]"
    if progress_text:
        panel_title = f"[title]Listening (Pro Mode)... ({progress_text})[/title]"

    speed_info = f"Current Speed: [highlight]{speed_display_name}[/]" if speed_display_name else ""
    
    controls_info = (
        "Controls:\n"
        "  [yellow]←[/yellow]/[yellow]→[/yellow] : Change Speed\n"
        "  [yellow]Space[/yellow]   : Replay Audio\n"
        "  [yellow]Enter[/yellow]   : Show Sentence\n"
        "  [yellow]q[/yellow]       : Quit to Menu"
    )

    content = f"{info_text}\n\n{speed_info}\n\n{controls_info}"
    console.print(Panel(content, title=panel_title, border_style="border", expand=False), justify="center")

def display_chinese_character(character, progress_text=""):
    """Displays the Chinese character large and centered."""
    clear_screen()
    panel_title = "[title]Character[/title]"
    if progress_text:
        panel_title = f"[title]Character ({progress_text})[/title]"

    text = Text(character, style="bold bright_green on black")
    # Panel title now includes progress, so we pass it here
    console.print(Align.center("\n" * 5))
    console.print(Align.center(Panel(text, title=panel_title, expand=False, padding=(5, 10), border_style="green")))
    console.print(Align.center("\n" * 5))


def display_chinese_sentence(sentence, progress_text=""): 
    """Displays the Chinese sentence centered."""
    clear_screen()
    panel_title = "[title]Sentence[/title]"
    if progress_text:
        panel_title = f"[title]Sentence ({progress_text})[/title]"
        
    text = Text(sentence, style="bold bright_green on black")
    # Panel title now includes progress
    console.print(Align.center("\n" * 3)) 
    console.print(Align.center(Panel(text, title=panel_title, expand=False, padding=(3, 6), border_style="green")))
    console.print(Align.center("\n" * 3))
    console.print(Align.center("Press [yellow]Enter[/yellow] to continue..."), style="prompt")


# --- Dictation Mode ---
def run_dictation_practice(args):
    """Runs the dictation practice session."""
    vocab = load_vocab(args.debug)
    if not vocab:
        console.print("[WARNING] Vocabulary is empty. Add words via the update menu.", style="warning")
        Prompt.ask("Press Enter to return to menu...")
        return

    # Uses the original Confirm.ask start screen
    if not display_dictation_start_screen():
        clear_screen()
        return

    random.shuffle(vocab)
    total_items = len(vocab)
    
    current_idx = 0
    while current_idx < total_items:
        item = vocab[current_idx]
        char = item.get('character')
        pinyin = item.get('pinyin')
        character_meaning = item.get('character_meaning')
        base_audio_file_name = item.get('audio_file_name') # e.g., "hello.mp3"

        progress_text = f"Progress: {current_idx + 1}/{total_items}"

        if not all([char, pinyin, character_meaning, base_audio_file_name]):
            console.print(f"[WARNING] Incomplete vocabulary entry: {item}. Skipping. ({progress_text})", style="warning")
            current_idx += 1
            continue
        
        base_name_no_ext, ext = os.path.splitext(base_audio_file_name)
        if not ext: ext = ".mp3" # Ensure extension
        # Construct filename for default speed audio
        default_speed_audio_filename = f"{base_name_no_ext}{DEFAULT_SPEED_SUFFIX}{ext}"
        audio_to_play = os.path.join(AUDIO_CHAR_DIR, default_speed_audio_filename)
        
        if not os.path.exists(audio_to_play):
            console.print(f"[ERROR] Default speed audio file '{default_speed_audio_filename}' for '{char}' not found. ({progress_text})", style="error")
            console.print(f"Please ensure audio files are generated (check system startup or update vocabulary). Skipping word.", style="error")
            # Add a small delay or prompt before auto-skipping
            Prompt.ask("Press Enter to skip to next word...")
            current_idx += 1
            continue 

        display_listening_prompt(character_meaning, progress_text)
        try:
            if args.debug:
                console.print(f"[DEBUG] Playing audio: {audio_to_play} ({progress_text})", style="dim cyan")
            playsound(audio_to_play)
        except Exception as e:
            console.print(f"[ERROR] Could not play audio {audio_to_play}: {e} ({progress_text})", style="error")
            if Confirm.ask("Error playing audio. Continue to next word?", default=True):
                current_idx += 1
                continue
            else:
                break # Exit dictation loop

        try:
            Prompt.ask("") 
        except (EOFError, KeyboardInterrupt):
            console.print("\nDictation ended.", style="info")
            clear_screen()
            return
            
        display_chinese_character(char, progress_text)

        try:
            Prompt.ask("") 
        except (EOFError, KeyboardInterrupt):
            console.print("\nDictation ended.", style="info")
            clear_screen()
            return
        
        current_idx += 1
        if current_idx >= total_items:
            console.print(Panel(f"✨ Dictation Complete! ({progress_text}) ✨", title="[title]Congratulations[/title]", border_style="border"), justify="center")
            if Confirm.ask("Practice again with a new shuffle?", default=True):
                random.shuffle(vocab) 
                current_idx = 0
            else:
                break 
                
    clear_screen()


# --- Dictation Pro Mode ---
def run_dictation_pro(args):
    """Runs the Dictation Pro session with sentences from sentences.csv."""
    sentences_vocab = load_sentences(args.debug)
    if not sentences_vocab:
        console.print("[WARNING] Sentence vocabulary is empty. Add sentences via the update menu.", style="warning")
        Prompt.ask("Press Enter to return to menu...")
        return

    start_choice = display_dictation_pro_start_options(len(sentences_vocab))
    if start_choice == "go_back":
        return
        
    random.shuffle(sentences_vocab) 
    total_items = len(sentences_vocab)
    current_item_idx = 0
    
    # Initialize speed index - find the index corresponding to DEFAULT_KOKORO_SPEED
    try:
        current_speed_index = [i for i, conf in enumerate(SPEED_CONFIGURATIONS) if conf["value"] == DEFAULT_KOKORO_SPEED][0]
    except IndexError:
        console.print("[ERROR] Default speed not found in SPEED_CONFIGURATIONS. Defaulting to slowest.", style="error")
        current_speed_index = 0 # Default to the first one (e.g., slowest) if not found

    while current_item_idx < total_items:
        item_data = sentences_vocab[current_item_idx]
        text = item_data.get("sentence_text")
        base_audio_file_name = item_data.get("audio_file_name")
        
        progress_text = f"Progress: {current_item_idx + 1}/{total_items}"

        if not text or not base_audio_file_name:
            console.print(f"[WARNING] Incomplete sentence entry: {item_data}. Skipping. ({progress_text})", style="warning")
            current_item_idx += 1
            continue

        base_name_no_ext, ext = os.path.splitext(base_audio_file_name)
        if not ext: ext = ".mp3"

        # Helper function to play audio at the current speed
        def play_current_sentence_audio():
            current_speed_config = SPEED_CONFIGURATIONS[current_speed_index]
            audio_filename_at_current_speed = f"{base_name_no_ext}{current_speed_config['suffix']}{ext}"
            audio_path_for_play = os.path.join(AUDIO_PRO_DIR, audio_filename_at_current_speed)

            if not os.path.exists(audio_path_for_play):
                console.print(f"[ERROR] Audio file '{audio_filename_at_current_speed}' for sentence '{text[:30]}...' not found. ({progress_text})", style="error")
                console.print(f"Attempting to play default speed instead...", style="warning")
                # Try to play default if specific speed is missing
                default_speed_config_idx = [i for i, conf in enumerate(SPEED_CONFIGURATIONS) if conf["value"] == DEFAULT_KOKORO_SPEED][0]
                default_suffix = SPEED_CONFIGURATIONS[default_speed_config_idx]['suffix']
                audio_filename_at_current_speed = f"{base_name_no_ext}{default_suffix}{ext}"
                audio_path_for_play = os.path.join(AUDIO_PRO_DIR, audio_filename_at_current_speed)
                if not os.path.exists(audio_path_for_play):
                    console.print(f"[ERROR] Default audio file '{audio_filename_at_current_speed}' also not found. Cannot play audio.", style="error")
                    return False


            try:
                if args.debug:
                    console.print(f"[DEBUG] Playing audio: {audio_path_for_play} ({progress_text}, Speed: {current_speed_config['display_name']})", style="dim cyan")
                playsound(audio_path_for_play)
                return True # Indicate success
            except Exception as e_play:
                console.print(f"[ERROR] Could not play audio {audio_path_for_play}: {e_play} ({progress_text})", style="error")
                return False # Indicate failure

        # Initial display and play for the current sentence
        display_listening_prompt_pro(f"Listen to the sentence", progress_text, SPEED_CONFIGURATIONS[current_speed_index]['display_name'])
        play_successful = play_current_sentence_audio()
        
        if not play_successful: # If initial play failed even after fallback attempt
            if Confirm.ask("Error playing audio. Continue to next sentence?", default=True, console=console):
                current_item_idx += 1
                continue
            else:
                break # Exit dictation pro loop

        # Input loop for speed change, replay, continue, or quit
        while True: 
            key = readchar.readkey()

            if key == readchar.key.LEFT:
                current_speed_index = (current_speed_index - 1 + len(SPEED_CONFIGURATIONS)) % len(SPEED_CONFIGURATIONS)
                display_listening_prompt_pro(f"Listen to the sentence", progress_text, SPEED_CONFIGURATIONS[current_speed_index]['display_name'])
                play_current_sentence_audio()
            elif key == readchar.key.RIGHT:
                current_speed_index = (current_speed_index + 1) % len(SPEED_CONFIGURATIONS)
                display_listening_prompt_pro(f"Listen to the sentence", progress_text, SPEED_CONFIGURATIONS[current_speed_index]['display_name'])
                play_current_sentence_audio()
            elif key == ' ': # Spacebar for replay
                display_listening_prompt_pro(f"Replaying sentence", progress_text, SPEED_CONFIGURATIONS[current_speed_index]['display_name'])
                play_current_sentence_audio()
            elif key == readchar.key.ENTER:
                break # Proceed to show sentence
            elif key.lower() == 'q':
                console.print("\nDictation Pro ended by user.", style="info")
                clear_screen()
                return # Exit run_dictation_pro

        display_chinese_sentence(text, progress_text)

        try:
            # Wait for Enter to continue to next sentence or finish (or q to quit)
            console.print(Align.center("Press [yellow]Enter[/yellow] to continue, or [yellow]q[/yellow] to quit..."), style="prompt")
            final_key = readchar.readkey()
            if final_key.lower() == 'q': 
                 console.print("\nDictation Pro ended by user.", style="info")
                 clear_screen()
                 return
            # Any other key (typically Enter) will proceed to the next item or finish
        except (EOFError, KeyboardInterrupt):
            console.print("\nDictation Pro ended.", style="info")
            clear_screen()
            return
        
        current_item_idx += 1
        if current_item_idx >= total_items:
            console.print(Panel(f"✨ Dictation Pro Complete! ({progress_text}) ✨", title="[title]Congratulations[/title]", border_style="border"), justify="center")
            console.print("Practice Dictation Pro again with a new shuffle? ([yellow]y[/yellow]/[yellow]n[/yellow]/[yellow]q[/yellow])", style="prompt")
            while True:
                again_key = readchar.readkey().lower()
                if again_key == 'y':
                    random.shuffle(sentences_vocab)
                    current_item_idx = 0
                    # current_speed_index is intentionally preserved from user's last setting
                    break 
                elif again_key == 'n' or again_key == 'q':
                    current_item_idx = total_items # Ensure outer loop terminates
                    break
                else:
                    console.print("Invalid input. Press 'y' for yes, 'n' for no, or 'q' to quit.", style="warning")
            
            if current_item_idx >= total_items: # if 'n' or 'q' was pressed in the practice again prompt
                break # Exit the main while loop for items
            
    clear_screen()

def handle_update_vocabulary_menu(args):
    """Handles the vocabulary update submenu."""
    while True:
        # _clear_and_redraw_menu_options expects title to be printed before it clears and redraws.
        # So, we print the panel first, then call the helper.
        clear_screen() 
        console.print(Panel("Update Vocabulary", title="[title]Menu[/title]", border_style="border"), style="title")
        
        options = ["Update Word Vocabulary", "Update Sentence Vocabulary", "Back to Main Menu"]
        current_selection = 0 # Reset selection for this menu

        # Initial draw of options before loop
        _clear_and_redraw_menu_options(options, current_selection, "Update Vocabulary")

        while True: # Inner loop for key handling within this menu
            key = readchar.readkey()

            if key == readchar.key.UP:
                current_selection = (current_selection - 1 + len(options)) % len(options)
            elif key == readchar.key.DOWN:
                current_selection = (current_selection + 1) % len(options)
            elif key == readchar.key.ENTER:
                if current_selection == 0:
                    update_word_vocab_interactive(args)
                    # After returning from update, break inner to redraw update menu
                    break 
                elif current_selection == 1:
                    update_sentence_vocab_interactive(args)
                    # After returning from update, break inner to redraw update menu
                    break
                elif current_selection == 2:
                    return  # Go back to main menu
            elif key.lower() == 'q':
                return  # Go back to main menu
            
            # Redraw options within the same menu screen
            _clear_and_redraw_menu_options(options, current_selection, "Update Vocabulary")
        
        # This part is reached if an action (like update_word_vocab) was taken and we broke the inner loop.
        # The outer loop will then redraw the "Update Vocabulary" menu from scratch.

# --- Main Application ---
def main():
    global ARGS # To access parsed args
    parser = argparse.ArgumentParser(description="Chinese Language Assistant with Dictation Practice")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging and prints")
    parser.add_argument("--update-vocab", action="store_true", help="Enter vocabulary update mode")
    parser.add_argument("--kokoro_voice", type=str, default=DEFAULT_KOKORO_VOICE, help=f"Kokoro TTS voice (default: {DEFAULT_KOKORO_VOICE})")
    parser.add_argument("--kokoro_lang", type=str, default=DEFAULT_KOKORO_LANG_CODE, help=f"Kokoro TTS language code (default: {DEFAULT_KOKORO_LANG_CODE})")
    parser.add_argument("--kokoro_speed", type=float, default=DEFAULT_KOKORO_SPEED, help=f"Kokoro TTS speed (default: {DEFAULT_KOKORO_SPEED})")
    # parser.add_argument("--openai_model", type=str, default=DEFAULT_OPENAI_MODEL, help=f"OpenAI model for Dictation Pro (default: {DEFAULT_OPENAI_MODEL})") # Removed
    ARGS = parser.parse_args()
    if ARGS.debug:
        logger.setLevel(logging.DEBUG)
        console.print("[DEBUG] Debug mode enabled", style="dim cyan")
    else:
        logger.setLevel(logging.WARNING)

    # Create base audio directory if it doesn't exist
    if not os.path.exists(AUDIO_DIR):
        os.makedirs(AUDIO_DIR)
        console.print(f"[INFO] Created base audio directory: {AUDIO_DIR}", style="info")

    # Create subdirectories for character and pro audio
    if not os.path.exists(AUDIO_CHAR_DIR):
        os.makedirs(AUDIO_CHAR_DIR)
        console.print(f"[INFO] Created character audio directory: {AUDIO_CHAR_DIR}", style="info")
    
    if not os.path.exists(AUDIO_PRO_DIR):
        os.makedirs(AUDIO_PRO_DIR)
        console.print(f"[INFO] Created pro audio directory: {AUDIO_PRO_DIR}", style="info")

    # Ensure audio files for existing vocabulary are checked/generated at startup
    ensure_audio_files_exist(ARGS)
    ensure_sentence_audio_files_exist(ARGS) # Call the new function for sentences

    if ARGS.update_vocab: # This CLI flag is now less relevant but can directly go to the menu
        handle_update_vocabulary_menu(ARGS) 
        return

    # console.print(Panel("Welcome to the Chinese Language Assistant!", title="[title]Welcome[/title]", border_style="border"), justify="center")
    while True:
        choice = display_main_menu()
        if choice == "dictation":
            run_dictation_practice(ARGS)
        elif choice == "dictation_pro": 
            run_dictation_pro(ARGS) # Will use the refactored version
        elif choice == "update_vocab": # New choice for updating vocabulary
            handle_update_vocabulary_menu(ARGS) # To be created
        elif choice == "exit":
            console.print("Exiting the application. Goodbye!", style="info")
            break
        else:
            console.print("[ERROR] Invalid choice. Please try again.", style="error")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\nApplication interrupted. Exiting...", style="warning")
        sys.exit(0)
    except Exception as e:
        console.print(f"[ERROR] An unexpected error occurred: {e}", style="error")
        sys.exit(1)

# End of laoshi.py
# Note: This code assumes the Kokoro TTS API is running and accessible at the specified URL.