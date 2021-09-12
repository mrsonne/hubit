import unittest
import re
from hubit.config import (
    HubitModelComponent,
    _HubitPath,
    HubitModelPath,
    HubitQueryPath,
    ModelIndexSpecifier,
    FlatData,
    _HubitQueryDepthPath,
    Range,
)
from hubit.errors import HubitModelComponentError


class TestHubitComponent(unittest.TestCase):
    def test_provides_nothing(self):
        """
        Componet provides nothing => error
        """
        cfg = {
            "path": "dummy",
            "func_name": "dummy",
            "consumes_input": [{"name": "attr", "path": "shared.input.attr.path"}],
        }
        with self.assertRaises(HubitModelComponentError):
            HubitModelComponent.from_cfg(cfg, 0)


class TestHubitPath(unittest.TestCase):
    def test_from_dotted(self):
        """Convert dotted path to path object and back"""
        dotted_path_string = "hi.how.12.are.you.34"
        result = _HubitPath.from_dotted(dotted_path_string)
        expected_result = "hi.how[12].are.you[34]"
        self.assertEqual(result, expected_result)

        result = _HubitPath.as_internal(result)
        self.assertEqual(result, dotted_path_string)


class TestHubitQueryPath(unittest.TestCase):
    def test_validate_braces(self):
        path = HubitQueryPath("segments[0].layers[17]test.positions[44]")
        with self.assertRaises(AssertionError):
            path._validate_brackets()

    def test_balanced(self):
        path = "segments[0].layers[17]"
        result = HubitQueryPath.balanced(path)
        self.assertTrue(result)

        path = "segments[44].layers[76"
        result = HubitQueryPath.balanced(path)
        self.assertFalse(result)

    def test_validate_index_specifiers(self):
        path = HubitQueryPath("segments[44].layers[76]")
        path._validate_index_specifiers()

        path = HubitQueryPath("segments[:].layers[76]")
        path._validate_index_specifiers()

        path = HubitQueryPath("segments[hej].layers[76]")
        with self.assertRaises(AssertionError):
            path._validate_index_specifiers()

    def test_get_matches(self):
        """Test that we can find the provider strings
        that match the query
        """
        qpath = HubitQueryPath("segs[42].walls[3].temps")
        provides = HubitModelPath("segs[IDXSEG].walls[IDXWALL].temps")
        mpaths = (
            HubitModelPath("price"),
            provides,
            HubitModelPath("segs[IDXSEG].walls.thicknesses"),
            HubitModelPath(qpath),
            HubitModelPath("segs[IDXSEG].walls[IDXWALL].thicknesses"),
            HubitModelPath("segs[IDXSEG].walls[IDXWALL]"),
        )

        idxs_match_expected = (1, 3)
        idxs_match = qpath.idxs_for_matches(mpaths)
        self.assertSequenceEqual(idxs_match, idxs_match_expected)


