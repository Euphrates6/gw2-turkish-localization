import zipfile
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def zip_directory(source_dir: Path, output_zip: Path):
    if not source_dir.exists():
        print(f"[ERROR] Source directory does not exist: {source_dir}")
        return
    print(f"Compressing {source_dir.name} -> {output_zip.name}...")
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for f in source_dir.rglob("*"):
            if f.is_file():
                arcname = str(f.relative_to(source_dir))
                z.write(f, arcname)
    size_mb = output_zip.stat().st_size / (1024 * 1024)
    print(f"[OK] Zip created: {output_zip.name} ({size_mb:.2f} MB)")

def create_zips(make_offline=True, make_online=True):
    if make_offline:
        zip_directory(BASE_DIR / "release_package_offline", BASE_DIR / "Local_Translator_Cevrimdisi_TR.zip")
    if make_online:
        zip_directory(BASE_DIR / "release_package_online", BASE_DIR / "Local_Translator_Cevrimici_TR.zip")

def main():
    parser = argparse.ArgumentParser(description="Create release zip packages for GW2 Turkish Localization")
    parser.add_argument("--offline", action="store_true", help="Create only offline zip")
    parser.add_argument("--online", action="store_true", help="Create only online zip")
    args = parser.parse_args()

    if args.offline:
        create_zips(make_offline=True, make_online=False)
    elif args.online:
        create_zips(make_offline=False, make_online=True)
    else:
        create_zips(make_offline=True, make_online=True)

if __name__ == "__main__":
    main()
