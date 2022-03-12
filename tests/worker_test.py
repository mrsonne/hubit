import unittest
from unittest.mock import Mock
import yaml
from hubit.tree import DummyLengthTree, tree_for_idxcontext, LengthNode, LengthTree
from hubit.worker import _Worker
from hubit.config import (
    HubitModelComponent,
    HubitBinding,
    HubitModelPath,
    HubitQueryPath,
)
from hubit.errors import HubitWorkerError


def dummy_function():
    pass


class TestWorker(unittest.TestCase):
    def setUp(self):
        pass

    def test_1(self):
        """
        Fails since query does not match.
        """
        func = None
        version = None
        cfg = {
            "path": "dummy",
            "func_name": "dummy",
            "provides_results": [
                {"name": "attr1", "path": "shared.results.attr1.path"},
                {"name": "attr2", "path": "shared.results.attr2.path"},
            ],
            "consumes_input": [{"name": "attr", "path": "shared.input.attr.path"}],
        }
        component = HubitModelComponent.from_cfg(cfg, 0)

        # No index IDs in model
        tree = DummyLengthTree()

        querystring = HubitQueryPath("shared.attr.path")
        with self.assertRaises(HubitWorkerError) as context:
            w = _Worker(
                lambda x: x,
                lambda x: x,
                component,
                querystring,
                func,
                version,
                tree,
                dryrun=True,
            )

    def test_2(self):
        """
        Initialize a simple worker with no idxids
        """
        func = None
        version = None
        cfg = {
            "path": "dummy",
            "func_name": "dummy",
            "provides_results": [
                {"name": "attr1", "path": "shared.results.attr1.path"},
                {"name": "attr2", "path": "shared.results.attr2.path"},
            ],
            "consumes_input": [{"name": "attr", "path": "shared.input.attr.path"}],
        }
        component = HubitModelComponent.from_cfg(cfg, 0)

        # No index IDs in model
        tree_for_idxcontext = {"": DummyLengthTree()}

        # Query something known to exist
        querystring = HubitQueryPath(component.provides_results[0].path)
        w = _Worker(
            lambda x: x,
            lambda x: x,
            component,
            querystring,
            func,
            version,
            tree_for_idxcontext,
            dryrun=True,
        )

    def _make_worker():
        qrunner = Mock()
        qrunner.check_cache.return_value = None
        cname = None
        func = dummy_function
        version = None
        cfg = {
            "path": "dummy",
            "func_name": "dummy_fun",
            "provides_results": [
                {
                    "name": "attrs1",
                    "path": "items_outer[:@IDX_OUTER].attr.items_inner[:@IDX_INNER].path1",
                }
            ],
            "consumes_input": [
                {
                    "name": "attrs",
                    "path": "items_outer[:@IDX_OUTER].attr.items_inner[:@IDX_INNER].path",
                },
                {"name": "number", "path": "some_number"},
            ],
            "consumes_results": [
                {"name": "dependency", "path": "value"},
                {"name": "dependency2", "path": "items_outer[:@IDX_OUTER].value"},
            ],
        }
        component = HubitModelComponent.from_cfg(cfg, 0)

        # Required for shape inference. TODO: change when shapes are defined in model
        inputdata = {
            "items_outer": [
                {"attr": {"items_inner": [{"path": 2}, {"path": 1}]}},
                {"attr": {"items_inner": [{"path": 3}, {"path": 4}]}},
            ],
            "some_number": 33,
        }

        querystring = HubitQueryPath("items_outer[1].attr.items_inner[0].path1")
        _tree_for_idxcontext = tree_for_idxcontext([component], inputdata)

        w = _Worker(
            lambda x: x,
            lambda x: x,
            component,
            querystring,
            func,
            version,
            _tree_for_idxcontext,
            dryrun=True,  # Use dryrun to easily predict the result
        )

        return w

    def test_4(self):
        """
        Adding required data to worker stepwise to see that it
        starts working when all expected consumptions are present

        TODO: split in multiple tests
        """
        w = TestWorker._make_worker()
        # Set current consumed input and results to nothing so we can fill manually
        w.set_values({}, {})

        # input_values = {
        #     "some_number": 64.0,
        #     "items_outer.0.attr.items_inner.0.path": 17.0,
        #     "items_outer.0.attr.items_inner.1.path": 18.0,
        #     "items_outer.1.attr.items_inner.0.path": 19.0,
        #     "items_outer.1.attr.items_inner.1.path": 20.0,
        # }

        input_values = {
            "some_number": 64.0,
            "items_outer[0].attr.items_inner[0].path": 17.0,
            "items_outer[0].attr.items_inner[1].path": 18.0,
            "items_outer[1].attr.items_inner[0].path": 19.0,
            "items_outer[1].attr.items_inner[1].path": 20.0,
        }

        input_values = {HubitQueryPath(key): val for key, val in input_values.items()}

        # Local version of worker input paths pending
        pending_input_paths = list(input_values.keys())
        # add input attributes one by one
        itests_paths_pending = []
        itests_ready_to_work = []
        rtests_paths_pending = []
        rtests_ready_to_work = []

        for key, val in input_values.items():
            w.set_consumed_input(key, val)

            # Update local version
            pending_input_paths.remove(key)

            itests_paths_pending.append(
                set(pending_input_paths) == set(w.pending_input_paths)
            )

            # Worker should not be ready to work since consumed results are missing
            itests_ready_to_work.append(w.is_ready_to_work() == False)

        # results_values = {
        #     "value": 11.0,
        #     "items_outer.1.value": 71.0,
        #     "items_outer.0.value": 49.0,
        # }

        results_values = {
            "value": 11.0,
            "items_outer[1].value": 71.0,
            "items_outer[0].value": 49.0,
        }

        pending_results_paths = list(results_values.keys())

        # Add results values
        for key, val in results_values.items():
            w.set_consumed_result(key, val)

            # Update local version
            pending_results_paths.remove(key)

            rtests_paths_pending.append(
                set(pending_results_paths) == set(w.pending_results_paths)
            )

            # All input is added so should be ready to work when all consumed
            # results have been set
            rtests_ready_to_work.append(
                w.is_ready_to_work() == (len(pending_results_paths) == 0)
            )

        # Start work
        w.work()

        # Work is sequential so now the results are ready
        self.assertTrue(w.results_ready())

        self.assertTrue(all(itests_paths_pending))

        self.assertTrue(all(itests_ready_to_work))

        self.assertTrue(all(rtests_paths_pending))

        self.assertTrue(all(rtests_ready_to_work))

    def test_5(self):
        """
        Initialize worker with ILOC locations in
        query and ILOC wildcards in bindings
        """
        func = None
        version = None
        cfg = """
            path: dummy,
            func_name: dummy,
            provides_results: 
                - name: k_therm 
                  path: segments[IDX_SEG].layers[:@IDX_LAY].k_therm
            consumes_input:
                - name: material
                  path: segments[IDX_SEG].layers[:@IDX_LAY].material
        """
        component = HubitModelComponent.from_cfg(
            yaml.load(cfg, Loader=yaml.FullLoader), 0
        )

        # Query something known to exist
        querystr = HubitQueryPath("segments[0].layers[0].k_therm")

        seg_node = LengthNode(2)
        lay_nodes = LengthNode(2), LengthNode(2)
        seg_node.set_children(lay_nodes)
        nodes = [seg_node]
        nodes.extend(lay_nodes)
        level_names = "IDX_SEG", "IDX_LAY"
        tree = LengthTree(nodes, level_names)
        _tree_for_idxcontext = {tree.index_context: tree}

        querystr = HubitQueryPath(querystr)
        w = _Worker(
            lambda x: x,
            lambda x: x,
            component,
            querystr,
            func,
            version,
            _tree_for_idxcontext,
            dryrun=True,
        )

    def test_6(self):
        """
        Get bindings for query with two location IDs and component
        bindings with one index ID and one index wildcard.

        The index wildcard is left as is since it is handled by
        the expansion
        """
        bindings = [
            HubitBinding.from_cfg(
                {
                    "name": "k_therm",
                    "path": "segments[IDX_SEG].layers[:@IDX_LAY].k_therm",
                }
            )
        ]
        querystring = HubitQueryPath("segments[0].layers[0].k_therm")
        path_for_name, _ = _Worker.get_bindings(bindings, querystring)
        # This is what will be provided for the query: The attribute 'k_therm'
        # for all layers for the specific index ID _IDX=0
        # expected_path_for_name = {"k_therm": "segments.0.layers.:.k_therm"}
        expected_path_for_name = {
            "k_therm": HubitModelPath("segments[0@IDX_SEG].layers[:@IDX_LAY].k_therm")
        }
        self.assertDictEqual(expected_path_for_name, path_for_name)
        self.assertTrue(
            all([type(item) == HubitModelPath for item in path_for_name.values()])
        )

    def test_get_bindings(self):
        """
        Get bindings for query where model path is fully specified
        """
        bindings = [
            HubitBinding.from_cfg(
                {
                    "name": "inflow",
                    "path": "inlets[0@IDX_INLET].tanks[2@IDX_TANK].inflow",
                }
            )
        ]

        # The query path mathces the model path
        querypath = HubitQueryPath("inlets[0].tanks[2].inflow")
        path_for_name, idxval_for_idxid = _Worker.get_bindings(bindings, querypath)
        expected_idxval_for_idxid = {"IDX_INLET": "0", "IDX_TANK": "2"}
        self.assertDictEqual(expected_idxval_for_idxid, idxval_for_idxid)

        expected_path_for_name = {
            "inflow": HubitModelPath("inlets[0@IDX_INLET].tanks[2@IDX_TANK].inflow")
        }
        self.assertDictEqual(expected_path_for_name, path_for_name)

        querypath = HubitQueryPath("inlets.1.tanks.2.inflow")
        with self.assertRaises(HubitWorkerError):
            _Worker.get_bindings(bindings, querypath)

    def test_7(self):
        """Queries should be expanded (location specific)
        otherwise a HubitWorkerError is raised
        """
        provides_results = [
            HubitBinding.from_cfg(
                {
                    "name": "k_therm",
                    "path": "segments[IDX_SEG].layers[:@IDX_LAY].k_therm",
                }
            )
        ]
        querystring = HubitQueryPath("segments[0].layers[:].k_therm")
        with self.assertRaises(HubitWorkerError):
            _Worker.get_bindings(provides_results, querystring)

    def test_8(self):
        """
        Test compression of indices. The query does not include any indices
        """
        func = None
        version = None
        comp_yml = """
                    path: dummy,
                    func_name: dummy,
                    provides_results:
                        - name: mylist
                          path: factors
                    consumes_input: 
                          - name: factors
                            path: list[:@IDX1].some_attr.factors
                    """
        component = HubitModelComponent.from_cfg(
            yaml.load(comp_yml, Loader=yaml.FullLoader), 0
        )

        # Query something known to exist
        querystr = "factors"
        idx1_node = LengthNode(2)
        nodes = [idx1_node]
        level_names = ("IDX1",)
        tree = LengthTree(nodes, level_names)
        dummy_tree = DummyLengthTree()

        _tree_for_idxcontext = {"": dummy_tree, tree.index_context: tree}

        querystr = HubitQueryPath(querystr)
        w = _Worker(
            lambda x: x,
            lambda x: x,
            component,
            querystr,
            func,
            version,
            _tree_for_idxcontext,
            dryrun=True,
        )

    def test_bindings_from_idxs_0(self):
        """
        Substitute idxids with idxs
        """
        bindings = [{"name": "heat_flux", "path": "segments[IDX_SEG].heat_flux"}]
        bindings = [HubitBinding.from_cfg(binding) for binding in bindings]
        idxval_for_idxid = {"IDX_SEG": "3"}
        path_for_name = _Worker.bindings_from_idxs(bindings, idxval_for_idxid)
        expected_path_for_name = {
            "heat_flux": HubitModelPath("segments[3@IDX_SEG].heat_flux")
        }
        self.assertDictEqual(path_for_name, expected_path_for_name)
        self.assertTrue(
            all([type(item) == HubitModelPath for item in path_for_name.values()])
        )

    def test_bindings_from_idxs_1(self):
        """
        Substitute idxids with idxs. Second index ID contains a wildcard
        and should be left as is
        """
        bindings = [
            HubitBinding.from_cfg(
                {
                    "name": "outer_temperature_all_layers",
                    "path": "segments[IDX_SEG].layers[:@IDX_LAY].outer_temperature",
                }
            )
        ]

        idxval_for_idxid = {"IDX_SEG": "0"}
        path_for_name = _Worker.bindings_from_idxs(bindings, idxval_for_idxid)
        expected_path_for_name = {
            "outer_temperature_all_layers": HubitModelPath(
                "segments[0@IDX_SEG].layers[:@IDX_LAY].outer_temperature"
            )
        }
        self.assertDictEqual(path_for_name, expected_path_for_name)
        self.assertTrue(
            all([type(item) == HubitModelPath for item in path_for_name.values()])
        )


if __name__ == "__main__":
    unittest.main()
