import unittest
import pytest
import pathlib
import yaml
import re
from hubit.config import (
    HubitBinding,
    HubitModelComponent,
    _HubitPath,
    HubitModelPath,
    HubitQueryPath,
    ModelIndexSpecifier,
    HubitModelConfig,
    FlatData,
    _HubitQueryDepthPath,
    PathIndexRange,
    PathIndexRange,
)
from hubit.errors import HubitModelComponentError, HubitError

THIS_DIR = pathlib.Path(__file__).parent


class TestHubitModelConfig(unittest.TestCase):
    def test_duplicate_providers(self):
        model = """
        components:
            - func_name: move_number
              path: ./components/comp0.py 
              provides_results:
                - name: number
                  path: first_coor[IDX1].second_coor[IDX2].value 
            - func_name: multiply_by_2
              path: ./components/comp1.py 
              provides_results: 
                - name: number
                  path: first_coor[IDX1].second_coor[IDX2].value 
          """
        with pytest.raises(HubitError):
            HubitModelConfig.from_cfg(
                yaml.load(model, Loader=yaml.FullLoader), base_path=THIS_DIR
            )


class TestHubitBinding(unittest.TestCase):
    def test_from_cfg(self):
        # Index range is full range
        cfg = {
            "name": "attr",
            "path": "segments[IDX_SEG].layers[:@IDX_LAY]",
        }
        HubitBinding.from_cfg(cfg)

        # Index range is digit
        cfg = {
            "name": "attr",
            "path": "segments[IDX_SEG].layers[0@IDX_LAY]",
        }
        HubitBinding.from_cfg(cfg)

        # Index range is limited
        cfg = {
            "name": "attr",
            "path": "segments[IDX_SEG].layers[0:12@IDX_LAY]",
        }
        with self.assertRaises(HubitError):
            HubitBinding.from_cfg(cfg)


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

    def test_names_reused(self):
        """
        Names shared between
        """
        cfg = {
            "path": "dummy",
            "func_name": "dummy",
            "provides_results": [{"name": "attr", "path": "shared.input.attr.path3"}],
            "consumes_input": [{"name": "attr", "path": "shared.input.attr.path1"}],
            "consumes_results": [{"name": "attr", "path": "shared.input.attr.path2"}],
        }
        with self.assertRaises(AssertionError):
            HubitModelComponent.from_cfg(cfg, 0)

    def test_circular_refs(self):
        cfg = {
            "path": "dummy",
            "func_name": "dummy",
            "provides_results": [{"name": "attr", "path": "shared.input.attr.path"}],
            "consumes_results": [{"name": "attr", "path": "shared.input.attr.path"}],
        }
        with self.assertRaises(AssertionError):
            HubitModelComponent.from_cfg(cfg, 0)

    def test_invalid_scope(self):

        # Multiple scopes not allowed
        cfg = {
            "path": "dummy",
            "func_name": "dummy",
            "index_scope": {"IDX1": "1:", "IDX2": ":"},
            "provides_results": [{"name": "attr", "path": "shared.input.attr.path1"}],
            "consumes_results": [{"name": "attr", "path": "shared.input.attr.path2"}],
        }
        with self.assertRaises(AssertionError):
            HubitModelComponent.from_cfg(cfg, 0)

        # Scope has invalid range
        cfg = {
            "path": "dummy",
            "func_name": "dummy",
            "index_scope": {"IDX": "1:chars"},
            "provides_results": [{"name": "attr", "path": "shared.input.attr.path1"}],
            "consumes_results": [{"name": "attr", "path": "shared.input.attr.path2"}],
        }
        with self.assertRaises(HubitError):
            HubitModelComponent.from_cfg(cfg, 0)

    def test_validate_scope(self):
        """
        The scope is validated.

        TODO: Separate validation or make it optional to mak the test more specific
        """
        cfg = {
            "path": "dummy",
            "func_name": "dummy",
            "provides_results": [
                {"name": "attr", "path": "list[IDX].attr.path1"},
                {"name": "attr", "path": "list[IDX-1].attr.path2"},
            ],
        }

        # No scope
        HubitModelComponent.from_cfg(cfg, 0)

        # Add various scopes
        cfg.update({"index_scope": {"IDX": "1"}})
        HubitModelComponent.from_cfg(cfg, 0)

        cfg.update({"index_scope": {"IDX": "1:4"}})
        HubitModelComponent.from_cfg(cfg, 0)

        cfg.update({"index_scope": {"IDX": ":"}})
        HubitModelComponent.from_cfg(cfg, 0)

        # Component with explicit index reference
        cfg = {
            "path": "dummy",
            "func_name": "dummy",
            "provides_results": [
                {"name": "attr", "path": "list[2@IDX].attr.path1"},
            ],
        }

        # Add various scopes
        cfg.update({"index_scope": {"IDX": "2"}})
        HubitModelComponent.from_cfg(cfg, 0)

        cfg.update({"index_scope": {"IDX": "1:4"}})
        HubitModelComponent.from_cfg(cfg, 0)

        cfg.update({"index_scope": {"IDX": ":"}})
        HubitModelComponent.from_cfg(cfg, 0)

        # Component with index wildcard
        cfg = {
            "path": "dummy",
            "func_name": "dummy",
            "provides_results": [
                {"name": "attr", "path": "list[:@IDX].attr.path2"},
            ],
        }

        # Add various scopes
        cfg.update({"index_scope": {"IDX": "2"}})
        with pytest.raises(HubitModelComponentError):
            HubitModelComponent.from_cfg(cfg, 0)

        cfg.update({"index_scope": {"IDX": "1:4"}})
        with pytest.raises(HubitModelComponentError):
            HubitModelComponent.from_cfg(cfg, 0)

        cfg.update({"index_scope": {"IDX": ":"}})
        HubitModelComponent.from_cfg(cfg, 0)

    def test_get_paths(self):
        cfg = {
            "path": "dummy",
            "func_name": "dummy",
            "provides_results": [
                {"name": "attr", "path": "list[IDX].attr.path2"},
            ],
            "consumes_input": [
                {"name": "attr1", "path": "shared.input.attr.path1"},
                {"name": "attr2", "path": "shared.input.attr.path2"},
            ],
            "consumes_results": [
                {"name": "attr3", "path": "shared.input.attr.path3"},
                {"name": "attr4", "path": "shared.input.attr.path4"},
            ],
        }

        cmp = HubitModelComponent.from_cfg(cfg, 0)
        result = set(cmp.consumes_input_paths)
        expected_result = set(
            [
                HubitModelPath("shared.input.attr.path1"),
                HubitModelPath("shared.input.attr.path2"),
            ]
        )
        assert result == expected_result

        result = set(cmp.consumes_results_paths)
        expected_result = set(
            [
                HubitModelPath("shared.input.attr.path3"),
                HubitModelPath("shared.input.attr.path4"),
            ]
        )
        assert result == expected_result

        result = set(cmp.provides_results_paths)
        expected_result = set(
            [
                HubitModelPath("list[IDX].attr.path2"),
            ]
        )
        assert result == expected_result

    def test_scope_start(self):
        cfg = {
            "path": "dummy",
            "func_name": "dummy",
            "provides_results": [
                {"name": "attr", "path": "list[IDX].attr.path2"},
            ],
        }

        # No scope
        cmp = HubitModelComponent.from_cfg(cfg, 0)
        assert cmp.scope_start == (None, None)

        # All slice
        cfg.update({"index_scope": {"IDX": "1:4"}})
        cmp = HubitModelComponent.from_cfg(cfg, 0)
        assert cmp.scope_start == ("IDX", 1)

        # All indices
        cfg.update({"index_scope": {"IDX": ":"}})
        cmp = HubitModelComponent.from_cfg(cfg, 0)
        assert cmp.scope_start == ("IDX", 0)


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
    def test_has_slice_range(self):
        path = HubitQueryPath("hi.how.2.you")
        assert path.has_slice_range() == False

        path = HubitQueryPath("hi.how[2].are.you")
        assert path.has_slice_range() == False

        path = HubitQueryPath("hi.how[:].are.you")
        assert path.has_slice_range() == True

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

        path = "segments]44[.layers[76"
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

        # limited ranges not allowed
        path = HubitQueryPath("segments[12:44].layers[76]")
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

    def test_path_match(self):
        # Match
        qpath = HubitQueryPath("segs[42].walls[3].temps")
        mpath = HubitModelPath("segs[IDX1].walls[IDX1].temps")
        assert qpath.path_match(mpath)

        # Match
        mpath = HubitModelPath("segs[:@IDX1].walls[IDX1].temps")
        assert qpath.path_match(mpath)

        # No match: different field names
        mpath = HubitModelPath("seg[:@IDX1].wall[IDX1].temp")
        assert not qpath.path_match(mpath)

        # No match: different field count
        qpath = HubitQueryPath("segs[42].walls[3].temps")
        mpath = HubitModelPath("segs[IDX1].walls[IDX1]")
        assert not qpath.path_match(mpath)

        # No match: different brace count
        qpath = HubitQueryPath("segs[42].walls[3].temps")
        mpath = HubitModelPath("segs.walls[IDX1].temps")
        assert not qpath.path_match(mpath)

        # No match: no intersection for second index
        qpath = HubitQueryPath("segs[42].walls[3].temps")
        mpath = HubitModelPath("segs[IDX1].walls[43@IDX2].temps")
        assert not qpath.path_match(mpath)

        ### Negative index in query
        # Match: negative index in query
        qpath = HubitQueryPath("segs[42].walls[-1].temps")
        mpath = HubitModelPath("segs[IDX1].walls[IDX1].temps")
        assert qpath.path_match(mpath)

        # Match: negative index in query
        mpath = HubitModelPath("segs[IDX1].walls[:@IDX1].temps")
        assert qpath.path_match(mpath)

        # No match: negative index in query. Index 12 might be the last index, i.e. math -1 but we cannot guarantee it
        mpath = HubitModelPath("segs[IDX1].walls[12@IDX1].temps")
        assert not qpath.path_match(mpath)

    def test_new_with_index(self):
        # Replace only first occurrence
        path = HubitModelPath("segments[1].lay1ers[1]")
        path = path.new_with_index("1", "11")
        assert path == HubitModelPath("segments[11].lay1ers[1]")

        # Do not change a match in the field name (1 in lay1ers)
        path = HubitModelPath("segments[2].lay1ers[1]")
        path = path.new_with_index("1", "11")
        print(path)
        assert path == HubitModelPath("segments[2].lay1ers[11]")


