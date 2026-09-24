# 📈 BoC Exchange Rate Monitor for SwiftBar v2.1 (Stable)

A lightweight macOS status bar plugin designed to monitor real-time exchange rates using official Bank of China (BOC) data. This tool was built to bridge the gap between financial theory and practical engineering, specifically addressing the "Exchange Rate Anxiety" often felt by international students.

---

### 🚀 What's New in v2.1

* **7-Day Trend Chart Export**: High-resolution PNG export with lazy loading, linear regression trendlines, and BOC quote anchoring.
* **Offline-First Resilience**: Automatically switches to "Offline Mode" when the network drops. It displays the last cached valid rate with a satellite icon (**📡**) instead of showing error messages.
* **Power Efficiency**: Optimized refresh interval changed from 1m to **10m**, reducing CPU wake-ups and significantly extending MacBook battery life.
* **Graceful Error Handling**: Technical Python exceptions (like DNS timeouts) are masked with user-friendly status updates in the dropdown menu.
* **Enhanced State Sync**: Fixed the interactive command bridge to ensure that manual refreshes instantly trigger UI updates.
* **Professional Documentation**: Codebase updated with technical annotations covering Scraper logic, Persistence layers, and macOS Bridge protocols.

---

### 🚀 Key Features

* **Real-time Monitoring**: Automatically refreshes every **10 minutes** to capture the latest market moves.
* **Official Data**: Fetches data directly from the **Bank of China (BOC)** official site.
* **Multi-Currency Support**: Tracks **AUD, USD, EUR, GBP, JPY, HKD, CAD, and NZD** against **CNY**.
* **Smart Alerts**: Visual color cues (Red/Green) and icons (📈/📉) trigger when rates hit your custom thresholds.
* **Financial Insights**: Displays real-time **Bid-Ask Spread** and spread percentage to help assess true transaction costs.
* **7-Day Trend Chart**: Export a high-resolution PNG of the past 7 days straight from the dropdown, anchored to BOC's own quote.
* **Zero Dependency Core**: Monitoring, caching and alerts run on the Python standard library alone. Only the optional chart export needs `matplotlib` / `numpy`.

---

### 📈 7-Day Trend Chart Export

Pick **📈 Save 7-Day Trend Chart...** from the dropdown to render the last 7 days as a
high-resolution PNG (300 dpi), saved wherever you choose via the native "Save As" sheet.

The plotting stack is imported **lazily** — only when you actually click — so the regular
10-minute refresh cycle stays exactly as cheap as before.

**What you get**

* The past 7 days of hourly movement for the configured currency against CNY
* Start and end anchors labelled with date and rate
* A dashed linear-regression line — **red** when the trend is up, **green** when it is down
* A shaded area under the curve, with BOC's current quote as the closing anchor

**How the data is built**

Yahoo Finance supplies the market movement (`{CODE}CNY=X`, hourly, 7 days), which is then
rebased onto BOC's quoting basis. Note that BOC's historical rate endpoint has been retired
(it now sits behind a captcha), so only the **latest** BOC quote is used as an anchor and
the opening anchor is derived proportionally from the Yahoo series. Because Yahoo quotes a
single unit while BOC quotes 100, this rebase also absorbs that ~100x gap — the closing
point always lands exactly on the displayed BOC rate.

**Requirements**

Plotting needs `matplotlib` and `numpy`. They are imported lazily, so they only need to be
installed for the interpreter that actually runs the plugin. SwiftBar is started by
`launchd`, which does not always pick up conda/Homebrew shell setup — if the export reports
a missing package, the notification names the interpreter to install into:

```bash
# example: python.org build
"/Library/Frameworks/Python.framework/Versions/3.13/bin/python3" -m pip install --user matplotlib numpy
```

The first export takes roughly 10 seconds while matplotlib builds its font cache;
subsequent exports are fast.

---

### 🛠 Installation

1.  **Software**: Install [SwiftBar](https://github.com/swiftbar/SwiftBar).
    **Special thanks to the SwiftBar team for providing such a versatile platform for developers.**
3.  **Download**: Place `Boc_Rates.10m.py` into your SwiftBar plugin folder.
4.  **Permissions**: Run the following in your Terminal to make the script executable:
    ```bash
    chmod +x Boc_Rates.10m.py
    ```
5.  **Run**: Open SwiftBar and select the plugin folder.

---

### 👨‍💻 About the Author

**Devon Peng**
* Master of Commerce in Finance & FinTech @ **UNSW**.
* Passionate about quantitative finance and building automation tools for financial decision-making.

---

### 📄 License

This project is licensed under the **MIT License**.
