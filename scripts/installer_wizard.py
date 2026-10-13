"""
Standalone Zero-Admin Setup Wizard for Sift Commercial Deal Desk.
Installs Sift into %LOCALAPPDATA%\\Programs\\Sift without administrator privileges,
creates Desktop & Start Menu shortcuts with the custom Sift icon, and launches the app.
Also supports silent headless installation via /S, /silent, or --silent.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

APP_NAME = "Sift"
VERSION = "1.0.0"
DEFAULT_INSTALL_DIR = Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Sift"))


def get_base_res() -> Path:
    """Resolve base directory for bundled PyInstaller assets."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent / "dist" / "Sift"


def resolve_payload_dir(base_res: Path) -> Path:
    """Find the payload directory containing Sift.exe."""
    candidates = [
        base_res / "payload" / "Sift",
        base_res / "payload",
        base_res / "dist" / "Sift",
        base_res,
    ]
    for c in candidates:
        if c.is_dir() and (c / "Sift.exe").is_file():
            return c
    # Fallback to base_res / "payload" if exists
    if (base_res / "payload").is_dir():
        return base_res / "payload"
    return base_res


def create_shortcut(target_path: Path, shortcut_path: Path, icon_path: Path):
    """Create a Windows shortcut (.lnk) using WScript.Shell or PowerShell."""
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.TargetPath = str(target_path)
        shortcut.WorkingDirectory = str(target_path.parent)
        shortcut.IconLocation = str(icon_path)
        shortcut.save()
        return True
    except Exception:
        pass

    try:
        ps_cmd = (
            f'$s=(New-Object -COM WScript.Shell).CreateShortcut("{shortcut_path}"); '
            f'$s.TargetPath="{target_path}"; '
            f'$s.WorkingDirectory="{target_path.parent}"; '
            f'$s.IconLocation="{icon_path}"; '
            f'$s.Save()'
        )
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
        return res.returncode == 0
    except Exception:
        return False


def kill_running_sift():
    """Ensure any running instance of Sift.exe is terminated before replacing files."""
    try:
        subprocess.run(["taskkill", "/F", "/IM", "Sift.exe"], capture_output=True)
    except Exception:
        pass


def perform_installation(install_dir: Path, make_desktop: bool, make_startmenu: bool, progress_callback=None):
    """Core copy & shortcut routine."""
    base_res = get_base_res()
    payload_dir = resolve_payload_dir(base_res)

    if not payload_dir.is_dir():
        raise RuntimeError(f"Payload directory not found at {payload_dir}")

    if progress_callback:
        progress_callback(20, "Stopping existing Sift instances...")
    kill_running_sift()

    if progress_callback:
        progress_callback(40, "Extracting application binaries and assets...")

    install_dir.mkdir(parents=True, exist_ok=True)

    # Copy files
    for item in payload_dir.iterdir():
        dest = install_dir / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    if progress_callback:
        progress_callback(75, "Creating Windows shortcuts...")

    target_exe = install_dir / "Sift.exe"
    icon_file = install_dir / "assets" / "sift_icon.ico"
    if not icon_file.is_file():
        icon_file = target_exe

    if make_desktop:
        desktop = Path(os.path.expandvars(r"%USERPROFILE%\Desktop"))
        if desktop.is_dir():
            create_shortcut(target_exe, desktop / "Sift.lnk", icon_file)

    if make_startmenu:
        start_programs = Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"))
        sift_folder = start_programs / "Sift"
        sift_folder.mkdir(parents=True, exist_ok=True)
        create_shortcut(target_exe, sift_folder / "Sift.lnk", icon_file)

    if progress_callback:
        progress_callback(100, "Installation complete!")


def silent_main():
    """Silent unattended installation for enterprise deployment."""
    try:
        perform_installation(DEFAULT_INSTALL_DIR, make_desktop=True, make_startmenu=True)
        print("[SILENT INSTALL] Sift installed successfully.")
        sys.exit(0)
    except Exception as e:
        print(f"[SILENT INSTALL ERROR] {e}", file=sys.stderr)
        sys.exit(1)


