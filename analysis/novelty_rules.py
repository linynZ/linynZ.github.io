# -*- coding: utf-8 -*-
"""新元素（障碍/机制）引入点的判定规则。独立成文件便于审核与单测。

规则：备注按分号/句号/驼峰粘连处切成分句；含 former/formerly/unofficial/used to 的分句不算（历史引入）；
排除"难度"类 first；其余分句命中引入词即算一次引入。
"""
import re

_SPLIT = re.compile(r"[;.]|(?<=[a-z\)])(?=[A-Z])")
_EXCLUDE = re.compile(r"former|formerly|unofficial|used to be|extremely hard difficulty|to be rated|hardest level|milestone|received|spawning blockers")
_HIT = re.compile(r"\b(is|are|was|were) (first |officially )?introduced|\bintroduction (of|to)\b|\bintroduced here\b|"
                  r"first level (with|to|where|that)|currently (the )?first level|first (mixed|ingredient|jelly|order|moves) (level|mode)|"
                  r"\bdebut\b")


def is_intro(remark: str) -> bool:
    for clause in _SPLIT.split(remark or ""):
        c = clause.lower().strip()
        if not c or _EXCLUDE.search(c):
            continue
        if _HIT.search(c):
            return True
    return False


if __name__ == "__main__":
    tests = {
        "is introduced": True,
        "Former introduction of candy cannons": False,
        "is introduced;Former introduction of": True,
        "was introduced": True,
        "Jelly fish booster unlocked Double jelly is first introduced": True,
        "First level with an extremely hard difficulty": False,
        "used to be introduced here": False,
        "First level to require the orders for candy colours that do not spawn on the board": True,
        "is unofficially introduced": False,
        "Was one of the hardest levels in the game before being nerfed.": False,
    }
    for t, exp in tests.items():
        assert is_intro(t) == exp, (t, is_intro(t))
    print("novelty_rules self-test ok")
