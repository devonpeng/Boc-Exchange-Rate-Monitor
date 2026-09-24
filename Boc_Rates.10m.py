#!/usr/bin/env python3
# <bitbar.title>BoC Exchange Rate Monitor</bitbar.title>
# <bitbar.version>v2.1</bitbar.version>

import urllib.request
import urllib.error
import re
import json
import os
import sys
import subprocess
import time

# ================= Basic Configuration =================
# Storage paths for persistent configuration and state
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
    """
    Bridge: Triggers a native macOS dialog via AppleScript for user input.
    Essential for interactive settings within the SwiftBar environment.
    """
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
        with urllib.request.urlopen(req, timeout=30) as response:
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
    now = time.time()
    cache = {"timestamp": 0, "rates": {}, "error": None}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                cache = {**cache, **json.load(f)}
        except: pass

    # Persistence: Cache TTL set to 595s (approx. 10m) to minimize CPU wake-ups.
    # Also handles 'Offline-First' state by caching error messages.
    if force or (now - cache.get("timestamp", 0) > 595):
        new_rates, err = fetch_boc_data()
        if err:
            cache["error"] = f"Offline: {err}"
            cache["timestamp"] = now
            with open(CACHE_FILE, 'w') as f:
                json.dump(cache, f)
            return cache, cache["error"]
        
        cache["error"] = None
        cache["timestamp"], cache["rates"] = now, new_rates
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f)

    return cache, cache.get("error")

# ================= On-Demand Chart Export (Lazy) =================
# Heavyweight imports (matplotlib / numpy) are done lazily inside the functions
# below, so the regular 10-minute SwiftBar refresh costs nothing extra in CPU
# or memory. NOTE: this block must stay above the `if len(sys.argv) > 1:`
# router further down, otherwise the action lookup raises NameError at runtime.

YAHOO_CHART_API = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# Unit note: BOC quotes rates as "CNY per 100 units of foreign currency"
# (e.g. 473.91 means 100 AUD), while Yahoo's AUDCNY=X quotes a single unit
# (~4.7) - roughly a 100x gap. The ratio rebase plus affine mapping below
# absorbs that difference automatically, so no manual conversion is needed.


def _applescript_escape(text):
    """Escape a string for an AppleScript literal: backslashes, quotes, newlines."""
    return (str(text).replace('\\', '\\\\').replace('"', '\\"')
            .replace('\r', ' ').replace('\n', ' '))


def notify(title, message):
    """Bridge: post a system notification (Standard Additions, no System Events needed)."""
    script = ('display notification "%s" with title "%s"'
              % (_applescript_escape(message), _applescript_escape(title)))
    try:
        subprocess.check_call(['osascript', '-e', script])
    except Exception:
        pass


def prompt_save_filepath(default_filename):
    """
    Bridge: show the native macOS "Save As" sheet (AppleScript choose file name).
    Returns the chosen POSIX path, or None when the user cancels or an error occurs.
    """
    script = (
        'set targetFile to choose file name with prompt "Save the 7-day trend chart as:" '
        'default name "%s" ' % _applescript_escape(default_filename)
        + 'default location (path to desktop folder)\n'
        + 'return POSIX path of targetFile'
    )
    try:
        result = subprocess.check_output(['osascript', '-e', script]).decode('utf-8').strip()
        return result or None
    except Exception:
        return None


def fetch_yahoo_series(symbol, interval='1h', span='7d'):
    """
    Single request against the Yahoo Finance chart API (the endpoint yfinance
    itself uses). Returns (timestamps, closes) as two equal-length lists and
    raises on failure so the caller can surface it.
    """
    url = YAHOO_CHART_API.format(symbol=symbol) + f"?interval={interval}&range={span}"
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode('utf-8'))

    chart = payload.get('chart') or {}
    if chart.get('error'):
        raise RuntimeError(f"Yahoo API: {chart['error']}")
    results = chart.get('result') or []
    if not results:
        raise RuntimeError("Yahoo API returned an empty result")

    result = results[0]
    quote = ((result.get('indicators') or {}).get('quote') or [{}])[0]
    # Keep timestamps aligned with closes by index, dropping exchange-closure gaps
    # and any non-positive print (a zero close would later divide by zero).
    pairs = [(t, c) for t, c in zip(result.get('timestamp') or [], quote.get('close') or [])
             if c is not None and c > 0]
    if len(pairs) < 2:
        raise RuntimeError("Yahoo returned too few valid data points")
    return [p[0] for p in pairs], [p[1] for p in pairs]


