from __future__ import print_function
import logging
import multiprocessing
import itertools
import copy
import sys
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
    def get_bindings(bindingdata, querystring, ilocstr, ilocs=None):
        itempairs = [(internalname, pstring) 
                     for internalname, pstring in bindingdata.items()]

        # Get path string for attributes provided
        _, pathstrings = zip(*itempairs)
        
        if ilocs is None:
            # get indices in path string list that match the query
            idxs = idxs_for_matches(querystring, pathstrings, ilocstr)
            if len(idxs) == 0:
                errmsg = 'Query "{}" did not match attributes provided by worker ({}).'.format(querystring,
                                                                                               ', '.join(pathstrings))
                raise HubitWorkerError(errmsg)

            # get the location indices from query
            _ilocs = get_iloc_indices(querystring, pathstrings[idxs[0]], ilocstr)
        else:
            _ilocs = ilocs

        # replace ILOCSTR with the actual iloc indices
        keyvalpairs = [(internalname, set_ilocs_on_pathstr(pstring, _ilocs, ilocstr)) for internalname, pstring in bindingdata.items()]

        return dict(keyvalpairs), _ilocs

    @staticmethod
    def expand(pstr_for_attrname, inputdata):
        pstrs_for_attrname = {}
        # exp_for_attrname = {}
        shape_for_attrname = {}
        for attrname, pstr in pstr_for_attrname.items():
            if not ":" in pstr:
                pstrs_for_attrname[attrname] = [pstr]
                # exp_for_attrname[attrname] = False
                shape_for_attrname[attrname] = [1]
                continue
 
            shape = pstr_shape(pstr, inputdata, ".", ":")
            pstrs = pstr_expand(pstr, shape, ":")
            pstrs_for_attrname[attrname] = pstrs
            # exp_for_attrname[attrname] = True
            shape_for_attrname[attrname] = shape

        return pstrs_for_attrname, shape_for_attrname



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
        """
        logging.basicConfig(level=logging_level)

        self.func = func
        self.name = cname
        self.version = version
        self.hmodel = hmodel
        self.multiprocess = multiprocess

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
            print(querystring)
            self.resultspath_provided_for_attrname, self.ilocs = _Worker.get_bindings(cfg["provides"],
                                                                                      querystring,
                                                                                      ilocstr)
        else:
            raise HubitWorkerError( 'No provider for Hubit model component "{}"'.format(cname) )

        self.resultspath_consumed_for_attrname = {}
        self.inputpath_consumed_for_attrname = {}
        if "consumes" in cfg:
            if "input" in cfg["consumes"] and len(cfg["consumes"]["input"]) > 0:
                self.inputpath_consumed_for_attrname, _ = _Worker.get_bindings(cfg["consumes"]["input"],
                                                                               querystring,
                                                                               ilocstr,
                                                                               ilocs=self.ilocs)

            if "results" in cfg["consumes"]  and len(cfg["consumes"]["results"]) > 0:
                self.resultspath_consumed_for_attrname, _ = _Worker.get_bindings(cfg["consumes"]["results"],
                                                                                 querystring,
                                                                                 ilocstr,
                                                                                 ilocs=self.ilocs)
            



        self._id = self.idstr()

        # print 'ORG inp', self.inputpath_consumed_for_attrname
        # print 'ORG results', self.resultspath_provided_for_attrname

        # Expand queries containing iloc wildcard

        if inputdata is not None:
            self.inputpaths_consumed_for_attrname, _ = _Worker.expand(self.inputpath_consumed_for_attrname,
                                                                      inputdata)

            self.resultspaths_consumed_for_attrname, _ = _Worker.expand(self.resultspath_consumed_for_attrname,
                                                                        inputdata)

            (self.resultspaths_provided_for_attrname,
            self.shape_provided_for_attrname) = _Worker.expand(self.resultspath_provided_for_attrname,
                                                               inputdata)

            self.input_attrname_for_pathstr = {pathstr:key for key, pathstrs in self.inputpaths_consumed_for_attrname.items() for pathstr in traverse(pathstrs)}
            self.results_attrname_for_pathstr = {pathstr:key for key, pathstrs in self.resultspaths_consumed_for_attrname.items() for pathstr in traverse(pathstrs)}



    def result_for_path(self):
        """
        Convert the results from internal attribute names to shared data names
        and expand ilocs
        """

        # TODO: Work only with : and not..... but not elegant...
        out = {}
        for attrname, pstrs in self.resultspaths_provided_for_attrname.items():
            
            if len(pstrs) > 1:
                for pstr, val in zip(traverse(pstrs), traverse(self.results[attrname])):
                    out[pstr] = val
            else:
                out[pstrs[0]] = self.results[attrname]
        return out


        # Work only with :
        # return {pstr:val for attrname, pstrs in self.resultspaths_provided_for_attrname.items() \
        #                  for pstr, val in zip(traverse(pstrs), traverse(self.results[attrname]))}

        # Does not work with :
        # return {pathstr:self.results[key] for key, pathstr in self.resultspath_provided_for_attrname.items()}


    def results_ready(self):
        """
        Checks that all attributes provided have been calculated
        """
        return set(self.results.keys()) == set(self.resultspath_provided_for_attrname.keys())


    def work_dryrun(self):
        """
        Sets all results to None
        """
        self.hmodel._set_worker_working(self)
        for attrname in self.resultspath_provided_for_attrname.keys():
            self.results[attrname] = list_from_shape(self.shape_provided_for_attrname[attrname])


    def work(self):
        """
        Executes actual work
        """
        logging.debug( '\n**START WORKING**\n{}'.format(self.__str__()) )

        # Notify the hubit model that we are about to start the work
        self.hmodel._set_worker_working(self)
        if self.multiprocess:
            job = multiprocessing.Process(target=self.func,
                                          args=(self.inputval_for_attrname,
                                                self.resultval_for_attrname,
                                                self.results))
            job.start()
        else:
            self.func(self.inputval_for_attrname, self.resultval_for_attrname, self.results)

        logging.debug( '\n**STOP WORKING**\n{}'.format(self.__str__()) )


    def reshape(self, pstrs_for_attrname, val_for_pstr):
        """
        Convert val_for_pathstr to val_for_attrname i.e. 
        from external names to internal names with expected shapes
        """
        return {attrname: reshape(pstrs, val_for_pstr) for attrname, pstrs in pstrs_for_attrname.items()}

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

            self.inputval_for_attrname = self.reshape(self.inputpaths_consumed_for_attrname,
                                                      self.inputval_for_pstr
                                                      )

            self.resultval_for_attrname = self.reshape(self.resultspaths_consumed_for_attrname,
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
        strtmp += fstr1.format(self.resultspath_provided_for_attrname,
                               self.resultspaths_provided_for_attrname,
                               self.inputpath_consumed_for_attrname,
                               self.inputpaths_consumed_for_attrname,
                               self.resultspath_consumed_for_attrname,
                               self.resultspaths_consumed_for_attrname,
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
