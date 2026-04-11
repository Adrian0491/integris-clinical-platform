import unittest

from bk.modules.libs import *

class TestLibs(unittest.TestCase):
    
    def test_load_module_from_path(self):
        # Assuming there's a test module at bk/test_module.py with a function test_func() that returns "Hello"
        module = load_module_from_path("test_module", Path("bk/test_module.py"))
        self.assertTrue(hasattr(module, "test_func"))
        self.assertEqual(module.test_func(), "Hello")
        
if __name__ == "__main__": 
    unittest.main()