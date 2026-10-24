#!/usr/bin/env python3
"""CLI utility to compile collected datasets into headcount_model.pkl."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings
from src.detector.trainer import train_headcount_model


def main():
    print("=" * 60)
    print("  Headcount Classifier Model Trainer")
    print("=" * 60)

    try:
        train_headcount_model(
            processed_dir=settings.DATA_PROCESSED_DIR,
            model_output_path=settings.HEADCOUNT_MODEL_PATH,
        )
    except Exception as e:
        print(f"\n[-] Training failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
