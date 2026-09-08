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

### 1. The Full End-to-End Pipeline (Default)

To process a new service recording, simply run the orchestrator without any flags. When invoked with zero arguments, the orchestrator defaults to running the **entire end-to-end workflow**:

```bash
python3 pipeline_orchestrator.py
```

* **What it does automatically:** 
  1. Prompts you to select a service type and recent service from Planning Center.
  2. Fetches the setlist from PCO.
  3. Automatically discovers the matching raw audio file in `RAW_AUDIO_DIR`.
  4. Generates an MP3 preview and uses Gemini AI to determine precise song timestamps.
  5. Slices the audio into individual tracks inside `PROCESSED_AUDIO_DIR`.
  6. **Post-Processing (Stage Songs):** Copies and stages songs into `STAGING_AUDIO_DIR` (stripping the `Song_XX_` prefix).
  7. **Post-Processing (Publish Verified):** Prompts you to confirm moving verified tracks from `STAGING_AUDIO_DIR` to `VERIFIED_AUDIO_DIR`.
  8. **Post-Processing (Generate Videos):** Renders OLED-safe, loudness-normalized MP4 videos into `VIDEOS_DIR`.

*Fine-Grained Controls & Overrides:*
You can bypass the interactive menu for headless automation, skip post-processing, or isolate specific stages:
```bash
# Run segmentation only (skips post-processing)
python3 pipeline_orchestrator.py --service-type "987654" --plan-id "123456" --date "2026-09-06"

# Run interactive segmentation only without post-processing
python3 pipeline_orchestrator.py --skip-post-processing

# Run segmentation for a specific audio file (with explicit post-processing)
python3 pipeline_orchestrator.py --audio-file "R_20260906-103109.wav" --publish-staging --publish-verified --make-videos
```

### 2. Post-Processing: Publishing & Video Generation

After the AI segments the audio, you can run post-processing steps individually or combined to stage, verify, and generate videos.

**Stage Songs:**
Strips the AI numbering prefix (e.g., `Song_01_`) and safely copies the files from `PROCESSED_AUDIO_DIR` to your staging area (`STAGING_AUDIO_DIR`):
```bash
python3 pipeline_orchestrator.py --publish-staging
```

**Publish Verified Songs:**
Prompts you to confirm if the recordings in `STAGING_AUDIO_DIR` have been manually verified. If you type 'y', it securely moves them into your `VERIFIED_AUDIO_DIR` without overwriting existing files:
```bash
python3 pipeline_orchestrator.py --publish-verified
```

**Generate Videos:**
Scans your `VERIFIED_AUDIO_DIR` for `.wav` files and generates OLED-safe, multiline text `.mp4` videos using a default `assets/images/background.png`. It uses a 2-pass FFmpeg `loudnorm` filter (I=-14, TP=-1) to guarantee perfect normalization for YouTube/Social Media:
```bash
python3 pipeline_orchestrator.py --make-videos
```

**Run All Post-Processing Stages Simultaneously:**
```bash
python3 pipeline_orchestrator.py --publish-staging --publish-verified --make-videos
```

*(Note: Ensure an image exists at `assets/images/background.png` or specify a custom path in the code for video generation to work.)*

### 3. Batch Processing / Backfilling

If you have a large archive of historical raw recordings and want to process them all at once, you can use the dedicated backfill orchestrator:

```bash
python3 pipeline_orchestrator_backfill.py
```

* **What it does:** 
  1. Interactively prompts you for a `Start Date` and `End Date` (YYYY-MM-DD).
  2. Fetches up to 100 recent plans from Planning Center and filters them down to your specified timeframe.
  3. Automatically searches your `RAW_AUDIO_DIR` for matching `.wav` files.
  4. Sequentially executes the Gemini AI segmentation on every matched date, wrapped in a fault-tolerant `try/except` loop so a single failure doesn't halt the entire batch.
  5. Respects API rate limits automatically by pausing between plans.
  6. Prints a final summary report of all successful and failed processing dates.

*Optional Overrides:*
```bash
python3 pipeline_orchestrator_backfill.py --start-date "2026-01-01" --end-date "2026-12-31" --limit 200
```

*Logging Output & Errors to a File:*
```bash
python3 -u pipeline_orchestrator_backfill.py 2>&1 | tee tmp/backfill_report.txt
```