class TestHubitModelPath(unittest.TestCase):
    def test_has_slice_range(self):
        path = HubitModelPath("hi.how.are.you")
        assert path.has_slice_range() == False

        path = HubitModelPath("hi.how[IDX].are.you")
        assert path.has_slice_range() == False

        path = HubitModelPath("hi.how[2@IDX].are.you")
        assert path.has_slice_range() == False

        path = HubitModelPath("hi.how[:@IDX].are.you")
        assert path.has_slice_range() == True

    def test_set_range_for_idxid(self):
        path = HubitModelPath("segs[:@IDX_SEG].walls[IDX_WALL].heat_flow")
        result = path.set_range_for_idxid({"IDX_SEG": "2"})
        expected_result = HubitModelPath("segs[2@IDX_SEG].walls[IDX_WALL].heat_flow")
        self.assertEqual(result, expected_result)

    def test_remove_braces(self):
        path = HubitModelPath("segs[:@IDX_SEG].walls[IDX_WALL].heat_flow")
        result = path.remove_braces()
        expected_result = "segs.walls.heat_flow"
        self.assertEqual(result, expected_result)

        result = path.field_names()
        expected_result = ["segs", "walls", "heat_flow"]
        self.assertSequenceEqual(result, expected_result)

    def test_get_idx_context(self):
        path = HubitModelPath("segs[:@IDX_SEG].walls[IDX_WALL].heat_flow")
        result = path.index_context
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

    def test_paths_between_specifiers(self):
        path = HubitModelPath(
            "segments[IDX_SEG].layers[IDX_LAY].test.positions[IDX_POS]"
        )
        paths = path.paths_between_specifiers()
        # Last element is empty since there are no attribute after IDX_POS
        expected_paths = ["segments", "layers", "test.positions", ""]
        self.assertSequenceEqual(expected_paths, paths)

    def test_paths_between_specifiers_tailed(self):
        path = HubitModelPath(
            "segments[IDX_SEG].layers[IDX_LAY].test.positions[IDX_POS].attr"
        )
        paths = path.paths_between_specifiers()
        # Last element is empty since there are no attribute after IDX_POS
        expected_paths = ["segments", "layers", "test.positions", "attr"]
        self.assertSequenceEqual(expected_paths, paths)

    def test_validate_index_specifiers(self):
        # Valid (empty index range)
        path = HubitModelPath("segments[IDX_SEG].layers[IDX_LAY]")
        path.validate()

        # Valid (full index range)
        path = HubitModelPath("segments[IDX_SEG].layers[:@IDX_LAY]")
        path.validate()

        # Valid (digit index range)
        path = HubitModelPath("segments[17@IDX_SEG].layers[0@IDX_LAY]")
        path.validate()

        # Invalid since limited index ranges are not allowed
        path = HubitModelPath("segments[17:34@IDX_SEG].layers[IDX_LAY]")
        path.validate()

        # Valid. Negative index range allowed
        path = HubitModelPath("segments[-1@IDX_SEG].layers[IDX_LAY]")
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

    def test_new_with_index(self):
        path = HubitModelPath("segments[IDX_SEG].lay1ers[:@IDX1LAY113]")
        index_specifiers = path.get_index_specifiers()
        path = path.new_with_index(index_specifiers[1], "1")
        assert path == HubitModelPath("segments[IDX_SEG].lay1ers[1]")


