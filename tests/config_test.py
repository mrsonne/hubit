import unittest
from hubit.config import HubitModelComponent
from hubit.errors import HubitModelComponentError

class TestWorker(unittest.TestCase):

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
