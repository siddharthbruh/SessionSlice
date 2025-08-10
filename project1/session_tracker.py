import tkinter as tk
from tkinter import colorchooser, messagebox, filedialog
from datetime import datetime, timedelta
import json
import os
import calendar
from collections import defaultdict
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# ----- Constants -----
BG = '#19191a'
PANEL = '#29293c'
CARD = '#242438'
ACCENT = '#7B67EE'
GREEN = '#4CAF50'
FONT = "Segoe UI"
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

SESSION_FILE = os.path.join(DATA_DIR, "sessions.json")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
SESSION_TYPES_FILE = os.path.join(DATA_DIR, "session_types.json")

# ------- Globals -------
sessions = []
tasks = []
session_types = []

root = None
tracker_frame = None

settings_window = None
analytics_window = None

# Widgets
timer_var = None
task_combo = None
session_type_combo = None
start_btn = pause_btn = stop_btn = break_btn = interrupt_btn = None
recent_list = None
calendar_frame = None
cal_month_lbl = None
cal_month = 0
cal_year = 0

# State vars
session_running = False
session_paused = False
session_start = None
session_left_sec = 0
current_task = None
current_session_type = None
break_count = 0
interrupt_count = 0
timer_id = None

# For Analytics window charts
canvas_sessiontype = None
canvas_dailytrend = None

# --------- Data Loading and Saving ---------
def load_json(filepath, default):
    try:
        print(f"Attempting to load {filepath}")
        with open(filepath, "r") as f:
            data = json.load(f)
            print(f"Loaded data: {data}")
            return data
    except Exception as e:
        print(f"Failed to load {filepath}: {e}")
        return default

