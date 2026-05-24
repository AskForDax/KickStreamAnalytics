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
 IMPORTANT — ANTIVIRUS WARNING FOR NEW USERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  If your antivirus flags KickAnalytics.exe please read this carefully.

  WHY IT GETS FLAGGED:
  This application is compiled using PyInstaller, a standard Python packaging
  tool used by thousands of legitimate applications. PyInstaller bundles the
  Python runtime and all libraries into a single executable. Antivirus programs
  use heuristic (behaviour-based) detection that sometimes misidentifies
  PyInstaller executables as suspicious because the self-extracting format
  resembles patterns used by malware — even though the actual code is clean.

  THIS APPLICATION:
  ✓ Contains NO malware, backdoors or remote access tools
  ✓ Makes only outbound HTTPS requests to public APIs:
      kick.com          (stream and chat data — public API)
      kickstats.com     (Top 100 streamer data — public)
      api.anthropic.com (optional AI analysis — only if you provide a key)
      127.0.0.1:11434   (optional local Ollama AI — your own machine only)
  ✓ Stores settings only in local JSON files next to the exe
  ✓ Uses Windows Credential Manager for optional API key storage only
  ✓ Has NO persistence — does not auto-start or modify your system
  ✓ Requires NO administrator privileges
  ✓ Installs NOTHING to your system

  WHAT TO DO IF YOUR AV FLAGS IT:

  Option A — Add an exclusion in Windows Defender:
    1. Open Windows Security
    2. Click Virus & Threat Protection
    3. Click Manage Settings under Virus & Threat Protection Settings
    4. Scroll to Exclusions and click Add or Remove Exclusions
    5. Click Add an Exclusion > Folder
    6. Select the KickAnalytics folder
    7. Run KickAnalytics.exe normally

  Option B — Restore from quarantine (Windows Defender):
    1. Open Windows Security
    2. Click Virus & Threat Protection
    3. Click Protection History
    4. Find the quarantined file and click Restore

  Option C — Run from source (zero AV flags):
    See the SOURCE VERSION section below. Running from the Python
    source script produces no AV warnings at all.

  DO NOT submit the exe to VirusTotal — this broadcasts the file hash
  to 70+ AV vendors and can cause wider false positive detections.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 SYSTEM REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Operating System : Windows 10 or Windows 11 (64-bit)
  RAM              : 4GB minimum, 8GB recommended
  Internet         : Required for all live monitoring and API features
  Python           : NOT required for the exe version
  Ollama           : Optional — only needed for local AI analysis feature

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 INSTALLATION — EXE VERSION (Recommended)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. Extract the KickAnalytics folder from the ZIP file
  2. Place the folder anywhere on your computer
  3. Double-click KickAnalytics.exe to launch
  4. No installation required — no Python needed

  FOLDER CONTENTS:
    KickAnalytics\
      KickAnalytics.exe     Main application
      _internal\            Python runtime (do not delete)
      README.txt            This file

  FILES CREATED AUTOMATICALLY ON FIRST USE:
    ai_settings.json        AI provider settings and GPU detection cache
    multi_channels.json     Saved Multi-Channel streamer list

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 INSTALLATION — SOURCE VERSION (Zero AV flags)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Requirements: Python 3.9 or higher with tkinter

  1. Place these files in the same folder:
       kick_report.py
       install.bat

  2. Double-click install.bat
     - Detects your Python installation automatically
     - Installs all required packages into a local packages\ folder
     - Creates run.bat launcher automatically

  3. Double-click run.bat to launch at any time

  Packages installed automatically:
    typer        Dependency conflict resolver
    websockets   Real-time chat WebSocket connection
    colorama     Console colour support
    tabulate     Table formatting
    curl_cffi    Cloudflare bypass for Kick API requests
    keyring      Secure API key storage (Windows Credential Manager)
    GPUtil       GPU detection for AI model recommendations
    psutil       Process detection

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GETTING STARTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. Launch the application
  2. Enter a Kick streamer username in the Streamer field (e.g. xqc)
  3. Set duration in seconds (default 600 = 10 minutes recommended)
  4. Click START to begin live monitoring
  5. Click STOP at any time to end the session
  6. Click Save Report to export a full analysis report

  MULTI-STREAMER: Click the green ➕ Add Streamer button in the top bar
  to open additional session tabs and monitor multiple streams at once.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 SIDE PANEL — CHANNEL & LIVE STATS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Updates live every second while monitoring. Polls the Kick API every
  30 seconds to refresh viewer count, followers and stream info.

  CHANNEL OVERVIEW
    Name         Streamer display name
    Status       LIVE or OFFLINE
    Viewers      Current viewer count (live from Kick API)
    Category     Current stream category or game
    Live For     How long the stream has been running
    Followers    Total channel followers (live from Kick API)
    Title        Current stream title

  CHATROOM SETTINGS
    Slow Mode    Whether slow mode is active in chat
    Sub Only     Whether chat is restricted to subscribers
    Emote Only   Whether only emotes are allowed

  LIVE STATS  (updates every second)
    Sampling     How long this monitoring session has been running
    Messages     Total chat messages received this session
    Chatters     Total unique users who sent at least one message
    Msgs/min     Current chat messages per minute rate
    Bots         Known bots detected by name pattern
    Active       Users who have sent 5 or more messages
    Subs seen    Subscription events received this session
    Gifts seen   Gift subscription events received this session
    Raids seen   Raid events received this session

  ACTIVITY BAR
    Visual bar chart of chat volume over the last 60 seconds.
    Updates every second. Useful for spotting hype moments.

  VIEWBOT DETECTOR  (updates every 5 seconds)
    Risk Score   0-100 suspicion score from four signals
    Verdict      CLEAN / LOW RISK / SUSPICIOUS / HIGH RISK
    Chat Ratio   Percentage of viewers who are chatting
                 Healthy streams: 3-8%. Below 1% is suspicious.
    Msgs/1k vw   Messages per minute per 1,000 viewers
                 Healthy: 10-50. Below 5 is suspicious.
    Vw Spike     Largest sudden viewer jump in the last 15 minutes
                 Jumps over 50% in under 3 minutes are flagged.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 TABS — PER STREAMER SESSION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  💬 LIVE CHAT
    Real-time chat with colour-coded badges.
    Green=regular  Yellow=mod/VIP  Purple=subscriber  Red=bot

    Toolbar row 1:
      Filter        Type username or keyword to show matching messages
      Hide Bots     Toggle to hide all detected bot messages
      Pause Scroll  Freeze auto-scrolling to read at your own pace
      Clear         Clear the chat display (data is still collected)
      Watch Stream  Open the streamer Kick page in your browser

    Toolbar row 2 — Show filters (multiple can be ticked):
      All Chatters    Default — show all messages
      Subscribers     Show only subscriber messages
      VIP             Show only VIP messages
      Moderators      Show only moderator messages
      Non Subscribers Show only users without a subscriber badge
      Exclude Emotes  When used with Spammers — ignores emote-only spam
      Spammers        Show only users sending the same message 2+
                      times within 2 seconds

  🤖 AI ANALYSIS
    AI-powered viewbot detection and stream analysis.
    Requires either Ollama (local, free) or an Anthropic API key.

    Provider selector:
      Ollama (Local — Free)    Runs AI on your own machine, no cost
      Anthropic API (Claude)   Uses Claude AI via API key

    Ollama setup:
      URL field     Default: http://127.0.0.1:11434
      Model         Populated automatically after Test Connection
      Test Connection  Connects to Ollama and loads installed models
                       Shows install guide if Ollama is not found

    GPU Setup strip:
      Detect GPU    Scans your hardware and recommends the best model
                    for your GPU tier. Results saved automatically.
      Download      Downloads the recommended model via Ollama
                    Shows live progress bar during download

    GPU tiers and recommended models:
      20GB+ VRAM    qwen3:32b   (best quality)
      10-20GB       qwen3:14b
      7-10GB        qwen3:8b    (recommended for RTX 3070/3080 — best local model)
      5-7GB         mistral:7b
      3-5GB         qwen3:4b
      1-3GB         llama3.2:3b
      CPU only      phi3:mini   (optimised for CPU, no GPU needed)

    Analysis controls:
      Run AI Analysis   Manually trigger an analysis
                        Locked for 10 minutes after START to ensure
                        enough data is collected for accurate results
      Auto-run          Tick and set interval to run automatically
      Stop Auto-Run     Cancel the scheduled auto-run
      Save Analysis     Export the full report to a text file
      Clear             Clear the analysis output

    The AI report contains six sections:
      1. Executive Summary
      2. Signal Analysis (each metric examined individually)
      3. Suspicious Patterns Identified
      4. Legitimate Explanations considered
      5. Confidence Assessment
      6. Final Verdict with score 0-100

    Anthropic API key:
      Paste your key from console.anthropic.com
      Tick Remember Key to save securely in Windows Credential Manager
      Key is never written to any file on disk

  🎉 EVENTS
    Logs all non-chat events in real time:
      RAID    Channel hosted with viewer count
      SUB     New subscription with months subscribed
      GIFT    Gift subscriptions with gifter name and quantity
      BAN     User banned from chat
      PIN     Message pinned by a moderator

  👥 CHATTERS
    Sortable table of all unique chatters this session.
    Columns: Username, messages, type, rate, badges
    Filter by type: Active / Casual / Lurker / Known Bot / Likely Bot
    Export CSV button saves the full chatter list

    Classification:
      Active      5+ messages, not a bot
      Casual      2-4 messages
      Lurker      1 message
      Known Bot   Matched known bot name pattern
      Likely Bot  2+ messages/sec OR 90%+ identical messages
                  AND no mod/sub/VIP badge

  🔤 TOP WORDS
    Bar chart of most used words and emotes by human chatters.
    Hide Emotes     Filter out Kick emote IDs (word+digits format)
    Auto-refresh    Automatically refreshes the list every 60 seconds
    Emotes shown in purple, regular words in green

  📊 ACTIVITY CHART
    Bar chart of message volume over the full monitoring session.
    Highest activity bucket highlighted. Click Refresh Chart to update.

  🎙 STREAMER INFO
    Full channel profile loaded from Kick API.
    Enter any username and click Load Info.

    Profile card:    Display name, verified status, followers,
                     channel age, total streams, avg/peak viewers,
                     mature flag, subscriber badge count, social links
    Channel Bio:     Full bio text from their Kick profile
    Stream Activity: Total hours streamed, avg duration, frequency
    Top Categories:  Bar chart of most streamed games by stream count
    Recent Streams:  Last 15 VODs with date, title, category, viewers
    Top Clips:       Top 10 clips — double-click opens in browser
    Watch Stream:    Opens their Kick page in your browser
    Export:          Saves a text summary to file

  📅 HISTORY
    Historical data for any channel. Enter username and click Load.

    Past Streams    VODs with date, title, category, duration, viewers
                    Paginate with Prev/Next. Export to CSV.

    Clips           Channel clips sorted by views or date
                    Double-click opens clip directly in your browser
                    Export to CSV

    Leaderboards    Top all-time gifters (left panel)
                    Top gifters this week (right panel)
                    Note: Kick does not expose subscriber leaderboards

    Stream Stats    Auto-generated summary: total VODs, avg duration,
                    peak and average viewers, top categories, top clips

  📄 REPORT
    Full plain-text analytics report for the current session.
    Includes: channel info, stream status, chatroom settings,
    chat statistics, event counts, viewbot analysis, top chatters,
    top words and curve analysis data.
    Generate Report  Build and display the report
    Save to File     Export as .txt file

  📖 AI GUIDE
    Built-in reference guide covering everything you need to know
    about the AI analysis features. Embedded directly in the app —
    no internet connection or external file required.

    Contents:
      Section 1  How AI models work with this application
      Section 2  Default models by GPU tier and how they work
      Section 3  How AI calculates scores — small vs large models
                 and why the Claude API produces superior results
      Section 4  How to read your AI analysis report in detail
                 including what each verdict label means and
                 what action to take for each outcome

    Scroll to Top button jumps back to the beginning.
    Fully colour coded for easy reading.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 TABS — GLOBAL (PINNED LEFT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  🏅 TOP 100
    Live ranking of the top 100 streamers on Kick pulled from
    kickstats.com. Click Refresh Now to load current data.

    Time Range:
      Live Now    Currently live streamers sorted by viewer count
      Today       Channels sorted by followers (24h proxy)
      This Week   Channels sorted by followers (7-day proxy)
      This Month  Channels sorted by followers (30-day proxy)

    Region Filter (radio buttons):
      Global / English / Spanish / Arabic / Turkish /
      German / Japanese / Portuguese / French
      Filters by stream language after loading — instant, no re-fetch

    Language column shows stream language from Kick API.
    Category filter: type to filter by game or streamer name.
    Click any column header to sort ascending or descending.
    Click a row for details. Double-click to open in Live Monitor.
    Export CSV saves the full current list.

  📡 MULTI-CHANNEL
    Monitor multiple Kick channels simultaneously.

    Add Streamer    Type username and click Add or press Enter
    Remove Selected Remove the highlighted channel
    Remove All      Clear the entire list (with confirmation)
    Auto-refresh    Refreshes all channels every 30 seconds
    Double-click    Opens that channel in the Live Monitor tab
    Export CSV      Snapshot of all tracked channels

    Columns sortable by clicking headers.
    Default sort: Status (LIVE channels shown first).
    List is saved automatically and restored on next launch.

    Auto-Report Scheduler:
      Enable      Tick to activate automatic report saving
      Every       Set interval in minutes
      Save to     Choose destination folder
      Browse      Pick folder with file dialog
      Status      Shows time of last successful save

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 MULTI-STREAMER TABS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Click ➕ Add Streamer in the top bar to open a new session tab.
  Each tab is completely independent with its own:
    Chat engine, WebSocket connection, side panel stats,
    all inner tabs, AI analysis, and report

  Tab auto-renames to the streamer display name when connected.
  LIVE indicator shown as 🔴 in the tab label.
  Double-click any tab to rename it manually.
  ✕ Close button removes the tab (last tab cannot be closed).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 OPTIONAL — SETTING UP OLLAMA FOR LOCAL AI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Ollama lets you run AI models locally on your machine for free.
  It is only required for the AI Analysis tab local option.

  1. Download Ollama from  https://ollama.com
  2. Run the installer — no admin rights required
  3. Ollama starts automatically in your system tray
  4. Open Command Prompt and run one of these based on your GPU:

     20GB+ VRAM:   ollama pull qwen3:32b
     8-10GB VRAM:  ollama pull llama3.1:8b
     4-6GB VRAM:   ollama pull qwen3:4b
     CPU only:     ollama pull phi3:mini

  5. Open the AI Analysis tab in the app
  6. Click Test Connection — your models will appear in the dropdown
  7. Select your model and click Run AI Analysis

  The app's GPU Setup button will automatically detect your GPU
  and recommend the best model for your hardware.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 NOTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  - No Kick account or API key required for any core feature
  - All data is sourced from Kick's public API and kickstats.com
  - The tool never writes to or modifies any Kick channel or account
  - Viewer history time-range data uses follower count as a proxy
    since Kick does not expose historical viewer data publicly
  - The Pusher WebSocket key used for chat may change over time.
    If chat stops connecting check for an updated version
  - AI Analysis needs 10 minutes of monitoring data for best results
    The Run AI Analysis button is locked for the first 10 minutes
  - GPU detection results are cached and restored automatically
    on next launch — no need to re-detect each time
  - The AI Guide tab is embedded in the app — no external file needed
  - This tool is not affiliated with or endorsed by Kick.com

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 CREATED BY  Ask_fOr_DaX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
