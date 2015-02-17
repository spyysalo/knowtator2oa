#!/usr/bin/env python

"""Convert Knowtator XML into Open Annotation format."""

import os
import sys
import six
import json
import codecs

# python 2.5
import uuid
import xml.etree.ElementTree as ET

usage = '%s FILE [FILE [...]]' % os.path.basename(__file__)

# Context description that is recommended for use in systems that
# implement the Open Annotation data model, copied Jan 2015 from
# http://www.openannotation.org/spec/core/publishing.html
oa_recommended_context = """"oa": "http://www.w3.org/ns/oa#",
    "cnt": "http://www.w3.org/2011/content#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "dctypes": "http://purl.org/dc/dcmitype/",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "prov": "http://www.w3.org/ns/prov#",
    "trig": "http://www.w3.org/2004/03/trix/rdfg-1/",
    "xsd": "http://www.w3.org/2001/XMLSchema#",

    "hasBody" :         {"@type":"@id", "@id" : "oa:hasBody"},
    "hasTarget" :       {"@type":"@id", "@id" : "oa:hasTarget"},
    "hasSource" :       {"@type":"@id", "@id" : "oa:hasSource"},
    "hasSelector" :     {"@type":"@id", "@id" : "oa:hasSelector"},
    "hasState" :        {"@type":"@id", "@id" : "oa:hasState"},
    "hasScope" :        {"@type":"@id", "@id" : "oa:hasScope"},
    "annotatedBy" :  {"@type":"@id", "@id" : "oa:annotatedBy"},
    "serializedBy" : {"@type":"@id", "@id" : "oa:serializedBy"},
    "motivatedBy" :  {"@type":"@id", "@id" : "oa:motivatedBy"},
    "equivalentTo" : {"@type":"@id", "@id" : "oa:equivalentTo"},
    "styledBy" :     {"@type":"@id", "@id" : "oa:styledBy"},
    "cachedSource" : {"@type":"@id", "@id" : "oa:cachedSource"},
    "conformsTo" :   {"@type":"@id", "@id" : "dcterms:conformsTo"},
    "default" :      {"@type":"@id", "@id" : "oa:default"},
    "item" :         {"@type":"@id", "@id" : "oa:item"},
    "first":         {"@type":"@id", "@id" : "rdf:first"},
    "rest":          {"@type":"@id", "@id" : "rdf:rest", "@container" : "@list"},

    "annotatedAt" :  { "@type": "xsd:dateTimeStamp", "@id": "oa:annotatedAt" },
    "end" :          { "@type": "xsd:nonNegativeInteger", "@id": "oa:end" },
    "exact" :        "oa:exact",
    "prefix" :       "oa:prefix",
    "serializedAt" : { "@type": "xsd:dateTimeStamp", "@id": "oa:serializedAt" },
    "start" :        { "@type": "xsd:nonNegativeInteger", "@id": "oa:start" },
    "styleClass" :   "oa:styleClass",
    "suffix" :       "oa:suffix",
    "when" :         { "@type": "xsd:dateTimeStamp", "@id": "oa:when" },

    "chars" :        "cnt:chars",
    "bytes" :        "cnt:bytes",
    "format" :       "dc:format",
    "language" :     "dc:language",
    "value" :        "rdf:value",
    "label" :        "rdfs:label",
    "name" :         "foaf:name",
    "mbox" :         "foaf:mbox\""""

# Compact OA context: minimal subset of the above
compact_oa_context = """"oa": "http://www.w3.org/ns/oa#",
    "hasBody" :      { "@type": "@id", "@id": "oa:hasBody" },
    "hasTarget" :    { "@type": "@id", "@id": "oa:hasTarget" },
    "annotatedBy" :  { "@type": "@id", "@id": "oa:annotatedBy" },
    "serializedBy" : { "@type": "@id", "@id": "oa:serializedBy" },
    "annotatedAt" :  { "@type": "xsd:dateTimeStamp", "@id": "oa:annotatedAt" },
    "serializedAt" : { "@type": "xsd:dateTimeStamp", "@id": "oa:serializedAt" }"""

# Local prefixes for compact output
compact_prefix_map = {
    "http://craft.ucdenver.edu/annotation/": "ann",
    "http://purl.obolibrary.org/obo/": "obo",
    "http://compbio.ucdenver.edu/": "ucdenver"
}

# Compact context: compact OA context and local prefixes
compact_context = ',\n'.join(
    [compact_oa_context] +
    ['    "%s": "%s"' % (p, f) for f, p in compact_prefix_map.items()]
    )

