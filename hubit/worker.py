import multiprocessing
import copy
from shared import get_matches, get_indices, set_ilocs


class Worker(object):
    """
    """

    @staticmethod
    def get_bindings(bindingdata, querystring, ilocstr, ilocs=None):
        itempairs = [(internalname, pstring) for internalname, pstring in bindingdata.items()]
        _, pathstrings = zip(*itempairs)

        if ilocs is None:
            # get indices in path string list that match the query
            idxs = get_matches(querystring, pathstrings, ilocstr)
            # get the location indices from query
            _ilocs = get_indices(querystring, pathstrings[idxs[0]], ilocstr)
        else:
            _ilocs = ilocs

        # replace ILOCSTR with the actual iloc indices
        keyvalpairs = [(internalname, set_ilocs(pstring, _ilocs, ilocstr)) for internalname, pstring in bindingdata.items()]

        return dict(keyvalpairs), _ilocs


    def __init__(self, hmodel, cname, cfg, querystring, func, 
                 version, ilocstr, multiprocess=False, dryrun=False):
        self.func = func
        self.name = cname
        self.version = version
        self.hmodel = hmodel
        self.multiprocess = multiprocess

        if dryrun:
            self.workfun = self.work_dryrun
        else:
            self.workfun = self.work


        self.pending_input_pathstrs = []
        self.pending_results_pathstrs = []

        # Stores required values using internal names as keys  
        self.inputval_for_attrname = {} 
        self.resultval_for_attrname = {} 

        # actual
        if self.multiprocess:
            # Using a pool for multiple queries block for any multi-processing in the worker
            mgr = multiprocessing.Manager()
            self.results =  mgr.dict() 
        else:
            self.results =  {}


        # TODO: assumes provider has the all ilocs defined
        self.resultspath_provided_for_attrname, self.ilocs = Worker.get_bindings(cfg["provides"],
                                                                                 querystring,
                                                                                 ilocstr)

        self.resultspath_consumed_for_attrname = {}
        self.inputpath_consumed_for_attrname = {}
        if "consumes" in cfg:
            if "input" in cfg["consumes"]:
                self.inputpath_consumed_for_attrname, _ = Worker.get_bindings(cfg["consumes"]["input"],
                                                                            querystring,
                                                                            ilocstr,
                                                                            ilocs=self.ilocs)

            if "results" in cfg["consumes"]:
                self.resultspath_consumed_for_attrname, _ = Worker.get_bindings(cfg["consumes"]["results"],
                                                                                querystring,
                                                                                ilocstr,
                                                                                ilocs=self.ilocs)
            

        self.input_attrname_for_pathstr = {pathstr:key for key, pathstr in self.inputpath_consumed_for_attrname.items()}
        self.results_attrname_for_pathstr = {pathstr:key for key, pathstr in self.resultspath_consumed_for_attrname.items()}

        self._id = self.idstr()


    def result_for_path(self):
        """
        Convert the results from internal attribute names to shared data names
        """
        return {pathstr:self.results[key] for key, pathstr in self.resultspath_provided_for_attrname.items()}


    def results_ready(self):
        """
        Checks that all attributes provided have been calculated
        """
        return set(self.results.keys()) == set(self.resultspath_provided_for_attrname.keys())


    def work_dryrun(self):
        """
        Sets all results to None
        """
        self.hmodel.set_worker_working(self)
        for attrname in self.resultspath_provided_for_attrname.keys():
            self.results[attrname] = None


    def work(self):
        """
        Executes actual work
        """
        print('\n**START WORKING**\n{}'.format(self.__str__()))

        # Notify the hubit model that we are about to start the work
        self.hmodel.set_worker_working(self)

        if self.multiprocess:
            job = multiprocessing.Process(target=self.func, args=(self.inputval_for_attrname,
                                                                  self.resultval_for_attrname,
                                                                  self.results))
            job.start()
        else:
            self.func(self.inputval_for_attrname, self.resultval_for_attrname, self.results)

        print('\n**STOP WORKING**\n{}'.format(self.__str__()))


    def work_if_ready(self):
        """
        If all consumed attributes are present start working
        """
        if len(self.pending_input_pathstrs) == 0 and len(self.pending_results_pathstrs) == 0:
            self.workfun()
            # self.work()


    def set_consumed_input(self, pathstr, value):
        if pathstr in self.pending_input_pathstrs:
            self.pending_input_pathstrs.remove(pathstr)
            self.inputval_for_attrname[self.input_attrname_for_pathstr[pathstr]] = value

        self.work_if_ready()


    def set_consumed_result(self, pathstr, value):
        if pathstr in self.pending_results_pathstrs:
            self.pending_results_pathstrs.remove(pathstr)
            self.resultval_for_attrname[self.results_attrname_for_pathstr[pathstr]] = value
        
        self.work_if_ready()


    def set_values(self, inputdata, resultsdata):
        """
        Set the consumed values if they are ready otherwise add them
        to the list of pending items
        """
        # set the worker here since in init we have not yet checked that a similar instance does not exist
        self.hmodel.set_worker(self)

        # Check consumed input (should not have any pending items by definition)
        for pathstr in self.input_attrname_for_pathstr.keys():
            if pathstr in inputdata.keys():
                self.inputval_for_attrname[self.input_attrname_for_pathstr[pathstr]] = inputdata[pathstr]
            else:
                self.pending_input_pathstrs.append(pathstr)

        # Check consumed results
        for pathstr in self.results_attrname_for_pathstr.keys():
            if pathstr in resultsdata.keys():
                self.resultval_for_attrname[self.results_attrname_for_pathstr[pathstr]] = resultsdata[pathstr]
            else:
                self.pending_results_pathstrs.append(pathstr)

        self.work_if_ready()

        return copy.copy(self.pending_input_pathstrs), copy.copy(self.pending_results_pathstrs)
        


    def idstr(self):
        """
        Make an ID string for the class that will be the same 
        if all ilocs are the same for the same component
        """
        return 'name={} v{} ilocs={}'.format(self.name, self.version, self.ilocs)


    def __str__(self):
        fstr1 = 'ID {}\nResults provided {}\nInput consumed {}\nResults consumed {}\n'
        fstr2 = 'Input values {}\nInput pending {}\nResults values {}\nResults pending {}\nResults {}\n'
        strtmp = fstr1.format(self.idstr(),
                              self.resultspath_provided_for_attrname,
                              self.inputpath_consumed_for_attrname,
                              self.resultspath_consumed_for_attrname)

        strtmp += fstr2.format(self.inputval_for_attrname,
                               self.pending_input_pathstrs,
                               self.resultval_for_attrname,
                               self.pending_results_pathstrs,
                               self.results)
        return strtmp
