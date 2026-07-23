import os
import sys

# Point Playwright to the bundled browser directory if running inside PyInstaller executable
if getattr(sys, 'frozen', False):
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(sys._MEIPASS, "ms-playwright")

# Try to make the application high-DPI aware on Windows
if sys.platform == "win32":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

import asyncio
import csv
import logging
import queue
import random
import threading
import time
import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter import ttk
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# ==========================================
#  Logging Configuration
# ==========================================
logger = logging.getLogger("ChessCheck")
logger.setLevel(logging.INFO)

# ==========================================
BG_DARK = "#f5f3f0"       # Creme/light gray base background
BG_CARD = "#ffffff"       # Pure white panel background
FG_LIGHT = "#212529"      # Dark charcoal text
FG_MUTED = "#6c757d"      # Medium gray text
ACCENT = "#1a73e8"        # Google blue accent
ACCENT_HOVER = "#1557b0"  # Hover accent
SUCCESS = "#137333"       # Forest green for active
WARNING = "#b06000"       # Inactive yellow/amber
DANGER = "#c5221f"        # Crimson red for inactive / error
BORDER_COLOR = "#dadce0"  # Light gray border
BG_TEXT = "#ffffff"       # Background for text boxes
CONSOLE_BG = "#f8f9fa"    # Background for logs

# ==========================================
#  Helpers
# ==========================================

def normalize_id(id_str):
    """Removes all non-alphanumeric characters and converts to lowercase."""
    return "".join(c for c in id_str if c.isalnum()).lower()

def match_ids(query_id, cell_id):
    """Robustly compares two IDs for equality or numeric prefix matching."""
    q_norm = normalize_id(query_id)
    c_norm = normalize_id(cell_id)
    if not q_norm or not c_norm:
        return False
    if q_norm == c_norm:
        return True
    # If query is purely numeric (e.g. 32194), it should match cell_id prefix (e.g. 32194ksca2026)
    if q_norm.isdigit() and c_norm.startswith(q_norm):
        return True
    return False


# ==========================================
#  Scraping Routines
# ==========================================

