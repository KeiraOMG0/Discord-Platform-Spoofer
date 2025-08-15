"""
main.py
Minimal Gateway-based platform spoofer with auto config creation.

- If config.json is missing, prompts for token and platform and saves it.
- Platforms exposed to user: desktop, web, mobile, console.
- Connects to Discord Gateway, sends IDENTIFY with spoofed properties.
- Maintains heartbeat, provides aiohttp session for REST if needed.

WARNING: Don't post your token anywhere. Selfbots/spoofing may violate Discord TOS.
"""

import os
import json
import base64
import asyncio
import logging
from typing import Dict, Optional, Any
import websockets
import aiohttp

# --- Config/token loader ---------------------------------------------------
CONFIG_PATH = "config.json"

# --- User-facing platforms mapping ----------------------------------------
# User-friendly names -> actual template keys
PLATFORM_ALIAS = {
    "desktop": "desktop",
    "web": "web",
    "mobile": "ios",             # mobile maps to iOS template
    "console": "playstation"     # console maps to embedded console template
}

def create_config(path: str = CONFIG_PATH) -> Dict[str, Any]:
    """Prompt user for token and platform, save to config.json"""
    print("No config.json found. Let's create one.")
    token = input("Enter your Discord token: ").strip()
    print("Choose platform to spoof:")
    print(" - desktop")
    print(" - web")
    print(" - mobile")
    print(" - console (embed)")
    platform_input = input("Platform (default 'desktop'): ").strip().lower() or "desktop"
    if platform_input not in PLATFORM_ALIAS:
        print("Unknown platform; defaulting to desktop")
        platform_input = "desktop"
    cfg = {"token": token, "platform": platform_input}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)
    print(f"Config saved to {path}")
    return cfg

def load_config(path: str = CONFIG_PATH) -> Dict[str, Any]:
    """Load existing config.json or create new one if missing"""
    if not os.path.exists(path):
        return create_config(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return create_config(path)

def load_token(cfg: Dict[str, Any]) -> Optional[str]:
    token = os.getenv("DISCORD_TOKEN")
    if token:
        return token
    return cfg.get("token")

# --- Templates for properties / UA ----------------------------------------
SUPER_PROPERTIES_TEMPLATES: Dict[str, Dict] = {
    "desktop": {
        "os": "Windows",
        "browser": "Discord Client",
        "device": "",
        "system_locale": "en-US",
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        "client_build_number": 432290
    },
    "web": {
        "os": "Windows",
        "browser": "Discord Web",
        "device": "",
        "system_locale": "en-US",
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        "client_build_number": 432290
    },
    "ios": {
        "os": "iOS",
        "browser": "Discord iOS",
        "device": "iPhone",
        "system_locale": "en-US",
        "browser_user_agent": "Discord/2024.0 (iPhone; iOS 16.6; Scale/3.00)",
        "client_build_number": 123456
    },
    "android": {
        "os": "Android",
        "browser": "Discord Android",
        "device": "Android Phone",
        "system_locale": "en-US",
        "browser_user_agent": "Discord/2024.0 (Android 13; Pixel 6)",
        "client_build_number": 123456
    },
    "xbox": {
        "os": "Xbox",
        "browser": "Discord Embedded",
        "device": "Xbox",
        "system_locale": "en-US",
        "browser_user_agent": "Discord/Embedded (Xbox)",
        "client_build_number": 123456
    },
    "playstation": {
        "os": "PlayStation",
        "browser": "Discord Embedded",
        "device": "PlayStation",
        "system_locale": "en-US",
        "browser_user_agent": "Discord/Embedded (PlayStation)",
        "client_build_number": 123456
    }
}

def encode_super_properties(obj: Dict) -> str:
    s = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    return base64.b64encode(s.encode("utf-8")).decode("ascii")

# --- Gateway logic ---------------------------------------------------------
GATEWAY_URL = "wss://gateway.discord.gg/?v=9&encoding=json"

async def heartbeat_loop(ws: websockets.WebSocketClientProtocol, interval_ms: int, get_seq_callable):
    interval = interval_ms / 1000.0
    try:
        while True:
            seq = get_seq_callable()
            payload = {"op": 1, "d": seq}
            await ws.send(json.dumps(payload))
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        return
    except Exception as exc:
        logging.getLogger("gateway_spoofer").exception("Heartbeat error: %s", exc)

async def run_gateway(token: str, platform: str):
    log = logging.getLogger("gateway_spoofer")
    props = SUPER_PROPERTIES_TEMPLATES.get(platform, SUPER_PROPERTIES_TEMPLATES["desktop"])
    encoded_props = encode_super_properties(props)
    ua = props.get("browser_user_agent")

    rest_headers = {
        "Authorization": token,
        "X-Super-Properties": encoded_props,
        "User-Agent": ua or "DiscordBot (https://example, 1.0)"
    }
    rest_session = aiohttp.ClientSession(headers=rest_headers)

    last_seq_holder = {"seq": None}

    def get_seq():
        return last_seq_holder["seq"]

    async with websockets.connect(GATEWAY_URL, max_size=None) as ws:
        log.info("Connected to gateway, waiting for HELLO...")
        raw = await ws.recv()
        msg = json.loads(raw)
        hello = msg.get("d", {})
        hb_interval = hello.get("heartbeat_interval", 41250)

        hb_task = asyncio.create_task(heartbeat_loop(ws, hb_interval, get_seq))

        identify_payload = {
            "op": 2,
            "d": {
                "token": token,
                "properties": {
                    "os": props.get("os", ""),
                    "browser": props.get("browser", ""),
                    "device": props.get("device", ""),
                },
                "presence": {"status": "online", "since": 0, "activities": [], "afk": False},
                "intents": 0
            }
        }
        await ws.send(json.dumps(identify_payload))
        log.info("IDENTIFY sent with properties: %s", identify_payload["d"]["properties"])

        try:
            while True:
                raw = await ws.recv()
                msg = json.loads(raw)
                if msg.get("s") is not None:
                    last_seq_holder["seq"] = msg["s"]
                op = msg.get("op")
                t = msg.get("t")
                if op == 0 and t == "READY":
                    user = msg.get("d", {}).get("user", {})
                    log.info("READY received. logged in as: %s (id=%s)", user.get("username"), user.get("id"))
                if op == 9:
                    log.warning("Invalid session. server asked to reconnect.")
                    break
                if op == 1:
                    await ws.send(json.dumps({"op": 1, "d": last_seq_holder["seq"]}))
        except websockets.exceptions.ConnectionClosed as e:
            log.info("Connection closed: %s", e)
        finally:
            hb_task.cancel()
            await rest_session.close()

# --- Main ------------------------------------------------------------------
def main():
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s")
    cfg = load_config()
    token = load_token(cfg)
    if not token:
        print("No token found. Set DISCORD_TOKEN or add config.json with {'token': '...'}")
        return

    platform_input = cfg.get("platform", "desktop").lower()
    if platform_input not in PLATFORM_ALIAS:
        print("Unknown platform in config.json; defaulting to desktop")
        platform_input = "desktop"

    # Map user-friendly platform to template
    platform_template = PLATFORM_ALIAS[platform_input]

    asyncio.run(run_gateway(token, platform_template))

if __name__ == "__main__":
    main()
