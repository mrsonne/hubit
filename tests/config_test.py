import unittest
from hubit.config import HubitModelComponent, HubitModelPath, HubitQueryPath
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
            HubitModelComponent.from_cfg(cfg)


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
        new_path = path.set_indices(("34", "3"))
        self.assertEqual(new_path, expected_pathstr)

    def test_set_ilocs_with_wildcard(self):
        """Insert real numbers where the ILOC placeholder is found"""
        expected_pathstr = "segs[34].walls[:@IDXWALL].temps"
        path = HubitModelPath("segs[IDXSEG].walls[:@IDXWALL].temps")
        new_path = path.set_indices(("34", "3"))
        self.assertEqual(new_path, expected_pathstr)

    def test_set_ilocs_assertion_error(self):
        """Too many indices specified"""
        path = HubitModelPath("segs[IDXSEG].walls[:@IDXWALL].temps")
        with self.assertRaises(AssertionError):
            path.set_indices(("34", "3", "19"))

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
        internal_paths = path.paths_between_idxids(idxids)
        # Last element is empty since there are no attribute after IDX_POS
        expected_internal_paths = ["segments", "layers", "test.positions", ""]
        self.assertSequenceEqual(expected_internal_paths, internal_paths)

    def test_validate_idxids(self):
        # Valid
        path = HubitModelPath("segments[IDX_SEG].layers[IDX-LAY]")
        path.validate()

        # Valid
        path = HubitModelPath("segments[IDX_SEG].layers[:@IDX-LAY]")
        path.validate()

        # Only one @ allowed in index specifier
        path = HubitModelPath("segments[IDX_SEG].layers[:@@IDX-LAY]")
        with self.assertRaises(AssertionError):
            path._validate_index_specifiers()

        # Invalid character \ in index identifier
        path = HubitModelPath("segments[IDX_SEG].layers[:@IDX/LAY]")
        with self.assertRaises(AssertionError):
            path._validate_index_identifiers()

        # Numbers allowed
        path = HubitModelPath("segments[IDX_SEG].layers[:@IDX1LAY113]")
        path.validate()

        path = HubitModelPath("segments[IDX_SEG].layers[@]")
        with self.assertRaises(AssertionError):
            path._validate_index_identifiers()
