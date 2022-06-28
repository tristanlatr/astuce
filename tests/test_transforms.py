
import ast

import pytest

from astuce import inference, nodes
from . import AstuceTestCase, capture_output

class Test__all__ListTransforms(AstuceTestCase):
    def test__all__transforms(self) -> None:
        with capture_output() as lines:
            module = self.parse(
                """
                __all__ = []
                m = [1]
                __all__.append(1)
                __all__.extend(m)
                """)
        # assert lines == ['test:4: Transforming __all__.append() into an augmented assigment', 
        # 'test:5: Transforming __all__.extend() into an augmented assigment'], lines

        assert "__all__ += [1]" == module.body[2].unparse()
        assert "__all__ += m" == module.body[3].unparse()
        
        assert isinstance(module.body[2], ast.AugAssign)
        assert module.body[2].parent == module, module.body[2].parent
        assert module.body[2].target.parent == module.body[2], module.body[2].target.parent

        assert isinstance(module.body[3], ast.AugAssign)
        assert module.body[3].parent == module, module.body[3].parent
        assert module.body[3].target.parent == module.body[3], module.body[3].target.parent
        get_all_ = inference.get_attr(module, '__all__')
        assert len(get_all_) == 1, get_all_
        
        with capture_output() as lines:
            assert ast.literal_eval(inference.safe_infer(get_all_[0])) == [1,1]
        assert lines == [], lines

        assert len(module.locals['__all__']) == 3, module.locals['__all__']
        
