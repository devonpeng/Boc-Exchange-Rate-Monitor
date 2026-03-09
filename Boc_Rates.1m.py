#!/usr/bin/env python3
# <bitbar.title>BoC Exchange Rate Monitor</bitbar.title>
# <bitbar.version>v1.0</bitbar.version>

import urllib.request
import urllib.error
import re
import json
import os
import sys
import subprocess
import time

# ================= Basic Configuration =================
CONFIG_FILE = os.path.expanduser('~/.boc_swiftbar_config.json')
CACHE_FILE = os.path.expanduser('~/.boc_swiftbar_cache.json')
SCRIPT_PATH = os.path.abspath(__file__)

# Mapping: Chinese Name (for Scraping) -> [Flag, English Display Name]
CURRENCY_MAP = {
    "澳大利亚元": ["🇦🇺", "AUD"],
    "美元": ["🇺🇸", "USD"],
    "欧元": ["🇪🇺", "EUR"], 
    "英镑": ["🇬🇧", "GBP"], 
    "日元": ["🇯🇵", "JPY"], 
    "港币": ["🇭🇰", "HKD"],
    "加拿大元": ["🇨🇦", "CAD"], 
    "新西兰元": ["🇳🇿", "NZD"]
}

DEFAULT_CONFIG = {
    "currency": "澳大利亚元", 
    "side": "SELL",
    "upper_bound": None, 
    "lower_bound": None
}

# ================= System Helpers =================

