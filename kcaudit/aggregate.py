"""판정 합산. 원장(ledger)의 개별 판정 → 체크별 판정 → 단위 판정.
규칙: 사람 판정이 있으면 그것이 우선. 없으면 필수 저지가 전원 같은 값일 때만 그 값, 엇갈리면 hold.
단위 판정 우선순위: fail > pending > hold > revise > pass (blocker 체크만 반영)."""
from collections import Counter, defaultdict
from .common import h, load_yaml, ROOT
from .prechecks import CODE_CHECKS, CODE_VERSION
from .units import load_cards, load_items, load_answers


class Registry:
    def __init__(self, path="checks.yaml", base=ROOT):
        self.base = base
        self.groups = load_yaml(base / path)["groups"]

    def group(self, stage):
        return next((n, g) for n, g in self.groups.items() if g["stage"] == stage)

    def prompt_hash(self, gname):
        g = self.groups[gname]
        return h([(self.base / g["prompt"]).read_text(encoding="utf-8"), g["checks"], g.get("batch_checks")])

    @staticmethod
    def applicable(gdef, item=None):
        out = {}
        for name, d in gdef["checks"].items():
            ap = d.get("applies")
            if item is not None and ap and not (item["format"] in ap or f"{item['format']}:{item['answer']}" in ap):
                continue
            out[name] = d
        return out


class Ctx:
    """한 시점의 데이터와 원장을 묶어 둔 것. as_of/snaps/prompt_hashes를 주면 과거 릴리스를 그대로 재현한다."""
    def __init__(self, store, cfg, reg, as_of=None, snaps=None, prompt_hashes=None):
        self.store, self.cfg, self.reg = store, cfg, reg
        as_of = as_of or {}
        snaps = {k: snaps.get(k, "") for k in ("cards", "items", "answers")} if snaps is not None else {}
        self.rows = store.all_verdicts(as_of.get("verdicts"))
        self.cards = load_cards(store, as_of.get("revisions"), snaps.get("cards"))
        self.items = load_items(store, snaps.get("items"))
        self.items_by_id = {i["item_id"]: i for i in self.items}
        self.answers = load_answers(store, self.items_by_id, snaps.get("answers"))
        self.phash = prompt_hashes or {n: reg.prompt_hash(n) for n in reg.groups}
        self.by_unit = defaultdict(list)
        for r in self.rows:
            self.by_unit[(r["unit_id"], r["unit_hash"])].append(r)
        self._memo = {}

    def stage_judges(self, stage):
        return list(self.cfg["stages"][stage]["judges"])

    def answer_judges(self, model):
        fam = next((f for p, f in sorted(self.cfg.get("target_families", {}).items(), key=lambda x: -len(x[0]))
                    if model.lower().startswith(p)), None)
        st = self.cfg["stages"]["answer"]
        ok = [j for j in st["judges"] if self.cfg["judges"][j]["family"] != fam]
        return ok[: st.get("n_judges", 2)]


def _resolve(ctx, uid, uhash, defs, judges, phash, garbled, use_human):
    rows = ctx.by_unit.get((uid, uhash), [])
    res = {}
    for name, d in defs.items():
        rs = [r for r in rows if r["check"] == name]
        human = [r for r in rs if r["judge"].startswith("human:")]
        if use_human and human:
            res[name] = {"v": human[-1]["v"], "src": human[-1]["judge"], "by": {}, "why": {human[-1]["judge"]: human[-1].get("why", "")}}
            continue
        if d.get("code"):
            cr = [r for r in rs if r["judge"] == "code" and r.get("prompt_hash") == CODE_VERSION]
            res[name] = {"v": cr[-1]["v"] if cr else ("pass" if name == "REVISE_FAILED" else "pending"), "src": "code", "by": {},
                         "why": {"code": cr[-1].get("why", "")} if cr and cr[-1]["v"] != "pass" else {}}
            continue
        by, why = {}, {}
        for j in judges:
            reps = {}
            for r in rs:
                if r["judge"] == j and r.get("prompt_hash") == phash:
                    reps[r.get("rep", 0)] = r
            if not reps:
                by[j] = "pending"; continue
            cnt = Counter(r["v"] for r in reps.values()).most_common()
            by[j] = cnt[0][0] if len(cnt) == 1 or cnt[0][1] > cnt[1][1] else "hold"     # 반복 실행이 갈리면 보류
            w = [r.get("why") for r in reps.values() if r.get("why")]
            if w:
                why[j] = w[-1]
        vals = set(by.values())
        v = "pending" if "pending" in vals else (vals.pop() if len(vals) == 1 else "hold")
        src = "judges"
        if ctx.cfg["policy"].get("math_evidence") == "hold" and d.get("evidence_dependent") and garbled:
            v, src = "hold", "math_policy"
        res[name] = {"v": v, "src": src, "by": by, "why": why}
    return res


def _decision(res, defs, pass_values=("pass",)):
    vs = [res[n]["v"] for n, d in defs.items() if d["severity"] == "blocker"]
    for k in ("fail", "pending", "hold", "revise"):
        if k in vs:
            return k
    return "pass" if all(v in pass_values for v in vs) else "hold"


