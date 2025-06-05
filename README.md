# Laoshi - AI Chinese Language Assistant

**Laoshi** is a command-line application designed to help users practice and learn Chinese (Mandarin) vocabulary and sentences through interactive dictation exercises. It utilizes a local Kokoro TTS (Text-to-Speech) engine to generate audio for characters and sentences, providing a rich learning experience.

## Features

*   **Interactive Main Menu:** Easy navigation using arrow keys.
*   **Two Dictation Modes:**
    *   **Dictation (Words):** Practice individual Chinese characters. Listen to the audio, then reveal the character and its pinyin/meaning.
    *   **Dictation Pro (Sentences):** Practice full sentences. Listen to the audio, then reveal the sentence.
        *   **Multi-Speed Playback:** Adjust audio playback speed (extra slow, slow, default) using left/right arrow keys during Dictation Pro.
        *   **Replay Audio:** Replay the current sentence audio by pressing the Spacebar.
        *   **Persistent Speed:** Your selected speed carries over to the next sentence.
*   **Progress Tracker:** Displays "Progress: X/Y" during dictation sessions.
*   **Vocabulary Management:**
    *   Add new words (character, pinyin, meaning, audio filename idea) interactively.
    *   Add new sentences (sentence text, audio filename idea) interactively.
    *   Vocabulary and sentences are stored in local CSV files (`vocabulary.csv`, `sentences.csv`).
*   **Multi-Speed Audio Generation:**
    *   When new vocabulary is added or audio files are missing, the script automatically generates audio at three speeds:
        *   Default (1.0x)
        *   Slow (0.7x)
        *   Extra Slow (0.5x)
    *   Audio files are stored with suffixes (e.g., `audio_default.mp3`, `audio_slow.mp3`, `audio_slower.mp3`).
*   **Audio File Integrity Check:** On startup, the script checks for missing audio files for all vocabulary and sentences and attempts to generate them.
*   **Customizable TTS:** Configure Kokoro TTS voice, language, and default speed via command-line arguments.
*   **Rich CLI Interface:** Uses the `rich` library for an enhanced visual experience in the terminal.

## Requirements

*   Python 3.x
*   A running instance of the [Kokoro TTS API](https://github.com/ranchui/Kokoro-TTS) (assumed to be accessible at `http://localhost:8880` by default).
*   Python libraries:
    *   `requests`
    *   `playsound`
    *   `readchar`
    *   `rich`

## Setup

1.  **Clone the Repository (or download the script):**
    Ensure `laoshi.py` is in your desired project directory.

2.  **Install Dependencies:**
    It's recommended to use a virtual environment.
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
    pip install requests playsound readchar rich
    ```

3.  **Ensure Kokoro TTS is Running:**
    Start your Kokoro TTS server. The script expects it to be available at `http://localhost:8880`. If it's running elsewhere, you'll need to modify the `KOKORO_API_BASE_URL` constant in the script or use command-line arguments if available for this in future versions.

4.  **Prepare Vocabulary (Optional):**
    *   The script will create `vocabulary.csv` and `sentences.csv` if they don't exist.
    *   You can pre-populate these files or add entries via the script's "Update Vocabulary" menu.

    **`vocabulary.csv` format:**
    ```csv
    character,pinyin,character_meaning,audio_file_name
    你好,nǐ hǎo,hello,ni_hao_audio.mp3
    学,xué,to study,xue_audio.mp3
    ```
    *(Note: The `.mp3` extension in `audio_file_name` is for the base name; the script will append speed suffixes like `_default.mp3`, `_slow.mp3` for actual files.)*

    **`sentences.csv` format:**
    ```csv
    sentence_text,audio_file_name
    你叫什么名字？,what_is_your_name_audio.mp3
    我喜欢学中文。,i_like_learning_chinese_audio.mp3
    ```

5.  **Audio Directories:**
    The script will automatically create an `audio` directory with `characters` and `pro` subdirectories in the same location as `laoshi.py` to store the generated MP3 files.

## Usage

Run the script from your terminal:

```bash
python3 laoshi.py
```

### Command-Line Arguments

*   `--debug`: Enable debug logging and additional print statements.
*   `--update-vocab`: (Less relevant now with menu option) Directly enter vocabulary update mode on start.
*   `--kokoro_voice VOICE`: Specify the Kokoro TTS voice (default: `zf_xiaoxiao`).
*   `--kokoro_lang LANG_CODE`: Specify the Kokoro TTS language code (default: `z`).
*   `--kokoro_speed SPEED`: Specify the default Kokoro TTS speed (default: `1.0`).

Example with arguments:
```bash
python3 laoshi.py --kokoro_voice zf_soso --kokoro_speed 0.9 --debug
```

### Interacting with the Application

*   **Main Menu:** Use **Up/Down arrow keys** to navigate and **Enter** to select an option. Press **'q'** to quit from most menus.
*   **Dictation Modes:**
    *   Listen to the audio.
    *   Press **Enter** to reveal the character/sentence.
    *   Press **Enter** again to continue to the next item.
*   **Dictation Pro Speed Control:**
    *   **Left Arrow (←):** Decrease playback speed.
    *   **Right Arrow (→):** Increase playback speed.
    *   **Spacebar:** Replay current sentence audio.
*   **Update Vocabulary Menu:**
    *   Select "Update Word Vocabulary" or "Update Sentence Vocabulary".
    *   Follow the on-screen prompts to enter new items.
        *   For words: `character|pinyin|meaning|audio_filename_idea`
        *   For sentences: `sentence_text|audio_filename_idea`
    *   Multiple entries can be added on one line, separated by a semicolon (`;`).
    *   Type `done` or `exit` to finish adding entries for the current type.

## Kokoro TTS Integration

The script relies on a running Kokoro TTS instance.
*   **API Endpoint:** `http://localhost:8880/v1/audio/speech` (by default)
*   **Audio Generation:** When new vocabulary is added or audio files are found missing during the startup check, the script calls the Kokoro API to generate `.mp3` files. These are saved in `audio/characters/` or `audio/pro/` with speed-specific suffixes (e.g., `my_audio_default.mp3`, `my_audio_slow.mp3`, `my_audio_slower.mp3`). The base filename (e.g., `my_audio.mp3`) is stored in the CSV.

## Troubleshooting

*   **"Kokoro TTS API Error" / "Kokoro TTS Request failed":**
    *   Ensure your Kokoro TTS server is running and accessible at the configured URL.
    *   Check your network connection to the TTS server.
*   **"Could not play audio":**
    *   Make sure you have a command-line MP3 player that `playsound` can use (e.g., `mpg123` on Linux). Install one if necessary (`sudo apt install mpg123`).
    *   Verify that the audio files exist in the `audio/characters` or `audio/pro` directories and are not corrupted.
*   **Permission Errors:**
    *   Ensure the script has write permissions to create the `audio` directory and its subdirectories, and to write CSV files in its own directory.

---

Happy Learning!
