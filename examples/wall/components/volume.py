def volume(_input_consumed, results_provided):
    """Calculate volume"""
    results_provided["volume"] = (
        _input_consumed["thickness"]
        * _input_consumed["width"]
        * _input_consumed["height"]
    )
