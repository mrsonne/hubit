import os
import unittest
import yaml

from hubit.model import HubitModel
from hubit.qrun import _QueryRunner
from hubit.errors import HubitModelQueryError
from hubit.config import FlatData, HubitModelConfig, HubitQueryPath

THIS_FILE = os.path.realpath(__file__)
THIS_DIR = os.path.dirname(THIS_FILE)
REL_TMP_DIR = "./tmp"


def setUpModule():
    global yml_input
    global model
    from tests.shared_data import model as model
    from tests.shared_data import yml_input as yml_input


def subscriptions_for_query(query, query_runner):
    """Get subscriptions from worker"""
    w = query_runner._worker_for_query(query)
    consumes = list(w.ipath_consumed_for_name.values())
    consumes += list(w.rpath_consumed_for_name.values())
    provides = list(w.rpath_provided_for_name.values())
    return consumes, provides


def subscriptions_for_component_idx(model_cfg, comp_idx, iloc, idxid):
    """Get subscriptions from model"""
    ilocstr = str(iloc)

    consumes = []
    try:
        consumes.extend(
            [binding.path for binding in model_cfg.components[comp_idx].consumes_input]
        )
    except KeyError:
        pass

    try:
        consumes.extend(
            [
                binding.path
                for binding in model_cfg.components[comp_idx].consumes_results
            ]
        )
    except KeyError:
        pass

    # Replace ilocstr with actual iloc
    consumes = [path.replace(idxid, f"{ilocstr}@{idxid}") for path in consumes]

    provides = [
        binding.path for binding in model_cfg.components[comp_idx].provides_results
    ]
    provides = [path.replace(idxid, f"{ilocstr}@{idxid}") for path in provides]

    return consumes, provides


class TestRunner(unittest.TestCase):
    def setUp(self):

        cfg = yaml.load(model, Loader=yaml.FullLoader)
        self.model_cfg = HubitModelConfig.from_cfg(cfg, base_path=THIS_DIR)
        self.hmodel = HubitModel(
            self.model_cfg,
            name="My model",
            output_path=REL_TMP_DIR,
        )
        use_multi_processing = False
        self.qr = _QueryRunner(self.hmodel, use_multi_processing)
        self.input = yaml.load(yml_input, Loader=yaml.FullLoader)
        self.hmodel.set_input(self.input)

        # Query which does not consume results
        self.idx = 1
        self.querystr_level0 = HubitQueryPath(
            "list[{}].some_attr.two_x_numbers".format(self.idx)
        )
        self.querystr_level1 = HubitQueryPath(
            "list[{}].some_attr.two_x_numbers_x_factor".format(self.idx)
        )

    def test_worker_comp1(self):
        """ """
        # Component index in model (TODO: brittle)'
        comp_idx = 1
        qstr = self.querystr_level0

        (worker_consumes, worker_provides) = subscriptions_for_query(qstr, self.qr)
        (
            worker_consumes_expected,
            worker_provides_expected,
        ) = subscriptions_for_component_idx(
            self.model_cfg, comp_idx, self.idx, idxid="IDX1"
        )

        test_consumes = set(worker_consumes) == set(worker_consumes_expected)
        self.assertTrue(test_consumes)
        test_provides = set(worker_provides) == set(worker_provides_expected)
        self.assertTrue(test_provides)

    def test_worker_comp2(self):
        """ """
        # Component index in model
        comp_idx = 2
        qstr = self.querystr_level1

        (worker_consumes, worker_provides) = subscriptions_for_query(qstr, self.qr)

        (
            worker_consumes_expected,
            worker_provides_expected,
        ) = subscriptions_for_component_idx(
            self.model_cfg, comp_idx, self.idx, idxid="IDX1"
        )

        test_consumes = set(worker_consumes) == set(worker_consumes_expected)
        self.assertTrue(test_consumes)

        test_provides = set(worker_provides) == set(worker_provides_expected)
        self.assertTrue(test_provides)

    def test_no_provider(self):
        """
        No provider for query since the query has not provider.
        """
        with self.assertRaises(HubitModelQueryError):
            self.qr._worker_for_query(HubitQueryPath("i.dont.exist"))

    def get_worker_counts(self, queries):
        flat_results = FlatData()
        flat_input = FlatData.from_dict(
            self.input,
            stop_at=self.model_cfg.compiled_query_depths,
            include_patterns=self.model_cfg.include_patterns,
        )
        worker_counts = []
        for qpaths in queries:
            self.qr.spawn_workers(
                qpaths, flat_input, flat_results, flat_input, dryrun=True
            )
            worker_counts.append(len(self.qr.workers))

        return worker_counts

    def test_number_of_workers_level0(self):
        """Test number of workers on level 0 quries ie queries
        that have no dependencies
        """
        queries = [[self.querystr_level0]]

        # Level 0 worker on specific index yields 1 worker
        expected_worker_counts = [1]
        worker_counts = self.get_worker_counts(queries)
        self.assertListEqual(worker_counts, expected_worker_counts)

    def test_number_of_workers_level1(self):
        """Test number of workers on level 1 queries i.e. queries
        that have one dependency
        """
        queries = [(self.querystr_level1,)]

        # Level 1 worker on specific index yields 2 workers - one for level 0 and one for level 1
        expected_worker_counts = [2]
        worker_counts = self.get_worker_counts(queries)
        self.assertListEqual(worker_counts, expected_worker_counts)

    def test_number_of_workers_composite(self):
        """Test composite queries"""
        queries = [(self.querystr_level0, self.querystr_level1)]

        # Level 1 query requires the level 0 attr so self.querystr_level0 is superfluous
        expected_worker_counts = [2]
        worker_counts = self.get_worker_counts(queries)
        self.assertListEqual(worker_counts, expected_worker_counts)

    def test_number_of_workers_slicing(self):
        """[summary]"""
        queries = [(HubitQueryPath("factors"),)]
        worker_counts = self.get_worker_counts(queries)
        expected_worker_counts = [1]
        self.assertListEqual(worker_counts, expected_worker_counts)

    def test_number_of_workers_multiple_levels(self):
        """Query level-1 attribute. Should deploy 2 level-0 workers
        and 2 level-1 workers.
        """
        queries = [
            (
                HubitQueryPath("list[0].some_attr.two_x_numbers_x_factor"),
                HubitQueryPath("list[1].some_attr.two_x_numbers_x_factor"),
            )
        ]
        worker_counts = self.get_worker_counts(queries)
        expected_worker_counts = [4]
        self.assertListEqual(worker_counts, expected_worker_counts)

    def test_number_of_workers_case6(self):
        """Query multiple attributes that are actually supplied by the
        same component. Therefore, only one worker should be deployed.
        """
        queries = [
            [
                HubitQueryPath("list[0].some_attr.inner_list[0].yval"),
                HubitQueryPath("list[0].some_attr.inner_list[1].yval"),
            ]
        ]

        worker_counts = self.get_worker_counts(queries)
        expected_worker_counts = [1]
        self.assertListEqual(worker_counts, expected_worker_counts)

    if __name__ == "__main__":
        unittest.main()
