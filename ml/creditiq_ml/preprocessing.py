"""Cleaning + encoding as a single sklearn ColumnTransformer (fit on TRAIN only -> no leakage)."""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from .contracts import CATEGORICAL, VOCABULARIES


class Winsorizer(BaseEstimator, TransformerMixin):
    """Outlier handling: clip each numeric column to [q_low, q_high] learned on train."""

    def __init__(self, lower: float = 0.01, upper: float = 0.99):
        self.lower, self.upper = lower, upper

    def fit(self, X, y=None):
        X = pd.DataFrame(X)
        self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        self.lo_ = X.quantile(self.lower)
        self.hi_ = X.quantile(self.upper)
        return self

    def transform(self, X):
        X = pd.DataFrame(X).copy()
        return X.clip(lower=self.lo_, upper=self.hi_, axis=1)

    def get_feature_names_out(self, input_features=None):
        return self.feature_names_in_


def split_columns(X: pd.DataFrame, max_missing: float = 1.0):
    # A fixed contract must not silently drop high-missingness fields.
    cat = [c for c in CATEGORICAL if c in X]
    num = [c for c in X.columns if c not in cat]
    return num, cat


def build_preprocessor(num_cols, cat_cols) -> ColumnTransformer:
    # No blanket clipping: rare flags and delinquency tails retain their meaning.
    num = Pipeline([("impute", SimpleImputer(strategy="median", keep_empty_features=True))])
    cat = Pipeline([("impute", SimpleImputer(strategy="constant", fill_value="MISSING")),
                    ("ohe", OneHotEncoder(categories=[VOCABULARIES[c] for c in cat_cols],
                                          handle_unknown="error", sparse_output=False))])
    ct = ColumnTransformer([("num", num, list(num_cols)), ("cat", cat, list(cat_cols))],
                           remainder="drop", verbose_feature_names_out=False)
    ct.set_output(transform="pandas")
    return ct
