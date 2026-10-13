# Project Sift: Distribution & Deployment Guide

> **Commercial Audit & Margin Triage Engine**  
> *Air-Gapped, Local-First Commercial Deal Desk & Margin Analytics Platform*

---

## 1. Distribution Overview & Strategy

Project Sift is engineered specifically for corporate commercial deal desks, revenue operations, and financial controllers who operate under stringent enterprise IT constraints:
- **Zero Administrative Elevation**: Target workstations typically block standard Windows UAC / Administrator prompts.
- **Air-Gapped / Zero-Telemetry Compliance**: No outbound network requests, external telemetry, or cloud-hosted dependencies.
- **No Pre-Installed Runtime Dependencies**: Non-technical financial analysts do not have Python, Node.js, or Git installed.
- **High-Volume Analytical Performance**: Capable of ingesting 2,000,000+ granular ERP transactions using an embedded, in-process DuckDB engine.

To meet these diverse enterprise scenarios, Sift is packaged into **two primary distribution formats**, supported by an enterprise IT script and a developer audit mode.

---

## 2. Distribution Formats: Which One to Use When?

| Distribution Format | Target Audience | Installation Rights | Desktop / Start Menu Shortcuts | Recommended Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **`Sift-v1.0-Portable.zip`** *(Portable Archive)* | Finance Controllers, Commercial Analysts, External Auditors | **Zero Rights Needed** (Runs from any folder or USB) | Manual shortcut or run directly | **Locked-down corporate PCs**, shared network drives (`\\corp\finance\`), running off encrypted USB drives, or evaluation without modifying the workstation. |
| **`Sift-Setup-v1.0.exe`** *(User-Level Setup Wizard)* | Commercial Deal Desk, Pricing Teams, Routine Users | **Zero Rights Needed** (Installs to `%LOCALAPPDATA%`) | **Automatic** (Desktop & Start Menu with custom icon) | **Daily workstation deployment**. Provides standard Windows app experience with desktop icons, start menu integration, and uninstaller. |
| **`sift_installer.iss`** *(Enterprise Inno Setup Script)* | Corporate IT Admins, Desktop Engineering | Configurable (User or Machine-wide) | Automatic via enterprise software centers | **Mass enterprise rollout** via Microsoft Intune, SCCM, Winget, or when corporate policy requires signing with internal Authenticode certificates. |
| **`setup.bat` & `run.bat`** *(Developer / Source Mode)* | Financial Data Engineers, Code Reviewers | Python 3.10+ required on host | N/A (Terminal / Batch execution) | **Code audits**, schema inspection, extending algorithms, or running the automated test suite (`pytest`). |

---

## 3. Detailed Usage Instructions

### Option A: Portable Archive (`Sift-v1.0-Portable.zip`)

**Best When**: You cannot run installers, your IT policy blocks `.exe` installations in user profiles, or you want to run Sift from a network share or USB drive.

1. **Download / Copy**: Place `Sift-v1.0-Portable.zip` on your machine.
2. **Extract**: Right-click the `.zip` file and select **Extract All...** to any folder (e.g., `C:\Tools\Sift` or your `Desktop`).
3. **Launch**:
   - Double-click **`Sift.exe`** (or **`Launch-Sift.bat`**).
   - The Sift standalone window will automatically launch on `http://127.0.0.1:8765`.
4. **Uninstallation / Removal**: Simply delete the extracted folder. No registry keys or hidden files are created.

---

### Option B: Standalone Setup Wizard (`Sift-Setup-v1.0.exe`)

**Best When**: You want a permanent desktop shortcut and start menu entry for daily commercial auditing without needing IT support.

1. **Launch Wizard**: Double-click `Sift-Setup-v1.0.exe`.
2. **Zero UAC Elevation**: Notice that Windows will **not** ask for Administrator credentials. Sift installs cleanly to:
   ```text
   %LOCALAPPDATA%\Programs\Sift\
   ```
3. **Customize Shortcuts**: Keep "Create a Desktop Shortcut" and "Create a Start Menu Shortcut" checked.
4. **Click Install**: The wizard unpacks the analytical engine, installs the branding icon, and registers shortcuts in 3–5 seconds.
5. **Launch**: Check "Launch Sift now" or open Sift anytime from your Windows Start Menu or Desktop.

#### Enterprise IT Silent Deployment:
System administrators can deploy `Sift-Setup-v1.0.exe` silently across multiple workstations without showing any GUI:
```cmd
Sift-Setup-v1.0.exe /S
:: Or:
Sift-Setup-v1.0.exe --silent
```

---

### Option C: Enterprise Inno Setup Script (`installer/sift_installer.iss`)

**Best When**: Enterprise IT demands standard MSI/Inno installers signed by a corporate Code Signing Certificate.

1. Install [Inno Setup 6](https://jrsoftware.org/isdl.php).
2. Open `installer/sift_installer.iss`.
3. (Optional) Add your corporate Authenticode signing command:
   ```pascal
   SignTool=signtool sign /sha1 <THUMBPRINT> /fd sha256 $f
   ```
4. Click **Compile** (or run `iscc installer/sift_installer.iss`).
5. Distribute the resulting `Sift-Setup-v1.0.exe` via Microsoft Intune or SCCM.

---

### Option D: Developer & Audit Mode (`setup.bat` & `run.bat`)

**Best When**: Technical auditors or pricing engineers need to inspect the Python/React codebase, review DuckDB analytical schemas, or execute unit/E2E test suites.

1. Open a terminal in the project directory:
   ```cmd
   cd C:\Shift
   ```
2. Run the environment setup script:
   ```cmd
   setup.bat
   ```
   *Creates an isolated `.venv`, upgrades pip, installs locked dependencies from `requirements.txt`, verifies `src/dist` frontend assets, and executes self-diagnostic smoke tests.*
3. Launch the desktop runtime:
   ```cmd
   run.bat
   ```
   *Binds FastAPI to `127.0.0.1:8765`, launches Microsoft Edge in standalone air-gapped app mode (`--app=http://127.0.0.1:8765`), and handles graceful dual-process supervision.*

---

## 4. System & Hardware Requirements

| Parameter | Minimum Specification | Recommended Specification |
| :--- | :--- | :--- |
| **Operating System** | Windows 10 (64-bit) / Windows 11 | Windows 11 (64-bit) |
| **Processor (CPU)** | Dual-core 2.0 GHz x64 | Quad-core 3.0+ GHz x64 |
| **Memory (RAM)** | 4 GB | 16 GB (for multi-million row datasets) |
| **Free Disk Space** | 500 MB | 2 GB (for temporary workspace disk-spill) |
| **Display Resolution** | 1366 × 768 | 1920 × 1080 or higher |
| **Network Connection** | **None (100% Offline / Air-Gapped)** | None |

---

## 5. Security, Privacy & Compliance Safeguards

Sift adheres to institutional security protocols required by Fortune 500 financial institutions:

1. **Air-Gapped Isolation**:
   - The backend server binds strictly to the loopback interface (`127.0.0.1:8765`).
   - All CORS origins and Host headers are strictly validated against localhost.
   - The embedded Chromium/Edge process runs with `--disable-background-networking`, `--disable-sync`, and `--disable-component-update`.
2. **In-Process DuckDB Analytical Engine**:
   - High-performance columnar processing without requiring a separate database server.
   - Hard memory ceiling enforced at **4 GB**, with automatic spill-to-disk for out-of-core multi-million row calculations.
3. **Encrypted Workspace Archives (`.mxa`)**:
   - Workspaces encapsulate schema, transaction data, calibration baselines, and investigation status.
   - Supports AES-256 zip encryption with user-defined passwords.
4. **Anti-CSV Formula Injection**:
   - All exported Excel and CSV files neutralize spreadsheet formula triggers (`=`, `+`, `-`, `@`, `\t`, `\r`) to protect analysts from malicious payload execution.
5. **ToneGuard™ Policy Enforcement**:
   - Free-form audit notes and executive summaries are validated at write-time against inflammatory, accusatory, or legally hazardous language (e.g., "fraud", "kickback", "bribe").

---

## 6. Verification & Test Data

The application comes equipped with a comprehensive manual testing suite located in `manual_testing/`:
- **Datasets**: 7 test datasets spanning clean baselines, high-drift inflation scenarios, extreme contract stacking, and a **2,000,000-row enterprise benchmark** (`enterprise_2m_transactions.parquet`).
- **Testing Guide**: Consult `manual_testing/MANUAL_TESTING_GUIDE.md` for 11 complex edge-case test protocols detailing exact expected results, margin recovery yields, and error bounds.
