from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from qlib_tradingbot.config import ARTIFACTS_DIR

try:  # pragma: no cover
    from qlib.contrib.model.gbdt import LGBModel
    QLIB_MODEL_AVAILABLE = True
except Exception:  # pragma: no cover
    LGBModel = object  # type: ignore
    QLIB_MODEL_AVAILABLE = False


@dataclass
class TrainedModel:
    model: Any
    artifacts_dir: Path


def train_lightgbm(
    dataset_bundle,
    *,
    params: Optional[Dict[str, Any]] = None,
    artifacts_subdir: str = "models/lgbm_scalp_v1",
) -> TrainedModel:
    """Train a LightGBM model via Qlib's model wrapper."""
    if not QLIB_MODEL_AVAILABLE:
        raise RuntimeError("pyqlib (and its LightGBM extras) are not installed.")

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out_dir = ARTIFACTS_DIR / artifacts_subdir
    out_dir.mkdir(parents=True, exist_ok=True)

    params = params or {
        "loss": "mse",
        "colsample_bytree": 0.9,
        "learning_rate": 0.05,
        "subsample": 0.9,
        "lambda_l1": 1.0,
        "lambda_l2": 1.0,
        "max_depth": 6,
        "num_leaves": 63,
        "num_threads": 4,
    }

    model = LGBModel(**params)
    model.fit(dataset_bundle.dataset)
    return TrainedModel(model=model, artifacts_dir=out_dir)


def predict(model: TrainedModel, dataset_bundle, *, segment: str = "test") -> pd.Series:
    """Predict and return a pd.Series with MultiIndex (datetime, instrument)."""
    preds = model.model.predict(dataset_bundle.dataset, segment=segment)
    # qlib returns pd.Series already; normalize
    if isinstance(preds, pd.DataFrame) and preds.shape[1] == 1:
        preds = preds.iloc[:, 0]
    return preds.sort_index()
