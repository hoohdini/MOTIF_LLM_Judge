"""공통 유틸: 해시, jsonl, 설정, 프롬프트, JSON 파싱."""
import hashlib, json, os, re
from datetime import datetime, timezone
from pathlib import Path
import yaml
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def h(obj):
    """내용 해시. 단위 내용이 바뀌면 이전 판정이 자동으로 무효가 되는 기준."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def fhash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path, limit=None):
    path = Path(path)
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                break
            if line.strip():
                out.append(json.loads(line))
    return out


def append_jsonl(path, rows):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_yaml(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def load_env(path=ROOT / ".env"):
    if Path(path).exists():
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def load_prompt(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    parts = re.split(r"^## (\w+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


_BAD_ESCAPE = re.compile(r'\\(?!["\\/bfnrtu])')   # LaTeX 백슬래시가 JSON을 깨는 경우 복구 (윤상 코드와 같은 방식)


def parse_json(text, key):
    """응답에서 `key`를 가진 첫 JSON 객체를 꺼낸다. 앞뒤에 다른 텍스트가 붙어도 된다."""
    for t in (text or "", _BAD_ESCAPE.sub(r"\\\\", text or "")):
        dec, pos = json.JSONDecoder(), 0
        while (i := t.find("{", pos)) >= 0:
            try:
                obj, _ = dec.raw_decode(t, i)
            except json.JSONDecodeError:
                pos = i + 1; continue
            if isinstance(obj, dict) and key in obj:
                return obj
            pos = i + 1
    return None


def book_of(unit_id):
    """책 코드. 'CART-C01-S1-01' → 'CART', 'CS-COMP-C01-S1-01-M1-OPEN' → 'CS-COMP' (책 코드에 '-'가 들어가도 된다)."""
    u = unit_id.replace("CANARY::", "")
    m = re.match(r"(.+?)-C\d+(?:-|$)", u)
    return m.group(1) if m else u.split("-")[0]
