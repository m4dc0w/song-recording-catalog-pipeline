# 🎙️ AI Audio Segmentation Pipeline

An automated Python pipeline that uses Google Gemini's multimodal AI to intelligently segment raw, continuous church service recordings into individual "song", "speaking", and "sermon" audio files. 

By utilizing advanced **Chain of Thought (CoT) self-reflection**, the AI rigorously audits its own timestamps to account for musical intros, outros, interludes, and background pads before precision-slicing the master file using FFmpeg.

## 🚀 Features

* **Multimodal AI Analysis:** Leverages the latest Gemini Flash models to listen to audio and map setlists dynamically.
* **Intelligent Crossfading:** Automatically applies 3-second crossfades for songs and tight 250ms fades for spoken word.
* **DAW Ready:** Generates tab-separated locator markers for seamless import into DAWs like Ableton Live.
* **Storage Agnostic:** Fully configurable via environment variables to work with Google Drive Desktop, local directories, or network drives.
* **Future-Proof:** Pin or upgrade your specific Gemini AI model directly from your `.env` configuration.
* **Self-Critique Loop:** AI actively prevents "speech bleed" and overlapping hallucinations before generating outputs.

---

## 📋 Prerequisites

Before running the script, ensure you have the following installed on your machine:

1. **Python 3.8+**
2. **FFmpeg:** The script relies on FFmpeg for fast audio compression and slicing.
   * *macOS (Homebrew):* `brew install ffmpeg`
   * *Windows:* Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add to your system PATH.
3. **Google Gemini API Key:** You can generate one for free from Google AI Studio.

---

## 🛠️ Installation & Setup

1. **Clone the repository and navigate to the project folder:**
   ```bash
   git clone [https://github.com/yourusername/song-recording-catalog-pipeline.git](https://github.com/yourusername/song-recording-catalog-pipeline.git)
   cd song-recording-catalog-pipeline/audio_segmentation

```

2. **Install Python dependencies:**
```bash
pip install google-genai python-dotenv

```


3. **Configure Environment Variables:**
* Copy the example environment file:
```bash
cp .env.example .env

```


* Open the `.env` file and fill in your specific credentials and directory paths:
```env
# Your Google Gemini API Key
GEMINI_API_KEY=your_actual_api_key_here

# The Gemini model to use for segmentation (Defaults to gemini-3.8-flash if left blank)
GEMINI_MODEL=gemini-3.8-flash

# Absolute path to the folder containing your unedited raw WAV files
RAW_AUDIO_DIR=/Path/To/Your/Raw/Recordings

# Absolute path to the destination folder where sliced files and reports will be saved
PROCESSED_AUDIO_DIR=/Path/To/Your/Processed/Output

# (Optional) Absolute path to your FFmpeg binary. 
# Leave blank to automatically use the "ffmpeg" command in your system PATH.
FFMPEG_PATH=

```


* *Note: The `.env` file is included in `.gitignore` and will never be pushed to your public repository.*



---

## 💻 Usage

To process a new recording, update the entry point variables at the very bottom of `audio_segmentation.py`:

```python
if __name__ == "__main__":
    RAW_WAV_FILENAME = "R_20260906-103109.wav"
    SERVICE_DATE = "2026-09-06"
    SETLIST_DATA = """
    Glorious and Mighty
    Crown Him With Many Crowns
    And Can It Be
    All I Have Is Christ
    Holy, Holy, Holy
    """

```

Once updated, run the script from your terminal:

```bash
python3 audio_segmentation.py

```

### What to Expect During Execution:

1. **Compression:** The script generates a temporary, lightweight 64kbps MP3 preview of your master WAV to drastically reduce API upload times.
2. **AI Analysis:** The MP3 is sent to Gemini. You will see the AI's internal "Self-Critique Log" printed to your terminal as it reasons through boundary overlaps.
3. **Slicing:** FFmpeg executes precision cuts directly on your local disk.
4. **Output:** Check your `PROCESSED_AUDIO_DIR` for the separated `.wav` files, the DAW Locator `.txt` file, and a text-based Segmentation Audit Report.

---

## 🧪 Running Tests

The project includes a robust unit testing suite that verifies timestamp math, string sanitization, hallucination prevention logic (negative durations/backwards jumps), and dynamic FFmpeg command construction.

To run the test suite, ensure you are in the `audio_segmentation` directory and execute:

```bash
python3 -m unittest audio_segmentation_tests.py -v

```

---

## 🧠 How the AI Logic Works

This pipeline does not blindly trust the AI's first guess. It enforces a strict JSON schema that requires the model to output its reasoning *before* outputting timestamps.

The AI must explicitly answer these questions natively in the API call:

* **Intros:** Did I accidentally include spoken introductions?
* **Outros:** Does the song end exactly when the instruments stop?
* **Interludes:** Did I properly overlap timestamps for continuous musical segues?
* **Background Pads:** Is the pastor just preaching over a soft synth pad?

This workflow guarantees deterministic, high-fidelity segmentation without requiring a secondary "correction" API call.
