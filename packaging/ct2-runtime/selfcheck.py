"""CT2 运行时包自检入口（预打包件内执行；依赖钉断言，模型无关）。

由 tools 构建流程复制进 subtrans-ct2-runtime-*.zip 包根；包内
`python.exe selfcheck.py` rc=0 即安装有效（asr_runtime.selfcheck 的
独立运行形态共享同一断言口径）。
"""
import av
import ctranslate2

assert ctranslate2.__version__ == "4.8.4", ctranslate2.__version__
assert av.__version__.startswith("13."), av.__version__
from faster_whisper import WhisperModel  # noqa: F401,E402

print("ct2-runtime-selfcheck OK")
