"""Windows process detection guard for GW2-TR Hub.

Uses ctypes + Win32 CreateToolhelp32Snapshot (no external dependencies,
no console window flash, no locale-dependent tasklist parsing).
"""
from __future__ import annotations

import sys

BLOCKING_PROCESSES: frozenset[str] = frozenset({
    "gw2-64.exe",
    "gw2.exe",
    "local_translator_tr.exe",
})


def running_process_names() -> set[str]:
    """Returns lowercase executable names of all currently running processes."""
    if sys.platform != "win32":
        return set()

    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_void_p),  # ULONG_PTR (x64 safe)
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    k32 = ctypes.windll.kernel32
    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    k32.Process32FirstW.restype = wintypes.BOOL
    k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    k32.Process32NextW.restype = wintypes.BOOL
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.CloseHandle.restype = wintypes.BOOL

    invalid_handle = ctypes.c_void_p(-1).value
    snap = k32.CreateToolhelp32Snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
    if not snap or snap == invalid_handle:
        return set()

    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    names: set[str] = set()
    try:
        if k32.Process32FirstW(snap, ctypes.byref(entry)):
            while True:
                if entry.szExeFile:
                    names.add(entry.szExeFile.lower())
                if not k32.Process32NextW(snap, ctypes.byref(entry)):
                    break
    finally:
        k32.CloseHandle(snap)
    return names


def blocking_processes(running: set[str] | None = None) -> list[str]:
    """Returns sorted list of running processes that would lock GW2-TR files."""
    active = running_process_names() if running is None else {p.lower() for p in running}
    return sorted(BLOCKING_PROCESSES & active)