# Encoding to read text files in
TEXT_ENCODING='utf-8'

DOCUMENT_ID_ROOT = 'http://craft.ucdenver.edu/document/PMID-'
ANNOTATION_ID_ROOT = 'http://craft.ucdenver.edu/annotation/'
ANNOTATOR_ID_ROOT = 'http://kabob.ucdenver.edu/annotator/'

# Mapping to resolvable annotator URIs
annotator_mapping = {
    'http://kabob.ucdenver.edu/annotator/CCPColoradoComputationalPharmacology':  'http://compbio.ucdenver.edu/Hunter_lab',
    'http://kabob.ucdenver.edu/annotator/CCPColoradoComputationalPharmacology,UCDenver':  'http://compbio.ucdenver.edu/Hunter_lab',
}

# Attribute name constants
a_id = 'id'
a_source = 'textSource'
a_start = 'start'
a_end = 'end'
a_value = 'value'

# Tag name constants
t_annotation = 'annotation'
t_span = 'span'
t_text = 'spannedText'
t_annotator = 'annotator'
t_mention = 'mention'
t_classm = 'classMention'
t_mclass = 'mentionClass'
t_hasslot = 'hasSlotMention'
t_boolslot = 'booleanSlotMention'
t_intslot = 'integerSlotMention'
t_strslot = 'stringSlotMention'
t_cmpxslot = 'complexSlotMention'
t_mslot = 'mentionSlot'
t_boolval = 'booleanSlotMentionValue'
t_intval = 'integerSlotMentionValue'
t_strval = 'stringSlotMentionValue'
t_cmpxval = 'complexSlotMentionValue'

# OA constats
oa_id = '@id'
oa_type = '@type'
oa_context = '@context'
oa_default_type = 'oa:Annotation'
oa_hasTarget = 'hasTarget'
oa_hasBody = 'hasBody'
oa_annotatedAt = 'annotatedAt'
oa_annotatedBy = 'annotatedBy'

# IDs of slots to discard as irrelevant (CRAFT-specific)
irrelevant_slot = set([
        'taxon ambiguity',  # boolean, false in 7434/7437 cases
        'common name',      # taxon common name
        'macromolecular complex or protein ambiguity', # boolean
        'is_substituent_group_from', # single instance in whole corpus
        'section name',
])

def argparser():
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument('-c', '--compact', action='store_true', default=False,
                        help='Compact output')
    parser.add_argument('-d', '--textdir', metavar='DIR', default=None,
                        help='Directory with text files')
    parser.add_argument('file', metavar='FILE', nargs='+',
                        help='Knowtator XML file to convert')

    return parser

def find_only(element, tag):
    """Return the only subelement with tag(s)."""
    if isinstance(tag, six.string_types):
        tag = [tag]
    found = []
    for t in tag:
        found.extend(element.findall(t))
    assert len(found) == 1, 'expected one <%s>, got %d' % (tag, len(found))
    return found[0]

def find_one_or_more(element, tag):
    """Return subelements with tag, checking that there is at least one."""
    s = element.findall(tag)
    assert len(s) >= 1, 'expected at least one <%s>, got %d' % (tag, len(s))
    return s

def get_document_id(root):
    source = root.attrib[a_source]
    # if source.endswith('.txt'):
    #     source = source[:-4]
    return DOCUMENT_ID_ROOT + source

def get_document_source(root):
    return root.attrib[a_source]

def get_mention_id(annotation):
    mention = find_only(annotation, t_mention)
    return mention.attrib[a_id]

def get_spans(annotation):
    spans = []
    for span in find_one_or_more(annotation, t_span):
        spans.append((int(span.attrib[a_start]), int(span.attrib[a_end])))
    return spans

def get_text(annotation):
    text = find_only(annotation, t_text)
    return text.text

def get_annotator(annotation):
    annotator = find_only(annotation, t_annotator)
    return annotator.text # ignore id

class Annotation(object):
    def __init__(self, mention_id, spans, text, annotator):
        self.id = ANNOTATION_ID_ROOT + str(uuid.uuid4()) # random uuid
        self.mention_id = mention_id
        self.spans = spans
        self.text = text
        self.annotator = ANNOTATOR_ID_ROOT + annotator.replace(' ', '')

    def targets(self, doc_id):
        targets = ['%s#char=%d,%d' % (doc_id, s[0], s[1]) for s in self.spans]
        if len(targets) == 1:
            return targets[0]
        else:
            return targets

    def __str__(self):
        return str((self.mention_id, self.spans, self.text, self.annotator))

    @classmethod
    def from_element(cls, element):
        expected = (t_mention, t_annotator, t_span, t_text)
        assert not any(True for e in element if e.tag not in expected)
        return cls(get_mention_id(element),
                   get_spans(element),
                   get_text(element),
                   get_annotator(element))

