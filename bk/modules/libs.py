import importlib.util
import sys

from pathlib import Path

def load_module_from_path(module_name: str, relative_file_path: Path):
    """Dinamically load a module from a given file path.
    
    param module_name: Name to assign to the loaded module.
    param file_path: Path to the .py file containing the module.
    """
    base_path = Path(__file__).parents[2]  # Adjust as needed to get to the project root
    module_path = base_path / relative_file_path
    
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module {module_name} from {module_path}")
    
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    
    return module    