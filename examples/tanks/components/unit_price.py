from __future__ import annotations
from signal import raise_signal
from typing import TYPE_CHECKING, Dict
import json
import urllib3

from hubit.errors import HubitError


if TYPE_CHECKING:
    from hubit.utils import ReadOnlyDict


def main(_input_consumed: ReadOnlyDict, results_provided: Dict):
    """
    Contact service at the 'url' and get today's unit price for the product
    """
    timeout = urllib3.Timeout(connect=1.0, read=5.0)
    url = _input_consumed["url"]
    headers = {
        "cache-control": "no-cache",
        "pragma": "no-cache",
    }
    http = urllib3.PoolManager(timeout=timeout, headers=headers)
    print(f"Looking up price at '{url}'")
    response = http.request("GET", url)
    if not (response.status == 200):
        raise HubitError(f"Could not connect to '{url}'")
    payload = json.loads(response.data.decode("utf-8"))
    print(f"Received price '{payload['unit_price']}'")
    results_provided["unit_price"] = payload["unit_price"]


def version() -> str:
    return "2.0.0"
