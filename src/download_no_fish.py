import shutil
import subprocess
from pathlib import Path

# =========================
# KONFIGURATION
# =========================

DOWNLOAD_COMMAND = "oi_download_images"
OUTPUT_DIR = "/Users/enis.namikaze/Desktop/Test"
LIMIT_PER_CLASS = 5

LABELS = [
    "Chair",
    "Car",
    "Table",
    "Person",
    "Dog",
    "Cat",
    "Boat",
    "Tree",
    "Bicycle",
    "Bus",
    "Truck",
    "House",
]

EXTRA_ARGS = []

# =========================
# HILFSFUNKTIONEN
# =========================

def get_unique_target_path(base_dir: Path, stem: str, suffix: str, start_index: int) -> Path:
    index = start_index
    while True:
        candidate = base_dir / f"{stem}{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def flatten_downloaded_images(base_dir: Path):
    print("Verschiebe Bilder direkt ins Hauptverzeichnis...")

    for label in LABELS:
        label_dir = base_dir / label.lower()
        images_dir = label_dir / "images"

        if not images_dir.exists():
            print(f"Warnung: Kein images-Ordner gefunden für Label '{label}'.")
            continue

        image_files = sorted([p for p in images_dir.iterdir() if p.is_file()])
        if not image_files:
            print(f"Warnung: Keine Bilder gefunden für Label '{label}'.")
            continue

        counter = 1
        for image_file in image_files:
            target_path = get_unique_target_path(
                base_dir=base_dir,
                stem=label.lower(),
                suffix=image_file.suffix.lower(),
                start_index=counter,
            )

            shutil.move(str(image_file), str(target_path))
            print(f"Verschoben: {image_file.name} -> {target_path.name}")

            counter += 1

        # Leere Klassenordner nach dem Verschieben entfernen
        try:
            shutil.rmtree(label_dir)
            print(f"Ordner entfernt: {label_dir}")
        except Exception as e:
            print(f"Warnung: Konnte Ordner {label_dir} nicht entfernen: {e}")


# =========================
# HAUPTPROGRAMM
# =========================

def main():
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)

    command_path = shutil.which(DOWNLOAD_COMMAND)
    if command_path is None:
        print(f"Fehler: Der Befehl '{DOWNLOAD_COMMAND}' wurde nicht gefunden.")
        print("Aktiviere zuerst die virtuelle Umgebung und starte dann das Skript mit:")
        print("source .venv/bin/activate")
        print("python src/download_no_fish.py")
        return

    cmd = [
        command_path,
        "--base_dir", str(output_path),
        "--limit", str(LIMIT_PER_CLASS),
        "--labels",
        *LABELS,
        *EXTRA_ARGS,
    ]

    print("Starte Download mit folgendem Befehl:")
    print(" ".join(cmd))
    print()

    try:
        subprocess.run(cmd, check=True)
        print("Download abgeschlossen.")
        flatten_downloaded_images(output_path)
        print("Alle Bilder liegen jetzt direkt im Test-Ordner.")
    except subprocess.CalledProcessError as e:
        print(f"Fehler beim Download. Rückgabecode: {e.returncode}")
        print("Wahrscheinlich ist mindestens ein Label im Open-Images-Katalog nicht exakt vorhanden.")
        print("Verwende vorerst nur diese getesteten Labels:")
        print(", ".join(LABELS))


if __name__ == "__main__":
    main()