class TestHubitModelPath(unittest.TestCase):
    def test_remove_braces(self):
        path = HubitModelPath("segs[:@IDX_SEG].walls[IDX_WALL].heat_flow")
        result = path.remove_braces()
        expected_result = "segs.walls.heat_flow"
        self.assertSequenceEqual(result, expected_result)

    def test_get_idx_context(self):
        path = HubitModelPath("segs[:@IDX_SEG].walls[IDX_WALL].heat_flow")
        result = path.get_idx_context()
        expected_result = "IDX_SEG-IDX_WALL"
        self.assertSequenceEqual(result, expected_result)

    def test_get_specifiers(self):
        """Extract idxspecs from path"""
        path = HubitModelPath("segs[:@IDX_SEG].walls[IDX_WALL].heat_flow")
        expected_idxids = [":@IDX_SEG", "IDX_WALL"]
        idxids = path.get_index_specifiers()
        self.assertSequenceEqual(expected_idxids, idxids)

    def test_get_identifiers(self):
        """Extract idxids from path"""
        path = HubitModelPath("segs[:@IDX_SEG].walls[IDX_WALL].heat_flow")
        expected_idxids = ["IDX_SEG", "IDX_WALL"]
        idxids = path.get_index_identifiers()
        self.assertSequenceEqual(expected_idxids, idxids)

    def test_set_indices(self):
        """Insert real numbers where the ILOC placeholder is found"""
        expected_pathstr = "segs[34].walls[3].temps"
        path = HubitModelPath("segs[IDXSEG].walls[IDXWALL].temps")
        new_path = path.set_indices(("34", "3"), mode=1)
        self.assertEqual(new_path, expected_pathstr)

    def test_set_ilocs_with_wildcard(self):
        """Insert real numbers where the ILOC placeholder is found"""
        expected_pathstr = "segs[34].walls[:@IDXWALL].temps"
        path = HubitModelPath("segs[IDXSEG].walls[:@IDXWALL].temps")
        new_path = path.set_indices(("34", "3"), mode=1)
        self.assertEqual(new_path, expected_pathstr)

    def test_set_ilocs_assertion_error(self):
        """Too many indices specified"""
        path = HubitModelPath("segs[IDXSEG].walls[:@IDXWALL].temps")
        with self.assertRaises(AssertionError):
            path.set_indices(("34", "3", "19"), mode=1)

    def test_as_internal(self):
        """Convert Hubit path to internal path"""
        path = "segs[IDX_SEG].walls[IDX_WALL].heat_flow"
        expected_internal_path = "segs.IDX_SEG.walls.IDX_WALL.heat_flow"
        internal_path = HubitModelPath.as_internal(path)
        self.assertSequenceEqual(expected_internal_path, internal_path)

    def test_as_internal_idx_wildcard(self):
        """Convert Hubit path to internal path"""
        path = "segs[:@IDX_SEG].walls[:@IDX_WALL].heat_flow"
        expected_internal_path = "segs.:@IDX_SEG.walls.:@IDX_WALL.heat_flow"
        internal_path = HubitModelPath.as_internal(path)
        self.assertSequenceEqual(expected_internal_path, internal_path)

    def test_paths_between_idxids(self):
        path = HubitModelPath(
            "segments[IDX_SEG].layers[IDX_LAY].test.positions[IDX_POS]"
        )
        idxids = path.get_index_specifiers()
        paths = path.paths_between_idxids(idxids)
        # Last element is empty since there are no attribute after IDX_POS
        expected_paths = ["segments", "layers", "test.positions", ""]
        self.assertSequenceEqual(expected_paths, paths)

    def test_paths_between_idxids_tailed(self):
        path = HubitModelPath(
            "segments[IDX_SEG].layers[IDX_LAY].test.positions[IDX_POS].attr"
        )
        idxids = path.get_index_specifiers()
        paths = path.paths_between_idxids(idxids)
        # Last element is empty since there are no attribute after IDX_POS
        expected_paths = ["segments", "layers", "test.positions", "attr"]
        self.assertSequenceEqual(expected_paths, paths)

    def test_validate_idxids(self):
        # Valid
        path = HubitModelPath("segments[IDX_SEG].layers[IDX_LAY]")
        path.validate()

        # Valid
        path = HubitModelPath("segments[IDX_SEG].layers[:@IDX_LAY]")
        path.validate()

        # Invalid due to negative index range
        path = HubitModelPath("segments[-1@IDX_SEG].layers[IDX_LAY]")
        with self.assertRaises(AssertionError):
            path.validate()

        # Only one @ allowed in index specifier
        path = HubitModelPath("segments[IDX_SEG].layers[:@@IDX_LAY]")
        with self.assertRaises(AssertionError):
            path._validate_index_specifiers()

        # Invalid character - in index identifier
        path = HubitModelPath("segments[IDX_SEG].layers[IDX-LAY]")
        with self.assertRaises(AssertionError):
            path.validate()

        # Invalid character - in index identifier
        path = HubitModelPath("segments[IDX_SEG].layers[:@IDX-LAY]")
        with self.assertRaises(AssertionError):
            path.validate()

        # Invalid character \ in index identifier
        path = HubitModelPath("segments[IDX_SEG].layers[:@IDX/LAY]")
        with self.assertRaises(AssertionError):
            path.validate()

        # Numbers allowed
        path = HubitModelPath("segments[IDX_SEG].layers[:@IDX1LAY113]")
        path.validate()

        path = HubitModelPath("segments[IDX_SEG].layers[@]")
        with self.assertRaises(AssertionError):
            path.validate()

    def test_as_query_depth_path(self):
        path = HubitModelPath("segments[IDX_SEG].layers[:@IDX1LAY113]")
        assert path.as_query_depth_path() == "segments[*].layers[*]"


class TestModelIndexSpecifier(unittest.TestCase):
    def test_mis(self):
        mis = ModelIndexSpecifier(":@IDX_LAY")
        assert mis.offset == 0
        assert mis.identifier == "IDX_LAY"
        assert mis.idx_range == ":"

        mis = ModelIndexSpecifier("IDX_LAY+1")
        assert mis.offset == 1
        assert mis.identifier == "IDX_LAY"
        assert mis.idx_range == ""

        mis = ModelIndexSpecifier("IDX_LAY-12")
        assert mis.offset == -12
        assert mis.identifier == "IDX_LAY"
        assert mis.idx_range == ""

        # cannot specify both range and offset
        mis = ModelIndexSpecifier("2@IDX_LAY-12")
        assert mis._validate_cross() == False

        # cannot specify both range and offset
        mis = ModelIndexSpecifier(":@IDX_LAY-12")
        assert mis._validate_cross() == False

        # incomplete range specification
        mis = ModelIndexSpecifier("@IDX_LAY-12")
        with self.assertRaises(AssertionError) as cm:
            mis.validate()
        print(cm.exception)


