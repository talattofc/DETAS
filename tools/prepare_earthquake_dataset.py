"""DETAS earthquake rescue YOLO dataset hazirlama araci."""

import argparse
import random
import shutil
from pathlib import Path


CLASSES = [
    "person",
    "rubble",
    "blocked_road",
    "collapsed_building",
    "damaged_vehicle",
    "fire_smoke",
    "rescue_worker",
    "safe_passage",
]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-dir",
        default="datasets/earthquake_rescue",
        help="Dataset kok klasoru",
    )
    parser.add_argument("--train", type=float, default=0.70, help="Train orani")
    parser.add_argument("--valid", type=float, default=0.20, help="Validation orani")
    parser.add_argument("--seed", type=int, default=42, help="Deterministik split seed")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Mevcut train/valid/test kopyalarini temizleyip yeniden olustur",
    )
    return parser.parse_args()


def ensure_dirs(dataset_dir):
    for split in ["train", "valid", "test"]:
        (dataset_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (dataset_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    (dataset_dir / "raw" / "images").mkdir(parents=True, exist_ok=True)
    (dataset_dir / "raw" / "labels").mkdir(parents=True, exist_ok=True)


def clear_split_dirs(dataset_dir):
    for split in ["train", "valid", "test"]:
        for root in [dataset_dir / "images" / split, dataset_dir / "labels" / split]:
            if not root.exists():
                continue

            for path in root.iterdir():
                if path.name == ".gitkeep":
                    continue
                if path.is_file():
                    path.unlink()


def read_pairs(dataset_dir):
    raw_images = dataset_dir / "raw" / "images"
    raw_labels = dataset_dir / "raw" / "labels"
    pairs = []
    missing_labels = []

    for image_path in sorted(raw_images.iterdir()):
        if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        label_path = raw_labels / f"{image_path.stem}.txt"
        if not label_path.exists():
            missing_labels.append(image_path.name)
            continue

        pairs.append((image_path, label_path))

    return pairs, missing_labels


def validate_label_file(label_path):
    errors = []

    for line_no, line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) != 5:
            errors.append(f"{label_path}:{line_no} 5 alan bekleniyor")
            continue

        try:
            class_id = int(parts[0])
            coords = [float(value) for value in parts[1:]]
        except ValueError:
            errors.append(f"{label_path}:{line_no} sayisal olmayan deger")
            continue

        if class_id < 0 or class_id >= len(CLASSES):
            errors.append(f"{label_path}:{line_no} gecersiz class_id {class_id}")

        if any(value < 0 or value > 1 for value in coords):
            errors.append(f"{label_path}:{line_no} koordinatlar 0-1 araliginda olmali")

    return errors


def split_pairs(pairs, train_ratio, valid_ratio, seed):
    if train_ratio <= 0 or valid_ratio < 0 or train_ratio + valid_ratio >= 1:
        raise ValueError("Split oranlari train > 0, valid >= 0 ve train+valid < 1 olmali")

    pairs = list(pairs)
    random.Random(seed).shuffle(pairs)

    train_end = int(len(pairs) * train_ratio)
    valid_end = train_end + int(len(pairs) * valid_ratio)

    return {
        "train": pairs[:train_end],
        "valid": pairs[train_end:valid_end],
        "test": pairs[valid_end:],
    }


def copy_split(dataset_dir, splits):
    for split, pairs in splits.items():
        for image_path, label_path in pairs:
            shutil.copy2(image_path, dataset_dir / "images" / split / image_path.name)
            shutil.copy2(label_path, dataset_dir / "labels" / split / label_path.name)


def write_data_yaml(dataset_dir):
    names = "\n".join(f"  {index}: {name}" for index, name in enumerate(CLASSES))
    content = (
        f"path: {dataset_dir.as_posix()}\n"
        "train: images/train\n"
        "val: images/valid\n"
        "test: images/test\n"
        f"names:\n{names}\n"
    )
    (dataset_dir / "data.yaml").write_text(content, encoding="utf-8")


def supervision_validate(dataset_dir):
    try:
        import supervision as sv
    except Exception:
        return "supervision kurulu degil, ek dataset dogrulamasi atlandi"

    try:
        dataset = sv.DetectionDataset.from_yolo(
            images_directory_path=str(dataset_dir / "images" / "train"),
            annotations_directory_path=str(dataset_dir / "labels" / "train"),
            data_yaml_path=str(dataset_dir / "data.yaml"),
        )
        return f"supervision dogrulamasi OK, train ornek sayisi: {len(dataset)}"
    except Exception as exc:
        return f"supervision dogrulamasi basarisiz: {exc}"


def main():
    args = parse_args()
    dataset_dir = Path(args.dataset_dir)

    ensure_dirs(dataset_dir)

    if args.clear:
        clear_split_dirs(dataset_dir)

    pairs, missing_labels = read_pairs(dataset_dir)
    label_errors = []

    for _, label_path in pairs:
        label_errors.extend(validate_label_file(label_path))

    if missing_labels:
        print("Label bulunamayan goruntuler:")
        for name in missing_labels:
            print(f"  - {name}")

    if label_errors:
        print("Label hatalari:")
        for error in label_errors:
            print(f"  - {error}")
        raise SystemExit(1)

    splits = split_pairs(pairs, args.train, args.valid, args.seed)
    copy_split(dataset_dir, splits)
    write_data_yaml(dataset_dir)

    print("Dataset hazirlandi:")
    for split, split_pairs_ in splits.items():
        print(f"  {split}: {len(split_pairs_)}")

    print(supervision_validate(dataset_dir))


if __name__ == "__main__":
    main()
