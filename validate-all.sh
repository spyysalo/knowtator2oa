#!/bin/bash

set -e
set -u

for f in data/examples/craft/*.xml; do
    echo "Process $f"
    o=`basename $f .xml`.json
    ./knowtator2oa.py "$f" > "$o"
    ./lsvalidate.sh "$o"
    rm "$o"
    echo "Process $f, compact"
    ./knowtator2oa.py -c "$f" > "$o"
    ./lsvalidate.sh "$o"
    rm "$o"
    echo
done