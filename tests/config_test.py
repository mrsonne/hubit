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
