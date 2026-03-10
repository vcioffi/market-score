from __future__ import annotations

from _bootstrap import bootstrap

bootstrap()

from src.config.settings import get_settings
from src.llm.schemas import export_json_schemas


def main() -> None:
    settings = get_settings()
    export_json_schemas(settings.schemas_dir)
    print(f"Schemas exported to {settings.schemas_dir}")


if __name__ == "__main__":
    main()