def save_json(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

def load_all_data():
    global sessions, tasks, session_types
    sessions = load_json(SESSION_FILE, [])
    tasks = load_json(TASKS_FILE, [{"name": "Sample Task", "category": "General", "color": ACCENT}])
    session_types = load_json(SESSION_TYPES_FILE, [
        {"name": "Focus", "icon": "🔥", "color": ACCENT, "hours": 0, "minutes": 25},
        {"name": "Break", "icon": "☕", "color": GREEN, "hours": 0, "minutes": 5},
    ])

def save_all_data():
    save_json(SESSION_FILE, sessions)
    save_json(TASKS_FILE, tasks)
    save_json(SESSION_TYPES_FILE, session_types)

# --------- Core Functional Callbacks ---------
def start_session():
    global session_running, session_paused, session_start, session_left_sec
    global current_task, current_session_type, break_count, interrupt_count
    global task_var, session_type_var, start_btn, pause_btn, stop_btn, break_btn, interrupt_btn

    if session_running:
        popup("Session already running.", "warning")
        return

    task_name = task_var.get() if task_var else None
    session_type_label = session_type_var.get().strip() if session_type_var else None

    if not task_name:
        popup("Please select a task.", "error")
        return

    current_task = next((t for t in tasks if t["name"] == task_name), None)

    current_session_type = None
    for st in session_types:
        label = f"{st['icon']} {st['name']}"
        if session_type_label == label or st["name"] in session_type_label:
            current_session_type = st
            break
    if current_session_type is None and len(session_types) > 0:
        current_session_type = session_types[0]

    if current_session_type is not None:
        hrs = current_session_type.get("hours", 0)
        mins = current_session_type.get("minutes", 25)
        session_left_sec = hrs * 3600 + mins * 60
        if session_left_sec == 0:
            session_left_sec = 25 * 60
    else:
        session_left_sec = 25 * 60

    session_start = datetime.now()
    session_running = True
    session_paused = False
    break_count = 0
    interrupt_count = 0
    update_timer_display()
    if start_btn:
        start_btn.config(state="disabled")
    if pause_btn:
        pause_btn.config(state="normal", text="Pause")
    if stop_btn:
        stop_btn.config(state="normal")
    if break_btn:
        break_btn.config(state="normal")
    if interrupt_btn:
        interrupt_btn.config(state="normal")
    update_timer()

def pause_resume_session():
    global session_paused, session_running, pause_btn
    if not session_running:
        popup("No session running.", "warning")
        return
    session_paused = not session_paused
    if pause_btn:
        pause_btn.config(text="Resume" if session_paused else "Pause")
    if not session_paused:
        update_timer()

def stop_session():
    global session_running, session_paused, session_start, session_left_sec
    global current_task, current_session_type, break_count, interrupt_count
    global start_btn, pause_btn, stop_btn, break_btn, interrupt_btn

    if not session_running:
        popup("No session running.", "warning")
        return

    end_time = datetime.now()
    mins = round((end_time - session_start).total_seconds() / 60, 1) if session_start else 0
    session_type_label = f"{current_session_type['icon']} {current_session_type['name']}" if current_session_type else ""

    sessions.append(
        {
            "name": current_task["name"] if current_task else "Unknown",
            "color": current_task.get("color", ACCENT) if current_task else ACCENT,
            "date": session_start.strftime("%Y-%m-%d") if session_start else "",
            "start": session_start.strftime("%H:%M") if session_start else "",
            "end": end_time.strftime("%H:%M"),
            "duration": mins,
            "breaks": break_count,
            "interruptions": interrupt_count,
            "session_type": session_type_label,
        }
    )
    save_json(SESSION_FILE, sessions)
    session_running = False
    session_paused = False
    session_start = None
    session_left_sec = 0
    update_timer_display()
    if start_btn:
        start_btn.config(state="normal")
    if pause_btn:
        pause_btn.config(state="disabled", text="Pause")
    if stop_btn:
        stop_btn.config(state="disabled")
    if break_btn:
        break_btn.config(state="disabled")
    if interrupt_btn:
        interrupt_btn.config(state="disabled")
    popup("Session saved.", "info")
    update_recent_sessions()
    build_calendar()

def log_break():
    global break_count, session_running, session_paused
    if not session_running or session_paused:
        popup("Session must be running and not paused to log break.", "warning")
        return
    break_count += 1
    popup(f"Break logged ({break_count})")

def log_interruption():
    global interrupt_count, session_running, session_paused
    if not session_running or session_paused:
        popup("Session must be running and not paused to log interruption.", "warning")
        return
    interrupt_count += 1
    popup(f"Interruption logged ({interrupt_count})")


# --------Hover Helpers--------

def on_enter(e):
    e.widget["bg"] = "#000000"  

def on_leave(e):
    e.widget["bg"] = ACCENT  


# --------- Timer Helpers ---------
def update_timer_display():
    global session_left_sec, timer_var
    if not timer_var:
        return
    mins = session_left_sec // 60
    secs = session_left_sec % 60
    timer_var.set(f"{mins:02d}:{secs:02d}")

def update_timer():
    global session_left_sec, session_running, session_paused, timer_id, root
    if not session_running or session_paused:
        return
    if session_left_sec <= 0:
        popup("Session complete!", "info")
        stop_session()
        return
    update_timer_display()
    session_left_sec -= 1
    if root:
        timer_id = root.after(1000, update_timer)

# --------- Calendar Controls ---------
def prev_month():
    global cal_month, cal_year
    cal_month -= 1
    if cal_month < 1:
        cal_month = 12
        cal_year -= 1
    build_calendar()

def next_month():
    global cal_month, cal_year
    cal_month += 1
    if cal_month > 12:
        cal_month = 1
        cal_year += 1
    build_calendar()

def build_calendar():
    global calendar_frame, cal_month_lbl, cal_month, cal_year, sessions
    if not calendar_frame or not cal_month_lbl:
        return

    for w in calendar_frame.winfo_children():
        w.destroy()

    cal_month_lbl.config(text=f"{calendar.month_name[cal_month]} {cal_year}")

    days_abbr = ["S", "M", "T", "W", "T", "F", "S"]
    for i, d in enumerate(days_abbr):
        tk.Label(
            calendar_frame,
            text=d,
            bg=BG,
            fg="#b0b0b0",
            font=(FONT, 10, "bold"),
            width=3,
        ).grid(row=0, column=i)
    month_days = calendar.monthcalendar(cal_year, cal_month)
    session_days = {
        int(s["date"].split("-")[2])
        for s in sessions
        if s["date"].startswith(f"{cal_year}-{cal_month:02d}")
    }
    for r, week in enumerate(month_days, 1):
        for c, day in enumerate(week):
            if day == 0:
                tk.Label(calendar_frame, text="", bg=BG, width=3).grid(row=r, column=c)
                continue
            bg_color = ACCENT if day in session_days else CARD
            fg_color = BG if day in session_days else "#DDD"
            tk.Label(
                calendar_frame,
                text=str(day),
                bg=bg_color,
                fg=fg_color,
                font=(FONT, 11, "bold"),
                width=3,
            ).grid(row=r, column=c)

# --------- Session Export ---------
def export_sessions():
    if not sessions:
        popup("No sessions to export.")
        return
    fname = f"sessions-{datetime.now().strftime('%Y%m%d')}.csv"
    path = filedialog.asksaveasfilename(
        defaultextension=".csv", initialfile=fname, filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    if not path:
        return
    try:
        import csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Name",
                    "Color",
                    "Date",
                    "Start",
                    "End",
                    "Duration (min)",
                    "Breaks",
                    "Interruptions",
                    "Session Type",
                ]
            )
            for s in sessions:
                writer.writerow(
                    [
                        s["name"],
                        s["color"],
                        s["date"],
                        s["start"],
                        s["end"],
                        s["duration"],
                        s["breaks"],
                        s["interruptions"],
                        s["session_type"],
                    ]
                )
        popup("Sessions exported successfully!", "info")
    except Exception as e:
        popup(f"Export failed: {e}", "error")

