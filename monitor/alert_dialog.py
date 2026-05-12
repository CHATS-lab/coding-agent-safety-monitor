#!/usr/bin/env python3
"""Cross-platform safety-monitor alert dialog (tkinter, stdlib only).

Usage:
    python alert_dialog.py <severity> <issue_type> <body> <action_line>
"""

import sys
import tkinter as tk
import tkinter.font as tkfont

SEVERITY_COLORS = {"critical": "#FF3B30", "warning": "#FF9500", "info": "#FFCC00"}
DEFAULT_ACCENT_COLOR = "#FF9500"
BG_COLOR = "#F5F5F5"
DIVIDER_COLOR = "#E0E0E0"
BORDER_COLOR = "#BDBDBD"
TEXT_PRIMARY = "#212121"
TEXT_SECONDARY = "#808080"
TEXT_ACTION = "#404040"
BUTTON_BG = "#4285F4"
BUTTON_HOVER = "#3367D6"
BUTTON_TEXT = "#FFFFFF"
PANEL_WIDTH = 440
HORIZONTAL_PAD = 24
CONTENT_WIDTH = PANEL_WIDTH - HORIZONTAL_PAD * 2
BADGE_HEIGHT = 26
BUTTON_WIDTH = 120
BUTTON_HEIGHT = 32
TOPMOST_RELEASE_MS = 250


def parse_args(argv: list[str]) -> tuple[str, str, str, str]:
    """Read the four positional CLI args with safe defaults."""
    severity = argv[1] if len(argv) > 1 else "Warning"
    issue_type = argv[2] if len(argv) > 2 else "Unknown Issue"
    body = argv[3] if len(argv) > 3 else "No details available."
    action = argv[4] if len(argv) > 4 else "Review the pending action carefully."
    return severity, issue_type, body, action


def round_rect(
    canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, radius: int, **canvas_kwargs
) -> None:
    """Draw a rounded rectangle on `canvas` using arcs plus rectangles."""
    canvas_kwargs.pop("width", None)
    canvas.create_arc(x1, y1, x1 + 2 * radius, y1 + 2 * radius, start=90, extent=90, **canvas_kwargs)
    canvas.create_arc(x2 - 2 * radius, y1, x2, y1 + 2 * radius, start=0, extent=90, **canvas_kwargs)
    canvas.create_arc(x2 - 2 * radius, y2 - 2 * radius, x2, y2, start=270, extent=90, **canvas_kwargs)
    canvas.create_arc(x1, y2 - 2 * radius, x1 + 2 * radius, y2, start=180, extent=90, **canvas_kwargs)
    canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, **canvas_kwargs)
    canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, **canvas_kwargs)


