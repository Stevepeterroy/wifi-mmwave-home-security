#!/bin/zsh
demo_dir=${0:A:h}
demo_python='/Users/stevepeterroy/Desktop/Final Year Project Sources/rd60_esp_diagnostic/.venv/bin/python'
if [[ ! -x "$demo_python" ]]; then
  demo_python=python3
fi
cd "$demo_dir" || exit 1
print 'Open http://127.0.0.1:8767 after the server starts. Press Ctrl+C to stop.'
exec "$demo_python" server.py
