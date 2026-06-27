"""
scoring.py - shared suburb scorer. Mirrors the production model/scoring.py, but
the dimension weights now come from the user's PROFILE (config), not a hardcoded
constant. Computes the balanced (prior=50) 0-100 Buyer-Fit score per suburb.
Stdlib only.
"""

DIMS = ["growth", "family", "land", "kdr", "prox", "post"]


def score_suburb(s, weights, prior=50):
    swing = 0.20
    t = (prior - 50) / 50.0
    w = dict(weights)
    w["prox"] = max(0.0, weights.get("prox", 0) - swing * t * 0.5)
    w["post"] = max(0.0, weights.get("post", 0) + swing * t * 0.5)
    sc = s["scores"]
    composite = (sc["growth"] * w.get("growth", 0) + sc["family"] * w.get("family", 0)
                 + sc["land"] * w.get("land", 0) + sc["kdr"] * w.get("kdr", 0)
                 + sc["prox"] * w["prox"])
    post_blend = sc["post"] * (1 - (prior / 100) * 0.5) + s["school"] * ((prior / 100) * 0.5)
    composite += post_blend * w["post"]
    score = composite * 10
    over = False
    if not s["band"]:
        mid = (s["mlo"] + s["mhi"]) / 2
        if mid > 1100:
            score *= 0.55
            over = True
        else:
            score *= 0.85
    return round(score * 10) / 10, over


def rank(suburbs, weights, prior=50):
    out = []
    for s in suburbs:
        score, over = score_suburb(s, weights, prior)
        out.append({"name": s["name"], "pc": s["pc"], "reg": s["reg"], "km": s["km"],
                    "mlo": s["mlo"], "mhi": s["mhi"], "band": s["band"], "score": score,
                    "over": over, "why": s.get("why", "")})
    out.sort(key=lambda r: -r["score"])
    return out
