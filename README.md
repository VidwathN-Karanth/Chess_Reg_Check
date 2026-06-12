# ChessCheck

> **⬇️ To run this application, go to the [Releases](../../releases) section on the right side of this page, open **v1.0.0 Initial Release (Latest)**, and download `ChessCheck.exe` under Assets. Double-click it to launch — no installation needed.**

---

ChessCheck is a standalone Windows desktop application to verify chess players' membership status on the **Karnataka State Chess Association (KSCA)** and **All India Chess Federation (AICF)** portals. It runs as a single `.exe` with no Python or setup required.

---

## 🧩 The Problem

Organizing a chess tournament in Karnataka involves verifying every participant's membership with both the Karnataka State Chess Association (KSCA) and the All India Chess Federation (AICF). Traditionally, organizers have to open each website manually, type in every player's ID one by one, wait for the page to load, read the result, and note it down — repeating this for every single participant. For a tournament with 50, 100, or even 200 players, this process can take hours, is highly prone to human error, and often causes delays in registration and pairing. There is no official tool provided by KSCA or AICF to do this in bulk.

ChessCheck was built to solve exactly this. Instead of spending hours on manual lookups, an organizer can paste all player IDs at once, click a single button, and get a complete verified list with names and active/inactive status within minutes — ready to export and use.

---

## ⬇️ Download & Run

1. Go to the **Releases** section on the right side of this page
2. Click **v1.0.0 Initial Release (Latest)**
3. Under **Assets**, download `ChessCheck.exe`
4. Double-click to launch

> **Note:** Windows SmartScreen may show a warning on first launch. Click **"More Info" → "Run Anyway"** to proceed. The app is safe — it is unsigned because it is compiled from source.

---

## 💻 Features

- **KSCA Tab** — Verify players on the Karnataka State Chess Association portal
- **AICF Tab** — Verify players on the All India Chess Federation portal
- **Bulk Input** — Paste multiple IDs at once (one per line)
- **Live Results Table** — Shows Player ID, Full Name, and Status in real time
  - 🟢 **Active** — Registered active member
  - 🔴 **Inactive** — Membership expired or not active
  - 🔴 **Not Found** — No record exists for this ID
- **Progress Bar** — Tracks verification progress with elapsed and estimated remaining time
- **Export to CSV** — Save the full results as a spreadsheet

---

## 🔍 How to Use

1. Open `ChessCheck.exe`
2. Select the **KSCA** or **AICF** tab
3. Paste player IDs into the input box (one ID per line)
4. Click **Verify All**
5. View live results in the table as each player is checked
6. Click **Export to CSV** to save the report

---

## 🛠️ Troubleshooting

- **SmartScreen warning on launch** — Click "More Info" → "Run Anyway"
- **Site not responding** — Check your internet connection. If KSCA or AICF website is down, the app will show `Error (Timeout)`
- **Player not found** — Double-check the ID and ensure the player is registered on that portal

---

## 🏛️ Portals Used

| Association | Website |
|---|---|
| KSCA — Karnataka State Chess Association | https://karnatakachess.com/player-search/ |
| AICF — All India Chess Federation | https://prs.aicf.in/players |
