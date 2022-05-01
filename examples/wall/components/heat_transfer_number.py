# Calculate heat transfer number and the energy class

from typing import Dict

from hubit.utils import ReadOnlyDict


energy_classes = {
    "A": (0, 0.5),
    "B": (0.5, 0.75),
    "C": (0.75, 1.0),
    "D": (1.0, 100000.0),
}


def heat_transfer_number(_input: ReadOnlyDict, results: Dict):
    areas = [
        width * height for width, height in zip(_input["widths"], _input["heights"])
    ]
    total_area = sum(areas)

    # Mean heat transfer number
    htn = sum(
        [
            htn * area / total_area
            for htn, area in zip(_input["heat_transfer_numbers"], areas)
        ]
    )
    results["heat_transfer_number"] = htn
    results["energy_class"] = [
        ecls
        for ecls, limits in energy_classes.items()
        if htn >= limits[0] and htn < limits[1]
    ][0]
