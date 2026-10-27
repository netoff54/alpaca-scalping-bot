"""
========================================================================================
AUDIT & BACKTEST RESMI 2 TAHUN (24 BULAN) - KALIMASADA & MARGIN PATEN $1.00 / 1.0%
========================================================================================
EntryPoint resmi untuk menjalankan backtest komprehensif 24 bulan (November 2024 s/d Oktober 2026).
"""

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backtest_2year_dynamic_1dollar_official import main

if __name__ == "__main__":
    main()
