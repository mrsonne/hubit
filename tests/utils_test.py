import unittest
import re
from hubit.utils import get_from_datadict, traverse, set_element


class TestUtils(unittest.TestCase):
    def test_get_from_datadict(self):
        """Extract value from nested dict using a list of keys."""
        datadict = {"a": {"b": [4, 5]}}
        # Should all be of type string
        keys = ["a", "b", "0"]
        value = get_from_datadict(datadict, keys)
        self.assertTrue(value == 4)

    def test_traverse(self):
        """Test iterator that traverses nested list"""
        l0 = "as", "fv", "dsd", ["fr", "hj", ["gb", 0]]
        self.assertTrue(len(list(traverse(l0))) == 7)

        paths = [["attr1", "attr2"], ["attr3", "attr4"]]
        valuemap = {"attr1": 1, "attr2": 2, "attr3": 3, "attr4": 4}

    def test_set_element_1d(self):
        data = [None, None, None]
        indices = (1,)
        value = 17.0
        result = set_element(data, value, indices)
        expected_result = [None, 17.0, None]
        self.assertListEqual(result, expected_result)

    def test_set_element_2d(self):
        data = [[None, None, None], [None, None]]
        indices = 0, 2
        value = 17.0
        result = set_element(data, value, indices)
        expected_result = [[None, None, 17.0], [None, None]]
        self.assertListEqual(result, expected_result)
