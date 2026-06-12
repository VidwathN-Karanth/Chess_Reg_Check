# Chess Registration Verifier

Chess Registration Verifier is a professional, standalone Windows desktop application designed to quickly verify chess players' membership status on the **Karnataka State Chess Association (KSCA)** and the **All India Chess Federation (AICF)** portals.

This application is packaged as a single executable containing all dependencies—including its own secure Chromium web browser engine—so you can run it instantly on any Windows machine without installing Python or setting up drivers.

---

## 🚀 How to Run the Application (Executable)

1. **Extract/Move the Folder**: Keep this `README.md` file and `ChessVerifier.exe` in the same directory.
2. **Double-click `ChessVerifier.exe`**: 
   - When run, the application will boot directly into the GUI dashboard.
   - *Note: On the very first launch, Windows SmartScreen or your antivirus might show a warning because the executable is compiled from source and unsigned. Simply click "More Info" and select "Run Anyway."*

---

## 💻 Running from Source Code (Alternative)

If you want to run the application directly from the Python source code instead of using the compiled `.exe`, follow these terminal instructions:

### Prerequisites
- Install **Python 3.10+** (Python 3.13 is highly recommended for compatibility). Ensure you check the box **"Add Python to PATH"** during installation.

### Step-by-Step Setup

1. **Open your Terminal / Command Prompt** and navigate to the project directory:
   ```bash
   cd f:\Chess
   ```

2. **Create a Python Virtual Environment**:
   ```bash
   python -m venv .venv
   ```

3. **Activate the Virtual Environment**:
   - **Windows Command Prompt**:
     ```cmd
     .venv\Scripts\activate.bat
     ```
   - **Windows PowerShell**:
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
   - **macOS / Linux**:
     ```bash
     source .venv/bin/activate
     ```

4. **Install Required Packages**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Install Playwright Browser Engine**:
   ```bash
   playwright install chromium
   ```

6. **Run the Application**:
   ```bash
   python app.py
   ```

---

## 📂 Features & Layout

### 1. Dual-Portal Verification Tabs
- **KSCA Verification Tab**: Queries player database records on the official KSCA search portal.
- **AICF Verification Tab**: Queries records on the official AICF players portal.

### 2. Side-by-Side Dashboard Layout
- **Left Panel (Inputs & Controls)**:
  - **Player ID Input Box**: Paste multiple Chess IDs (one per line) that you want to check.
  - **Verify All Button**: Begins the automated verification run.
  - **Cancel Verification Button**: Aborts the run safely.
  - **Clear Input & Results Button**: Resets the window back to its default state.
- **Right Panel (Live Output Table & Progress)**:
  - **Results Table**: Displays the Player ID, Scraped Full Name, and Membership Status in real-time as they finish checking.
    - 🟢 **Active** (Green): Registered active member.
    - 🔴 **Inactive** (Red): Membership is expired or not active.
    - 🔴 **Not Found** (Red): No record exists for this ID.
  - **Live Progress Bar**: Shows the percentage of completed items and keeps the UI stable.
  - **Time Estimation Indicators**: Shows real-time **Elapsed Time** and dynamically predicts the **Estimated Remaining Time** based on your network response speeds.
- **Bottom Panel (System Console)**:
  - Prints real-time log statements for every action (e.g. launching browser context, navigating pages, processing forms), allowing you to see what the scraper is doing.

---

## 🔍 How to Format Player IDs

To verify memberships accurately, format your input list in the text box as follows:

### A. KSCA Portal
- Input one KSCA ID or registration number per line (e.g. `38135` or `38135KSCA2027`).
- KSCA verification runs in **Bulk Mode**—it queries all your entered IDs at once and extracts names and active statuses directly from the directory tables.

### B. AICF Portal
- Input one AICF ID per line (e.g. `12345`).
- AICF verification runs sequentially with optimized fast-polling, inspecting the search database for each individual profile.

---

## 💾 Exporting Results

Once verification is complete:
1. Click the **Export to CSV** button at the top-right of the results pane.
2. Select a location on your computer and save the file.
3. The exported spreadsheet will contain:
   - **Chess Player ID**
   - **Scraped Full Name**
   - **Verification Status**

---

## 🛠️ Troubleshooting

- **GUI is slow or frozen**: The browser scraping runs entirely in a separate background thread, meaning the Tkinter GUI window will never freeze. You can move the window or click "Cancel" at any time.
- **Network timeouts / Not Found errors**: Ensure you have an active internet connection. If the state chess association or national federation website is down, the application will display `Error (Timeout)` or fail gracefully and log the issue in the console.
- **Stealth and Rate-Limiting**: The application employs standard browser stealth contexts and polite delays between requests to bypass bot blockages and protect your IP address from rate limits.