def _combine(ctx, res, defs, judges):
    """두 저지(이상)의 판정을 단위 판정으로 합친다. policy.combine으로 고른다.
    - "decision"(기본): 저지마다 자기 단위 판정을 낸 뒤, 통과/불통과가 같으면 확정한다.
      둘 다 통과면 pass, 둘 다 불통과면 fail(둘 다 fail일 때만) 아니면 revise(일단 고쳐서 다시 검수),
      한쪽만 통과면 hold(사람 검토). 어느 저지든 hold면 hold.
    - "check": 체크마다 저지 전원이 같아야 확정하고, 하나라도 갈리면 hold (더 엄격, 사람 검토가 많음).
    코드 검사, 사람이 체크 단위로 내린 판정, 수식 정책 hold는 두 방식 모두 그대로 적용된다."""
    if ctx.cfg.get("policy", {}).get("combine", "decision") == "check" or len(judges) < 2:
        return _decision(res, defs)
    blk = [n for n, d in defs.items() if d["severity"] == "blocker"]
    fixed = [res[n]["v"] for n in blk if res[n]["src"] != "judges"]
    if "fail" in fixed:
        return "fail"
    per_j = {}
    for j in judges:
        vs = [res[n]["by"].get(j, "pending") if res[n]["src"] == "judges" else res[n]["v"] for n in blk]
        per_j[j] = next((k for k in ("fail", "pending", "hold", "revise") if k in vs), "pass")
    ds = set(per_j.values())
    for k in ("pending", "hold"):
        if k in ds:
            return k
    if ds == {"pass"}:
        return "pass"
    if "pass" in ds:
        return "hold"
    return "fail" if ds == {"fail"} else "revise"


def _unit_override(ctx, uid, uhash, use_human):
    if not use_human:
        return None
    hs = [r for r in ctx.by_unit.get((uid, uhash), []) if r["check"] == "_UNIT" and r["judge"].startswith("human:")]
    return hs[-1] if hs else None


def _code_defs(stage):
    return {n: {"severity": s, "code": True} for n, s in CODE_CHECKS[stage].items()}


def decide_card(ctx, judges=None, use_human=True):
    key = ("card", tuple(judges or ()), use_human)
    if key in ctx._memo:
        return ctx._memo[key]
    gname, g = ctx.reg.group("card")
    judges = judges or ctx.stage_judges("card")
    defs = {**_code_defs("card"), **g["checks"]}
    out = {}
    for c in ctx.cards:
        for a in c["atoms"]:
            res = _resolve(ctx, a["atom_id"], a["_hash"], defs, judges, ctx.phash[gname], a["_garbled"], use_human)
            d = _combine(ctx, res, defs, judges)
            if d == "revise" and a.get("rev_round", 0) >= ctx.cfg["policy"].get("revise_max_rounds", 1):
                d = "hold"                                           # 자동 수정본이 또 걸리면 사람에게
            ov = _unit_override(ctx, a["atom_id"], a["_hash"], use_human)
            out[a["atom_id"]] = {"unit_id": a["atom_id"], "unit_hash": a["_hash"], "card_id": c["card_id"],
                                 "decision": ov["v"] if ov else d, "own": d, "checks": res, "human": bool(ov)}
    ctx._memo[key] = out
    return out


def decide_item(ctx, judges=None, use_human=True):
    key = ("item", tuple(judges or ()), use_human)
    if key in ctx._memo:
        return ctx._memo[key]
    gname, g = ctx.reg.group("item")
    judges = judges or ctx.stage_judges("item")
    atoms = {a["atom_id"]: a for c in ctx.cards for a in c["atoms"]}
    atom_dec = decide_card(ctx)
    out = {}
    for it in ctx.items:
        defs = {**_code_defs("item"), **ctx.reg.applicable(g, it)}
        res = _resolve(ctx, it["item_id"], it["_hash"], defs, judges, ctx.phash[gname], it["_garbled"], use_human)
        own = _combine(ctx, res, defs, judges)
        ov = _unit_override(ctx, it["item_id"], it["_hash"], use_human)
        a = atoms.get(it["atom_id"])
        if a is None or a["statement"] != it["atom_statement"]:
            dec, dep = "blocked", "atom_changed"                     # atom이 수정·분리·폐기됨 → 문항 재생성 필요
        elif atom_dec[it["atom_id"]]["decision"] != "pass":
            dec, dep = "blocked", f"atom_{atom_dec[it['atom_id']]['decision']}"
        else:
            dec, dep = (ov["v"] if ov else own), ""
        out[it["item_id"]] = {"unit_id": it["item_id"], "unit_hash": it["_hash"], "card_id": it["card_id"],
                              "decision": dec, "own": ov["v"] if ov else own, "blocked_by": dep, "checks": res, "human": bool(ov)}
    ctx._memo[key] = out
    return out


def decide_answer(ctx, use_human=True):
    gname, g = ctx.reg.group("answer")
    item_dec = decide_item(ctx)
    out = {}
    for a in ctx.answers:
        it = a["_item"]
        if it["format"] == "OPEN":
            defs = {"KEYPOINTS": g["checks"]["KEYPOINTS"]}
            res = _resolve(ctx, a["_id"], a["_hash"], defs, ctx.answer_judges(a["model"]), ctx.phash[gname], False, use_human)
            own = res["KEYPOINTS"]["v"]
        else:
            defs = {"ANSWER_LABEL": {"severity": "blocker", "code": True}}
            res = _resolve(ctx, a["_id"], a["_hash"], defs, [], None, False, use_human)
            own = res["ANSWER_LABEL"]["v"]
        dec = own if item_dec[it["item_id"]]["decision"] == "pass" else "excluded"   # 승인되지 않은 문항의 답변은 점수에서 제외
        out[a["_id"]] = {"unit_id": a["_id"], "unit_hash": a["_hash"], "item_id": it["item_id"], "model": a["model"],
                         "format": it["format"], "decision": dec, "own": own, "checks": res}
    return out


DECIDE = {"card": decide_card, "item": decide_item, "answer": decide_answer}
