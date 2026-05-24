"""Helper script — installs required packages then writes KickAnalytics.spec and runs PyInstaller."""
import os, sys, subprocess, glob

root = os.path.dirname(os.path.abspath(__file__))

# ── Pre-build: ensure all required packages are installed system-wide ─────
# PyInstaller needs packages installed in the Python environment, not local packages\
REQUIRED = [
    "websockets",
    "curl_cffi",
    "keyring",
    "GPUtil",
    "psutil",
    "colorama",
    "tabulate",
    "typer",
]

print("Checking required packages for PyInstaller...")
for pkg in REQUIRED:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "show", pkg],
        capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  Installing {pkg}...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg, "-q",
             "--no-warn-script-location"],
            check=False)
    else:
        print(f"  ✓ {pkg} already installed")

print()
python_dir = os.path.dirname(sys.executable)

# ── Collect all needed DLLs ───────────────────────────────────
binaries = []

def add_dlls(*patterns):
    for pattern in patterns:
        for f in glob.glob(pattern):
            if os.path.isfile(f):
                binaries.append((f, '.'))

# SSL DLLs (Conda keeps these in Library\bin)
add_dlls(
    os.path.join(python_dir, "Library", "bin", "libssl*.dll"),
    os.path.join(python_dir, "Library", "bin", "libcrypto*.dll"),
    os.path.join(python_dir, "Library", "bin", "openssl*.dll"),
    os.path.join(python_dir, "DLLs", "_ssl*.pyd"),
    os.path.join(python_dir, "DLLs", "_hashlib*.pyd"),
)

# Tkinter DLLs
add_dlls(
    os.path.join(python_dir, "DLLs", "_tkinter*.pyd"),
    os.path.join(python_dir, "DLLs", "tcl*.dll"),
    os.path.join(python_dir, "DLLs", "tk*.dll"),
    os.path.join(python_dir, "Library", "bin", "tcl*.dll"),
    os.path.join(python_dir, "Library", "bin", "tk*.dll"),
)

print(f"Found {len(binaries)} DLLs to bundle:")
for b, _ in binaries:
    print(f"  {os.path.basename(b)}")

# ── TCL/TK data folders ───────────────────────────────────────
datas = []

def add_data(src_pattern, dst):
    for f in glob.glob(src_pattern):
        if os.path.exists(f):
            datas.append((f, dst))
            print(f"  Data: {f} -> {dst}")

# Find tcl/tk library folders
for tcl_dir in [
    os.path.join(python_dir, "Library", "lib"),
    os.path.join(python_dir, "tcl"),
    os.path.join(python_dir, "Lib", "tkinter"),
]:
    if os.path.isdir(tcl_dir):
        for sub in os.listdir(tcl_dir):
            full = os.path.join(tcl_dir, sub)
            if os.path.isdir(full) and sub.lower().startswith(("tcl", "tk")):
                datas.append((full, sub))
                print(f"  TCL/TK data: {full}")
        break

# Build spec strings
binaries_str = "\n".join(f"        (r'{b}', '{d}')," for b, d in binaries)
datas_str    = "\n".join(f"        (r'{b}', '{d}')," for b, d in datas)

spec_content = f"""# -*- mode: python -*-
block_cipher = None
a = Analysis(
    [r'{os.path.join(root, "kick_report.py")}'],
    pathex=[r'{root}'],
    binaries=[
{binaries_str}
    ],
    datas=[
{datas_str}
    ],
    hiddenimports=[
        'ssl', '_ssl',
        'tkinter', 'tkinter.ttk',
        'tkinter.scrolledtext',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'websockets',
        'websockets.legacy',
        'websockets.legacy.client',
        'websockets.legacy.server',
        'websockets.asyncio',
        'websockets.asyncio.client',
        'websockets.connection',
        'websockets.frames',
        'websockets.exceptions',
        'curl_cffi',
        'keyring',
        'keyring.backends',
        'keyring.backends.Windows',
        'GPUtil',
        'psutil',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts,
    [],
    exclude_binaries=True,
    name='KickAnalytics',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='KickAnalytics',
)
"""

spec_path = os.path.join(root, "KickAnalytics.spec")
with open(spec_path, "w") as f:
    f.write(spec_content)
print(f"Spec written: {spec_path}")

dist_path  = os.path.join(root, "dist")
build_path = os.path.join(root, "build_temp")

result = subprocess.run([
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--distpath", dist_path,
    "--workpath", build_path,
    spec_path,
], cwd=root)

sys.exit(result.returncode)
