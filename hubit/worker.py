from __future__ import print_function
import logging
import multiprocessing
import copy
from .shared import (idxs_for_matches,
                     get_iloc_indices,
                     set_ilocs_on_pathstr,
                     traverse,
                     list_from_shape,
                     reshape,
                     get_from_datadict,
                     pstr_shape,
                     pstr_expand,
                     get_nested_list,
                     HubitError)

class HubitWorkerError(HubitError):
    pass


class _Worker(object):
    """
    """

    # @staticmethod
    # def get_lengths(pstr, inputdata, sepstr, wcilocstr, idxold=0):
    #     """
    #     No homogeneity assumption
    #     """
    #     if pstr.count(wcilocstr) == 0: 
    #         return {}

    #     pcmps = [int(pcmp) if pcmp.isdigit() else pcmp for pcmp in pstr.split(sepstr)]

    #     idx = pcmps[idxold:].index(wcilocstr) 
    #     cidx = idx + idxold
    #     m = len(get_from_datadict(inputdata, pcmps[:cidx]))
    #     _id = sepstr.join([str(cmp) for cmp in pcmps[:cidx]])
    #     counts = {_id : m}

    #     for _m in range(m):
    #         pcmps[idx] = _m
    #         _pstr = sepstr.join([str(cmp) for cmp in pcmps])
    #         counts.update(Worker.get_lengths(_pstr, inputdata, sepstr, wcilocstr, idxold=cidx-1))

    #     return counts


    @staticmethod
    def get_bindings(bindings, query_path, ilocstr, query_indices=None):
        """Make symbolic binding specific i.e. replace index IDs 
        with actual indices based on query

        Args:
            bindings (List[str]): List of bindings 
            query_path (str): Query path
            ilocstr (str): Index identification string
            query_indices (List[int], optional): TODO [description]. Defaults to None.

        Raises:
            HubitWorkerError: Raised if query does not match any of the bindings

        Returns:
            [type]: TODO [description]
        """
        binding_paths = [binding['path'] for binding in bindings]

        if query_indices is None:
            # Get indices in binding_paths list that match the query
            idxs = idxs_for_matches(query_path, binding_paths, ilocstr)
            if len(idxs) == 0:
                fstr = 'Query "{}" did not match attributes provided by worker ({}).'
                raise HubitWorkerError(fstr.format(query_path,
                                                   ", ".join(binding_paths)))

            # Get the location indices from query. Using the first binding path that 
            # matched the query suffice
            _indices_from_query = get_iloc_indices(query_path,
                                                   binding_paths[idxs[0]],
                                                   ilocstr)
        else:
            _indices_from_query = query_indices

        # replace ILOCSTR with the actual indices
        keyvalpairs = [(binding['name'], set_ilocs_on_pathstr(binding['path'],
                                                              _indices_from_query,
                                                              ilocstr)) 
                        for binding in bindings]

        return dict(keyvalpairs), _indices_from_query


    @staticmethod
    def expand(path_for_name, inputdata):
        paths_for_name = {}
        # exp_for_attrname = {}
        shape_for_name = {}
        for name, path in path_for_name.items():
            if not ":" in path:
                paths_for_name[name] = [path]
                # exp_for_attrname[attrname] = False
                shape_for_name[name] = [1]
                continue
 
            shape = pstr_shape(path, inputdata, ".", ":")
            pstrs = pstr_expand(path, shape, ":")
            paths_for_name[name] = pstrs
            # exp_for_attrname[attrname] = True
            shape_for_name[name] = shape

        return paths_for_name, shape_for_name



    # @staticmethod
    # def asdict(values, pstrs):
    #     """
    #     values are results stored in a nested list due to iloc wildcard(s)
    #     attrnames are the correspondning path strings
    #     return a dict of results 
    #     """
    #     return {pstr:value for pstr, value in zip(traverse(pstrs), traverse(values))}



    def __init__(self, hmodel, cname, cfg, inputdata, querystring, func, 
                 version, ilocstr, multiprocess=False, dryrun=False,
                 logging_level=logging.DEBUG):
        """
        If inputdata is None the worker cannot work but can still 
        render itself and print.

        querystring for one specific location ie no [:]
        """
        logging.basicConfig(level=logging_level)

        self.func = func
        self.name = cname
        self.version = version
        self.hmodel = hmodel
        self.multiprocess = multiprocess
        self.job = None
        # print "Worker"
        # print 'name', cname
        # print 'query', querystring
        # print 'provides', cfg["provides"]
        # print 'consumes', cfg["consumes"]
        # sfwefwe

        if dryrun:
            self.workfun = self.work_dryrun
        else:
            self.workfun = self.work


        self.pending_input_pathstrs = []
        self.pending_results_pathstrs = []

        # Stores required values using internal names as keys  
        self.inputval_for_attrname = {} 
        self.resultval_for_attrname = {} 

        # Stores required values using internal names as keys  
        self.inputval_for_pstr = {} 
        self.resultval_for_pstr = {} 

        # actual
        if self.multiprocess:
            # Using a pool for multiple queries block for any multi-processing in the worker
            mgr = multiprocessing.Manager()
            self.results =  mgr.dict() 
        else:
            self.results =  {}


        # TODO: assumes provider has the all ilocs defined
        if "provides" in cfg:
            (self.rpath_provided_for_name,
             self.ilocs) = _Worker.get_bindings(cfg["provides"],
                                                querystring,
                                                ilocstr)
        else:
            raise HubitWorkerError( 'No provider for Hubit model component "{}"'.format(cname) )

        self.rpath_consumed_for_name = {}
        self.ipath_consumed_for_name = {}
        if "consumes" in cfg:
            if "input" in cfg["consumes"] and len(cfg["consumes"]["input"]) > 0:
                self.ipath_consumed_for_name, _ = _Worker.get_bindings(cfg["consumes"]["input"],
                                                                       querystring,
                                                                       ilocstr,
                                                                       query_indices=self.ilocs)

            if "results" in cfg["consumes"]  and len(cfg["consumes"]["results"]) > 0:
                self.rpath_consumed_for_name, _ = _Worker.get_bindings(cfg["consumes"]["results"],
                                                                       querystring,
                                                                       ilocstr,
                                                                       query_indices=self.ilocs)
            



        self._id = self.idstr()

        # print 'ORG inp', self.ipath_consumed_for_name
        # print 'ORG results', self.rpath_provided_for_name

        # Expand queries containing iloc wildcard

        if inputdata is not None:
            self.ipaths_consumed_for_name, _ = _Worker.expand(self.ipath_consumed_for_name,
                                                              inputdata)

            self.rpaths_consumed_for_name, _ = _Worker.expand(self.rpath_consumed_for_name,
                                                              inputdata)

            # Expand from abstract path with : to list of paths with actual ilocs
            (self.rpaths_provided_for_name,
            self.shape_provided_for_attrname) = _Worker.expand(self.rpath_provided_for_name,
                                                               inputdata)

            self.input_attrname_for_pathstr = {path: key 
                                               for key, paths in self.ipaths_consumed_for_name.items()
                                               for path in traverse(paths)}
            self.results_attrname_for_pathstr = {path: key 
                                                 for key, paths in self.rpaths_consumed_for_name.items() 
                                                 for path in traverse(paths)}


    def paths_provided(self):
        """Generates a list of the (expanded) paths that will be provided.  

        Returns:
            List: Sequence of paths that will be provided by the worker
        """
        return [path 
                for paths in self.rpaths_provided_for_name.values()
                for path in paths]


    def result_for_path(self):
        """
        Convert the results from internal attribute names to shared data names
        and expand ilocs
        """

        # TODO: Work only with : and not..... but not elegant...
        out = {}
        for attrname, pstrs in self.rpaths_provided_for_name.items():
            
            if len(pstrs) > 1:
                for pstr, val in zip(traverse(pstrs), traverse(self.results[attrname])):
                    out[pstr] = val
            else:
                out[pstrs[0]] = self.results[attrname]
        return out


        # Work only with :
        # return {pstr:val for attrname, pstrs in self.rpaths_provided_for_name.items() \
        #                  for pstr, val in zip(traverse(pstrs), traverse(self.results[attrname]))}

        # Does not work with :
        # return {pathstr:self.results[key] for key, pathstr in self.rpath_provided_for_name.items()}


    def results_ready(self):
        """
        Checks that all attributes provided have been calculated
        """
        return set(self.results.keys()) == set(self.rpath_provided_for_name.keys())


    def work_dryrun(self):
        """
        Sets all results to None
        """
        self.hmodel._set_worker_working(self)
        for attrname in self.rpath_provided_for_name.keys():
            self.results[attrname] = list_from_shape(self.shape_provided_for_attrname[attrname])


    def join(self):
        if self.job is not None:
            self.job.join()


    def work(self):
        """
        Executes actual work
        """
        logging.debug( '\n**START WORKING**\n{}'.format(self.__str__()) )

        # Notify the hubit model that we are about to start the work
        self.hmodel._set_worker_working(self)
        if self.multiprocess:
            self.job = multiprocessing.Process(target=self.func,
                                               args=(self.inputval_for_attrname,
                                                     self.resultval_for_attrname,
                                                     self.results))
            self.job.daemon = False
            self.job.start()
        else:
            self.func(self.inputval_for_attrname,
                      self.resultval_for_attrname,
                      self.results)

        logging.debug( '\n**STOP WORKING**\n{}'.format(self.__str__()) )


    def reshape(self, pstrs_for_attrname, val_for_pstr):
        """
        Convert val_for_pathstr to val_for_attrname i.e. 
        from external names to internal names with expected shapes
        """
        return {attrname: reshape(pstrs, val_for_pstr)
                for attrname, pstrs in pstrs_for_attrname.items()}

    def is_ready_to_work(self):
        return (len(self.pending_input_pathstrs) == 0 and 
                len(self.pending_results_pathstrs) == 0)


    def work_if_ready(self):
        """
        If all consumed attributes are present start working
        """
        # print "work_if_ready", self.name, self.pending_results_pathstrs, self.pending_input_pathstrs
        if self.is_ready_to_work():
            print("Let the work begin", self.workfun)

            self.inputval_for_attrname = self.reshape(self.ipaths_consumed_for_name,
                                                      self.inputval_for_pstr
                                                      )

            self.resultval_for_attrname = self.reshape(self.rpaths_consumed_for_name,
                                                       self.resultval_for_pstr
                                                       )


            self.workfun()


    def set_consumed_input(self, pathstr, value):
        if pathstr in self.pending_input_pathstrs:
            self.pending_input_pathstrs.remove(pathstr)
            self.inputval_for_pstr[pathstr] = value

        self.work_if_ready()


    def set_consumed_result(self, pathstr, value):
        if pathstr in self.pending_results_pathstrs:
            self.pending_results_pathstrs.remove(pathstr)
            self.resultval_for_pstr[pathstr] = value
        
        self.work_if_ready()


    def set_values(self, inputdata, resultsdata):
        """
        Set the consumed values if they are ready otherwise add them
        to the list of pending items
        """
        # set the worker here since in init we have not yet checked that a similar instance does not exist
        self.hmodel._set_worker(self)

        # Check consumed input (should not have any pending items by definition)
        for pathstr in self.input_attrname_for_pathstr.keys():
            if pathstr in inputdata.keys():
               self.inputval_for_pstr[pathstr] = inputdata[pathstr]
            else:
                self.pending_input_pathstrs.append(pathstr)

        # Check consumed results
        for pathstr in self.results_attrname_for_pathstr.keys():
            if pathstr in resultsdata.keys():
                self.resultval_for_pstr[pathstr] = resultsdata[pathstr]
            else:
                self.pending_results_pathstrs.append(pathstr)

        self.work_if_ready()

        return (copy.copy(self.pending_input_pathstrs), 
                copy.copy(self.pending_results_pathstrs))
        


    def idstr(self):
        """
        Make an ID string for the worker class that will be the same 
        if all ilocs are the same for the same component
        """
        return 'name={} v{} ilocs={}'.format(self.name, self.version, self.ilocs)


    def __str__(self):
        n = 100
        fstr1 = 'R provided {}\nR provided exp {}\nI consumed {}\nI consumed exp {}\nR consumed {}\nR consumed exp {}\n'
        fstr2 = 'I attr values {}\nI pstr values {}\nR attr values {}\nR pstr values {}\nI pending {}\nR pending {}\n'
        strtmp = '='*n + '\n'
        strtmp += 'ID {}\n'.format(self.idstr())
        strtmp += 'Function {}\n'.format(self.func)
        strtmp += '-'*n + '\n'
        strtmp += fstr1.format(self.rpath_provided_for_name,
                               self.rpaths_provided_for_name,
                               self.ipath_consumed_for_name,
                               self.ipaths_consumed_for_name,
                               self.rpath_consumed_for_name,
                               self.rpaths_consumed_for_name,
                               )
        strtmp += '-'*n + '\n'
        strtmp += fstr2.format(self.inputval_for_attrname,
                               self.inputval_for_pstr,
                               self.resultval_for_attrname,
                               self.resultval_for_pstr,
                               self.pending_input_pathstrs,
                               self.pending_results_pathstrs
                               )
        strtmp += '-'*n + '\n'
        strtmp += 'Results {}\n'.format(self.results)
        
        strtmp += '='*n + '\n'

        return strtmp