def gui_main():
    """Standard user-level graphical setup wizard."""
    import tkinter as tk
    from tkinter import ttk, messagebox

    root = tk.Tk()
    root.title(f"{APP_NAME} Setup Wizard — Version {VERSION}")
    root.geometry("540x400")
    root.resizable(False, False)
    root.configure(bg="#0f172a")

    # Icon
    base_res = get_base_res()
    icon_candidates = [
        base_res / "assets" / "sift_icon.ico",
        base_res / "payload" / "assets" / "sift_icon.ico",
        Path(__file__).resolve().parent.parent / "assets" / "sift_icon.ico",
    ]
    for ic in icon_candidates:
        if ic.is_file():
            try:
                root.iconbitmap(str(ic))
                break
            except Exception:
                pass

    # Header
    header = tk.Frame(root, bg="#1e293b", height=80)
    header.pack(fill="x")
    lbl_title = tk.Label(
        header,
        text="Install Sift Desktop Application",
        font=("Segoe UI", 16, "bold"),
        fg="#38bdf8",
        bg="#1e293b"
    )
    lbl_title.pack(anchor="w", padx=20, pady=(15, 2))
    lbl_sub = tk.Label(
        header,
        text="Commercial Audit & Margin Triage Engine (Local-First, Air-Gapped)",
        font=("Segoe UI", 10),
        fg="#94a3b8",
        bg="#1e293b"
    )
    lbl_sub.pack(anchor="w", padx=20)

    # Body
    body = tk.Frame(root, bg="#0f172a")
    body.pack(fill="both", expand=True, padx=24, pady=20)

    lbl_desc = tk.Label(
        body,
        text="This wizard will install Sift for your user account.\nNo administrator rights or internet connection required.",
        font=("Segoe UI", 10),
        fg="#f8fafc",
        bg="#0f172a",
        justify="left"
    )
    lbl_desc.pack(anchor="w", pady=(0, 15))

    lbl_dest = tk.Label(
        body,
        text=f"Destination:  {DEFAULT_INSTALL_DIR}",
        font=("Segoe UI", 9, "bold"),
        fg="#cbd5e1",
        bg="#0f172a"
    )
    lbl_dest.pack(anchor="w", pady=(0, 10))

    var_desktop = tk.BooleanVar(value=True)
    chk_desk = tk.Checkbutton(
        body,
        text="Create a Desktop Shortcut",
        variable=var_desktop,
        font=("Segoe UI", 10),
        fg="#38bdf8",
        bg="#0f172a",
        selectcolor="#1e293b",
        activebackground="#0f172a"
    )
    chk_desk.pack(anchor="w", pady=4)

    var_startmenu = tk.BooleanVar(value=True)
    chk_start = tk.Checkbutton(
        body,
        text="Create a Start Menu Shortcut",
        variable=var_startmenu,
        font=("Segoe UI", 10),
        fg="#38bdf8",
        bg="#0f172a",
        selectcolor="#1e293b",
        activebackground="#0f172a"
    )
    chk_start.pack(anchor="w", pady=4)

    progress = ttk.Progressbar(body, orient="horizontal", mode="determinate")
    progress.pack(fill="x", pady=(20, 5))
    lbl_status = tk.Label(body, text="Ready to install.", font=("Segoe UI", 9), fg="#94a3b8", bg="#0f172a")
    lbl_status.pack(anchor="w")

    # Footer
    footer = tk.Frame(root, bg="#1e293b", height=50)
    footer.pack(fill="x", side="bottom")

    btn_cancel = tk.Button(
        footer,
        text="Cancel",
        font=("Segoe UI", 10),
        command=root.destroy,
        width=10,
        bg="#334155",
        fg="#f8fafc",
        bd=0
    )
    btn_cancel.pack(side="right", padx=16, pady=10)

    def do_install():
        btn_install.config(state="disabled")
        btn_cancel.config(state="disabled")

        def update_progress(pct, msg):
            progress['value'] = pct
            lbl_status.config(text=msg)
            root.update()

        try:
            perform_installation(
                DEFAULT_INSTALL_DIR,
                make_desktop=var_desktop.get(),
                make_startmenu=var_startmenu.get(),
                progress_callback=update_progress
            )
            lbl_status.config(text="Installation completed successfully!", fg="#34d399")
            root.update()

            target_exe = DEFAULT_INSTALL_DIR / "Sift.exe"
            if messagebox.askyesno(
                "Setup Complete",
                "Sift has been installed successfully!\n\nWould you like to launch Sift now?"
            ):
                subprocess.Popen([str(target_exe)])
            root.destroy()
        except Exception as e:
            messagebox.showerror("Installation Error", f"Failed to install Sift:\n{str(e)}")
            btn_install.config(state="normal")
            btn_cancel.config(state="normal")
            lbl_status.config(text="Installation failed.", fg="#f87171")

    btn_install = tk.Button(
        footer,
        text="Install",
        font=("Segoe UI", 10, "bold"),
        command=do_install,
        width=12,
        bg="#0ea5e9",
        fg="#ffffff",
        bd=0
    )
    btn_install.pack(side="right", padx=6, pady=10)

    root.mainloop()


if __name__ == "__main__":
    if any(arg in sys.argv for arg in ["--silent", "/S", "/silent", "-s"]):
        silent_main()
    else:
        gui_main()
