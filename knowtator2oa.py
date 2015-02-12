#!/usr/bin/env python

"""Convert Knowtator XML into Open Annotation format."""

import os
import sys
import json

# python 2.5
import uuid
import xml.etree.ElementTree as ET

usage = '%s FILE [FILE [...]]' % os.path.basename(__file__)

DOCUMENT_ID_ROOT = 'http://craft.ucdenver.edu/document/PMID-'
ANNOTATION_ID_ROOT = 'http://craft.ucdenver.edu/annotation/'
ANNOTATOR_ID_ROOT = 'http://kabob.ucdenver.edu/annotator/'

# attribute name constants
a_id = 'id'
a_source = 'textSource'
a_start = 'start'
a_end = 'end'

# tag name constants
t_annotation = 'annotation'
t_span = 'span'
t_text = 'spannedText'
t_annotator = 'annotator'
t_mention = 'mention'
t_mclass = 'mentionClass'

# OA constats
oa_id = '@id'
oa_hasTarget = 'hasTarget'
oa_hasBody = 'hasBody'
oa_annotatedAt = 'annotatedAt'
oa_annotatedBy = 'annotatedBy'

def find_only(element, tag):
    """Return the only subelement with tag."""
    s = element.findall(tag)
    assert len(s) == 1, 'expected one <%s>, got %d' % (tag, len(s))
    return s[0]

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
        expected_elements = (t_mention, t_annotator, t_span, t_text)
        assert not any(True for e in element if e.tag not in expected_elements)
        return cls(get_mention_id(element),
                   get_spans(element),
                   get_text(element),
                   get_annotator(element))

class Mention(object):
    def __init__(self, id_, class_id, class_text):
        self.id = id_
        self.class_id = class_id
        self.class_text = class_text

    def __str__(self):
        return str((self.id, self.class_id, self.class_text))

    @classmethod
    def from_element(cls, element):
        assert not any(True for e in element if e.tag != t_mclass),\
            'unexpected child: ' + ' '.join(['<%s>' % e.tag for e in element])
        mclass = find_only(element, t_mclass)
        return cls(element.attrib[a_id],
                   mclass.attrib[a_id],
                   mclass.text)

prefix_uri_map = {
    'CHEBI:': 'http://purl.obolibrary.org/obo/CHEBI_%s',
    'CL:':    'http://purl.obolibrary.org/obo/CL_%s',
    'GO:':    'http://purl.obolibrary.org/obo/GO_%s',
    'PR:':    'http://purl.obolibrary.org/obo/PR_%s',
    'SO:':    'http://purl.obolibrary.org/obo/SO_%s',
}

id_uri_map = {
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

def pretty_print(doc):
    return json.dumps(doc, sort_keys=True, indent=2, 
                      separators=(',', ': '))

def convert(annotations, mentions, doc_id):
    # There should be exactly one mention for each annotation. The two
    # are connected by annotation.mention_id == mention.id
    assert len(annotations) == len(mentions)
    mention_by_id = { m.id: m for m in mentions }

    converted = []
    for annotation in annotations:
        mention = mention_by_id[annotation.mention_id]
        converted.append({
            oa_id:          annotation.id,
            oa_hasTarget:   annotation.targets(doc_id),
            oa_hasBody:     id_to_uri(mention.class_id),
            oa_annotatedBy: annotation.annotator,
            #oa_annotatedAt: # Knowtator doesn't store this
            })
    return converted

def parse(fn):
    tree = ET.parse(fn)
    root = tree.getroot()    

    doc_id = get_document_id(root)

    annotations, mentions = [], []
    for element in root:
        if element.tag == t_annotation:
            annotations.append(Annotation.from_element(element))
        elif element.tag == 'classMention':
            mentions.append(Mention.from_element(element))
        else:
            raise ValueError('unexpected tag %s' % element.tag)

    return annotations, mentions, doc_id

def process(fn):
    try:
        annotations, mentions, doc_id = parse(fn)
    except:
        print >> sys.stderr, 'Failed to parse %s' % fn
        raise
    for c in convert(annotations, mentions, doc_id):
        print pretty_print(c)

def main(argv):
    if len(argv) < 2:
        print >> sys.stderr, 'Usage:', usage
        return 1

    for fn in argv[1:]:
        process(fn)

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
