"""
Project Sift — Complete Packaging & Distribution Build Pipeline
Builds both:
1. Sift-v1.0-Portable.zip (Self-contained zero-install folder with Sift.exe)
2. Sift-Setup-v1.0.exe (Standalone user-level Windows installer wizard, zero admin rights needed)
3. installer/sift_installer.iss (Official Inno Setup enterprise script)
"""

import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"
BUILD_DIR = REPO_ROOT / "build"
ASSETS_DIR = REPO_ROOT / "assets"
ICON_PATH = ASSETS_DIR / "sift_icon.ico"

print("===============================================================================")
print("          PROJECT SIFT: PACKAGING & DISTRIBUTION BUILD PIPELINE                ")
print("===============================================================================")
print(f"[*] Workspace Root: {REPO_ROOT}")
print(f"[*] Distribution Directory: {DIST_DIR}")

# 1. Verify / Build Icon
if not ICON_PATH.is_file():
    print("[*] Generating branding icons...")
    subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "generate_icon.py")], check=True)

# 2. Verify Frontend Assets in src/dist
dist_html = REPO_ROOT / "src" / "dist" / "index.html"
if not dist_html.is_file():
    print("[*] Building frontend assets in src...")
    subprocess.run(["npm", "run", "build"], cwd=str(REPO_ROOT / "src"), shell=True, check=True)
else:
    print("[OK] Frontend bundle verified at src/dist/index.html")

# 3. Compile Standalone OneDir Application via PyInstaller
print("\n[*] Compiling standalone Sift application via PyInstaller...")
pyinstaller_args = [
    sys.executable,
    "-m", "PyInstaller",
    "--noconfirm",
    "--onedir",
    "--windowed",
    "--name", "Sift",
    f"--icon={ICON_PATH}",
    f"--add-data={REPO_ROOT / 'src' / 'dist'};src/dist",
    f"--add-data={ASSETS_DIR};assets",
    f"--add-data={REPO_ROOT / 'backend'};backend",
    "--collect-all=duckdb",
    "--collect-all=uvicorn",
    "--collect-all=pyzipper",
    "--collect-all=openpyxl",
    "--collect-all=pyarrow",
    "--hidden-import=fastapi",
    "--hidden-import=starlette",
    "--hidden-import=pydantic",
    "--hidden-import=pandas",
    "--hidden-import=h11",
    "--hidden-import=anyio",
    "--hidden-import=anyio._backends._asyncio",
    "--hidden-import=backend.storage",
    "--hidden-import=backend.ingestion",
    "--hidden-import=backend.loao",
    "--hidden-import=backend.beam_search",
    "--hidden-import=backend.overlap_ledger",
    "--hidden-import=backend.interactions",
    "--hidden-import=backend.pvmc_bridge",
    "--hidden-import=backend.lifecycle",
    "--hidden-import=backend.export",
    str(REPO_ROOT / "backend" / "run_desktop.py"),
]

subprocess.run(pyinstaller_args, cwd=str(REPO_ROOT), check=True)
app_dir = DIST_DIR / "Sift"

# 4. Copy Documentation & Quickstart into dist/Sift
readme_text = """===============================================================================
            SIFT — COMMERCIAL AUDIT & MARGIN TRIAGE ENGINE
            Local-First, Air-Gapped Desktop Application
===============================================================================

Quick Start:
1. Double-click 'Sift.exe' to launch the application.
2. The standalone desktop window will appear automatically on http://127.0.0.1:8765.
3. No internet connection, Python installation, or administrator rights required.

Storage & Persistence:
- Workspaces are saved as single '.mxa' files which can be safely stored,
  copied, or shared across local enterprise network drives.

Safety & Security:
- 100% Air-Gapped: Zero telemetry, zero external network calls.
- Analytical Engine: Embedded In-Process DuckDB (4GB Memory Ceiling with disk-spill).
- Anti-Injection Defense: All exported spreadsheets neutralize CSV formula execution.

Support & Documentation:
- Refer to MANUAL_TESTING_GUIDE.md for detailed testing protocols.
===============================================================================
"""

with open(app_dir / "README.txt", "w", encoding="utf-8") as f:
    f.write(readme_text)

# Also create a handy batch launcher in the folder
with open(app_dir / "Launch-Sift.bat", "w", encoding="utf-8") as f:
    f.write("@echo off\nstart \"\" \"%~dp0Sift.exe\"\n")

print(f"[OK] Sift standalone bundle compiled successfully in {app_dir}")

# 5. Build Sift-v1.0-Portable.zip
zip_target = DIST_DIR / "Sift-v1.0-Portable.zip"
print(f"\n[*] Creating portable archive: {zip_target.name}...")
if zip_target.is_file():
    zip_target.unlink()