async def scrape_ksca(ids, result_queue, stop_event):
    """
    Scrapes KSCA player search page in bulk.
    URL: https://karnatakachess.com/player-search/
    """
    result_queue.put(('log', "Initializing browser for KSCA (Bulk Mode)..."))
    result_queue.put(('progress_step', 10, "Initializing browser context..."))
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)
            
            result_queue.put(('log', "Navigating to KSCA Player Search portal..."))
            result_queue.put(('progress_step', 30, "Navigating to KSCA player directory..."))
            await page.goto("https://karnatakachess.com/player-search/", wait_until="domcontentloaded", timeout=60000)
            
            # Wait for the bulk textarea to load (there's only one textarea on the page)
            await page.wait_for_selector("textarea", timeout=15000)
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            
            result_queue.put(('log', "Page loaded. Pasting IDs into Bulk search..."))
            result_queue.put(('progress_step', 50, "Pasting player IDs into Bulk search..."))
            
            # Prepare comma separated list of IDs
            clean_ids = [pid.strip() for pid in ids if pid.strip()]
            bulk_text = ", ".join(clean_ids)
            
            # Fill textarea
            await page.fill("textarea", bulk_text)
            await asyncio.sleep(0.3)
            
            result_queue.put(('start', len(clean_ids)))
            
            # Click search and wait for the API response with up to 3 retries
            response_received = False
            for attempt in range(1, 4):
                if stop_event.is_set():
                    break
                try:
                    result_queue.put(('log', f"Submitting bulk query (Attempt {attempt}/3)..."))
                    result_queue.put(('progress_step', 60, f"Submitting query (Attempt {attempt})..."))
                    
                    async with page.expect_response(
                        lambda r: "portal.karnatakachess.com/api/players" in r.url and "bulk_ksca" in r.url,
                        timeout=15000
                    ) as response_info:
                        # Click the search button specifically for the bulk container
                        # Fallback chain to find the correct search button next to the textarea
                        button_clicked = False
                        for selector in [
                            'div:has-text("Bulk KSCA IDs") button',
                            'textarea ~ button',
                            'div.v-input:has(textarea) button'
                        ]:
                            try:
                                btn = page.locator(selector).first
                                if await btn.is_visible():
                                    await btn.click()
                                    button_clicked = True
                                    break
                            except Exception:
                                continue
                                
                        if not button_clicked:
                            try:
                                # Fallback using relative DOM position
                                btn = page.locator("textarea").locator("xpath=../..").locator("button").first
                                await btn.click()
                                button_clicked = True
                            except Exception:
                                result_queue.put(('log', "Warning: could not click search button, pressing Enter instead..."))
                                await page.focus("textarea")
                                await page.keyboard.press("Enter")
                    
                    response = await response_info.value
                    if response.status == 200 or response.status == 201:
                        response_received = True
                        result_queue.put(('log', "Search results successfully loaded from server."))
                        break
                    else:
                        result_queue.put(('log', f"Server returned error code {response.status}. Retrying..."))
                except Exception as e:
                    result_queue.put(('log', f"Attempt {attempt} failed or timed out: {str(e)}"))
                    if attempt < 3:
                        await asyncio.sleep(2.0)
            
            if not response_received:
                raise Exception("Failed to fetch search results from KSCA server after 3 attempts.")
            
            # Give Javascript half a second to render the table rows in the DOM
            await asyncio.sleep(0.5)
            
            # Read all matches page-by-page
            results_map = {}
            page_num = 1
            
            while not stop_event.is_set():
                result_queue.put(('log', f"Reading results on page {page_num}..."))
                result_queue.put(('progress_step', 85, f"Reading database results (Page {page_num})..."))
                
                # Retrieve rows
                rows = await page.query_selector_all("table tbody tr")
                if len(rows) == 0:
                    break
                if len(rows) == 1:
                    row_text = await rows[0].inner_text()
                    if "No data available" in row_text or "No matching records" in row_text:
                        break
                
                # Parse current page rows
                for row in rows:
                    cells = await row.query_selector_all("td")
                    if len(cells) >= 6:
                        cell_id = (await cells[0].inner_text()).strip()
                        name = (await cells[1].inner_text()).strip()
                        district = (await cells[2].inner_text()).strip() or "N/A"
                        status = (await cells[5].inner_text()).strip()
                        
                        if "inactive" in status.lower() or "in-active" in status.lower():
                            status_str = "Inactive"
                        elif "active" in status.lower():
                            status_str = "Active"
                        else:
                            status_str = status
                        
                        # Match with query IDs (exact or exact numeric match)
                        for pid in clean_ids:
                            if match_ids(pid, cell_id):
                                results_map[pid] = (name, district, status_str)
                
                # Check for "Next page" button
                next_btn = await page.query_selector("button.v-pagination__next, button[aria-label*='Next'], button[aria-label*='next']")
                if next_btn:
                    is_disabled = await next_btn.get_attribute("disabled")
                    class_attr = await next_btn.get_attribute("class") or ""
                    if is_disabled is not None or "disabled" in class_attr:
                        break
                    else:
                        page_num += 1
                        page_loaded = False
                        
                        for attempt in range(1, 4):
                            try:
                                async with page.expect_response("**/api/players*", timeout=10000) as response_info:
                                    await next_btn.click()
                                response = await response_info.value
                                if response.status == 200 or response.status == 201:
                                    page_loaded = True
                                    break
                            except Exception as e:
                                result_queue.put(('log', f"Pagination transition attempt {attempt} timed out or failed: {str(e)}"))
                                if attempt < 3:
                                    await asyncio.sleep(1.0)
                        
                        if not page_loaded:
                            raise Exception(f"Failed to navigate to page {page_num} on KSCA website.")
                        
                        # Allow React/Vue pagination rendering
                        await asyncio.sleep(0.5)
                else:
                    break
            
            result_queue.put(('progress_step', 95, "Compiling and presenting results..."))
            
            # Emit findings in order
            result_queue.put(('progress_step', 100, "Compiling and presenting results..."))
            for idx, pid in enumerate(clean_ids):
                if pid in results_map:
                    name, district, status = results_map[pid]
                    result_queue.put(('result', 'ksca', pid, name, district, status))
                    result_queue.put(('log', f"ID {pid} Found: {name} | {district} ({status})"))
                else:
                    result_queue.put(('result', 'ksca', pid, "N/A", "N/A", "Not Found"))
                    result_queue.put(('log', f"ID {pid}: Not Found"))
                    
            await browser.close()
            result_queue.put(('done', None))
    except Exception as e:
        logger.exception("KSCA bulk scraping loop failed")
        result_queue.put(('error', f"Fatal: {str(e)}"))

# ----------------------------------------------------

