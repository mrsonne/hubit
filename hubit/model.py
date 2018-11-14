import imp
import os
import sys
import time
import copy
import traceback
import itertools
import subprocess
import yaml
from datetime import datetime
from threading import Thread, Event
from worker import Worker
from shared import get_matches, flatten
from multiprocessing import Pool, TimeoutError, cpu_count, active_children

POLLTIME = 0.1
THISPATH = os.path.dirname(os.path.abspath(__file__))

def cb(x):
    print 'WELCOME BACK! WELCOME BACK! WELCOME BACK! WELCOME BACK!'


def get_star(args):   
    """
    https://stackoverflow.com/questions/5442910/python-multiprocessing-pool-map-for-multiple-arguments
    Convert `f([1,2])` to `f(1,2)` call.
    """
    return get(*args)


def get(queryrunner, querystrings, all_input, dryrun=False):
    """
    all_input is a flat dictionary with path strings as keys
    """
    # Reset book keeping data
    queryrunner.workers = []
    queryrunner.workers_working = []
    queryrunner.workers_completed = []
    queryrunner.worker_for_id = {}
    queryrunner.observers_for_query = {}

    extracted_input = {}
    all_results = {}

    # Start thread that periodically checks whether we are finished or no   
    run_event = Event()
    run_event.set()
    watcher = Thread(target=queryrunner.watcher, args=(querystrings, all_results, run_event))
    watcher.start()

    tstart = time.time()

    # remeber to send SIGTERM for processes
    # https://stackoverflow.com/questions/11436502/closing-all-threads-with-a-keyboard-interrupt
    try:
        queryrunner.deploy(querystrings, extracted_input, all_results, all_input, dryrun=dryrun)
    except BaseException as err:
        traceback.print_exc()
        print(err)
        run_event.clear()

    watcher.join()

    response = {query:all_results[query] for query in querystrings}
    # print([(key, [obj.idstr() for obj in objs]) for key, objs in self.observers_for_query.items()])
    print('\n**SUMMARY**\n')
    print('Input extracted\n{}\n'.format(extracted_input))
    print('Results\n{}\n'.format(all_results))
    print('Response\n{}'.format(response))

    print('Response created in {} s'.format(time.time() - tstart))
    return response


