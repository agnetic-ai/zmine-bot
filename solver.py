"""
ZMINE Dual-Engine SI Tasks Solver
- Level 1: Regex & Math Rule Engine (0 token, instantaneous)
- Level 2: OpenAI-compatible LLM Fallback (for complex reasoning, trivia, and text logic)
"""

import re
import httpx


def clean_num(s: str) -> float:
    return float(s.replace(",", "").replace(" ", "").replace("$", "").strip())


def solve_prompt_rule(p: str, options: list) -> int | None:
    p = p.replace("×", "x").replace("−", "-").replace("—", "-")

    # 1. Percentage: "What is X% of Y?"
    m = re.search(r"What is\s+([\d\.]+)%\s+of\s+([\d\.,]+)", p, re.I)
    if m:
        ans = (float(m.group(1)) / 100.0) * clean_num(m.group(2))
        for i, opt in enumerate(options):
            if abs(clean_num(opt) - ans) < 1e-4:
                return i

    # 2. Block production per day: "produces one block every X seconds. How many blocks is that per day?"
    m = re.search(r"produces one block every\s+([\d\.]+)\s+seconds.*?per day", p, re.I)
    if m:
        ans = 86400 / float(m.group(1))
        for i, opt in enumerate(options):
            if abs(clean_num(opt) - ans) < 1e-4:
                return i

    # 3. Epochs in hours: "Epochs last X minutes. How many epochs are there in Y hours?"
    m = re.search(r"Epochs last\s+([\d\.]+)\s+minutes.*?in\s+([\d\.]+)\s+hours", p, re.I)
    if m:
        ans = (float(m.group(2)) * 60) / float(m.group(1))
        for i, opt in enumerate(options):
            if abs(clean_num(opt) - ans) < 1e-4:
                return i

    # 4. Seconds in hours: "How many seconds are in X hours?"
    m = re.search(r"How many seconds are in\s+([\d\.]+)\s+hours", p, re.I)
    if m:
        ans = float(m.group(1)) * 3600
        for i, opt in enumerate(options):
            if abs(clean_num(opt) - ans) < 1e-4:
                return i

    # 5. Seconds in minutes: "How many seconds are in X minutes?"
    m = re.search(r"How many seconds are in\s+([\d\.]+)\s+minutes", p, re.I)
    if m:
        ans = float(m.group(1)) * 60
        for i, opt in enumerate(options):
            if abs(clean_num(opt) - ans) < 1e-4:
                return i

    # 6. Assistant claims arithmetic: "An assistant claims: A x B = C"
    m = re.search(
        r"An assistant claims:\s*([\d\.,]+)\s*([x\+\-\/])\s*([\d\.,]+)\s*=\s*([\d\.,]+)",
        p,
        re.I,
    )
    if m:
        a, op, b, c = clean_num(m.group(1)), m.group(2), clean_num(m.group(3)), clean_num(m.group(4))
        actual = (
            a * b
            if op == "x"
            else a + b
            if op == "+"
            else a - b
            if op == "-"
            else a / b
        )
        target = "Correct" if abs(actual - c) < 1e-4 else "Incorrect"
        if target in options:
            return options.index(target)

    # 7. Assistant claims ZEC = zatoshi: "An assistant claims: X ZEC = Y zatoshi"
    m = re.search(
        r"An assistant claims:\s*([\d\.,]+)\s*ZEC\s*=\s*([\d\.,]+)\s*zatoshi",
        p,
        re.I,
    )
    if m:
        actual_zat = clean_num(m.group(1)) * 100_000_000
        target = (
            "Correct"
            if abs(actual_zat - clean_num(m.group(2))) < 1e-4
            else "Incorrect"
        )
        if target in options:
            return options.index(target)

    # 8. ZEC to zatoshi conversion: "How many zatoshi are in X ZEC?"
    m = re.search(r"How many zatoshi are in\s+([\d\.]+)\s+ZEC", p, re.I)
    if m:
        ans = float(m.group(1)) * 100_000_000
        for i, opt in enumerate(options):
            if abs(clean_num(opt) - ans) < 1e-4:
                return i

    # 9. Halving: "A reward of X halves Y times. What is the final reward?"
    m = re.search(r"reward of\s+([\d\.,]+)\s+halves\s+(\d+)\s+times", p, re.I)
    if m:
        ans = clean_num(m.group(1)) / (2 ** int(m.group(2)))
        for i, opt in enumerate(options):
            if abs(clean_num(opt) - ans) < 1e-4:
                return i

    # 10. Simple arithmetic: "What is A x B?"
    m = re.search(r"What is\s+([\d\.,]+)\s*([x\+\-\/])\s*([\d\.,]+)", p, re.I)
    if m:
        a, op, b = clean_num(m.group(1)), m.group(2), clean_num(m.group(3))
        ans = (
            a * b
            if op == "x"
            else a + b
            if op == "+"
            else a - b
            if op == "-"
            else a / b
        )
        for i, opt in enumerate(options):
            if abs(clean_num(opt) - ans) < 1e-4:
                return i

    return None


def solve_with_ai(
    prompt: str,
    options: list,
    ai_url: str,
    ai_key: str,
    ai_model: str = "ag/gemini-3.8-flash-low",
) -> int:
    if not ai_url or not ai_key:
        return 0
    try:
        opts_str = "\n".join([f"{i}: {opt}" for i, opt in enumerate(options)])
        payload = {
            "model": ai_model,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert multiple-choice quiz solver. Respond with ONLY the single 0-based integer index of the correct option (e.g. 0, 1, 2, or 3).",
                },
                {
                    "role": "user",
                    "content": f"Question: {prompt}\n\nOptions:\n{opts_str}\n\nRespond with ONLY the integer index.",
                },
            ],
        }
        headers = {"Authorization": f"Bearer {ai_key}"}
        r = httpx.post(ai_url, json=payload, headers=headers, timeout=15.0)
        content = r.json()["choices"][0]["message"]["content"].strip()
        digits = re.findall(r"\d+", content)
        if digits:
            idx = int(digits[0])
            if 0 <= idx < len(options):
                return idx
    except Exception as e:
        print(f"    [AI Solver Error] {e}")
    return 0


def solve_task(
    prompt: str,
    options: list,
    ai_url: str = "",
    ai_key: str = "",
    ai_model: str = "ag/gemini-3.8-flash-low",
) -> tuple[int, str]:
    """
    Returns (answer_index, method_used)
    """
    rule_ans = solve_prompt_rule(prompt, options)
    if rule_ans is not None:
        return rule_ans, "rule"

    ai_ans = solve_with_ai(prompt, options, ai_url, ai_key, ai_model)
    return ai_ans, "ai"
