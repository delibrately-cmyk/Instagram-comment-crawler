from pathlib import Path
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ig_crawler import IGCrawler


@pytest.fixture
def crawler(tmp_path):
    config_path = Path(__file__).resolve().parents[1] / "config.example.json"
    data_dir = tmp_path / "crawler_data"
    return IGCrawler(data_dir=str(data_dir), config_file=str(config_path))