class Mention(object):
    def __init__(self, id_, class_id, class_text, slot_ids):
        self.id = id_
        self.class_id = class_id
        self.class_text = class_text
        self.slot_ids = slot_ids

    def values(self, slot_by_id):
        # First, discard values that are known to be irrelevant to the
        # core information content (e.g. redundant common names)
        self.slot_ids = [i for i in self.slot_ids
                         if slot_by_id[i].slot_id not in irrelevant_slot]

        # If there are no slots (indirect values), assume that the
        # value is the class ID (this holds e.g. for most OBOs in
        # CRAFT). Otherwise, draw values from the slots, affixing the
        # slot ID to differentiate between values types.
        if len(self.slot_ids) == 0:
            values = [self.class_id]
        else:
            slots = [slot_by_id[i] for i in self.slot_ids]
            values = [s.slot_id + ':' + s.value for s in slots]

        if len(values) == 1:
            return values[0]
        else:
            return values

    def __str__(self):
        return str((self.id, self.class_id, self.class_text, self.slot_ids))

    @classmethod
    def from_element(cls, element):
        expected = (t_mclass, t_hasslot)
        assert not any(True for e in element if e.tag not in expected),\
            'unexpected child: ' + ' '.join(['<%s>' % e.tag for e in element])
        mclass = find_only(element, t_mclass)
        slot_ids = [s.attrib[a_id] for s in element.findall(t_hasslot)]
        return cls(element.attrib[a_id],
                   mclass.attrib[a_id],
                   mclass.text,
                   slot_ids)

class Slot(object):
    def __init__(self, id_, slot_id, value_type, value):
        self.id = id_
        self.slot_id = slot_id
        self.value_type = value_type
        self.value = value

    def __str__(self):
        return str((self.id, self.slot_id, self.value_type, self.value))

    @classmethod
    def from_element(cls, element):
        expected = (t_mslot, t_boolval, t_intval, t_strval, t_cmpxval)
        assert not any(True for e in element if e.tag not in expected)
        mslot = find_only(element, t_mslot)
        value = find_only(element, (t_boolval, t_intval, t_strval, t_cmpxval))
        value_type = value.tag.replace('SlotMention', '')
        return cls(element.attrib[a_id],
                   mslot.attrib[a_id],
                   value_type,
                   value.attrib[a_value])

prefix_uri_map = {
    'CHEBI:': 'http://purl.obolibrary.org/obo/CHEBI_%s',
    'CL:':    'http://purl.obolibrary.org/obo/CL_%s',
    'GO:':    'http://purl.obolibrary.org/obo/GO_%s',
    'PR:':    'http://purl.obolibrary.org/obo/PR_%s',
    'SO:':    'http://purl.obolibrary.org/obo/SO_%s',
    'taxonomy ID:': 'http://purl.obolibrary.org/obo/NCBITaxon_%s',
    'has Entrez Gene ID:': 'http://kabob.ucdenver.edu/iao/eg/EG_%s_ICE',
}

id_uri_map = {
    'independent_continuant': 'http://purl.obolibrary.org/obo/BFO_0000004',
    # NCBI taxonomy non-specific
    'taxonomic_rank': 'http://purl.obolibrary.org/obo/NCBITaxon_taxonomic_rank',
    'species': 'http://purl.obolibrary.org/obo/NCBITaxon_species',
    'subspecies': 'http://purl.obolibrary.org/obo/NCBITaxon_subspecies',
    'phylum': 'http://purl.obolibrary.org/obo/NCBITaxon_phylum',
    'kingdom': 'http://purl.obolibrary.org/obo/NCBITaxon_kingdom',
    # Typography
    'bold': 'http://craft.ucdenver.edu/iao/bold',
    'italic': 'http://craft.ucdenver.edu/iao/italic',
    'underline': 'http://craft.ucdenver.edu/iao/underline',
    'sub': 'http://craft.ucdenver.edu/iao/sub',
    'sup': 'http://craft.ucdenver.edu/iao/sup',
    'section': 'http://purl.obolibrary.org/obo/IAO_0000314',
}

def id_to_uri(id_):
    if id_ in id_uri_map:
        return id_uri_map[id_]
    for p, s in prefix_uri_map.items():
        if id_.startswith(p):
            return s % id_[len(p):]
    print >> sys.stderr, 'Warning: failed to map %s' % id_
    return id_

