"""
解析 QMT 的 bin.x64，将 **含 xtquant 包的目录** 加入 sys.path，并在 Windows 上注册 DLL 搜索路径。

华鑫等安装布局示例（你已本机验证）：
  bin.x64\\Lib\\site-packages\\xtquant\\...
  ..\\userdata_mini\\          ← XtQuantTrader(path, ...) 的 path 指向此处

若仅把 bin.x64 根目录加入 sys.path，**无法** import xtquant（包在 site-packages 下）。
"""

from __future__ import annotations

import os
import sys

from app import config

_added_sys_path: str | None = None
_qmt_bin_x64_for_dll: str | None = None


def _is_xtquant_dir(parent: str) -> bool:
    xq = os.path.join(parent, "xtquant")
    return os.path.isdir(xq)


def _resolve_xtquant_sys_path(bin_or_seed: str) -> str | None:
    """
    在 bin.x64（或任意已存在目录）下解析应加入 sys.path 的目录。
    优先：bin.x64/Lib/site-packages；兼容：seed 下直接含 xtquant。
    """
    seed = os.path.abspath(bin_or_seed)
    if not os.path.isdir(seed):
        return None

    sp = os.path.join(seed, "Lib", "site-packages")
    if _is_xtquant_dir(sp):
        return sp
    if _is_xtquant_dir(seed):
        return seed
    return None


def _ensure_bin_x64_dll_path(site_packages_root: str) -> None:
    """Windows：为 xtquant 自带 .pyd 注册 DLL 目录（与 qmt_data_server 思路一致）。"""
    global _qmt_bin_x64_for_dll
    if sys.platform != "win32":
        return

    cur = os.path.abspath(site_packages_root)
    bin_x64: str | None = None
    for _ in range(20):
        base = os.path.basename(cur).lower()
        if base == "bin.x64" and os.path.isdir(cur):
            bin_x64 = cur
            break
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent

    if bin_x64 is None:
        return
    _qmt_bin_x64_for_dll = bin_x64

    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(bin_x64)
        except OSError:
            pass
        for sub in ("lib", "Lib"):
            extra = os.path.join(bin_x64, sub)
            if os.path.isdir(extra):
                try:
                    os.add_dll_directory(extra)
                except OSError:
                    pass

    os.environ["PATH"] = bin_x64 + os.pathsep + os.environ.get("PATH", "")


def init_xtquant_path() -> str | None:
    """
    将含 xtquant 的目录 append 到 sys.path（append 而非 insert，避免抢走 venv 里的 numpy/pandas）。

    QMT_BIN_DIR：填 **bin.x64** 的绝对路径即可（与 qmt_data_server 一致）。

    返回实际加入 sys.path 的目录；失败返回 None。
    """
    global _added_sys_path
    if _added_sys_path and _added_sys_path in sys.path:
        return _added_sys_path

    root = config.QMT_BIN_DIR.strip()
    if not root:
        return None

    resolved = _resolve_xtquant_sys_path(root)
    if not resolved:
        return None

    _ensure_bin_x64_dll_path(resolved)

    if resolved not in sys.path:
        sys.path.append(resolved)
    _added_sys_path = resolved
    return resolved