class HubitModel(object):

    def __init__(self, cfg, name=None):

        self.ilocstr = "_IDX"
        self.module_for_clsname = {}
        self.cfg = cfg
        self.name = name


    @classmethod
    def from_file(cls, filepath, name):
        with open(filepath, "r") as stream:
            cfg = yaml.load(stream)

        path = os.path.split(filepath)[0]
        # path = os.path.abspath(os.path.join(THISPATH, path))
        for key, val in cfg.items():
            val["path"] = os.path.abspath(os.path.join(path, val["path"]))
            # print val["path"]

        return cls(cfg, name)
    

    def render(self, querystrings=None, all_input=None):
        """
        Renders model if querystrings and all_input are not provided.
        If querystrings and all_input are provided the query is rendered instead.
        """
        from graphviz import Digraph
        calccolor = "gold2"
        arrowsize = ".5"
        inputcolor = "lightpink3"
        resultscolor = "aquamarine3"
        renderformat = "png"


        # strict=True assures that only one edge is drawn although many may be defined
        dot = Digraph(comment='hubit model', format=renderformat, strict=True)
        dot.attr(compound='true')

        fstr = 'Hubit model: {}\nRendered at {} by {}'
        dot.attr(label=fstr.format(self.name,
                                   datetime.now().strftime("%b %d %Y %H:%M"),
                                   subprocess.check_output(['whoami']).replace("\\", "/"),),
                 fontsize='9',
                 fontname="monospace")



        if querystrings is not None and all_input is not None:
            direction = -1
            workers = self.validate_query(querystrings, all_input, mpworkers=False)
            # with dot.subgraph() as s:
                # s.attr(rank = 'same')
            dot.node("_Response", "Response", shape='box', color=resultscolor, fontcolor=resultscolor)
            dot.node("_Query", '\n'.join(querystrings), shape='box',
                        color=inputcolor, fontsize='9', fontname="monospace",fontcolor=inputcolor)
        else:
            direction = -1 
            workers = []
            for cname, cdata in self.cfg.items():
                dummy_query = cdata["provides"].values()[0].replace(self.ilocstr, "0")
                func, version = QueryRunner.get_func(cname, cdata)
                workers.append(Worker(self, cname, cdata, dummy_query, func, version, self.ilocstr))



        # Component nodes
        with dot.subgraph() as s:
            s.attr(rank = 'same')
            for w in workers:
                s.node(w.name, w.name + '\nv {}'.format(w.version), fontname="monospace",
                       shape='ellipse', style="filled", fillcolor=calccolor, fontsize="10")




        # Extract object names to allow pointing to e.g. results cluster. 
        # This requires one node id in the cluster
        prefix_results = "cluster_results"
        prefix_input = "cluster_input"
        input_object_ids, results_object_ids = self.get_all_objects(prefix_input, prefix_results)

        if querystrings is not None and all_input is not None:
            dot.edge('_Query', results_object_ids[0], lhead=prefix_results, constraint="false",
                     arrowsize=arrowsize, color=inputcolor, arrowhead="box")

            dot.edge(results_object_ids[0], '_Response', ltail=prefix_results, 
                     arrowsize=arrowsize,
                     color=resultscolor)


        for w in workers:
            with dot.subgraph(name='cluster_input', node_attr={'shape': 'box'}) as c:
                c.attr(label='Input', color=inputcolor, style="dashed")

                self._render_objects(w.name, w.inputpath_consumed_for_attrname,
                                     "cluster_input", prefix_input, input_object_ids[0],
                                     c, arrowsize, inputcolor, direction=-direction)

            with dot.subgraph(name='cluster_results', node_attr={'shape': 'box'}) as c:
                c.attr(label='Results', color=resultscolor, style="dashed")
                self._render_objects(w.name, w.resultspath_provided_for_attrname,
                                     "cluster_results", prefix_results, results_object_ids[0],
                                     c, arrowsize, resultscolor, direction=direction)

                # Not all components cosume results
                try:
                    self._render_objects(w.name, w.resultspath_consumed_for_attrname, 
                                         "cluster_results", prefix_results, results_object_ids[0], 
                                         c, arrowsize, resultscolor, direction=-direction,
                                         constraint="false", render_objects=False)
                except KeyError:
                    pass

        filename = 'model'
        dot.render(filename, view=False)


    def _render_objects(self, cname, cdata, clusterid, prefix, cluster_node_id, dot, arrowsize,
               color, direction=1, constraint="true", render_objects=True):
        """
        The constraint attribute, which lets you add edges which are 
        visible but don't affect layout.
        https://stackoverflow.com/questions/2476575/how-to-control-node-placement-in-graphviz-i-e-avoid-edge-crossings
        """

        ids = []
        skipped = []
        attrnames_for_nodeids = {}
        for _, pathstr in cdata.items():
            pathcmps = pathstr.split(".")
            pathcmps_old = copy.copy(pathcmps)
            pathcmps = self.cleanpathcmps(pathcmps)

            # Collect data for connecting to nearest objects 
            # and labeling the edge with the attributes consumed/provided
            if len(pathcmps) > 1:
                _id = '{}{}'.format(prefix, pathcmps[-2])
                t = _id, cname
                try:
                    attrnames_for_nodeids[t].append(pathcmps[-1])
                except KeyError:
                    attrnames_for_nodeids[t] = [pathcmps[-1]]
            else:
                skipped.append(pathcmps[0])
                # t = obj_in_cluster, cname

            nobjs = len(pathcmps) - 1
            if nobjs > 0 and render_objects:

                # Connect objects
                for idx in range(nobjs - 1): # dont include last object since we use "next"
                    pcmp = pathcmps[idx]
                    pcmp_next = pathcmps[idx + 1]
                    
                    # check the next component in the original pathstr (doesnt work for repeated keys)
                    pcmp_old = pathcmps_old[pathcmps_old.index(pcmp) + 1]
                    if pcmp_old == ':' or pcmp_old == self.ilocstr:
                        peripheries = '2'
                    else:
                        peripheries = '1'

                    pcmp_old = pathcmps_old[pathcmps_old.index(pcmp_next) + 1]
                    if pcmp_old == ':' or pcmp_old == self.ilocstr:
                        peripheries_next = '2'
                    else:
                        peripheries_next = '1'

                    _id = '{}{}'.format(prefix, pcmp)
                    _id_next = '{}{}'.format(prefix, pcmp_next)
                    ids.extend([_id, _id_next])
                    dot.node(_id, pcmp, shape='box', fillcolor=color, color=color, fontcolor=color, peripheries=peripheries)
                    dot.node(_id_next, pcmp_next, shape='box', fillcolor=color, color=color, fontcolor=color, peripheries=peripheries_next)
                    t = _id, _id_next
                    # _direction = 1
                    dot.edge(*t[::direction], arrowsize=str(float(arrowsize)*1.5),
                             color=color, constraint=constraint, arrowhead="none")

        self.edge_with_label(attrnames_for_nodeids, color, constraint, direction, arrowsize, dot)

        if len(skipped) > 0:
            if direction == 1:
                clusterid_tail = clusterid
                clusterid_head = None
            else:
                clusterid_tail = None
                clusterid_head = clusterid

            attrnames_for_nodeids = {(cluster_node_id, cname): skipped}
            self.edge_with_label(attrnames_for_nodeids, color, constraint, direction, 
                                 arrowsize, dot, ltail=clusterid_tail, lhead=clusterid_head)

        return skipped, ids


    def get_all_objects(self, prefix_input, prefix_results):
        """
        """
        results_object_ids = set()
        input_object_ids = set()
        for _, cdata in self.cfg.items():
            _cdata = cdata["provides"]
            results_object_ids.update(['{}{}'.format(prefix_results, objname) for objname in self.get_objects(_cdata)])

            _cdata = cdata["consumes"]["input"]
            input_object_ids.update(['{}{}'.format(prefix_input, objname) for objname in self.get_objects(_cdata)])

            # Not all components cosume results
            try:
                _cdata = cdata["consumes"]["results"]
                results_object_ids.update(['{}{}'.format(prefix_results, objname) for objname in self.get_objects(_cdata)])
            except KeyError:
                pass

        results_object_ids = list(results_object_ids)
        input_object_ids = list(input_object_ids)
        return input_object_ids, results_object_ids

    
    def cleanpathcmps(self, pathcmps):
        # TODO: check for digits and mark box below

        _pathcmps = copy.copy(pathcmps)
        try:
            _pathcmps.remove(self.ilocstr)
        except ValueError:
            pass

        try:
            _pathcmps.remove(":")
        except ValueError:
            pass
 
        _pathcmps = [cmp for cmp in  _pathcmps if not cmp.isdigit()] 
 
        return _pathcmps


    def get_objects(self, cdata):
        objects = set()
        for _, pathstr in cdata.items():
            pathcmps = pathstr.split(".")
            pathcmps = self.cleanpathcmps(pathcmps)
            nobjs = len(pathcmps) - 1
            if nobjs > 0:
                objects.update(pathcmps[:-1])
        return objects


    def edge_with_label(self, attrnames_for_nodeids, color, constraint, direction, arrowsize, dot, 
                        ltail=None, lhead=None):
        # Render attributes consumed/provided
        # Add space on the right side of the label. The graph becomes 
        # wider and the edge associated with a given label becomes clearer
        spaces = 7
        for t, attrnames in attrnames_for_nodeids.items():
            tmp = ''.join(['<tr><td align="left">{}</td><td>{}</td></tr>'.format(attrname, " "*spaces) for attrname in attrnames])
            labelstr = '<<table cellpadding="0" border="0" cellborder="0">\
                        {}\
                        </table>>'.format(tmp)

            # ltail is there to attach attributes directly on the cluster
            dot.edge(*t[::direction], label=labelstr, ltail=ltail, lhead=lhead,
                    fontsize='9', fontname="monospace", fontcolor=color, color=color,
                    arrowsize=arrowsize, arrowhead="vee", labeljust='l', constraint=constraint)


    def get(self, querystrings, all_input, mpworkers=False, validate=False):
        """
        all_input is a dictionary with path strings as keys
        """
        flat_input = flatten(all_input)
        qrunner = QueryRunner(self, mpworkers)

        if validate:
            get(qrunner, querystrings, flat_input, dryrun=True)

        get(qrunner, querystrings, flat_input)


    def validate_query(self, querystrings, all_input, mpworkers=False):
        """
        Run the query using a dummy calculation to see that all required 
        input and results are available
        """
        flat_input = flatten(all_input)
        qrunner = QueryRunner(self, mpworkers)
        get(qrunner, querystrings, flat_input, dryrun=True)
        return qrunner.workers


    def get_many(self, querystrings, all_input, input_perturbations, nproc=None):

        tstart = time.time()

        flat_input = flatten(all_input)

        # form all combinations
        pkeys, pvalues = zip(*input_perturbations.items())
        ppvalues = list(itertools.product(*pvalues))

        args = []
        inps = []
        for pvalues in ppvalues:
            _flat_input = copy.deepcopy(flat_input)
            for key, val in zip(pkeys, pvalues):
                _flat_input[key] = val
            qrun = QueryRunner(self, mpworkers=False)
            args.append( (qrun, querystrings, _flat_input) )
            inps.append(_flat_input)

        if nproc is None:
            _nproc = min(len(input_perturbations), cpu_count())
        else:
            _nproc = nproc
        pool = Pool(_nproc)

        # Results are ordered as input but only accessible after completion
        results = pool.map_async(get_star, args, callback=cb)            
        pool.close()
        while len(active_children()) > 1:
            print 'waiting'
            time.sleep(0.25)
        pool.join()
        responses = results.get()

        # Results in random order so we need an ID
        # but callback is called in each query 
        # multiple_results = [pool.apply_async(get, _args, callback=cb) for _args in args]
        # responses = [result.get(timeout=99999) for result in multiple_results]

        print('Queries processed in {} s'.format(time.time() - tstart))


        return responses, inps


    def validate(self):
        """
        Checks that we don't have multiple components providing the same attribute

        TODO: check for circular references
        """
        compname_for_pstring = {}
        for compname, compdata in self.cfg.items():
            for _, pstring in compdata["provides"].items():
                if not pstring in compname_for_pstring:
                    compname_for_pstring[pstring] = compname
                else:
                    fstr = '"{}" on component "{}" also provided by component "{}"'
                    raise BaseException(fstr.format(pstring, compname, compname_for_pstring[pstring]))


