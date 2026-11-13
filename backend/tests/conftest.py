import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("POKERMIND_DB", os.path.join(os.path.dirname(__file__), "_test.db"))
