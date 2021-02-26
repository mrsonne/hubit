import unittest
from unittest.mock import Mock
import yaml
from hubit import shared
from hubit.worker import _Worker, HubitWorkerError


class TestWorker(unittest.TestCase):
    def setUp(self):
        self.manager = None

    def test_1(self):
        """
        Fails since query does not match.
        """
        hmodel = None
        cname = None
        func = None
        version = None
        comp_data = {
            "provides": [
                {"name": "attr1", "path": "shared.results.attr1.path"},
                {"name": "attr2", "path": "shared.results.attr2.path"},
            ],
            "consumes": {
                "input": [{"name": "attr", "path": "shared.input.attr.path"}],
                "results": [],
            },
        }

        # No index IDs in model
        tree = shared.DummyLengthTree()

        # inputdata = {'shared' : {"input": {"attr": {"path": 2}}}}
        # [{'name':, 'path':},
        # {'name':, 'path':}]

        querystring = "shared.attr.path"
        with self.assertRaises(HubitWorkerError) as context:
            w = _Worker(
                self.manager,
                hmodel,
                cname,
                comp_data,
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
        hmodel = None
        cname = None
        func = None
        version = None
        comp_data = {
            "provides": [
                {"name": "attr1", "path": "shared.results.attr1.path"},
                {"name": "attr2", "path": "shared.results.attr2.path"},
            ],
            "consumes": {
                "input": [{"name": "attr", "path": "shared.input.attr.path"}],
                "results": [],
            },
        }

        # No index IDs in model
        tree_for_idxcontext = {"": shared.DummyLengthTree()}

        # Query something known to exist
        querystring = comp_data["provides"][0]["path"]
        w = _Worker(
            self.manager,
            hmodel,
            cname,
            comp_data,
            querystring,
            func,
            version,
            tree_for_idxcontext,
            dryrun=True,
        )

    def test_3(self):
        """
        Componet provides nothing => error
        """
        hmodel = None
        cname = "Test component"
        func = None
        version = None
        cfg = {
            "consumes": {
                "input": [{"name": "attr", "path": "shared.input.attr.path"}],
                "results": [],
            }
        }

        # No index IDs in model
        tree = shared.DummyLengthTree()

        querystring = "shared.results.attr1.path"

        with self.assertRaises(HubitWorkerError) as context:
            w = _Worker(
                self.manager,
                hmodel,
                cname,
                cfg,
                querystring,
                func,
                version,
                tree,
                dryrun=True,
            )

    def test_4(self):
        """
        Adding required data to worker stepwise to see that it
        starts working when all expected consumptions are present

        TODO: split in multiple tests
        """
        hmodel = Mock()
        hmodel._set_worker
        hmodel._set_worker_working

        cname = None
        func = None
        version = None
        cfg = {
            "provides": [
                {
                    "name": "attrs1",
                    "path": "items_outer[:@IDX_OUTER].attr.items_inner[:@IDX_INNER].path1",
                }
            ],
            "consumes": {
                "input": [
                    {
                        "name": "attrs",
                        "path": "items_outer[:@IDX_OUTER].attr.items_inner[:@IDX_INNER].path",
                    },
                    {"name": "number", "path": "some_number"},
                ],
                "results": [
                    {"name": "dependency", "path": "value"},
                    {"name": "dependency2", "path": "items_outer[:@IDX_OUTER].value"},
                ],
            },
        }

        # Required for shape inference. TODO: change when shapes are defined in model
        inputdata = {
            "items_outer": [
                {"attr": {"items_inner": [{"path": 2}, {"path": 1}]}},
                {"attr": {"items_inner": [{"path": 3}, {"path": 4}]}},
            ],
            "some_number": 33,
        }

        querystring = "items_outer.1.attr.items_inner.0.path1"
        tree_for_idxcontext = shared.tree_for_idxcontext([cfg], inputdata)

        w = _Worker(
            self.manager,
            hmodel,
            cname,
            cfg,
            querystring,
            func,
            version,
            tree_for_idxcontext,
            dryrun=True,  # Use dryrun to easily predict the result
        )

        # Set current consumed input and results to nothing so we can fill manually
        w.set_values({}, {})

        input_values = {
            "some_number": 64.0,
            "items_outer.0.attr.items_inner.0.path": 17.0,
            "items_outer.0.attr.items_inner.1.path": 18.0,
            "items_outer.1.attr.items_inner.0.path": 19.0,
            "items_outer.1.attr.items_inner.1.path": 20.0,
        }

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

        results_values = {
            "value": 11.0,
            "items_outer.1.value": 71.0,
            "items_outer.0.value": 49.0,
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

        # After adding last attribute the worker starts running (sequentially)
        test_results_ready = w.results_ready() == True

        with self.subTest():
            self.assertTrue(test_results_ready)

        with self.subTest():
            self.assertTrue(all(itests_paths_pending))

        with self.subTest():
            self.assertTrue(all(itests_ready_to_work))

        with self.subTest():
            self.assertTrue(all(rtests_paths_pending))

        with self.subTest():
            self.assertTrue(all(rtests_ready_to_work))

    def test_5(self):
        """
        Initialize worker with ILOC locations in
        query and ILOC wildcards in bindings
        """
        hmodel = None
        cname = None
        func = None
        version = None
        comp_yml = """
                    provides : 
                        - name: k_therm 
                          path: segments[IDX_SEG].layers[:@IDX_LAY].k_therm
                    consumes:
                        input:
                        - name: material
                          path: segments[IDX_SEG].layers[:@IDX_LAY].material
                    """
        comp_data = yaml.load(comp_yml, Loader=yaml.FullLoader)

        # Query something known to exist
        querystr = "segments[0].layers[0].k_therm"

        seg_node = shared.LengthNode(2)
        lay_nodes = shared.LengthNode(2), shared.LengthNode(2)
        seg_node.set_children(lay_nodes)
        nodes = [seg_node]
        nodes.extend(lay_nodes)
        level_names = "IDX_SEG", "IDX_LAY"
        tree = shared.LengthTree(nodes, level_names)
        tree_for_idxcontext = {tree.get_idx_context(): tree}

        querystr = shared.convert_to_internal_path(querystr)
        w = _Worker(
            self.manager,
            hmodel,
            cname,
            comp_data,
            querystr,
            func,
            version,
            tree_for_idxcontext,
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
            {"name": "k_therm", "path": "segments[IDX_SEG].layers[:@IDX_LAY].k_therm"}
        ]
        querystring = "segments[0].layers[0].k_therm"
        idxids = "IDX_SEG", "IDX_LAY"
        path_for_name, _ = _Worker.get_bindings(bindings, querystring)
        # This is what will be provided for the query: The attribute 'k_therm'
        # for all layers for the specific index ID _IDX=0
        # expected_path_for_name = {"k_therm": "segments.0.layers.:.k_therm"}
        expected_path_for_name = {"k_therm": "segments[0].layers[:@IDX_LAY].k_therm"}
        self.assertDictEqual(expected_path_for_name, path_for_name)

    def test_7(self):
        """Queries should be expanded (location specific)
        otherwise a HubitWorkerError is raised
        """
        provides = [
            {"name": "k_therm", "path": "segments[IDX_SEG].layers[:@IDX_LAY].k_therm"}
        ]
        querystring = "segments[0].layers[:].k_therm"
        idxids = "IDX_SEG", "IDX_LAY"
        with self.assertRaises(HubitWorkerError) as context:
            _Worker.get_bindings(provides, querystring)

    def test_8(self):
        """
        Test compression of indices. The query does not include any indices
        """
        hmodel = None
        cname = None
        func = None
        version = None
        comp_yml = """
                    provides:
                        - name: mylist
                          path: factors
                    consumes:
                        input: 
                          - name: factors
                            path: list[:@IDX1].some_attr.factors
                    """
        comp_data = yaml.load(comp_yml, Loader=yaml.FullLoader)

        # Query something known to exist
        querystr = "factors"
        idx1_node = shared.LengthNode(2)
        nodes = [idx1_node]
        level_names = ("IDX1",)
        tree = shared.LengthTree(nodes, level_names)
        dummy_tree = shared.DummyLengthTree()

        tree_for_idxcontext = {"": dummy_tree, tree.get_idx_context(): tree}

        querystr = shared.convert_to_internal_path(querystr)
        w = _Worker(
            self.manager,
            hmodel,
            cname,
            comp_data,
            querystr,
            func,
            version,
            tree_for_idxcontext,
            dryrun=True,
        )

    def test_bindings_from_idxs_0(self):
        """
        Substitute idxids with idxs
        """
        bindings = [{"name": "heat_flux", "path": "segments[IDX_SEG].heat_flux"}]

        idxval_for_idxid = {"IDX_SEG": "3"}
        path_for_name = _Worker.bindings_from_idxs(bindings, idxval_for_idxid)
        expected_path_for_name = {"heat_flux": "segments[3].heat_flux"}
        self.assertDictEqual(path_for_name, expected_path_for_name)

    def test_bindings_from_idxs_1(self):
        """
        Substitute idxids with idxs. Second index ID contains a wildcard
        and should be left as is
        """
        bindings = [
            {
                "name": "outer_temperature_all_layers",
                "path": "segments[IDX_SEG].layers[:@IDX_LAY].outer_temperature",
            },
        ]

        idxval_for_idxid = {"IDX_SEG": "0"}
        path_for_name = _Worker.bindings_from_idxs(bindings, idxval_for_idxid)
        expected_path_for_name = {
            "outer_temperature_all_layers": "segments[0].layers[:@IDX_LAY].outer_temperature"
        }
        self.assertDictEqual(path_for_name, expected_path_for_name)


if __name__ == "__main__":
    unittest.main()
