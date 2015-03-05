#!/bin/bash

# Convert the CRAFT corpus 1.0 Knowtator annotations into the Open
# Annotation format, combining annotations of the various upper-level
# semantic types.

set -e
set -u

if [ "$#" -lt 2 -o "$#" -gt 2 ]; then
    echo "Usage: $0 CRAFT-ROOT OUTPUT-DIR"
    exit 1
fi

indir="$1/knowtator-xml"
textdir="$1/articles/txt"
outdir="$2"

if [ ! -d "$indir" ]; then
    echo "$indir: not a directory"
    exit 1
fi

if [ ! -d "$textdir" ]; then
    echo "$textdir: not a directory"
    exit 1
fi

if [ -e "$outdir" ]; then
    echo "$outdir exists, won't clobber"
    exit 1
fi

mkdir "$outdir"

for f in $(ls "$indir"/{chebi,cl,entrezgene,go_bpmf,go_cc,ncbitaxon,pr,so,sections-and-typography} | \
    egrep '\.xml$' | sort | uniq); do
    o="$outdir"/$(basename "$f" .txt.knowtator.xml).jsonld
    echo "Converting $f to $o ... " >&2
    ./knowtator2oa.py -d "$textdir" "$indir"/{chebi,cl,entrezgene,go_bpmf,go_cc,ncbitaxon,pr,so,sections-and-typography}/$f > "$o"
done