# --------- Streak Calculation ---------
def calculate_streak():
    if not sessions:
        return 0
    dates = {s["date"] for s in sessions}
    streak = 0
    day = datetime.now().date()
    while day.strftime("%Y-%m-%d") in dates:
        streak += 1
        day -= timedelta(days=1)
    return streak

# --------- Recent Sessions Update ---------
def update_recent_sessions():
    global recent_list
    if not recent_list:
        return
    recent_list.delete(0, tk.END)
    for s in reversed(sessions[-15:]):
        line = f"{s.get('session_type', '')} | {s['date']} - {s['name']} ({round(s['duration'])}m), B:{s['breaks']} I:{s['interruptions']}"
        recent_list.insert(tk.END, line)

# --------- Task/Session Type Combo Refresh ---------
def refresh_task_combo():
    global task_combo, task_var, tasks
    if task_combo and task_var:
        menu = task_combo["menu"]
        menu.delete(0, "end")
        names = [t["name"] for t in tasks]
        if names:
            task_var.set(names[0])
            for name in names:
                menu.add_command(label=name, command=lambda v=name: task_var.set(v))
        else:
            task_var.set("")

def refresh_sessiontype_combo():
    global session_type_combo, session_type_var, session_types
    if session_type_combo and session_type_var:
        menu = session_type_combo["menu"]
        menu.delete(0, "end")
        values = [f"{st['icon']} {st['name']}" for st in session_types]
        if values:
            session_type_var.set(values[0])
            for val in values:
                menu.add_command(label=val, command=lambda v=val: session_type_var.set(v))
        else:
            session_type_var.set("")

# --------- UI Popups ---------
def popup(msg, kind="info"):
    if kind == "info":
        messagebox.showinfo("SessionSlice", msg)
    elif kind == "error":
        messagebox.showerror("SessionSlice", msg)
    else:
        messagebox.showwarning("SessionSlice", msg)

