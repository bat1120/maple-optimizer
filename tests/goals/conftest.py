"""판정 테스트가 tests/helpers.py를 import할 수 있게 한다."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