class QueryRunner(object):

    def __init__(self, model, mpworkers):
        self.model = model
        self.mpworkers = mpworkers 
        self.workers = []
        self.workers_working = []
        self.workers_completed = []
        self.worker_for_id = {}
        self.observers_for_query = {}


    def components_for_query(self, querystring):
        """
        Find names of components that can respond to the "query".
        """
        itempairs = [(cmpname, pstring) for cmpname, cmpdata in self.model.cfg.items() for _, pstring in cmpdata["provides"].items()]
        compnames, providerstrings = zip(*itempairs)
        idxs = get_matches(querystring, providerstrings, self.model.ilocstr)
        return [compnames[idx] for idx in idxs]


    @staticmethod
    def get_func(cname, cfgdata):
        path, filename = os.path.split(cfgdata["path"])
        filename = os.path.splitext(filename)[0]
        f, _filename, description = imp.find_module(filename, [path])
        module = imp.load_module(filename, f, _filename, description)
        func = getattr(module, cname)
        try:
            version = module.version()
        except AttributeError:
            version = None

        return func, version


    def worker_for_query(self, query, dryrun=False):
        """
        Creates instance of the worker class that can respond to the query
        """
        components = self.components_for_query(query)

        if len(components) > 1:
            msg = "Fatal error. Multiple providers for query '{}': {}".format(query, [wcls.name for wcls in components])
            raise KeyError(msg)

        if len(components) == 0:
            msg = "Fatal error. No provider for query '{}'.".format(query)
            raise KeyError(msg)

        cname = components[0]
        cfgdata = self.model.cfg[cname]
        func, version = QueryRunner.get_func(cname, cfgdata)

        return Worker(self, cname, cfgdata, query, func, version, 
                      self.model.ilocstr, multiprocess=self.mpworkers, dryrun=dryrun)


    def transfer_input(self, input_paths, worker, inputdata, all_input):
        """
        Transfer required input from all input to extracted input
        """
        for pathstr in input_paths:
            val = all_input[pathstr]
            inputdata[pathstr] = val
            worker.set_consumed_input(pathstr, val)


    def deploy(self, querystrings, extracted_input, all_results, all_input, dryrun=False):
        # print('DEPLOY', querystrings)
        for querystring in querystrings:

            # Check whether the queried data is already available  
            if not querystring in all_results:

                # Figure out which worker component can provide a response to the query
                # and get the corresponding worker
                worker = self.worker_for_query(querystring, dryrun=dryrun)

                # Check that another query did not already request this worker
                if worker._id not in self.worker_for_id.keys():
                    self.worker_for_id[worker._id] = worker

                    # Set available data on the worker. If data is missing the corresponding 
                    # paths (queries) are returned  
                    input_paths_missing, querystrings_next = worker.set_values(extracted_input, all_results)

                    self.transfer_input(input_paths_missing, worker, extracted_input, all_input)

                    # Add the worker to the oberservers list for that query in order
                    for query_next in querystrings_next:
                        if query_next in self.observers_for_query.keys():
                            self.observers_for_query[query_next].append(worker)
                        else:
                            self.observers_for_query[query_next] = [worker]

                    self.deploy(querystrings_next,
                                extracted_input,
                                all_results,
                                all_input,
                                dryrun=dryrun)


    def set_worker(self, worker):
        """
        Called from Worker object when the input is set. Not on init since 
        we do not yet know if a similar object exists.
        """
        self.workers.append(worker)


    def set_worker_working(self, worker):
        """
        Called from Worker object just before the worker process is started.
        """
        self.workers_working.append(worker)


    def set_worker_completed(self, worker, all_results):
        """
        Called from Workflow when results attribute has been populated 
        """
        self.workers_completed.append(worker)
        self.transfer_results(worker, all_results)
        self.workers_working.remove(worker)


    def transfer_results(self, worker, all_results):
        """
        Transfer results and notify observers. Called from workflow.
        """
        results = worker.result_for_path()
        # sets results on workflow
        for path, value in results.items():
            if path in self.observers_for_query.keys():
                for observer in self.observers_for_query[path]:
                    observer.set_consumed_result(path, value)
            all_results[path] = value


    def watcher(self, queries, all_results, run_event):
        """
        Run this watcher on a thread. Runs until all queried data is present in the results.
        Not needed for sequential run, but is necessary when main tread should waiting for 
        calculation processes when using multiprocessing
        """
        should_stop = False
        while not should_stop and run_event.is_set():
            # print("WATCH:")
            # print(resultsdata)
            _workers_completed = [worker for worker in self.workers_working if worker.results_ready()]
            for worker in _workers_completed:
                self.set_worker_completed(worker, all_results)

            should_stop = all([query in all_results.keys() for query in queries])
            time.sleep(POLLTIME)