def ids_to_uris(ids):
    if isinstance(ids, six.string_types):
        return id_to_uri(ids)
    else:
        return [id_to_uri(i) for i in ids]

def pretty_print(doc, initial_indent=0):
    s = json.dumps(doc, sort_keys=True, indent=2, separators=(',', ': '))
    if initial_indent == 0:
        return s
    else:
        idt = ' ' * initial_indent
        return idt + s.replace('\n', '\n'+idt)

def compact(s, prefix_map):
    for pref, short in prefix_map.items():
        if s.startswith(pref):
            return '%s:%s' % (short, s[len(pref):])
    return s

def compact_values(object, prefix_map=None):
    if prefix_map is None:
        prefix_map = compact_prefix_map
    compacted = {}
    for key, val in object.items():
        if isinstance(val, six.string_types):
            val = compact(val, prefix_map)
        else:
            assert isinstance(val, list)
            val = [compact(v, prefix_map) for v in val]
        compacted[key] = val
    return compacted

def convert(annotations, mentions, slots, doc_id, options=None):
    # There should be exactly one mention for each annotation. The two
    # are connected by annotation.mention_id == mention.id
    assert len(annotations) == len(mentions)
    mention_by_id = { m.id: m for m in mentions }
    slot_by_id = { s.id: s for s in slots }

    converted = []
    for annotation in annotations:
        mention = mention_by_id[annotation.mention_id]
        values = mention.values(slot_by_id)
        annotator = annotation.annotator
        annotator = annotator_mapping.get(annotator, annotator)
        converted.append({
            oa_id:          annotation.id,
            oa_type:        oa_default_type,
            oa_hasTarget:   annotation.targets(doc_id),
            oa_hasBody:     ids_to_uris(values),
            oa_annotatedBy: annotator,
            #oa_annotatedAt: # Knowtator XML doesn't include this
            })
    if options and options.compact:
        converted = [compact_values(c) for c in converted]
    return converted

def get_document_text(ann_fn, doc_source, options=None):
    # Text file should be in same directory as annotation by default,
    # other dirs can be given as options.
    text_dir = os.path.dirname(ann_fn)
    if options is not None and options.textdir is not None:
        text_dir = options.textdir

    fn = os.path.join(text_dir, os.path.basename(doc_source))
    try:
        with codecs.open(fn, encoding=TEXT_ENCODING) as f:
            return f.read()
    except IOError, e:
        raise IOError('Failed to find text file for %s: %s' % (ann_fn, fn))

def validate(annotation, text):
    """Check that annotation text matches text identified by its spans."""
    texts = []
    for start, end in annotation.spans:
        texts.append(text[start:end])
    combined = ' ... '.join(texts)
    assert combined == annotation.text, \
        'Text mismatch:\n"%s" vs.\n"%s"' % (combined, annotation.text)

def parse(fn, options=None):
    tree = ET.parse(fn)
    root = tree.getroot()    

    doc_id = get_document_id(root)

    annotations, mentions, slots = [], [], []
    for element in root:
        if element.tag == t_annotation:
            annotations.append(Annotation.from_element(element))
        elif element.tag == t_classm:
            mentions.append(Mention.from_element(element))
        elif element.tag in (t_boolslot, t_intslot, t_strslot, t_cmpxslot):
            slots.append(Slot.from_element(element))
        else:
            raise ValueError('unexpected tag %s' % element.tag)

    doc_source = get_document_source(root)
    doc_text = get_document_text(fn, doc_source, options)
    for a in annotations:
        validate(a, doc_text)

    return annotations, mentions, slots, doc_id

def write_header(out, options=None, context=None):
    if context is None:
        if options is None or not options.compact:
            context = oa_recommended_context
        else:
            context = compact_context

    print >> out, '''{
  "@context": {
    %s
  },
  "@graph": [''' % context

def write_footer(out):
    print >> out, '''
  ]
}'''

def process(fn, options=None, is_first=True):
    try:
        parsed = parse(fn, options)
    except:
        print >> sys.stderr, 'Failed to parse %s' % fn
        raise
    out = sys.stdout
    for i, c in enumerate(convert(*parsed, options=options)):
        if not is_first or i != 0:
            out.write(',\n')
        out.write(pretty_print(c, 5))

def main(argv):
    args = argparser().parse_args(argv[1:])

    write_header(sys.stdout, args)
    for i, fn in enumerate(args.file):
        process(fn, args, i==0)
    write_footer(sys.stdout)

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
