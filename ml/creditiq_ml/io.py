"""Data input layer: locate + load CSVs with memory down-casting."""
from __future__ import annotations
import logging
import numpy as np
import pandas as pd
from . import config as C

log = logging.getLogger(__name__)


def find_file(key: str):
    files = {p.name.lower(): p for p in C.RAW_DIR.glob("*") if p.suffix.lower() == ".csv"}
    for cand in C.FILES[key]:
        if cand.lower() in files:
            return files[cand.lower()]
    return None


def exists(key: str) -> bool:
    return find_file(key) is not None


def reduce_memory(df: pd.DataFrame) -> pd.DataFrame:
    # Preserve float64 for cent-level payment reconciliation.
    for c in df.select_dtypes(include=["int64"]).columns:
        df[c] = pd.to_numeric(df[c], downcast="integer")
    return df


def load(key: str, usecols=None) -> pd.DataFrame:
    path = find_file(key)
    if path is None:
        raise FileNotFoundError(
            f"'{key}' not found in {C.RAW_DIR}. Expected one of: {C.FILES[key]}")
    log.info("Loading %s", path.name)
    df = pd.read_csv(path, usecols=usecols)
    return reduce_memory(df)