def fetch_aicf_player_sync(player_id, max_retries=5, timeout=15):
    import json
    import ssl
    import urllib.request
    import time
    
    url = f"https://admin.aicf.in/api/players?name={player_id}&state=0&city=0"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://prs.aicf.in",
        "Referer": "https://prs.aicf.in/"
    }
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as response:
                if response.status == 200:
                    body = response.read().decode('utf-8')
                    res_json = json.loads(body)
                    # If empty dataset returned, retry as it could be a transient DB load/empty state
                    if not res_json.get("data") and attempt < max_retries:
                        sleep_time = 2.0 * attempt
                        logger.info(f"Attempt {attempt} for ID {player_id} returned empty data. Retrying in {sleep_time}s...")
                        time.sleep(sleep_time)
                        continue
                    return res_json
                else:
                    raise Exception(f"HTTP Status {response.status}")
        except Exception as e:
            last_err = e
            logger.info(f"Attempt {attempt} for ID {player_id} failed: {e}")
            if attempt < max_retries:
                # Sleep progressively longer to bypass transient rate limits/load
                sleep_time = 3.0 * attempt
                time.sleep(sleep_time)
    
    if last_err:
        raise last_err
    return {"status": "ok", "data": []}

async def scrape_aicf(ids, result_queue, stop_event, sleep_delay=0.0):
    """
    Queries AICF backend players API directly with fast polling.
    URL: https://admin.aicf.in/api/players
    """
    result_queue.put(('log', "Initializing AICF API search connection..."))
    result_queue.put(('progress_step', 15, "API connection ready. Starting search..."))
    
    try:
        for idx, player_id in enumerate(ids):
            if stop_event.is_set():
                result_queue.put(('log', "Scraping cancelled by user."))
                break
            
            player_id = player_id.strip()
            if not player_id:
                continue
            
            result_queue.put(('progress', idx + 1, player_id))
            result_queue.put(('log', f"Searching AICF ID: {player_id} ({idx+1}/{len(ids)})"))
            
            try:
                # Fetch data directly from the server API with retries
                data_response = await asyncio.to_thread(fetch_aicf_player_sync, player_id)
                
                players = data_response.get("data", [])
                found = False
                
                for player in players:
                    cell_id = player.get("aicf_id", "").strip()
                    
                    if match_ids(player_id, cell_id):
                        first_name = player.get("first_name") or ""
                        middle_name = player.get("middle_name") or ""
                        last_name = player.get("last_name") or ""
                        
                        # Format full name nicely
                        name_parts = [first_name, middle_name, last_name]
                        full_name = " ".join([p.strip() for p in name_parts if p and p.strip()]).strip()
                        if not full_name:
                            full_name = "Unknown"
                            
                        state = player.get("state_name") or "N/A"
                        district = player.get("city_name") or player.get("district_name") or "N/A"
                        
                        membership_status = player.get("membership_status")
                        if membership_status is True:
                            status_str = "Active"
                        elif membership_status is False:
                            status_str = "Inactive"
                        else:
                            status_str = "Unknown"
                            
                        result_queue.put(('result', 'aicf', player_id, full_name, state, district, status_str))
                        result_queue.put(('log', f"ID {player_id} Found: {full_name} | {state} | {district} ({status_str})"))
                        found = True
                        break
                
                if not found:
                    result_queue.put(('result', 'aicf', player_id, "N/A", "N/A", "N/A", "Not Found"))
                    result_queue.put(('log', f"ID {player_id}: Not Found"))
                    
            except Exception as e:
                logger.error(f"Error scraping AICF ID {player_id}: {str(e)}")
                result_queue.put(('result', 'aicf', player_id, "Error (Timeout)", "N/A", "N/A", "Error"))
                result_queue.put(('log', f"ID {player_id}: Connection or API error occurred: {str(e)}"))
            
            # Apply configured delay
            if sleep_delay > 0:
                await asyncio.sleep(sleep_delay)
                
        result_queue.put(('done', None))
    except Exception as e:
        logger.exception("AICF main scraping loop failed")
        result_queue.put(('error', f"Fatal: {str(e)}"))

# ==========================================
#  Scraping Worker Thread
# ==========================================

class ScrapingWorker(threading.Thread):
    def __init__(self, ids, site_type, result_queue):
        super().__init__()
        self.ids = ids
        self.site_type = site_type
        self.result_queue = result_queue
        self.stop_event = threading.Event()
        self.loop = None

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            if self.site_type == 'ksca':
                self.loop.run_until_complete(scrape_ksca(self.ids, self.result_queue, self.stop_event))
            elif self.site_type == 'aicf':
                self.loop.run_until_complete(scrape_aicf(self.ids, self.result_queue, self.stop_event))
        except Exception as e:
            self.result_queue.put(('error', f"Worker error: {str(e)}"))
        finally:
            self.loop.close()

    def stop(self):
        self.stop_event.set()


# ==========================================
#  Tkinter Application GUI
# ==========================================

class ChessCheckApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ChessCheck v1.2 (Dynamic Pagination)")
        self.root.geometry("1000x650")
        self.root.minsize(900, 550)
        self.root.configure(bg=BG_DARK)
        
        # Result queues and state variables
        self.result_queue = queue.Queue()
        self.worker = None
        self.is_running = False
        self.total_ids = 0
        self.start_time = None
        self.completed_ids = 0
        self.current_pct = 0
        self.current_status_text = "Idle"
        self.active_tab = None
        
        # Set window icon if any, otherwise skip
        # App layout components
        self.setup_styles()
        self.build_ui()
        self.start_queue_poller()

    def setup_styles(self):
        """Sets up custom premium style configuration using TTK Clam theme."""
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Base backgrounds & frames
        self.style.configure("TFrame", background=BG_DARK)
        self.style.configure("Card.TFrame", background=BG_CARD, borderwidth=1, relief="solid")
        
        # Labels
        self.style.configure("TLabel", background=BG_DARK, foreground=FG_LIGHT, font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", background=BG_DARK, foreground=ACCENT, font=("Segoe UI", 18, "bold"))
        self.style.configure("Sub.TLabel", background=BG_DARK, foreground=FG_MUTED, font=("Segoe UI", 9, "italic"))
        self.style.configure("Card.TLabel", background=BG_CARD, foreground=FG_LIGHT, font=("Segoe UI", 10, "bold"))
        self.style.configure("Console.TLabel", background=BG_DARK, foreground=ACCENT, font=("Segoe UI", 9, "bold"))
        self.style.configure("Footer.TLabel", background=BG_DARK, foreground=FG_MUTED, font=("Segoe UI", 8, "italic"))
        
        # Buttons
        self.style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", font=("Segoe UI", 10, "bold"), borderwidth=0, focuscolor=ACCENT)
        self.style.map("Accent.TButton", background=[("active", ACCENT_HOVER)])
        
        self.style.configure("Secondary.TButton", background=BG_CARD, foreground=FG_LIGHT, font=("Segoe UI", 10), borderwidth=1, bordercolor=BORDER_COLOR)
        self.style.map("Secondary.TButton", background=[("active", "#f1f3f4")])
        
        self.style.configure("Danger.TButton", background=DANGER, foreground="#ffffff", font=("Segoe UI", 10, "bold"), borderwidth=0, focuscolor=DANGER)
        self.style.map("Danger.TButton", background=[("active", "#b31b1b")])

        # Notebook / Tabs
        self.style.configure("TNotebook", background=BG_DARK, borderwidth=0)
        self.style.configure("TNotebook.Tab", background="#e8e6e3", foreground=FG_MUTED, font=("Segoe UI", 10, "bold"), padding=[16, 6])
        self.style.map("TNotebook.Tab", 
                       background=[("selected", BG_DARK)], 
                       foreground=[("selected", ACCENT)])

        # Treeview (Table)
        # Calculate dynamic row height based on font metrics to support DPI scaling properly
        from tkinter.font import Font
        tree_font = Font(font=("Segoe UI", 10))
        font_height = tree_font.metrics("linespace")
        row_height = font_height + 10  # generous padding for a clean aesthetic
        
        self.style.configure("Treeview", background=BG_CARD, fieldbackground=BG_CARD, foreground=FG_LIGHT, font=("Segoe UI", 10), rowheight=row_height, borderwidth=1, bordercolor=BORDER_COLOR)
        self.style.configure("Treeview.Heading", background=BG_DARK, foreground=FG_LIGHT, font=("Segoe UI", 10, "bold"), borderwidth=1, bordercolor=BORDER_COLOR)
        self.style.map("Treeview", 
                       background=[("selected", ACCENT)], 
                       foreground=[("selected", "#ffffff")])

        # Progressbar
        self.style.configure("TProgressbar", thickness=8, troughcolor=BG_DARK, background=ACCENT, borderwidth=0)

    def build_ui(self):
        """Constructs the application layout."""
        # Top Title Header Banner
        header_frame = ttk.Frame(self.root, padding=(20, 15, 20, 10))
        header_frame.pack(fill="x")
        
        title_lbl = ttk.Label(header_frame, text="ChessCheck", style="Header.TLabel")
        title_lbl.pack(anchor="w")
        
        subtitle_lbl = ttk.Label(header_frame, text="Verify active memberships on Karnataka State Chess Association (KSCA) and All India Chess Federation (AICF)", style="Sub.TLabel")
        subtitle_lbl.pack(anchor="w")
        
        # Bottom Footer
        footer_frame = ttk.Frame(self.root, padding=(10, 0, 20, 5))
        footer_frame.pack(fill="x", side="bottom")
        developer_lbl = ttk.Label(footer_frame, text="Developed by Vidwath N Karanth", style="Footer.TLabel")
        developer_lbl.pack(side="right")
        
        # Bottom Console Log Area
        console_frame = ttk.Frame(self.root, padding=(10, 5, 10, 10))
        console_frame.pack(fill="x", side="bottom")
        
        console_lbl = ttk.Label(console_frame, text="SYSTEM LOGGER CONSOLE", style="Console.TLabel")
        console_lbl.pack(anchor="w", padx=10)
        
        self.log_text = tk.Text(console_frame, height=5, bg=CONSOLE_BG, fg=FG_LIGHT, insertbackground=FG_LIGHT, font=("Consolas", 9), relief="solid", borderwidth=1, highlightthickness=0, state="disabled", padx=8, pady=8)
        self.log_text.pack(fill="x", padx=10, pady=5)

        # Tabs Notebook
        self.notebook = ttk.Notebook(self.root, padding=10)
        self.notebook.pack(fill="both", expand=True)
        
        # Initialize KSCA & AICF verification frames
        self.ksca_frame = ttk.Frame(self.notebook)
        self.aicf_frame = ttk.Frame(self.notebook)
        
        self.notebook.add(self.ksca_frame, text="  KSCA Verification  ")
        self.notebook.add(self.aicf_frame, text="  AICF Verification  ")
        
        # Build contents inside both tabs
        self.build_tab_content(self.ksca_frame, "ksca")
        self.build_tab_content(self.aicf_frame, "aicf")

    def build_tab_content(self, parent, site_type):
        """Constructs a standardized side-by-side dashboard structure inside a tab."""
        parent.columnconfigure(0, weight=1)  # Left column (Input & Controls)
        parent.columnconfigure(1, weight=2)  # Right column (Results Table)
        parent.rowconfigure(0, weight=1)
        
        # ----------------------------------------------------
        # Left Panel (Input / Controls)
        # ----------------------------------------------------
        left_panel = ttk.Frame(parent, style="Card.TFrame", padding=15)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(5, 10), pady=5)
        
        input_lbl = ttk.Label(left_panel, text="Enter Player IDs (one per line):", style="Card.TLabel")
        input_lbl.pack(anchor="w", pady=(0, 5))
        
        # Button controls layout (pack at the bottom first so it remains visible)
        btn_frame = ttk.Frame(left_panel, style="Card.TFrame")
        btn_frame.pack(side="bottom", fill="x", pady=(10, 0))
        
        verify_btn = ttk.Button(
            btn_frame, 
            text="Verify All", 
            style="Accent.TButton", 
            command=lambda: self.start_verification(site_type)
        )
        verify_btn.pack(fill="x", pady=2)
        
        cancel_btn = ttk.Button(
            btn_frame, 
            text="Cancel Verification", 
            style="Danger.TButton", 
            command=self.cancel_verification,
            state="disabled"
        )
        cancel_btn.pack(fill="x", pady=2)
        
        clear_btn = ttk.Button(
            btn_frame, 
            text="Clear Input & Results", 
            style="Secondary.TButton", 
            command=lambda: self.clear_views(site_type)
        )
        clear_btn.pack(fill="x", pady=2)
        
        # Keep button references
        if site_type == 'ksca':
            self.ksca_verify_btn = verify_btn
            self.ksca_cancel_btn = cancel_btn
            self.ksca_clear_btn = clear_btn
        else:
            self.aicf_verify_btn = verify_btn
            self.aicf_cancel_btn = cancel_btn
            self.aicf_clear_btn = clear_btn

        # Scrollable Text box for player IDs (pack to fill remaining space)
        text_container = ttk.Frame(left_panel)
        text_container.pack(fill="both", expand=True, pady=5)
        
        text_box = tk.Text(text_container, bg=BG_TEXT, fg=FG_LIGHT, insertbackground=FG_LIGHT, font=("Consolas", 10), relief="solid", borderwidth=1, highlightthickness=0, padx=8, pady=8)
        text_box.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(text_container, orient="vertical", command=text_box.yview)
        scrollbar.pack(side="right", fill="y")
        text_box.configure(yscrollcommand=scrollbar.set)
        
        # Keep references to input boxes
        if site_type == 'ksca':
            self.ksca_input = text_box
        else:
            self.aicf_input = text_box

        # ----------------------------------------------------
        # Right Panel (Results Table)
        # ----------------------------------------------------
        right_panel = ttk.Frame(parent, padding=5)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 5), pady=5)
        
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)
        
        # Progress & Action Bar above table
        top_bar = ttk.Frame(right_panel)
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        
        progress_lbl = ttk.Label(top_bar, text="Results Output", font=("Segoe UI", 11, "bold"))
        progress_lbl.pack(side="left", anchor="w")
        
        export_btn = ttk.Button(
            top_bar, 
            text="Export to CSV", 
            style="Secondary.TButton", 
            command=lambda: self.export_results(site_type)
        )
        export_btn.pack(side="right", anchor="e")
        
        if site_type == 'ksca':
            self.ksca_progress_lbl = progress_lbl
            self.ksca_export_btn = export_btn
        else:
            self.aicf_progress_lbl = progress_lbl
            self.aicf_export_btn = export_btn
            
        # Table (Treeview)
        table_container = ttk.Frame(right_panel, style="Card.TFrame")
        table_container.grid(row=1, column=0, sticky="nsew")
        
        if site_type == 'ksca':
            columns = ("id", "name", "district", "status")
            tree = ttk.Treeview(table_container, columns=columns, show="headings", selectmode="browse")
            tree.pack(side="left", fill="both", expand=True)
            
            tree.heading("id", text="Player ID")
            tree.heading("name", text="Full Name")
            tree.heading("district", text="District")
            tree.heading("status", text="Membership Status")
            
            tree.column("id", width=120, anchor="center")
            tree.column("name", width=250, anchor="w")
            tree.column("district", width=150, anchor="center")
            tree.column("status", width=150, anchor="center")
        else:
            columns = ("id", "name", "state", "district", "status")
            tree = ttk.Treeview(table_container, columns=columns, show="headings", selectmode="browse")
            tree.pack(side="left", fill="both", expand=True)
            
            tree.heading("id", text="Player ID")
            tree.heading("name", text="Full Name")
            tree.heading("state", text="State")
            tree.heading("district", text="District")
            tree.heading("status", text="Membership Status")
            
            tree.column("id", width=120, anchor="center")
            tree.column("name", width=220, anchor="w")
            tree.column("state", width=130, anchor="center")
            tree.column("district", width=130, anchor="center")
            tree.column("status", width=150, anchor="center")
        
        # Custom scrollbar for table
        table_scroll = ttk.Scrollbar(table_container, orient="vertical", command=tree.yview)
        table_scroll.pack(side="right", fill="y")
        tree.configure(yscrollcommand=table_scroll.set)
        
        # Status Color Tags
        tree.tag_configure("Active", foreground=SUCCESS)
        tree.tag_configure("Inactive", foreground=DANGER)
        tree.tag_configure("Not Found", foreground=DANGER)
        tree.tag_configure("Error", foreground=DANGER)
        
        if site_type == 'ksca':
            self.ksca_tree = tree
        else:
            self.aicf_tree = tree
            
        # Live ProgressBar
        prog_bar = ttk.Progressbar(right_panel, style="TProgressbar", orient="horizontal", mode="determinate")
        prog_bar.grid(row=2, column=0, sticky="ew", pady=(10, 2))
        prog_bar.configure(value=0)
        
        if site_type == 'ksca':
            self.ksca_progress_bar = prog_bar
        else:
            self.aicf_progress_bar = prog_bar

    # ==========================================
    #  Event Handlers & Logic
    # ==========================================

    def log(self, message):
        """Appends log statements safely to the bottom text console."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{threading.current_thread().name}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def start_verification(self, site_type):
        """Fetches the IDs entered in the UI, checks states, and boots the scraper worker thread."""
        if self.is_running:
            return
            
        # Retrieve IDs
        input_widget = self.ksca_input if site_type == 'ksca' else self.aicf_input
        raw_text = input_widget.get("1.0", "end-1c")
        player_ids = [line.strip() for line in raw_text.splitlines() if line.strip()]
        
        if not player_ids:
            messagebox.showwarning("Empty List", "Please enter at least one Chess ID to verify.")
            return
            
        # Disable/Enable appropriate controls
        self.is_running = True
        self.total_ids = len(player_ids)
        self.active_tab = site_type
        
        # Clear old rows in tree
        tree = self.ksca_tree if site_type == 'ksca' else self.aicf_tree
        for child in tree.get_children():
            tree.delete(child)
            
        # Toggle GUI states
        self.toggle_gui_state(site_type, is_scraping=True)
        
        # Reset progress components
        self.start_time = time.time()
        self.completed_ids = 0
        self.current_pct = 0
        self.current_status_text = "Initializing browser..."
        self.active_tab = site_type
        
        prog_bar = self.ksca_progress_bar if site_type == 'ksca' else self.aicf_progress_bar
        prog_bar.grid(row=2, column=0, sticky="ew", pady=(10, 2))
        prog_bar.configure(mode="determinate")
        prog_bar['value'] = 0
        prog_bar['maximum'] = 100
        
        # Start the timer loop
        self.update_timer_loop()
        
        # Launch Threaded Worker
        self.worker = ScrapingWorker(player_ids, site_type, self.result_queue)
        self.worker.start()

    def cancel_verification(self):
        """Signals the running scraping worker to shut down."""
        if self.worker and self.worker.is_alive():
            self.worker.stop()
            self.log("Cancellation signal sent to browser thread...")

    def clear_views(self, site_type):
        """Resets the ID inputs and table outputs for a given tab."""
        # Clean text editor
        text_widget = self.ksca_input if site_type == 'ksca' else self.aicf_input
        text_widget.delete("1.0", "end")
        
        # Clean tree view
        tree = self.ksca_tree if site_type == 'ksca' else self.aicf_tree
        for child in tree.get_children():
            tree.delete(child)
            
        # Reset labels
        lbl = self.ksca_progress_lbl if site_type == 'ksca' else self.aicf_progress_lbl
        lbl.configure(text="Results Output")
        
        # Reset progressbar
        prog = self.ksca_progress_bar if site_type == 'ksca' else self.aicf_progress_bar
        prog.configure(value=0)

    def toggle_gui_state(self, site_type, is_scraping=True):
        """Handles widget activation/deactivation during scraping runs."""
        # Elements to change
        verify_btn = self.ksca_verify_btn if site_type == 'ksca' else self.aicf_verify_btn
        cancel_btn = self.ksca_cancel_btn if site_type == 'ksca' else self.aicf_cancel_btn
        clear_btn = self.ksca_clear_btn if site_type == 'ksca' else self.aicf_clear_btn
        export_btn = self.ksca_export_btn if site_type == 'ksca' else self.aicf_export_btn
        input_widget = self.ksca_input if site_type == 'ksca' else self.aicf_input
        
        if is_scraping:
            verify_btn.configure(state="disabled")
            clear_btn.configure(state="disabled")
            export_btn.configure(state="disabled")
            input_widget.configure(state="disabled")
            cancel_btn.configure(state="normal")
            
            # Disable non-active notebook tab
            other_index = 1 if site_type == 'ksca' else 0
            self.notebook.tab(other_index, state="disabled")
        else:
            verify_btn.configure(state="normal")
            clear_btn.configure(state="normal")
            export_btn.configure(state="normal")
            input_widget.configure(state="normal")
            cancel_btn.configure(state="disabled")
            
            # Enable other notebook tab
            self.notebook.tab(0, state="normal")
            self.notebook.tab(1, state="normal")

    def export_results(self, site_type):
        """Saves current Treeview rows to a CSV format."""
        tree = self.ksca_tree if site_type == 'ksca' else self.aicf_tree
        children = tree.get_children()
        
        if not children:
            messagebox.showwarning("No Data", "There are no results available to export.")
            return
            
        initial_file = f"{site_type.upper()}_Verification_Results.csv"
        filepath = filedialog.asksaveasfilename(
            title="Export Scraped Verification Data",
            initialfile=initial_file,
            defaultextension=".csv",
            filetypes=[("CSV Document", "*.csv"), ("All files", "*.*")]
        )
        
        if not filepath:
            return
            
        try:
            with open(filepath, mode="w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                if site_type == 'ksca':
                    writer.writerow(["Chess Player ID", "Scraped Full Name", "District", "Verification Status"])
                else:
                    writer.writerow(["Chess Player ID", "Scraped Full Name", "State", "District", "Verification Status"])
                for row_id in children:
                    writer.writerow(tree.item(row_id)["values"])
                    
            messagebox.showinfo("Export Successful", f"Scraped results successfully saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"An error occurred while writing the file:\n{str(e)}")

    # ==========================================
    #  Queue-based Live UI Refresher Loop
    # ==========================================

    def start_queue_poller(self):
        """Starts the recurring loop to poll queue messages."""
        self.poll_queue()

    def poll_queue(self):
        """Periodically polls the queue for updates from the scraper worker thread."""
        try:
            while True:
                msg = self.result_queue.get_nowait()
                msg_type = msg[0]
                
                if msg_type == 'start':
                    # Scraper has started
                    total = msg[1]
                    self.log(f"Started verification scraping session for {total} IDs.")
                    
                elif msg_type == 'progress':
                    # Scraper reports checking ID X
                    curr_idx, pid = msg[1], msg[2]
                    if self.active_tab == 'aicf':
                        self.current_status_text = f"Verifying ID {curr_idx} of {self.total_ids} ({pid})"
                        self.current_pct = 15 + ((curr_idx - 1) / self.total_ids) * 85
                        prog_bar = self.aicf_progress_bar
                        prog_bar['value'] = self.current_pct
                    
                elif msg_type == 'progress_step':
                    # Determinate step progress during bulk scraping
                    val, text = msg[1], msg[2]
                    self.current_pct = val
                    self.current_status_text = text
                    prog_bar = self.ksca_progress_bar if self.active_tab == 'ksca' else self.aicf_progress_bar
                    prog_bar['value'] = val
                    
                elif msg_type == 'result':
                    # Scraper returned single result row
                    site = msg[1]
                    tree = self.ksca_tree if site == 'ksca' else self.aicf_tree
                    
                    if site == 'ksca':
                        _, _, player_id, name, district, status = msg
                        tree.insert("", "end", values=(player_id, name, district, status), tags=(status,))
                    else:
                        _, _, player_id, name, state, district, status = msg
                        tree.insert("", "end", values=(player_id, name, state, district, status), tags=(status,))
                        
                        self.completed_ids += 1
                        self.current_pct = 15 + (self.completed_ids / self.total_ids) * 85
                        prog_bar = self.aicf_progress_bar
                        prog_bar['value'] = self.current_pct
                    
                elif msg_type == 'log':
                    # Log message string
                    self.log(msg[1])
                    
                elif msg_type == 'done':
                    # Worker thread finished
                    self.is_running = False
                    self.toggle_gui_state(self.active_tab, is_scraping=False)
                    elapsed = time.time() - self.start_time
                    elapsed_str = self.format_time(elapsed)
                    self.log(f"Verification task successfully completed in {elapsed_str}.")
                    
                    # Final label state
                    lbl = self.ksca_progress_lbl if self.active_tab == 'ksca' else self.aicf_progress_lbl
                    lbl.configure(text=f"Verification Complete! Processed {self.total_ids} IDs in {elapsed_str}.")
                    
                    # Keep progressbar at 100%
                    prog = self.ksca_progress_bar if self.active_tab == 'ksca' else self.aicf_progress_bar
                    prog.configure(value=100)
                    
                    messagebox.showinfo("Verification Complete", f"Verification processing completed successfully in {elapsed_str}.")
                    
                elif msg_type == 'error':
                    # Fatal exception from scraper
                    err_msg = msg[1]
                    self.is_running = False
                    self.toggle_gui_state(self.active_tab, is_scraping=False)
                    self.log(f"ERROR: {err_msg}")
                    
                    # Reset UI
                    lbl = self.ksca_progress_lbl if self.active_tab == 'ksca' else self.aicf_progress_lbl
                    lbl.configure(text="Verification Failed.")
                    
                    prog = self.ksca_progress_bar if self.active_tab == 'ksca' else self.aicf_progress_bar
                    prog.configure(value=0)
                    
                    messagebox.showerror("Scraping Failure", f"Scraper encountered a failure:\n{err_msg}")
                
                self.result_queue.task_done()
        except queue.Empty:
            pass
        
        # Schedule the next poll in 100 milliseconds
        self.root.after(100, self.poll_queue)

    def format_time(self, seconds):
        if seconds is None or seconds < 0:
            return "--"
        mins = int(seconds) // 60
        secs = int(seconds) % 60
        if mins > 0:
            return f"{mins}m {secs}s"
        return f"{secs}s"

    def update_timer_loop(self):
        """Updates the elapsed time and remaining time estimation on the progress label."""
        if not self.is_running:
            return
            
        elapsed = time.time() - self.start_time
        elapsed_str = self.format_time(elapsed)
        
        # Calculate time remaining estimate
        est_remaining = None
        
        if self.active_tab == 'aicf':
            if self.completed_ids == 0:
                # Still initializing or on first ID
                est_remaining = max(1.0, (4.0 + self.total_ids * 2.0) - elapsed)
            else:
                avg_time_per_id = elapsed / self.completed_ids
                remaining_ids = self.total_ids - self.completed_ids
                est_remaining = remaining_ids * avg_time_per_id
        else:
            # KSCA is bulk
            if self.current_pct < 100:
                # KSCA typically takes ~12.0s total
                expected_total = 12.0
                est_remaining = max(1.0, expected_total - elapsed)
                
        rem_str = self.format_time(est_remaining) if est_remaining is not None else "--"
        
        # Update progress label
        lbl = self.ksca_progress_lbl if self.active_tab == 'ksca' else self.aicf_progress_lbl
        
        if self.active_tab == 'aicf':
            if self.completed_ids == 0:
                status = f"{self.current_status_text} | Elapsed: {elapsed_str} | Est. Remaining: {rem_str}"
            else:
                status = f"Verifying {self.completed_ids}/{self.total_ids} ({int(self.current_pct)}%) | Elapsed: {elapsed_str} | Est. Remaining: {rem_str}"
        else:
            status = f"{self.current_status_text} ({int(self.current_pct)}%) | Elapsed: {elapsed_str} | Est. Remaining: {rem_str}"
            
        lbl.configure(text=status)
        
        # Schedule next update in 500ms
        self.root.after(500, self.update_timer_loop)


# ==========================================
#  Main Entrypoint
# ==========================================

if __name__ == "__main__":
    root = tk.Tk()
    app = ChessCheckApp(root)
    root.mainloop()