# --------- Main Tracker UI ---------
def build_tracker_ui(frame):
    global task_var, session_type_var, timer_var
    global task_combo, session_type_combo
    global start_btn, pause_btn, stop_btn, break_btn, interrupt_btn
    global recent_list, calendar_frame, cal_month_lbl

    left = tk.Frame(frame, bg=PANEL)
    left.pack(side="left", fill="y", padx=10, pady=10)
    middle = tk.Frame(frame, bg=BG)
    middle.pack(side="left", fill="both", expand=True, padx=10, pady=10)
    right = tk.Frame(frame, bg=PANEL)
    right.pack(side="left", fill="y", padx=10, pady=10)

    # Task selection
    tk.Label(left, text="Select Task:", bg=PANEL, fg=ACCENT, font=(FONT, 12)).pack(pady=5)
    task_var = tk.StringVar()
    task_combo = tk.OptionMenu(left, task_var, "",)
    task_combo.config(width=20)
    task_combo.pack(pady=5)

    # Session Type selection
    tk.Label(left, text="Session Type:", bg=PANEL, fg=ACCENT, font=(FONT, 12)).pack(pady=5)
    session_type_var = tk.StringVar()
    session_type_combo = tk.OptionMenu(left, session_type_var, "")
    session_type_combo.config(width=20)
    session_type_combo.pack(pady=5)
    add_type_btn = tk.Button(left, text="Add Type", command=add_custom_sessiontype)
    add_type_btn.pack(pady=5)

    # Timer display
    timer_var = tk.StringVar(value="00:00")
    timer_lbl = tk.Label(middle, textvariable=timer_var, font=(FONT, 48, "bold"), fg=ACCENT, bg=BG)
    timer_lbl.pack(pady=40)

    # Timer control buttons
    btn_frame = tk.Frame(middle, bg=BG)
    btn_frame.pack()
    start_btn = tk.Button(btn_frame, text="Start",bg=ACCENT,fg="white", command=start_session)
    start_btn.grid(row=0, column=0, padx=5, pady=5)
    pause_btn = tk.Button(btn_frame, text="Pause",bg=ACCENT,fg="white", command=pause_resume_session)
    pause_btn.grid(row=0, column=1, padx=5, pady=5)
    stop_btn = tk.Button(btn_frame, text="Stop",bg=ACCENT,fg="white", command=stop_session)
    stop_btn.grid(row=0, column=2, padx=5, pady=5)
    break_btn = tk.Button(middle, text="Log Break",bg=ACCENT,fg="white", command=log_break)
    break_btn.pack(pady=10)
    interrupt_btn = tk.Button(middle, text="Log Interruption",bg=ACCENT,fg="white", command=log_interruption)
    interrupt_btn.pack(pady=10)

#--------Hover effect--------
    for btn in (start_btn, stop_btn, pause_btn, break_btn,interrupt_btn,add_type_btn):
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)


    # Recent sessions listbox
    tk.Label(right, text="Recent Sessions:", bg=BG, fg=ACCENT, font=(FONT, 12)).pack(pady=10)

    # Frame for listbox and scrollbars
    recent_frame = tk.Frame(right, bg=BG)
    recent_frame.pack(padx=5, pady=5, fill="both", expand=True)

    # Scrollbars first so we can reference them in Listbox
    recent_v_scroll = tk.Scrollbar(recent_frame, orient="vertical")
    recent_h_scroll = tk.Scrollbar(recent_frame, orient="horizontal")

    # Listbox
    recent_list = tk.Listbox(
        recent_frame,
        width=60,
        height=15,
        yscrollcommand=recent_v_scroll.set,
        xscrollcommand=recent_h_scroll.set
    )
    recent_list.grid(row=0, column=0, sticky="nsew")

    # Attach scrollbars to listbox
    recent_v_scroll.config(command=recent_list.yview)
    recent_v_scroll.grid(row=0, column=1, sticky="ns")

    recent_h_scroll.config(command=recent_list.xview)
    recent_h_scroll.grid(row=1, column=0, sticky="ew")

    # Make frame expandable
    recent_frame.grid_rowconfigure(0, weight=1)
    recent_frame.grid_columnconfigure(0, weight=1)

    
    # Calendar widget
    cal_container = tk.Frame(left, bg=PANEL)
    cal_container.pack(pady=10)
    cal_nav = tk.Frame(cal_container, bg=PANEL)
    cal_nav.pack(side="top")
    tk.Button(cal_nav, text="<", width=3, command=prev_month).pack(side="left")
    cal_month_lbl = tk.Label(cal_nav, text="", bg=PANEL, fg=ACCENT, font=(FONT, 11, "bold"))
    cal_month_lbl.pack(side="left", padx=5)
    tk.Button(cal_nav, text=">", width=3, command=next_month).pack(side="left")
    calendar_frame = tk.Frame(cal_container, bg=BG)
    calendar_frame.pack()

# --------- Settings & Analytics Windows and Helpers ---------
def create_top_buttons(parent):
    btn_frame = tk.Frame(parent, bg=PANEL)
    btn_frame.pack(side="top", fill="x", pady=8)
    tk.Button(btn_frame, text="Settings ⚙️", command=open_settings_window).pack(side="left", padx=6)
    tk.Button(btn_frame, text="Analytics 📊", command=open_analytics_window).pack(side="left", padx=6)

