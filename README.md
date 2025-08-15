# Discord-Platform-Spoofer
A minimal selfbot gateway spoofer for Discord that allows users to appear as mobile, desktop, web, or console clients. Includes auto-config creation and optional REST session support.

> ⚠️ Warning: Selfbots and account automation may violate Discord TOS. Use at your own risk.

---

## Features

- Spoof platform: **desktop, web, mobile (iOS/Android), console (Xbox/PlayStation)**  
- Auto-creates `config.json` if missing for token and platform  
- Maintains a Discord Gateway connection with spoofed X-Super-Properties  
- Optional REST session with spoofed headers for further automation  
- Works on **Windows, macOS, and Linux**  

---

## Requirements

- Python 3.11+ (3.10 may work)  
- `discord.py-self`  
- `aiohttp`  
- `websockets`  

---

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/KeiraOMG0/Discord-Platform-Spoofer.git
cd discord-platform-spoofer
````

### 2. Create a virtual environment

#### Windows

```cmd
python -m venv venv
venv\Scripts\activate.bat
```

#### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> If you installed `discord.py-self` via Git, `aiohttp` should already be installed. Install `websockets` manually if needed:

```bash
pip install websockets
```

---

## Usage

1. Run the main script:

```bash
python main.py
```

2. If `config.json` does not exist, you'll be prompted to enter:

   * **Discord token**
   * **Platform to spoof** (`desktop`, `web`, `mobile`, `console`)

3. The script will maintain a Gateway connection and display your logged-in username and spoofed platform.

---

## Optional: Precompiled Executable

You can provide a precompiled `ChedLog.exe` or your own compiled version of this script.

* Windows users can run `.exe` directly.
* Linux/macOS users can use **PyInstaller** or run via Python (`python main.py`).
* Linux users can also run Windows `.exe` via **Wine**.

---

## License

This project is licensed under **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**.

* Users may clone, fork, and modify
* Commercial use is prohibited
* Changes must remain under the same license
* Credit and a link to the original source must be included

Full license: [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode)