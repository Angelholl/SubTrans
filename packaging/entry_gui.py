"""PyInstaller entry point for SubTrans GUI.

Thin launcher only; frozen 下 webview_gui._auto_setup 会按既有逻辑短路。
不承载任何业务逻辑，正式应用入口仍为 subtransjav.webview_gui.main.main。
"""

from subtransjav.webview_gui.main import main

if __name__ == "__main__":
    main()
