RARE_BOOST = 1.6
COMMON_BOOST = 1.0


def rarity_boost(paper: dict) -> float:
    return RARE_BOOST if paper.get("rarity") == "rare" else COMMON_BOOST
