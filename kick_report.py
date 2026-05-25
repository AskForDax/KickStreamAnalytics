#!/usr/bin/env python3
"""
Kick.com Streamer Analytics - GUI Edition
Full real-time dashboard with chat feed, events, charts and reports.
"""

import sys, os

# Resolve app directory correctly for both .py and PyInstaller .exe
if getattr(sys, 'frozen', False):
    # Running as compiled exe — use the exe's directory
    APP_DIR = os.path.dirname(sys.executable)
else:
    # Running as .py script
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, os.path.join(APP_DIR, 'packages'))

# Hide the console window on Windows
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.user32.ShowWindow(
            ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except Exception:
        pass

import json, re, time, threading, asyncio, urllib.request, ssl, argparse
from collections import defaultdict, Counter
from datetime import datetime, timezone
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox

# ── Optional deps ──────────────────────────────────────────────
try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

try:
    import websockets
    HAS_WS = True
except ImportError:
    HAS_WS = False

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

# ── Constants ──────────────────────────────────────────────────
KICK_API_BASE = "https://kick.com/api/v2"
PUSHER_KEY    = "32cbd69e4b950bf97679"
PUSHER_URL    = f"wss://ws-us2.pusher.com/app/{PUSHER_KEY}?protocol=7&client=js&version=8.4.0-rc2&flash=false"

BOT_NAMES = re.compile(
    r"bot$|^bot|nightbot|streamelements|streamlabs|moobot|wizebot|fossabot|"
    r"supibot|soundalerts|commanderroot|sery_bot|titlechange_bot|logviewer|"
    r"stay_hydrated_bot|own3d|restreambot|omnibotx|coebot|ohbot|modbot|automoderator",
    re.IGNORECASE
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://kick.com/",
}

# ── Colour palette ─────────────────────────────────────────────
BG       = "#0f1117"
BG2      = "#1a1d27"
BG3      = "#22263a"
ACCENT   = "#53fc18"   # Kick green
ACCENT2  = "#a855f7"   # purple
RED      = "#ef4444"
YELLOW   = "#facc15"
BLUE     = "#38bdf8"
WHITE    = "#f0f0f0"
GREY     = "#6b7280"
CHATBG   = "#13161f"

# ══════════════════════════════════════════════════════════════
#  DATA LAYER
# ══════════════════════════════════════════════════════════════

def api_get(url, params=None):
    try:
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        if HAS_CURL_CFFI:
            r = cffi_requests.get(url, headers=HEADERS, impersonate="chrome124", timeout=10)
            r.raise_for_status()
            return r.json()
        req = urllib.request.Request(url, headers=HEADERS)
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return None

def get_channel(slug):
    return api_get(f"{KICK_API_BASE}/channels/{slug}")

def get_videos(slug, page=1):
    return api_get(f"{KICK_API_BASE}/channels/{slug}/videos", {"page": page})

def get_clips(slug, page=1, sort="view"):
    return api_get(f"{KICK_API_BASE}/channels/{slug}/clips", {"page": page, "sort": sort})

def get_leaderboard(slug):
    return api_get(f"{KICK_API_BASE}/channels/{slug}/leaderboards")

def get_top_streams(page=1, limit=25):
    """
    Fetch live streams using multiple endpoint strategies.
    Returns list of stream dicts or None.
    """
    # Try featured livestreams first (works without auth, returns top live channels)
    for lang in ["en", "es", "ar", "tr", "de", "pt", "fr", "ko", "ja"]:
        data = api_get(f"{KICK_API_BASE}/featured-livestreams/{lang}", {"limit": limit})
        if data and isinstance(data, list) and len(data) > 2:
            return data
        if data and isinstance(data, dict):
            items = data.get("data") or data.get("channels") or []
            if len(items) > 2:
                return items
    # Fallback: browse channels sorted by viewers
    data = api_get(f"{KICK_API_BASE}/channels",
                   {"sort": "viewer_count", "page": page, "limit": limit})
    return data

def get_featured_streams():
    """Get featured/top live streams across all languages."""
    all_streams = []
    seen_slugs  = set()
    for lang in ["en", "es", "ar", "tr", "de", "pt", "fr"]:
        data = api_get(f"{KICK_API_BASE}/featured-livestreams/{lang}", {"limit": 20})
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("data") or data.get("channels") or []
        for item in items:
            ch   = item.get("channel", item)
            slug = ch.get("slug","")
            if slug and slug not in seen_slugs:
                seen_slugs.add(slug)
                all_streams.append(item)
    return all_streams

def get_channel_poll(slug):
    """Lightweight poll — just followers + live status."""
    data = api_get(f"{KICK_API_BASE}/channels/{slug}")
    if not data: return None
    ls = data.get("livestream")
    followers = (data.get("followersCount")
              or data.get("followers_count")
              or data.get("followers")
              or 0)
    cats = []
    if ls:
        cats = ls.get("categories", [])
    cat = cats[0].get("name","N/A") if cats else "N/A"
    return {
        "slug":      slug,
        "followers": followers,
        "is_live":   bool(ls),
        "viewers":   ls.get("viewer_count", 0) if ls else 0,
        "category":  cat,
        "last_updated": time.time(),
        "ts":        time.time(),
    }

def export_csv(path, headers, rows):
    """Write a simple CSV file."""
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)

def parse_kick_time(s):
    """
    Parse Kick's datetime strings robustly.
    Kick returns: '2026-05-17 21:12:34' (space-separated, no timezone)
    Also handles: '2026-05-17T21:12:34Z', '2026-05-17T21:12:34+00:00'
    Returns a UTC-aware datetime or None.
    """
    if not s: return None
    try:
        # Normalise: replace space with T, strip trailing chars
        clean = str(s).strip().replace(" ", "T")
        # Add Z if no timezone info present
        if "+" not in clean and clean.endswith(("Z",)):
            clean = clean[:-1] + "+00:00"
        elif "+" not in clean and "-" not in clean[10:]:
            # No timezone at all — assume UTC
            clean = clean + "+00:00"
        elif clean.endswith("Z"):
            clean = clean[:-1] + "+00:00"
        return datetime.fromisoformat(clean)
    except Exception:
        try:
            # Last resort: strip to just date+time and assume UTC
            clean = str(s).strip()[:19].replace(" ", "T")
            return datetime.fromisoformat(clean).replace(tzinfo=timezone.utc)
        except Exception:
            return None

def calc_live_for(started_str):
    """Calculate 'Xh Ym Zs' from a Kick start time string."""
    dt = parse_kick_time(started_str)
    if not dt: return "N/A"
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        if delta.total_seconds() < 0: return "N/A"
        h, r   = divmod(int(delta.total_seconds()), 3600)
        m, sec = divmod(r, 60)
        if h:  return f"{h}h {m}m {sec}s"
        if m:  return f"{m}m {sec}s"
        return f"{sec}s"
    except Exception:
        return "N/A"

def fmt_duration(ms):
    if not ms: return "N/A"
    s    = int(ms) // 1000
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    if h:  return f"{h}h {m}m"
    if m:  return f"{m}m {s}s"
    return f"{s}s"

def fmt_date(s):
    if not s: return "N/A"
    dt = parse_kick_time(s)
    if dt:
        return dt.strftime("%Y-%m-%d  %H:%M")
    return str(s)[:16]

def parse_channel(data):
    if not data:
        return None
    ls = data.get("livestream")
    started_dt   = None
    duration_str = "N/A"
    if ls:
        s = ls.get("start_time") or ls.get("created_at")
        if s:
            started_dt   = parse_kick_time(s)
            duration_str = calc_live_for(s)

    cat = "N/A"
    if ls:
        cats = ls.get("categories", [])
        if cats:
            cat = cats[0].get("name", "N/A")

    # followers field name varies across API versions
    followers = (data.get("followersCount")
              or data.get("followers_count")
              or data.get("followers")
              or 0)

    return {
        "slug":          data.get("slug", "N/A"),
        "display_name":  data.get("user", {}).get("username", "N/A"),
        "channel_id":    data.get("id"),
        "chatroom_id":   data.get("chatroom", {}).get("id"),
        "followers":     followers,
        "verified":      data.get("verified", False),
        "mature":        data.get("is_mature", False),
        "bio":           (data.get("user", {}).get("bio") or "")[:120],
        "is_live":       bool(ls),
        "stream_title":  ls.get("session_title", "N/A") if ls else "N/A",
        "viewer_count":  ls.get("viewer_count", 0) if ls else 0,
        "category":      cat,
        "duration":      duration_str,
        "started_at":    started_dt,
        "slow_mode":     data.get("chatroom", {}).get("slow_mode", False),
        "sub_mode":      data.get("chatroom", {}).get("subscribers_mode", False),
        "emote_mode":    data.get("chatroom", {}).get("emotes_mode", False),
        "social":        {p: data.get("user", {}).get(p, "") for p in
                          ["twitter","youtube","instagram","discord","tiktok"]
                          if data.get("user", {}).get(p)},
    }

# ══════════════════════════════════════════════════════════════
#  CHAT ENGINE
# ══════════════════════════════════════════════════════════════