def open_settings_window():
    global settings_window
    if settings_window and settings_window.winfo_exists():
        settings_window.lift()
        return
    settings_window = tk.Toplevel(root)
    settings_window.title("Settings & Task Management")
    settings_window.geometry("700x580")
    settings_window.configure(bg=BG)

    tab_frame = tk.Frame(settings_window, bg=BG)
    tab_frame.pack(side="top", fill="x")
    body_frame = tk.Frame(settings_window, bg=BG)
    body_frame.pack(fill="both", expand=True)
    tasks_frame = tk.Frame(body_frame, bg=BG)
    sessions_frame = tk.Frame(body_frame, bg=BG)

    def show_frame(f):
        tasks_frame.pack_forget()
        sessions_frame.pack_forget()
        f.pack(fill="both", expand=True)

    tk.Button(tab_frame, text="Tasks", command=lambda: show_frame(tasks_frame)).pack(side="left", padx=10, pady=5)
    tk.Button(tab_frame, text="Session Types", command=lambda: show_frame(sessions_frame)).pack(side="left", padx=10, pady=5)

    # Tasks tab
    tk.Button(tasks_frame, text="Add Task", bg=ACCENT,fg="white", command=add_task_popup).pack(pady=12)
    tasks_listbox = tk.Listbox(tasks_frame, width=50, height=10)
    tasks_listbox.pack(pady=12)
    for t in tasks: 
        tasks_listbox.insert(tk.END, f"{t['name']} | {t['category']} | {t['color']}")

    # Session Types tab
    tk.Button(sessions_frame, text="Add Session Type",bg=ACCENT,fg="white", command=add_custom_sessiontype).pack(pady=12)
    types_listbox = tk.Listbox(sessions_frame, width=50, height=10)
    types_listbox.pack(pady=12)
    for st in session_types:
        types_listbox.insert(
            tk.END,
            f"{st['icon']} {st['name']} | {st['color']} | {st.get('hours',0)}h {st.get('minutes',25)}m"
        )
    show_frame(tasks_frame)

def open_analytics_window():
    global analytics_window, canvas_sessiontype, canvas_dailytrend
    if analytics_window and analytics_window.winfo_exists():
        analytics_window.lift()
        return
    analytics_window = tk.Toplevel(root)
    analytics_window.title("Session Analytics")
    analytics_window.geometry("850x600")
    analytics_window.configure(bg=BG)

    tab_frame = tk.Frame(analytics_window, bg=BG)
    tab_frame.pack(side="top", fill="x")
    body_frame = tk.Frame(analytics_window, bg=BG)
    body_frame.pack(fill="both", expand=True)
    summary_frame = tk.Frame(body_frame, bg=BG)
    detailed_frame = tk.Frame(body_frame, bg=BG)

    def show_frame(f):
        summary_frame.pack_forget()
        detailed_frame.pack_forget()
        f.pack(fill="both", expand=True)

    tk.Button(tab_frame, text="Summary", command=lambda: show_frame(summary_frame)).pack(side="left", padx=10, pady=5)
    tk.Button(tab_frame, text="Detailed Data", command=lambda: show_frame(detailed_frame)).pack(side="left", padx=10, pady=5)

    # Summary tab
    stat_today = tk.Label(summary_frame, bg=BG, fg=ACCENT, font=(FONT, 11))
    stat_today.pack(pady=3)
    stat_week = tk.Label(summary_frame, bg=BG, fg=ACCENT, font=(FONT, 11))
    stat_week.pack(pady=3)
    stat_streak = tk.Label(summary_frame, bg=BG, fg=ACCENT, font=(FONT, 11))
    stat_streak.pack(pady=3)
    chart_frame = tk.Frame(summary_frame, bg=BG)
    chart_frame.pack(fill="both", expand=True)

    update_stats_labels(stat_today, stat_week, stat_streak)
    update_sessiontype_chart(parent=chart_frame)
    update_dailytrend_chart(parent=chart_frame)

    # Detailed tab
    tk.Button(detailed_frame, text="Export Sessions to CSV", command=export_sessions).pack(pady=15)

    show_frame(summary_frame)

