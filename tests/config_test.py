import unittest
from hubit.config import HubitModelComponent, HubitPath
from hubit.errors import HubitModelComponentError


class Test(unittest.TestCase):
    def test_1(self):
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

    def test_get_idxids(self):
        """Extract idxids from path"""
        path = HubitPath("segs[IDX_SEG].walls[IDX_WALL].heat_flow")
        expected_idxids = ["IDX_SEG", "IDX_WALL"]
        idxids = path.get_idxids()
        self.assertSequenceEqual(expected_idxids, idxids)

    def test_set_ilocs(self):
        """Insert real numbers where the ILOC placeholder is found"""
        expected_pathstr = "segs[34].walls[3].temps"
        path = HubitPath("segs[IDXSEG].walls[IDXWALL].temps")
        new_path = path.set_ilocs(("34", "3"))
        self.assertEqual(new_path, expected_pathstr)

    def test_set_ilocs_with_wildcard(self):
        """Insert real numbers where the ILOC placeholder is found"""
        expected_pathstr = "segs[34].walls[:@IDXWALL].temps"
        path = HubitPath("segs[IDXSEG].walls[:@IDXWALL].temps")
        new_path = path.set_ilocs(("34", "3"))
        self.assertEqual(new_path, expected_pathstr)

    def test_as_internal(self):
        """Convert Hubit path to internal path"""
        path = "segs[IDX_SEG].walls[IDX_WALL].heat_flow"
        expected_internal_path = "segs.IDX_SEG.walls.IDX_WALL.heat_flow"
        internal_path = HubitPath.as_internal(path)
        self.assertSequenceEqual(expected_internal_path, internal_path)

    def test_as_internal_idx_wildcard(self):
        """Convert Hubit path to internal path"""
        path = "segs[:@IDX_SEG].walls[:@IDX_WALL].heat_flow"
        expected_internal_path = "segs.:@IDX_SEG.walls.:@IDX_WALL.heat_flow"
        internal_path = HubitPath.as_internal(path)
        self.assertSequenceEqual(expected_internal_path, internal_path)

    def test_paths_between_idxids(self):
        path = HubitPath("segments[IDX_SEG].layers[IDX_LAY].test.positions[IDX_POS]")
        idxids = path.get_idxids()
        internal_paths = path.paths_between_idxids(idxids)
        # Last element is empty since there are no attribute after IDX_POS
        expected_internal_paths = ["segments", "layers", "test.positions", ""]
        self.assertSequenceEqual(expected_internal_paths, internal_paths)
