import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
# "packages": ["os"] is used as example only
build_exe_options = {
    "packages": ["os", "numpy", "numpy.core._methods", "matplotlib"],
    "includes": ["numpy.core._methods", "numpy", "tkinter", "pandas.plotting._matplotlib"]}

# base="Win32GUI" should be used only for Windows GUI app
base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(
    name="tout-compare",
    version="0.0.16",
    description="Compare TOUT electricity tariffs",
    options={
        "build_exe": build_exe_options
        },
    executables=[Executable("toutc.py", base=base)],
)