╔══════════════════════════════════════════════════════════════════════════════╗
║         KICK STREAM ANALYTICS & DEEP AI RESEARCH TOOL                      ║
║         by Ask_fOr_DaX                                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 DESCRIPTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A fully self-contained desktop analytics dashboard for Kick.com streamers.
Monitor multiple live streams simultaneously, detect viewbots with AI-powered
analysis, track chat behaviour, browse the global Top 100, analyse streamer
history and generate detailed reports — all from a single GUI with no Kick
account or API key required.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 TWO WAYS TO RUN THIS APP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ┌─────────────────────────────────────────────────────────────────────────┐
  │  METHOD              BEST FOR               PYTHON REQUIRED?            │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  A. Source (run.bat) Zero AV flags,         Yes — Python 3.9+           │
  │                      inspect/modify code    Run install.bat first       │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  B. Build your       Standalone exe,        Yes — Python 3.9+           │
  │     own EXE folder   share with others      Run build_folder.bat        │
  └─────────────────────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 IMPORTANT — ANTIVIRUS WARNING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  If your antivirus flags a compiled KickAnalytics.exe please read this.

  WHY IT GETS FLAGGED:
  Executables compiled with PyInstaller are sometimes flagged by heuristic
  antivirus scanners. This is a well-known false positive issue.

  THIS APPLICATION:
  ✓ Contains NO malware, backdoors or remote access tools
  ✓ Makes only outbound HTTPS requests to public APIs:
      kick.com          (stream and chat data — public API)
      kickstats.com     (Top 100 streamer data — public)
      api.anthropic.com (optional AI — only if you provide a key)
      127.0.0.1:11434   (optional local Ollama — your own machine only)
  ✓ Stores settings only in local JSON files next to the exe
  ✓ Uses Windows Credential Manager for optional API key storage only
  ✓ Has NO persistence — does not auto-start or modify your system
  ✓ Requires NO administrator privileges
  ✓ Full source code is included — inspect it yourself at any time

  YOUR OPTIONS IF AV BLOCKS THE EXE:
    Best — Use Method A (source version) — zero AV issues
    Alternative — Build your own exe (Method B) — unique hash
    Alternative — Add a Windows Defender exclusion for the folder

  IF WINDOWS SMARTSCREEN BLOCKS THE EXE:
    Click "More info" then "Run anyway"

  DO NOT submit the exe to VirusTotal.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 SYSTEM REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Operating System : Windows 10 or Windows 11 (64-bit)
  RAM              : 4GB minimum, 8GB recommended
  Internet         : Required for live monitoring and API features
  Python           : Required for both methods (Python 3.9 or higher)
  Ollama           : Optional — only needed for local AI analysis

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 METHOD A — SOURCE VERSION (run.bat)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. Place kick_report.py and install.bat in the same folder
  2. Double-click install.bat (run once — installs all packages)
  3. Double-click run.bat to launch at any time

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 METHOD B — BUILD YOUR OWN EXE FOLDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. Place kick_report.py, build_folder.bat and build_spec_folder.py together
  2. Double-click build_folder.bat
  3. Output at dist\KickAnalytics\ — ZIP and share
  !! Never separate KickAnalytics.exe from the _internal\ folder !!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GETTING STARTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. Launch the app using Method A or B above
  2. Enter a Kick streamer username (e.g. xqc)
  3. Set duration in seconds (default 600 = 10 minutes recommended)
  4. Click START to begin live monitoring
  5. Click STOP at any time to end the session
  6. Click Save Report to export a full analysis report

  MULTI-STREAMER: Click ➕ Add Streamer in the top bar to open
  additional tabs and monitor multiple streams simultaneously.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 SIDE PANEL — CHANNEL & LIVE STATS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  CHANNEL OVERVIEW
    Name, Status (LIVE/OFFLINE), Viewers, Category, Live For,
    Followers, Title

  CHATROOM SETTINGS
    Followers Only  Whether followers-only mode is active  ← new
    Slow Mode       Whether slow mode is active
    Sub Only        Whether chat is restricted to subscribers
    Emote Only      Whether only emotes are allowed

  LIVE STATS
    Sampling, Messages, Chatters, Msgs/min, Bots, Active,
    Subs seen, Gifts seen, Raids seen

  ACTIVITY BAR
    Visual chat volume bar chart — last 60 seconds

  VIEWBOT DETECTOR  (updates every 5 seconds)
    Risk Score   0-100 numeric score (locked to AI verdict after analysis)
    Verdict      CLEAN / LOW RISK / SUSPICIOUS / HIGH RISK
                 Shows "← AI Analysis" label after AI run
    Chat Ratio   % of viewers chatting (healthy: 3-8%)
    Msgs/1k vw   Messages per min per 1,000 viewers (healthy: 10-50)
    Vw Spike     Largest viewer jump in last 15 minutes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 TABS — PER STREAMER SESSION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  💬 LIVE CHAT
    Real-time chat. Colour coded badges.
    Filter by text, hide bots, pause scroll, badge filters,
    Spammers filter, Exclude Emotes option.

  🤖 AI ANALYSIS
    AI viewbot detection. Locked for 10 minutes after START.
    Supports Ollama (local/free) and Anthropic API (~$0.03/run).
    GPU Setup detects your hardware and recommends the best model.
    Auto-run option fires analysis automatically every X minutes.
    Results update the Viewbot Detector side panel automatically.

    GPU tiers and default models:
      20GB+    qwen3:32b     10-20GB  qwen3:14b
      7-10GB   qwen3:8b      5-7GB   mistral:7b
      3-5GB    qwen3:4b      1-3GB   llama3.2:3b
      CPU      phi3:mini

  🎉 EVENTS
    Real-time event log with icons:
      🚀 RAID        Channel raided with viewer count
      ⭐ SUB         New subscription
      🎁 GIFT        Gift subscriptions
      🔨 BAN         User banned from chat
      ✅ UNBAN       User unbanned
      📌 PIN         Message pinned
      🗑 DELETED     Message deleted
      📴 STREAM ENDED  Stream went offline

  👥 CHATTERS
    Sortable chatter table with bot classification.
    Auto Scan every 30 seconds (ticked by default).
    Export CSV button.

  🔤 TOP WORDS
    Bar chart of most used words. Hide emotes option.
    Auto Scan every 20 seconds (ticked by default).

  📊 ACTIVITY CHART
    Message volume chart over the full session.
    Auto Scan every 20 seconds (ticked by default).

  🎙 STREAMER INFO
    Full channel profile — loads automatically when monitoring starts.
    Social links are clickable and open in your default browser.
    Includes VODs, clips, bio, social links, stream stats.

  📅 HISTORY
    Past streams, clips, gift leaderboards, stream stats.
    Double-click a clip to open it in your browser.

  📄 REPORT
    Full session report — generate and save as text file.

  📖 AI GUIDE
    Built-in reference guide — embedded in the app.
    Covers how AI models work, GPU tiers, scoring and reading results.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 TABS — GLOBAL (PINNED LEFT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  🏅 TOP 100
    Live top 100 Kick streamers from kickstats.com.
    Region filter, time range, sortable columns.
    Double-click to open that streamer in a new monitor tab.

  📡 MULTI-CHANNEL
    Monitor multiple channels simultaneously.
    Auto-refreshes every 30 seconds.
    Default sort: LIVE channels first.
    Saved list restored on every launch.
    Double-click any row to open in Live Monitor.

    Auto Mon column (far right):
      Tick any channel to automatically open a monitor tab and
      start monitoring when that channel goes live.
      Requires Live Notifications/Auto Monitor Enable to be ticked.

    🔔 Live Notifications/Auto Monitor Enable:
      When ticked — shows a popup notification in the bottom right
      corner when any tracked channel goes live.
      Popup contains channel name, category, viewer count and a
      45 second countdown with Monitor and Dismiss buttons.
      Multiple notifications stack upward if several go live at once.
      Auto Mon channels start monitoring automatically without a popup.
      Always resets to OFF when the app is closed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 MULTI-STREAMER TABS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Click ➕ Add Streamer in the top bar to open a new session tab.
  Each tab is completely independent with its own chat engine,
  side panel stats, all inner tabs and AI analysis.
  Tab auto-renames to the streamer display name when connected.
  Double-click any tab to rename it manually.
  ✕ Close button removes the tab (last tab cannot be closed).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 OPTIONAL — SETTING UP OLLAMA FOR LOCAL AI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. Download from https://ollama.com and install (no admin needed)
  2. Ollama starts automatically in your system tray
  3. Open Command Prompt and pull a model based on your GPU:

       20GB+ VRAM:   ollama pull qwen3:32b
       8-10GB VRAM:  ollama pull qwen3:8b
       4-6GB VRAM:   ollama pull qwen3:4b
       CPU only:     ollama pull phi3:mini

  4. In the app — AI Analysis tab — click Test Connection
  5. Use GPU Setup to detect your hardware and get a recommendation
  6. Select your model and click Run AI Analysis

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PACKAGE CONTENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  README.txt              This guide
  AI_GUIDE.txt            AI model reference (also built into the app)
  LICENSE                 Personal Use License — read before using

  Method A — Source version:
    kick_report.py        Full application source code
    install.bat           First-time setup — installs packages
    run.bat               Daily launcher (created by install.bat)
    run_debug.bat         Debug launcher — shows errors in console

  Method B — Build your own EXE:
    kick_report.py        Full application source code (same file)
    build_folder.bat      Double-click to compile the EXE folder
    build_spec_folder.py  Build configuration — called automatically

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 LICENSE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  This software is licensed for personal, non-commercial use only.
  Commercial use by companies or organizations is strictly prohibited
  without explicit written permission from the author.
  See the LICENSE file for full terms.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 NOTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  - No Kick account or API key required for any core feature
  - All data sourced from Kick's public API and kickstats.com
  - The tool never writes to or modifies any Kick channel or account
  - AI Analysis needs 10 minutes of data for best results
  - GPU detection results are cached and restored automatically
  - WebSocket reconnects silently if dropped
  - Anthropic API costs approximately $0.03 per full analysis
  - The AI Guide tab is embedded — no external file needed
  - Do not submit your compiled exe to VirusTotal
  - This tool is not affiliated with or endorsed by Kick.com

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 CREATED BY  Ask_fOr_DaX
 https://github.com/AskForDax/KickStreamAnalytics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