with zipfile.ZipFile(zip_target, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(app_dir):
        for file in files:
            full_path = Path(root) / file
            rel_path = full_path.relative_to(DIST_DIR)
            zf.write(full_path, arcname=str(rel_path))

zip_size_mb = zip_target.stat().st_size / (1024 * 1024)
print(f"[OK] Created {zip_target.name} ({zip_size_mb:.1f} MB)")

# 6. Generate Official Inno Setup Script
installer_iss_dir = REPO_ROOT / "installer"
installer_iss_dir.mkdir(exist_ok=True)
iss_path = installer_iss_dir / "sift_installer.iss"

dist_dir_str = str(DIST_DIR).replace('\\', '\\\\')
icon_path_str = str(ICON_PATH).replace('\\', '\\\\')
app_dir_str = str(app_dir).replace('\\', '\\\\')

iss_content = f"""; Inno Setup Script for Project Sift
; Compiles a lightweight, non-admin Windows installer
#define MyAppName "Sift"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Sift Commercial Deal Desk"
#define MyAppExeName "Sift.exe"

[Setup]
AppId={{{{E49B31D8-7241-4FB9-B6A0-1A87D095C2B4}}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
DefaultDirName={{localappdata}}\\Programs\\{{#MyAppName}}
DefaultGroupName={{#MyAppName}}
DisableProgramGroupPage=yes
OutputDir={dist_dir_str}
OutputBaseFilename=Sift-Setup-v1.0
SetupIconFile={icon_path_str}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"

[Files]
Source: "{app_dir_str}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{group}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; IconFilename: "{{app}}\\{{#MyAppExeName}}"
Name: "{{group}}\\Uninstall {{#MyAppName}}"; Filename: "{{uninstallexe}}"
Name: "{{autodesktop}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; IconFilename: "{{app}}\\{{#MyAppExeName}}"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\{{#MyAppExeName}}"; Description: "{{cm:LaunchProgram,{{#StringChange(MyAppName, '&', '&&')}}}}"; Flags: nowait postinstall skipifsilent
"""

with open(iss_path, "w", encoding="utf-8") as f:
    f.write(iss_content)
print(f"[OK] Generated Inno Setup script: {iss_path}")

# 7. Compile Self-Contained Non-Admin Setup Executable (Sift-Setup-v1.0.exe)
print("\n[*] Building standalone user-level setup wizard (Sift-Setup-v1.0.exe)...")
installer_py = REPO_ROOT / "scripts" / "installer_wizard.py"
if not installer_py.is_file():
    raise FileNotFoundError(f"Expected installer script at {installer_py}")

# Optional: Attempt Inno Setup ISCC compilation if installed
iscc_bin = None
for candidate_iscc in [
    shutil.which("iscc"),
    r"C:\Program Files (x86)\Inno Setup 6\iscc.exe",
    r"C:\Program Files\Inno Setup 6\iscc.exe",
]:
    if candidate_iscc and os.path.isfile(candidate_iscc):
        iscc_bin = candidate_iscc
        break

if iscc_bin:
    print(f"[*] Found Inno Setup Compiler at {iscc_bin}. Compiling official Inno installer...")
    try:
        subprocess.run([iscc_bin, str(iss_path)], check=True)
        print("[OK] Inno Setup installer compiled successfully.")
    except Exception as e:
        print(f"[WARNING] ISCC compilation failed ({e}), continuing with native PyInstaller wizard...")
else:
    print("[INFO] Inno Setup compiler not found on PATH. Generated .iss script for enterprise CI/CD.")


# Compile Setup Wizard with embedded payload into dist/Sift-Setup-v1.0.exe
print("[*] Packaging Sift-Setup-v1.0.exe via PyInstaller...")
setup_args = [
    sys.executable,
    "-m", "PyInstaller",
    "--noconfirm",
    "--onefile",
    "--windowed",
    "--name", "Sift-Setup-v1.0",
    f"--icon={ICON_PATH}",
    f"--add-data={app_dir};payload",
    f"--add-data={ICON_PATH};assets",
    str(installer_py),
]

subprocess.run(setup_args, cwd=str(REPO_ROOT), check=True)
setup_exe = DIST_DIR / "Sift-Setup-v1.0.exe"
if setup_exe.is_file():
    setup_size_mb = setup_exe.stat().st_size / (1024 * 1024)
    print(f"[OK] Created standalone installer: {setup_exe.name} ({setup_size_mb:.1f} MB)")

print("\n===============================================================================")
print("                   PACKAGING COMPLETED SUCCESSFULLY!                           ")
print("===============================================================================")
print(f"1. Portable Archive:  {zip_target} ({zip_size_mb:.1f} MB)")
print(f"2. Windows Installer: {setup_exe} ({setup_size_mb:.1f} MB)")
print(f"3. Inno Setup Script: {iss_path}")
print("===============================================================================\n")
