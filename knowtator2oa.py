#!/usr/bin/env python

"""Convert Knowtator XML into Open Annotation format."""

import os
import sys
import six
import json

# python 2.5
import uuid
import xml.etree.ElementTree as ET

usage = '%s FILE [FILE [...]]' % os.path.basename(__file__)

DOCUMENT_ID_ROOT = 'http://craft.ucdenver.edu/document/PMID-'
ANNOTATION_ID_ROOT = 'http://craft.ucdenver.edu/annotation/'
ANNOTATOR_ID_ROOT = 'http://kabob.ucdenver.edu/annotator/'

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
        self.id = ANNOTATION_ID_ROOT + 'TODO!' #str(uuid.uuid4()) # random uuid
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
    'independent_continuant': 'purl.obolibrary.org/obo/BFO_0000004',
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

def pretty_print(doc):
    return json.dumps(doc, sort_keys=True, indent=2, 
                      separators=(',', ': '))

def convert(annotations, mentions, slots, doc_id):
    # There should be exactly one mention for each annotation. The two
    # are connected by annotation.mention_id == mention.id
    assert len(annotations) == len(mentions)
    mention_by_id = { m.id: m for m in mentions }
    slot_by_id = { s.id: s for s in slots }

    converted = []
    for annotation in annotations:
        mention = mention_by_id[annotation.mention_id]
        values = mention.values(slot_by_id)
        converted.append({
            oa_id:          annotation.id,
            oa_hasTarget:   annotation.targets(doc_id),
            oa_hasBody:     ids_to_uris(values),
            oa_annotatedBy: annotation.annotator,
            #oa_annotatedAt: # Knowtator XML doesn't include this
            })
    return converted

def parse(fn):
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

    return annotations, mentions, slots, doc_id

def process(fn):
    try:
        parsed = parse(fn)
    except:
        print >> sys.stderr, 'Failed to parse %s' % fn
        raise
    for c in convert(*parsed):
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