def build_fitted_series(closes, b_end):
    """
    Anchor Yahoo's market series onto BOC's quoting basis.

    BOC's historical rate endpoint is gone (the old
    srh.bankofchina.com/search/whpj/search_cn.jsp now returns a JSON 404, and
    the replacement requires a Geetest captcha), so the opening anchor is
    rebased proportionally instead of fetched:
        B_start = B_end * (Y_start / Y_end)
    That value then feeds the affine mapping that squeezes Y(t) into
    [B_start, B_end]:
        P(t) = B_start + (B_end - B_start) / (Y_end - Y_start) * (Y(t) - Y_start)
    Substituting the rebased B_start reduces it to a plain rescale,
    P(t) = (B_end / Y_end) * Y(t); the general form is kept so that plugging in
    a real historical BOC rate later needs no change to the formula.
    """
    y_start, y_end = closes[0], closes[-1]
    if y_start <= 0 or y_end <= 0:
        raise RuntimeError("Yahoo series contains a non-positive price")
    if y_end == y_start:
        raise RuntimeError("Yahoo series is flat, cannot align")
    b_start = b_end * (y_start / y_end)
    scale = (b_end - b_start) / (y_end - y_start)
    return [b_start + scale * (y - y_start) for y in closes]


def render_trend_chart(save_path, timestamps, fitted, curr_en, side_label):
    """
    Lazily import matplotlib / numpy and render a high-resolution PNG.
    Only ever called after the user clicks "Save 7-Day Trend Chart...".
    """
    import tempfile
    from datetime import datetime

    # ~/.matplotlib is not always writable from SwiftBar's host environment,
    # which makes matplotlib fall back to a slow path and print warnings; point
    # it at a writable cache dir, then force the headless Agg backend.
    cache_dir = os.path.join(tempfile.gettempdir(), 'boc_mpl_cache')
    try:
        os.makedirs(cache_dir, exist_ok=True)
        os.environ.setdefault('MPLCONFIGDIR', cache_dir)
    except Exception:
        pass

    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    # Keep the minus sign renderable using the default DejaVu Sans metrics.
    matplotlib.rcParams['axes.unicode_minus'] = False
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    dates = [datetime.fromtimestamp(t) for t in timestamps]
    values = np.asarray(fitted, dtype=float)
    line_color = '#1f3b73'

    # Y-axis floor, split by the currency's base magnitude.
    #
    # Large-base currencies (AUD/USD/EUR/GBP/CAD/NZD, all quoted well above 200):
    # pin the floor to a flat 450 so the visible band stays tight and small moves
    # remain legible. Never clamp above the data - if an extreme dip goes below
    # 450, drop the floor just underneath it instead of cutting the series off.
    #
    # Small-base currencies (JPY ~4.3, HKD ~85): they sit far below 450 to begin
    # with, so simply fit their own range.
    data_min = float(values.min())
    base_quote = float(values[-1])       # closing anchor == BOC's current quote
    if base_quote >= 200.0:
        y_bottom = 450.0 if data_min >= 450.0 else data_min * 0.995
    else:
        y_bottom = data_min * 0.995

    fig, ax = plt.subplots(figsize=(10, 5))

    ax.fill_between(dates, values, y_bottom, color=line_color, alpha=0.15, zorder=2)
    ax.plot(dates, values, color=line_color, linewidth=1.5, zorder=3)

    # Scatter the opening/closing anchors and label each with date + amount.
    # Two things keep the labels clear of the curve: a white rounded halo drawn
    # above every other artist (zorder 7 > line 3 / scatter 5 / trend 4), so the
    # series never crosses the glyphs; and a vertical side picked from where the
    # endpoint sits, so the label lands in the emptier half of the plot.
    ax.scatter([dates[0], dates[-1]], [values[0], values[-1]], color=line_color, s=30, zorder=5)

    label_halo = dict(boxstyle='round,pad=0.28', facecolor='white',
                      edgecolor='none', alpha=0.88)
    midpoint = float(values.min() + values.max()) / 2.0
    for date, value, is_last in ((dates[0], values[0], False),
                                 (dates[-1], values[-1], True)):
        above = value >= midpoint            # high endpoint -> lift label, low -> drop it
        ax.annotate(f"{date.strftime('%m-%d')}: {value:.2f}", xy=(date, value),
                    xytext=(-8 if is_last else 8, 12 if above else -18),
                    textcoords='offset points', fontsize=9, color='#333333',
                    ha='right' if is_last else 'left',
                    va='bottom' if above else 'top',
                    bbox=label_halo, zorder=7)

    # First-order regression: positive slope draws a red dashed line, else green
    x_idx = np.arange(values.size, dtype=float)
    slope, intercept = np.polyfit(x_idx, values, 1)
    trend_color = '#d62728' if slope > 0 else '#2ca02c'
    ax.plot(dates, slope * x_idx + intercept, linestyle='--', linewidth=1.2,
            color=trend_color, zorder=4,
            label=('%s trend (regression)' % ('Upward' if slope > 0 else 'Downward')))

    ax.set_ylim(bottom=y_bottom)
    ax.set_title(f"{curr_en}/CNY 7-Day Rate Trend - {side_label}", fontsize=13, pad=14)
    ax.set_ylabel("CNY per 100 units", fontsize=10)

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    ax.grid(axis='y', linestyle='-', linewidth=0.6, color='#dddddd')
    ax.set_axisbelow(True)
    ax.legend(frameon=True, facecolor='white', edgecolor='none', framealpha=0.85,
              fontsize=9, loc='best')

    try:
        fig.tight_layout()
        fig.savefig(save_path, dpi=300, bbox_inches='tight')
    finally:
        plt.close(fig)