* **Next Steps After Backfill:**
Once backfilling is complete and you have verified the sliced audio files in `PROCESSED_AUDIO_DIR`, proceed to **[Post-Processing: Publishing & Video Generation](#2-post-processing-publishing--video-generation)** to stage, verify, and generate videos for the entire batch:
```bash
# Stage the segmented songs:
python3 pipeline_orchestrator.py --publish-staging

# After listening and verifying in STAGING_AUDIO_DIR, publish and generate videos:
python3 pipeline_orchestrator.py --publish-verified --make-videos
```

---

## 🧪 Testing

The project includes a robust unit testing suite (50+ tests) covering API interactions, timestamp math, string sanitization, hallucination prevention logic, file operations, and dynamic FFmpeg command construction.

To run the entire test suite across the repository, use the included test runner:
```bash
python3 run_tests.py
```

---

## 💻 Development Workflow (Google AI Studio Build)

This repository is optimized for rapid development and maintenance using **[Google AI Studio Build](https://aistudio.google.com/build)**. You can import, edit, test, and sync this codebase directly in the cloud using natural language prompts powered by Gemini.

### 1. Importing the Repository into Google AI Studio
1. Navigate to [aistudio.google.com/build](https://aistudio.google.com/build).
2. Click **New App** or **Import** and select **Import from GitHub**.
3. Authorize your GitHub account (if not already connected) and select this repository.
4. Choose the target branch (e.g., `main`) to load the workspace. AI Studio will automatically provision a full-stack container environment with Python, Node.js, and audio dependencies pre-configured.

### 2. Environment Variables & Secrets Configuration
* **Never commit secrets to GitHub.**
* In AI Studio, open **Settings** (gear icon) or the **Secrets** panel to configure required environment variables:
  * `GEMINI_API_KEY`: Your Google Gemini API key.
  * `PCO_APP_ID`: Planning Center Online Application ID.
  * `PCO_SECRET`: Planning Center Online Secret key.
  * `RAW_AUDIO_DIR`, `PROCESSED_AUDIO_DIR`, `STAGING_AUDIO_DIR`, `VERIFIED_AUDIO_DIR`: Set paths appropriate for your environment or mounted storage.
* Refer to `.env.example` for all configurable variables and documentation.

### 3. Iterating and Coding with Gemini Prompts
You can direct Gemini in the chat interface to modify logic, implement new features, or fix bugs:
* **Targeted Prompts:** Highlight code in the editor or mention specific files and functions (e.g., *"In `pipeline_orchestrator.py`, add support for..."*).
* **Test-Driven Modifications:** Ask Gemini to write unit tests alongside feature changes to verify functionality.
* **Automated Verification:** Prompt Gemini to execute `python3 run_tests.py` after edits to ensure that all unit tests pass without regressions before completing the task.

### 4. Reviewing Changes with the Diff Viewer
Before committing or exporting your work, inspect the modifications using the built-in Diff Viewer:
1. Click the **Review PR / Diff Viewer** tab or button in the upper workspace navigation.
2. Review the side-by-side or unified visual diff of all modified, added, or deleted files.
3. Verify that only intentional changes and functional artifacts are staged (and that no scratch files or secrets were created).

### 5. Committing and Creating a Pull Request (Push to GitHub)
Once you have reviewed the changes and verified that all tests pass:
1. In the top-right header, click **Export** and select **Push to GitHub**.
2. Select your destination:
   * **Create a new branch & Pull Request (Recommended):** Enter a descriptive branch name and PR title/description. AI Studio will push the branch and open a Pull Request directly on GitHub.
   * **Commit directly to current branch:** Push changes straight to your existing working branch.
3. Click **Push** to sync your changes with GitHub.

### 6. Best Practices & Persistent AI Guidelines (`AGENTS.md`)
* **Project Rules:** AI Studio automatically reads `AGENTS.md` and `GEMINI.md` at the root of the repository to enforce coding standards, directory conventions, and testing requirements across all AI assistant turns.
* **No Scratch Files:** Per `AGENTS.md`, temporary test scripts should never be committed to the repository root. Always run inline experiments or write to `/tmp/`.
* **Always Run Tests:** Run `python3 run_tests.py` before exporting to ensure zero regressions across the test suite.
