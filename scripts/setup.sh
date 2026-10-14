#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
python3 -c 'import sys; assert sys.version_info >= (3,12), "需要Python 3.12或更新版本"'
python3 -m unittest discover -v
printf '%s\n' '检查完成。启动：python3 -m workbench serve'