class TestModelIndexSpecifier(unittest.TestCase):
    def test_mis(self):
        mis = ModelIndexSpecifier(":@IDX_LAY")
        assert mis.offset == 0
        assert mis.identifier == "IDX_LAY"
        assert mis.range == ":"

        mis = ModelIndexSpecifier("IDX_LAY+1")
        assert mis.offset == 1
        assert mis.identifier == "IDX_LAY"
        assert mis.range == ""

        mis = ModelIndexSpecifier("IDX_LAY-12")
        assert mis.offset == -12
        assert mis.identifier == "IDX_LAY"
        assert mis.range == ""

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


class TestPathIndexRange(unittest.TestCase):
    def test_is_limited_range(self):
        assert PathIndexRange._is_limited_range("2") == False
        assert PathIndexRange._is_limited_range(":") == False
        assert PathIndexRange._is_limited_range("") == False
        assert PathIndexRange._is_limited_range("1:") == True
        assert PathIndexRange._is_limited_range(":3") == True
        assert PathIndexRange._is_limited_range("1:3") == True

    def test_validate_limited_range(self):
        # Valid ranges
        PathIndexRange("1:")._validate_limited_range()
        PathIndexRange("1:4")._validate_limited_range()
        PathIndexRange(":4")._validate_limited_range()

        # Invalid ranges
        with pytest.raises(HubitError):
            PathIndexRange("4:1")._validate_limited_range()

        with pytest.raises(HubitError):
            PathIndexRange(":-1")._validate_limited_range()

        with pytest.raises(HubitError):
            PathIndexRange("-1:")._validate_limited_range()

        with pytest.raises(HubitError):
            PathIndexRange("k:")._validate_limited_range()

        with pytest.raises(HubitError):
            PathIndexRange(":k")._validate_limited_range()

    def test_start(self):
        assert PathIndexRange("2").start == 2
        assert PathIndexRange(":").start == 0
        assert PathIndexRange(":5").start == 0
        assert PathIndexRange("5:").start == 5
        assert PathIndexRange("5:17").start == 5
        assert PathIndexRange("").start == None

    def test_range_type(self):
        range = PathIndexRange("2")
        assert range.is_digit
        assert not range.is_limited_range
        assert not range.is_full_range

        range = PathIndexRange("2:")
        assert not range.is_digit
        assert range.is_limited_range
        assert not range.is_full_range

        range = PathIndexRange(":2")
        assert not range.is_digit
        assert range.is_limited_range
        assert not range.is_full_range

        range = PathIndexRange("2:4")
        assert not range.is_digit
        assert range.is_limited_range
        assert not range.is_full_range

        range = PathIndexRange(":")
        assert not range.is_digit
        assert not range.is_limited_range
        assert range.is_full_range

    def test_range_includes(self):
        range = PathIndexRange("2")
        assert range.includes(PathIndexRange("1")) == False
        assert range.includes(PathIndexRange("2")) == True
        assert range.includes(PathIndexRange("3")) == False
        assert range.includes(PathIndexRange(":")) == False

        range = PathIndexRange(":")
        assert range.includes(PathIndexRange(":")) == True

        # Limited range not supported as argument
        range = PathIndexRange("2")
        with pytest.raises(NotImplementedError):
            range.includes(PathIndexRange("1:"))

        range = PathIndexRange(":")
        with pytest.raises(NotImplementedError):
            range.includes(PathIndexRange("1:"))

        # If range is empty it is always in scope
        range = PathIndexRange("")
        assert range.includes(PathIndexRange("2")) == True
        assert range.includes(PathIndexRange(":")) == True
        assert range.includes(PathIndexRange("2:")) == True

    def test_range_intersects(self):
        range = PathIndexRange("2")
        assert not range.intersects(PathIndexRange("1"))
        assert range.intersects(PathIndexRange("2"))
        assert not range.intersects(PathIndexRange("3"))

        range = PathIndexRange("2:")
        assert not range.intersects(PathIndexRange("1"))
        assert range.intersects(PathIndexRange("2"))
        assert range.intersects(PathIndexRange("3"))

        range = PathIndexRange(":2")
        assert range.intersects(PathIndexRange("1"))
        assert not range.intersects(PathIndexRange("2"))
        assert not range.intersects(PathIndexRange("3"))

        range = PathIndexRange("2:14")
        assert not range.intersects(PathIndexRange("1"))
        assert range.intersects(PathIndexRange("2"))
        assert range.intersects(PathIndexRange("3"))
        assert not range.intersects(PathIndexRange("14"))

        range = PathIndexRange(":")
        assert range.intersects(PathIndexRange("1"))
        assert range.intersects(PathIndexRange("2"))
        assert range.intersects(PathIndexRange("3"))

    def test_lrange_intersects_lrange(self):
        # Intersection with one self should return True
        range1 = PathIndexRange("2:4")
        self.assertTrue(range1._lrange_intersects_lrange(range1))

        # Edge case that behave like standard Python e.g.
        # set(range(2,4)).intersection(set(range(4,17))) gives an empty set
        range1 = PathIndexRange("2:4")
        range2 = PathIndexRange("4:17")
        self.assertFalse(range1._lrange_intersects_lrange(range2))
        self.assertFalse(range2._lrange_intersects_lrange(range1))

        # Range 2 inside range 1
        range1 = PathIndexRange("2:14")
        range2 = PathIndexRange("4:7")
        self.assertTrue(range1._lrange_intersects_lrange(range2))

        # Overlap
        range1 = PathIndexRange("2:14")
        range2 = PathIndexRange("10:24")
        self.assertTrue(range1._lrange_intersects_lrange(range2))

        # Implicit start
        range1 = PathIndexRange(":14")
        range2 = PathIndexRange(":24")
        self.assertTrue(range1._lrange_intersects_lrange(range2))

        # Implicit end
        range1 = PathIndexRange("4:")
        range2 = PathIndexRange("2:")
        self.assertTrue(range1._lrange_intersects_lrange(range2))

        # Implicit start & end
        range1 = PathIndexRange(":6")
        range2 = PathIndexRange("2:")
        self.assertTrue(range1._lrange_intersects_lrange(range2))

        # Implicit start & end
        range1 = PathIndexRange(":6")
        range2 = PathIndexRange("6:")
        self.assertFalse(range1._lrange_intersects_lrange(range2))

        # Implicit end1
        range1 = PathIndexRange("8:")
        range2 = PathIndexRange("6:16")
        self.assertTrue(range1._lrange_intersects_lrange(range2))

        range1 = PathIndexRange("18:")
        range2 = PathIndexRange("6:16")
        self.assertFalse(range1._lrange_intersects_lrange(range2))

    def test_invalid(self):
        with self.assertRaises(HubitError):
            PathIndexRange("-1", allow_negative_index=False)

        with self.assertRaises(HubitError):
            PathIndexRange("k")


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
        key = "list1.1.list2.32"
        includes = "list1.list2", "ok"
        result = FlatData._include(key, includes)
        expected_result = True
        assert result == expected_result

        includes = "list1", "ok"
        result = FlatData._include(key, includes)
        expected_result = False
        assert result == expected_result
