import json
import sys
from pathlib import Path

from app.main import create_app

TARGET = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


def main() -> None:
    content = (
        json.dumps(create_app().openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    if "--check" in sys.argv:
        if not TARGET.exists() or TARGET.read_text() != content:
            raise SystemExit("OpenAPI changed. Run npm run api:generate and commit both contracts.")
    else:
        TARGET.write_text(content)


if __name__ == "__main__":
    main()
