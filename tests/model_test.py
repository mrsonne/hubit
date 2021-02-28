import unittest
import os
import pathlib
import yaml

from hubit.errors import HubitModelNoInputError, HubitModelQueryError

from hubit import HubitModel
from hubit.shared import convert_to_internal_path, inflate

yml_input = None
model = None

THIS_DIR = os.path.dirname(os.path.realpath(__file__))
REL_TMP_DIR = "./tmp"
TMP_DIR = os.path.join(THIS_DIR, REL_TMP_DIR)
pathlib.Path(TMP_DIR).mkdir(parents=True, exist_ok=True)


def setUpModule():
    global yml_input
    global model
    from tests.shared_data import model as model
    from tests.shared_data import yml_input as yml_input


def level0_results_at_idx(input, idx):
    fact = 2.0
    return [fact * x for x in input["list"][idx]["some_attr"]["numbers"]]


def level1_results_at_idx(input, idx):
    level0_fact = 2.0
    return [
        level0_fact * level1_fact * number
        for number, level1_fact in zip(
            input["list"][idx]["some_attr"]["numbers"],
            input["list"][idx]["some_attr"]["factors"],
        )
    ]


class TestModel(unittest.TestCase):
    def setUp(self):
        modelname = "Test model"
        model_data = yaml.load(model, Loader=yaml.FullLoader)
        self.hmodel = HubitModel(
            model_data, name=modelname, base_path=THIS_DIR, output_path=REL_TMP_DIR
        )
        self.input = yaml.load(yml_input, Loader=yaml.FullLoader)
        self.use_multi_processing_values = False, True

        # Query which does not consume results
        self.idx = 1
        self.querystr_level0 = "list[{}].some_attr.two_x_numbers".format(self.idx)
        self.expected_result_level0 = level0_results_at_idx(self.input, self.idx)

        self.querystr_level1 = "list[{}].some_attr.two_x_numbers_x_factor".format(
            self.idx
        )

        self.querystr_level0_slice = "list[:].some_attr.two_x_numbers"
        self.expected_result_level0_slice = [
            level0_results_at_idx(self.input, 0),
            level0_results_at_idx(self.input, 1),
        ]

        self.querystr_level0_last = "list[-1].some_attr.two_x_numbers"

    def test_from_file(self):
        """
        Test if model can successfully be loaded from a file
        """
        fpath = os.path.join(TMP_DIR, "model.yml")
        with open(fpath, "w") as handle:
            yaml.dump(
                yaml.load(model, Loader=yaml.FullLoader),
                handle,
                default_flow_style=False,
            )
        HubitModel.from_file(fpath)
        self.assertTrue(True)

    def test_validate(self):
        """
        Model validation
        """
        self.assertTrue(self.hmodel.validate())

    def test_validate_query_first_element(self):
        """
        Validate query for first list element
        """
        self.hmodel.set_input(self.input)
        queries = [self.querystr_level0]
        is_ok = self.hmodel.validate(queries)
        self.assertTrue(is_ok)

    def test_validate_query_all_elements(self):
        """
        Validate query for all list element
        """
        self.hmodel.set_input(self.input)
        queries = [self.querystr_level0_slice]
        is_ok = self.hmodel.validate(queries)
        self.assertTrue(is_ok)

    def test_validate_query_last_element(self):
        """
        Validate query for last list element.
        """
        self.skipTest("Catch22 in normalize, prune, expand")
        self.hmodel.set_input(self.input)
        queries = [self.querystr_level0_last]
        is_ok = self.hmodel.validate(queries)

    def test_render_model(self):
        """
        Test that rendering the model does not raise an exception
        TODO: could test the dot object instead
        """
        self.hmodel.render()

    def test_render_query_fail(self):
        """
        Render the query, but not input.
        """
        queries = ["list.1.some_attr.two_x_numbers"]

        # ModuleNotFoundError raised if graphviz is not installed
        with self.assertRaises(HubitModelNoInputError) as context:
            self.hmodel.render(queries)

    def test_render_query(self):
        """
        Render the query
        TODO: could test the dot object instead
        Sometimes (?!?!) gives this warning:
        Warning: _Query -> cluster_resultslist: head not inside head cluster cluster_results
        Warning: cluster_resultslist -> _Response: tail not inside tail cluster cluster_results
        """
        self.hmodel.set_input(self.input)
        queries = [self.querystr_level0]
        self.hmodel.render(queries)

    def test_get_fail_no_input(self):
        """
        Simple request with no input. Fails
        """
        queries = [self.querystr_level0]

        def test():
            with self.assertRaises(HubitModelNoInputError) as context:
                self.hmodel.get(queries, use_multi_processing=use_multi_processing)

        for use_multi_processing in self.use_multi_processing_values:
            with self.subTest(use_multi_processing=use_multi_processing):
                test()

    def test_get_fail_query_error(self):
        """
        Simple request with no input. Fails
        """
        self.hmodel.set_input(self.input)
        queries = ["list.1.some_attr.i_dont_exist"]

        def test():
            with self.assertRaises(HubitModelQueryError) as context:
                self.hmodel.get(queries, use_multi_processing=use_multi_processing)

        for use_multi_processing in self.use_multi_processing_values:
            with self.subTest(use_multi_processing=use_multi_processing):
                test()

    def test_get_level0(self):
        """
        Level 0 query (no dependencies)
        """
        self.hmodel.set_input(self.input)

        queries = [self.querystr_level0]

        def test():
            response = self.hmodel.get(
                queries, use_multi_processing=use_multi_processing, validate=False
            )

            self.assertSequenceEqual(
                response[self.querystr_level0], self.expected_result_level0
            )

        for use_multi_processing in self.use_multi_processing_values:
            with self.subTest(use_multi_processing=use_multi_processing):
                test()

    def test_get_level1(self):
        """
        Level 1 query (one dependency)
        """
        self.hmodel.set_input(self.input)
        queries = [self.querystr_level1]

        def test():
            response = self.hmodel.get(
                queries, use_multi_processing=use_multi_processing, validate=True
            )
            self.assertSequenceEqual(
                response[self.querystr_level1], level1_results_at_idx(self.input, 1)
            )

        for use_multi_processing in self.use_multi_processing_values:
            with self.subTest(use_multi_processing=use_multi_processing):
                test()

    def test_comsume_2_idxids(self):
        """Level 1 fixed, level 2 fixed"""
        use_multi_processing = False
        self.hmodel.set_input(self.input)
        response = self.hmodel.get(
            ["first_coor[0].second_coor[0].value"],
            use_multi_processing=use_multi_processing,
            validate=False,
        )
        expected_response = {"first_coor[0].second_coor[0].value": 1.0}
        self.assertDictEqual(response, expected_response)

    def test_comsume_2_idxids_idxwc(self):
        """Level 1 fixed, index wildcard on level 2"""
        use_multi_processing = False
        self.hmodel.set_input(self.input)
        response = self.hmodel.get(
            ["first_coor[0].second_coor[:].value"],
            use_multi_processing=use_multi_processing,
            validate=False,
        )
        expected_response = {"first_coor[0].second_coor[:].value": [1.0, 2.0]}
        self.assertDictEqual(response, expected_response)

    def test_comsume_2_idxids_idxwc_a(self):
        """Index wildcard on level 1. Level 2 fixed"""
        use_multi_processing = False
        self.hmodel.set_input(self.input)
        response = self.hmodel.get(
            ["first_coor[:].second_coor[0].value"],
            use_multi_processing=use_multi_processing,
            validate=False,
        )
        expected_response = {"first_coor[:].second_coor[0].value": [1.0, 3.0]}
        self.assertDictEqual(response, expected_response)

    def test_comsume_2_idxids_2_idxwc(self):
        """Level 1 fixed, index wildcard on level 2"""
        use_multi_processing = False
        self.hmodel.set_input(self.input)
        response = self.hmodel.get(
            ["first_coor[:].second_coor[:].value"],
            use_multi_processing=use_multi_processing,
            validate=False,
        )
        expected_response = {
            "first_coor[:].second_coor[:].value": [[1.0, 2.0], [3.0, 4.0]]
        }
        self.assertDictEqual(response, expected_response)

    def test_get_slice(self):
        """
        Query all list element
        """
        self.hmodel.set_input(self.input)
        queries = [self.querystr_level0_slice]

        def test():
            response = self.hmodel.get(
                queries, use_multi_processing=use_multi_processing, validate=True
            )
            self.assertSequenceEqual(
                response[self.querystr_level0_slice], self.expected_result_level0_slice
            )

        for use_multi_processing in self.use_multi_processing_values:
            with self.subTest(use_multi_processing=use_multi_processing):
                test()

    def test_get_last(self):
        """
        Query last list element
        """
        self.skipTest("Catch22 in normalize, prune, expand")
        self.hmodel.set_input(self.input)
        queries = [self.querystr_level0_last]
        for use_multi_processing in self.use_multi_processing_values:
            with self.subTest(use_multi_processing=use_multi_processing):
                response = self.hmodel.get(
                    queries, use_multi_processing=use_multi_processing
                )
                self.assertSequenceEqual(
                    response[self.querystr_level0_last], self.expected_result_level0
                )

    def test_get_all(self):
        """
        No query yields all results
        """
        self.skipTest("Not implemented")
        self.hmodel.set_input(self.input)
        for use_multi_processing in self.use_multi_processing_values:
            with self.subTest(use_multi_processing=use_multi_processing):
                response = self.hmodel.get(use_multi_processing=use_multi_processing)
                print(response)

    def test_sweep(self):
        """
        Sweep input parameters
        """
        # self.skipTest('TODO. Works but not with other test?!?!?')
        idx = 1
        # TODO change this
        path = "list[{}].some_attr.numbers".format(idx)
        ipath = convert_to_internal_path(path)
        input_values_for_path = {
            path: ([1.0, 2.0, 3.0], [4.0, 5.0, 6.0]),
        }
        self.hmodel.set_input(self.input)
        queries = [self.querystr_level0]
        responses, inps, _ = self.hmodel.get_many(queries, input_values_for_path)

        expected_results = []
        calc_responses = []
        for flat_inp, response in zip(inps, responses):
            inp = inflate(flat_inp)
            expected_results.append(level0_results_at_idx(inp, idx))
            calc_responses.append(response[self.querystr_level0])

        for idx, flat_inp in enumerate(inps):
            with self.subTest():
                self.assertListEqual(flat_inp[ipath], input_values_for_path[path][idx])

        with self.subTest():
            self.assertSequenceEqual(calc_responses, expected_results)

    if __name__ == "__main__":
        unittest.main()
