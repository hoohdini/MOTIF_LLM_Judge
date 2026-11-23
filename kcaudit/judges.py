"""저지 호출. provider만 다르고 입출력은 같다: (system, user) → 텍스트.
자동 재시도는 하지 않는다 (응답 유실 뒤 재호출하면 중복 과금될 수 있음. 실패는 기록하고 다음 실행에서 이어간다)."""
import json, os, random


def call(jid, jcfg, system, user, mock_spec=None):
    p = jcfg["provider"]
    if p == "mock":
        return json.dumps(_mock(jid, mock_spec), ensure_ascii=False), {"mock": True}
    import httpx
    key = os.environ.get(jcfg.get("key_env", ""), "")
    if jcfg["model"] == "SET_ME":
        raise RuntimeError(f"config.yaml의 {jid}.model을 설정하세요.")
    if p == "openai_compat":
        base = os.environ.get(jcfg.get("base_url_env", ""), "").rstrip("/")
        if not base:
            raise RuntimeError(f"{jcfg.get('base_url_env')} 환경변수가 없습니다.")
        body = {"model": jcfg["model"], jcfg.get("token_param", "max_tokens"): jcfg.get("max_tokens", 8000),
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if jcfg.get("reasoning_effort"):
            body["reasoning_effort"] = jcfg["reasoning_effort"]
        if jcfg.get("temperature") is not None:
            body["temperature"] = jcfg["temperature"]
        r = httpx.post(f"{base}/chat/completions", headers={"Authorization": f"Bearer {key}"}, json=body, timeout=600)
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")
        r.raise_for_status(); b = r.json(); ch = b["choices"][0]
        usage = {**(b.get("usage") or {}), "finish_reason": ch.get("finish_reason"), "estimated_cost": b.get("estimated_cost"),
                 "response_model": b.get("model"), "request": {k: v for k, v in body.items() if k != "messages"}}
        if ch.get("finish_reason") == "length":
            raise RuntimeError("출력이 max_tokens에서 잘렸습니다.")
        return ch["message"].get("content") or "", usage
    if p == "anthropic":
        body = {"model": jcfg["model"], "max_tokens": jcfg.get("max_tokens", 8000), "system": system,
                "messages": [{"role": "user", "content": user}]}
        r = httpx.post("https://api.anthropic.com/v1/messages", json=body, timeout=600,
                       headers={"x-api-key": key, "anthropic-version": "2023-06-01"})
        r.raise_for_status(); b = r.json()
        if b.get("stop_reason") != "end_turn":
            raise RuntimeError(f"stop_reason={b.get('stop_reason')}")
        return "".join(x.get("text", "") for x in b["content"] if x["type"] == "text"), {**b.get("usage", {}), "stop_reason": b["stop_reason"]}
    raise ValueError(f"지원하지 않는 provider: {p}")


def _mock(jid, spec):
    """API 없이 흐름을 검증하기 위한 가짜 저지. 두 mock 저지는 같은 '참값'에 각자 잡음을 더해 서로 상관된 판정을 낸다."""
    def vote(uid, check, values, canary=False):
        base = random.Random(f"{uid}:{check}"); noise = random.Random(f"{jid}:{uid}:{check}")
        v = values[0] if base.random() < 0.9 else base.choice(values[1:] or values)
        if canary:
            v = values[-1] if noise.random() < 0.85 else values[0]
        elif noise.random() < 0.05:
            v = noise.choice(values)
        return v
    if spec["kind"] == "audit":
        out = {"units": {}, "batch": {}}
        ids = list(spec["units"])
        for uid, checks in spec["units"].items():
            out["units"][uid] = {}
            for c, d in checks.items():
                v = vote(spec.get("alias", {}).get(uid, uid), c, d["values"], canary=c in spec.get("canary", {}).get(uid, []))
                e = {"v": v}
                if v != d["values"][0]:
                    e["why"] = "(mock) reason"
                if d.get("cite") == "evidence_id" and v != "fail":
                    e["cite"] = spec["cite_pool"][uid][:1]
                if d.get("cite") == "unit_id" and v == "fail":
                    e["cite"] = [x for x in ids if x != uid][:1]
                out["units"][uid][c] = e
        for c, d in spec.get("batch", {}).items():
            out["batch"][c] = {"v": vote(spec["batch_id"], c, d["values"])}
        return out
    if spec["kind"] == "answer":
        words = spec["response"].split()
        pts = []
        for k in range(1, spec["n_kp"] + 1):
            s = vote(spec["unit_id"], f"kp{k}", ["present", "absent", "contradicted"])
            pts.append({"kp": k, "s": s, "quote": " ".join(words[:5]) if s != "absent" else ""})
        return {"units": {spec["unit_id"]: {"KEYPOINTS": {"points": pts}, "ADDITIONAL_CONTENT": {"present": False, "quotes": []}}}}
    if spec["kind"] == "revise":
        parts = [p.strip() for p in spec["statement"].split(", and ") if p.strip()][:3]
        return {"atoms": [{"statement": (p if p.endswith(".") else p + ".") + " (mock revised)", "scope": spec["scope"],
                           "evidence_ids": spec["evidence_ids"][:1]} for p in parts], "note": ""}
