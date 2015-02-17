#!/bin/bash

# Validate Open Annotation JSON-LD using the lorestore validation service
# http://austese.net/lorestore/validate.html .

# See also
# http://www.w3.org/2001/sw/wiki/images/0/0b/RDFVal_Gerber_Cole_Lowery.pfd,
# https://github.com/uq-eresearch/lorestore

set -e
set -u

VALIDATOR_URL="http://austese.net/lorestore/oa/validate/"
REQUEST_METHOD="POST"

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 FILE [FILE [...]]"
    exit 1
fi

for f in "$@"; do
    echo "-------------------- Validating $f --------------------"
    tmp=`mktemp lsvalidate-tmp-XXX`
    curl -# -X "$REQUEST_METHOD" -i -H 'Content-Type: application/json' \
	-d "@$f" $VALIDATOR_URL > $tmp
    tail -n 1 $tmp | \
	python -c 'import json; print json.dumps(json.loads(raw_input()), indent=2, separators=(",", ": "))' | \
	egrep '^  "(error|warn|pass|total)"' | \
	perl -pe 's/"//g' | tr '\n' ' ' | perl -pe 's/$/\n/'
    rm "$tmp"
done