# --------- Analytics and Stats Helpers ---------
def update_stats_labels(today_lbl, week_lbl, streak_lbl):
    today = datetime.now().strftime("%Y-%m-%d")
    total_today = round(sum(s["duration"] for s in sessions if s["date"] == today))
    sessions_today = sum(1 for s in sessions if s["date"] == today)
    date_7_days_ago = datetime.now().date() - timedelta(days=6)
    total_week = round(
        sum(
            s["duration"]
            for s in sessions
            if datetime.strptime(s["date"], "%Y-%m-%d").date() >= date_7_days_ago
        )
    )
    sessions_week = sum(
        1
        for s in sessions
        if datetime.strptime(s["date"], "%Y-%m-%d").date() >= date_7_days_ago
    )
    streak = calculate_streak()
    today_lbl.config(text=f"Today: {total_today} min across {sessions_today} session{'s' if sessions_today != 1 else ''}")
    week_lbl.config(text=f"Last 7 days: {total_week} min across {sessions_week} session{'s' if sessions_week != 1 else ''}")
    streak_lbl.config(text=f"Current streak: {streak} day{'s' if streak != 1 else ''}")

def update_sessiontype_chart(parent):
    global canvas_sessiontype
    if canvas_sessiontype:
        canvas_sessiontype.get_tk_widget().destroy()
    now = datetime.now().date()
    last_7_days = [now - timedelta(days=i) for i in range(6, -1, -1)]
    type_time = defaultdict(float)
    for s in sessions:
        try:
            d = datetime.strptime(s["date"], "%Y-%m-%d").date()
            if d in last_7_days:
                type_time[s.get("session_type", "Unknown")] += s.get("duration", 0)
        except Exception:
            continue
    labels = list(type_time.keys())
    values = [type_time[l] for l in labels]
    if not labels:
        labels = ["No Data"]
        values = [1]
    fig = Figure(figsize=(4, 3), dpi=90)
    ax = fig.add_subplot(111)
    ax.bar(labels, values, color=ACCENT)
    ax.set_title("Time per Session Type (7 days)")
    ax.set_ylabel("Minutes")
    ax.set_xticklabels(labels, rotation=45, ha="right")
    canvas_sessiontype = FigureCanvasTkAgg(fig, master=parent)
    canvas_sessiontype.draw()
    canvas_sessiontype.get_tk_widget().pack(side="left", fill="both", expand=True)

def update_dailytrend_chart(parent):
    global canvas_dailytrend
    if canvas_dailytrend:
        canvas_dailytrend.get_tk_widget().destroy()
    now = datetime.now().date()
    last_7_days = [now - timedelta(days=i) for i in range(6, -1, -1)]
    daily_time = {d: 0 for d in last_7_days}
    for s in sessions:
        try:
            d = datetime.strptime(s["date"], "%Y-%m-%d").date()
            if d in daily_time:
                daily_time[d] += s.get("duration", 0)
        except Exception:
            continue
    dates = [d.strftime("%a") for d in last_7_days]
    values = [daily_time[d] for d in last_7_days]
    fig = Figure(figsize=(4, 3), dpi=90)
    ax = fig.add_subplot(111)
    ax.plot(dates, values, marker="o", color=ACCENT)
    ax.set_title("Daily Focus Time (7 days)")
    ax.set_ylabel("Minutes")
    ax.set_ylim(bottom=0)
    canvas_dailytrend = FigureCanvasTkAgg(fig, master=parent)
    canvas_dailytrend.draw()
    canvas_dailytrend.get_tk_widget().pack(side="left", fill="both", expand=True)

