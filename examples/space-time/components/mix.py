from typing import Dict
from hubit.utils import ReadOnlyDict


def main(_input: ReadOnlyDict, results: Dict):
    feed_concs = _input["feed_concs"]
    V_feed = _input["V_feed"]
    results["mole_numbers"] = [conc * V_feed for conc in feed_concs]
    results["V_liq"] = V_feed
