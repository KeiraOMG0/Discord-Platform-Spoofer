import os
import sys
import json
import asyncio
import logging
import websockets
import aiohttp
import signal
import ssl
import http.client
import re
import pickle
from urllib.parse import urlparse
from datetime import datetime, timedelta
import base64

# --- Config / cache ---
CONFIG_PATH = "config.json"
CACHE_FILE = "build_cache.pkl"
CACHE_DURATION_DAYS = 7
stop_flag = False
current_tasks = []

# --- Signal handling ---
def signal_handler(sig, frame):
    global stop_flag
    print(f"[INFO] Received signal {sig}, shutting down...")
    sys.stdout.flush()
    stop_flag = True
    for task in current_tasks:
        if not task.done():
            task.cancel()

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
if os.name == "nt":
    signal.signal(signal.SIGBREAK, signal_handler)

# --- HTTP request helper ---
class reqresp:
    def __init__(self, status, data):
        self.status_code = status
        self._data = data
    @property
    def text(self):
        try:
            return self._data.decode('utf-8')
        except UnicodeDecodeError:
            return self._data
    def json(self):
        try:
            return json.loads(self._data.decode('utf-8'))
        except:
            return None
    @property
    def content(self):
        return self._data

class requesters:
    @staticmethod
    def request(method, url, headers=None, json_data=None):
        if headers is None:
            headers = {}
        parsed_url = urlparse(url)
        host = parsed_url.netloc
        endpoint = parsed_url.path
        if parsed_url.query:
            endpoint += '?' + parsed_url.query
        if parsed_url.scheme == "https":
            conn = http.client.HTTPSConnection(host, context=ssl.create_default_context())
        else:
            conn = http.client.HTTPConnection(host)
        body = None
        if json_data:
            body = json.dumps(json_data)
            headers['Content-Type'] = 'application/json'
        try:
            conn.request(method, endpoint, body=body, headers=headers)
            res = conn.getresponse()
            data = res.read()
            conn.close()
            return reqresp(res.status, data)
        except Exception:
            return reqresp(500, b"")

    @staticmethod
    def get(url, headers=None):
        return requesters.request("GET", url, headers=headers)

# --- Build number caching ---
def load_cached_build():
    try:
        with open(CACHE_FILE, 'rb') as f:
            return pickle.load(f)
    except:
        return None, None

def save_cached_build(build_number):
    try:
        with open(CACHE_FILE, 'wb') as f:
            pickle.dump((build_number, datetime.now()), f)
    except:
        pass

def extract_asset_files():
    req = requesters.get("https://discord.com/login")
    pattern = r'<script\s+src="([^"]+\.js)"\s+defer>\s*</script>'
    return re.findall(pattern, req.text)

def get_live_build_number():
    try:
        files = extract_asset_files()
        for file in files:
            url = f"https://discord.com{file}"
            resp = requesters.get(url)
            if "buildNumber" in resp.text:
                return int(resp.text.split('buildNumber:"')[1].split('"')[0])
    except:
        pass
    return None

def get_current_build_number():
    cached, timestamp = load_cached_build()
    if cached and timestamp and datetime.now() - timestamp < timedelta(days=CACHE_DURATION_DAYS):
        return cached
    new_build = get_live_build_number()
    if new_build:
        save_cached_build(new_build)
        return new_build
    if cached:
        return cached
    return 432290  # fallback

# --- Load config ---
def load_config(path=CONFIG_PATH):
    if not os.path.exists(path):
        token = input("Enter your Discord token: ").strip()
        platform = input("Platform (desktop/web/mobile/console, default desktop): ").strip().lower() or "desktop"
        cfg = {"token": token, "platform": platform}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
        return cfg
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_token(cfg):
    return os.getenv("DISCORD_TOKEN") or cfg.get("token")

