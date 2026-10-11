"""Simulates the next day (with an extra ad placement) to test trends, discovery and the monthly view."""
import datetime as dt, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "radar"))
import util
real = util.now
util.now = lambda: real() + dt.timedelta(days=1)
fx = ROOT / "tests" / "fixtures" / "varzesh3.com" / "index.html"
orig = fx.read_text(encoding="utf-8")
fx.write_text(orig.replace("<header", '<div style="position:fixed;bottom:0;left:0;right:0"><a rel="sponsored" href="https://technolife.com/product/list/iphone?utm_campaign=v3-sticky"><img src="https://cdn.ads-static.ir/tl.png"></a></div><header'), encoding="utf-8")
try:
    exec(open(ROOT / "tests" / "run_offline.py").read())
finally:
    fx.write_text(orig, encoding="utf-8")
