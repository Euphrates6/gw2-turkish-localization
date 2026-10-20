import zipfile
from pathlib import Path

def create_zip():
    zip_path = Path("Local_Translator_0.10.0_TR.zip")
    root = Path("release_package")
    print("Compressing release package...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in root.rglob("*"):
            if f.is_file():
                arcname = str(f.relative_to(root))
                z.write(f, arcname)
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Zip created: {zip_path.name} ({size_mb:.2f} MB)")

if __name__ == "__main__":
    create_zip()
