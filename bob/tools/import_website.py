"""Copy the built story website into Bob, so one local server serves the website and the dashboards.

    cd ../vitamin-bob-site && npm run build        # Next.js static export with basePath /website
    python tools/import_website.py [path/to/vitamin-bob-site/out]

Bob then serves it at http://127.0.0.1:8100/website/ (and / redirects there). Its "Live call" screen
embeds /dashboard/live from the same origin, as stuart/WEBSITE_INTEGRATION.md recommends.
"""

import shutil
import sys
from pathlib import Path

BOB_DIR = Path(__file__).resolve().parents[1]
TARGET = BOB_DIR / "vitamin_bob" / "website"
DEFAULT_SRC = BOB_DIR.parents[1] / "vitamin-bob-site" / "out"


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    if not (src / "index.html").exists():
        print(f"No built site at {src}. Run `npm run build` in vitamin-bob-site first.")
        return 1
    if "/website/_next/" not in (src / "index.html").read_text(encoding="utf-8"):
        print("The build was not made with basePath '/website'; check next.config.ts.")
        return 1
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(src, TARGET)
    files = sum(1 for p in TARGET.rglob("*") if p.is_file())
    size = sum(p.stat().st_size for p in TARGET.rglob("*") if p.is_file()) / 1e6
    print(f"Copied {files} files ({size:.1f} MB) to {TARGET}. Restart Bob and open /website/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
