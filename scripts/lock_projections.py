#!/usr/bin/env python3
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from record_tracker import atomic_json,canonical_digest
ap=argparse.ArgumentParser();ap.add_argument("path");args=ap.parse_args();p=Path(args.path)
d=json.loads(p.read_text());d["locked"]=True;d["lockedAt"]=d.get("lockedAt") or datetime.now(timezone.utc).isoformat().replace('+00:00','Z');d["lockDigest"]=canonical_digest(d);atomic_json(p,d);print(d["lockDigest"])