def compute_display_lines(text: str, pixel_width: int, font: tkfont.Font) -> int:
    """Estimate how many wrapped lines `text` occupies at `pixel_width`."""
    wrapped_line_count = 0
    for paragraph in text.split("\n"):
        if not paragraph:
            wrapped_line_count += 1
            continue
        wrapped_line_count += max(1, -(-font.measure(paragraph) // pixel_width))
    return max(1, wrapped_line_count)


def text_widget(
    parent: tk.Widget,
    *,
    text: str,
    font: tkfont.Font,
    fg: str,
    pixel_width: int,
    spacing2: int,
    spacing3: int,
) -> tk.Text:
    """Create a read-only `tk.Text` sized to render `text` without scrolling."""
    char_width = max(1, pixel_width // font.measure("0"))
    line_count = compute_display_lines(text, pixel_width, font)
    widget = tk.Text(
        parent,
        wrap="word",
        font=font,
        fg=fg,
        bg=BG_COLOR,
        borderwidth=0,
        highlightthickness=0,
        padx=0,
        pady=0,
        spacing2=spacing2,
        spacing3=spacing3,
        width=char_width,
        height=line_count,
    )
    widget.insert("1.0", text)
    widget.configure(state="disabled")
    return widget


def set_button_fill(canvas: tk.Canvas, fill: str, font: tkfont.Font) -> None:
    """Redraw the OK button (Canvas items don't support hover styles natively)."""
    canvas.delete("all")
    round_rect(canvas, 0, 0, BUTTON_WIDTH, BUTTON_HEIGHT, radius=8, fill=fill, outline=fill)
    canvas.create_text(
        BUTTON_WIDTH // 2, BUTTON_HEIGHT // 2, text="OK", fill=BUTTON_TEXT, font=font
    )


def center_on_main_monitor(root: tk.Tk) -> None:
    """Center the dialog on the primary monitor."""
    root.update_idletasks()
    window_width = root.winfo_reqwidth()
    window_height = root.winfo_reqheight()
    window_x = (root.winfo_screenwidth() - window_width) // 2
    window_y = (root.winfo_screenheight() - window_height) // 2
    root.geometry(f"{window_width}x{window_height}+{window_x}+{window_y}")


def show_in_foreground(root: tk.Tk) -> None:
    """Raise the dialog to the foreground without an OS permission prompt."""
    root.deiconify()
    root.lift()
    root.attributes("-topmost", True)
    try:
        root.focus_force()
    except tk.TclError:
        pass
    root.after(TOPMOST_RELEASE_MS, lambda: root.attributes("-topmost", False))


def _build_header(
    parent: tk.Frame,
    severity: str,
    issue_type: str,
    accent_color: str,
    font_badge: tkfont.Font,
    font_title: tkfont.Font,
) -> None:
    header = tk.Frame(parent, bg=BG_COLOR)
    header.pack(fill="x", padx=HORIZONTAL_PAD, pady=(20, 16))

    badge_text = severity.upper()
    badge_width = font_badge.measure(badge_text) + 24
    badge_canvas = tk.Canvas(
        header, width=badge_width, height=BADGE_HEIGHT, bg=BG_COLOR, highlightthickness=0
    )
    badge_canvas.pack(side="left", padx=(0, 12))
    round_rect(
        badge_canvas,
        0,
        0,
        badge_width,
        BADGE_HEIGHT,
        radius=BADGE_HEIGHT // 2,
        fill=accent_color,
        outline=accent_color,
    )
    badge_canvas.create_text(
        badge_width // 2,
        BADGE_HEIGHT // 2,
        text=badge_text,
        fill="white",
        font=font_badge,
    )

    tk.Label(
        header,
        text=issue_type,
        font=font_title,
        fg=TEXT_PRIMARY,
        bg=BG_COLOR,
        anchor="w",
    ).pack(side="left", fill="x")


def _build_body(parent: tk.Frame, body_text: str, font_body: tkfont.Font) -> None:
    body_frame = tk.Frame(parent, bg=BG_COLOR)
    body_frame.pack(fill="x", padx=HORIZONTAL_PAD, pady=(18, 16))
    text_widget(
        body_frame,
        text=body_text,
        font=font_body,
        fg=TEXT_SECONDARY,
        pixel_width=CONTENT_WIDTH,
        spacing2=5,
        spacing3=5,
    ).pack(fill="x")


def _build_action(
    parent: tk.Frame,
    action_text: str,
    accent_color: str,
    font_action: tkfont.Font,
    font_action_bold: tkfont.Font,
    root: tk.Tk,
) -> None:
    action_frame = tk.Frame(parent, bg=BG_COLOR)
    action_frame.pack(fill="x", padx=HORIZONTAL_PAD, pady=(14, 20))

    icon_label = tk.Label(
        action_frame, text="⚠️", font=("Helvetica", 14), fg=accent_color, bg=BG_COLOR
    )
    icon_label.pack(side="left", anchor="n", padx=(0, 10), pady=(1, 0))

    root.update_idletasks()
    action_pixel_width = CONTENT_WIDTH - (icon_label.winfo_reqwidth() + 10)
    action_widget = tk.Text(
        action_frame,
        wrap="word",
        font=font_action,
        fg=TEXT_ACTION,
        bg=BG_COLOR,
        borderwidth=0,
        highlightthickness=0,
        padx=0,
        pady=0,
        spacing2=3,
        spacing3=3,
        width=max(1, action_pixel_width // font_action.measure("0")),
        height=compute_display_lines(action_text, action_pixel_width, font_action),
    )
    action_widget.tag_configure("bold", font=font_action_bold)

    for word_index, word in enumerate(action_text.split(" ")):
        prefix = " " if word_index else ""
        clean_word = word.lower().strip(".,;:!?")
        if clean_word in ("approve", "reject"):
            action_widget.insert("end", prefix + word, "bold")
        else:
            action_widget.insert("end", prefix + word)

    action_widget.configure(state="disabled")
    action_widget.pack(side="left", fill="x", expand=True)


def _build_button(parent: tk.Frame, font_button: tkfont.Font, root: tk.Tk) -> None:
    button_frame = tk.Frame(parent, bg=BG_COLOR)
    button_frame.pack(pady=(0, 20))

    ok_button = tk.Canvas(
        button_frame,
        width=BUTTON_WIDTH,
        height=BUTTON_HEIGHT,
        bg=BG_COLOR,
        highlightthickness=0,
        cursor="hand2",
    )
    ok_button.pack()
    set_button_fill(ok_button, BUTTON_BG, font_button)

    def close_dialog(_event=None) -> None:
        root.destroy()

    ok_button.bind("<Button-1>", close_dialog)
    ok_button.bind(
        "<Enter>", lambda _event: set_button_fill(ok_button, BUTTON_HOVER, font_button)
    )
    ok_button.bind(
        "<Leave>", lambda _event: set_button_fill(ok_button, BUTTON_BG, font_button)
    )
    root.bind("<Return>", close_dialog)
    root.bind("<Escape>", close_dialog)


def build_ui(severity: str, issue_type: str, body_text: str, action_text: str) -> tk.Tk:
    """Build the dialog widget tree. Returns the (un-mainlooped) root window."""
    accent_color = SEVERITY_COLORS.get(severity.lower(), DEFAULT_ACCENT_COLOR)

    root = tk.Tk()
    root.title("Security Monitor")
    root.configure(bg=BG_COLOR)

    outer = tk.Frame(root, bg=BORDER_COLOR, padx=1, pady=1)
    outer.pack()
    main_frame = tk.Frame(outer, bg=BG_COLOR)
    main_frame.pack()

    font_badge = tkfont.Font(family="Helvetica", size=11, weight="bold")
    font_title = tkfont.Font(family="Helvetica", size=20, weight="bold")
    font_body = tkfont.Font(family="Helvetica", size=14)
    font_action = tkfont.Font(family="Helvetica", size=13)
    font_action_bold = tkfont.Font(family="Helvetica", size=13, weight="bold")
    font_button = tkfont.Font(family="Helvetica", size=13)

    _build_header(main_frame, severity, issue_type, accent_color, font_badge, font_title)
    tk.Frame(main_frame, bg=DIVIDER_COLOR, height=1).pack(fill="x", padx=20)
    _build_body(main_frame, body_text, font_body)
    tk.Frame(main_frame, bg=DIVIDER_COLOR, height=1).pack(fill="x", padx=20)
    _build_action(main_frame, action_text, accent_color, font_action, font_action_bold, root)
    _build_button(main_frame, font_button, root)
    return root


def main() -> None:
    severity, issue_type, body, action = parse_args(sys.argv)
    root = build_ui(severity, issue_type, body, action)
    center_on_main_monitor(root)
    show_in_foreground(root)
    root.mainloop()


if __name__ == "__main__":
    main()
