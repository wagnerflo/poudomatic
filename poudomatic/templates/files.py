from .base import *

class files(Template):
    config_schema = (
        yamap()
          .zero_or_one('data', yamap().one_or_more('.+', yastr))
          .zero_or_one('script', yamap().one_or_more('.+', yastr))
          .zero_or_one('symlink', yamap().one_or_more('.+', yastr))
    )
