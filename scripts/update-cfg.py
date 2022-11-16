from pathlib import Path

import requests

if __name__ == "__main__":
    
    model_file_contents = requests.get('https://github.com/SMAT-Lab/Scalpel/raw/main/scalpel/cfg/model.py').text
    builder_file_contents = requests.get('https://github.com/SMAT-Lab/Scalpel/raw/main/scalpel/cfg/builder.py').text
    # use absolute import
    builder_file_contents = builder_file_contents.replace('from ..core.func_call_visitor import get_func_calls', 
                                                           'from scalpel.core.func_call_visitor import get_func_calls')

    (Path(__file__).parent.parent / 'astuce' / 'cfg').mkdir(parents=True, exist_ok=True)
    (Path(__file__).parent.parent / 'astuce' / 'cfg' / 'model.py').write_text(model_file_contents)
    (Path(__file__).parent.parent / 'astuce' / 'cfg' / 'builder.py').write_text(builder_file_contents)
