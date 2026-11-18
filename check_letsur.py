#!/usr/bin/env python3
"""Letsur 연결 확인.
  python check_letsur.py              → 쓸 수 있는 GPT·Gemini·Claude 등 텍스트 모델 코드와 단가 출력
  python check_letsur.py <모델코드>   → 그 모델로 짧은 테스트 호출 1번 (비용과 응답 확인)
"""
import json, os, sys
import httpx
from kcaudit.common import load_env
load_env()
key = os.environ.get("LETSUR_API_KEY"); base = os.environ.get("LETSUR_BASE_URL", "https://gw.letsur.ai/v1").rstrip("/")
if not key:
    sys.exit(".env에 LETSUR_API_KEY가 없습니다. .env.example을 .env로 복사하고 키를 넣으세요.")
H = {"Authorization": f"Bearer {key}"}
if len(sys.argv) == 1:
    r = httpx.get(f"{base}/models", headers=H, timeout=60)
    if r.status_code >= 400:
        sys.exit(f"HTTP {r.status_code}: {r.text[:300]}")
    rows = r.json().get("data", [])
    pick = [m for m in rows if any(k in m.get("id", "").lower() for k in ("gpt", "gemini", "claude", "o3", "o4", "llama", "qwen", "deepseek", "mistral"))]
    print(f"전체 {len(rows)}개 중 텍스트 모델 후보 {len(pick)}개\n")
    for m in sorted(pick, key=lambda m: m["id"]):
        print(f"{m['id']:45s} {json.dumps(m.get('pricing', ''), ensure_ascii=False)[:120]}")
    print("\n고른 코드를 config.yaml의 judge_a(GPT), judge_b(Gemini) model: 칸에 넣으세요.")
else:
    model = sys.argv[1]
    for param in ("max_completion_tokens", "max_tokens"):
        body = {"model": model, param: 2000, "messages": [{"role": "user", "content": 'Reply with exactly this JSON: {"ok": true}'}]}
        r = httpx.post(f"{base}/chat/completions", headers=H, json=body, timeout=300)
        if r.status_code < 400:
            b = r.json()
            print("응답:", b["choices"][0]["message"].get("content"))
            print("usage:", json.dumps(b.get("usage"), ensure_ascii=False))
            print("estimated_cost:", json.dumps(b.get("estimated_cost"), ensure_ascii=False))
            print(f"\n이 모델은 token_param: {param} 로 설정하세요.")
            break
        print(f"{param}: HTTP {r.status_code} {r.text[:300]}")
