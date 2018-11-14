import re
import copy
import itertools
import collections

def inflate(d, sep="."):
    """
    https://gist.github.com/fmder/494aaa2dd6f8c428cede
    """
    items = dict()
    for k, v in d.items():
        keys = k.split(sep)
        sub_items = items
        for ki in keys[:-1]:
            try:
                sub_items = sub_items[ki]
            except KeyError:
                sub_items[ki] = dict()
                sub_items = sub_items[ki]
            
        sub_items[keys[-1]] = v

    return items


def flatten(d, parent_key='', sep='.'):
    """
    Flattens dict and concatenates keys 
    Modified from: https://stackoverflow.com/questions/6027558/flatten-nested-python-dictionaries-compressing-keys
    """
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(flatten(v, new_key, sep=sep).items())
        elif isinstance(v, collections.Iterable) and not isinstance(v, basestring):
            try:
                # Elements are dicts
                for idx, item in enumerate(v):
                    _new_key = new_key + '.' + str(idx)
                    items.extend(flatten(item, _new_key, sep=sep).items())
            except AttributeError:
                # Elements are not dicts
                items.append((new_key, v))
        else:
            items.append((new_key, v))
    return dict(items)


def set_ilocs(string, ilocs, ilocstr):
    """
    Replace the ILOCSTR on the path string with location indices 
    in ilocs
    """
    _string = copy.copy(string)
    for iloc in ilocs:
        _string = _string.replace(ilocstr, iloc, 1)
    return _string


def regex_preprocess(querystring, providerstrings, ilocstr):
    """
    """
    # get rid of . before doing regex stuff
    clean_query = querystring.replace(".", "->")
    clean_providerstr = [pstring.replace(".", "->") for pstring in providerstrings]

    # Look for digits whenever ilocstr is encountered
    clean_regexps = [string.replace(ilocstr, r"(\d+)") + '$' for string in clean_providerstr]
    compiled_regexps = [re.compile(string) for string in clean_regexps]
    # print clean_regexps
    return clean_query, compiled_regexps


def get_matches(querystring, providerstrings, ilocstr):
    """
    Returns indices of provider strings that match the query string
    """
    clean_query, compiled_regexps = regex_preprocess(querystring, providerstrings, ilocstr)
    # print 'clean_query', clean_query
    # print compiled_regexps
    return [idx for idx, cex in enumerate(compiled_regexps) if re.match(cex, clean_query)]


def get_indices(querystring, providerstring, ilocstr):
    """
    Array indices extracted from query
    """
    _q, _lc = regex_preprocess(querystring, [providerstring], ilocstr)
    compiledstring = _lc[0]
    match = re.search(compiledstring, _q)
    return match.groups()


def expand_query(querystr, flat_input):
    """
    querystr = "segs.:.walls.temps"
    all_input = {"segs.0.walls.temps" : 1, "segs.1.walls.temps" : 2, "segs.2.walls.temps" : None}
    result = "segs.0.walls.temps", "segs.1.walls.temps", "segs.2.walls.temps"
    """
    sepstr = "."
    wcstr = ":"
    querycmps = querystr.split(sepstr)

    # At which indices are the wildcard encountered
    wcidxs = [idx for idx, qcmp in enumerate(querycmps) if qcmp == wcstr]

    # Find maximal iloc for the indices with wildcards
    maxilocs = []
    for icount, cmpidx in enumerate(wcidxs):
        for pathstr in flat_input.keys():
            pathcmps = pathstr.split(sepstr)
            try:
                pathcmp = int(pathcmps[cmpidx])
            except IndexError:
                continue
                
            try:
                maxilocs[icount] = max(pathcmp, maxilocs[icount])
            except IndexError:
                maxilocs.append(pathcmp)

    # Make all query combinations
    queries = []
    for ilocs in itertools.product(*[range(maxval + 1) for maxval in maxilocs]):
        queries.append(set_ilocs(querystr, [str(iloc) for iloc in ilocs], wcstr))

    return queries

def query_all(providerstrings, flat_input, ilocstr):
    """
    Assumes complete input
    """
    return [qry for pstr in providerstrings for qry in expand_query(pstr.replace(ilocstr, ":"), flat_input)]
    