import re
import copy
import itertools
import collections
from functools import reduce
from operator import getitem

class Container(object):

    def __init__(self, val):
        self.val = val


    def __str__(self):
        return str(self.val)


def reshape(pstrs, valmap):
    """
    pstrs contains path strings in the correct shape i.e. a nested list. 
    Even a simple number is a list of one element due to the expansion. 
    If only one element return that element i.e. the value. Else collect the 
    values from the value map an store them in a nested list structure like
    pstrs.
    """
    if len(pstrs) > 1:
        return [valmap[pstr] if isinstance(pstr, basestring) else reshape(pstr, valmap) for pstr in pstrs]
    else:
        return valmap[pstrs[0]]
        

def traverse(items):
    """
    Iterate nested list. Stop iteration if string elements are encountered 
    """
    try:
        for i in iter(items):
            if not isinstance(i, basestring):
                for j in traverse(i):
                    yield j
            else:
                yield i
    except TypeError:
        yield items


def set_element(data, value, indices):
    """
    Set the "value" on the "data" at the "indices"
    """
    _data = data
    for idx in indices[:-1]:
        _data = _data[idx]
    _data[indices[-1]] = value
    return _data


def get_nested_list(maxilocs):
    """
    Create nested list with all values set to None.
    Dimensions given in "maxilocs" which are the max element number ie zero-based
    """
    empty_list = None
    for n in maxilocs[::-1]:
        empty_list = [copy.deepcopy(empty_list) for _ in range(n + 1)]
    return empty_list


def list_from_shape(shape):
    """
    Create nested list with all values set to None.
    Dimensions given in "shape". shape = 1 results in a number 
    """
    empty_list = None
    for n in shape[::-1]:
        if n > 1:
            empty_list = [copy.deepcopy(empty_list) for _ in range(n)]
        else:
            empty_list = copy.deepcopy(empty_list)
    return empty_list


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
    # TODO: also replace ":"... maybe loop over all possible 
    # TODO iloc wildcard
    clean_regexps = [string.replace(":", r"(\d+)") + '$' for string in clean_regexps]
    # print "clean_regexps", clean_regexps, clean_query
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
    # print 'querycmps', querycmps
    # At which indices are the wildcard encountered
    wcidxs = [idx for idx, qcmp in enumerate(querycmps) if qcmp == wcstr]
    # print 'wcidxs', wcidxs
    # Find maximal iloc for the indices with wildcards
    maxilocs = []
    for icount, cmpidx in enumerate(wcidxs):
        for pathstr in flat_input.keys():
            pathcmps = pathstr.split(sepstr)
            # print 'pathcmps', pathcmps
            try:
                pathcmp = int(pathcmps[cmpidx])
            except IndexError: # too few components in path
                continue
            except ValueError: # cannot cast component to int
                continue
                
            try:
                maxilocs[icount] = max(pathcmp, maxilocs[icount])
            except IndexError:
                maxilocs.append(pathcmp)

    # Make all query combinations
    queries = []
    for ilocs in itertools.product(*[range(maxval + 1) for maxval in maxilocs]):
        queries.append(set_ilocs(querystr, [str(iloc) for iloc in ilocs], wcstr))

    return queries, maxilocs


def query_all(providerstrings, flat_input, ilocstr):
    """
    Assumes complete input
    """
    return [qry for pstr in providerstrings for qry in expand_query(pstr.replace(ilocstr, ":"), flat_input)]
    

def get_from_datadict(datadict, keys):
    """
    Extract from nested dictionary using list of keys.
    datadict is a dict. keys is a list of keys.
    """
    return reduce(getitem, keys, datadict)



def pstr_shape(pstr, inputdata, sepstr, ilocwcchar):
    """
    From the input data infer the shape corresponding to the iloc 
    wildcard character (ilocwcchar) in the pstr.
    Rectagular data assumed.
    """
    nwc = pstr.count(ilocwcchar)
    shape = []
    pcmps = pstr.split(sepstr)
    cidx = 0
    for _ in range(nwc):
        idx = pcmps[cidx:].index(ilocwcchar) 
        cidx += idx
        shape.append(len(get_from_datadict(inputdata, pcmps[:cidx])))
        pcmps[cidx] = 0

    return shape


def pstr_expand(pstr, shape, ilocwcchar):
    """
    Expand a path string according to the shape. 
    The result is a nested list of path strings
    """
    # pstrs = []
    pstrs = get_nested_list([s-1 for s in shape])
    for ilocs in itertools.product(*[range(nitm) for nitm in shape]):
        #pstrs.append(set_ilocs(pstr, [str(iloc) for iloc in ilocs], ilocwcchar))
        set_element(pstrs, set_ilocs(pstr, [str(iloc) for iloc in ilocs], ilocwcchar), ilocs)
    return pstrs
