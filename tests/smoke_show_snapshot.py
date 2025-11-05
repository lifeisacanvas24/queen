from queen.cli.show_snapshot import _latest_snapshot_path
from queen.helpers import io

p = _latest_snapshot_path()
df = io.read_any(p)
print("rows:", len(df))
print("cols:", df.columns)