# --------- Settings Dialogs ---------
def add_custom_sessiontype():
    global session_types
    def save_new_type():
        name = name_var.get().strip()
        icon = icon_var.get().strip() or "💡"
        color = color_var.get()
        try:
            hrs = int(hours_var.get())
            mins = int(minutes_var.get())
        except Exception:
            popup("Hours and minutes must be valid integers.", "warning")
            return
        if not name:
            popup("Name cannot be empty.", "warning")
            return
        if any(t["name"].lower() == name.lower() for t in session_types):
            popup("Session type already exists.", "error")
            return
        session_types.append({"name": name, "icon": icon, "color": color, "hours": hrs, "minutes": mins})
        save_json(SESSION_TYPES_FILE, session_types)
        refresh_sessiontype_combo()
        popup("Session type added!", "info")
        top.destroy()
    top = tk.Toplevel(root)
    top.title("Add Custom Session Type")
    top.geometry("320x320")
    top.configure(bg=BG)
    tk.Label(top, text="Icon (emoji):", bg=BG, fg=ACCENT, font=(FONT, 12)).pack(pady=6)
    icon_var = tk.StringVar(value="💡")
    tk.Entry(top, textvariable=icon_var, font=(FONT, 14), width=3).pack()
    tk.Label(top, text="Name:", bg=BG, fg=ACCENT, font=(FONT, 12)).pack(pady=6)
    name_var = tk.StringVar()
    tk.Entry(top, textvariable=name_var, font=(FONT, 12), width=18).pack()
    tk.Label(top, text="Color:", bg=BG, fg=ACCENT, font=(FONT, 12)).pack(pady=6)
    def pick_color():
        c = colorchooser.askcolor(title="Choose Color")
        if c and c[1]:
            color_var.set(c[1])
            color_btn.config(bg=c[1])
    color_var = tk.StringVar(value=ACCENT)
    color_btn = tk.Button(top, bg=ACCENT, text="Pick Color", font=(FONT, 11), fg="white", command=pick_color)
    color_btn.pack(pady=6)
    frame_time = tk.Frame(top, bg=BG)
    frame_time.pack(pady=20)
    tk.Label(frame_time, text="Hours:", bg=BG, fg=ACCENT, font=(FONT, 12)).grid(row=0, column=0, padx=10)
    hours_var = tk.StringVar(value="0")
    tk.Entry(frame_time, textvariable=hours_var, font=(FONT, 11), width=4).grid(row=0, column=1)
    tk.Label(frame_time, text="Minutes:", bg=BG, fg=ACCENT, font=(FONT, 12)).grid(row=0, column=2, padx=10)
    minutes_var = tk.StringVar(value="25")
    tk.Entry(frame_time, textvariable=minutes_var, font=(FONT, 11), width=4).grid(row=0, column=3)
    tk.Button(top, text="Add Session Type", bg=GREEN, fg="white", font=(FONT, 13, "bold"), command=save_new_type).pack(pady=10)
    top.transient(root)
    top.grab_set()

def add_task_popup():
    global tasks
    popup_win = tk.Toplevel(root)
    popup_win.title("Add Task")
    popup_win.configure(bg=BG)
    tk.Label(popup_win, text="Task Name:", bg=BG, fg=ACCENT, font=(FONT, 12)).pack(pady=5)
    name_var = tk.StringVar()
    tk.Entry(popup_win, textvariable=name_var, font=(FONT, 12)).pack(pady=5)
    def do_add():
        task_name = name_var.get().strip()
        if not task_name:
            messagebox.showwarning("Input", "Task name required")
            return
        tasks.append({"name": task_name, "category": "General", "color": ACCENT})
        save_json(TASKS_FILE, tasks)
        refresh_task_combo()
        popup_win.destroy()
    tk.Button(popup_win, text="Add", command=do_add).pack(pady=10)
    popup_win.transient(root)
    popup_win.grab_set()

# --------- Main GUI Setup ---------
def setup_gui():
    global root, tracker_frame, cal_month, cal_year
    root = tk.Tk()
    root.title("SessionSlice")
    root.geometry("1220x780")
    root.configure(bg=BG)
    create_top_buttons(root)
    container = tk.Frame(root, bg=BG)
    container.pack(fill="both", expand=True)
    tracker_frame = tk.Frame(container, bg=BG)
    build_tracker_ui(tracker_frame)
    tracker_frame.pack(fill="both", expand=True)
    now = datetime.now()
    cal_month, cal_year = now.month, now.year
    refresh_task_combo()
    refresh_sessiontype_combo()
    update_recent_sessions()
    build_calendar()

if __name__ == "__main__":
    load_all_data()
    setup_gui()
    if root:
        root.mainloop()