def export_chart_flow(cfg):
    """Full flow behind "Save 7-Day Trend Chart...": anchor -> path -> data -> fit -> render -> notify."""
    curr_cn = cfg.get("currency", DEFAULT_CONFIG["currency"])
    side = cfg.get("side", DEFAULT_CONFIG["side"])
    _, curr_en = CURRENCY_MAP.get(curr_cn, ["💰", "UNK"])
    side_label = "BoC Buying Rate" if side == "BUY" else "BoC Selling Rate"

    # 1) Closing anchor: reuse the cached current rate, no extra network call
    data, _ = get_data_with_cache()
    rates = (data or {}).get("rates", {}).get(curr_cn)
    if not rates:
        notify("Export Failed", f"No cached rate for {curr_en} yet, try again shortly")
        return
    b_end = rates["buy"] if side == "BUY" else rates["sell"]

    # 2) Native "Save As" sheet (silently stop when the user cancels)
    default_name = f"{curr_en}_CNY_7D_Trend_{time.strftime('%Y%m%d')}.png"
    save_path = prompt_save_filepath(default_name)
    if not save_path:
        return
    if not save_path.lower().endswith('.png'):
        save_path += '.png'

    # 3) Market series, rebased onto BOC's quoting basis
    try:
        ts, closes = fetch_yahoo_series(f"{curr_en}CNY=X")
        fitted = build_fitted_series(closes, b_end)
    except Exception as e:
        notify("Export Failed", f"Could not load {curr_en}/CNY series: {e}")
        return

    # 4) Render (this is where matplotlib / numpy finally get imported)
    try:
        render_trend_chart(save_path, ts, fitted, curr_en, side_label)
    except ImportError as e:
        missing = getattr(e, 'name', None) or e
        notify("Export Failed",
               f"Missing package '{missing}'. Run: {sys.executable} -m pip install --user matplotlib numpy")
        return
    except Exception as e:
        notify("Export Failed", str(e))
        return

    notify("Export Successful", f"{os.path.basename(save_path)} saved")

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
    elif action == "export_chart":
        # On-demand export: run dialog/scrape/render, then exit without writing config
        export_chart_flow(cfg)
        sys.exit(0)
    save_config(cfg)
    # SwiftBar Protocol: Exit settings actions immediately to prevent UI ghosting; 
    # force_refresh will bypass this and continue to main() for re-rendering.
    if action != "force_refresh":
        sys.exit(0)

# ================= Rendering Logic =================

def main(force_refresh=False):
    cfg = load_config()
    curr_cn, side = cfg["currency"], cfg["side"]
    data, err = get_data_with_cache(force=force_refresh)
    
    if not data or not data.get("rates"):
        print(f"⚠️ Connection Error")
        print("---")
        print(f"Check Internet Connection")
        print(f"Manual Refresh | bash='{SCRIPT_PATH}' param1='force_refresh' terminal=false refresh=true")
        return

    rates = data["rates"].get(curr_cn)
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
    # UI Logic: Prioritize 📡 satellite icon if network is unavailable (Offline Mode);
    # otherwise, follow the default alert icon or currency flag priority.
    status_icon = "📡" if err else (alert_icon or flag)
    print(f"{status_icon} {price:.2f}{alert_color}")
    
    # --- 2. Dropdown Menu ---
    print("---")
    if err:
        print(f"⚠️ Network Unavailable (Showing Cached Data) | color=orange")
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
        
    print("---")
    # No refresh=true on purpose: exporting only writes a file and changes no menu
    # state, so re-running the plugin afterwards would be wasted work.
    print(f"📈 Save 7-Day Trend Chart... | bash='{SCRIPT_PATH}' param1='export_chart' terminal=false")
    print("Open BoC Official Site | href=https://www.boc.cn/sourcedb/whpj/index.html")
    print(f"Manual Refresh | bash='{SCRIPT_PATH}' param1='force_refresh' terminal=false refresh=true")

if __name__ == "__main__":
    is_force = len(sys.argv) > 1 and sys.argv[1] == "force_refresh"
    main(force_refresh=is_force)