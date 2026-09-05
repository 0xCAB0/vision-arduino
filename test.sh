#!/usr/bin/env bash
PORT=/dev/ttyUSB0

stty -F $PORT 9600 raw -echo -echoe -echok 2>/dev/null
exec 3<>$PORT
sleep 2.5
read -r -t 1 -u 3 bootline

pass=0; fail=0
for d in 0 1 2 3 4 5 0; do
    printf '%s' "$d" >&3
    line=""
    read -r -t 2 -u 3 line
    line="${line%%$'\r'}"
    case $d in
        0) expected="Display off" ;;
        *) expected="Showing: $d" ;;
    esac
    if [ "$line" = "$expected" ]; then
        echo "[PASS] sent '$d' -> '$line'"
        pass=$((pass+1))
    else
        echo "[FAIL] sent '$d' -> '$line' (expected '$expected')"
        fail=$((fail+1))
    fi
    sleep 1.5
done
exec 3<&-
echo
echo "RESULT: $pass passed, $fail failed"
exit $fail