class TestRange(unittest.TestCase):
    def test_range_type(self):
        range = Range("2")
        assert range.is_digit
        assert not range.is_limited_range
        assert not range.is_full_range

        range = Range("2:")
        assert not range.is_digit
        assert range.is_limited_range
        assert not range.is_full_range

        range = Range(":2")
        assert not range.is_digit
        assert range.is_limited_range
        assert not range.is_full_range

        range = Range("2:4")
        assert not range.is_digit
        assert range.is_limited_range
        assert not range.is_full_range

        range = Range(":")
        assert not range.is_digit
        assert not range.is_limited_range
        assert range.is_full_range

    def test_range_contains(self):
        range = Range("2")
        assert not range.contains_index(1)
        assert range.contains_index(2)
        assert not range.contains_index(3)

        range = Range("2:")
        assert not range.contains_index(1)
        assert range.contains_index(2)
        assert range.contains_index(3)

        range = Range(":2")
        assert range.contains_index(1)
        assert not range.contains_index(2)
        assert not range.contains_index(3)

        range = Range("2:4")
        assert not range.contains_index(1)
        assert range.contains_index(2)
        assert range.contains_index(3)
        assert not range.contains_index(4)

        range = Range(":")
        assert range.contains_index(1)
        assert range.contains_index(2)
        assert range.contains_index(3)


class TestFlatData(unittest.TestCase):
    def test_from_dict(self):
        """
        Test nested dict
        """
        data = {"level1": {"level2": [{"attr1": 1}, {"attr2": 2}]}, "number": 3}
        result = FlatData.from_dict(
            data, include_patterns=["level1.level2.attr1", "level1.level2.attr2"]
        )
        expected_result = {
            "level1.level2[0].attr1": 1,
            "level1.level2[1].attr2": 2,
        }

        self.assertTrue(all([isinstance(key, HubitQueryPath) for key in result.keys()]))

        assert result == expected_result

    def test_from_dict_with_simple_list(self):
        """
        Test flattening of simple list
        """
        data = {"list": [1, 2, 3], "level0": {"list": [1, 2, 3]}}
        result = FlatData.from_dict(data, include_patterns=["list", "level0.list"])
        expected_result = {
            "list[0]": 1,
            "list[1]": 2,
            "list[2]": 3,
            "level0.list[0]": 1,
            "level0.list[1]": 2,
            "level0.list[2]": 3,
        }
        assert result == expected_result

    def test_from_dict_stop_at_level0(self):
        """
        Test stop at root level
        """
        data = {"level0": {"level1": [{"attr1": 1}, {"attr2": 2}]}, "number": 3}
        result = FlatData.from_dict(
            data,
            stop_at=[re.compile("level0")],
            include_patterns=["level0", "number"],
        )
        expected_result = data
        assert result == expected_result

    def test_from_dict_stop_at_level1(self):
        """
        Test stop at level 1
        """
        data = {"level0": {"level1": [{"attr1": 1}, {"attr2": 2}]}, "number": 3}
        include_path = "level0.level1"
        result = FlatData.from_dict(
            data, stop_at=[re.compile(include_path)], include_patterns=[include_path]
        )
        expected_result = {
            "level0.level1": [{"attr1": 1}, {"attr2": 2}],
        }
        print(result)

        assert result == expected_result

    def test_from_dict_stop_at_level0_a(self):
        """
        Test stop at level0. level1 also specified but is preceded
        by level0
        """
        data = {"level0": {"level1": [{"attr1": 1}, {"attr2": 2}]}, "number": 3}
        include_path = "level0"
        result = FlatData.from_dict(
            data,
            stop_at=[re.compile(include_path)],
            include_patterns=[include_path, "number"],
        )
        expected_result = data
        assert result == expected_result

    def test_from_dict_stop_at_level1_list(self):
        """
        Test stop at root level
        """
        data = {
            "level0": [{"level1": [1, 2, 3, 4], "ff": 4}, {"level1": [2, 5], "gg": 5}],
            "number": 3,
        }
        spec = _HubitQueryDepthPath("level0[*].level1")
        specs = [spec.compile_regex()]
        result = FlatData.from_dict(
            data,
            stop_at=specs,
            include_patterns=["level0.level1", "level0.ff", "level0.gg", "number"],
        )
        print(result)
        expected_result = {
            "level0[0].level1": [1, 2, 3, 4],
            "level0[0].ff": 4,
            "level0[1].level1": [2, 5],
            "level0[1].gg": 5,
            "number": 3,
        }

        assert result == expected_result

    def test_include(self):
        key = "list1.1.list2.3"
        includes = "list1.list2", "ok"
        result = FlatData._include(key, includes)
        expected_result = True
        assert result == expected_result

        includes = "list1", "ok"
        result = FlatData._include(key, includes)
        expected_result = False
        assert result == expected_result