def load_config():
    """Loads the configuration from the local JSON file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except: pass
    return DEFAULT_CONFIG

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def prompt_input(title, default_val=""):
    script = f'''
    tell application "System Events"
        activate
        set userInput to text returned of (display dialog "Enter {title} (Leave blank to cancel alert):" default answer "{default_val}")
    end tell
    return userInput
    '''
    try:
        result = subprocess.check_output(['osascript', '-e', script]).decode('utf-8').strip()
        if not result: return None
        return float(result)
    except: return None

# ================= Core Scraper & Cache =================

def fetch_boc_data():
    """
    Scrapes real-time exchange rate data from the Bank of China website.
    Returns:
        A tuple containing the rates dictionary and an error message (if any).
    """
    url = "https://www.boc.cn/sourcedb/whpj/index.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
        rates = {}
        for cn_name in CURRENCY_MAP.keys():
            # Pattern matches the Chinese name on the BOC website
            pattern = fr'<td>{cn_name}</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>'
            match = re.search(pattern, html)
            if match:
                rates[cn_name] = {
                    "buy": round(float(match.group(1).strip()), 2),
                    "sell": round(float(match.group(3).strip()), 2)
                }
        return rates, None
    except urllib.error.URLError as e:
        return None, f"Network Error: {e.reason}"
    except Exception as e:
        return None, f"Unexpected Error: {str(e)}"

def get_data_with_cache(force=False):
    """ Retrieves exchange rates from cache or fetches new data if cache is expired (55s)."""
    now = time.time()
    cache = {"timestamp": 0, "rates": {}}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
        except: pass

    if force or (now - cache.get("timestamp", 0) > 55):
        new_rates, err = fetch_boc_data()
        if err: return None, err
        cache["timestamp"], cache["rates"] = now, new_rates
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    return cache, None

# ================= Interactive Commands =================

if len(sys.argv) > 1:
    action = sys.argv[1]
    cfg = load_config()
    if action == "set_currency": cfg["currency"] = sys.argv[2]
    elif action == "set_side": cfg["side"] = sys.argv[2]
    elif action == "set_upper":
        cfg["upper_bound"] = prompt_input("Upper Bound Alert Rate", cfg.get("upper_bound") or "")
    elif action == "set_lower":
        cfg["lower_bound"] = prompt_input("Lower Bound Alert Rate", cfg.get("lower_bound") or "")
    elif action == "clear_alerts":
        cfg["upper_bound"], cfg["lower_bound"] = None, None
    elif action == "force_refresh": get_data_with_cache(force=True)
    save_config(cfg)
    sys.exit(0)

# ================= Rendering Logic =================

def main():
    cfg = load_config()
    curr_cn, side = cfg["currency"], cfg["side"]
    data, err = get_data_with_cache()
    
    if err:
        print(f"⚠️ Data Error")
        print("---")
        print(f"Manual Refresh | bash='{SCRIPT_PATH}' param1='force_refresh' terminal=false refresh=true")
        return

    rates = data["rates"].get(curr_cn)
    if not rates:
        print(f"⚠️ {curr_cn} Not Found")
        return

    price = rates["buy"] if side == "BUY" else rates["sell"]
    
    # --- 1. Menu Bar Display ---
    flag = CURRENCY_MAP.get(curr_cn, ["💰", "UNK"])[0]
    curr_en = CURRENCY_MAP.get(curr_cn, ["💰", "UNK"])[1]
    
    alert_color = ""
    alert_icon = "" 
    alert_msg = ""

    if cfg["upper_bound"] and price >= cfg["upper_bound"]:
        alert_color = " | color=red"
        alert_icon = "📈 " 
        alert_msg = " (Upper Bound Hit)"
    elif cfg["lower_bound"] and price <= cfg["lower_bound"]:
        alert_color = " | color=green"
        alert_icon = "📉 " 
        alert_msg = " (Lower Bound Hit)"

    print(f"{alert_icon}{flag} {price:.2f}{alert_color}")
    
    # --- 2. Dropdown Menu ---
    print("---")
    print(f"🏦 Monitoring: {curr_en}")
    for cn_key, (c_flag, c_en) in CURRENCY_MAP.items():
        mark = "✓ " if cn_key == curr_cn else "  "
        print(f"--{mark}{c_flag} {c_en} | bash='{SCRIPT_PATH}' param1='set_currency' param2='{cn_key}' terminal=false refresh=true")
    
    side_display = "BoC Buying Rate" if side == "BUY" else "BoC Selling Rate"
    print(f"📊 Alert Side: {side_display}")
    print(f"--{'✓ ' if side == 'BUY' else '  '}BoC Buying Rate | bash='{SCRIPT_PATH}' param1='set_side' param2='BUY' terminal=false refresh=true")
    print(f"--{'✓ ' if side == 'SELL' else '  '}BoC Selling Rate | bash='{SCRIPT_PATH}' param1='set_side' param2='SELL' terminal=false refresh=true")
    
    print(f"🔔 Alert Settings{alert_msg}")
    up_t = f"{cfg['upper_bound']:.2f}" if cfg['upper_bound'] else "Not Set"
    low_t = f"{cfg['lower_bound']:.2f}" if cfg['lower_bound'] else "Not Set"
    print(f"--Set Upper Bound (Current: {up_t}) | bash='{SCRIPT_PATH}' param1='set_upper' terminal=false refresh=true")
    print(f"--Set Lower Bound (Current: {low_t}) | bash='{SCRIPT_PATH}' param1='set_lower' terminal=false refresh=true")
    if cfg['upper_bound'] or cfg['lower_bound']:
        print(f"--🗑️ Clear All Alerts | bash='{SCRIPT_PATH}' param1='clear_alerts' terminal=false refresh=true")

    print("---")
    print(f"Current Buying Rate: {rates['buy']:.2f}")
    print(f"Current Selling Rate: {rates['sell']:.2f}")
    spread = rates['sell'] - rates['buy']
    mid_price = (rates['sell'] + rates['buy']) / 2
    spread_pct = (spread / mid_price) * 100
    print(f"Spread: {spread:.2f} ({spread_pct:.2f}%)")
    print("---")
    update_time = time.strftime("%H:%M:%S", time.localtime(data["timestamp"]))
    print(f"🕒 Last Update: {update_time}")
        
    print("Open BoC Official Site | href=https://www.boc.cn/sourcedb/whpj/index.html")
    print(f"Manual Refresh | bash='{SCRIPT_PATH}' param1='force_refresh' terminal=false refresh=true")

if __name__ == "__main__":
    main()