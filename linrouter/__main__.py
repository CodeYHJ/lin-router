"""Lin Router 模块执行入口：python -m linrouter"""

from __future__ import annotations

import sys
from pathlib import Path

# 将项目根目录加入 sys.path，以便导入 app/desktop/settings_store 等根级模块
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import desktop  # noqa: E402

if __name__ == "__main__":
    desktop.main()
