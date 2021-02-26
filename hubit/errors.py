class HubitError(Exception):
    pass


class HubitIndexError(HubitError):
    pass


class HubitModelNoInputError(HubitError):
    def __init__(self):
        self.message = (
            "No input set on the model instance. Set input using the set_input() method"
        )

    def __str__(self):
        return self.message


class HubitModelNoResultsError(HubitError):
    def __init__(self):
        self.message = "No results found on the model instance so cannot reuse results"

    def __str__(self):
        return self.message


class HubitModelComponentError(HubitError):
    pass


class HubitModelValidationError(HubitError):
    def __init__(self, path, fname, fname_for_path):
        fstr = '"{}" on component "{}" also provided by component "{}"'
        self.message = fstr.format(path, fname, fname_for_path[path])

    def __str__(self):
        return self.message


class HubitModelQueryError(HubitError):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class HubitWorkerError(HubitError):
    pass
