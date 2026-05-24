# ⚡ Kick Stream Analytics & Deep AI Research Tool
### by Ask_fOr_DaX

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?logo=windows)
![License](https://img.shields.io/badge/License-MIT-green)
![AI](https://img.shields.io/badge/AI-Ollama%20%7C%20Claude-purple)

A fully self-contained desktop analytics dashboard for **Kick.com** streamers. Monitor multiple live streams simultaneously, detect viewbots with AI-powered analysis, track chat behaviour, browse the global Top 100, analyse streamer history and generate detailed reports — all from a single GUI with **no Kick account or API key required**.

---

## ✨ Features

- 🔴 **Live chat monitoring** via Pusher WebSocket — real-time, colour-coded
- 📺 **Multi-stream support** — monitor multiple streamers in independent tabs
- 🤖 **AI-powered viewbot detection** — Ollama (local/free) or Anthropic Claude API
- 🖥️ **GPU-aware model selection** — auto-detects your GPU and recommends the best LLM
- 📊 **Viewbot detector panel** — live numeric scoring updated every 5 seconds
- 🏅 **Top 100 global streamers** — live ranking from kickstats.com
- 📡 **Multi-channel monitor** — track dozens of channels simultaneously
- 👥 **Chatter classification** — Active / Casual / Lurker / Known Bot / Likely Bot
- 🚫 **Spam & emote detection** — filter spammers and emote-only messages
- 📅 **Stream history** — VODs, clips, gift leaderboards, stream stats
- 🎙️ **Streamer profiles** — full channel info, social links, top categories
- 📄 **Full session reports** — generate and export detailed analytics
- 📖 **Built-in AI Guide** — embedded reference for all AI features
- 🔄 **Auto-reconnect** — silently reconnects on dropped WebSocket connections

---

## 🖥️ Screenshots

### Main Application — Live Chat & Viewbot Detection
![Main App](screenshots/screenshot_main.png)

### AI Analysis — Forensic Viewbot Detection Report
![AI Analysis](screenshots/screenshot_ai_analysis.png)

### Multi-Channel Monitor — Track Multiple Streamers
![Multi Channel](screenshots/screenshot_multi-channel.png)

---

## 🚀 Two Ways to Run

### Option A — Run from Source (Zero AV flags, recommended)

> Python required. Scripts are never flagged by antivirus software.

1. Download or clone this repository
2. Place `kick_report.py` and `install.bat` in the same folder
3. Double-click **`install.bat`** — installs all packages automatically
4. Double-click **`run.bat`** to launch the app

```
kick_report.py      ← Application source
install.bat         ← First-time setup (run once)
run.bat             ← Daily launcher (created by install.bat)
run_debug.bat       ← Debug launcher — keeps console open for errors
```

### Option B — Build Your Own EXE Folder

> Compile to a standalone folder that runs without Python installed.
> Building your own exe creates a **unique file hash** no AV database has seen.

1. Download or clone this repository
2. Place `kick_report.py`, `build_folder.bat` and `build_spec_folder.py` in the same folder
3. Double-click **`build_folder.bat`**
4. Output appears in `dist\KickAnalytics\`
5. ZIP the `KickAnalytics` folder and share

```
kick_report.py          ← Application source
build_folder.bat        ← Double-click to build
build_spec_folder.py    ← Build configuration (called automatically)
```

> ⚠️ **Never separate `KickAnalytics.exe` from the `_internal\` folder** — they must stay together

---

## ⚙️ System Requirements

| Requirement | Details |
|---|---|
| OS | Windows 10 or Windows 11 (64-bit) |
| Python | 3.9 or higher ([python.org](https://python.org) or [Miniconda](https://docs.conda.io)) |
| RAM | 4GB minimum, 8GB recommended |
| Internet | Required for live monitoring |
| Ollama | Optional — local AI analysis only |

---

## 🤖 AI Analysis

The AI Analysis tab sends 10 minutes of collected stream data to an LLM for forensic-level viewbot detection. Two provider options:

### 🖥️ Ollama — Local & Free
Run AI models on your own machine with no cost or internet required.

| GPU VRAM | Recommended Model | Quality |
|---|---|---|
| 20GB+ | `qwen3:32b` | Outstanding |
| 10–20GB | `qwen3:14b` | Excellent |
| 7–10GB | `qwen3:8b` | Very good ⭐ |
| 5–7GB | `mistral:7b` | Good |
| 3–5GB | `qwen3:4b` | Good |
| 1–3GB | `llama3.2:3b` | Decent |
| CPU only | `phi3:mini` | Decent |

```bash
# Install Ollama from https://ollama.com then pull your model
ollama pull qwen3:8b
```

### ☁️ Anthropic Claude API
Superior forensic reasoning. ~$0.03 per analysis.
Get a key at [console.anthropic.com](https://console.anthropic.com)

> API key stored securely in Windows Credential Manager — never written to disk

---

## 📦 Packages Installed Automatically

| Package | Purpose |
|---|---|
| `websockets` | Real-time Pusher WebSocket connection |
| `curl_cffi` | Kick API requests |
| `keyring` | Secure API key storage |
| `GPUtil` | GPU VRAM detection |
| `psutil` | Process detection |
| `colorama` | Console colour support |
| `tabulate` | Table formatting |
| `typer` | Dependency conflict resolver |

---

## 🔒 Antivirus Notice

Compiled executables (Method B) may be flagged by antivirus heuristics due to PyInstaller's bundling format — this is a **false positive** common to all PyInstaller applications.

**This application:**
- Contains **no malware, backdoors or remote access tools**
- Makes only outbound HTTPS requests to `kick.com`, `kickstats.com`, `api.anthropic.com` and `127.0.0.1` (local Ollama)
- Requires **no administrator privileges**
- Installs **nothing** to your system
- Full source code available here for inspection

**Recommended:** Use **Method A** (source version) if your AV blocks the exe — Python scripts are never flagged.

> ❌ Do not submit your compiled exe to VirusTotal — this broadcasts the hash to 70+ AV vendors

---

## 📋 Tab Overview

### Per-Streamer Tabs
| Tab | Description |
|---|---|
| 💬 Live Chat | Real-time chat with badge colours, filters, spammer detection |
| 🤖 AI Analysis | AI viewbot detection with Ollama or Claude — 10min lock |
| 🎉 Events | Raids, subs, gifts, bans, pins in real time |
| 👥 Chatters | Sortable chatter table with bot classification, CSV export |
| 🔤 Top Words | Most used words bar chart, hide emotes, auto-refresh |
| 📊 Activity | Message volume chart over the full session |
| 🎙️ Streamer Info | Full channel profile, VODs, clips, social links |
| 📅 History | Past streams, clips, gift leaderboards, stream stats |
| 📄 Report | Full session report — generate and export as text |
| 📖 AI Guide | Built-in reference — how to use AI and read results |

### Global Tabs (pinned left)
| Tab | Description |
|---|---|
| 🏅 Top 100 | Live top 100 Kick streamers — region filter, sortable, CSV export |
| 📡 Multi-Channel | Monitor many channels — auto-refresh, LIVE sort, saved list |

---

## 🔧 Optional — Ollama Setup

1. Download from **[ollama.com](https://ollama.com)** and install (no admin required)
2. Ollama starts automatically in your system tray
3. Pull a model based on your GPU (see table above)
4. In the app → AI Analysis tab → click **Test Connection**
5. Click **Detect GPU** to get a personalised recommendation
6. Click **Run AI Analysis** after 10 minutes of monitoring

---

## 📝 Notes

- No Kick account or API key required for any core feature
- All data sourced from Kick's public API and kickstats.com
- The tool never writes to or modifies any Kick channel or account
- WebSocket auto-reconnects silently on dropped connections
- GPU detection results are cached — no need to re-detect each launch
- AI Analysis verdict locks the Viewbot Detector panel automatically

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## ⚡ Created by [Ask_fOr_DaX](https://github.com/AskForDax)

> This tool is not affiliated with or endorsed by Kick.com
