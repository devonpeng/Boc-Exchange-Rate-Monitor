# 📈 BoC Exchange Rate Monitor for SwiftBar

A lightweight macOS status bar plugin designed to monitor real-time exchange rates using official Bank of China (BOC) data. This tool was built to bridge the gap between financial theory and practical engineering, specifically addressing the "Exchange Rate Anxiety" often felt by international students.

---

### 🚀 Key Features

* **Real-time Monitoring**: Automatically refreshes every **1 minute** to capture the latest market moves.
* **Official Data**: Fetches data directly from the **Bank of China (BOC)** official site.
* **Multi-Currency Support**: Tracks **AUD, USD, EUR, GBP, JPY, HKD, CAD, and NZD** against **CNY**.
* **Smart Alerts**: Visual color cues (Red/Green) and icons (📈/📉) trigger when rates hit your custom thresholds.
* **Financial Insights**: Displays real-time **Bid-Ask Spread** and spread percentage to help assess true transaction costs.
* **Zero Dependency**: Built purely with Python standard libraries—no external packages required.

---

### 🛠 Installation

1.  **Software**: Install [SwiftBar](https://github.com/swiftbar/SwiftBar).
    **Special thanks to the SwiftBar team for providing such a versatile platform for developers.
3.  **Download**: Place `Boc_Rates.1m.py` into your SwiftBar plugin folder.
4.  **Permissions**: Run the following in your Terminal to make the script executable:
    ```bash
    chmod +x Boc_Rates.1m.py
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
