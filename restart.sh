#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

echo $SCRIPT_DIR

PID=$(pgrep -f $SCRIPT_DIR/vestelEvc04Service.py)
echo $PID
kill $PID
