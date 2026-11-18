"""적재소. 원칙: 원본 스냅샷은 불변, 판정·수정 기록은 추가만, 승인본은 언제든 다시 만들 수 있는 파생물."""
import json, shutil
from pathlib import Path
from .common import ROOT, now, fhash, read_jsonl, append_jsonl


class Store:
    def __init__(self, root):
        self.root = (ROOT / root) if not Path(root).is_absolute() else Path(root)
        for d in ("snapshots", "ledger", "runs", "releases", "human", "derived"):
            (self.root / d).mkdir(parents=True, exist_ok=True)
        self.verdicts = self.root / "ledger" / "verdicts.jsonl"
        self.revisions = self.root / "ledger" / "revisions.jsonl"
        self.active_file = self.root / "ACTIVE.json"

    # ---- 스냅샷 (불변) ----
    def ingest(self, kind, paths, label=""):
        rows, sources = [], []
        for p in sorted(map(Path, paths)):
            rows += read_jsonl(p); sources.append({"file": p.name, "sha256": fhash(p)})
        key = {"cards": "card_id", "items": "item_id"}.get(kind)
        if key:
            ids = [r[key] for r in rows]
            dup = {i for i in ids if ids.count(i) > 1}
            if dup:
                raise SystemExit(f"{kind}: 중복 id {sorted(dup)[:5]} … 합치기 전에 확인하세요.")
        tmp = self.root / "snapshots" / f".tmp_{kind}.jsonl"
        tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        sha = fhash(tmp)[:12]
        d = self.root / "snapshots" / kind / sha
        if d.exists():
            tmp.unlink()
        else:
            d.mkdir(parents=True); shutil.move(str(tmp), d / f"{kind}.jsonl")
            (d / "manifest.json").write_text(json.dumps(
                {"kind": kind, "sha": sha, "rows": len(rows), "sources": sources, "label": label, "ingested_at": now()},
                ensure_ascii=False, indent=1), encoding="utf-8")
        active = self.active(); active[kind] = sha
        self.active_file.write_text(json.dumps(active, indent=1), encoding="utf-8")
        append_jsonl(self.root / "snapshots" / "history.jsonl", [{"ts": now(), "kind": kind, "sha": sha, "label": label, "rows": len(rows)}])
        return sha, len(rows)

    def active(self):
        return json.loads(self.active_file.read_text()) if self.active_file.exists() else {}

    def snapshot(self, kind, sha=None):
        sha = self.active().get(kind) if sha is None else sha       # sha=""는 "그 시점에는 없었음"
        return read_jsonl(self.root / "snapshots" / kind / sha / f"{kind}.jsonl") if sha else []

    # ---- 판정 원장 (추가만) ----
    def add_verdicts(self, rows):
        append_jsonl(self.verdicts, rows)

    def all_verdicts(self, as_of=None):
        return read_jsonl(self.verdicts, limit=as_of)

    def all_revisions(self, as_of=None):
        return read_jsonl(self.revisions, limit=as_of)

    def offsets(self):
        n = lambda p: sum(1 for _ in p.open(encoding="utf-8")) if p.exists() else 0
        return {"verdicts": n(self.verdicts), "revisions": n(self.revisions)}

    # ---- 실행 기록 ----
    def new_run(self, stage, meta):
        run_id = f"{now().replace(':', '').replace('+0000', 'Z')[:17]}_{stage}"
        d = self.root / "runs" / run_id; n = 1
        while d.exists():
            n += 1; d = self.root / "runs" / f"{run_id}_{n}"
        (d / "raw").mkdir(parents=True)
        (d / "run.json").write_text(json.dumps({**meta, "run_id": d.name, "stage": stage, "started_at": now(),
                                                "active": self.active(), "offsets_at_start": self.offsets()},
                                               ensure_ascii=False, indent=1), encoding="utf-8")
        return d.name, d

    # ---- 릴리스 포인터 ----
    def current_release(self):
        p = self.root / "releases" / "CURRENT"
        return p.read_text().strip() if p.exists() else None

    def set_current(self, tag, why):
        if not (self.root / "releases" / tag).exists():
            raise SystemExit(f"릴리스 {tag} 없음")
        prev = self.current_release()
        (self.root / "releases" / "CURRENT").write_text(tag)
        append_jsonl(self.root / "releases" / "history.jsonl", [{"ts": now(), "from": prev, "to": tag, "why": why}])
