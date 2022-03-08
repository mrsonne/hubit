from __future__ import annotations
from typing import TYPE_CHECKING, Dict
import urllib.request
import json

if TYPE_CHECKING:
    from hubit.utils import ReadOnlyDict


def main(_input_consumed: ReadOnlyDict, results_provided: Dict):
    """
    Contact service at the 'url' and get today's unit price for the product
    """
    # url = _input_consumed["url"]
    # with urllib.request.urlopen(url) as response:
    #     response = json.loads(response.read())
    # results_provided["unit_price"] = response["unit_price"]
    results_provided["unit_price"] = 1.7


def version() -> str:
    return "2.0.0"
