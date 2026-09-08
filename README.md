# 🎙️ Song Recording Catalog Pipeline

An end-to-end Python orchestration pipeline for music ministries and churches. This tool automates the tedious process of cataloging live service recordings by integrating directly with Planning Center Online (PCO), using Google Gemini's multimodal AI to intelligently segment raw master audio files, and preparing the final tracks for publication with FFmpeg-powered video generation.

## 🚀 Pipeline Features

1. **Planning Center Integration:** Automatically fetches recent service plans and setlists via the PCO API, eliminating manual data entry.
2. **Automated Audio Discovery:** Scans your raw recordings folder to automatically find the matching `.wav` file for a selected service date.
3. **Multimodal AI Segmentation:** Leverages the latest Gemini Flash models with a strict "Self-Critique" loop to dynamically listen to the audio, avoid speech-bleed, and map precise timestamps for every song in the setlist.
4. **Precision FFmpeg Slicing:** Automatically applies 3-second crossfades and cuts the master `.wav` file into pristine, individual tracks.
5. **DAW Ready:** Generates tab-separated locator markers for seamless import into DAWs like Ableton Live.
6. **Automated Post-Processing:** 
   - **Publish:** Strips prefix metadata and safely copies verified tracks to a clean publication folder.
   - **Video Generation:** Generates OLED-safe, multiline typography MP4 videos from your verified audio using a precise 2-pass `loudnorm` audio normalization.

---

## 📋 Prerequisites

Before running the script, ensure you have the following installed on your machine:

1. **Python 3.10+**
2. **FFmpeg:** The script relies on FFmpeg for audio compression, precision slicing, and video rendering.
   * *macOS (Homebrew):* `brew install ffmpeg`
   * *Windows:* Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add to your system PATH.
3. **Google Gemini API Key:** Generate one for free from Google AI Studio.
4. **Planning Center API Keys:** Generate personal access tokens via the PCO developer dashboard.

---

## 🛠️ Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/song-recording-catalog-pipeline.git
   cd song-recording-catalog-pipeline
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
   Open the `.env` file and configure your API keys and folder structures:
   - `GEMINI_API_KEY`, `PCO_APP_ID`, `PCO_SECRET`
   - `PCO_SERVICE_TYPE_ID` *(Optional: If left blank, the CLI will prompt you to select a service type dynamically).*
   - Define your strict local/cloud drive folder paths: `RAW_AUDIO_DIR`, `PROCESSED_AUDIO_DIR`, `STAGING_AUDIO_DIR`, `VERIFIED_AUDIO_DIR`, `VIDEOS_DIR`.

---

## 💻 Usage & Workflows

The entire tool is orchestrated via a single command-line interface: `pipeline_orchestrator.py`.

### 1. The Core Segmentation Pipeline

To process a new service recording, simply run the orchestrator without any flags. It will provide an interactive menu of your service types (if not configured in `.env`) and recent Planning Center services:

```bash
python3 pipeline_orchestrator.py
```

* **What it does:** 
  1. Prompts you to select a service type and recent service.
  2. Fetches the setlist from PCO.
  3. Automatically discovers the matching raw audio file in `RAW_AUDIO_DIR`.
  4. Generates a compressed MP3 preview for the Gemini AI.
  5. The AI rigorously analyzes the audio to find timestamps.
  6. Slices the audio into individual tracks inside a safely isolated output folder within `PROCESSED_AUDIO_DIR`.

*(Note: While the base command focuses purely on generating the initial audio cuts, the orchestrator also natively handles the final publishing and video generation! See Section 2 for isolated post-processing, or chain the flags below.)*

*Automation & End-to-End Overrides:*
You can bypass the interactive menu for headless automation, and even chain the post-processing flags to run the entire end-to-end lifecycle (Segmentation ➔ Publishing ➔ Video Generation) in a single command:
```bash
# Run segmentation only for a specific plan
python3 pipeline_orchestrator.py --service-type "987654" --plan-id "123456" --date "2026-09-06"

# Run segmentation for a specific audio file
python3 pipeline_orchestrator.py --audio-file "R_20260906-103109.wav"

# Run the FULL end-to-end pipeline (Segment, Publish, and Generate Videos)
python3 pipeline_orchestrator.py --audio-file "R_20260906-103109.wav" --publish-verified --make-videos
```

### 2. Post-Processing: Publishing & Video Generation

After the AI segments the audio, you may want to manually listen to the tracks. Once you are satisfied, you can run the orchestrator in **Post-Processing Mode** to prepare them for publication.

**Publish Verified Songs:**
Strips the AI numbering prefix (e.g., `Song_01_`) and safely copies the files to a staging area (`STAGING_AUDIO_DIR`). The script will then interactively prompt you to confirm if they have been manually verified. If you type 'y', it securely moves them into your `VERIFIED_AUDIO_DIR` without overwriting existing files.
```bash
python3 pipeline_orchestrator.py --publish-verified
```

**Generate Videos:**
Scans your `VERIFIED_AUDIO_DIR` for `.wav` files and generates OLED-safe, multiline text `.mp4` videos using a default `assets/images/background.png`. It uses a 2-pass FFmpeg `loudnorm` filter (I=-14, TP=-1) to guarantee perfect normalization for YouTube/Social Media.
```bash
python3 pipeline_orchestrator.py --make-videos
```

**Run Both Simultaneously:**
```bash
python3 pipeline_orchestrator.py --publish-verified --make-videos
```

*(Note: Ensure an image exists at `assets/images/background.png` or specify a custom path in the code for video generation to work.)*

### 3. Batch Processing / Backfilling

If you have a large archive of historical raw recordings and want to process them all at once, you can use the dedicated backfill orchestrator:

```bash
python3 pipeline_orchestrator_backfill.py
```

* **What it does:** 
  1. Interactively prompts you for a `Start Date` and `End Date` (YYYY-MM-DD).
  2. Fetches up to 50 recent plans from Planning Center and filters them down to your specified timeframe.
  3. Automatically searches your `RAW_AUDIO_DIR` for matching `.wav` files.
  4. Sequentially executes the Gemini AI segmentation on every matched date, wrapped in a fault-tolerant `try/except` loop so a single failure doesn't halt the entire batch.
  5. Respects API rate limits automatically by pausing between plans.
  6. Prints a final summary report of all successful and failed processing dates.

*Optional Overrides:*
```bash
python3 pipeline_orchestrator_backfill.py --start-date "2026-01-01" --end-date "2026-12-31" --limit 100
```

---

## 🧪 Testing

The project includes a robust unit testing suite (24+ tests) covering API interactions, timestamp math, string sanitization, hallucination prevention logic, file operations, and dynamic FFmpeg command construction.

To run the entire test suite across the repository, use the included test runner:
```bash
python3 run_tests.py
```
