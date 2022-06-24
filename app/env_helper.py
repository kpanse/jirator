from os import path
import os
import shutil
import tempfile
from pathlib import Path
from python_json_config import ConfigBuilder


def get_appdata():
    builder = ConfigBuilder()
    config = builder.parse_config("jirator.json")

    app_data_name = config.app_name
    app_data_dir = Path(path.expandvars(r"%APPDATA%")) / app_data_name

    if Path(app_data_dir).exists():
        return app_data_dir
    else:
        Path(app_data_dir).mkdir(parents=True, exist_ok=True)
        return app_data_dir


def get_temp():
    builder = ConfigBuilder()
    config = builder.parse_config("jirator.json")

    app_data_name = config.app_name
    tmp_data_dir = Path(tempfile.gettempdir()) / app_data_name

    Path(tmp_data_dir).mkdir(parents=True, exist_ok=True)

    return tmp_data_dir
