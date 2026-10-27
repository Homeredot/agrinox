"""Train a crop-specific Plant Lens classifier with a held-out split.

Expected directory:
  DATASET_ROOT/
    Potato___Early_blight/
    Potato___Late_blight/
    Potato___healthy/

Use a curated dataset you are authorized to use. Never place the exported pickle
in an untrusted download path: FastAI exports use pickle and must be trusted.
"""

import argparse
import hashlib
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

CROP_CLASS_DIRS = {
    "potato": (
        "Potato___Early_blight",
        "Potato___Late_blight",
        "Potato___healthy",
    ),
    "tomato": (
        "Tomato_Bacterial_spot",
        "Tomato_Early_blight",
        "Tomato_Late_blight",
        "Tomato_Leaf_Mold",
        "Tomato_Septoria_leaf_spot",
        "Tomato_Spider_mites_Two_spotted_spider_mite",
        "Tomato__Target_Spot",
        "Tomato__Tomato_mosaic_virus",
        "Tomato__Tomato_YellowLeaf__Curl_Virus",
        "Tomato_healthy",
    ),
}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
UNSUPPORTED_LABEL = "Unsupported_or_wrong_crop"


def collect_images(dataset: Path, crop: str = "potato", unsupported_limit: int = 1200, per_class_limit: int = 0) -> tuple[list[dict], dict[str, int], int]:
    """Collect selected crop classes plus a sample of other-crop negatives.

    Some disease_dataset downloads contain a second complete ``disease_dataset`` tree
    inside the extraction directory. Restricting discovery to direct class
    folders prevents a byte-identical image from landing in both train and
    validation sets and producing misleading validation metrics.
    """
    supported_class_dirs = CROP_CLASS_DIRS[crop]
    missing = [name for name in supported_class_dirs if not (dataset / name).is_dir()]
    if missing:
        raise SystemExit(
            f"Missing required class folders in {dataset}: {', '.join(missing)}"
        )

    unique: dict[str, Path] = {}
    records: list[dict] = []
    class_counts: dict[str, int] = {}
    duplicate_count = 0
    for class_name in supported_class_dirs:
        class_files = sorted(
            path
            for path in (dataset / class_name).iterdir()
            if path.is_file() and path.suffix.casefold() in IMAGE_SUFFIXES
        )
        if per_class_limit and len(class_files) > per_class_limit:
            random.Random(f"42:{class_name}").shuffle(class_files)
            class_files = class_files[:per_class_limit]
        accepted = 0
        for path in class_files:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in unique:
                duplicate_count += 1
                continue
            unique[digest] = path
            records.append({"path": str(path), "label": class_name})
            accepted += 1
        class_counts[class_name] = accepted

    unsupported_candidates = [
        path
        for class_dir in dataset.iterdir()
        if class_dir.is_dir() and class_dir.name not in {*supported_class_dirs, "disease_dataset"}
        for path in class_dir.iterdir()
        if path.is_file() and path.suffix.casefold() in IMAGE_SUFFIXES
    ]
    random.Random(42).shuffle(unsupported_candidates)
    unsupported_count = 0
    for path in unsupported_candidates:
        if unsupported_count >= unsupported_limit:
            break
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in unique:
            duplicate_count += 1
            continue
        unique[digest] = path
        records.append({"path": str(path), "label": UNSUPPORTED_LABEL})
        unsupported_count += 1
    class_counts[UNSUPPORTED_LABEL] = unsupported_count

    if len(records) < 40 or any(count < 10 for count in class_counts.values()):
        raise SystemExit(
            "Dataset must contain at least 10 unique images in each supported class; "
            f"found {class_counts}"
        )
    return records, class_counts, duplicate_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--crop", choices=tuple(CROP_CLASS_DIRS), default="potato")
    parser.add_argument("--output", type=Path, default=Path("models/plant_lens_potato.pkl"))
    parser.add_argument("--version", default="fastai-potato-v1")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--image-size", type=int, default=160)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=0, help="Image-loader worker processes; use 2-4 on a multi-core machine")
    parser.add_argument("--unsupported-limit", type=int, default=1200)
    parser.add_argument("--per-class-limit", type=int, default=0, help="Maximum images per crop class; 0 uses all")
    parser.add_argument("--resume", type=Path, help="Trusted FastAI export to continue fine-tuning")
    parser.add_argument("--freeze-backbone", action="store_true", help="On resume, update only the classifier head; useful for a fast full-dataset coverage pass")
    args = parser.parse_args()

    from fastai.vision.all import (
        DataBlock,
        ImageBlock,
        Resize,
        accuracy,
        aug_transforms,
        CategoryBlock,
        ColReader,
        CrossEntropyLossFlat,
        error_rate,
        models,
        load_learner,
        vision_learner,
    )
    import pandas as pd
    import torch

    records, class_counts, duplicate_count = collect_images(
        args.dataset.resolve(), args.crop, args.unsupported_limit, args.per_class_limit
    )
    frame = pd.DataFrame.from_records(records)

    # Split the explicit, deduplicated file list. Using the path's parent as the
    # label preserves the labels supplied by the Kaggle disease_dataset dataset.
    from fastai.data.transforms import RandomSplitter

    splitter = RandomSplitter(valid_pct=0.2, seed=42)
    dls = DataBlock(
        blocks=(ImageBlock, CategoryBlock),
        get_x=ColReader("path"),
        get_y=ColReader("label"),
        splitter=splitter,
        item_tfms=Resize(args.image_size),
        batch_tfms=aug_transforms(size=args.image_size, min_scale=0.8),
    ).dataloaders(frame, bs=args.batch_size, num_workers=args.workers)

    class_weights = torch.tensor(
        [math.sqrt(len(records) / (len(dls.vocab) * class_counts[str(label)])) for label in dls.vocab],
        dtype=torch.float32,
    )

    loss_func = CrossEntropyLossFlat(weight=class_weights)
    if args.resume:
        learner = load_learner(args.resume.resolve(), cpu=True)
        learner.dls = dls
        learner.loss_func = loss_func
        learner.metrics = [accuracy, error_rate]
        if args.freeze_backbone:
            learner.freeze()
            learner.fit_one_cycle(args.epochs, lr_max=3e-4)
        else:
            learner.unfreeze()
            learner.fit_one_cycle(args.epochs, lr_max=slice(1e-5, 1e-4))
    else:
        learner = vision_learner(
            dls,
            models.resnet18,
            loss_func=loss_func,
            metrics=[accuracy, error_rate],
        )
        learner.fine_tune(args.epochs)
    predictions, targets, losses = learner.get_preds(ds_idx=1, with_loss=True)
    decoded = predictions.argmax(dim=1)
    validation_accuracy = float((decoded == targets).float().mean())
    validation_loss = float(losses.mean())
    class_count = len(dls.vocab)
    confusion = torch.bincount(
        targets.to(torch.int64) * class_count + decoded.to(torch.int64),
        minlength=class_count * class_count,
    ).reshape(class_count, class_count)
    class_metrics = []
    for index, label in enumerate(dls.vocab):
        true_positive = int(confusion[index, index])
        predicted = int(confusion[:, index].sum())
        actual = int(confusion[index, :].sum())
        class_metrics.append({
            "class": str(label),
            "precision": true_positive / predicted if predicted else None,
            "recall": true_positive / actual if actual else None,
            "validation_images": actual,
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    learner.export(args.output)
    metadata = {
        "model_version": args.version,
        "crop": args.crop,
        "framework": "fastai",
        "architecture": "resnet18 transfer learning",
        "resumed_from": str(args.resume.resolve()) if args.resume else None,
        "backbone_frozen_during_this_run": bool(args.resume and args.freeze_backbone),
        "image_size": args.image_size,
        "classes": [str(item) for item in dls.vocab],
        "dataset": {
            "name": "disease_dataset / Plant Disease Recognition (Kaggle emmarex/plantdisease)",
            "source": "https://www.kaggle.com/datasets/emmarex/plantdisease/",
            "root": str(args.dataset.resolve()),
            "unique_class_counts": class_counts,
            "duplicates_excluded_within_selected_tree": duplicate_count,
            "nested_dataset_trees_excluded": True,
            "unsupported_sampling": "Deterministic sample of direct other-crop folders with seed 42.",
        },
        "training_images": len(dls.train_ds),
        "validation_images": len(dls.valid_ds),
        "validation_design": "File-level random 80/20 held-out split with seed 42; validation images are not used for gradient updates.",
        "validation_loss": validation_loss,
        "validation_accuracy": validation_accuracy,
        "validation_error_rate": 1.0 - validation_accuracy,
        "per_class_validation": class_metrics,
        "confusion_matrix": confusion.tolist(),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            f"disease_dataset-style images may not represent Rwanda field backgrounds, lighting, cultivars or all {args.crop} disorders.",
            "The unsupported class improves rejection of included other-crop images but cannot represent every possible unrelated photograph.",
            "Validate on an independent Rwanda field dataset before clinical or automatic treatment use.",
        ],
    }
    args.output.with_suffix(".metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