# --- Super properties ---
CURRENT_BUILD = get_current_build_number()
SUPER_PROPERTIES = {
    "desktop": {"os":"Windows","browser":"Discord Client","device":"","system_locale":"en-US","browser_user_agent":"Mozilla/5.0","client_build_number":CURRENT_BUILD},
    "web": {"os":"Windows","browser":"Discord Web","device":"","system_locale":"en-US","browser_user_agent":"Mozilla/5.0","client_build_number":CURRENT_BUILD},
    "ios": {"os":"iOS","browser":"Discord iOS","device":"iPhone","system_locale":"en-US","browser_user_agent":"Discord/2024.0 (iPhone; iOS 16.6; Scale/3.00)","client_build_number":CURRENT_BUILD},
    "playstation": {"os":"PlayStation","browser":"Discord Embedded","device":"PlayStation","system_locale":"en-US","browser_user_agent":"Discord/Embedded (PlayStation)","client_build_number":CURRENT_BUILD}
}

DISPLAY_NAMES = {"playstation":"console","ios":"mobile","desktop":"desktop","web":"web"}

def encode_super_properties(obj):
    s = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    return base64.b64encode(s.encode("utf-8")).decode("ascii")

# --- Gateway ---
GATEWAY_URL = "wss://gateway.discord.gg/?v=9&encoding=json"

async def heartbeat_loop(ws, interval_ms, get_seq):
    interval = interval_ms / 1000.0
    try:
        while not stop_flag:
            await ws.send(json.dumps({"op":1,"d":get_seq()}))
            await asyncio.sleep(interval)
    except (asyncio.CancelledError, websockets.exceptions.ConnectionClosed):
        return

async def run_gateway(token, platform):
    log = logging.getLogger("gateway_spoofer")
    props = SUPER_PROPERTIES.get(platform, SUPER_PROPERTIES["desktop"])
    encoded_props = encode_super_properties(props)
    ua = props.get("browser_user_agent")
    headers = {"Authorization": token, "X-Super-Properties": encoded_props, "User-Agent": ua}
    session = aiohttp.ClientSession(headers=headers)
    last_seq = {"seq": None}
    def get_seq(): return last_seq["seq"]

    hb_task = None
    platform_display = DISPLAY_NAMES.get(platform, platform)

    try:
        async with websockets.connect(GATEWAY_URL, max_size=None, ping_interval=None) as ws:
            raw = await ws.recv()
            hello = json.loads(raw).get("d", {})
            hb_task = asyncio.create_task(heartbeat_loop(ws, hello.get("heartbeat_interval", 41250), get_seq))
            current_tasks.append(hb_task)

            identify_payload = {
                "op": 2,
                "d": {"token": token,"properties":{"os":props.get("os"),"browser":props.get("browser"),"device":props.get("device")}, "intents":0}
            }
            await ws.send(json.dumps(identify_payload))
            log.info(f"IDENTIFY sent for platform: {platform_display} (build: {CURRENT_BUILD})")

            while not stop_flag:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1)
                    msg = json.loads(raw)
                    if msg.get("s") is not None:
                        last_seq["seq"] = msg["s"]
                    if msg.get("op") == 0 and msg.get("t") == "READY":
                        user = msg.get("d", {}).get("user", {})
                        log.info(f"Logged in: {user.get('username')} (ID: {user.get('id')}) on {platform_display}")
                    if msg.get("op") == 9:
                        log.warning("Invalid session, exiting...")
                        break
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    log.info("WebSocket closed")
                    break
    finally:
        if hb_task and not hb_task.done():
            hb_task.cancel()
            try: await hb_task
            except asyncio.CancelledError: pass
        await session.close()
        log.info("Disconnected")

# --- Main ---
def main():
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s")
    cfg = load_config()
    token = load_token(cfg)
    if not token:
        print("No token found in config.json or DISCORD_TOKEN env")
        return
    platform_input = cfg.get("platform","desktop").lower()
    if platform_input not in ["desktop","web","mobile","console"]:
        platform_input = "desktop"
    template_platform = "ios" if platform_input=="mobile" else ("playstation" if platform_input=="console" else platform_input)
    asyncio.run(run_gateway(token, template_platform))

if __name__ == "__main__":
    main()
