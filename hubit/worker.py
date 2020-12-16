from __future__ import print_function
import logging
import multiprocessing
import copy
from typing import Dict
from .shared import (idxs_for_matches,
                     get_iloc_indices,
                     set_ilocs_on_path,
                     traverse,
                     list_from_shape,
                     reshape,
                     path_shape,
                     path_expand,
                     HubitError)

class HubitWorkerError(HubitError):
    pass


class _Worker:
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
        keyvalpairs = [(binding['name'], set_ilocs_on_path(binding['path'],
                                                           _indices_from_query,
                                                           ilocstr)) 
                        for binding in bindings]

        return dict(keyvalpairs), _indices_from_query


    @staticmethod
    def expand(path_for_name, inputdata):
        paths_for_name = {}
        shape_for_name = {}
        for name, path in path_for_name.items():
            if not ":" in path:
                paths_for_name[name] = [path]
                shape_for_name[name] = [1]
                continue
 
            shape_for_name[name] = path_shape(path, inputdata, ".", ":")
            paths_for_name[name] = path_expand(path, shape_for_name[name], ":")

        return paths_for_name, shape_for_name



    # @staticmethod
    # def asdict(values, pstrs):
    #     """
    #     values are results stored in a nested list due to iloc wildcard(s)
    #     attrnames are the correspondning path strings
    #     return a dict of results 
    #     """
    #     return {pstr:value for pstr, value in zip(traverse(pstrs), traverse(values))}



    def __init__(self, hmodel, name, cfg, inputdata, query, func, 
                 version, ilocstr, multiprocess=False, dryrun=False):
        """
        If inputdata is None the worker cannot work but can still 
        render itself and print.

        querystring for one specific location ie no [:]
        """
        self.func = func # function to excecute 
        self.name = name # name of the component
        self.version = version # Version of the component
        self.hmodel = hmodel # reference to the Hubit model instance
        self.use_multiprocessing = multiprocess # flag indicating if multiprocessing should be used
        self.job = None # For referencing the job if using multiprocessing
        self.query = query

        if dryrun:
            # If worker should perform a dry run set the worker function to "work_dryrun"
            self.workfun = self.work_dryrun
        else:
            self.workfun = self.work


        # Paths for values that are consumed but not ready
        self.pending_input_paths = []
        self.pending_results_paths = []

        # Stores required values using internal names as keys  
        self.inputval_for_name = {} 
        self.resultval_for_name = {} 

        # Stores required values using internal names as keys  
        self.inputval_for_path = {} 
        self.resultval_for_path = {} 

        if self.use_multiprocessing:
            # Using a pool for multiple queries block for any multi-processing in the worker
            mgr = multiprocessing.Manager()
            self.results =  mgr.dict() 
        else:
            self.results =  {}


        # TODO: assumes provider has the all ilocs defined
        if "provides" in cfg:
            (self.rpath_provided_for_name,
             self.ilocs) = _Worker.get_bindings(cfg["provides"],
                                                query,
                                                ilocstr)
        else:
            raise HubitWorkerError( 'No provider for Hubit model component "{}"'.format(self.name) )

        if _Worker.consumes_type(cfg, "input"):
            self.ipath_consumed_for_name, _ = _Worker.get_bindings(cfg["consumes"]["input"],
                                                                    query,
                                                                    ilocstr,
                                                                    query_indices=self.ilocs)
        else:
            self.ipath_consumed_for_name = {}


        if _Worker.consumes_type(cfg, "results"):
            self.rpath_consumed_for_name, _ = _Worker.get_bindings(cfg["consumes"]["results"],
                                                                    query,
                                                                    ilocstr,
                                                                    query_indices=self.ilocs)
        else:
            self.rpath_consumed_for_name = {}
            



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
            self.shape_provided_for_name) = _Worker.expand(self.rpath_provided_for_name,
                                                           inputdata)

            self.iname_for_path = {path: key 
                                   for key, paths 
                                   in self.ipaths_consumed_for_name.items()
                                   for path in traverse(paths)}

            self.rname_for_path = {path: key 
                                   for key, paths 
                                   in self.rpaths_consumed_for_name.items() 
                                   for path in traverse(paths)}

        logging.info( f'Worker "{self.name}" was deployed for query "{self.query}"')

    @staticmethod
    def consumes_type(cfg: Dict, consumption_type: str) -> bool:
        """Check if configuration (cfg) consumes the "consumption_type"

        Args:
            cfg (Dict): Componet configuration
            consumption_type (str): The consumption type. Can either be "input" or "results". Validity not checked.

        Returns:
            bool: Flag indicating if the configuration consumes the "consumption_type"
        """
        return ("consumes" in cfg and 
                consumption_type in cfg["consumes"] and 
                len(cfg["consumes"][consumption_type]) > 0)


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
        for name, paths in self.rpaths_provided_for_name.items():
            if len(paths) > 1:
                _out = {path: val 
                        for path, val in zip(traverse(paths),
                                             traverse(self.results[name]))}
            else:
                _out = {paths[0]: self.results[name]}
            out.update(_out)
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
        for name in self.rpath_provided_for_name.keys():
            self.results[name] = list_from_shape(self.shape_provided_for_name[name])


    def join(self):
        if self.job is not None:
            self.job.join()


    def work(self):
        """
        Executes actual work
        """
        logging.info( f'Worker "{self.name}" started for query "{self.query}"')

        logging.debug( '\n**START WORKING**\n{}'.format(self.__str__()) )

        # Notify the hubit model that we are about to start the work
        self.hmodel._set_worker_working(self)
        if self.use_multiprocessing:
            self.job = multiprocessing.Process(target=self.func,
                                               args=(self.inputval_for_name,
                                                     self.resultval_for_name,
                                                     self.results))
            self.job.daemon = False
            self.job.start()
        else:
            self.func(self.inputval_for_name,
                      self.resultval_for_name,
                      self.results)

        logging.debug( '\n**STOP WORKING**\n{}'.format(self.__str__()) )
        logging.info( f'Worker "{self.name}" finished for query "{self.query}"')


    def reshape(self, path_for_name, val_for_path):
        """
        Convert val_for_pathstr to val_for_attrname i.e. 
        from external names to internal names with expected shapes
        """
        return {name: reshape(path, val_for_path)
                for name, path in path_for_name.items()}


    def is_ready_to_work(self):
        return (len(self.pending_input_paths) == 0 and 
                len(self.pending_results_paths) == 0)


    def work_if_ready(self):
        """
        If all consumed attributes are present start working
        """
        if self.is_ready_to_work():
            logging.debug( "Let the work begin: {}".format(self.workfun) )

            self.inputval_for_name = self.reshape(self.ipaths_consumed_for_name,
                                                  self.inputval_for_path
                                                  )

            self.resultval_for_name = self.reshape(self.rpaths_consumed_for_name,
                                                   self.resultval_for_path
                                                   )


            self.workfun()


    def set_consumed_input(self, path, value):
        if path in self.pending_input_paths:
            self.pending_input_paths.remove(path)
            self.inputval_for_path[path] = value

        self.work_if_ready()


    def set_consumed_result(self, path, value):
        if path in self.pending_results_paths:
            self.pending_results_paths.remove(path)
            self.resultval_for_path[path] = value
        
        self.work_if_ready()


    def set_values(self, inputdata, resultsdata):
        """
        Set the consumed values if they are ready otherwise add them
        to the list of pending items
        """
        # set the worker here since in init we have not yet checked that a similar instance does not exist
        self.hmodel._set_worker(self)

        # Check consumed input (should not have any pending items by definition)
        for path in self.iname_for_path.keys():
            if path in inputdata.keys():
               self.inputval_for_path[path] = inputdata[path]
            else:
                self.pending_input_paths.append(path)

        # Check consumed results
        for path in self.rname_for_path.keys():
            if path in resultsdata.keys():
                self.resultval_for_path[path] = resultsdata[path]
            else:
                self.pending_results_paths.append(path)

        self.work_if_ready()

        return (copy.copy(self.pending_input_paths), 
                copy.copy(self.pending_results_paths))
        


    def idstr(self):
        """
        Make an ID string for the worker class that will be the same 
        if all ilocs are the same for the same component
        """
        return 'name={} v{} ilocs={}'.format(self.name, self.version, self.ilocs)


    def __str__(self):
        n = 100
        fstr1 = 'R provided {}\nR provided exp {}\nI consumed {}\nI consumed exp {}\nR consumed {}\nR consumed exp {}\n'
        fstr2 = 'I attr values {}\nI path values {}\nR attr values {}\nR path values {}\nI pending {}\nR pending {}\n'
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
        strtmp += fstr2.format(self.inputval_for_name,
                               self.inputval_for_path,
                               self.resultval_for_name,
                               self.resultval_for_path,
                               self.pending_input_paths,
                               self.pending_results_paths
                               )
        strtmp += '-'*n + '\n'
        strtmp += 'Results {}\n'.format(self.results)
        
        strtmp += '='*n + '\n'

        return strtmp