class ChatEngine:
    def __init__(self):
        self.reset()

    def reset(self):
        self.messages      = []
        self.events        = []          # raids, subs, gifts, clips
        self.user_msgs     = defaultdict(list)
        self.user_first    = {}
        self.user_last     = {}
        self.user_badges   = defaultdict(set)
        self.start_time    = None
        self.running       = False
        self._loop         = None
        self._thread       = None
        # callbacks set by GUI
        self.on_message      = None
        self.on_event        = None
        self.on_connected    = None
        self.on_reconnecting = None
        self.on_error        = None

    def record_message(self, payload):
        now     = time.time()
        sender  = payload.get("sender", {})
        name    = sender.get("slug") or sender.get("username") or "unknown"
        content = payload.get("content", "")
        badges  = [b.get("text","") for b in
                   sender.get("identity",{}).get("badges",[]) if b.get("text")]
        msg = {"username": name, "content": content,
               "timestamp": now, "badges": badges}
        self.messages.append(msg)
        self.user_msgs[name].append(content)
        if name not in self.user_first:
            self.user_first[name] = now
        self.user_last[name] = now
        for b in badges:
            self.user_badges[name].add(b)
        if self.on_message:
            self.on_message(msg)

    def record_event(self, kind, data):
        ev = {"kind": kind, "data": data, "timestamp": time.time()}
        self.events.append(ev)
        if self.on_event:
            self.on_event(ev)

    async def _connect(self, chatroom_id, channel_id=None):
        extra = {
            "Origin": "https://kick.com",
            "User-Agent": HEADERS["User-Agent"],
        }
        max_retries = 10
        retry_delay = 3
        attempt     = 0

        while self.running and attempt < max_retries:
            try:
                async with websockets.connect(
                    PUSHER_URL,
                    additional_headers=extra,
                    ping_interval=20,
                    ping_timeout=10,
                    open_timeout=15,
                ) as ws:
                    await ws.send(json.dumps({
                        "event": "pusher:subscribe",
                        "data":  {"auth": "", "channel": f"chatrooms.{chatroom_id}.v2"}
                    }))
                    if channel_id:
                        await ws.send(json.dumps({
                            "event": "pusher:subscribe",
                            "data":  {"auth": "", "channel": f"channel.{channel_id}"}
                        }))
                    if self.on_connected:
                        self.on_connected()
                    attempt = 0  # reset on successful connect

                    async for raw in ws:
                        if not self.running:
                            return
                        try:
                            env   = json.loads(raw)
                            event = env.get("event","")
                            if event == "pusher:ping":
                                await ws.send(json.dumps({"event":"pusher:pong","data":{}}))
                            elif event in (
                                "App\\Events\\ChatMessageEvent",
                                "App\\Events\\ChatMessageSentEvent",
                            ):
                                p = env.get("data","{}");
                                if isinstance(p, str): p = json.loads(p)
                                self.record_message(p)
                            elif event in (
                                "App\\Events\\SubscriptionEvent",
                                "App\\Events\\NewSubscriberEvent",
                                "App\\Events\\SubscriptionCreatedEvent",
                                "App\\Events\\ChannelSubscriptionEvent",
                            ):
                                p = env.get("data","{}");
                                if isinstance(p, str): p = json.loads(p)
                                self.record_event("subscription", p)
                            elif event in (
                                "App\\Events\\GiftedSubscriptionsEvent",
                                "App\\Events\\GiftSubscriptionsEvent",
                                "App\\Events\\SubscriptionGiftedEvent",
                                "App\\Events\\LuckyUsersWhoGotGiftSubscriptionsEvent",
                            ):
                                p = env.get("data","{}");
                                if isinstance(p, str): p = json.loads(p)
                                self.record_event("gift", p)
                            elif event in (
                                "App\\Events\\StreamHostEvent",
                                "App\\Events\\ChannelHostEvent",
                            ):
                                p = env.get("data","{}");
                                if isinstance(p, str): p = json.loads(p)
                                self.record_event("raid", p)
                            elif event in (
                                "App\\Events\\ChatMessageDeletedEvent",
                                "App\\Events\\MessageDeletedEvent",
                            ):
                                p = env.get("data","{}");
                                if isinstance(p, str):
                                    try: p = json.loads(p)
                                    except: p = {}
                                self.record_event("delete", p)
                            elif event == "App\\Events\\UserBannedEvent":
                                p = env.get("data","{}");
                                if isinstance(p, str): p = json.loads(p)
                                self.record_event("ban", p)
                            elif event == "App\\Events\\UserUnbannedEvent":
                                p = env.get("data","{}");
                                if isinstance(p, str): p = json.loads(p)
                                self.record_event("unban", p)
                            elif event == "App\\Events\\PinnedMessageCreatedEvent":
                                p = env.get("data","{}");
                                if isinstance(p, str): p = json.loads(p)
                                self.record_event("pin", p)
                            elif event in (
                                "App\\Events\\GiftsLeaderboardUpdated",
                            ):
                                p = env.get("data","{}");
                                if isinstance(p, str): p = json.loads(p)
                                self.record_event("gift", p)
                            elif event == "App\\Events\\StopStreamBroadcast":
                                p = env.get("data","{}");
                                if isinstance(p, str):
                                    try: p = json.loads(p)
                                    except: p = {}
                                self.record_event("streamend", p)
                            elif event not in (
                                "pusher:connection_established",
                                "pusher_internal:subscription_succeeded",
                                "pusher:pong",
                            ):
                                p = env.get("data","{}");
                                if isinstance(p, str):
                                    try: p = json.loads(p)
                                    except: p = {}
                                if isinstance(p, dict) and p:
                                    self.record_event("unknown", {"event": event, "data": p})
                        except:
                            pass

            except Exception as e:
                if not self.running:
                    return
                err_str = str(e)
                # 4200 = Pusher reconnect immediately — silent auto-reconnect
                transient = any(c in err_str for c in
                    ["4200", "1001", "1006", "1011",
                     "ConnectionClosed", "connection closed",
                     "no close frame", "timed out"])
                if transient:
                    if hasattr(self, "on_reconnecting") and self.on_reconnecting:
                        self.on_reconnecting(attempt + 1)
                    attempt += 1
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    if self.on_error:
                        self.on_error(err_str)
                    return

    def _run_loop(self, chatroom_id, channel_id=None):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect(chatroom_id, channel_id))

    def start(self, chatroom_id, channel_id=None):
        self.running    = True
        self.start_time = time.time()
        self._thread    = threading.Thread(
            target=self._run_loop, args=(chatroom_id, channel_id), daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    # ── Analytics ─────────────────────────────────────────────
    def classify(self):
        # Badge keywords that indicate a real human — exempt from likely_bot
        HUMAN_BADGES = {
            "moderator", "mod", "subscriber", "sub", "vip",
            "founder", "og", "staff", "verified", "broadcaster",
        }
        results = {}
        for name, msgs in self.user_msgs.items():
            n    = len(msgs)
            span = self.user_last[name] - self.user_first[name]
            rate = n / span if span > 1 else float(n)
            rep  = Counter(msgs).most_common(1)[0][1] / n if n >= 2 else 0

            # Check if user has any badge that confirms they're human
            badges_lower = {b.lower() for b in self.user_badges.get(name, set())}
            is_badged    = bool(badges_lower & HUMAN_BADGES)

            if BOT_NAMES.search(name):
                label = "known_bot"
            elif (not is_badged               # never flag badged users as bots
                  and n >= 5
                  and (rate >= 2.0            # raised from 0.5 — needs 2 msgs/sec sustained
                       or rep >= 0.9)):       # raised from 0.8 — needs 90% identical msgs
                label = "likely_bot"
            elif n >= 5:
                label = "active"
            elif n >= 2:
                label = "casual"
            else:
                label = "lurker"
            results[name] = {
                "label": label, "count": n,
                "rate": round(rate, 3), "rep": round(rep, 2),
                "badges": list(self.user_badges.get(name, set()))
            }
        return results

    def top_words(self, classified, n=25):
        bots = {u for u,d in classified.items() if "bot" in d["label"]}
        skip = {"the","a","an","is","it","in","of","to","and","i","you","he",
                "she","we","they","on","at","for","was","are","with","this",
                "that","be","has","have","do","did","not","no","so","if","but",
                "or","me","my","your","its","im","just","like","can","ok",
                "okay","yeah","yes","lol","omg","i'm","its","go","get","got"}
        ctr = Counter()
        for u, msgs in self.user_msgs.items():
            if u in bots: continue
            for m in msgs:
                for w in m.split():
                    w = re.sub(r"[^\w]","",w).lower()
                    if w and w not in skip and len(w) > 1:
                        ctr[w] += 1
        return ctr.most_common(n)

    def timeline(self, buckets=20):
        if not self.messages: return []
        elapsed = time.time() - self.start_time
        bsize   = max(elapsed / buckets, 1)
        counts  = [0] * buckets
        for m in self.messages:
            i = int((m["timestamp"] - self.start_time) / bsize)
            counts[min(i, buckets-1)] += 1
        return counts

# ══════════════════════════════════════════════════════════════
#  GUI
# ══════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════
#  STREAMER SESSION — one per monitored streamer
# ══════════════════════════════════════════════════════════════

class StreamerSession:
    """
    A self-contained session for one streamer.
    Owns its own ChatEngine, channel data and all per-streamer UI widgets.
    Instantiated by KickGUI each time a new streamer tab is opened.
    """
    def __init__(self, parent_frame, root, app):
        self.root    = root
        self.app     = app
        self.engine  = ChatEngine()
        self.channel = None
        self._viewer_history    = []
        self._words_auto_id     = None
        self._filter_after_id   = None
        self._info_clip_data    = []
        self._info_channel_data = None
        self._vod_data          = []
        self._clip_data         = []
        self._current_hist_slug = ""
        self._vod_current_page  = 1
        self._clip_current_page = 1
        self._countdown_secs    = 0   # remaining seconds on duration countdown
        self._countdown_id      = None  # after() job id for countdown tick
        self._ai_verdict_locked = False  # True after AI analysis — prevents numeric override

        self._build_session_topbar(parent_frame)
        main_area = tk.Frame(parent_frame, bg=BG)
        main_area.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self._build_left(main_area)
        self._build_right(main_area)
        self._tick()

    def _build_session_topbar(self, parent):
        """Per-session topbar: streamer input, start/stop, save, close tab."""
        bar = tk.Frame(parent, bg=BG2, height=46)
        bar.pack(fill="x", padx=0, pady=(0,2))
        bar.pack_propagate(False)

        ctrl = tk.Frame(bar, bg=BG2)
        ctrl.pack(side="left", padx=10)

        tk.Label(ctrl, text="Streamer:", bg=BG2, fg=WHITE,
                 font=("Segoe UI",10)).grid(row=0, column=0, padx=(0,4))
        self.slug_var = tk.StringVar()
        e = tk.Entry(ctrl, textvariable=self.slug_var, width=18,
                     bg=BG3, fg=WHITE, insertbackground=WHITE,
                     font=("Segoe UI",11), relief="flat", bd=4)
        e.grid(row=0, column=1, padx=(0,8))
        e.bind("<Return>", lambda _: self._start())

        tk.Label(ctrl, text="Duration (s):", bg=BG2, fg=WHITE,
                 font=("Segoe UI",10)).grid(row=0, column=2, padx=(0,4))
        self.dur_var = tk.StringVar(value="600")
        self.dur_entry = tk.Entry(ctrl, textvariable=self.dur_var, width=6,
                 bg=BG3, fg=WHITE, insertbackground=WHITE,
                 font=("Segoe UI",11), relief="flat", bd=4)
        self.dur_entry.grid(row=0, column=3, padx=(0,8))

        self.start_btn = tk.Button(ctrl, text="▶ START", command=self._start,
                                   bg=ACCENT, fg="#000", font=("Segoe UI",10,"bold"),
                                   relief="flat", padx=12, pady=3, cursor="hand2")
        self.start_btn.grid(row=0, column=4, padx=3)

        self.stop_btn = tk.Button(ctrl, text="■ STOP", command=self._stop,
                                  bg=RED, fg=WHITE, font=("Segoe UI",10,"bold"),
                                  relief="flat", padx=12, pady=3, cursor="hand2",
                                  state="disabled")
        self.stop_btn.grid(row=0, column=5, padx=3)

        tk.Button(ctrl, text="💾 Save Report", command=self._save_report,
                  bg=BG3, fg=WHITE, font=("Segoe UI",10),
                  relief="flat", padx=10, pady=3, cursor="hand2").grid(row=0, column=6, padx=6)

        # Close tab button
        tk.Button(bar, text="✕ Close",
                  command=lambda: self.app._close_session(self),
                  bg=BG3, fg=GREY, font=("Segoe UI",8),
                  relief="flat", padx=6, pady=2, cursor="hand2").pack(side="right", padx=6)

        self.status_var = tk.StringVar(value="Enter a streamer name and press START")
        tk.Label(bar, textvariable=self.status_var, bg=BG2, fg=GREY,
                 font=("Segoe UI",9)).pack(side="right", padx=8)

    def _style_tree(self, tree):
        style = ttk.Style()
        style.configure("Treeview",
                        background=BG2, foreground=WHITE,
                        fieldbackground=BG2, rowheight=24,
                        font=("Segoe UI",10))
        style.configure("Treeview.Heading",
                        background=BG3, foreground=ACCENT,
                        font=("Segoe UI",10,"bold"))
        style.map("Treeview", background=[("selected", BG3)])


    def _build_left(self, parent):
        left = tk.Frame(parent, bg=BG2, width=280)
        left.pack(side="left", fill="y", padx=(0,6))
        left.pack_propagate(False)

        # Channel card
        ch_header = tk.Frame(left, bg=BG2)
        ch_header.pack(fill="x", padx=0)
        tk.Label(ch_header, text="CHANNEL", bg=BG2, fg=GREY,
                 font=("Segoe UI",8,"bold")).pack(side="left", padx=12, pady=(10,2))
        self.lbl_ch_updated = tk.Label(ch_header, text="", bg=BG2, fg=GREY,
                                        font=("Segoe UI",7))
        self.lbl_ch_updated.pack(side="right", padx=8, pady=(10,2))
        card = tk.Frame(left, bg=BG3)
        card.pack(fill="x", padx=8, pady=2)

        self.lbl_name      = self._info_row(card, "Name",      "—")
        self.lbl_live      = self._info_row(card, "Status",    "—")
        self.lbl_viewers   = self._info_row(card, "Viewers",   "—")
        self.lbl_category  = self._info_row(card, "Category",  "—")
        self.lbl_duration  = self._info_row(card, "Live For",  "—")
        self.lbl_followers = self._info_row(card, "Followers", "—")
        self.lbl_title     = self._info_row(card, "Title",     "—")

        # Chatroom flags
        tk.Label(left, text="CHATROOM", bg=BG2, fg=GREY,
                 font=("Segoe UI",8,"bold")).pack(anchor="w", padx=12, pady=(10,2))
        flags = tk.Frame(left, bg=BG3)
        flags.pack(fill="x", padx=8, pady=2)
        self.lbl_slow  = self._info_row(flags, "Slow Mode",    "—")
        self.lbl_sub   = self._info_row(flags, "Sub Only",     "—")
        self.lbl_emote = self._info_row(flags, "Emote Only",   "—")

        # Live stats
        tk.Label(left, text="LIVE STATS", bg=BG2, fg=GREY,
                 font=("Segoe UI",8,"bold")).pack(anchor="w", padx=12, pady=(10,2))
        stats = tk.Frame(left, bg=BG3)
        stats.pack(fill="x", padx=8, pady=2)
        self.lbl_elapsed   = self._info_row(stats, "Sampling",   "—")
        self.lbl_msgs      = self._info_row(stats, "Messages",   "0")
        self.lbl_chatters  = self._info_row(stats, "Chatters",   "0")
        self.lbl_mpm       = self._info_row(stats, "Msgs/min",   "0")
        self.lbl_bots      = self._info_row(stats, "Bots",       "0")
        self.lbl_active    = self._info_row(stats, "Active",     "0")
        self.lbl_subs      = self._info_row(stats, "Subs seen",  "0")
        self.lbl_gifts     = self._info_row(stats, "Gifts seen", "0")
        self.lbl_raids     = self._info_row(stats, "Raids seen", "0")

        # Mini activity bar
        tk.Label(left, text="ACTIVITY (last 60s)", bg=BG2, fg=GREY,
                 font=("Segoe UI",8,"bold")).pack(anchor="w", padx=12, pady=(10,2))
        self.mini_canvas = tk.Canvas(left, bg=BG3, height=60, highlightthickness=0)
        self.mini_canvas.pack(fill="x", padx=8, pady=2)

        # Viewbot detector
        tk.Label(left, text="VIEWBOT DETECTOR", bg=BG2, fg=GREY,
                 font=("Segoe UI",8,"bold")).pack(anchor="w", padx=12, pady=(10,2))
        vbot = tk.Frame(left, bg=BG3)
        vbot.pack(fill="x", padx=8, pady=2)
        self.lbl_vbot_score   = self._info_row(vbot, "Risk Score", "—")
        self.lbl_vbot_verdict = self._info_row(vbot, "Verdict",    "—")
        self.lbl_vbot_ratio   = self._info_row(vbot, "Chat Ratio", "—")
        self.lbl_vbot_mpm     = self._info_row(vbot, "Msgs/1k vw", "—")
        self.lbl_vbot_spike   = self._info_row(vbot, "Vw Spike",   "—")

        # Internal viewer history for spike detection
        self._viewer_history  = []   # list of (timestamp, viewer_count)


    def _info_row(self, parent, label, value):
        row = tk.Frame(parent, bg=BG3)
        row.pack(fill="x", padx=8, pady=2)
        tk.Label(row, text=label, bg=BG3, fg=GREY,
                 font=("Segoe UI",9), width=11, anchor="w").pack(side="left")
        var = tk.StringVar(value=value)
        tk.Label(row, textvariable=var, bg=BG3, fg=WHITE,
                 font=("Segoe UI",9,"bold"), anchor="w").pack(side="left")
        return var

    # ── Right panel: tabbed views ─────────────────────────────

    def _build_right(self, parent):
        right = tk.Frame(parent, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.TNotebook",           background=BG,  borderwidth=0)
        style.configure("Dark.TNotebook.Tab",       background=BG2, foreground=GREY,
                        padding=[14,6], font=("Segoe UI",10,"bold"))
        style.map("Dark.TNotebook.Tab",
                  background=[("selected", BG3)],
                  foreground=[("selected", ACCENT)])

        self.nb = ttk.Notebook(right, style="Dark.TNotebook")
        self.nb.pack(fill="both", expand=True)

        self._build_chat_tab()
        self._build_ai_viewbot_tab()
        self._build_events_tab()
        self._build_chatters_tab()
        self._build_words_tab()
        self._build_chart_tab()
        self._build_streamer_info_tab()
        self._build_history_tab()
        self._build_report_tab()
        self._build_guide_tab()

    # ── Tab: Live Chat ────────────────────────────────────────

    def _build_chat_tab(self):
        f = tk.Frame(self.nb, bg=CHATBG)
        self.nb.add(f, text="💬 Live Chat")

        # ── Toolbar row 1: text filter + toggles ──────────────
        toolbar = tk.Frame(f, bg=BG2)
        toolbar.pack(fill="x")
        tk.Label(toolbar, text="Filter:", bg=BG2, fg=GREY,
                 font=("Segoe UI",9)).pack(side="left", padx=8, pady=4)
        self.chat_filter = tk.StringVar()
        self.chat_filter.trace("w", lambda *_: self._apply_chat_filter())
        tk.Entry(toolbar, textvariable=self.chat_filter, width=20,
                 bg=BG3, fg=WHITE, insertbackground=WHITE,
                 font=("Segoe UI",9), relief="flat").pack(side="left", pady=4)
        self.hide_bots_var = tk.BooleanVar(value=False)
        tk.Checkbutton(toolbar, text="Hide bots", variable=self.hide_bots_var,
                       bg=BG2, fg=WHITE, selectcolor=BG3,
                       font=("Segoe UI",9), command=self._apply_chat_filter_now
                       ).pack(side="left", padx=10)
        self.pause_chat_var = tk.BooleanVar(value=False)
        tk.Checkbutton(toolbar, text="Pause scroll", variable=self.pause_chat_var,
                       bg=BG2, fg=WHITE, selectcolor=BG3,
                       font=("Segoe UI",9)).pack(side="left", padx=4)
        tk.Button(toolbar, text="Clear", command=self._clear_chat,
                  bg=BG3, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=8, pady=2).pack(side="right", padx=4, pady=4)
        tk.Button(toolbar, text="▶ Watch Stream", command=self._open_stream,
                  bg=ACCENT, fg="#000", font=("Segoe UI",9,"bold"),
                  relief="flat", padx=10, pady=2, cursor="hand2").pack(side="right", padx=4, pady=4)

        # ── Toolbar row 2: badge/role filters ────────────────
        tb2 = tk.Frame(f, bg=BG3)
        tb2.pack(fill="x")
        tk.Label(tb2, text="  Show:", bg=BG3, fg=GREY,
                 font=("Segoe UI",8,"bold")).pack(side="left", padx=(8,6), pady=3)

        # Badge filter vars — multiple can be ticked simultaneously
        self.chat_badge_filters = {}
        badge_opts = [
            ("All Chatters",     "all",         WHITE),
            ("Subscribers",      "sub",         ACCENT2),
            ("VIP",              "vip",         YELLOW),
            ("Moderators",       "mod",         YELLOW),
            ("Non Subscribers",  "nonfollower", GREY),
        ]
        for label, key, colour in badge_opts:
            var = tk.BooleanVar(value=(key == "all"))
            cb  = tk.Checkbutton(tb2, text=label, variable=var,
                                  bg=BG3, fg=colour, selectcolor=BG2,
                                  activebackground=BG3, activeforeground=colour,
                                  font=("Segoe UI",9),
                                  command=lambda k=key: self._badge_filter_changed(k))
            cb.pack(side="left", padx=6, pady=3)
            self.chat_badge_filters[key] = var

        # Spammer filter + Exclude Emotes option
        self.show_spammers_var = tk.BooleanVar(value=False)
        tk.Checkbutton(tb2, text="🚫 Spammers", variable=self.show_spammers_var,
                       bg=BG3, fg=RED, selectcolor=BG2,
                       activebackground=BG3, activeforeground=RED,
                       font=("Segoe UI",9,"bold"),
                       command=self._apply_chat_filter_now).pack(side="right", padx=(4,10), pady=3)

        self.exclude_emotes_var = tk.BooleanVar(value=False)
        tk.Checkbutton(tb2, text="Exclude Emotes", variable=self.exclude_emotes_var,
                       bg=BG3, fg=GREY, selectcolor=BG2,
                       activebackground=BG3, activeforeground=WHITE,
                       font=("Segoe UI",9),
                       command=self._apply_chat_filter_now).pack(side="right", padx=4, pady=3)

        self.chat_box = scrolledtext.ScrolledText(
            f, bg=CHATBG, fg=WHITE, font=("Consolas",10),
            state="disabled", wrap="word", relief="flat",
            selectbackground=BG3)
        self.chat_box.pack(fill="both", expand=True)

        # Tags for colouring
        self.chat_box.tag_config("time",    foreground=GREY)
        self.chat_box.tag_config("name",    foreground=ACCENT)
        self.chat_box.tag_config("mod",     foreground=YELLOW)
        self.chat_box.tag_config("sub",     foreground=ACCENT2)
        self.chat_box.tag_config("vip",     foreground=YELLOW)
        self.chat_box.tag_config("bot",     foreground=RED)
        self.chat_box.tag_config("msg",     foreground=WHITE)
        self.chat_box.tag_config("colon",   foreground=GREY)

        self._chat_buffer = []   # all messages for filtering


    def _is_spammer(self, username):
        """
        Detect spammers — same message sent 2+ times within 2 seconds.
        If Exclude Emotes is ticked, emote-only messages are ignored.
        """
        import re as _re
        def is_emote_only(text):
            words = text.strip().split()
            return bool(words) and all(_re.search(r'[0-9]', w) for w in words)

        exclude = getattr(self, "exclude_emotes_var", None)
        exclude = exclude and exclude.get()

        user_msgs_timed = [m for m in self.engine.messages
                           if m["username"] == username]
        if len(user_msgs_timed) < 2:
            return False
        recent = user_msgs_timed[-10:]
        for i in range(len(recent)):
            for j in range(i+1, len(recent)):
                if abs(recent[j]["timestamp"] - recent[i]["timestamp"]) <= 2.0:
                    c1 = recent[i]["content"].strip()
                    c2 = recent[j]["content"].strip()
                    if not c1 or not c2:
                        continue
                    if exclude and (is_emote_only(c1) or is_emote_only(c2)):
                        continue
                    if c1 == c2:
                        return True
        return False

    def _append_chat(self, msg):
        self._chat_buffer.append(msg)
        if len(self._chat_buffer) > 2000:
            self._chat_buffer = self._chat_buffer[-2000:]

        filt     = self.chat_filter.get().lower()
        hidebots = self.hide_bots_var.get()

        is_bot = BOT_NAMES.search(msg["username"]) is not None
        if not is_bot:
            msgs_count = len(self.engine.user_msgs.get(msg["username"], []))
            span = (self.engine.user_last.get(msg["username"], 0) -
                    self.engine.user_first.get(msg["username"], 0))
            rate = msgs_count / span if span > 1 else float(msgs_count)
            is_bot = msgs_count >= 5 and rate >= 2.0

        if hidebots and is_bot:
            return
        if filt and filt not in msg["username"].lower()                 and filt not in msg["content"].lower():
            return
        if not self._msg_passes_badge_filter(msg):
            return

        # Spammer filter — only show messages from spammers when ticked
        show_spam = getattr(self, "show_spammers_var", None)
        if show_spam and show_spam.get():
            if not self._is_spammer(msg["username"]):
                return

        badges   = msg.get("badges", [])
        name_tag = ("bot"  if is_bot else
                    "mod"  if "Moderator" in badges else
                    "vip"  if any("VIP" in b or "vip" in b.lower() for b in badges) else
                    "sub"  if any("Sub" in b or "sub" in b for b in badges)
                    else "name")
        self._write_chat_line(msg, is_bot, name_tag)

    def _write_chat_line(self, msg, is_bot=False, name_tag=None):
        cb = self.chat_box
        cb.config(state="normal")
        ts        = datetime.fromtimestamp(msg["timestamp"]).strftime("%H:%M:%S")
        badges    = msg.get("badges", [])
        if name_tag is None:
            name_tag = ("bot" if is_bot else
                        "mod" if "Moderator" in badges else
                        "sub" if any("Sub" in b or "sub" in b for b in badges)
                        else "name")
        badge_str = " ".join(f"[{b}]" for b in badges) + " " if badges else ""
        cb.insert("end", f"[{ts}] ", "time")
        cb.insert("end", badge_str, name_tag)
        cb.insert("end", msg["username"], name_tag)
        cb.insert("end", ": ", "colon")
        cb.insert("end", msg["content"] + "\n", "msg")

        cb.config(state="disabled")
        if not self.pause_chat_var.get():
            cb.see("end")


    def _apply_chat_filter(self):
        """Debounced filter for text input — waits 300ms after typing stops."""
        if hasattr(self, "_filter_after_id") and self._filter_after_id:
            self.root.after_cancel(self._filter_after_id)
        self._filter_after_id = self.root.after(300, self._do_apply_chat_filter)

    def _apply_chat_filter_now(self):
        """Immediate filter for checkbox clicks — clears and redraws instantly."""
        if hasattr(self, "_filter_after_id") and self._filter_after_id:
            self.root.after_cancel(self._filter_after_id)
            self._filter_after_id = None
        self._do_apply_chat_filter()


    def _do_apply_chat_filter(self):
        filt     = self.chat_filter.get().lower()
        hidebots = self.hide_bots_var.get()

        # Work on last 500 messages only
        recent = self._chat_buffer[-500:]

        # Filter in Python first — fast
        filtered = []
        for msg in recent:
            is_bot = BOT_NAMES.search(msg["username"]) is not None
            if not is_bot:
                msgs_list = self.engine.user_msgs.get(msg["username"], [])
                n    = len(msgs_list)
                span = (self.engine.user_last.get(msg["username"],0) -
                        self.engine.user_first.get(msg["username"],0))
                rate = n / span if span > 1 else float(n)
                is_bot = n >= 5 and rate >= 2.0
            if hidebots and is_bot:
                continue
            if filt and filt not in msg["username"].lower() \
                    and filt not in msg["content"].lower():
                continue
            if not self._msg_passes_badge_filter(msg):
                continue
            # Spammer filter
            show_spam = getattr(self, "show_spammers_var", None)
            if show_spam and show_spam.get():
                if not self._is_spammer(msg["username"]):
                    continue
            filtered.append((msg, is_bot))

        cb = self.chat_box
        cb.config(state="normal")
        cb.delete("1.0", "end")

        for msg, is_bot in filtered:
            badges   = msg.get("badges", [])
            name_tag = ("bot"  if is_bot else
                        "mod"  if "Moderator" in badges else
                        "vip"  if any("VIP" in b or "vip" in b.lower() for b in badges) else
                        "sub"  if any("Sub" in b or "sub" in b for b in badges)
                        else "name")
            ts        = datetime.fromtimestamp(msg["timestamp"]).strftime("%H:%M:%S")
            badge_str = " ".join(f"[{b}]" for b in badges) + " " if badges else ""
            cb.insert("end", f"[{ts}] ", "time")
            cb.insert("end", badge_str, name_tag)
            cb.insert("end", msg["username"], name_tag)
            cb.insert("end", ": ", "colon")
            cb.insert("end", msg["content"] + "\n", "msg")

        cb.config(state="disabled")
        if not self.pause_chat_var.get():
            cb.see("end")


    def _badge_filter_changed(self, clicked_key):
        """Handle badge filter checkbox logic — All deselects others, others deselect All."""
        if clicked_key == "all":
            # If All was just ticked, untick everything else
            if self.chat_badge_filters["all"].get():
                for key, var in self.chat_badge_filters.items():
                    if key != "all":
                        var.set(False)
        else:
            # If any specific filter ticked, untick All
            self.chat_badge_filters["all"].set(False)
            # If nothing is ticked at all, re-tick All as fallback
            any_ticked = any(v.get() for k, v in self.chat_badge_filters.items()
                             if k != "all")
            if not any_ticked:
                self.chat_badge_filters["all"].set(True)
        self._apply_chat_filter_now()


    def _msg_passes_badge_filter(self, msg):
        """Return True if message passes the current badge filter selection."""
        # If All is ticked, everything passes
        if self.chat_badge_filters["all"].get():
            return True

        badges_lower = {b.lower() for b in msg.get("badges", [])}

        want_sub    = self.chat_badge_filters["sub"].get()
        want_vip    = self.chat_badge_filters["vip"].get()
        want_mod    = self.chat_badge_filters["mod"].get()
        want_nonfol = self.chat_badge_filters["nonfollower"].get()

        is_sub    = any(b in badges_lower for b in ("subscriber","sub","og","founder"))
        is_vip    = "vip" in badges_lower
        is_mod    = any(b in badges_lower for b in ("moderator","mod"))
        has_badge = bool(badges_lower)   # any badge = some kind of recognised user
        is_nonsub = not is_sub           # Non Subscriber = no sub badge

        if want_sub    and is_sub:    return True
        if want_vip    and is_vip:    return True
        if want_mod    and is_mod:    return True
        if want_nonfol and is_nonsub: return True
        return False


    def _clear_chat(self):
        self.chat_box.config(state="normal")
        self.chat_box.delete("1.0","end")
        self.chat_box.config(state="disabled")


    def _open_stream(self):
        """Open the current streamer's Kick page in the default browser."""
        import webbrowser
        slug = self.slug_var.get().strip().lower()
        if not slug:
            if self.channel:
                slug = self.channel.get("slug","")
        if slug:
            webbrowser.open(f"https://kick.com/{slug}")
        else:
            messagebox.showinfo("No Channel", "Enter a streamer name first.")

    # ── Tab: Events ───────────────────────────────────────────


    # ── Tab: AI Analysis ──────────────────────────────────────
    def _build_ai_viewbot_tab(self):
        f = tk.Frame(self.nb, bg=BG)
        self.nb.add(f, text="🤖 AI Analysis")

        # ── Provider selector row ─────────────────────────────
        prov_bar = tk.Frame(f, bg=BG3)
        prov_bar.pack(fill="x")

        tk.Label(prov_bar, text="  AI Provider:", bg=BG3, fg=WHITE,
                 font=("Segoe UI",9,"bold")).pack(side="left", padx=(8,8), pady=6)

        self.ai_provider_var = tk.StringVar(value="ollama")

        tk.Radiobutton(prov_bar, text="🖥 Ollama (Local — Free)",
                       variable=self.ai_provider_var, value="ollama",
                       bg=BG3, fg=ACCENT, selectcolor=BG2,
                       activebackground=BG3, font=("Segoe UI",9,"bold"),
                       command=self._ai_provider_changed).pack(side="left", padx=6)

        tk.Radiobutton(prov_bar, text="☁ Anthropic API (Claude)",
                       variable=self.ai_provider_var, value="anthropic",
                       bg=BG3, fg=BLUE, selectcolor=BG2,
                       activebackground=BG3, font=("Segoe UI",9,"bold"),
                       command=self._ai_provider_changed).pack(side="left", padx=6)

        # ── Shared container — both provider frames live here ──
        # This keeps them in the same position when switching
        self.ai_provider_container = tk.Frame(f, bg=BG2)
        self.ai_provider_container.pack(fill="x")

        # ── Ollama config row ─────────────────────────────────
        self.ollama_frame = tk.Frame(self.ai_provider_container, bg=BG2)
        self.ollama_frame.pack(fill="x")  # shown by default

        tk.Label(self.ollama_frame, text="  Ollama URL:",
                 bg=BG2, fg=WHITE, font=("Segoe UI",9)).pack(side="left", padx=(8,4), pady=5)
        self.ai_ollama_url_var = tk.StringVar(value="http://127.0.0.1:11434")
        tk.Entry(self.ollama_frame, textvariable=self.ai_ollama_url_var, width=28,
                 bg=BG3, fg=WHITE, insertbackground=WHITE,
                 font=("Segoe UI",9), relief="flat").pack(side="left", pady=5)

        tk.Label(self.ollama_frame, text="  Model:",
                 bg=BG2, fg=WHITE, font=("Segoe UI",9)).pack(side="left", padx=(12,4))
        self.ai_ollama_model_var = tk.StringVar(value="")
        self.ai_model_menu = tk.OptionMenu(self.ollama_frame, self.ai_ollama_model_var, "")
        self.ai_model_menu.config(bg=BG3, fg=WHITE, font=("Segoe UI",9),
                                   relief="flat", highlightthickness=0, width=22)
        self.ai_model_menu.pack(side="left", pady=5)

        tk.Button(self.ollama_frame, text="🔍 Test Connection",
                  command=self._ai_test_ollama,
                  bg=BG3, fg=WHITE, font=("Segoe UI",8),
                  relief="flat", padx=8, pady=2).pack(side="left", padx=8)

        tk.Label(self.ollama_frame,
                 text="Tip: qwen3:8b gives best local analysis results for 8GB GPU",
                 bg=BG2, fg=GREY, font=("Segoe UI",8)).pack(side="left", padx=8)

        # ── Anthropic config row ──────────────────────────────
        self.anthropic_frame = tk.Frame(self.ai_provider_container, bg=BG2)
        # Not packed initially (Ollama is default)

        tk.Label(self.anthropic_frame, text="  Anthropic API Key:",
                 bg=BG2, fg=WHITE, font=("Segoe UI",9)).pack(side="left", padx=(8,4), pady=5)
        self.ai_api_key_var = tk.StringVar()
        key_entry = tk.Entry(self.anthropic_frame, textvariable=self.ai_api_key_var,
                             width=50, bg=BG3, fg=WHITE, insertbackground=WHITE,
                             font=("Segoe UI",9), relief="flat", show="•")
        key_entry.pack(side="left", pady=5)
        tk.Button(self.anthropic_frame, text="👁",
                  command=lambda: key_entry.config(
                      show="" if key_entry.cget("show") == "•" else "•"),
                  bg=BG3, fg=GREY, font=("Segoe UI",8),
                  relief="flat", padx=4, pady=2).pack(side="left", padx=4)

        self.ai_remember_key_var = tk.BooleanVar(value=False)
        tk.Checkbutton(self.anthropic_frame, text="Remember Key",
                       variable=self.ai_remember_key_var,
                       bg=BG2, fg=WHITE, selectcolor=BG3,
                       font=("Segoe UI",9),
                       command=self._ai_save_api_key).pack(side="left", padx=8)

        tk.Label(self.anthropic_frame,
                 text="Key saved to Windows Credential Manager — never written to disk",
                 bg=BG2, fg=GREY, font=("Segoe UI",8)).pack(side="left", padx=4)

        # Load saved key on startup
        self._ai_load_api_key()

        # ── GPU Detection & Model Download strip ──────────────
        gpu_bar = tk.Frame(f, bg=BG3)
        gpu_bar.pack(fill="x")

        tk.Label(gpu_bar, text="  🖥 GPU Setup:", bg=BG3, fg=WHITE,
                 font=("Segoe UI",9,"bold")).pack(side="left", padx=(8,6), pady=5)

        tk.Button(gpu_bar, text="🔍 Detect GPU & Recommend Model",
                  command=self._ai_detect_gpu,
                  bg=BG2, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=10, pady=3,
                  cursor="hand2").pack(side="left", padx=4, pady=4)

        self.ai_download_btn = tk.Button(gpu_bar, text="⬇ Download Recommended Model",
                  command=self._ai_download_model,
                  bg=BG2, fg=GREY, font=("Segoe UI",9),
                  relief="flat", padx=10, pady=3,
                  cursor="hand2", state="disabled")
        self.ai_download_btn.pack(side="left", padx=4, pady=4)

        self.ai_gpu_status_var = tk.StringVar(
            value="Click 'Detect GPU' to find the best model for your hardware")
        tk.Label(gpu_bar, textvariable=self.ai_gpu_status_var,
                 bg=BG3, fg=GREY, font=("Segoe UI",8)).pack(side="left", padx=12)

        # Download progress bar
        self.ai_dl_progress_var = tk.StringVar(value="")
        tk.Label(gpu_bar, textvariable=self.ai_dl_progress_var,
                 bg=BG3, fg=ACCENT, font=("Consolas",9)).pack(side="right", padx=12)

        # Store recommended model for download
        self._ai_recommended_model = None

        # ── Toolbar ───────────────────────────────────────────
        tb = tk.Frame(f, bg=BG2)
        tb.pack(fill="x")

        self.ai_vb_run_btn = tk.Button(tb, text="▶ Run AI Analysis",
                  command=self._ai_viewbot_run,
                  bg=ACCENT, fg="#000", font=("Segoe UI",10,"bold"),
                  relief="flat", padx=14, pady=4, cursor="hand2")
        self.ai_vb_run_btn.pack(side="left", padx=8, pady=6)

        self.ai_vb_stop_btn = tk.Button(tb, text="■ Stop Auto-Run",
                  command=self._ai_viewbot_stop_auto,
                  bg=RED, fg=WHITE, font=("Segoe UI",10,"bold"),
                  relief="flat", padx=14, pady=4, cursor="hand2",
                  state="disabled")
        self.ai_vb_stop_btn.pack(side="left", padx=4)

        self.ai_vb_auto_var = tk.BooleanVar(value=False)
        tk.Checkbutton(tb, text="Auto-run every", variable=self.ai_vb_auto_var,
                       bg=BG2, fg=WHITE, selectcolor=BG3,
                       font=("Segoe UI",9),
                       command=self._ai_viewbot_toggle_auto).pack(side="left", padx=(12,2))
        self.ai_vb_interval_var = tk.StringVar(value="5")
        tk.Entry(tb, textvariable=self.ai_vb_interval_var, width=4,
                 bg=BG3, fg=WHITE, insertbackground=WHITE,
                 font=("Segoe UI",9), relief="flat").pack(side="left")
        tk.Label(tb, text="mins", bg=BG2, fg=GREY,
                 font=("Segoe UI",9)).pack(side="left", padx=(2,12))

        tk.Button(tb, text="💾 Save Analysis", command=self._ai_viewbot_save,
                  bg=BG3, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=10, pady=4).pack(side="left", padx=4)

        tk.Button(tb, text="🗑 Clear", command=self._ai_viewbot_clear,
                  bg=BG3, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=8, pady=4).pack(side="left", padx=4)

        self.ai_vb_status = tk.StringVar(
            value="Start monitoring a stream then click Run AI Analysis")
        tk.Label(tb, textvariable=self.ai_vb_status, bg=BG2, fg=GREY,
                 font=("Segoe UI",9)).pack(side="right", padx=12)

        # ── Info bar ──────────────────────────────────────────
        info = tk.Frame(f, bg=BG3)
        info.pack(fill="x")
        tk.Label(info,
                 text="  Powered by Claude AI  |  Combines viewer curve analysis "
                      "with AI pattern recognition for detailed viewbot detection",
                 bg=BG3, fg=GREY, font=("Segoe UI",8)).pack(side="left", padx=8, pady=3)

        # ── Score strip ───────────────────────────────────────
        score_bar = tk.Frame(f, bg=BG2, height=36)
        score_bar.pack(fill="x")
        score_bar.pack_propagate(False)
        tk.Label(score_bar, text="Numeric Score:", bg=BG2, fg=GREY,
                 font=("Segoe UI",9)).pack(side="left", padx=(12,4), pady=6)
        self.ai_score_var = tk.StringVar(value="—")
        tk.Label(score_bar, textvariable=self.ai_score_var,
                 bg=BG2, fg=ACCENT, font=("Segoe UI",11,"bold")).pack(side="left")
        tk.Label(score_bar, text="   Verdict:", bg=BG2, fg=GREY,
                 font=("Segoe UI",9)).pack(side="left", padx=(16,4))
        self.ai_verdict_var = tk.StringVar(value="—")
        tk.Label(score_bar, textvariable=self.ai_verdict_var,
                 bg=BG2, fg=WHITE, font=("Segoe UI",11,"bold")).pack(side="left")
        tk.Label(score_bar, text="   Last run:", bg=BG2, fg=GREY,
                 font=("Segoe UI",9)).pack(side="left", padx=(16,4))
        self.ai_lastrun_var = tk.StringVar(value="Never")
        tk.Label(score_bar, textvariable=self.ai_lastrun_var,
                 bg=BG2, fg=GREY, font=("Segoe UI",9)).pack(side="left")

        # ── Main analysis output ──────────────────────────────
        self.ai_vb_box = scrolledtext.ScrolledText(
            f, bg=BG2, fg=WHITE, font=("Consolas",10),
            state="disabled", wrap="word", relief="flat")
        self.ai_vb_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.ai_vb_box.tag_config("heading",  foreground=ACCENT,  font=("Consolas",11,"bold"))
        self.ai_vb_box.tag_config("verdict",  foreground=YELLOW,  font=("Consolas",12,"bold"))
        self.ai_vb_box.tag_config("high",     foreground=RED,     font=("Consolas",11,"bold"))
        self.ai_vb_box.tag_config("medium",   foreground=YELLOW,  font=("Consolas",10))
        self.ai_vb_box.tag_config("low",      foreground=ACCENT,  font=("Consolas",10))
        self.ai_vb_box.tag_config("clean",    foreground=ACCENT,  font=("Consolas",11,"bold"))
        self.ai_vb_box.tag_config("label",    foreground=GREY,    font=("Consolas",10))
        self.ai_vb_box.tag_config("body",     foreground=WHITE,   font=("Consolas",10))
        self.ai_vb_box.tag_config("divider",  foreground=BG3,     font=("Consolas",10))

        # Internal state
        self._ai_vb_auto_id   = None
        self._ai_vb_running   = False

        # Settings file path — saved next to kick_report.py
        self._ai_settings_path = os.path.join(
            APP_DIR, "ai_settings.json")

        # Restore saved settings on launch
        self._ai_load_settings()

    def _ai_save_api_key(self):
        """Save or delete API key in Windows Credential Manager via keyring."""
        try:
            import keyring
        except ImportError:
            # Auto-install keyring if missing
            import subprocess, sys
            subprocess.run([sys.executable, "-m", "pip", "install",
                            "keyring", "-q", "--target",
                            os.path.join(APP_DIR, "packages")],
                           capture_output=True)
            try:
                import keyring
            except ImportError:
                self.ai_vb_status.set(
                    "⚠ Could not install keyring — key not saved.")
                return

        SERVICE = "KickAnalytics"
        USERNAME = "anthropic_api_key"
        if self.ai_remember_key_var.get():
            key = self.ai_api_key_var.get().strip()
            if key:
                keyring.set_password(SERVICE, USERNAME, key)
                self.ai_vb_status.set("✓ API key saved to Windows Credential Manager")
            else:
                self.ai_vb_status.set("⚠ Enter a key first before saving")
                self.ai_remember_key_var.set(False)
        else:
            # Unticked — delete saved key
            try:
                keyring.delete_password(SERVICE, USERNAME)
                self.ai_vb_status.set("✓ Saved API key removed from Credential Manager")
            except Exception:
                pass

    def _ai_load_api_key(self):
        """Load API key from Windows Credential Manager on startup."""
        try:
            import keyring
            SERVICE  = "KickAnalytics"
            USERNAME = "anthropic_api_key"
            key = keyring.get_password(SERVICE, USERNAME)
            if key:
                self.ai_api_key_var.set(key)
                self.ai_remember_key_var.set(True)
        except Exception:
            pass  # keyring not installed yet — will install on first save

    def _ai_save_settings(self, models=None, extra=None):
        """Save Ollama URL, model list, selected model and GPU info to ai_settings.json."""
        try:
            existing = {}
            if os.path.exists(self._ai_settings_path):
                with open(self._ai_settings_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            existing.update({
                "ollama_url":     self.ai_ollama_url_var.get(),
                "selected_model": self.ai_ollama_model_var.get(),
                "provider":       self.ai_provider_var.get(),
            })
            if models is not None:
                existing["model_list"] = models
            if extra:
                existing.update(extra)
            with open(self._ai_settings_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)
        except Exception:
            pass

    def _ai_load_settings(self):
        """Restore saved Ollama settings and repopulate model dropdown."""
        try:
            if not os.path.exists(self._ai_settings_path):
                return
            with open(self._ai_settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Restore URL and provider
            if data.get("ollama_url"):
                self.ai_ollama_url_var.set(data["ollama_url"])
            if data.get("provider"):
                self.ai_provider_var.set(data["provider"])
                self._ai_provider_changed()

            # Restore model list into dropdown
            models = data.get("model_list", [])
            if models:
                menu = self.ai_model_menu["menu"]
                menu.delete(0, "end")
                for m in models:
                    menu.add_command(
                        label=m,
                        command=lambda v=m: (
                            self.ai_ollama_model_var.set(v),
                            self._ai_save_settings()
                        ))
                # Restore selected model
                selected = data.get("selected_model", models[0])
                if selected in models:
                    self.ai_ollama_model_var.set(selected)
                else:
                    self.ai_ollama_model_var.set(models[0])
                self.ai_vb_status.set(
                    f"✓ Restored {len(models)} models from last session — "
                    f"selected: {self.ai_ollama_model_var.get()}")

            # Restore GPU detection results — check app cache first (instant)
            gpu_data = getattr(self.app, '_cached_gpu', {})
            if not gpu_data:
                gpu_data = {
                    "gpu_name":  data.get("gpu_name", ""),
                    "gpu_vram":  data.get("gpu_vram", 0),
                    "gpu_tier":  data.get("gpu_tier", ""),
                    "gpu_model": data.get("gpu_model", ""),
                }
            gpu_name  = gpu_data.get("gpu_name", "")
            gpu_vram  = gpu_data.get("gpu_vram", 0)
            gpu_tier  = gpu_data.get("gpu_tier", "")
            gpu_model = gpu_data.get("gpu_model", "")
            if gpu_name and gpu_vram:
                status = (f"GPU: {gpu_name}  |  VRAM: {gpu_vram}GB  |  "
                          f"Tier: {gpu_tier}  |  Recommended: {gpu_model}"
                          f"  |  (cached — click Detect to refresh)")
                self.ai_gpu_status_var.set(status)
                self._ai_recommended_model = gpu_model
                if gpu_model:
                    self.ai_download_btn.config(
                        text=f"⬇ Download {gpu_model}",
                        state="normal", fg=WHITE)
        except Exception:
            pass

    def _build_viewer_curve_summary(self):
        """
        Option 3: Analyse the shape of the viewer count curve.
        Returns a dict with curve metrics and a human-readable description.
        """
        history = self._viewer_history
        if len(history) < 3:
            return {"description": "Insufficient data (need 3+ data points)",
                    "points": len(history), "curve_score": 0}

        times   = [t for t, v in history]
        viewers = [v for t, v in history]
        n       = len(viewers)

        # Max spike in any 3-min window
        max_spike_pct = 0
        max_drop_pct  = 0
        for i in range(n):
            for j in range(i+1, n):
                if times[j] - times[i] <= 180 and viewers[i] > 50:
                    chg = (viewers[j] - viewers[i]) / viewers[i] * 100
                    if chg > max_spike_pct: max_spike_pct = chg
                    if chg < max_drop_pct:  max_drop_pct  = chg

        # Flatness — how little variance is there (bots hold steady)
        avg_v   = sum(viewers) / n
        variance= sum((v - avg_v)**2 for v in viewers) / n
        std_dev  = variance ** 0.5
        flatness = std_dev / avg_v * 100 if avg_v else 0

        # Velocity changes — sudden vs gradual
        deltas = []
        for i in range(1, n):
            dt = max(times[i] - times[i-1], 1)
            deltas.append((viewers[i] - viewers[i-1]) / dt)
        max_velocity = max(abs(d) for d in deltas) if deltas else 0

        # Trend — growing, declining, flat, erratic
        if n >= 4:
            first_half  = sum(viewers[:n//2]) / (n//2)
            second_half = sum(viewers[n//2:]) / (n - n//2)
            trend_pct   = (second_half - first_half) / first_half * 100 if first_half else 0
        else:
            trend_pct = 0

        # Curve score — higher = more suspicious shape
        curve_score = 0
        if max_spike_pct >= 200:  curve_score += 40
        elif max_spike_pct >= 100: curve_score += 28
        elif max_spike_pct >= 50:  curve_score += 14
        if abs(max_drop_pct) >= 100: curve_score += 20
        elif abs(max_drop_pct) >= 50: curve_score += 10
        if flatness < 5 and avg_v > 500: curve_score += 15  # unnaturally flat
        curve_score = min(curve_score, 100)

        # Build time-series string for Claude
        series_str = "  ".join(
            f"{int((times[i]-times[0])//60)}m={viewers[i]}"
            for i in range(min(n, 20))
        )

        return {
            "points":        n,
            "duration_mins": int((times[-1] - times[0]) / 60),
            "min_viewers":   min(viewers),
            "max_viewers":   max(viewers),
            "avg_viewers":   int(avg_v),
            "max_spike_pct": round(max_spike_pct, 1),
            "max_drop_pct":  round(max_drop_pct, 1),
            "flatness_pct":  round(flatness, 1),
            "max_velocity":  round(max_velocity, 1),
            "trend_pct":     round(trend_pct, 1),
            "curve_score":   curve_score,
            "series":        series_str,
            "description":   (
                f"{n} data points over {int((times[-1]-times[0])/60)} mins. "
                f"Range: {min(viewers):,}–{max(viewers):,} viewers. "
                f"Max spike: +{max_spike_pct:.0f}%. "
                f"Max drop: {max_drop_pct:.0f}%. "
                f"Flatness: {flatness:.1f}%. "
                f"Trend: {trend_pct:+.1f}%."
            )
        }

    def _ai_provider_changed(self):
        """Show/hide the correct config row — both inside the shared container."""
        if self.ai_provider_var.get() == "ollama":
            self.anthropic_frame.pack_forget()
            self.ollama_frame.pack(fill="x")
        else:
            self.ollama_frame.pack_forget()
            self.anthropic_frame.pack(fill="x")
        self._ai_save_settings()

    def _ai_detect_gpu(self):
        """Detect GPU VRAM and recommend the best Ollama model."""
        self.ai_gpu_status_var.set("Detecting GPU...")
        self.ai_download_btn.config(state="disabled")
        threading.Thread(target=self._ai_detect_gpu_thread, daemon=True).start()

    def _ai_detect_gpu_thread(self):
        """GPU detection using nvidia-smi with CREATE_NO_WINDOW to prevent hanging."""
        import subprocess, os
        vram_gb  = 0
        gpu_name = "No GPU detected"

        # Use CREATE_NO_WINDOW so subprocess never opens a console or hangs
        NO_WINDOW = subprocess.CREATE_NO_WINDOW

        # Method 1: nvidia-smi — works on your machine, accurate VRAM
        try:
            result = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=name,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True,
                timeout=8, creationflags=NO_WINDOW)
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    if "," in line:
                        parts    = line.split(",")
                        gpu_name = parts[0].strip()
                        vram_mb  = int(parts[1].strip())
                        vram_gb  = round(vram_mb / 1024, 1)
                        break
        except Exception as e:
            pass

        # Method 2: GPUtil fallback
        if vram_gb == 0:
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu      = max(gpus, key=lambda g: g.memoryTotal)
                    vram_gb  = round(gpu.memoryTotal / 1024, 1)
                    gpu_name = gpu.name
            except Exception:
                pass

        # Method 3: wmic fallback — last resort
        if vram_gb == 0:
            try:
                result = subprocess.run(
                    ["wmic", "path", "win32_VideoController",
                     "get", "AdapterRAM,Name", "/format:csv"],
                    capture_output=True, text=True,
                    timeout=5, creationflags=NO_WINDOW)
                best = 0
                for line in result.stdout.strip().split("\n"):
                    line = line.strip()
                    if not line or "," not in line or "Node" in line:
                        continue
                    parts = line.split(",")
                    if len(parts) >= 3:
                        try:
                            ram  = int(parts[1])
                            name = parts[2]
                            if ram > best and "Microsoft" not in name:
                                best     = ram
                                gpu_name = name
                        except: pass
                if best > 0:
                    vram_gb = round(best / (1024**3), 1)
            except Exception:
                pass

        # ── Recommend model based on VRAM ─────────────────────
        if vram_gb >= 20:
            tier  = "12-24GB GPU"; model = "qwen3:32b"
            reason = f"Your {vram_gb}GB VRAM can run 32B models"
        elif vram_gb >= 10:
            tier  = "12GB GPU";    model = "qwen3:14b"
            reason = f"Your {vram_gb}GB VRAM is ideal for 14B models"
        elif vram_gb >= 7:
            tier  = "8GB GPU";     model = "qwen3:8b"
            reason = f"Your {vram_gb}GB VRAM runs 8B models with GPU acceleration"
        elif vram_gb >= 5:
            tier  = "6GB GPU";     model = "mistral:7b"
            reason = f"Your {vram_gb}GB VRAM can handle 7B models"
        elif vram_gb >= 3:
            tier  = "4GB GPU";     model = "qwen3:4b"
            reason = f"Your {vram_gb}GB VRAM is best suited for 4B models"
        elif vram_gb > 0:
            tier  = "Low VRAM GPU"; model = "llama3.2:3b"
            reason = f"Your {vram_gb}GB VRAM can run small 3B models"
        else:
            tier  = "CPU only";    model = "phi3:mini"
            reason = "No compatible GPU found — phi3:mini is optimised for CPU"

        self._ai_recommended_model = model

        # Check if model already installed in Ollama
        already_installed = False
        try:
            import urllib.request as _ur, json as _json, ssl as _ssl
            url = self.ai_ollama_url_var.get().strip().rstrip("/")
            req = _ur.Request(f"{url}/api/tags",
                              headers={"Accept": "application/json"})
            ctx = _ssl.create_default_context()
            with _ur.urlopen(req, context=ctx, timeout=5) as resp:
                data = _json.loads(resp.read().decode())
            installed = [m["name"] for m in data.get("models", [])]
            already_installed = any(model in m for m in installed)
        except: pass

        def update_ui(model=model, gpu_name=gpu_name, vram_gb=vram_gb,
                      tier=tier, reason=reason,
                      already_installed=already_installed):
            status = (f"GPU: {gpu_name}  |  VRAM: {vram_gb}GB  |  "
                      f"Tier: {tier}  |  Recommended: {model}")
            self.ai_gpu_status_var.set(status)
            if already_installed:
                self.ai_download_btn.config(
                    text=f"✓ {model} already installed",
                    state="disabled", fg=ACCENT)
                self.ai_ollama_model_var.set(model)
                self._ai_save_settings()
                self.ai_vb_status.set(
                    f"✓ {model} already installed and selected — ready to use!")
            else:
                self.ai_download_btn.config(
                    text=f"⬇ Download {model}",
                    state="normal", fg=WHITE)
                self.ai_vb_status.set(
                    f"Recommended: {model}  |  {reason}  |  "
                    f"Click Download to install")

        self.root.after(0, update_ui)

        # Save to file and also store on app object so new tabs get it instantly
        try:
            extra = {
                "gpu_name":  gpu_name,
                "gpu_vram":  vram_gb,
                "gpu_tier":  tier,
                "gpu_model": model,
            }
            self._ai_save_settings(extra=extra)
            # Store on the app so new session tabs can read it without re-detecting
            self.app._cached_gpu = extra
        except: pass

    def _ai_download_model(self):
        """Download the recommended model via Ollama pull API."""
        model = self._ai_recommended_model
        if not model:
            return
        self.ai_download_btn.config(state="disabled",
                                     text=f"⬇ Downloading {model}...")
        self.ai_gpu_status_var.set(f"Downloading {model} — this may take several minutes...")
        threading.Thread(target=self._ai_download_thread,
                         args=(model,), daemon=True).start()

    def _ai_download_thread(self, model):
        """Stream the Ollama pull progress."""
        import urllib.request as _ur, json as _json, ssl as _ssl
        url = self.ai_ollama_url_var.get().strip().rstrip("/")
        try:
            payload = _json.dumps({"name": model, "stream": True}).encode()
            req = _ur.Request(f"{url}/api/pull", data=payload,
                              headers={"content-type": "application/json"},
                              method="POST")
            ctx = _ssl.create_default_context()
            with _ur.urlopen(req, context=ctx, timeout=600) as resp:
                while True:
                    line = resp.readline()
                    if not line: break
                    try:
                        chunk = _json.loads(line.decode("utf-8"))
                        status   = chunk.get("status","")
                        total    = chunk.get("total", 0)
                        completed= chunk.get("completed", 0)

                        if total and completed:
                            pct  = int(completed / total * 100)
                            done = round(completed / (1024**3), 2)
                            tot  = round(total / (1024**3), 2)
                            prog = f"{'█' * (pct//5)}{'░' * (20 - pct//5)} {pct}%  {done}/{tot}GB"
                            self.root.after(0, lambda p=prog:
                                self.ai_dl_progress_var.set(p))
                        elif status:
                            self.root.after(0, lambda s=status:
                                self.ai_gpu_status_var.set(f"Pulling {model}: {s}"))
                    except: pass

            # Download complete
            def on_done(model=model):
                self.ai_dl_progress_var.set("✓ Download complete!")
                self.ai_download_btn.config(
                    text=f"✓ {model} installed", state="disabled", fg=ACCENT)
                self.ai_gpu_status_var.set(
                    f"✓ {model} downloaded successfully — running Test Connection to load it")
                self.ai_ollama_model_var.set(model)
                self._ai_save_settings()
                # Refresh model list
                self._ai_test_ollama()
            self.root.after(0, on_done)

        except Exception as e:
            err = str(e)
            def on_err(err=err, model=model):
                self.ai_dl_progress_var.set("")
                self.ai_download_btn.config(
                    text=f"⬇ Download {model}", state="normal", fg=WHITE)
                self.ai_gpu_status_var.set(
                    f"Download failed: {err}  |  Is Ollama running?")
            self.root.after(0, on_err)

    def _ai_test_ollama(self):
        """Test Ollama connection and populate model dropdown with installed models."""
        import urllib.request as _ur, json as _json, ssl as _ssl
        url = self.ai_ollama_url_var.get().strip().rstrip("/")
        self.ai_vb_status.set("Testing Ollama connection...")
        def test():
            try:
                req = _ur.Request(f"{url}/api/tags",
                                  headers={"Accept": "application/json"})
                ctx = _ssl.create_default_context()
                with _ur.urlopen(req, context=ctx, timeout=5) as resp:
                    data = _json.loads(resp.read().decode())
                models = [m["name"] for m in data.get("models", [])]
                if models:
                    def update_menu(models=models):
                        menu = self.ai_model_menu["menu"]
                        menu.delete(0, "end")
                        for m in models:
                            menu.add_command(
                                label=m,
                                command=lambda v=m: (
                                    self.ai_ollama_model_var.set(v),
                                    self._ai_save_settings()
                                ))
                        # Keep current selection if it exists in new list
                        current = self.ai_ollama_model_var.get()
                        if current not in models:
                            self.ai_ollama_model_var.set(models[0])
                        # Save everything
                        self._ai_save_settings(models=models)
                        self.ai_vb_status.set(
                            f"✓ Connected  |  {len(models)} models loaded — "
                            f"selected: {self.ai_ollama_model_var.get()}")
                    self.root.after(0, update_menu)
                else:
                    self.root.after(0, lambda: self.ai_vb_status.set(
                        "✓ Ollama connected but no models installed. "
                        "Run: ollama pull llama3.1"))
            except Exception as e:
                def show_ollama_help(e=str(e)):
                    self.ai_vb_status.set(
                        f"✗ Cannot reach Ollama at {url}  ({e})")
                    # Show install help in the analysis box
                    self._ai_vb_write("", clear=True)
                    cb = self.ai_vb_box
                    cb.config(state="normal")
                    cb.insert("end", "OLLAMA NOT FOUND\n", "heading")
                    cb.insert("end", "="*64 + "\n\n", "heading")
                    cb.insert("end",
                        "Ollama is a free app that runs AI models locally on your machine.\n"
                        "It is required for the local AI Analysis feature.\n\n", "body")
                    cb.insert("end", "HOW TO INSTALL OLLAMA:\n\n", "heading")
                    cb.insert("end",
                        "  1. Go to  https://ollama.com\n"
                        "  2. Click Download for Windows\n"
                        "  3. Run the installer (no admin required)\n"
                        "  4. Ollama starts automatically in the system tray\n"
                        "  5. Open a Command Prompt and run:\n\n", "body")
                    cb.insert("end",
                        "        ollama pull qwen3:8b\n\n", "verdict")
                    cb.insert("end",
                        "  6. Come back here and click  Test Connection\n\n", "body")
                    cb.insert("end", "ALTERNATIVE — NO INSTALL NEEDED:\n\n", "heading")
                    cb.insert("end",
                        "  Switch to  ☁ Anthropic API  at the top of this tab.\n"
                        "  Get a free API key at  https://console.anthropic.com\n"
                        "  Paste it in the API Key field and run analysis instantly.\n\n",
                        "body")
                    cb.insert("end", "="*64 + "\n", "heading")
                    cb.config(state="disabled")
                self.root.after(0, show_ollama_help)
        threading.Thread(target=test, daemon=True).start()

    def _ai_viewbot_run(self):
        """Trigger an AI analysis run."""
        if self._ai_vb_running:
            return
        if not self.channel or not self.engine.start_time:
            self.ai_vb_status.set("⚠ Start monitoring a stream first.")
            return
        self._ai_vb_running = True
        self.ai_vb_run_btn.config(state="disabled")
        provider = self.ai_provider_var.get()
        self.ai_vb_status.set(
            f"🤖 Running AI analysis via {'Ollama (local)' if provider == 'ollama' else 'Anthropic API'}...")
        self._ai_vb_write("", clear=True)
        threading.Thread(target=self._ai_viewbot_fetch, daemon=True).start()

    def _ai_viewbot_fetch(self):
        """Build prompt and call Claude API in background thread."""
        import json as _json, urllib.request as _ur, ssl as _ssl

        ch       = self.channel or {}
        elapsed  = time.time() - (self.engine.start_time or time.time())
        viewers  = ch.get("viewer_count", 0)
        chatters = len(self.engine.user_msgs)
        total_msgs = len(self.engine.messages)
        mpm      = total_msgs / (elapsed / 60) if elapsed > 60 else 0
        chat_ratio = (chatters / viewers * 100) if viewers else 0
        mpm_per_1k = (mpm / viewers * 1000) if viewers else 0

        # Numeric score from existing detector
        num_score, num_verdict, breakdown = self._calc_viewbot_score()

        # Curve analysis (Option 3)
        curve = self._build_viewer_curve_summary()

        # Bot counts
        bot_count = sum(1 for u in self.engine.user_msgs if BOT_NAMES.search(u))
        bot_ratio = (bot_count / chatters * 100) if chatters else 0

        # Subs, gifts, raids
        subs  = sum(1 for e in self.engine.events if e["kind"] == "subscription")
        gifts = sum(1 for e in self.engine.events if e["kind"] == "gift")
        raids = sum(1 for e in self.engine.events if e["kind"] == "raid")

        # Top chatters count vs viewer ratio
        active = sum(1 for msgs in self.engine.user_msgs.values() if len(msgs) >= 5)

        prompt = f"""You are an expert analyst specialising in detecting viewbot fraud on live streaming platforms.
Analyse the following real-time data from a Kick.com stream and provide a detailed viewbot detection report.

=== STREAM INFORMATION ===
Channel: {ch.get("display_name","?")} (kick.com/{ch.get("slug","?")})
Category: {ch.get("category","N/A")}
Stream duration monitored: {int(elapsed//60)} minutes {int(elapsed%60)} seconds
Verified channel: {ch.get("verified", False)}

=== CURRENT METRICS ===
Current viewer count: {viewers:,}
Total unique chatters: {chatters:,}
Chat/Viewer ratio: {chat_ratio:.2f}% (healthy streams: 3-8%)
Total messages captured: {total_msgs:,}
Messages per minute: {mpm:.1f}
Messages per minute per 1,000 viewers: {mpm_per_1k:.2f} (healthy: 10-50)
Active chatters (5+ messages): {active:,}
Known bots detected: {bot_count:,} ({bot_ratio:.1f}% of chatters)
Subscriptions seen: {subs}
Gift subs seen: {gifts}
Raids seen: {raids}

=== VIEWER COUNT CURVE ANALYSIS ===
{curve["description"]}
Time series (minute=viewers): {curve["series"]}
Max spike in 3-min window: +{curve["max_spike_pct"]}%
Max drop in 3-min window: {curve["max_drop_pct"]}%
Viewer curve flatness: {curve["flatness_pct"]}% std deviation (unnaturally flat if <5%)
Overall trend: {curve["trend_pct"]:+.1f}%
Curve suspicion score: {curve["curve_score"]}/100

=== NUMERICAL DETECTOR SCORE ===
Combined score: {num_score}/100
Verdict: {num_verdict}
Signal breakdown: {_json.dumps({k: v[0] for k, v in breakdown.items() if isinstance(v, tuple)}, indent=2)}

=== YOUR TASK ===
Provide a DETAILED viewbot detection report with the following sections:

1. EXECUTIVE SUMMARY
   One paragraph overall assessment.

2. SIGNAL ANALYSIS
   Analyse each signal individually:
   - Viewer count curve shape (natural growth vs artificial spikes)
   - Chat-to-viewer ratio assessment
   - Message rate analysis
   - Bot presence in chat
   - Event activity (subs/gifts/raids vs viewer count)

3. SUSPICIOUS PATTERNS IDENTIFIED
   List specific patterns that indicate viewbotting, if any. 
   Be specific about what numbers triggered concern.

4. LEGITIMATE EXPLANATIONS
   List any alternative explanations that could explain the data 
   (raids, viral moments, category switch etc).

5. CONFIDENCE ASSESSMENT
   How confident are you in your assessment and why?

6. FINAL VERDICT
   One of: CLEAN / LOW RISK / SUSPICIOUS / HIGH RISK / CONFIRMED BOTTING
   With a score 0-100 and brief justification.

Be direct, specific and reference the actual numbers in your analysis.
Keep each section concise — 2-4 sentences per signal is enough.
Complete ALL 6 sections. Do not stop early."""

        try:
            provider = self.ai_provider_var.get()
            text     = ""

            if provider == "ollama":
                # ── Ollama local model ─────────────────────────
                url   = self.ai_ollama_url_var.get().strip().rstrip("/")
                model = self.ai_ollama_model_var.get().strip()
                if not model:
                    self.root.after(0, lambda: self._ai_viewbot_display(
                        "No model selected.\n\nClick 'Test Connection' first to "
                        "load your installed models, then select one from the dropdown.",
                        0, "Error"))
                    return

                self.root.after(0, lambda: self.ai_vb_status.set(
                    f"🤖 Sending to {model} — this may take 30-90 seconds..."))

                payload = _json.dumps({
                    "model":  model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 3000, "temperature": 0.3}
                }).encode("utf-8")

                req = _ur.Request(
                    f"{url}/api/generate",
                    data=payload,
                    headers={"content-type": "application/json"},
                    method="POST"
                )
                ctx = _ssl.create_default_context()
                with _ur.urlopen(req, context=ctx, timeout=180) as resp:
                    result = _json.loads(resp.read().decode("utf-8"))
                text = result.get("response", "No response from Ollama.")

            else:
                # ── Anthropic API ──────────────────────────────
                api_key = self.ai_api_key_var.get().strip()
                if not api_key:
                    self.root.after(0, lambda: self._ai_viewbot_display(
                        "No Anthropic API key provided.\n\n"
                        "Enter your key in the field above, or switch to "
                        "Ollama (Local — Free) which requires no key.",
                        0, "Error"))
                    return

                payload = _json.dumps({
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 3000,
                    "messages": [{"role": "user", "content": prompt}]
                }).encode("utf-8")

                req = _ur.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=payload,
                    headers={
                        "content-type":      "application/json",
                        "anthropic-version": "2023-06-01",
                        "x-api-key":         api_key,
                    },
                    method="POST"
                )
                ctx = _ssl.create_default_context()
                with _ur.urlopen(req, context=ctx, timeout=120) as resp:
                    result = _json.loads(resp.read().decode("utf-8"))
                for block in result.get("content", []):
                    if block.get("type") == "text":
                        text += block.get("text", "")

            if not text:
                text = "No response received from AI model."

            # Parse AI verdict and score from the response text
            import re as _re
            ai_verdict = num_verdict  # fallback to numeric
            ai_score   = num_score

            # Look for verdict line in AI response
            verdict_map = {
                "CONFIRMED BOTTING": ("🔴 CONFIRMED BOTTING", 95),
                "HIGH RISK":         ("🔴 HIGH RISK",         80),
                "SUSPICIOUS":        ("🟡 SUSPICIOUS",        55),
                "LOW RISK":          ("🟢 LOW RISK",          25),
                "CLEAN":             ("✅ CLEAN",              5),
            }
            for line in text.split("\n"):
                upper = line.upper()
                for key, (label, default_score) in verdict_map.items():
                    if key in upper and ("VERDICT" in upper or "FINAL" in upper
                                        or "RISK" in upper or "CLEAN" in upper
                                        or "BOTTING" in upper):
                        ai_verdict = label
                        # Try to extract numeric score from same line
                        nums = _re.findall(r'\b(\d{1,3})\s*/\s*100\b', line)
                        if nums:
                            ai_score = int(nums[0])
                        else:
                            ai_score = default_score
                        break
                if ai_verdict != num_verdict:
                    break

            self.root.after(0, lambda t=text, s=ai_score, v=ai_verdict:
                self._ai_viewbot_display(t, s, v))

        except Exception as e:
            err = str(e)
            provider = self.ai_provider_var.get()
            if provider == "ollama":
                hint = ("Could not reach Ollama.\n\n"
                        "Make sure Ollama is installed and running:\n"
                        "1. Download from ollama.com\n"
                        "2. Run: ollama serve\n"
                        "3. Run: ollama pull qwen3:8b\n"
                        "4. Click 'Test Connection' to verify\n\n"
                        "Error: " + err)
            else:
                if "529" in err:
                    hint = ("Anthropic API Overloaded (Error 529)\n\n"
                            "Anthropic's servers are temporarily at capacity.\n"
                            "This is not an error with your API key or this app.\n\n"
                            "What to do:\n"
                            "  1. Wait 1-2 minutes and try again\n"
                            "  2. Try during off-peak hours\n"
                            "  3. Switch to Ollama (Local) as a free alternative\n\n"
                            "Error: " + err)
                elif "401" in err:
                    hint = ("Anthropic API — Invalid API Key (Error 401)\n\n"
                            "Your API key was rejected by Anthropic.\n\n"
                            "What to do:\n"
                            "  1. Check your key at console.anthropic.com\n"
                            "  2. Make sure you copied the full key (starts with sk-ant-)\n"
                            "  3. Create a new key if this one has been revoked\n\n"
                            "Error: " + err)
                elif "400" in err:
                    hint = ("Anthropic API — Bad Request (Error 400)\n\n"
                            "The request was rejected. The model name may have changed.\n"
                            "Please check for an updated version of this app.\n\n"
                            "Error: " + err)
                else:
                    hint = "Anthropic API error: " + err
            self.root.after(0, lambda h=hint: self._ai_viewbot_display(h, 0, "Error"))

    def _ai_viewbot_display(self, text, score, verdict):
        """Render the AI analysis in the tab."""
        self._ai_vb_running = False
        self.ai_vb_run_btn.config(state="normal")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.ai_lastrun_var.set(ts)
        self.ai_score_var.set(str(score) + "/100")
        self.ai_verdict_var.set(verdict)

        # Update the side panel viewbot detector with AI verdict
        # Lock it so the numeric detector doesn't overwrite it
        if verdict and verdict not in ("—", "Error", "Warming up..."):
            try:
                self._ai_verdict_locked = True
                self.lbl_vbot_score.set(f"{score}/100  (AI)")
                self.lbl_vbot_verdict.set(f"{verdict}  ← AI Analysis")
            except Exception:
                pass

        cb = self.ai_vb_box
        cb.config(state="normal")
        cb.delete("1.0", "end")

        div = "=" * 64
        ch_name = self.channel.get("display_name","?") if self.channel else "?"
        ch_slug = self.channel.get("slug","?") if self.channel else "?"
        header = (div + "\n"
                  "  AI VIEWBOT ANALYSIS REPORT\n"
                  "  Channel : " + ch_name + " (kick.com/" + ch_slug + ")\n"
                  "  Generated: " + ts + "\n" +
                  div + "\n\n")
        cb.insert("end", header, "heading")

        import re as _re
        for line in text.split("\n"):
            stripped = line.strip()
            if _re.match(r"^\d+\.\s+[A-Z]", stripped) or                (stripped.upper() == stripped and len(stripped) > 3 and stripped.isalpha()):
                cb.insert("end", line + "\n", "heading")
            elif any(v in line.upper() for v in
                     ["CLEAN","LOW RISK","SUSPICIOUS","HIGH RISK","CONFIRMED BOTTING",
                      "FINAL VERDICT","VERDICT:"]):
                tag = ("high"   if any(x in line.upper() for x in ["HIGH","CONFIRMED"]) else
                       "medium" if "SUSPICIOUS" in line.upper() else
                       "low"    if "LOW" in line.upper() else
                       "clean"  if "CLEAN" in line.upper() else "verdict")
                cb.insert("end", line + "\n", tag)
            else:
                cb.insert("end", line + "\n", "body")

        cb.insert("end", "\n" + div + "\n", "heading")
        cb.config(state="disabled")
        cb.see("end")

        self.ai_vb_status.set("Analysis complete  " + ts)

        if self.ai_vb_auto_var.get() and self._ai_vb_auto_id is not None:
            try:
                mins = max(1, int(self.ai_vb_interval_var.get()))
            except Exception:
                mins = 5
            self._ai_vb_auto_id = self.root.after(
                mins * 60000, self._ai_viewbot_run)

    def _ai_viewbot_toggle_auto(self):
        if self.ai_vb_auto_var.get():
            self.ai_vb_stop_btn.config(state="normal")
            self._ai_vb_auto_id = 0   # mark as enabled
            # Only run immediately if countdown is already done
            if self._countdown_secs <= 0:
                self._ai_viewbot_run()
            else:
                self.ai_vb_status.set(
                    f"Auto-run enabled — will start when countdown reaches 0")
        else:
            self._ai_viewbot_stop_auto()

    def _ai_viewbot_stop_auto(self):
        self.ai_vb_auto_var.set(False)
        if self._ai_vb_auto_id:
            try: self.root.after_cancel(self._ai_vb_auto_id)
            except: pass
        self._ai_vb_auto_id = None
        self.ai_vb_stop_btn.config(state="disabled")
        self.ai_vb_status.set("Auto-run stopped.")

    def _ai_vb_write(self, text, clear=False):
        cb = self.ai_vb_box
        cb.config(state="normal")
        if clear:
            cb.delete("1.0", "end")
        if text:
            cb.insert("end", text)
        cb.config(state="disabled")

    def _ai_viewbot_save(self):
        cb = self.ai_vb_box
        text = cb.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("Empty", "No analysis to save yet.")
            return
        slug = self.channel["slug"] if self.channel else "kick"
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files","*.txt")],
            initialfile=f"ai_viewbot_{slug}_{ts}.txt")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            messagebox.showinfo("Saved", f"Analysis saved to:\n{path}")

    def _ai_viewbot_clear(self):
        self._ai_vb_write("", clear=True)
        self.ai_score_var.set("—")
        self.ai_verdict_var.set("—")
        self.ai_lastrun_var.set("Never")
        self.ai_vb_status.set("Cleared.")

    def _build_events_tab(self):
        f = tk.Frame(self.nb, bg=BG)
        self.nb.add(f, text="🎉 Events")

        self.events_box = scrolledtext.ScrolledText(
            f, bg=BG2, fg=WHITE, font=("Consolas",10),
            state="disabled", wrap="word", relief="flat")
        self.events_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.events_box.tag_config("raid",      foreground=YELLOW,  font=("Consolas",11,"bold"))
        self.events_box.tag_config("sub",       foreground=ACCENT2, font=("Consolas",10,"bold"))
        self.events_box.tag_config("gift",      foreground=ACCENT,  font=("Consolas",10,"bold"))
        self.events_box.tag_config("ban",       foreground=RED,     font=("Consolas",10,"bold"))
        self.events_box.tag_config("unban",     foreground=ACCENT,  font=("Consolas",10,"bold"))
        self.events_box.tag_config("pin",       foreground=BLUE,    font=("Consolas",10,"bold"))
        self.events_box.tag_config("delete",    foreground=GREY,    font=("Consolas",10))
        self.events_box.tag_config("streamend", foreground=RED,     font=("Consolas",11,"bold"))
        self.events_box.tag_config("time",      foreground=GREY)
        self.events_box.tag_config("plain",     foreground=WHITE)


    def _append_event(self, ev):
        eb   = self.events_box
        ts   = datetime.fromtimestamp(ev["timestamp"]).strftime("%H:%M:%S")
        d    = ev["data"]
        kind = ev["kind"]
        eb.config(state="normal")
        eb.insert("end", f"[{ts}] ", "time")

        if kind == "raid":
            host = d.get("host_username") or d.get("channel", {}).get("slug","?")
            vwrs = d.get("number_viewers", "?")
            eb.insert("end", f"🚀 RAID       {host} raided with {vwrs} viewers!\n", "raid")

        elif kind == "subscription":
            u = (d.get("username")
              or d.get("user",{}).get("username","?")
              or d.get("subscriber",{}).get("username","?"))
            months = d.get("months_subscribed") or d.get("months","")
            month_str = f" ({months} months)" if months else ""
            # Handle ChannelSubscriptionEvent which has user_ids list
            if not u or u == "?":
                uids = d.get("user_ids", [])
                if uids:
                    u = f"{len(uids)} user(s)"
            eb.insert("end", f"⭐ SUB        {u} just subscribed!{month_str}\n", "sub")

        elif kind == "gift":
            u = (d.get("gifted_by")
              or d.get("gifter_username","?")
              or d.get("user",{}).get("username","?"))
            recipients = (d.get("gifted_usernames")
                       or d.get("gifted_users")
                       or d.get("recipients", []))
            # LuckyUsersWhoGotGiftSubscriptionsEvent has a users list
            if not recipients:
                recipients = d.get("users", [])
            qty = d.get("quantity") or d.get("amount") or len(recipients) or 1
            if u == "?" and recipients:
                u = f"{len(recipients)} lucky users"
            eb.insert("end", f"🎁 GIFT       {u} gifted {qty} sub(s)!\n", "gift")

        elif kind == "ban":
            u = d.get("user",{}).get("username","?")
            eb.insert("end", f"🔨 BAN        {u} was banned.\n", "ban")

        elif kind == "unban":
            u = d.get("user",{}).get("username","?")
            eb.insert("end", f"✅ UNBAN      {u} was unbanned.\n", "unban")

        elif kind == "pin":
            eb.insert("end", f"📌 PIN        A message was pinned.\n", "pin")

        elif kind == "delete":
            msg_id = d.get("id","") if isinstance(d, dict) else ""
            eb.insert("end", f"🗑 DELETED    A message was removed.\n", "delete")

        elif kind == "streamend":
            title = ""
            if isinstance(d, dict):
                ls = d.get("livestream", {})
                title = ls.get("session_title","") if ls else ""
            eb.insert("end", f"📴 STREAM ENDED  {title}\n", "streamend")

        elif kind == "unknown":
            event_name = d.get("event","?").split("\\")[-1] if isinstance(d, dict) else str(d)
            eb.insert("end", f"❓ UNKNOWN    {event_name}: {str(d.get('data','') if isinstance(d,dict) else '')[:60]}\n", "plain")

        else:
            eb.insert("end", f"ℹ {kind}: {str(d)[:80]}\n", "plain")

        eb.config(state="disabled")
        eb.see("end")

    # ── Tab: Chatters ─────────────────────────────────────────

    def _build_chatters_tab(self):
        f = tk.Frame(self.nb, bg=BG)
        self.nb.add(f, text="👥 Chatters")

        toolbar = tk.Frame(f, bg=BG2)
        toolbar.pack(fill="x")
        tk.Button(toolbar, text="⟳ Scan", command=self._refresh_chatters,
                  bg=ACCENT, fg="#000", font=("Segoe UI",9,"bold"),
                  relief="flat", padx=10, pady=3).pack(side="left", padx=8, pady=4)
        tk.Button(toolbar, text="💾 Export CSV", command=self._export_chatters_csv,
                  bg=BG3, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=8, pady=3).pack(side="left", padx=4, pady=4)
        self.chatter_filter_var = tk.StringVar()
        self.chatter_filter_var.trace("w", lambda *_: self._refresh_chatters())
        tk.Label(toolbar, text="Filter:", bg=BG2, fg=GREY,
                 font=("Segoe UI",9)).pack(side="left")
        tk.Entry(toolbar, textvariable=self.chatter_filter_var, width=16,
                 bg=BG3, fg=WHITE, insertbackground=WHITE,
                 font=("Segoe UI",9), relief="flat").pack(side="left", padx=6, pady=4)
        self.chatter_type_var = tk.StringVar(value="All")
        for opt in ["All","active","casual","lurker","known_bot","likely_bot"]:
            tk.Radiobutton(toolbar, text=opt, variable=self.chatter_type_var,
                           value=opt, bg=BG2, fg=WHITE, selectcolor=BG3,
                           font=("Segoe UI",9),
                           command=self._refresh_chatters).pack(side="left", padx=3)

        # Auto Scan checkbox — far right, ticked by default
        self.chatter_auto_var = tk.BooleanVar(value=True)
        tk.Checkbutton(toolbar, text="Auto Scan (30s)",
                       variable=self.chatter_auto_var,
                       bg=BG2, fg=WHITE, selectcolor=BG3,
                       font=("Segoe UI",9),
                       command=self._chatter_auto_toggle
                       ).pack(side="right", padx=10)
        self._chatter_auto_id = None

        cols = ("Username","Messages","Type","Rate/s","Badges")
        self.chatter_tree = ttk.Treeview(f, columns=cols, show="headings",
                                          selectmode="browse")
        style = ttk.Style()
        style.configure("Treeview",            background=BG2, foreground=WHITE,
                        fieldbackground=BG2,   rowheight=24,
                        font=("Segoe UI",10))
        style.configure("Treeview.Heading",    background=BG3, foreground=ACCENT,
                        font=("Segoe UI",10,"bold"))
        style.map("Treeview", background=[("selected", BG3)])

        widths = [180, 90, 100, 80, 200]
        for col, w in zip(cols, widths):
            self.chatter_tree.heading(col, text=col,
                command=lambda c=col: self._sort_chatters(c))
            self.chatter_tree.column(col, width=w, anchor="w")

        sb = ttk.Scrollbar(f, orient="vertical", command=self.chatter_tree.yview)
        self.chatter_tree.configure(yscroll=sb.set)
        self.chatter_tree.pack(side="left", fill="both", expand=True, padx=(4,0), pady=4)
        sb.pack(side="right", fill="y", pady=4, padx=(0,4))

        self._sort_col = "Messages"
        self._sort_rev = True


    def _chatter_auto_toggle(self):
        if self.chatter_auto_var.get():
            self._chatter_auto_scan()
        else:
            if self._chatter_auto_id:
                self.root.after_cancel(self._chatter_auto_id)
                self._chatter_auto_id = None

    def _chatter_auto_scan(self):
        if not self.chatter_auto_var.get():
            return
        self._refresh_chatters()
        self._chatter_auto_id = self.root.after(30000, self._chatter_auto_scan)

    def _refresh_chatters(self):
        classified = self.engine.classify()
        filt  = self.chatter_filter_var.get().lower()
        ttype = self.chatter_type_var.get()
        for row in self.chatter_tree.get_children():
            self.chatter_tree.delete(row)
        rows = []
        for name, d in classified.items():
            if ttype != "All" and d["label"] != ttype: continue
            if filt and filt not in name.lower(): continue
            rows.append((name, d["count"], d["label"], d["rate"],
                         ", ".join(d["badges"]) or "—"))
        col_idx = {"Username":0,"Messages":1,"Type":2,"Rate/s":3,"Badges":4}
        idx = col_idx.get(self._sort_col, 1)
        rows.sort(key=lambda r: r[idx], reverse=self._sort_rev)
        tag_map = {"active":"act","casual":"cas","lurker":"lur",
                   "known_bot":"bot","likely_bot":"bot"}
        self.chatter_tree.tag_configure("act", foreground=ACCENT)
        self.chatter_tree.tag_configure("cas", foreground=WHITE)
        self.chatter_tree.tag_configure("lur", foreground=GREY)
        self.chatter_tree.tag_configure("bot", foreground=RED)
        for r in rows:
            tag = tag_map.get(r[2],"cas")
            self.chatter_tree.insert("","end", values=r, tags=(tag,))


    def _sort_chatters(self, col):
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = True
        self._refresh_chatters()

    # ── Tab: Top Words ────────────────────────────────────────

    def _build_words_tab(self):
        f = tk.Frame(self.nb, bg=BG)
        self.nb.add(f, text="🔤 Top Words")

        toolbar = tk.Frame(f, bg=BG2)
        toolbar.pack(fill="x")
        tk.Button(toolbar, text="⟳ Scan", command=self._refresh_words,
                  bg=ACCENT, fg="#000", font=("Segoe UI",9,"bold"),
                  relief="flat", padx=10, pady=3).pack(side="left", padx=8, pady=4)

        self.words_hide_emotes_var = tk.BooleanVar(value=False)
        tk.Checkbutton(toolbar, text="Hide emotes", variable=self.words_hide_emotes_var,
                       bg=BG2, fg=WHITE, selectcolor=BG3,
                       font=("Segoe UI",9),
                       command=self._refresh_words).pack(side="left", padx=8)

        self.words_auto_refresh_var = tk.BooleanVar(value=True)
        tk.Checkbutton(toolbar, text="Auto Scan (20s)", variable=self.words_auto_refresh_var,
                       bg=BG2, fg=WHITE, selectcolor=BG3,
                       font=("Segoe UI",9),
                       command=self._words_auto_refresh_toggle).pack(side="left", padx=4)

        self.words_status_var = tk.StringVar(value="")
        tk.Label(toolbar, textvariable=self.words_status_var, bg=BG2, fg=GREY,
                 font=("Segoe UI",8)).pack(side="right", padx=10)

        self.words_canvas = tk.Canvas(f, bg=BG2, highlightthickness=0)
        wsb = ttk.Scrollbar(f, orient="vertical", command=self.words_canvas.yview)
        self.words_canvas.configure(yscrollcommand=wsb.set)
        self.words_canvas.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        wsb.pack(side="right", fill="y", pady=4)
        self.words_inner = tk.Frame(self.words_canvas, bg=BG2)
        self.words_canvas.create_window((0,0), window=self.words_inner, anchor="nw")
        self.words_inner.bind("<Configure>",
            lambda e: self.words_canvas.configure(
                scrollregion=self.words_canvas.bbox("all")))

        self._words_auto_id = None   # holds the after() job id


    def _words_auto_refresh_toggle(self):
        """Start or stop the auto-refresh loop."""
        if self.words_auto_refresh_var.get():
            self._words_schedule_refresh()
        else:
            if self._words_auto_id:
                self.root.after_cancel(self._words_auto_id)
                self._words_auto_id = None
            self.words_status_var.set("")


    def _words_schedule_refresh(self):
        """Refresh now and schedule the next one in 20s if still enabled."""
        if not self.words_auto_refresh_var.get():
            return
        self._refresh_words()
        ts = datetime.now().strftime("%H:%M:%S")
        self.words_status_var.set(f"Auto-scanned {ts}")
        self._words_auto_id = self.root.after(20000, self._words_schedule_refresh)


    def _refresh_words(self):
        for w in self.words_inner.winfo_children():
            w.destroy()
        classified = self.engine.classify()

        # Emote detection — top_words lowercases all words already.
        # Kick emotes come through as the emote name + numeric ID e.g.
        # "emote3232323", "pog123456", "kekw99887" — always end in 4+ digits.
        hide_emotes = self.words_hide_emotes_var.get()

        def is_emote(word):
            """
            Detect Kick emotes after lowercasing:
              - ends in 4 or more digits  (emote3232323, kekw12345)
              - is purely numeric
              - contains any digit at all (Kick always appends ID to emote name)
            """
            import re as _re
            # Any word containing digits is almost certainly a Kick emote ID
            if _re.search(r'\d', word):
                return True
            return False

        words = self.engine.top_words(classified, 50)

        if hide_emotes:
            words = [(w, c) for w, c in words if not is_emote(w)]

        words = words[:30]   # show top 30 after filtering

        if not words:
            tk.Label(self.words_inner,
                     text="No data yet." if not hide_emotes else
                          "No non-emote words yet.",
                     bg=BG2, fg=GREY, font=("Segoe UI",11)).pack(pady=20)
            return

        max_c = words[0][1] if words else 1
        for i, (word, count) in enumerate(words, 1):
            emote_flag = "〔emote〕" if is_emote(word) else ""
            row = tk.Frame(self.words_inner, bg=BG2)
            row.pack(fill="x", padx=12, pady=2)
            tk.Label(row, text=f"{i:>2}.", bg=BG2, fg=GREY,
                     font=("Consolas",11), width=3).pack(side="left")
            colour = ACCENT2 if is_emote(word) else WHITE
            tk.Label(row, text=word, bg=BG2, fg=colour,
                     font=("Consolas",11), width=22, anchor="w").pack(side="left")
            bar_w = max(4, int((count / max_c) * 280))
            bar_colour = ACCENT2 if is_emote(word) else ACCENT
            bar = tk.Frame(row, bg=bar_colour, height=16, width=bar_w)
            bar.pack(side="left", padx=6)
            tk.Label(row, text=str(count), bg=BG2, fg=bar_colour,
                     font=("Consolas",11)).pack(side="left", padx=4)
            if emote_flag and not hide_emotes:
                tk.Label(row, text=emote_flag, bg=BG2, fg=GREY,
                         font=("Segoe UI",7)).pack(side="left")

    # ── Tab: Chart ────────────────────────────────────────────

    def _build_chart_tab(self):
        f = tk.Frame(self.nb, bg=BG)
        self.nb.add(f, text="📊 Activity Chart")

        toolbar = tk.Frame(f, bg=BG2)
        toolbar.pack(fill="x")
        tk.Button(toolbar, text="⟳ Scan", command=self._refresh_chart,
                  bg=ACCENT, fg="#000", font=("Segoe UI",9,"bold"),
                  relief="flat", padx=10, pady=3).pack(side="left", padx=8, pady=4)

        # Auto Scan checkbox — far right, ticked by default
        self.chart_auto_var = tk.BooleanVar(value=True)
        tk.Checkbutton(toolbar, text="Auto Scan (20s)",
                       variable=self.chart_auto_var,
                       bg=BG2, fg=WHITE, selectcolor=BG3,
                       font=("Segoe UI",9),
                       command=self._chart_auto_toggle
                       ).pack(side="right", padx=10)
        self._chart_auto_id = None

        self.chart_canvas = tk.Canvas(f, bg=BG2, highlightthickness=0)
        self.chart_canvas.pack(fill="both", expand=True, padx=8, pady=8)


    def _chart_auto_toggle(self):
        if self.chart_auto_var.get():
            self._chart_auto_scan()
        else:
            if self._chart_auto_id:
                self.root.after_cancel(self._chart_auto_id)
                self._chart_auto_id = None

    def _chart_auto_scan(self):
        if not self.chart_auto_var.get():
            return
        self._refresh_chart()
        self._chart_auto_id = self.root.after(20000, self._chart_auto_scan)

    def _refresh_chart(self):
        c  = self.chart_canvas
        c.delete("all")
        counts = self.engine.timeline(30)
        if not counts or max(counts) == 0:
            c.create_text(400, 200, text="No data yet — start monitoring a channel.",
                          fill=GREY, font=("Segoe UI",13))
            return
        W = c.winfo_width() or 900
        H = c.winfo_height() or 400
        pad_l, pad_r, pad_t, pad_b = 60, 20, 20, 50
        n       = len(counts)
        max_c   = max(counts)
        bar_w   = (W - pad_l - pad_r) / n
        elapsed = (time.time() - self.engine.start_time) if self.engine.start_time else 1
        bsize   = elapsed / n

        # Grid lines
        for i in range(5):
            y = pad_t + (H - pad_t - pad_b) * i / 4
            val = int(max_c * (1 - i/4))
            c.create_line(pad_l, y, W-pad_r, y, fill=BG3, width=1)
            c.create_text(pad_l-6, y, text=str(val), fill=GREY,
                          font=("Consolas",9), anchor="e")

        # Bars
        for i, cnt in enumerate(counts):
            x1 = pad_l + i * bar_w + 2
            x2 = pad_l + (i+1) * bar_w - 2
            bh = (cnt / max_c) * (H - pad_t - pad_b) if max_c else 0
            y1 = H - pad_b - bh
            y2 = H - pad_b
            colour = ACCENT if cnt == max_c else BLUE
            c.create_rectangle(x1, y1, x2, y2, fill=colour, outline="")
            if cnt > 0:
                c.create_text((x1+x2)/2, y1-6, text=str(cnt),
                              fill=WHITE, font=("Consolas",8))
            # X label (time)
            t_start = i * bsize
            mins = int(t_start // 60)
            secs = int(t_start % 60)
            if i % 5 == 0:
                c.create_text((x1+x2)/2, H-pad_b+12,
                              text=f"{mins}:{secs:02d}",
                              fill=GREY, font=("Consolas",8))

        # Axes
        c.create_line(pad_l, pad_t, pad_l, H-pad_b, fill=GREY, width=2)
        c.create_line(pad_l, H-pad_b, W-pad_r, H-pad_b, fill=GREY, width=2)
        c.create_text(W//2, H-10, text="Time →",
                      fill=GREY, font=("Segoe UI",9))
        c.create_text(14, H//2, text="msgs", fill=GREY,
                      font=("Segoe UI",9), angle=90)

    # ── Tab: Report ───────────────────────────────────────────

    def _build_report_tab(self):
        f = tk.Frame(self.nb, bg=BG)
        self.nb.add(f, text="📄 Report")

        toolbar = tk.Frame(f, bg=BG2)
        toolbar.pack(fill="x")
        tk.Button(toolbar, text="⟳ Generate Report", command=self._generate_report,
                  bg=ACCENT, fg="#000", font=("Segoe UI",9,"bold"),
                  relief="flat", padx=10, pady=3).pack(side="left", padx=8, pady=4)
        tk.Button(toolbar, text="💾 Save to File", command=self._save_report,
                  bg=BG3, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=10, pady=3).pack(side="left", padx=4, pady=4)

        self.report_box = scrolledtext.ScrolledText(
            f, bg=BG2, fg=WHITE, font=("Consolas",10),
            state="disabled", wrap="word", relief="flat")
        self.report_box.pack(fill="both", expand=True, padx=4, pady=4)

    # ── Tab: Streamer Info ────────────────────────────────────


    # ── Tab: AI Guide ─────────────────────────────────────────
    def _build_guide_tab(self):
        f = tk.Frame(self.nb, bg=BG)
        self.nb.add(f, text="📖 AI Guide")

        # Toolbar
        tb = tk.Frame(f, bg=BG2)
        tb.pack(fill="x")
        tk.Label(tb, text="  AI Analysis Guide — How to use AI models and read results",
                 bg=BG2, fg=GREY, font=("Segoe UI",9)).pack(side="left", padx=8, pady=4)
        tk.Button(tb, text="⬆ Scroll to Top",
                  command=lambda: guide_box.yview_moveto(0),
                  bg=BG3, fg=WHITE, font=("Segoe UI",8),
                  relief="flat", padx=8, pady=2).pack(side="right", padx=8, pady=4)

        # Scrollable text box
        guide_box = scrolledtext.ScrolledText(
            f, bg=BG2, fg=WHITE, font=("Consolas", 10),
            wrap="word", relief="flat", state="normal",
            padx=16, pady=12)
        guide_box.pack(fill="both", expand=True, padx=4, pady=4)

        # Colour tags
        guide_box.tag_config("heading",  foreground=ACCENT,  font=("Consolas",11,"bold"))
        guide_box.tag_config("subhead",  foreground=YELLOW,  font=("Consolas",10,"bold"))
        guide_box.tag_config("body",     foreground=WHITE,   font=("Consolas",10))
        guide_box.tag_config("divider",  foreground=BG3,     font=("Consolas",10))
        guide_box.tag_config("metric",   foreground=ACCENT2, font=("Consolas",10))
        guide_box.tag_config("verdict",  foreground=YELLOW,  font=("Consolas",10,"bold"))

        # Embed the guide text with colour coding
        GUIDE_TEXT = """╔══════════════════════════════════════════════════════════════════════════════╗
║      KICK STREAM ANALYTICS — AI ANALYSIS GUIDE                             ║
║      Understanding AI Models, GPU Requirements & Reading Your Results       ║
╚══════════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 SECTION 1 — HOW AI MODELS WORK WITH THIS APPLICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHAT IS AN LLM?

  LLM stands for Large Language Model. Think of it as an extremely well-read
  analyst who has studied billions of documents, research papers, forum posts,
  and data sets. It has learned patterns in language and reasoning so well
  that it can read a set of numbers and metrics and write a detailed,
  intelligent analysis — just like a human expert would.

  The key word is "large" — the bigger the model, the more it has learned,
  and the more nuanced and accurate its reasoning becomes.

HOW IT WORKS IN THIS APP

  When you click Run AI Analysis, the app does the following:

  Step 1 — DATA COLLECTION
    The app gathers everything it has monitored during your session:
      • Viewer count history (every 30 seconds)
      • Total unique chatters and their message counts
      • Messages per minute rate
      • Chat-to-viewer ratio
      • Subscription, gift and raid events
      • Known and likely bot detections
      • Viewer count spike and drop percentages
      • Stream duration, category, channel info

  Step 2 — BUILDING THE PROMPT
    All that data is formatted into a detailed briefing document — called a
    "prompt" — that describes the stream metrics in a structured way. This is
    sent to the AI model as the question it needs to answer.

    Think of it like emailing a forensic analyst and saying:
    "Here is everything we know about this stream. What do you think?"

  Step 3 — AI REASONING
    The AI model reads the entire prompt and reasons through the data the
    same way a human expert would — comparing your stream's numbers against
    what healthy, real streams typically look like, identifying patterns that
    are suspicious, considering alternative explanations, and forming a
    verdict based on the weight of evidence.

  Step 4 — THE REPORT
    The AI writes back a full structured report covering six sections:
    Executive Summary, Signal Analysis, Suspicious Patterns, Legitimate
    Explanations, Confidence Assessment, and Final Verdict.

    This report appears in the AI Analysis tab and the key verdict
    updates the Viewbot Detector panel in the side bar automatically.

WHY DOES IT NEED 10 MINUTES OF DATA?

  The AI's analysis is only as good as the data you give it. In the first
  few minutes of monitoring, you don't have enough data points to draw
  meaningful conclusions. After 10 minutes you have:

    • 20+ viewer count snapshots to build a curve
    • Hundreds or thousands of chat messages to analyse
    • A reliable chat-to-viewer ratio
    • Time to observe whether any real events (subs, gifts, raids) occur
    • Enough history to spot spikes, drops or unnatural flatness

  This is why the Run AI Analysis button is locked for the first 10 minutes.
  Analysing a stream after 2 minutes would produce unreliable results.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 SECTION 2 — DEFAULT MODELS BY GPU AND HOW THEY WORK TOGETHER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHAT IS VRAM AND WHY DOES IT MATTER?

  VRAM (Video RAM) is the memory on your graphics card (GPU). AI models are
  stored entirely in VRAM while running. Think of VRAM like a desk — the
  bigger your desk, the larger the document you can spread out and read at
  once. A bigger model needs a bigger desk.

  If a model is too large for your VRAM it will either refuse to run or
  spill over into regular system RAM, which is dramatically slower —
  like moving half your papers to a filing cabinet in another room.

  Running a model that fits comfortably in your VRAM means it runs fast
  and produces results in 30-90 seconds. Running one that doesn't fit
  properly can take 5-15 minutes or time out entirely.

GPU TIERS AND DEFAULT MODELS

  ┌─────────────────────────────────────────────────────────────────────┐
  │  GPU TIER       VRAM      DEFAULT MODEL      MODEL SIZE             │
  ├─────────────────────────────────────────────────────────────────────┤
  │  High End       20GB+     qwen3:32b          ~20GB                  │
  │  Upper Mid      10-20GB   qwen3:14b          ~9GB                   │
  │  Mid Range      7-10GB    qwen3:8b           ~5.2GB  ← Recommended │
  │  Entry Mid      5-7GB     mistral:7b         ~4.4GB                 │
  │  Budget GPU     3-5GB     qwen3:4b           ~2.5GB                 │
  │  Low VRAM       1-3GB     llama3.2:3b        ~2.0GB                 │
  │  CPU Only       No GPU    phi3:mini          ~2.3GB                 │
  └─────────────────────────────────────────────────────────────────────┘

4GB GPU (e.g. GTX 1650, RTX 3050)
  Default: qwen3:4b

  The qwen3:4b model uses about 2.5GB of your 4GB VRAM, leaving headroom
  for your operating system and other processes. Despite being a smaller
  model, qwen3:4b is part of Alibaba's Qwen3 series which is specifically
  engineered for strong reasoning in a compact size. It will produce a
  solid viewbot analysis report with clear verdicts, though it may be less
  detailed than larger models on subtle or complex cases.

  What to expect:
    • Analysis time: 30-60 seconds
    • Report quality: Good — covers all 6 sections reliably
    • Best for: Catching obvious viewbot cases, quick checks
    • Limitation: May miss subtle sophisticated botting patterns

8GB GPU (e.g. RTX 3070, RTX 3060, RTX 4060)
  Default: qwen3:8b  ← Best free local option

  This is the sweet spot for local AI analysis. The qwen3:8b model uses
  about 5.2GB of your 8GB VRAM, running fully on the GPU for fast,
  high quality results. Real-world testing on this application showed
  qwen3:8b outperforming the older llama3.1:8b on analytical reasoning
  tasks — it produces more structured, decisive and accurate reports.

  What to expect:
    • Analysis time: 45-90 seconds
    • Report quality: Very good — detailed reasoning, accurate verdicts
    • Best for: All viewbot cases including moderately sophisticated ones
    • Note: Approaches Claude API quality on clear-cut cases

12GB+ GPU (e.g. RTX 3080, RTX 4070, RTX 4090)
  Default: qwen3:14b or qwen3:32b

  With 12GB or more VRAM you can run 14 billion parameter models which
  represent a significant jump in reasoning capability. At 20GB+ you can
  run the full qwen3:32b model which produces analysis very close to
  the commercial Claude API in quality and depth.

  What to expect:
    • Analysis time: 60-120 seconds (larger model = more processing)
    • Report quality: Excellent — nuanced, forensic-level analysis
    • Best for: Complex cases, borderline streams, research investigations
    • qwen3:32b approaches Claude Sonnet quality on difficult cases

CPU ONLY (No dedicated GPU)
  Default: phi3:mini

  If your machine has no dedicated graphics card (or integrated graphics
  only), the model runs on your CPU using system RAM instead. Microsoft's
  phi3:mini is specifically designed and optimised for CPU inference —
  it uses aggressive compression techniques to run efficiently without
  a GPU. The tradeoff is speed: expect 2-5 minutes for a full analysis.

  What to expect:
    • Analysis time: 2-5 minutes
    • Report quality: Decent — will catch obvious cases
    • Best for: Occasional use on office machines, laptops without GPU
    • Tip: Consider using the Anthropic API instead for faster results

HOW THE GPU DETECTION WORKS

  When you click "Detect GPU" in the AI Analysis tab the app:

  1. Queries nvidia-smi (Nvidia's own diagnostic tool) for exact VRAM
  2. Falls back to GPUtil Python library if nvidia-smi isn't available
  3. Falls back to Windows WMI (built-in system query) as a last resort

  The detected GPU name, VRAM amount and recommended model are saved
  automatically so you never need to detect again on the same machine.
  Results are stored in ai_settings.json next to the application.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 SECTION 3 — HOW AI CALCULATES SCORES AND WHY BIGGER MODELS ARE BETTER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HOW THE NUMERIC DETECTOR WORKS (The side panel score)

  The numeric detector in the side panel uses a simple rule-based system.
  Think of it like a checklist with points:

    Chat ratio below 1%?        → Add 22 points
    Viewer spike over 100%?     → Add 28 points
    Msgs/min per 1k below 3?    → Add 14 points
    High bot ratio?             → Add 6 points
    Spike AND low ratio?        → Bonus multiplier

  These rules were set by hand and work well for obvious cases. But they
  have a fundamental limitation: they only look at each signal one at a
  time. They can't reason about the combination of signals in context.

  Example of where it fails:
    A stream with 110,000 viewers, 0.79% chat ratio, and 1.67 msgs/min
    per 1,000 viewers might only score 28/100 — LOW RISK — because the
    viewer curve happened to look relatively smooth and the spike score
    was low. But a human expert looking at those same numbers would
    immediately recognise this as almost certainly viewbotted.

HOW THE AI CALCULATES ITS SCORE (The AI Analysis report)

  The AI model doesn't use a fixed checklist. Instead it reasons about
  the data the same way a forensic analyst would:

  1. BASELINE COMPARISON
     The AI knows what healthy streams look like from its training data.
     It compares your stream's metrics against those baselines and asks:
     "How far does each signal deviate from normal?"

  2. CROSS-VALIDATION
     Instead of scoring each signal separately, the AI looks for
     consistency across all signals. For example:

     "This stream has 111,000 viewers but only 185 messages per minute.
      185 messages per minute is consistent with roughly 3,700-18,500
      organic viewers — not 111,000. The message volume and the viewer
      count are telling completely different stories. That contradiction
      is the most important signal."

     A simple checklist can't do this. The AI can.

  3. ALTERNATIVE EXPLANATIONS
     The AI actively considers innocent explanations before concluding
     botting. Could this be a quiet stream? A different cultural audience?
     A raid that just ended? It weighs these alternatives and states its
     confidence level explicitly.

  4. WEIGHTED VERDICT
     The AI combines all its observations into a final verdict, scoring
     0-100 and assigning one of five labels:
       CLEAN              Very likely legitimate
       LOW RISK           Minor anomalies, probably fine
       SUSPICIOUS         Multiple red flags, investigate further
       HIGH RISK          Strong evidence of viewbotting
       CONFIRMED BOTTING  Overwhelming evidence, near certain

WHY BIGGER MODELS ARE BETTER

  Model size is measured in "parameters" — think of parameters as the
  number of connections in the AI's brain. More connections = more
  nuance = better reasoning.

  ┌──────────────┬────────────┬──────────────────────────────────────┐
  │ Model        │ Parameters │ Capability                           │
  ├──────────────┼────────────┼──────────────────────────────────────┤
  │ phi3:mini    │ 3.8B       │ Basic analysis, obvious cases        │
  │ qwen3:4b     │ 4B         │ Good analysis, most cases            │
  │ qwen3:8b     │ 8B         │ Strong analysis, subtle cases        │
  │ qwen3:14b    │ 14B        │ Excellent, near-API quality          │
  │ qwen3:32b    │ 32B        │ Outstanding, approaches Claude       │
  │ Claude Sonnet│ ~70B+      │ Forensic quality, best available    │
  └──────────────┴────────────┴──────────────────────────────────────┘

  The difference in practice:

  SMALL MODEL (4B) on a borderline stream:
    "The chat ratio is below the healthy threshold. This may indicate
    viewbotting. Further investigation is recommended."

  LARGE MODEL (32B or Claude) on the same stream:
    "At 111,119 viewers, a healthy engagement rate would produce between
    3,334 and 8,889 chatters. This stream produced 875 over more than an
    hour — approximately 1/4 of the low end of the healthy range. The
    message volume of 185 per minute cross-validates to an organic audience
    of roughly 3,700-18,500 viewers, orders of magnitude smaller than the
    displayed count. Additionally, only 4 subscriptions were recorded during
    this period — at a conservative 0.1% conversion rate, 111K viewers
    would be expected to generate 111 subscriptions. The engagement deficit
    has no comfortable organic explanation at this scale."

  The larger model catches the same red flags but ALSO:
    • Cross-validates multiple signals against each other
    • Calculates what the numbers imply about real audience size
    • Considers the financial conversion angle (subs/gifts)
    • States exactly how confident it is and why
    • Produces a more persuasive, evidence-based verdict

WHY THE CLAUDE API IS CURRENTLY THE BEST OPTION

  Claude Sonnet (the Anthropic API model) is a frontier-class commercial
  AI with hundreds of billions of parameters trained by one of the world's
  leading AI safety companies. It represents a step above even the best
  local models available today.

  In real-world testing on this application, Claude Sonnet:
    • Performed cross-validation that local models missed entirely
    • Correctly isolated organic audience size from the message volume
    • Used the subscription deficit as a key corroborating signal
    • Distinguished between chat bots and viewer bots (separate fraud types)
    • Noted that platform context matters (Kick skews more chat-active
      than YouTube, making low ratios more alarming on Kick specifically)

  Cost: approximately $0.03 per full analysis — less than a cent for
  most sessions. For serious investigation work the quality difference
  is worth it.

  The tradeoff:
    • Requires an internet connection and an API key
    • Costs a small amount per use
    • Data is sent to Anthropic's servers (only stream metrics, never
      personal data or your account information)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 SECTION 4 — HOW TO READ YOUR AI ANALYSIS REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

YOUR REPORT HAS SIX SECTIONS — HERE IS WHAT EACH ONE MEANS:

─────────────────────────────────────────────────────────────────────────────
  1. EXECUTIVE SUMMARY
─────────────────────────────────────────────────────────────────────────────

  This is the TL;DR — the AI's overall impression in one paragraph.
  Read this first. It will tell you immediately whether the AI thinks
  something is wrong and give you the headline finding.

  What to look for:
    • "Deeply contradictory data profile" = serious red flags found
    • "Consistent with organic viewership" = stream looks legitimate
    • "Further investigation warranted" = borderline, needs more time
    • Any mention of a specific ratio being far below healthy = key signal

  Example of a HIGH RISK summary:
    "A channel broadcasting to 111,119 viewers is generating chat activity
    consistent with a stream of roughly 1,500-3,000 organic viewers. The
    engagement deficit is the story, and it is damning."

  Example of a CLEAN summary:
    "All engagement metrics are consistent with organic viewership at this
    scale. Chat activity, message rates and event frequency all fall within
    expected ranges for a stream of this size."

─────────────────────────────────────────────────────────────────────────────
  2. SIGNAL ANALYSIS
─────────────────────────────────────────────────────────────────────────────

  This section examines each metric individually. The AI looks at:

  VIEWER COUNT CURVE SHAPE
    Is the viewer count rising and falling naturally, or is it suspiciously
    flat or showing sudden vertical jumps? Real streams fluctuate naturally
    as viewers join and leave. Viewbots tend to maintain an unnaturally
    steady count or spike suddenly in large round numbers.

    Key terms:
      "Unnaturally flat" = viewer count barely moves (bots hold steady)
      "Standard deviation < 5%" = too little variation for a real stream
      "Vertical spike" = sudden jump of 50%+ in under 3 minutes
      "Organic drift" = normal gentle rises and falls

  CHAT-TO-VIEWER RATIO
    This is often the single most important signal. It measures what
    percentage of viewers are actively chatting.

    Healthy ranges:
      3-8%  = normal for most live streams
      1-3%  = quiet stream, some concern
      < 1%  = very suspicious at large viewer counts
      < 0.5% = almost certainly artificial viewers

    Why this matters: Viewbots can inflate the viewer count number, but
    they cannot chat. Real viewers chat. If you have 100,000 viewers but
    only 500 chatters — that ratio (0.5%) is telling you the real audience
    is far smaller than the number suggests.

  MESSAGE RATE PER 1,000 VIEWERS
    This is a normalised version of chat activity — how active is the
    chat relative to the viewer count? A stream with 1,000 viewers having
    100 messages per minute is very different from a stream with 100,000
    viewers having 100 messages per minute.

    Healthy range: 10-50 messages per minute per 1,000 viewers
    Suspicious:    below 5
    Very suspicious: below 2

    The AI will often cross-validate this number to estimate the real
    organic audience size. For example:
      "185 messages per minute at a healthy rate of 10-50/min/1k viewers
       implies an organic audience of 3,700-18,500 — not 111,000."

  BOT PRESENCE IN CHAT
    This detects bots that are chatting — account names matching known
    bot patterns, or accounts sending identical messages at inhuman speeds.

    Important note: This signal detects CHAT bots, not VIEWER bots.
    These are two different types of fraud. Viewer bots inflate the
    viewer counter but do not chat. The absence of chat bots does NOT
    mean there are no viewer bots — they are separate mechanisms.

  EVENT ACTIVITY (Subs, Gifts, Raids)
    Real viewers subscribe, gift subs to others, and raid other channels.
    Viewbots cannot do any of these things — they have no accounts, no
    wallets, and no ability to take actions.

    At high viewer counts, the absence of financial activity is a strong
    signal:
      "4 subscriptions at 111,000 viewers — at 0.1% conversion that
       should be 111 subscriptions. The financial silence is deafening."

─────────────────────────────────────────────────────────────────────────────
  3. SUSPICIOUS PATTERNS IDENTIFIED
─────────────────────────────────────────────────────────────────────────────

  This section lists the specific observations that raised concern,
  written as bullet points or a numbered list. Read this carefully —
  this is where the AI explains exactly WHY it is suspicious.

  Strong patterns to watch for:
    • Multiple signals all pointing the same direction simultaneously
    • Chat volume consistent with much smaller real audience
    • Subscription/gift count far below what viewer count implies
    • Viewer curve flat during moments that should cause spikes
      (raids, hype moments, exciting gameplay)
    • Message volume that matches a 3,000 viewer stream, not 100,000

─────────────────────────────────────────────────────────────────────────────
  4. LEGITIMATE EXPLANATIONS
─────────────────────────────────────────────────────────────────────────────

  A good AI analyst always considers innocent explanations before
  concluding fraud. This section lists alternative reasons that could
  explain the data without viewbotting being involved.

  Common legitimate explanations:
    • Recent raid from a large channel (sudden viewer spike is natural)
    • Category or title change that pulled in browsing viewers
    • Stream is primarily background content (music, sleep streams)
    • Non-English speaking audience with different chat culture
    • Stream just started and audience hasn't settled

  How to use this section:
    If the AI lists a legitimate explanation that you know applies
    (e.g. you saw a massive raid happen), weight the verdict accordingly.
    If none of the listed explanations seem to apply based on what you
    observed, that strengthens the case for viewbotting.

─────────────────────────────────────────────────────────────────────────────
  5. CONFIDENCE ASSESSMENT
─────────────────────────────────────────────────────────────────────────────

  This section tells you how certain the AI is about its verdict and why.

  High confidence means:
    • Multiple independent signals all agree
    • The numbers are far outside normal ranges, not borderline
    • Legitimate explanations have been considered and ruled out
    • The cross-validation of different metrics produces consistent results

  Low confidence means:
    • Only one or two signals are flagged
    • The numbers are in a borderline range
    • There are plausible legitimate explanations
    • The monitoring session was too short or data was limited

  Always read this section alongside the verdict. A HIGH RISK verdict
  with LOW confidence should prompt you to monitor longer before drawing
  conclusions. A SUSPICIOUS verdict with HIGH confidence is worth taking
  seriously even though it's not the strongest verdict label.

─────────────────────────────────────────────────────────────────────────────
  6. FINAL VERDICT
─────────────────────────────────────────────────────────────────────────────

  The AI's bottom line. One of five labels with a score 0-100:

  ✅ CLEAN (0-20)
    All metrics are consistent with organic viewership. No action needed.
    The stream looks legitimate based on the available data.

  🟢 LOW RISK (21-40)
    Minor anomalies detected but nothing that strongly indicates fraud.
    Could be a quiet stream, niche audience, or just an off day.
    Worth a second look if you monitor again and see the same pattern.

  🟡 SUSPICIOUS (41-65)
    Multiple signals raise concern. Not conclusive, but warrants attention.
    Recommended: monitor for another session to see if the pattern persists.
    Note the specific signals flagged and watch whether they improve.

  🔴 HIGH RISK (66-85)
    Strong evidence of artificial viewer inflation. The data profile is
    very difficult to explain through organic means. Multiple independent
    signals point in the same direction. This stream should be reported
    to Kick.com through their official reporting channels.

  🔴 CONFIRMED BOTTING (86-100)
    Overwhelming evidence. The combination of signals — engagement deficit,
    financial silence, curve analysis, message cross-validation — all
    converge on the same conclusion with very high confidence. The gap
    between displayed viewers and real audience is almost certainly
    artificial. Report immediately.

WHAT TO DO WITH THE RESULTS

  CLEAN or LOW RISK:
    No action required. Continue monitoring if you want more data.

  SUSPICIOUS:
    Monitor the stream for a second 10-minute session. If the pattern
    persists across two independent sessions the case is stronger.

  HIGH RISK or CONFIRMED BOTTING:
    1. Save the analysis report using the Save Analysis button
    2. Note the channel name, date, time and key metrics
    3. Report to Kick.com:  kick.com/help (use the Report Content option)
    4. You can reference specific metrics from the report in your submission
       (e.g. "0.79% chat ratio with 111,000 viewers, 4 subs in 63 minutes")

A NOTE ON CERTAINTY

  No tool — human or AI — can be 100% certain about viewbotting from
  metrics alone. The AI analysis provides a probability assessment based
  on available evidence. It is a powerful investigative tool, not a
  definitive legal determination.

  The strongest cases are those where:
    • Multiple independent signals all point the same direction
    • The numbers are far outside normal ranges (not borderline)
    • The pattern is consistent across more than one monitoring session
    • Legitimate explanations have been considered and don't apply


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 QUICK REFERENCE — KEY METRICS AT A GLANCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  CHAT-TO-VIEWER RATIO
    Healthy:       3-8%
    Concerning:    1-3%
    Suspicious:    < 1%
    Very suspicious: < 0.5%

  MESSAGES PER MINUTE PER 1,000 VIEWERS
    Healthy:       10-50
    Concerning:    5-10
    Suspicious:    2-5
    Very suspicious: < 2

  VIEWER CURVE FLATNESS (standard deviation)
    Healthy:       > 5% variation
    Suspicious:    < 3% variation
    Very suspicious: < 1% variation

  VIEWER SPIKE (within 3 minutes)
    Normal:        < 25%
    Concerning:    25-50%
    Suspicious:    50-100%
    Very suspicious: > 100%

  SUBSCRIPTION RATE (rough benchmark)
    Expected minimum: 0.05-0.1% of viewer count per hour
    e.g. 100,000 viewers → expect at least 50-100 subs/hour
    Near zero subs at high viewer counts = strong red flag

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 CREATED FOR  Kick Stream Analytics & Deep AI Research Tool
 by Ask_fOr_DaX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        import re as _re
        for line in GUIDE_TEXT.split("\n"):
            stripped = line.strip()
            # Section headers (all caps with dashes)
            if stripped.startswith("━") or stripped.startswith("─"):
                guide_box.insert("end", line + "\n", "divider")
            elif stripped.startswith("╔") or stripped.startswith("╚") or stripped.startswith("║"):
                guide_box.insert("end", line + "\n", "heading")
            elif _re.match(r"^ SECTION \d+", line):
                guide_box.insert("end", line + "\n", "heading")
            elif stripped.startswith("SECTION ") or (
                stripped.isupper() and len(stripped) > 4 and stripped.isalpha()):
                guide_box.insert("end", line + "\n", "heading")
            elif stripped and stripped[0].isdigit() and ". " in stripped[:4] and stripped.isupper():
                guide_box.insert("end", line + "\n", "subhead")
            elif any(stripped.startswith(x) for x in
                     ["✅", "🟢", "🟡", "🔴", "CLEAN", "LOW RISK",
                      "SUSPICIOUS", "HIGH RISK", "CONFIRMED"]):
                guide_box.insert("end", line + "\n", "verdict")
            elif stripped.startswith("Healthy:") or stripped.startswith("Suspicious:") or \
                 stripped.startswith("Concerning:") or stripped.startswith("Very suspicious:") or \
                 stripped.startswith("Expected"):
                guide_box.insert("end", line + "\n", "metric")
            elif stripped.startswith("┌") or stripped.startswith("│") or \
                 stripped.startswith("├") or stripped.startswith("└"):
                guide_box.insert("end", line + "\n", "metric")
            else:
                guide_box.insert("end", line + "\n", "body")

        guide_box.config(state="disabled")

    def _build_streamer_info_tab(self):
        f = tk.Frame(self.nb, bg=BG)
        self.nb.add(f, text="🎙 Streamer Info")

        # ── Toolbar ───────────────────────────────────────────
        tb = tk.Frame(f, bg=BG2)
        tb.pack(fill="x")
        tk.Label(tb, text="Streamer:", bg=BG2, fg=WHITE,
                 font=("Segoe UI",10)).pack(side="left", padx=(10,4), pady=6)
        self.info_slug_var = tk.StringVar()
        e = tk.Entry(tb, textvariable=self.info_slug_var, width=20,
                     bg=BG3, fg=WHITE, insertbackground=WHITE,
                     font=("Segoe UI",11), relief="flat", bd=4)
        e.pack(side="left", pady=6)
        e.bind("<Return>", lambda _: self._load_streamer_info())
        tk.Button(tb, text="▶ Watch Stream", command=self._info_watch_stream,
                  bg=BG3, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=10, pady=4, cursor="hand2").pack(side="left", padx=8)
        tk.Button(tb, text="💾 Export", command=self._export_streamer_info,
                  bg=BG3, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=10, pady=4, cursor="hand2").pack(side="left", padx=4)
        self.info_status_var = tk.StringVar(value="Streamer info loads automatically when monitoring starts")
        tk.Label(tb, textvariable=self.info_status_var, bg=BG2, fg=GREY,
                 font=("Segoe UI",9)).pack(side="right", padx=12)

        # Auto-load when tab is selected
        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # ── Main content area: left card + right scrollable ───
        content = tk.Frame(f, bg=BG)
        content.pack(fill="both", expand=True, padx=8, pady=6)

        # Left: profile card
        left = tk.Frame(content, bg=BG2, width=240)
        left.pack(side="left", fill="y", padx=(0,6))
        left.pack_propagate(False)

        # Avatar placeholder
        self.info_avatar_frame = tk.Frame(left, bg=BG3, height=120)
        self.info_avatar_frame.pack(fill="x", padx=8, pady=(10,4))
        self.info_avatar_label = tk.Label(self.info_avatar_frame,
                                           text="👤", font=("Segoe UI",48),
                                           bg=BG3, fg=GREY)
        self.info_avatar_label.pack(expand=True)

        self.info_display_name = tk.Label(left, text="—",
                                           font=("Segoe UI",14,"bold"),
                                           bg=BG2, fg=WHITE, wraplength=220)
        self.info_display_name.pack(pady=(4,0))
        self.info_slug_label = tk.Label(left, text="—",
                                         font=("Segoe UI",9),
                                         bg=BG2, fg=GREY)
        self.info_slug_label.pack()
        self.info_verified_label = tk.Label(left, text="",
                                             font=("Segoe UI",9,"bold"),
                                             bg=BG2, fg=ACCENT)
        self.info_verified_label.pack()

        tk.Frame(left, bg=BG3, height=1).pack(fill="x", padx=8, pady=8)

        # Key stats in card
        stats_frame = tk.Frame(left, bg=BG2)
        stats_frame.pack(fill="x", padx=8)
        self._si = {}   # store info row vars
        for label in ["Status","Followers","Channel Age",
                       "Total Streams","Avg Viewers","Peak Viewers",
                       "Mature","Subscriber Badges"]:
            row = tk.Frame(stats_frame, bg=BG2)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, bg=BG2, fg=GREY,
                     font=("Segoe UI",8), width=15, anchor="w").pack(side="left")
            var = tk.StringVar(value="—")
            tk.Label(row, textvariable=var, bg=BG2, fg=WHITE,
                     font=("Segoe UI",8,"bold"), anchor="w",
                     wraplength=110).pack(side="left")
            self._si[label] = var

        tk.Frame(left, bg=BG3, height=1).pack(fill="x", padx=8, pady=8)

        # Social links
        tk.Label(left, text="SOCIAL LINKS", bg=BG2, fg=GREY,
                 font=("Segoe UI",8,"bold")).pack(anchor="w", padx=8)
        self.info_socials_frame = tk.Frame(left, bg=BG2)
        self.info_socials_frame.pack(fill="x", padx=8, pady=4)

        # Right: scrollable detail panels
        right_outer = tk.Frame(content, bg=BG)
        right_outer.pack(side="left", fill="both", expand=True)

        canvas = tk.Canvas(right_outer, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(right_outer, orient="vertical",
                                   command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.info_right = tk.Frame(canvas, bg=BG)
        canvas_window = canvas.create_window((0,0), window=self.info_right,
                                              anchor="nw")
        def _on_frame_config(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_canvas_config(e):
            canvas.itemconfig(canvas_window, width=e.width)
        self.info_right.bind("<Configure>", _on_frame_config)
        canvas.bind("<Configure>", _on_canvas_config)
        # Mouse wheel scrolling
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Section builder helper
        def make_section(title):
            sec = tk.Frame(self.info_right, bg=BG2)
            sec.pack(fill="x", padx=4, pady=4)
            tk.Label(sec, text=title, bg=BG2, fg=YELLOW,
                     font=("Segoe UI",10,"bold")).pack(anchor="w", padx=10, pady=(8,4))
            tk.Frame(sec, bg=BG3, height=1).pack(fill="x", padx=10, pady=(0,6))
            return sec

        # Bio section
        bio_sec = make_section("📝  Channel Bio")
        self.info_bio_text = tk.Text(bio_sec, bg=BG3, fg=WHITE,
                                      font=("Segoe UI",10), height=4,
                                      wrap="word", relief="flat",
                                      state="disabled", padx=8, pady=6)
        self.info_bio_text.pack(fill="x", padx=10, pady=(0,8))

        # Stream activity section
        activity_sec = make_section("📊  Stream Activity")
        self.info_activity_frame = tk.Frame(activity_sec, bg=BG2)
        self.info_activity_frame.pack(fill="x", padx=10, pady=(0,8))

        # Top categories section
        cat_sec = make_section("🎮  Top Categories Streamed")
        self.info_categories_frame = tk.Frame(cat_sec, bg=BG2)
        self.info_categories_frame.pack(fill="x", padx=10, pady=(0,8))

        # Recent streams section
        recent_sec = make_section("🎬  Recent Streams")
        cols = ("Date","Title","Category","Duration","Viewers")
        self.info_vod_tree = ttk.Treeview(recent_sec, columns=cols,
                                           show="headings", height=8,
                                           selectmode="none")
        widths = [120, 280, 130, 80, 80]
        for col, w in zip(cols, widths):
            self.info_vod_tree.heading(col, text=col)
            self.info_vod_tree.column(col, width=w, anchor="w")
        self._style_tree(self.info_vod_tree)
        self.info_vod_tree.pack(fill="x", padx=10, pady=(0,8))

        # Top clips section
        clips_sec = make_section("✂️  Top Clips")
        cols2 = ("Date","Title","Category","Duration","Views")
        self.info_clips_tree = ttk.Treeview(clips_sec, columns=cols2,
                                             show="headings", height=6,
                                             selectmode="browse")
        widths2 = [120, 280, 130, 80, 80]
        for col, w in zip(cols2, widths2):
            self.info_clips_tree.heading(col, text=col)
            self.info_clips_tree.column(col, width=w, anchor="w")
        self._style_tree(self.info_clips_tree)
        self.info_clips_tree.bind("<Double-1>", self._info_open_clip)
        self.info_clips_tree.pack(fill="x", padx=10, pady=(0,4))
        tk.Label(clips_sec, text="Double-click a clip to open in browser",
                 bg=BG2, fg=GREY, font=("Segoe UI",8)).pack(anchor="w", padx=10, pady=(0,8))

        # Store clip data for double-click
        self._info_clip_data = []
        self._info_channel_data = None

    # ── Streamer Info: load & populate ───────────────────────

    def _on_tab_changed(self, event=None):
        """Auto-load streamer info when the Streamer Info tab is selected."""
        try:
            current = self.nb.tab(self.nb.select(), "text")
            if "Streamer Info" in current:
                # Only auto-load if we have a channel and haven't loaded yet
                if self.channel and not self.info_slug_var.get():
                    slug = self.channel.get("slug", "")
                    if slug:
                        self.info_slug_var.set(slug)
                        self._load_streamer_info()
        except Exception:
            pass

    def _load_streamer_info(self):
        slug = self.info_slug_var.get().strip().lower()
        if not slug:
            slug = self.slug_var.get().strip().lower()
        if not slug:
            messagebox.showwarning("Missing", "Enter a streamer username.")
            return
        self.info_slug_var.set(slug)
        self.info_status_var.set(f"Loading info for '{slug}'...")
        threading.Thread(target=self._fetch_streamer_info,
                         args=(slug,), daemon=True).start()


    def _fetch_streamer_info(self, slug):
        """Fetch channel data, VODs and clips in parallel."""
        results = {}
        lock = threading.Lock()

        def fetch(key, fn):
            try:
                data = fn()
                with lock:
                    results[key] = data
            except Exception:
                pass

        threads = [
            threading.Thread(target=fetch, args=("channel", lambda: get_channel(slug))),
            threading.Thread(target=fetch, args=("vods",    lambda: get_videos(slug, 1))),
            threading.Thread(target=fetch, args=("clips",   lambda: get_clips(slug, 1, "view"))),
        ]
        for t in threads: t.start()
        for t in threads: t.join()

        self.root.after(0, lambda: self._populate_streamer_info(slug, results))


    def _populate_streamer_info(self, slug, results):
        raw     = results.get("channel")
        vod_raw = results.get("vods")
        clip_raw= results.get("clips")

        if not raw:
            self.info_status_var.set(f"⚠ Could not load channel: {slug}")
            return

        ch   = parse_channel(raw)
        user = raw.get("user", {}) or {}
        self._info_channel_data = {"channel": ch, "raw": raw}

        # ── Profile card ──────────────────────────────────────
        self.info_display_name.config(text=ch["display_name"])
        self.info_slug_label.config(text=f"kick.com/{ch['slug']}")
        self.info_verified_label.config(
            text="✓ Verified" if ch["verified"] else "")

        # Key stats
        # Channel creation date
        created = raw.get("created_at","")
        ch_age  = "N/A"
        if created:
            dt = parse_kick_time(created)
            if dt:
                delta = datetime.now(timezone.utc) - dt
                years  = delta.days // 365
                months = (delta.days % 365) // 30
                ch_age = f"{years}y {months}m" if years else f"{months} months"
                ch_age += f"  (joined {dt.strftime('%b %Y')})"

        # VOD stats
        vods = []
        if vod_raw:
            vods = vod_raw if isinstance(vod_raw, list) else \
                   vod_raw.get("data", vod_raw.get("videos", []))
        total_streams = len(vods)
        peak_viewers  = max((v.get("viewer_count",0) for v in vods), default=0)
        avg_viewers   = (sum(v.get("viewer_count",0) for v in vods) // total_streams
                         if total_streams else 0)

        # Sub badge count
        badges = raw.get("subscriber_badges", [])

        self._si["Status"].set("🔴 LIVE" if ch["is_live"] else "⬛ Offline")
        self._si["Followers"].set(f"{ch['followers']:,}")
        self._si["Channel Age"].set(ch_age)
        self._si["Total Streams"].set(f"{total_streams:,}" if total_streams else "N/A")
        self._si["Avg Viewers"].set(f"{avg_viewers:,}" if total_streams else "N/A")
        self._si["Peak Viewers"].set(f"{peak_viewers:,}" if total_streams else "N/A")
        self._si["Mature"].set("Yes" if ch["mature"] else "No")
        self._si["Subscriber Badges"].set(str(len(badges)) if badges else "0")

        # Bio
        bio = ch.get("bio","") or user.get("bio","") or "No bio available."
        self.info_bio_text.config(state="normal")
        self.info_bio_text.delete("1.0","end")
        self.info_bio_text.insert("end", bio)
        self.info_bio_text.config(state="disabled")

        # Social links
        for w in self.info_socials_frame.winfo_children():
            w.destroy()
        icons = {"twitter":"🐦","youtube":"▶","instagram":"📷",
                 "discord":"💬","tiktok":"🎵","facebook":"👥"}
        socials = ch.get("social","") or {}
        if not socials and isinstance(ch.get("social"), dict):
            socials = ch["social"]
        if not socials:
            socials = {p: user.get(p,"") for p in
                       ["twitter","youtube","instagram","discord","tiktok"]
                       if user.get(p)}
        if socials:
            for platform, url in socials.items():
                if url:
                    icon = icons.get(platform.lower(),"🔗")
                    row  = tk.Frame(self.info_socials_frame, bg=BG2)
                    row.pack(fill="x", pady=1)
                    tk.Label(row, text=f"{icon} {platform.title()}",
                             bg=BG2, fg=WHITE, font=("Segoe UI",8),
                             width=12, anchor="w").pack(side="left")
                    tk.Label(row, text=str(url)[:25], bg=BG2, fg=BLUE,
                             font=("Segoe UI",8), anchor="w").pack(side="left")
        else:
            tk.Label(self.info_socials_frame, text="No social links on profile",
                     bg=BG2, fg=GREY, font=("Segoe UI",8)).pack(anchor="w")

        # ── Stream activity summary ───────────────────────────
        for w in self.info_activity_frame.winfo_children():
            w.destroy()
        if vods:
            total_dur  = sum(v.get("duration",0) for v in vods)
            total_hrs  = total_dur // 3600000
            total_mins = (total_dur % 3600000) // 60000
            avg_dur    = fmt_duration(total_dur // total_streams) if total_streams else "N/A"

            # Stream frequency — how many per week on average
            if total_streams >= 2:
                dates = []
                for v in vods:
                    dt = parse_kick_time(v.get("created_at","") or
                                         v.get("start_time",""))
                    if dt: dates.append(dt)
                if len(dates) >= 2:
                    span_days = (max(dates) - min(dates)).days or 1
                    per_week  = round(len(dates) / span_days * 7, 1)
                    freq_str  = f"{per_week} streams/week"
                else:
                    freq_str = "N/A"
            else:
                freq_str = "N/A"

            stats = [
                ("Total Hours Streamed", f"{total_hrs}h {total_mins}m"),
                ("Avg Stream Duration",  avg_dur),
                ("Stream Frequency",     freq_str),
                ("Peak Viewers",         f"{peak_viewers:,}"),
                ("Avg Viewers",          f"{avg_viewers:,}"),
            ]
        else:
            stats = [("No VOD data available","—")]

        for label, val in stats:
            row = tk.Frame(self.info_activity_frame, bg=BG2)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, bg=BG2, fg=GREY,
                     font=("Segoe UI",9), width=22, anchor="w").pack(side="left")
            tk.Label(row, text=val, bg=BG2, fg=WHITE,
                     font=("Segoe UI",9,"bold")).pack(side="left")

        # ── Top categories ────────────────────────────────────
        for w in self.info_categories_frame.winfo_children():
            w.destroy()
        if vods:
            from collections import Counter as _Counter
            cat_counts = _Counter()
            for v in vods:
                for cat in v.get("categories",[]):
                    cat_counts[cat.get("name","?")] += 1
            max_c = max(cat_counts.values()) if cat_counts else 1
            for cat, cnt in cat_counts.most_common(8):
                row = tk.Frame(self.info_categories_frame, bg=BG2)
                row.pack(fill="x", pady=2)
                bar_w = max(4, int((cnt/max_c) * 200))
                tk.Label(row, text=cat, bg=BG2, fg=WHITE,
                         font=("Segoe UI",9), width=24, anchor="w").pack(side="left")
                tk.Frame(row, bg=ACCENT, height=14,
                         width=bar_w).pack(side="left", padx=4)
                tk.Label(row, text=f"{cnt} stream{'s' if cnt!=1 else ''}",
                         bg=BG2, fg=GREY, font=("Segoe UI",8)).pack(side="left")
        else:
            tk.Label(self.info_categories_frame, text="No category data available",
                     bg=BG2, fg=GREY, font=("Segoe UI",9)).pack(anchor="w")

        # ── Recent streams VOD table ──────────────────────────
        for row in self.info_vod_tree.get_children():
            self.info_vod_tree.delete(row)
        for v in vods[:15]:
            cats = v.get("categories",[])
            cat  = cats[0].get("name","?") if cats else "N/A"
            self.info_vod_tree.insert("","end", values=(
                fmt_date(v.get("created_at","") or v.get("start_time","")),
                (v.get("session_title","") or v.get("title","—"))[:55],
                cat,
                fmt_duration(v.get("duration",0)),
                f"{v.get('viewer_count',0):,}",
            ))

        # ── Top clips ─────────────────────────────────────────
        for row in self.info_clips_tree.get_children():
            self.info_clips_tree.delete(row)
        clips = []
        if clip_raw:
            clips = clip_raw if isinstance(clip_raw, list) else \
                    clip_raw.get("data", clip_raw.get("clips", []))
        self._info_clip_data = clips
        for c in clips[:10]:
            cats = c.get("category",{})
            cat  = cats.get("name","N/A") if isinstance(cats,dict) else "N/A"
            self.info_clips_tree.insert("","end", values=(
                fmt_date(c.get("created_at","")),
                (c.get("title","—"))[:55],
                cat,
                fmt_duration(c.get("duration",0)*1000),
                f"{c.get('views',0):,}",
            ))

        n_clips = len(clips)
        self.info_status_var.set(
            f"✓ Loaded  —  {ch['followers']:,} followers  |  "
            f"{total_streams} VODs  |  {n_clips} clips")


    def _info_watch_stream(self):
        import webbrowser
        slug = self.info_slug_var.get().strip().lower()
        if slug:
            webbrowser.open(f"https://kick.com/{slug}")


    def _info_open_clip(self, event):
        import webbrowser
        sel = self.info_clips_tree.selection()
        if not sel: return
        idx = self.info_clips_tree.index(sel[0])
        if idx < len(self._info_clip_data):
            c    = self._info_clip_data[idx]
            slug = c.get("slug") or c.get("clip_id") or c.get("id","")
            ch_slug = self.info_slug_var.get().strip().lower()
            url = f"https://kick.com/{ch_slug}?clip={slug}" if slug \
                  else f"https://kick.com/{ch_slug}"
            webbrowser.open(url)


    def _export_streamer_info(self):
        if not self._info_channel_data:
            messagebox.showinfo("No Data","Load a streamer first.")
            return
        ch   = self._info_channel_data["channel"]
        raw  = self._info_channel_data["raw"]
        user = raw.get("user",{}) or {}
        bio  = ch.get("bio","") or user.get("bio","")

        lines = [
            "═"*60,
            f"  STREAMER INFO  —  {ch['display_name']}",
            f"  kick.com/{ch['slug']}",
            "═"*60,"",
            f"  Display Name : {ch['display_name']}",
            f"  Slug         : {ch['slug']}",
            f"  Verified     : {'Yes' if ch['verified'] else 'No'}",
            f"  Followers    : {ch['followers']:,}",
            f"  Mature       : {'Yes' if ch['mature'] else 'No'}",
            f"  Status       : {'LIVE' if ch['is_live'] else 'Offline'}",
            "",
            "── STATS ──────────────────────────────────────────",
        ]
        for label, var in self._si.items():
            lines.append(f"  {label:<20}: {var.get()}")
        lines += ["","── BIO ────────────────────────────────────────────",
                  f"  {bio}",""]

        socials = ch.get("social",{}) or {}
        if socials:
            lines.append("── SOCIAL LINKS ───────────────────────────────────")
            for p, v in socials.items():
                if v: lines.append(f"  {p.title():<12}: {v}")
            lines.append("")

        lines += ["═"*60]
        text = "\n".join(lines)

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files","*.txt")],
            initialfile=f"streamer_info_{ch['slug']}.txt")
        if path:
            with open(path,"w",encoding="utf-8") as fh:
                fh.write(text)
            messagebox.showinfo("Saved",f"Saved to:\n{path}")

    # ── Tab: Historical Data ──────────────────────────────────

    def _build_history_tab(self):
        f = tk.Frame(self.nb, bg=BG)
        self.nb.add(f, text="📅 History")

        # Top bar: slug entry + load button
        topbar = tk.Frame(f, bg=BG2)
        topbar.pack(fill="x", padx=0, pady=0)

        tk.Label(topbar, text="Streamer:", bg=BG2, fg=WHITE,
                 font=("Segoe UI",10)).pack(side="left", padx=(12,4), pady=6)
        self.hist_slug_var = tk.StringVar()
        tk.Entry(topbar, textvariable=self.hist_slug_var, width=18,
                 bg=BG3, fg=WHITE, insertbackground=WHITE,
                 font=("Segoe UI",11), relief="flat", bd=4).pack(side="left", pady=6)
        tk.Button(topbar, text="🔍 Load History", command=self._load_history,
                  bg=ACCENT, fg="#000", font=("Segoe UI",10,"bold"),
                  relief="flat", padx=12, pady=4, cursor="hand2").pack(side="left", padx=10)
        self.hist_status = tk.StringVar(value="Enter a streamer name and click Load History")
        tk.Label(topbar, textvariable=self.hist_status, bg=BG2, fg=GREY,
                 font=("Segoe UI",9)).pack(side="left", padx=8)

        # Inner notebook with sub-tabs
        inner_style = ttk.Style()
        inner_style.configure("Inner.TNotebook",     background=BG,  borderwidth=0)
        inner_style.configure("Inner.TNotebook.Tab", background=BG3, foreground=GREY,
                               padding=[10,4], font=("Segoe UI",9,"bold"))
        inner_style.map("Inner.TNotebook.Tab",
                        background=[("selected", BG2)],
                        foreground=[("selected", YELLOW)])

        self.hist_nb = ttk.Notebook(f, style="Inner.TNotebook")
        self.hist_nb.pack(fill="both", expand=True, padx=4, pady=4)

        self._build_hist_vods_tab()
        self._build_hist_clips_tab()
        self._build_hist_leaderboard_tab()
        self._build_hist_summary_tab()


    def _build_hist_vods_tab(self):
        f = tk.Frame(self.hist_nb, bg=BG)
        self.hist_nb.add(f, text="🎬 Past Streams (VODs)")

        toolbar = tk.Frame(f, bg=BG2)
        toolbar.pack(fill="x")
        tk.Button(toolbar, text="◀ Prev Page", command=lambda: self._vod_page(-1),
                  bg=BG3, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=8, pady=3).pack(side="left", padx=6, pady=4)
        tk.Button(toolbar, text="Next Page ▶", command=lambda: self._vod_page(1),
                  bg=BG3, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=8, pady=3).pack(side="left", pady=4)
        tk.Button(toolbar, text="💾 Export CSV", command=self._export_vods_csv,
                  bg=BG3, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=8, pady=3).pack(side="right", padx=8, pady=4)
        self.vod_page_var = tk.StringVar(value="Page 1")
        tk.Label(toolbar, textvariable=self.vod_page_var, bg=BG2, fg=GREY,
                 font=("Segoe UI",9)).pack(side="left", padx=12)
        self.vod_count_var = tk.StringVar(value="")
        tk.Label(toolbar, textvariable=self.vod_count_var, bg=BG2, fg=ACCENT,
                 font=("Segoe UI",9,"bold")).pack(side="left")

        cols = ("Date", "Title", "Category", "Duration", "Views")
        self.vod_tree = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
        widths = [140, 340, 140, 90, 80]
        for col, w in zip(cols, widths):
            self.vod_tree.heading(col, text=col)
            self.vod_tree.column(col, width=w, anchor="w")
        self._style_tree(self.vod_tree)
        sb = ttk.Scrollbar(f, orient="vertical", command=self.vod_tree.yview)
        self.vod_tree.configure(yscroll=sb.set)
        self.vod_tree.pack(side="left", fill="both", expand=True, padx=(4,0), pady=4)
        sb.pack(side="right", fill="y", pady=4, padx=(0,4))

        self._vod_current_page = 1
        self._vod_data = []


    def _build_hist_clips_tab(self):
        f = tk.Frame(self.hist_nb, bg=BG)
        self.hist_nb.add(f, text="✂️ Clips")

        toolbar = tk.Frame(f, bg=BG2)
        toolbar.pack(fill="x")
        tk.Label(toolbar, text="Sort by:", bg=BG2, fg=WHITE,
                 font=("Segoe UI",9)).pack(side="left", padx=(10,4), pady=4)
        self.clip_sort_var = tk.StringVar(value="view")
        for label, val in [("Most Viewed","view"), ("Recent","date")]:
            tk.Radiobutton(toolbar, text=label, variable=self.clip_sort_var,
                           value=val, bg=BG2, fg=WHITE, selectcolor=BG3,
                           font=("Segoe UI",9),
                           command=self._reload_clips).pack(side="left", padx=4)
        tk.Button(toolbar, text="◀ Prev", command=lambda: self._clip_page(-1),
                  bg=BG3, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=8, pady=3).pack(side="left", padx=10, pady=4)
        tk.Button(toolbar, text="Next ▶", command=lambda: self._clip_page(1),
                  bg=BG3, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=8, pady=3).pack(side="left", pady=4)
        tk.Button(toolbar, text="💾 Export CSV", command=self._export_clips_csv,
                  bg=BG3, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=8, pady=3).pack(side="right", padx=8, pady=4)
        self.clip_page_var = tk.StringVar(value="Page 1")
        tk.Label(toolbar, textvariable=self.clip_page_var, bg=BG2, fg=GREY,
                 font=("Segoe UI",9)).pack(side="left", padx=10)

        cols = ("Date", "Title", "Category", "Duration", "Views", "URL")
        self.clip_tree = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
        widths = [120, 300, 130, 80, 70, 220]
        for col, w in zip(cols, widths):
            self.clip_tree.heading(col, text=col)
            self.clip_tree.column(col, width=w, anchor="w")
        self._style_tree(self.clip_tree)
        # Double-click opens clip in browser
        self.clip_tree.bind("<Double-1>", self._open_clip)
        sb = ttk.Scrollbar(f, orient="vertical", command=self.clip_tree.yview)
        self.clip_tree.configure(yscroll=sb.set)
        self.clip_tree.pack(side="left", fill="both", expand=True, padx=(4,0), pady=4)
        sb.pack(side="right", fill="y", pady=4, padx=(0,4))

        tk.Label(f, text="Double-click a clip to open it in your browser",
                 bg=BG, fg=GREY, font=("Segoe UI",8)).pack(pady=(0,4))

        self._clip_current_page = 1
        self._clip_data = []


    def _build_hist_leaderboard_tab(self):
        f = tk.Frame(self.hist_nb, bg=BG)
        self.hist_nb.add(f, text="🏆 Leaderboards")

        panes = tk.Frame(f, bg=BG)
        panes.pack(fill="both", expand=True, padx=4, pady=4)

        # Gifters (all-time)
        left = tk.Frame(panes, bg=BG2)
        left.pack(side="left", fill="both", expand=True, padx=(0,4))
        tk.Label(left, text="🎁 TOP GIFTERS (All-Time)", bg=BG2, fg=ACCENT,
                 font=("Segoe UI",11,"bold")).pack(pady=(8,4))
        cols = ("Rank","Username","Gifts")
        self.gift_tree = ttk.Treeview(left, columns=cols, show="headings",
                                       selectmode="none", height=20)
        for col, w in zip(cols, [60,200,80]):
            self.gift_tree.heading(col, text=col)
            self.gift_tree.column(col, width=w, anchor="w")
        self._style_tree(self.gift_tree)
        self.gift_tree.pack(fill="both", expand=True, padx=4, pady=4)

        # Weekly gifters
        right = tk.Frame(panes, bg=BG2)
        right.pack(side="left", fill="both", expand=True, padx=(4,0))
        tk.Label(right, text="📅 TOP GIFTERS (This Week)", bg=BG2, fg=ACCENT2,
                 font=("Segoe UI",11,"bold")).pack(pady=(8,4))
        cols2 = ("Rank","Username","Gifts")
        self.sub_tree = ttk.Treeview(right, columns=cols2, show="headings",
                                      selectmode="none", height=20)
        for col, w in zip(cols2, [60,200,80]):
            self.sub_tree.heading(col, text=col)
            self.sub_tree.column(col, width=w, anchor="w")
        self._style_tree(self.sub_tree)
        self.sub_tree.pack(fill="both", expand=True, padx=4, pady=4)


    def _build_hist_summary_tab(self):
        f = tk.Frame(self.hist_nb, bg=BG)
        self.hist_nb.add(f, text="📊 Stream Stats")

        self.hist_summary_box = scrolledtext.ScrolledText(
            f, bg=BG2, fg=WHITE, font=("Consolas",10),
            state="disabled", wrap="word", relief="flat")
        self.hist_summary_box.pack(fill="both", expand=True, padx=4, pady=4)

    # ── History data loading ──────────────────────────────────

    def _load_history(self):
        slug = self.hist_slug_var.get().strip().lower()
        if not slug:
            # Fall back to the main slug if set
            slug = self.slug_var.get().strip().lower()
        if not slug:
            messagebox.showwarning("Missing", "Enter a streamer username.")
            return
        self.hist_slug_var.set(slug)
        self.hist_status.set(f"Loading history for '{slug}'...")
        threading.Thread(target=self._fetch_history, args=(slug,), daemon=True).start()


    def _fetch_history(self, slug):
        # Fetch all data in parallel via threads
        results = {}

        def fetch(key, fn):
            results[key] = fn()

        threads = [
            threading.Thread(target=fetch, args=("vods",    lambda: get_videos(slug, 1))),
            threading.Thread(target=fetch, args=("clips",   lambda: get_clips(slug, 1, "view"))),
            threading.Thread(target=fetch, args=("leaders", lambda: get_leaderboard(slug))),
        ]
        for t in threads: t.start()
        for t in threads: t.join()

        self.root.after(0, lambda: self._populate_history(slug, results))


    def _populate_history(self, slug, results):
        self._current_hist_slug = slug

        # ── VODs ──────────────────────────────────────────────
        vod_raw = results.get("vods")
        self._vod_data = []
        if vod_raw:
            # API returns either a list or {"data": [...]}
            if isinstance(vod_raw, list):
                self._vod_data = vod_raw
            elif isinstance(vod_raw, dict):
                self._vod_data = vod_raw.get("data", vod_raw.get("videos", []))
        self._vod_current_page = 1
        self._render_vods()

        # ── Clips ─────────────────────────────────────────────
        clip_raw = results.get("clips")
        self._clip_data = []
        if clip_raw:
            if isinstance(clip_raw, list):
                self._clip_data = clip_raw
            elif isinstance(clip_raw, dict):
                self._clip_data = clip_raw.get("data", clip_raw.get("clips", []))
        self._clip_current_page = 1
        self._render_clips()

        # ── Leaderboard ───────────────────────────────────────
        self._render_leaderboard(results.get("leaders"))

        # ── Summary ───────────────────────────────────────────
        self._render_hist_summary(slug)

        total_vods  = len(self._vod_data)
        total_clips = len(self._clip_data)
        self.hist_status.set(
            f"✓ Loaded: {total_vods} VODs  |  {total_clips} clips  —  kick.com/{slug}")


    def _render_vods(self, per_page=20):
        for row in self.vod_tree.get_children():
            self.vod_tree.delete(row)
        page  = self._vod_current_page
        start = (page - 1) * per_page
        chunk = self._vod_data[start:start + per_page]
        self.vod_page_var.set(f"Page {page} / {max(1, -(-len(self._vod_data)//per_page))}")
        self.vod_count_var.set(f"{len(self._vod_data)} total VODs")
        for v in chunk:
            cats = v.get("categories", [])
            cat  = cats[0].get("name","?") if cats else "N/A"
            self.vod_tree.insert("", "end", values=(
                fmt_date(v.get("created_at") or v.get("start_time","")),
                (v.get("session_title") or v.get("title","—"))[:60],
                cat,
                fmt_duration(v.get("duration",0)),
                f"{v.get('viewer_count',0):,}",
            ))


    def _render_clips(self, per_page=20):
        for row in self.clip_tree.get_children():
            self.clip_tree.delete(row)
        page  = self._clip_current_page
        start = (page - 1) * per_page
        chunk = self._clip_data[start:start + per_page]
        self.clip_page_var.set(f"Page {page} / {max(1, -(-len(self._clip_data)//per_page))}")
        for c in chunk:
            cats = c.get("category", {})
            cat  = cats.get("name","N/A") if isinstance(cats, dict) else "N/A"
            # Build the proper Kick web URL for the clip
            slug = c.get("slug") or c.get("clip_id") or c.get("id","")
            channel_slug = (c.get("channel",{}) or {}).get("slug","") or self._current_hist_slug
            if slug:
                web_url = f"https://kick.com/{channel_slug}?clip={slug}"
            else:
                # Fallback: go to channel page
                web_url = f"https://kick.com/{channel_slug}"
            self.clip_tree.insert("", "end", values=(
                fmt_date(c.get("created_at","")),
                (c.get("title","—"))[:55],
                cat,
                fmt_duration(c.get("duration",0)*1000),
                f"{c.get('views',0):,}",
                web_url,
            ))


    def _render_leaderboard(self, data):
        for t in (self.gift_tree, self.sub_tree):
            for row in t.get_children():
                t.delete(row)
        if not data:
            self.gift_tree.insert("","end",values=("—","No data available",""))
            self.sub_tree.insert("","end",values=("—","No data available",""))
            return

        # API returns: gifts (all-time), gifts_week, gifts_month
        # No subscriber leaderboard is available publicly
        gifters = (data.get("gifts")
                or data.get("gifted_subs_leaderboard")
                or data.get("top_gifters", []))

        if gifters:
            for i, g in enumerate(gifters[:20], 1):
                name = g.get("username","?")
                qty  = g.get("quantity", 0)
                self.gift_tree.insert("","end", values=(i, name, f"{qty:,}"))
        else:
            self.gift_tree.insert("","end",values=("—","No gift data",""))

        # Weekly gifters in the sub column (no sub leaderboard available)
        weekly = (data.get("gifts_week")
               or data.get("sub_leaderboard")
               or data.get("top_subscribers", []))

        if weekly:
            for i, g in enumerate(weekly[:20], 1):
                name = g.get("username","?")
                qty  = g.get("quantity") or g.get("months_subscribed") or g.get("duration", 0)
                self.sub_tree.insert("","end", values=(i, name, f"{qty:,}"))
        else:
            self.sub_tree.insert("","end",values=("—","No weekly data",""))


    def _render_hist_summary(self, slug):
        vods  = self._vod_data
        clips = self._clip_data
        if not vods and not clips:
            return
        total_vods     = len(vods)
        total_clips    = len(clips)
        total_view_dur = sum(v.get("duration",0) for v in vods)
        avg_dur        = fmt_duration(total_view_dur // total_vods) if total_vods else "N/A"
        peak_viewers   = max((v.get("viewer_count",0) for v in vods), default=0)
        avg_viewers    = int(sum(v.get("viewer_count",0) for v in vods) / total_vods) if total_vods else 0
        top_clip_views = max((c.get("views",0) for c in clips), default=0)
        cats = Counter()
        for v in vods:
            for cat in v.get("categories",[]):
                cats[cat.get("name","?")] += 1

        lines = [
            "═" * 56,
            f"  HISTORICAL SUMMARY  —  kick.com/{slug}",
            "═" * 56, "",
            "── PAST STREAMS (VODs) " + "─"*32,
            f"  Total VODs stored    : {total_vods}",
            f"  Avg stream duration  : {avg_dur}",
            f"  Peak viewers (VODs)  : {peak_viewers:,}",
            f"  Avg viewers  (VODs)  : {avg_viewers:,}",
            "",
            "── CLIPS " + "─"*45,
            f"  Total clips          : {total_clips}",
            f"  Top clip views       : {top_clip_views:,}",
            "",
        ]
        if cats:
            lines.append("── TOP CATEGORIES (by stream count) " + "─"*19)
            for cat, cnt in cats.most_common(10):
                bar = "█" * min(cnt, 30)
                lines.append(f"  {cat:<28} {bar} {cnt}")
            lines.append("")

        if vods:
            lines.append("── RECENT STREAMS " + "─"*38)
            for v in vods[:10]:
                cats2 = v.get("categories",[])
                cat   = cats2[0].get("name","?") if cats2 else "N/A"
                lines.append(
                    f"  {fmt_date(v.get('created_at',''))}  "
                    f"{fmt_duration(v.get('duration',0)):<10}  "
                    f"{v.get('viewer_count',0):>6,} viewers  "
                    f"[{cat}]"
                )
            lines.append("")

        if clips:
            lines.append("── TOP CLIPS " + "─"*43)
            top = sorted(clips, key=lambda c: c.get("views",0), reverse=True)[:10]
            for c in top:
                lines.append(
                    f"  {c.get('views',0):>7,} views  "
                    f"{fmt_date(c.get('created_at',''))}  "
                    f"{(c.get('title','—'))[:40]}"
                )

        lines += ["", "═" * 56]
        text = "\n".join(lines)
        self.hist_summary_box.config(state="normal")
        self.hist_summary_box.delete("1.0","end")
        self.hist_summary_box.insert("end", text)
        self.hist_summary_box.config(state="disabled")


    def _vod_page(self, delta):
        self._vod_current_page = max(1, self._vod_current_page + delta)
        self._render_vods()


    def _clip_page(self, delta):
        self._clip_current_page = max(1, self._clip_current_page + delta)
        self._render_clips()


    def _reload_clips(self):
        slug = getattr(self, "_current_hist_slug", "")
        if not slug: return
        sort = self.clip_sort_var.get()
        self.hist_status.set("Reloading clips...")
        def fetch():
            raw = get_clips(slug, 1, sort)
            self._clip_data = []
            if raw:
                if isinstance(raw, list):
                    self._clip_data = raw
                elif isinstance(raw, dict):
                    self._clip_data = raw.get("data", raw.get("clips",[]))
            self._clip_current_page = 1
            self.root.after(0, self._render_clips)
            self.root.after(0, lambda: self.hist_status.set(
                f"✓ {len(self._clip_data)} clips loaded"))
        threading.Thread(target=fetch, daemon=True).start()


    def _open_clip(self, event):
        import webbrowser
        sel = self.clip_tree.selection()
        if not sel: return
        vals = self.clip_tree.item(sel[0], "values")
        url  = vals[5] if len(vals) > 5 else ""
        if url:
            webbrowser.open(url)
            self.hist_status.set(f"✓ Opening: {url[:70]}")

    # ══════════════════════════════════════════════════════════
    #  TAB: TOP 100 STREAMERS
    # ══════════════════════════════════════════════════════════

    def _export_chatters_csv(self):
        classified = self.engine.classify()
        if not classified:
            messagebox.showinfo("No Data", "Start monitoring a channel first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files","*.csv")],
            initialfile=f"chatters_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
        if not path: return
        headers = ["Username","Messages","Type","Rate/s","Repeat Ratio","Badges"]
        rows = [(u, d["count"], d["label"], d["rate"], d["rep"],
                 "|".join(d["badges"])) for u, d in classified.items()]
        rows.sort(key=lambda r: r[1], reverse=True)
        export_csv(path, headers, rows)
        messagebox.showinfo("Exported", f"Saved {len(rows)} chatters to:\n{path}")


    def _export_vods_csv(self):
        if not self._vod_data:
            messagebox.showinfo("No Data", "Load VOD history first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files","*.csv")],
            initialfile=f"vods_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
        if not path: return
        headers = ["Date","Title","Category","Duration (ms)","Peak Viewers"]
        rows = []
        for v in self._vod_data:
            cats = v.get("categories",[])
            cat  = cats[0].get("name","?") if cats else "N/A"
            rows.append((
                fmt_date(v.get("created_at","")),
                v.get("session_title","") or v.get("title",""),
                cat,
                v.get("duration",0),
                v.get("viewer_count",0),
            ))
        export_csv(path, headers, rows)
        messagebox.showinfo("Exported", f"Saved {len(rows)} VODs to:\n{path}")


    def _export_clips_csv(self):
        if not self._clip_data:
            messagebox.showinfo("No Data", "Load clip history first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files","*.csv")],
            initialfile=f"clips_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
        if not path: return
        headers = ["Date","Title","Category","Duration (s)","Views","URL"]
        rows = []
        for c in self._clip_data:
            cats = c.get("category",{})
            cat  = cats.get("name","N/A") if isinstance(cats,dict) else "N/A"
            rows.append((
                fmt_date(c.get("created_at","")),
                c.get("title",""),
                cat,
                c.get("duration",0),
                c.get("views",0),
                c.get("clip_url","") or c.get("url",""),  # raw stream URL for CSV
            ))
        export_csv(path, headers, rows)
        messagebox.showinfo("Exported", f"Saved {len(rows)} clips to:\n{path}")


    def _generate_report(self, silent=False):
        if not self.channel:
            if not silent:
                messagebox.showinfo("No Data", "Start monitoring a channel first.")
            return None
        ch  = self.channel
        eng = self.engine
        classified = eng.classify()
        bots    = {u for u,d in classified.items() if "bot" in d["label"]}
        humans  = set(classified) - bots
        active  = {u for u,d in classified.items() if d["label"]=="active"} - bots
        casual  = {u for u,d in classified.items() if d["label"]=="casual"} - bots
        lurkers = {u for u,d in classified.items() if d["label"]=="lurker"} - bots
        total   = len(eng.messages)
        elapsed = (time.time() - eng.start_time) if eng.start_time else 1
        mpm     = round(total / (elapsed/60), 1)
        human_msgs = sum(d["count"] for u,d in classified.items() if u not in bots)
        bot_msgs   = total - human_msgs
        subs  = sum(1 for e in eng.events if e["kind"]=="subscription")
        gifts = sum(1 for e in eng.events if e["kind"]=="gift")
        raids = sum(1 for e in eng.events if e["kind"]=="raid")
        bans  = sum(1 for e in eng.events if e["kind"]=="ban")
        now   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = []
        W = 64
        lines += [
            "=" * W,
            f"  KICK STREAMER ANALYTICS REPORT",
            f"  Channel  : {ch['display_name']} (kick.com/{ch['slug']})",
            f"  Generated: {now}",
            "=" * W, "",
            "── CHANNEL ─────────────────────────────────────────────",
            f"  Followers  : {ch['followers']:,}",
            f"  Verified   : {'Yes' if ch['verified'] else 'No'}",
            f"  Mature     : {'Yes' if ch['mature'] else 'No'}",
        ]
        if ch.get("bio"):
            lines.append(f"  Bio        : {ch['bio']}")
        lines += ["",
            "── STREAM ──────────────────────────────────────────────",
            f"  Status     : {'🔴 LIVE' if ch['is_live'] else 'OFFLINE'}",
        ]
        if ch["is_live"]:
            lines += [
                f"  Title      : {ch['stream_title']}",
                f"  Category   : {ch['category']}",
                f"  Viewers    : {ch['viewer_count']:,}",
                f"  Live For   : {ch['duration']}",
            ]
        lines += ["",
            "── CHATROOM SETTINGS ───────────────────────────────────",
            f"  Slow Mode  : {'On' if ch['slow_mode'] else 'Off'}",
            f"  Sub Only   : {'On' if ch['sub_mode'] else 'Off'}",
            f"  Emote Only : {'On' if ch['emote_mode'] else 'Off'}",
            "",
            "── CHAT SAMPLE ─────────────────────────────────────────",
            f"  Duration      : {int(elapsed)}s ({elapsed/60:.1f} min)",
            f"  Total Messages: {total:,}",
            f"  Messages/Min  : {mpm}",
            f"  Human Messages: {human_msgs:,} ({100*human_msgs//total if total else 0}%)",
            f"  Bot Messages  : {bot_msgs:,}  ({100*bot_msgs//total if total else 0}%)",
            "",
            "── CHATTER BREAKDOWN ───────────────────────────────────",
            f"  Total Unique  : {len(classified):,}",
            f"  ├─ Humans     : {len(humans):,}",
            f"  │  ├─ Active  : {len(active):,}",
            f"  │  ├─ Casual  : {len(casual):,}",
            f"  │  └─ Lurkers : {len(lurkers):,}",
            f"  └─ Bots       : {len(bots):,}",
            "",
            "── EVENTS ──────────────────────────────────────────────",
            f"  Subscriptions : {subs}",
            f"  Gift Subs     : {gifts}",
            f"  Raids         : {raids}",
            f"  Bans          : {bans}",
            "",
        ]

        # Viewbot analysis
        vb_score, vb_verdict, vb_bd = self._calc_viewbot_score()
        viewers = ch.get("viewer_count", 0)
        chatters_n = len(eng.user_msgs)
        vb_ratio   = vb_bd.get("chat_ratio", (0,0))[0]
        vb_mpm1k   = vb_bd.get("mpm_per_1k", (0,0))[0]
        vb_spike   = vb_bd.get("spike", (0,0))[0]
        vb_botr    = vb_bd.get("bot_ratio", (0,0))[0]
        lines += [
            "── VIEWBOT ANALYSIS ────────────────────────────────────",
            f"  Risk Score     : {vb_score}/100",
            f"  Verdict        : {vb_verdict}",
            f"  Chat/Vw Ratio  : {vb_ratio:.2f}%  (healthy = 3-8%)",
            f"  Msgs/min/1k vw : {vb_mpm1k:.1f}  (healthy = 10-50)",
            f"  Peak Vw Spike  : +{vb_spike:.0f}%  (suspicious > 50%)",
            f"  Bot Ratio      : {vb_botr:.1f}%  (suspicious > 15%)",
            "",
            "── TOP CHATTERS (non-bot) ──────────────────────────────",
        ]
        top = sorted(((u,d) for u,d in classified.items() if u not in bots),
                     key=lambda x: x[1]["count"], reverse=True)[:15]
        for i,(u,d) in enumerate(top, 1):
            lines.append(f"  {i:>2}. {u:<28} {d['count']:>4} msgs  [{d['label']}]")
        lines += ["",
            "── TOP WORDS / EMOTES ──────────────────────────────────",
        ]
        for word, cnt in eng.top_words(classified, 20):
            bar = "█" * min(cnt, 30)
            lines.append(f"  {word:<22} {bar} {cnt}")
        lines += ["", "=" * W, "  End of report", "=" * W]
        text = "\n".join(lines)
        if not silent:
            self.report_box.config(state="normal")
            self.report_box.delete("1.0","end")
            self.report_box.insert("end", text)
            self.report_box.config(state="disabled")
        return text


    def _save_report(self):
        text = self._generate_report()
        if not text: return
        slug = self.channel["slug"] if self.channel else "kick"
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        default = f"report_{slug}_{ts}.txt"
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files","*.txt"),("All files","*.*")],
            initialfile=default)
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            messagebox.showinfo("Saved", f"Report saved to:\n{path}")

    # ── Mini activity bar (left panel) ────────────────────────

    def _draw_mini_bar(self):
        c = self.mini_canvas
        c.delete("all")
        if not self.engine.start_time or not self.engine.messages:
            return
        now     = time.time()
        window  = 60
        bucket  = 3
        n       = window // bucket
        counts  = [0] * n
        for m in self.engine.messages:
            age = now - m["timestamp"]
            if age > window: continue
            idx = int((window - age) / bucket)
            counts[min(idx, n-1)] += 1
        W = c.winfo_width() or 260
        H = c.winfo_height() or 60
        max_c = max(counts) or 1
        bw = W / n
        for i, cnt in enumerate(counts):
            bh = (cnt / max_c) * (H - 4)
            x1 = i * bw + 1
            x2 = (i+1) * bw - 1
            y1 = H - bh - 2
            y2 = H - 2
            colour = ACCENT if i == n-1 else BLUE
            c.create_rectangle(x1, y1, x2, y2, fill=colour, outline="")

    # ── Start / Stop ──────────────────────────────────────────

    def _start(self):
        slug = self.slug_var.get().strip().lower()
        if not slug:
            messagebox.showwarning("Missing", "Enter a streamer username.")
            return
        if not HAS_WS:
            messagebox.showerror("Missing Dependency",
                "websockets is not installed.\nRun: pip install websockets")
            return

        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_var.set(f"Fetching channel data for '{slug}'...")
        self.engine.reset()
        self._chat_buffer.clear()
        self._clear_chat()
        self._viewer_history     = []
        self._ai_verdict_locked  = False

        # Parse duration — handle countdown strings like "09:45" or "✓ Done"
        raw = self.dur_var.get().strip()
        try:
            # Plain number e.g. "600"
            self._countdown_secs = int(raw)
        except ValueError:
            try:
                # MM:SS format e.g. "09:45"
                parts = raw.replace("✓","").replace("Done","").strip().split(":")
                self._countdown_secs = int(parts[0]) * 60 + int(parts[1])
            except:
                self._countdown_secs = 600
        # Reset entry to clean state
        self.dur_var.set(str(self._countdown_secs))
        self.dur_entry.config(fg=WHITE)

        self._start_countdown()

        threading.Thread(target=self._fetch_and_start,
                         args=(slug,), daemon=True).start()

    def _fetch_and_start(self, slug):
        raw = get_channel(slug)
        if not raw:
            self.root.after(0, lambda: self._on_error(
                f"Could not fetch channel '{slug}'.\nCheck the username and try again."))
            return
        ch = parse_channel(raw)
        if not ch or not ch.get("chatroom_id"):
            self.root.after(0, lambda: self._on_error("Could not parse channel data."))
            return
        self.channel = ch
        self.root.after(0, self._update_channel_panel)

        self.engine.on_message      = lambda m: self.root.after(0, lambda: self._append_chat(m))
        self.engine.on_event        = lambda e: self.root.after(0, lambda: self._append_event(e))
        self.engine.on_connected    = lambda: self.root.after(0, self._on_connected)
        self.engine.on_reconnecting = lambda n: self.root.after(0, lambda n=n:
            self.status_var.set(f"⚠ Connection dropped — reconnecting (attempt {n})..."))
        self.engine.on_error        = lambda e: self.root.after(0, lambda: self._on_error(e))
        self.engine.start(ch["chatroom_id"], ch.get("channel_id"))

    def _start_countdown(self):
        """Lock AI button and start ticking countdown in duration entry."""
        if hasattr(self, "ai_vb_run_btn"):
            m, s = divmod(self._countdown_secs, 60)
            self.ai_vb_run_btn.config(
                state="disabled", bg="#444444", fg=YELLOW,
                text=f"\u23f3 AI ready in {m:02d}:{s:02d}")
        # Start ticking after 1 second — gives engine time to connect
        self._countdown_id = self.root.after(1000, self._countdown_tick)

    def _countdown_tick(self):
        """Decrement every second — update entry and AI button."""
        # Don't bail out — countdown runs regardless of connection state
        # (engine.running becomes True once connected)
        if self._countdown_secs > 0:
            self._countdown_secs -= 1
            m, s = divmod(self._countdown_secs, 60)
            self.dur_var.set(f"{m:02d}:{s:02d}")
            self.dur_entry.config(
                fg=YELLOW if self._countdown_secs < 60 else WHITE)
            if hasattr(self, "ai_vb_run_btn"):
                self.ai_vb_run_btn.config(
                    text=f"\u23f3 AI ready in {m:02d}:{s:02d}")
            self._countdown_id = self.root.after(1000, self._countdown_tick)
        else:
            # Done — unlock AI button
            self.dur_var.set("\u2713 Done")
            self.dur_entry.config(fg=ACCENT)
            if hasattr(self, "ai_vb_run_btn"):
                self.ai_vb_run_btn.config(
                    state="normal", bg=ACCENT, fg="#000",
                    text="\u25b6 Run AI Analysis")
            if hasattr(self, "ai_vb_status"):
                self.ai_vb_status.set(
                    "\u2705 10 minutes collected — AI Analysis is ready!")
            # If auto-run was pre-ticked, fire it now
            if hasattr(self, "ai_vb_auto_var") and self.ai_vb_auto_var.get():
                self.root.after(500, self._ai_viewbot_run)

    def _stop(self):
        # Cancel countdown
        if self._countdown_id:
            self.root.after_cancel(self._countdown_id)
            self._countdown_id = None
        # Restore duration entry
        self.dur_var.set("600")
        self.dur_entry.config(fg=WHITE)
        # Re-enable AI button
        if hasattr(self, "ai_vb_run_btn"):
            self.ai_vb_run_btn.config(
                state="normal", bg=ACCENT, fg="#000",
                text="\u25b6 Run AI Analysis")
        # Cancel auto scans
        if hasattr(self, "_chatter_auto_id") and self._chatter_auto_id:
            self.root.after_cancel(self._chatter_auto_id)
            self._chatter_auto_id = None
        if hasattr(self, "_words_auto_id") and self._words_auto_id:
            self.root.after_cancel(self._words_auto_id)
            self._words_auto_id = None
        if hasattr(self, "_chart_auto_id") and self._chart_auto_id:
            self.root.after_cancel(self._chart_auto_id)
            self._chart_auto_id = None
        self.engine.stop()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_var.set("Stopped. Refresh tabs to see final stats.")
        self._refresh_chatters()
        self._refresh_words()
        self._refresh_chart()
        self._generate_report()

    def _on_connected(self):
        slug = self.channel["slug"] if self.channel else "?"
        name = self.channel.get("display_name", slug) if self.channel else slug
        self.status_var.set(f"✓ Connected — monitoring kick.com/{slug}")
        self.root.after(30000, self._poll_channel)

        # Start auto scans on connect
        if hasattr(self, "chatter_auto_var") and self.chatter_auto_var.get():
            self._chatter_auto_scan()
        if hasattr(self, "words_auto_refresh_var") and self.words_auto_refresh_var.get():
            self._words_schedule_refresh()
        if hasattr(self, "chart_auto_var") and self.chart_auto_var.get():
            self._chart_auto_scan()

        # Auto-load streamer info
        if self.channel:
            slug = self.channel.get("slug", "")
            if slug and hasattr(self, "info_slug_var"):
                self.info_slug_var.set(slug)
                self.root.after(1000, self._load_streamer_info)

        # Update the tab label in the main notebook to show streamer name
        try:
            live = "🔴" if self.channel and self.channel.get("is_live") else "📺"
            for tab_id in self.app.main_nb.tabs():
                frame = self.app.main_nb.nametowidget(tab_id)
                for widget in frame.winfo_children():
                    if hasattr(widget, '_session_owner') and widget._session_owner is self:
                        self.app.main_nb.tab(tab_id, text=f"{live} {name}")
                        return
            selected = self.app.main_nb.select()
            if selected:
                self.app.main_nb.tab(selected, text=f"{live} {name}")
        except Exception:
            pass


    def _on_error(self, msg):
        # Don't show a dialog for transient WebSocket errors — they auto-reconnect
        transient = any(c in str(msg) for c in
            ["4200", "1001", "1006", "1011",
             "ConnectionClosed", "connection closed",
             "no close frame", "timed out", "reconnect"])
        if transient:
            self.status_var.set(f"⚠ Connection issue — reconnecting... ({str(msg)[:60]})")
            return
        # Only show dialog for real non-recoverable errors
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_var.set(f"Error: {str(msg)[:80]}")
        messagebox.showerror("Error", msg)


    def _update_channel_panel(self):
        ch = self.channel
        self.lbl_name.set(ch["display_name"])
        self.lbl_live.set("🔴 LIVE" if ch["is_live"] else "⬛ OFFLINE")
        self.lbl_viewers.set(f"{ch['viewer_count']:,}")
        self.lbl_category.set(ch["category"])
        self.lbl_duration.set(ch["duration"])
        self.lbl_followers.set(f"{ch['followers']:,}")
        self.lbl_title.set(ch["stream_title"][:30])
        self.lbl_slow.set("On" if ch["slow_mode"] else "Off")
        self.lbl_sub.set("On" if ch["sub_mode"] else "Off")
        self.lbl_emote.set("On" if ch["emote_mode"] else "Off")
        self.hist_slug_var.set(ch["slug"])
        self.info_slug_var.set(ch["slug"])
        # Show last updated time so user knows data is live
        now = datetime.now().strftime("%H:%M:%S")
        self.lbl_ch_updated.config(text=f"↻ {now}")


    def _poll_channel(self):
        """
        Poll the Kick API every 60s to keep channel/chatroom panel data fresh.
        Updates: viewers, followers, live status, title, category,
                 slow mode, sub-only mode, emote-only mode.
        Runs in a background thread while monitoring is active.
        """
        if not self.engine.running or not self.channel:
            # Stop polling when not monitoring
            self.root.after(30000, self._poll_channel)
            return

        slug = self.channel.get("slug","")
        if not slug:
            self.root.after(30000, self._poll_channel)
            return

        def fetch_and_update():
            raw = get_channel(slug)
            if not raw:
                self.root.after(30000, self._poll_channel)
                return
            ch = parse_channel(raw)
            if not ch:
                self.root.after(30000, self._poll_channel)
                return

            # Preserve started_at from original fetch for accurate live timer
            if self.channel.get("started_at") and not ch.get("started_at"):
                ch["started_at"] = self.channel["started_at"]

            self.channel = ch

            # Update viewer history for viewbot spike detection
            self._viewer_history.append((time.time(), ch["viewer_count"]))

            self.root.after(0, self._update_channel_panel)
            self.root.after(30000, self._poll_channel)

        threading.Thread(target=fetch_and_update, daemon=True).start()

    # ── Viewbot Detection ─────────────────────────────────────

    def _calc_viewbot_score(self):
        """
        Calculate a viewbot suspicion score 0-100.

        Signals:
          Viewer spike/drop  — 40pts  (sudden jump or drop)
          Chat/viewer ratio  — 30pts  (< 1% is very suspicious)
          Msgs/min per 1k vw — 20pts  (< 5 is suspicious)
          Bot ratio in chat  — 10pts
          Combined multiplier — spike + low ratio together = bonus pts

        Returns (score, verdict, breakdown_dict)
        """
        if not self.channel or not self.engine.start_time:
            return 0, "—", {}

        viewers = self.channel.get("viewer_count", 0)
        if viewers < 10:
            return 0, "Not enough data", {}

        elapsed    = time.time() - self.engine.start_time
        total_msgs = len(self.engine.messages)
        chatters   = len(self.engine.user_msgs)
        mpm        = (total_msgs / (elapsed / 60)) if elapsed > 60 else 0
        score      = 0
        breakdown  = {}

        # ── Signal 1: Viewer spike or drop ────────────────────
        now = time.time()
        self._viewer_history.append((now, viewers))
        self._viewer_history = [(t, v) for t, v in self._viewer_history
                                if now - t <= 900]

        spike_pct = 0
        drop_pct  = 0
        spike_pts = 0

        if len(self._viewer_history) >= 2:
            for i in range(len(self._viewer_history)):
                for j in range(i+1, len(self._viewer_history)):
                    t1, v1 = self._viewer_history[i]
                    t2, v2 = self._viewer_history[j]
                    if t2 - t1 <= 180 and v1 > 50:
                        jump = (v2 - v1) / v1 * 100
                        if jump > spike_pct:
                            spike_pct = jump
                        if jump < drop_pct:
                            drop_pct = jump  # negative = drop

            # Score spike
            if spike_pct >= 300:
                spike_pts = 40
            elif spike_pct >= 200:
                spike_pts = 35
            elif spike_pct >= 100:
                spike_pts = 28
            elif spike_pct >= 75:
                spike_pts = 20
            elif spike_pct >= 50:
                spike_pts = 12
            elif spike_pct >= 25:
                spike_pts = 5

            # Also score sudden drops (bots leaving)
            drop_abs = abs(drop_pct)
            if drop_abs >= 200:
                spike_pts = max(spike_pts, 35)
            elif drop_abs >= 100:
                spike_pts = max(spike_pts, 25)
            elif drop_abs >= 50:
                spike_pts = max(spike_pts, 12)

        score += spike_pts
        breakdown["spike"] = (spike_pct, spike_pts)
        breakdown["drop"]  = (drop_pct, 0)

        # ── Signal 2: Chat/viewer ratio ───────────────────────
        chat_ratio = (chatters / viewers * 100) if viewers else 0
        if chat_ratio < 0.3:
            pts = 30
        elif chat_ratio < 0.7:
            pts = 22
        elif chat_ratio < 1.0:
            pts = 14
        elif chat_ratio < 2.0:
            pts = 5
        else:
            pts = 0
        score += pts
        breakdown["chat_ratio"] = (chat_ratio, pts)

        # ── Signal 3: Msgs/min per 1000 viewers ───────────────
        mpm_per_1k = (mpm / viewers * 1000) if viewers else 0
        if mpm_per_1k < 1:
            pts = 20
        elif mpm_per_1k < 3:
            pts = 14
        elif mpm_per_1k < 5:
            pts = 8
        elif mpm_per_1k < 10:
            pts = 3
        else:
            pts = 0
        score += pts
        breakdown["mpm_per_1k"] = (mpm_per_1k, pts)

        # ── Signal 4: Bot ratio in chat ───────────────────────
        if chatters > 0:
            bot_count = sum(1 for u in self.engine.user_msgs
                            if BOT_NAMES.search(u))
            likely_bot_count = sum(
                1 for u, msgs in self.engine.user_msgs.items()
                if not BOT_NAMES.search(u)
                and len(msgs) >= 5
                and len(msgs) / max(
                    self.engine.user_last.get(u,0) -
                    self.engine.user_first.get(u,0), 1
                ) >= 2.0
            )
            bot_ratio = (bot_count + likely_bot_count) / chatters * 100
            if bot_ratio > 30:   pts = 10
            elif bot_ratio > 15: pts = 6
            elif bot_ratio > 5:  pts = 2
            else:                pts = 0
        else:
            bot_ratio = 0
            pts = 0
        score += pts
        breakdown["bot_ratio"] = (bot_ratio, pts)

        # ── Signal 5: Combined multiplier ─────────────────────
        # Spike + low chat ratio together = strongest viewbot signal.
        # A real stream gaining viewers organically would have MORE chat,
        # not less. If viewers spike but chat ratio drops or stays low,
        # that's almost certainly viewbotting.
        bonus = 0
        if spike_pct >= 50 and chat_ratio < 2.0:
            # The bigger the spike AND the lower the ratio, the higher the bonus
            ratio_factor = max(0, (2.0 - chat_ratio) / 2.0)   # 0-1
            spike_factor = min(spike_pct / 300, 1.0)           # 0-1
            bonus = int(25 * ratio_factor * spike_factor)
            score += bonus
        breakdown["combined_bonus"] = bonus

        # Cap at 100
        score = min(score, 100)

        # ── Verdict ───────────────────────────────────────────
        if elapsed < 60:
            verdict = "Warming up..."
        elif score >= 70:
            verdict = "🔴 HIGH RISK"
        elif score >= 45:
            verdict = "🟡 SUSPICIOUS"
        elif score >= 20:
            verdict = "🟢 LOW RISK"
        else:
            verdict = "✅ CLEAN"

        return score, verdict, breakdown

        # ── Verdict ───────────────────────────────────────────
        if elapsed < 60:
            verdict = "Warming up..."
        elif score >= 70:
            verdict = "🔴 HIGH RISK"
        elif score >= 45:
            verdict = "🟡 SUSPICIOUS"
        elif score >= 20:
            verdict = "🟢 LOW RISK"
        else:
            verdict = "✅ CLEAN"

        return score, verdict, breakdown

    # ── Tick (1s update loop) ─────────────────────────────────

    def _tick(self):
        if self.engine.running and self.engine.start_time:
            elapsed = time.time() - self.engine.start_time
            h, r = divmod(int(elapsed), 3600)
            m, s = divmod(r, 60)
            self.lbl_elapsed.set(f"{h:02d}:{m:02d}:{s:02d}")

            # Update live duration from actual stream start time
            if self.channel and self.channel.get("started_at"):
                lf = calc_live_for(
                    self.channel["started_at"].isoformat()
                    if hasattr(self.channel["started_at"], "isoformat")
                    else str(self.channel["started_at"])
                )
                if lf != "N/A":
                    self.lbl_duration.set(lf)

            total  = len(self.engine.messages)
            mpm    = round(total / (elapsed / 60), 1) if elapsed > 0 else 0
            subs   = sum(1 for e in self.engine.events if e["kind"] == "subscription")
            gifts  = sum(1 for e in self.engine.events if e["kind"] == "gift")
            raids  = sum(1 for e in self.engine.events if e["kind"] == "raid")

            # Fast stats — no classify needed, just raw counts
            all_chatters = len(self.engine.user_msgs)
            # Active = 5+ messages, not a known bot name
            active_count = sum(
                1 for u, msgs in self.engine.user_msgs.items()
                if len(msgs) >= 5 and not BOT_NAMES.search(u)
            )
            # Known bots from name pattern only
            bot_count = sum(1 for u in self.engine.user_msgs
                            if BOT_NAMES.search(u))

            self.lbl_msgs.set(str(total))
            self.lbl_chatters.set(str(all_chatters))
            self.lbl_mpm.set(str(mpm))
            self.lbl_bots.set(str(bot_count))
            self.lbl_active.set(str(active_count))
            self.lbl_subs.set(str(subs))
            self.lbl_gifts.set(str(gifts))
            self.lbl_raids.set(str(raids))
            self._draw_mini_bar()

            # Update viewbot detector every 5s — skip if AI verdict is locked
            if int(elapsed) % 5 == 0 and not self._ai_verdict_locked:
                score, verdict, bd = self._calc_viewbot_score()
                if score > 0 or verdict not in ("—", "Warming up..."):
                    viewers    = self.channel.get("viewer_count", 0) if self.channel else 0
                    chatters_n = len(self.engine.user_msgs)
                    ratio      = (chatters_n / viewers * 100) if viewers else 0
                    mpm_1k     = bd.get("mpm_per_1k",(0,0))[0]
                    spike      = bd.get("spike",(0,0))[0]
                    self.lbl_vbot_score.set(f"{score}/100")
                    self.lbl_vbot_verdict.set(verdict)
                    self.lbl_vbot_ratio.set(f"{ratio:.2f}%")
                    self.lbl_vbot_mpm.set(f"{mpm_1k:.1f}")
                    self.lbl_vbot_spike.set(f"+{spike:.0f}%" if spike > 0 else "None")

        self.root.after(1000, self._tick)

# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════



# ══════════════════════════════════════════════════════════════
#  MAIN APP — manages sessions + global tabs
# ══════════════════════════════════════════════════════════════

class KickGUI:

    def _multi_refresh_one(self, slug):
        def fetch():
            data = get_channel_poll(slug)
            if data:
                ch = self._multi_channels.get(slug, {})
                prev = ch.get("followers", 0)
                if ch.get("followers_start", 0) == 0:
                    data["followers_start"] = data["followers"]
                else:
                    data["followers_start"] = ch["followers_start"]
                data["followers_prev"] = prev
                self._multi_channels[slug] = data
                if self.multi_track_var.get():
                    self._multi_history[slug].append((time.time(), data["followers"]))
            else:
                if slug in self._multi_channels:
                    self._multi_channels[slug]["status"] = "error"
            self.root.after(0, self._multi_render)
        threading.Thread(target=fetch, daemon=True).start()


    def _load_top100(self):
        self.top100_status.set("Loading top streamers...")
        self._top100_raw = []
        threading.Thread(target=self._fetch_top100, daemon=True).start()


    def _export_top100_csv(self):
        if not self._top100_raw:
            messagebox.showinfo("No Data", "Load Top 100 first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files","*.csv")],
            initialfile=f"kick_top100_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
        if not path: return
        headers = ["Rank","Username","Viewers","Category","Title",
                   "Live For","Followers","Verified","Mature","Slug"]
        rows = [(r["rank"],r["name"],r["viewers"],r["category"],r["title"],
                 r["live_for"],r["followers"],r["verified"],r["mature"],r["slug"])
                for r in self._top100_raw]
        export_csv(path, headers, rows)
        messagebox.showinfo("Exported", f"Saved {len(rows)} rows to:\n{path}")

    # ══════════════════════════════════════════════════════════
    #  TAB: MULTI-CHANNEL MONITOR
    # ══════════════════════════════════════════════════════════

    def _multi_save(self):
        """Save the current channel slug list to a local JSON file."""
        try:
            slugs = list(self._multi_channels.keys())
            with open(self._multi_save_path, "w", encoding="utf-8") as f:
                json.dump({"channels": slugs}, f, indent=2)
        except Exception:
            pass


    def _multi_tick(self):
        """Auto-refresh multi-channel list every 30s."""
        if self.multi_auto_var.get() and self._multi_channels:
            now = time.time()
            if now - self._multi_last_refresh >= 30:
                self._multi_last_refresh = now
                for slug in list(self._multi_channels.keys()):
                    self._multi_refresh_one(slug)
        self.root.after(30000, self._multi_tick)


    def _browse_sched_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.sched_folder_var.set(folder)

    # ══════════════════════════════════════════════════════════
    #  CSV EXPORT helpers (chatters + VODs + clips)
    # ══════════════════════════════════════════════════════════
    def _build_ui(self):
        self._build_topbar()
        self._build_main_notebook()

    def _setup_window(self):
        self.root.title("Kick.com Streamer Analytics")
        self.root.configure(bg=BG)
        self.root.geometry("1440x860")
        self.root.minsize(1100, 700)
        try:
            self.root.state("zoomed")
        except:
            pass

    def _multi_add(self):
        slug = self.multi_slug_var.get().strip().lower()
        if not slug: return
        if slug in self._multi_channels:
            messagebox.showinfo("Already added", f"{slug} is already in the list.")
            return
        self._multi_channels[slug] = {
            "slug": slug, "status": "...", "viewers": 0,
            "category": "...", "followers": 0, "followers_start": 0,
            "last_updated": "Never"
        }
        self.multi_slug_var.set("")
        self._multi_save()
        self._multi_refresh_one(slug)


    def _sched_save_report(self):
        folder = self.sched_folder_var.get().strip()
        # Get active session for report generation
        session = self._get_active_session()
        if not session:
            self.sched_status_var.set("No active session")
            return
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as e:
            self.sched_status_var.set(f"⚠ Folder error: {e}")
            return
        text = session._generate_report(silent=True)
        if not text:
            self.sched_status_var.set("⚠ No report data yet — start monitoring first")
            return
        slug = session.channel["slug"] if session.channel else "kick"
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(folder, f"auto_report_{slug}_{ts}.txt")
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            self.sched_status_var.set(f"✓ Saved {datetime.now().strftime('%H:%M:%S')} → {os.path.basename(path)}")
        except Exception as e:
            self.sched_status_var.set(f"⚠ Save failed: {e}")


    def _top100_open_channel(self, event):
        sel = self.top100_tree.selection()
        if not sel: return
        vals = self.top100_tree.item(sel[0], "values")
        if not vals: return
        name = vals[1].replace("✓ ","").strip()
        found = next((r for r in self._top100_raw if r["name"] == name), None)
        if found:
            # Open in a new session tab
            session = self._add_streamer_tab(found["slug"])
            session._start()


    def _sort_top100(self, col):
        if self._top100_sort_col == col:
            self._top100_sort_rev = not self._top100_sort_rev
        else:
            self._top100_sort_col = col
            self._top100_sort_rev = True
        key_map = {"#":"rank","Streamer":"name","Viewers":"viewers",
                   "Category":"category","Followers":"followers","Language":"language"}
        key = key_map.get(col, "rank")
        sorted_data = sorted(self._top100_raw, key=lambda r: r.get(key, ""),
                             reverse=self._top100_sort_rev)
        self._render_top100(sorted_data)


    def _style_tree(self, tree):
        style = ttk.Style()
        style.configure("Treeview",
                        background=BG2, foreground=WHITE,
                        fieldbackground=BG2, rowheight=24,
                        font=("Segoe UI",10))
        style.configure("Treeview.Heading",
                        background=BG3, foreground=ACCENT,
                        font=("Segoe UI",10,"bold"))
        style.map("Treeview", background=[("selected", BG3)])


    def _rename_tab(self, event):
        """Double-click a tab to rename it."""
        try:
            idx = self.main_nb.index(f"@{event.x},{event.y}")
            current = self.main_nb.tab(idx, "text")
            # Simple rename dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Rename Tab")
            dialog.configure(bg=BG2)
            dialog.geometry("300x100")
            dialog.resizable(False, False)
            dialog.transient(self.root)
            dialog.grab_set()
            tk.Label(dialog, text="Tab name:", bg=BG2, fg=WHITE,
                     font=("Segoe UI",10)).pack(pady=(12,4))
            var = tk.StringVar(value=current.replace("📺 ",""))
            e = tk.Entry(dialog, textvariable=var, bg=BG3, fg=WHITE,
                         insertbackground=WHITE, font=("Segoe UI",11),
                         relief="flat", width=24)
            e.pack()
            e.select_range(0,"end")
            e.focus_set()
            def apply(_=None):
                new_name = var.get().strip() or current
                self.main_nb.tab(idx, text=f"📺 {new_name}")
                dialog.destroy()
            e.bind("<Return>", apply)
            tk.Button(dialog, text="Rename", command=apply,
                      bg=ACCENT, fg="#000", font=("Segoe UI",9,"bold"),
                      relief="flat", padx=10).pack(pady=8)
        except Exception:
            pass

    def _build_top100_tab(self):
        f = tk.Frame(self.main_nb, bg=BG)
        self.main_nb.add(f, text="🏅 Top 100")

        # ── Toolbar row 1: controls ────────────────────────────
        tb = tk.Frame(f, bg=BG2)
        tb.pack(fill="x")

        tk.Button(tb, text="🔄 Refresh Now", command=self._load_top100,
                  bg=ACCENT, fg="#000", font=("Segoe UI",10,"bold"),
                  relief="flat", padx=12, pady=4, cursor="hand2").pack(side="left", padx=8, pady=6)

        tk.Label(tb, text="Category filter:", bg=BG2, fg=WHITE,
                 font=("Segoe UI",9)).pack(side="left", padx=(8,4))
        self.top100_cat_var = tk.StringVar(value="All")
        self.top100_cat_entry = tk.Entry(tb, textvariable=self.top100_cat_var, width=16,
                                          bg=BG3, fg=WHITE, insertbackground=WHITE,
                                          font=("Segoe UI",10), relief="flat", bd=3)
        self.top100_cat_entry.pack(side="left", pady=6)
        self.top100_cat_entry.bind("<Return>", lambda _: self._filter_top100())

        tk.Button(tb, text="Filter", command=self._filter_top100,
                  bg=BG3, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=8, pady=4).pack(side="left", padx=4)

        tk.Label(tb, text="Time range:", bg=BG2, fg=WHITE,
                 font=("Segoe UI",9)).pack(side="left", padx=(12,4))
        self.top100_range_var = tk.StringVar(value="Live Now")
        for opt in ["Live Now", "Today", "This Week", "This Month"]:
            tk.Radiobutton(tb, text=opt, variable=self.top100_range_var,
                           value=opt, bg=BG2, fg=WHITE, selectcolor=BG3,
                           font=("Segoe UI",9),
                           command=self._load_top100).pack(side="left", padx=3)

        tk.Button(tb, text="💾 Export CSV", command=self._export_top100_csv,
                  bg=BG3, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=8, pady=4).pack(side="right", padx=8)

        # ── Toolbar row 2: region filter ───────────────────────
        tb2 = tk.Frame(f, bg=BG3)
        tb2.pack(fill="x")

        tk.Label(tb2, text="  Region:", bg=BG3, fg=GREY,
                 font=("Segoe UI",9,"bold")).pack(side="left", padx=(8,6), pady=4)

        self.top100_region_var = tk.StringVar(value="Global")

        regions = [
            ("🌍 Global",           "Global"),
            ("🇺🇸 English / USA",    "English"),
            ("🇪🇸 Spanish / LATAM",  "Spanish"),
            ("🇸🇦 Arabic",           "Arabic"),
            ("🇹🇷 Turkish",          "Turkish"),
            ("🇩🇪 German",           "German"),
            ("🇯🇵 Japanese",         "Japanese"),
            ("🇵🇹 Portuguese",       "Portuguese"),
            ("🇫🇷 French",           "French"),
        ]
        for label, val in regions:
            tk.Radiobutton(tb2, text=label, variable=self.top100_region_var,
                           value=val, bg=BG3, fg=WHITE, selectcolor=BG2,
                           activebackground=BG3, activeforeground=ACCENT,
                           font=("Segoe UI",9),
                           command=self._filter_top100).pack(side="left", padx=4, pady=3)

        tk.Label(tb2, text="  (filters by stream language after loading)",
                 bg=BG3, fg=GREY, font=("Segoe UI",8)).pack(side="right", padx=8)

        # ── Status bar ─────────────────────────────────────────
        self.top100_status = tk.StringVar(value="Click Refresh to load top streamers")
        tk.Label(f, textvariable=self.top100_status, bg=BG, fg=GREY,
                 font=("Segoe UI",9)).pack(anchor="w", padx=8, pady=2)

        # ── Treeview ───────────────────────────────────────────
        cols = ("#", "Streamer", "Viewers", "Language", "Category", "Title",
                "Live For", "Followers", "Verified")
        self.top100_tree = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
        widths = [40, 150, 80, 90, 120, 240, 80, 90, 70]
        for col, w in zip(cols, widths):
            self.top100_tree.heading(col, text=col,
                command=lambda c=col: self._sort_top100(c))
            self.top100_tree.column(col, width=w, anchor="w")
        self._style_tree(self.top100_tree)
        self.top100_tree.tag_configure("verified", foreground=ACCENT)
        self.top100_tree.tag_configure("normal",   foreground=WHITE)
        self.top100_tree.tag_configure("offline",  foreground=GREY)

        sb = ttk.Scrollbar(f, orient="vertical", command=self.top100_tree.yview)
        self.top100_tree.configure(yscroll=sb.set)
        self.top100_tree.pack(side="left", fill="both", expand=True, padx=(4,0), pady=4)
        sb.pack(side="right", fill="y", pady=4, padx=(0,4))

        self.top100_tree.bind("<Double-1>", self._top100_open_channel)
        self.top100_tree.bind("<<TreeviewSelect>>", self._top100_show_detail)

        self._top100_raw      = []
        self._top100_sort_col = "#"
        self._top100_sort_rev = False

        # ── Detail panel ───────────────────────────────────────
        det = tk.Frame(f, bg=BG2, height=80)
        det.pack(fill="x", padx=4, pady=(0,4))
        det.pack_propagate(False)
        tk.Label(det, text="Select a streamer for details  |  Double-click to open in Live Monitor",
                 bg=BG2, fg=GREY, font=("Segoe UI",9)).pack(anchor="w", padx=10, pady=(6,2))
        self.top100_detail_var = tk.StringVar()
        tk.Label(det, textvariable=self.top100_detail_var, bg=BG2, fg=WHITE,
                 font=("Segoe UI",10), justify="left").pack(anchor="w", padx=10)


    def _add_streamer_tab(self, slug=""):
        """Create a new streamer session tab."""
        label = slug if slug else f"Stream {len(self.sessions)+1}"
        frame = tk.Frame(self.main_nb, bg=BG)
        self.main_nb.add(frame, text=f"📺 {label}")

        idx = len(self.sessions)
        session = StreamerSession(frame, self.root, self)
        tag_frame = tk.Frame(frame, width=0, height=0)
        tag_frame._session_owner = session
        tag_frame.place(x=0, y=0)
        if slug:
            session.slug_var.set(slug)
        self.sessions.append(session)
        self.main_nb.select(frame)
        return session

    def _multi_export_csv(self):
        if not self._multi_channels:
            messagebox.showinfo("No Data", "Add channels first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files","*.csv")],
            initialfile=f"kick_multi_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
        if not path: return
        headers = ["Slug","Status","Viewers","Category","Followers","Follower Change"]
        rows = []
        for slug, ch in self._multi_channels.items():
            delta = ch.get("followers",0) - ch.get("followers_start",0)
            rows.append((slug,
                         "LIVE" if ch.get("is_live") else "Offline",
                         ch.get("viewers",0),
                         ch.get("category",""),
                         ch.get("followers",0),
                         delta))
        export_csv(path, headers, rows)
        messagebox.showinfo("Exported", f"Saved to:\n{path}")


    def _fetch_top100(self):
        """
        Fetch top 100 live streamers from kickstats.com/api/livestreams?limit=100
        For time ranges (no historical API available), shows all channels
        sorted by followers using the known slug list + Kick API.
        """
        import urllib.request as _ur
        import ssl as _ssl
        import json as _json

        mode = self.top100_range_var.get()

        KICKSTATS_HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.kickstats.com/channels",
        }

        def fetch_kickstats(url):
            """Fetch kickstats.com API — works with plain urllib, no auth needed."""
            try:
                if HAS_CURL_CFFI:
                    for imp in ["chrome124", "chrome131", "safari17_0"]:
                        try:
                            r = cffi_requests.get(url, headers=KICKSTATS_HEADERS,
                                                  impersonate=imp, timeout=15)
                            if r.status_code == 200:
                                return r.json()
                        except: continue
                req = _ur.Request(url, headers=KICKSTATS_HEADERS)
                ctx = _ssl.create_default_context()
                with _ur.urlopen(req, context=ctx, timeout=15) as resp:
                    return _json.loads(resp.read().decode("utf-8", errors="ignore"))
            except Exception as e:
                return None

        # ── TOP 100 SLUGS for time-range fallback ─────────────
        TOP_SLUGS = [
            "bakaprase","korekore_ch","absi","eray","zonagemelosoficial",
            "firas","maddyson","hype","ilyaselmaliki","aidavictoriamerlano",
            "jukes","jahrein","rempledur","xqc","n3on","adinross",
            "trainwreckstv","amouranth","nickmercs","timthetatman","cloakzy",
            "summit1g","sodapoppin","shroud","lirik","moonmoon","jynxzi",
            "stewie2k","tarik","fextralife","nadeshot","forsen","chickenandy",
            "sketch","blaustoise","miles","nymn","saqib","elajjaz","ramee",
            "cyr","penta","dundee","poke","zerkaa","ksi","miniminter",
            "westcol","elmariana","juansguarnizo","ibai","alexby11","auronplay",
            "rubius","lolito","agustin51","perxitaa","thegrefg","quackity",
            "mowit","guanyar","theranking","spreen","luzu","coscu","reven",
            "maherco","malistroy","hadesost","tortur","pasha","korekore",
            "trymacs","papaplatte","kev1n","ohnepixel","s1mple","paszabiceps",
            "clavicular","clix","kaicenat","agent00","ddg","ranboo","tubbo",
            "philza","jokerd","buddha","juicetra","viking","erayrust",
        ]

        def parse_kickstats_stream(s, rank):
            ch  = s.get("channel", {}) or {}
            cat = s.get("category", {}) or {}
            return {
                "rank":      rank,
                "slug":      ch.get("slug", "?"),
                "name":      ch.get("username", ch.get("slug","?")),
                "viewers":   s.get("viewer_count", 0),
                "is_live":   True,
                "language":  "N/A",
                "category":  cat.get("name", "N/A"),
                "title":     (s.get("title","") or s.get("session_title",""))[:60],
                "live_for":  "N/A",
                "followers": 0,
                "verified":  False,
                "mature":    False,
                "started":   "",
            }

        def enrich_entries(entries, limit=100):
            """Add followers, verified, live_for, language from Kick API."""
            slugs    = [e["slug"] for e in entries[:limit]]
            api_data = {}
            lock     = threading.Lock()

            def enrich_one(slug):
                d = get_channel(slug)
                if d:
                    with lock:
                        api_data[slug] = d

            threads = [threading.Thread(target=enrich_one, args=(s,), daemon=True)
                       for s in slugs]
            for t in threads: t.start()
            for t in threads: t.join()

            for e in entries:
                slug = e["slug"]
                if slug not in api_data: continue
                d    = api_data[slug]
                user = d.get("user", {}) or {}
                ls   = d.get("livestream") or {}
                cats = ls.get("categories", []) if ls else []
                e["followers"] = (d.get("followersCount") or d.get("followers_count")
                               or d.get("followers") or 0)
                e["verified"]  = d.get("verified", False)
                e["mature"]    = d.get("is_mature", False)
                e["name"]      = user.get("username", e["name"])
                e["language"]  = ls.get("language", "N/A") if ls else "N/A"
                if ls:
                    e["is_live"] = True
                    if cats:
                        e["category"] = cats[0].get("name", e["category"])
                    e["viewers"]  = ls.get("viewer_count", e["viewers"])
                    e["title"]    = (ls.get("session_title","") or e["title"])[:60]
                    started = ls.get("start_time","") or ls.get("created_at","")
                    lf = calc_live_for(started)
                    if lf != "N/A":
                        e["live_for"] = lf

        # ── LIVE NOW: use kickstats.com/api/livestreams?limit=100 ──
        if mode == "Live Now":
            self.root.after(0, lambda: self.top100_status.set(
                "Fetching top 100 live streams from kickstats.com..."))

            data = fetch_kickstats(
                "https://www.kickstats.com/api/livestreams?limit=100")

            entries = []
            if data:
                streams = (data.get("data", {}) or {}).get("livestreams", [])
                if not streams and isinstance(data, list):
                    streams = data
                entries = [parse_kickstats_stream(s, i+1)
                           for i, s in enumerate(streams)]

            if entries:
                n = len(entries)
                self.root.after(0, lambda n=n: self.top100_status.set(
                    f"Got {n} live streamers — enriching all with Kick data (language detection)..."))
                enrich_entries(entries, limit=100)
            else:
                # Fallback: individual Kick API fetches
                self.root.after(0, lambda: self.top100_status.set(
                    "kickstats.com unavailable — fetching from Kick API..."))
                self._fetch_top100_fallback(TOP_SLUGS, mode)
                return

        # ── TIME RANGES: Kick API individual fetches sorted by followers ──
        else:
            label = {"Today":"24h","This Week":"7d","This Month":"30d"}.get(mode, mode)
            self.root.after(0, lambda label=label: self.top100_status.set(
                f"Fetching {label} top channels (sorted by followers)..."))

            done_c = [0]
            results = {}
            lock2   = threading.Lock()
            seen, slugs = set(), []
            for s in TOP_SLUGS:
                if s not in seen: seen.add(s); slugs.append(s)

            def fetch_one(slug):
                d = get_channel(slug)
                with lock2:
                    done_c[0] += 1
                    if done_c[0] % 15 == 0 or done_c[0] == len(slugs):
                        dc = done_c[0]
                        self.root.after(0, lambda dc=dc: self.top100_status.set(
                            f"Fetching channels... {dc}/{len(slugs)}"))
                    if d: results[slug] = d

            threads = [threading.Thread(target=fetch_one, args=(s,), daemon=True)
                       for s in slugs]
            for t in threads: t.start()
            for t in threads: t.join()

            all_d = list(results.values())
            all_d.sort(key=lambda d: (
                bool(d.get("livestream")),
                d.get("followersCount") or d.get("followers_count") or
                d.get("followers") or 0
            ), reverse=True)

            entries = []
            for i, d in enumerate(all_d):
                user = d.get("user",{}) or {}
                ls   = d.get("livestream") or {}
                cats = ls.get("categories",[]) if ls else []
                cat  = cats[0].get("name","?") if cats else "N/A"
                flw  = (d.get("followersCount") or d.get("followers_count")
                     or d.get("followers") or 0)
                vw   = ls.get("viewer_count",0) if ls else 0
                started = (ls.get("start_time","") or ls.get("created_at","")) if ls else ""
                lf = calc_live_for(started) if started else "N/A"
                entries.append({
                    "rank": i+1, "slug": d.get("slug","?"),
                    "name": user.get("username", d.get("slug","?")),
                    "viewers": vw, "is_live": bool(ls), "category": cat,
                    "title": (ls.get("session_title","") or "")[:60] if ls else "",
                    "live_for": lf, "followers": flw,
                    "verified": d.get("verified", False),
                    "mature": d.get("is_mature", False), "started": started,
                })

        if not entries:
            self.root.after(0, lambda: self.top100_status.set(
                "No data returned. Check internet connection and try again."))
            return

        self._top100_raw = entries
        self.root.after(0, self._render_top100)


    def _toggle_schedule(self):
        if self.sched_enabled.get():
            self._sched_stop.clear()
            self._sched_thread = threading.Thread(
                target=self._sched_loop, daemon=True)
            self._sched_thread.start()
            self.sched_status_var.set("⏰ Auto-report running...")
        else:
            self._sched_stop.set()
            self.sched_status_var.set("Auto-report disabled")


    def _build_multi_tab(self):
        f = tk.Frame(self.main_nb, bg=BG)
        self.main_nb.add(f, text="📡 Multi-Channel")

        # Top controls
        tb = tk.Frame(f, bg=BG2)
        tb.pack(fill="x")
        tk.Label(tb, text="Add streamer:", bg=BG2, fg=WHITE,
                 font=("Segoe UI",10)).pack(side="left", padx=(10,4), pady=6)
        self.multi_slug_var = tk.StringVar()
        e = tk.Entry(tb, textvariable=self.multi_slug_var, width=18,
                     bg=BG3, fg=WHITE, insertbackground=WHITE,
                     font=("Segoe UI",10), relief="flat", bd=3)
        e.pack(side="left", pady=6)
        e.bind("<Return>", lambda _: self._multi_add())
        tk.Button(tb, text="➕ Add", command=self._multi_add,
                  bg=ACCENT, fg="#000", font=("Segoe UI",10,"bold"),
                  relief="flat", padx=10, pady=4).pack(side="left", padx=6)
        tk.Button(tb, text="🗑 Remove Selected", command=self._multi_remove,
                  bg=RED, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=8, pady=4).pack(side="left", padx=4)
        tk.Button(tb, text="✖ Remove All", command=self._multi_remove_all,
                  bg=RED, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=8, pady=4).pack(side="left", padx=4)
        tk.Button(tb, text="💾 Export CSV", command=self._multi_export_csv,
                  bg=BG3, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=8, pady=4).pack(side="right", padx=8)

        self.multi_auto_var = tk.BooleanVar(value=True)
        tk.Checkbutton(tb, text="Auto-refresh (30s)", variable=self.multi_auto_var,
                       bg=BG2, fg=WHITE, selectcolor=BG3,
                       font=("Segoe UI",9)).pack(side="right", padx=8)

        # Follower tracker toggle
        self.multi_track_var = tk.BooleanVar(value=False)
        tk.Checkbutton(tb, text="Track followers", variable=self.multi_track_var,
                       bg=BG2, fg=WHITE, selectcolor=BG3,
                       font=("Segoe UI",9)).pack(side="right", padx=4)

        self.multi_status = tk.StringVar(value="Add streamers to monitor multiple channels at once")
        tk.Label(f, textvariable=self.multi_status, bg=BG, fg=GREY,
                 font=("Segoe UI",9)).pack(anchor="w", padx=8, pady=2)

        # Treeview
        cols = ("Streamer","Status","Viewers","Category","Followers","Δ Followers","Last Updated")
        self.multi_tree = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
        widths = [160, 80, 90, 150, 100, 100, 150]
        for col, w in zip(cols, widths):
            self.multi_tree.heading(col, text=col,
                command=lambda c=col: self._multi_sort(c))
            self.multi_tree.column(col, width=w, anchor="w")
        self._style_tree(self.multi_tree)
        self.multi_tree.tag_configure("live",    foreground=ACCENT)
        self.multi_tree.tag_configure("offline", foreground=GREY)
        self.multi_tree.tag_configure("error",   foreground=RED)
        self.multi_tree.bind("<Double-1>", self._multi_open)

        # Sort state — default to Status descending (LIVE first)
        self._multi_sort_col = "Status"
        self._multi_sort_rev = True

        sb = ttk.Scrollbar(f, orient="vertical", command=self.multi_tree.yview)
        self.multi_tree.configure(yscroll=sb.set)
        self.multi_tree.pack(side="left", fill="both", expand=True, padx=(4,0), pady=4)
        sb.pack(side="right", fill="y", pady=4, padx=(0,4))

        tk.Label(f, text="Double-click a channel to open it in Live Monitor",
                 bg=BG, fg=GREY, font=("Segoe UI",8)).pack(pady=(0,4))

        # Scheduled report controls
        sched_frame = tk.Frame(f, bg=BG2)
        sched_frame.pack(fill="x", padx=4, pady=(0,4))
        tk.Label(sched_frame, text="⏰ Auto-Report:", bg=BG2, fg=WHITE,
                 font=("Segoe UI",9,"bold")).pack(side="left", padx=8, pady=4)
        self.sched_enabled = tk.BooleanVar(value=False)
        tk.Checkbutton(sched_frame, text="Enable", variable=self.sched_enabled,
                       bg=BG2, fg=WHITE, selectcolor=BG3,
                       font=("Segoe UI",9),
                       command=self._toggle_schedule).pack(side="left")
        tk.Label(sched_frame, text="Every:", bg=BG2, fg=WHITE,
                 font=("Segoe UI",9)).pack(side="left", padx=(12,4))
        self.sched_interval_var = tk.StringVar(value="60")
        tk.Entry(sched_frame, textvariable=self.sched_interval_var, width=5,
                 bg=BG3, fg=WHITE, insertbackground=WHITE,
                 font=("Segoe UI",9), relief="flat").pack(side="left")
        tk.Label(sched_frame, text="minutes", bg=BG2, fg=WHITE,
                 font=("Segoe UI",9)).pack(side="left", padx=4)
        tk.Label(sched_frame, text="Save to:", bg=BG2, fg=WHITE,
                 font=("Segoe UI",9)).pack(side="left", padx=(12,4))
        self.sched_folder_var = tk.StringVar(value=os.path.expanduser("~\\Desktop"))
        tk.Entry(sched_frame, textvariable=self.sched_folder_var, width=28,
                 bg=BG3, fg=WHITE, insertbackground=WHITE,
                 font=("Segoe UI",9), relief="flat").pack(side="left")
        tk.Button(sched_frame, text="Browse", command=self._browse_sched_folder,
                  bg=BG3, fg=WHITE, font=("Segoe UI",9),
                  relief="flat", padx=6, pady=2).pack(side="left", padx=4)
        self.sched_status_var = tk.StringVar(value="Auto-report disabled")
        tk.Label(sched_frame, textvariable=self.sched_status_var, bg=BG2, fg=GREY,
                 font=("Segoe UI",9)).pack(side="left", padx=8)

        # Internal state
        self._multi_channels  = {}    # slug -> {followers_start, followers_now, ...}
        self._multi_history   = defaultdict(list)  # slug -> [(ts, followers)]
        self._sched_thread    = None
        self._sched_stop      = threading.Event()
        self._multi_last_refresh = 0

        # Persistence — save/load channel list from local JSON file
        self._multi_save_path = os.path.join(
            APP_DIR, "multi_channels.json")
        self._multi_load_saved()

        # Start auto-refresh loop
        self._multi_tick()


    def _build_main_notebook(self):
        """Top-level notebook: streamer sessions + global tabs."""
        style = ttk.Style()
        style.configure("Main.TNotebook",     background=BG,  borderwidth=0)
        style.configure("Main.TNotebook.Tab", background=BG2, foreground=GREY,
                        padding=[14,7], font=("Segoe UI",10,"bold"))
        style.map("Main.TNotebook.Tab",
                  background=[("selected", BG3)],
                  foreground=[("selected", ACCENT)])

        self.main_nb = ttk.Notebook(self.root, style="Main.TNotebook")
        self.main_nb.pack(fill="both", expand=True, padx=8, pady=(0,8))

        # Global tabs pinned left
        self._build_top100_tab()
        self._build_multi_tab()

        # Session tabs start after global tabs
        self._add_streamer_tab()

        # Double-click tab to rename
        self.main_nb.bind("<Double-Button-1>", self._rename_tab)

    def _filter_top100(self):
        """Apply both category text filter and region radio button."""
        cat    = self.top100_cat_var.get().strip().lower()
        region = self.top100_region_var.get()

        # Language mapping for region filter
        LANG_MAP = {
            "Global":          None,   # no filter
            "English":         ["english", "en"],
            "Spanish":         ["spanish", "es"],
            "Arabic":          ["arabic", "ar"],
            "Turkish":         ["turkish", "tr"],
            "German":          ["german", "de"],
            "Japanese":        ["japanese", "ja"],
            "Portuguese":      ["portuguese", "pt"],
            "French":          ["french", "fr"],
        }
        lang_keys = LANG_MAP.get(region)

        filtered = self._top100_raw
        # Category/name text filter
        if cat and cat != "all":
            filtered = [r for r in filtered
                        if cat in r["category"].lower() or cat in r["name"].lower()]
        # Region/language filter
        if lang_keys:
            filtered = [r for r in filtered
                        if r.get("language","").lower() in lang_keys
                        or r.get("language","N/A") == "N/A"]  # include unenriched entries

        # Re-rank after filtering
        for i, r in enumerate(filtered):
            r["rank"] = i + 1
        self._render_top100(filtered)


    def _sched_loop(self):
        while not self._sched_stop.is_set():
            try:
                mins = int(self.sched_interval_var.get())
            except:
                mins = 60
            self._sched_stop.wait(mins * 60)
            if self._sched_stop.is_set(): break
            self.root.after(0, self._sched_save_report)


    def _fetch_top100_fallback(self, slugs, mode):
        """Individual Kick API fetch fallback when kickstats.com is unavailable."""
        done_c  = [0]
        results = {}
        lock    = threading.Lock()
        seen, slugs_dedup = set(), []
        for s in slugs:
            if s not in seen: seen.add(s); slugs_dedup.append(s)

        def fetch_one(slug):
            d = get_channel(slug)
            with lock:
                done_c[0] += 1
                if d: results[slug] = d

        threads = [threading.Thread(target=fetch_one, args=(s,), daemon=True)
                   for s in slugs_dedup]
        for t in threads: t.start()
        for t in threads: t.join()

        all_d = list(results.values())
        if mode == "Live Now":
            all_d = [d for d in all_d if d.get("livestream")]
        all_d.sort(key=lambda d: (
            bool(d.get("livestream")),
            d.get("livestream",{}).get("viewer_count",0) if d.get("livestream") else
            (d.get("followersCount") or d.get("followers") or 0)
        ), reverse=True)

        entries = []
        for i, d in enumerate(all_d):
            user = d.get("user",{}) or {}
            ls   = d.get("livestream") or {}
            cats = ls.get("categories",[]) if ls else []
            cat  = cats[0].get("name","?") if cats else "N/A"
            flw  = d.get("followersCount") or d.get("followers_count") or d.get("followers") or 0
            vw   = ls.get("viewer_count",0) if ls else 0
            started = (ls.get("start_time","") or ls.get("created_at","")) if ls else ""
            lf = calc_live_for(started) if started else "N/A"
            entries.append({
                "rank": i+1, "slug": d.get("slug","?"),
                "name": user.get("username", d.get("slug","?")),
                "viewers": vw, "is_live": bool(ls), "language": ls.get("language","N/A") if ls else "N/A",
                "category": cat, "title": (ls.get("session_title","") or "")[:60] if ls else "",
                "live_for": lf, "followers": flw,
                "verified": d.get("verified",False),
                "mature": d.get("is_mature",False), "started": started,
            })

        self._top100_raw = entries
        self.root.after(0, self._render_top100)


    def _close_session(self, session):
        """Stop and remove a session tab by session object reference."""
        # Count live sessions (not None)
        live = [s for s in self.sessions if s is not None]
        if len(live) <= 1:
            messagebox.showinfo("Cannot Close",
                "Keep at least one streamer tab open. Add a new one first.")
            return

        # Stop the engine
        if session.engine.running:
            session.engine.stop()

        # Find which notebook tab owns this session by checking the tag frame
        for tab_id in self.main_nb.tabs():
            frame = self.main_nb.nametowidget(tab_id)
            for widget in frame.winfo_children():
                if getattr(widget, '_session_owner', None) is session:
                    self.main_nb.forget(tab_id)
                    # Remove from sessions list
                    self.sessions = [s for s in self.sessions if s is not session]
                    return

        # Fallback: remove by object reference only
        self.sessions = [s for s in self.sessions if s is not session]

    def _render_top100(self, data=None):
        rows = data if data is not None else self._top100_raw
        for row in self.top100_tree.get_children():
            self.top100_tree.delete(row)
        total_viewers = sum(r["viewers"] for r in rows)
        for r in rows:
            is_live = r.get("is_live", False)
            tag = "verified" if r["verified"] else ("offline" if not is_live else "normal")
            live_marker = "🔴 " if is_live else "⬛ "
            self.top100_tree.insert("", "end", tags=(tag,), values=(
                r["rank"],
                ("✓ " if r["verified"] else "") + r["name"],
                f"{r['viewers']:,}" if is_live else "—",
                r.get("language", "N/A"),
                r["category"],
                r["title"],
                r["live_for"],
                f"{r['followers']:,}",
                "Yes" if r["verified"] else "No",
            ))
        region = self.top100_region_var.get()
        region_label = f"  [{region}]" if region != "Global" else ""
        ts = datetime.now().strftime("%H:%M:%S")
        self.top100_status.set(
            f"✓ {len(rows)} streamers{region_label}  |  "
            f"{total_viewers:,} total viewers  |  Updated {ts}")


    def _get_active_session(self):
        """Return the StreamerSession for the currently selected tab, or None."""
        try:
            idx = self.main_nb.index(self.main_nb.select())
            if idx < len(self.sessions):
                return self.sessions[idx]
        except Exception:
            pass
        return None

    def _multi_open(self, event):
        sel = self.multi_tree.selection()
        if not sel: return
        vals = self.multi_tree.item(sel[0], "values")
        slug = vals[0].strip() if vals else ""
        if slug:
            session = self._add_streamer_tab(slug)
            session._start()


    def _multi_sort(self, col):
        """Handle column header click — toggle direction then apply."""
        if self._multi_sort_col == col:
            self._multi_sort_rev = not self._multi_sort_rev
        else:
            self._multi_sort_col = col
            self._multi_sort_rev = False
        self._multi_sort_apply()

    def _multi_sort_apply(self):
        """Apply current sort column and direction to the treeview."""
        col = self._multi_sort_col
        if not col:
            return

        # Update heading arrows
        arrow = " ▼" if self._multi_sort_rev else " ▲"
        cols = ("Streamer","Status","Viewers","Category",
                "Followers","Δ Followers","Last Updated")
        for c in cols:
            label = c + (arrow if c == col else "")
            self.multi_tree.heading(c, text=label,
                command=lambda c=c: self._multi_sort(c))

        # Sort rows
        rows = [(self.multi_tree.set(k, col), k)
                for k in self.multi_tree.get_children("")]

        def sort_key(item):
            val = item[0].replace(",","").replace("+","").replace("—","0").strip()
            try:
                return (0, float(val))
            except ValueError:
                return (1, val.lower())

        rows.sort(key=sort_key, reverse=self._multi_sort_rev)
        for i, (_, k) in enumerate(rows):
            self.multi_tree.move(k, "", i)

    def _multi_render(self):
        for row in self.multi_tree.get_children():
            self.multi_tree.delete(row)
        for slug, ch in self._multi_channels.items():
            is_live  = ch.get("is_live", False)
            status   = "🔴 LIVE" if is_live else "⬛ Offline"
            if ch.get("status") == "error": status = "❌ Error"
            tag      = "live" if is_live else ("error" if ch.get("status")=="error" else "offline")
            flw      = ch.get("followers", 0)
            flw_s    = ch.get("followers_start", flw)
            delta    = flw - flw_s
            delta_s  = f"+{delta:,}" if delta >= 0 else f"{delta:,}"
            ts       = ch.get("last_updated","Never")
            if isinstance(ts, float):
                ts = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            self.multi_tree.insert("","end", tags=(tag,), values=(
                slug,
                status,
                f"{ch.get('viewers',0):,}" if is_live else "—",
                ch.get("category","N/A"),
                f"{flw:,}",
                delta_s,
                ts,
            ))
        n_live = sum(1 for ch in self._multi_channels.values() if ch.get("is_live"))
        self.multi_status.set(
            f"{len(self._multi_channels)} channels tracked  |  {n_live} live now")

        # Re-apply current sort after render (default: Status ▲ keeps LIVE on top)
        if self._multi_sort_col:
            self._multi_sort_apply()


    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=BG2, height=56)
        bar.pack(fill="x", padx=8, pady=8)
        bar.pack_propagate(False)

        logo_frame = tk.Frame(bar, bg=BG2)
        logo_frame.pack(side="left", padx=16)
        tk.Label(logo_frame, text="⚡ KICK STREAM ANALYTICS", font=("Consolas",13,"bold"),
                 bg=BG2, fg=ACCENT).pack(anchor="center")
        tk.Label(logo_frame, text="& Deep AI Research Tool", font=("Segoe UI",9,"bold"),
                 bg=BG2, fg=WHITE).pack(anchor="center")
        tk.Label(logo_frame, text="by Ask_fOr_DaX", font=("Segoe UI",8),
                 bg=BG2, fg=GREY).pack(anchor="center")

        tk.Button(bar, text="➕  Add Streamer", command=self._add_streamer_tab,
                  bg=ACCENT, fg="#000", font=("Segoe UI",11,"bold"),
                  relief="flat", padx=16, pady=6, cursor="hand2").pack(side="left", padx=16)

        tk.Label(bar, text="Double-click a tab to rename  |  ✕ Close Tab to remove",
                 bg=BG2, fg=GREY, font=("Segoe UI",9)).pack(side="left", padx=8)

        # Live system clock — far right, same format as report timestamps
        clock_frame = tk.Frame(bar, bg=BG2)
        clock_frame.pack(side="right", padx=16)
        tk.Label(clock_frame, text="🕐", bg=BG2, fg=GREY,
                 font=("Segoe UI",11)).pack(side="left", padx=(0,4))
        self.clock_var = tk.StringVar()
        tk.Label(clock_frame, textvariable=self.clock_var,
                 bg=BG2, fg=WHITE, font=("Consolas",13,"bold")).pack(side="left")
        self._update_clock()

    def _update_clock(self):
        """Update the system clock every second — same format as report timestamps."""
        self.clock_var.set(datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        self.root.after(1000, self._update_clock)

    # ── Left panel: channel info + live stats ─────────────────

    def _multi_remove(self):
        sel = self.multi_tree.selection()
        if not sel: return
        vals = self.multi_tree.item(sel[0], "values")
        slug = vals[0].strip() if vals else ""
        if slug in self._multi_channels:
            del self._multi_channels[slug]
            self._multi_save()
            self._multi_render()


    def _multi_load_saved(self):
        """Load saved channel slugs from local JSON and fetch their data."""
        try:
            if not os.path.exists(self._multi_save_path):
                return
            with open(self._multi_save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            slugs = data.get("channels", [])
            if not slugs:
                return
            for slug in slugs:
                self._multi_channels[slug] = {
                    "slug": slug, "status": "...", "viewers": 0,
                    "category": "...", "followers": 0, "followers_start": 0,
                    "last_updated": "Restoring..."
                }
            self._multi_render()
            # Refresh all restored channels in background
            for slug in slugs:
                self._multi_refresh_one(slug)
        except Exception:
            pass


    def _top100_show_detail(self, event):
        sel = self.top100_tree.selection()
        if not sel: return
        vals = self.top100_tree.item(sel[0], "values")
        if not vals: return
        name = vals[1].replace("✓ ","").strip()
        found = next((r for r in self._top100_raw if r["name"] == name), None)
        if found:
            self.top100_detail_var.set(
                f"kick.com/{found['slug']}  |  {found['viewers']:,} viewers  |  "
                f"Language: {found.get('language','N/A')}  |  "
                f"Category: {found['category']}  |  "
                f"Followers: {found['followers']:,}  |  "
                f"Mature: {'Yes' if found['mature'] else 'No'}  |  "
                f"Started: {fmt_date(found['started'])}")


    def __init__(self, root):
        self.root       = root
        self.sessions   = []
        self._cached_gpu = {}  # shared GPU info across all session tabs
        self._setup_window()
        self._build_ui()
        # Load cached GPU from settings file into app object
        try:
            path = os.path.join(APP_DIR, "ai_settings.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("gpu_name") and data.get("gpu_vram"):
                    self._cached_gpu = {
                        "gpu_name":  data["gpu_name"],
                        "gpu_vram":  data["gpu_vram"],
                        "gpu_tier":  data.get("gpu_tier", ""),
                        "gpu_model": data.get("gpu_model", ""),
                    }
        except: pass

    def _multi_remove_all(self):
        if not self._multi_channels:
            return
        if messagebox.askyesno("Remove All",
                               f"Remove all {len(self._multi_channels)} channels?"):
            self._multi_channels.clear()
            self._multi_save()
            self._multi_render()


def main():
    root = tk.Tk()
    app  = KickGUI(root)
    # Allow pre-filling slug from CLI
    if len(sys.argv) > 1:
        app.slug_var.set(sys.argv[1])
    root.mainloop()

if __name__ == "__main__":
    main()
