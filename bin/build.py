#!/usr/bin/env python3
"""Build json-ld-api-contrib from the case tables below, cross-checking every expectation.

    python3 bin/build.py            write tests/ and its manifests
    python3 bin/build.py --check    write nothing; fail if a file would change

toRdf: each JSON-LD input is read by jsonld-streaming-parser-array and by rdflib-array (the rdf-array
venv's python); the two readings must be isomorphic, blank nodes inside sequences included, and the
expected N-Quads-array is that reading. fromRdf: rdflib-array writes each N-Quads-array input as
expanded JSON-LD, which is the expectation, and jsonld-streaming-parser-array must read it back to the
input graph. array: the JSON-LD-array tests are captured from jsonld.js-array's own test run
(tools/capture-jsonld-array.js in rdf-array/rdf-array), the only implementation so far.
"""
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLS = ROOT.parent / 'rdf-array' / 'tools'
sys.path.insert(0, str(TOOLS))
import rdfarray as ra  # noqa: E402

VENV_PY = os.environ.get('RDFLIB_ARRAY_PYTHON', str(ROOT.parent / '.venv-pyshex' / 'bin' / 'python'))
JSONLD_JS = pathlib.Path(os.environ.get('JSONLD_JS_ARRAY', ROOT.parent / 'jsonld.js-array'))
BASE = 'https://rdf-array.github.io/json-ld-api-contrib/tests/'
CHECK = '--check' in sys.argv
JP = 'jsonld-streaming-parser-array test/JsonLdParser-test.ts'
JS = 'jsonld-streaming-serializer-array test/lib'
RL = 'rdflib-array test/jsonld'
E = 'http://ex.org/'

TORDF = [  # name, input, purpose, duplicates
    ('li01', {'@id': E + 's', E + 'p': {'@list': ['a', 'b', 'c']}}, 'a @list of strings is one sequence term',
     [f'{JP} "a triple with an anonymous list array"']),
    ('li02', {'@id': E + 's', E + 'p': {'@list': []}}, 'an empty @list is the empty sequence, not rdf:nil', [f'{JP} "without @id and an empty list"']),
    ('li03', {'@id': E + 's', E + 'p': {'@list': [{'@list': ['a']}, {'@list': ['b', 'c']}]}}, 'nested lists are nested sequences', []),
    ('li04', {'@id': E + 's', E + 'p': {'@list': [{'@list': []}, {'@list': [{'@list': []}]}]}}, 'empty sequences nested', []),
    ('li05', {'@context': {'p': {'@id': E + 'p', '@container': '@list'}}, '@id': E + 's', 'p': ['a', 'b']},
     'an array value of a @container @list term is one sequence', [f'{JP} "a list container"']),
    ('li06', {'@id': E + 's', E + 'p': {'@list': 'a'}}, 'a single non-array @list value is a one-element sequence', []),
    ('li07', {'@id': E + 's', E + 'p': {'@list': ['a', None, 'b']}}, 'null inside a @list leaves no element', []),
    ('li08', {'@id': E + 's', E + 'p': {'@list': [{'@id': E + 'a'}, {E + 'q': 1}]}},
     'node objects as elements; a blank node element keeps its own triples', [f'{JP} "a list container" "with an inner predicate"']),
    ('li09', {'@id': E + 'g', '@graph': [{'@id': E + 's', E + 'p': {'@list': [1, 2]}}]}, 'a sequence in a named graph', []),
    ('li10', {'@context': {'@base': 'http://ex.org/base/', 'p': {'@id': E + 'p', '@type': '@id', '@container': '@list'}},
              '@id': E + 's', 'p': ['a', 'b']}, 'IRI elements resolved against @base', []),
    # (no double: rdflib-array writes 1.5 as "1.5", not JSON-LD's canonical "1.5E0" -- an rdflib quirk, not a list matter)
    ('li11', {'@id': E + 's', E + 'p': {'@list': [1, True, {'@value': 'chat', '@language': 'fr'}]}},
     'native values and a language-tagged string as elements', []),
    ('li12', {'@id': E + 's', E + 'p': {'@set': ['a', 'b']}}, 'a @set is still two values, not a sequence', []),
    ('li13', {'@id': E + 's', E + 'p': [{'@list': ['a']}, {'@list': ['a']}]}, 'two equal lists are one sequence term', []),
]
FROMRDF = [  # name, N-Quads-array input, purpose
    ('seq01', f'<{E}s> <{E}p> ("a" "b") .', 'a sequence of literals is a @list'),
    ('seq02', f'<{E}s> <{E}p> () .', 'the empty sequence is an empty @list'),
    ('seq03', f'<{E}s> <{E}p> (("a") ("b" "c")) .', 'nested sequences are nested @lists'),
    ('seq04', f'<{E}s> <{E}p> (<{E}a> _:b0) .\n_:b0 <{E}q> "c" .', 'IRI and blank node elements are node references'),
    # (string elements only: rdflib-array writes typed numbers as native JSON numbers, which JSON-LD's fromRdf does
    # only under useNativeTypes, and jsonld-streaming-parser-array cannot read a native number with an explicit @type)
    ('seq05', f'<{E}s> <{E}p> ("a") <{E}g> .', 'a sequence in a named graph'),
]


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)


def write(rel, text):
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding='utf-8') == text:
        return False
    if CHECK:
        raise SystemExit(f'{rel} would change')
    path.write_text(text, encoding='utf-8')
    return True


def relabel(quads):
    m = {}

    def lab(t):
        if t is None:
            return None
        if t[0] == 'bnode':
            m.setdefault(t, ra.bnode(f'b{len(m)}'))
            return m[t]
        if t[0] == 'seq':
            return ra.seq(lab(e) for e in t[1])
        return t
    return [tuple(lab(t) for t in q) for q in quads]


def manifest(name, label, description, entries, extra_context=None):
    ctx = {'@base': name}
    if extra_context:
        ctx.update(extra_context)
    return json.dumps({
        '@context': ['https://w3c.github.io/json-ld-api/tests/context.jsonld', ctx],
        '@id': '', '@type': 'mf:Manifest', 'name': label, 'description': description,
        'baseIri': BASE, 'sequence': entries}, indent=2) + '\n'


def main():
    problems, dups = [], []
    entries = []
    for name, doc, purpose, dup in TORDF:
        inp = f'tests/toRdf/{name}-in.jsonld'
        write(inp, json.dumps(doc, indent=2) + '\n')
        base = BASE + f'toRdf/{name}-in.jsonld'
        js = run(['node', TOOLS / 'parse-jsonld-array.js', ROOT / inp, base])
        py = run([VENV_PY, TOOLS / 'rdflib-array-jsonld.py', 'tordf', ROOT / inp, base])
        if js.returncode or py.returncode:
            problems.append(f'toRdf/{name}: {js.stderr.strip()[-150:]} {py.stderr.strip()[-150:]}')
            continue
        qj, qp = ra.parse(js.stdout), ra.parse(py.stdout)
        if not ra.isomorphic(qj, qp):
            problems.append(f'toRdf/{name}: jsonld-streaming-parser-array and rdflib-array differ:\n{js.stdout}--\n{py.stdout}')
            continue
        write(f'tests/toRdf/{name}-out.nq', ra.write(relabel(qj)))
        entries.append({'@id': f'#t{name}', '@type': ['jld:PositiveEvaluationTest', 'jld:ToRDFTest'], 'name': name,
                        'purpose': f'rdf-array: {purpose}', 'input': f'toRdf/{name}-in.jsonld', 'expect': f'toRdf/{name}-out.nq',
                        'option': {'specVersion': 'json-ld-1.1'}})
        if dup:
            dups.append({'test': f'tests/toRdf-manifest#t{name}', 'duplicates': dup})
    write('tests/toRdf-manifest.jsonld', manifest('toRdf-manifest', 'rdf-array: Transform JSON-LD to RDF (sequences)',
          'JSON-LD to rdf-array: a @list is one sequence term.', entries))
    entries = []
    for name, nq, purpose in FROMRDF:
        inp = f'tests/fromRdf/{name}-in.nq'
        write(inp, nq + '\n')
        py = run([VENV_PY, TOOLS / 'rdflib-array-jsonld.py', 'fromrdf', ROOT / inp])
        if py.returncode:
            problems.append(f'fromRdf/{name}: rdflib-array: {py.stderr.strip()[-200:]}')
            continue
        out = f'tests/fromRdf/{name}-out.jsonld'
        write(out, json.dumps(canonical(json.loads(py.stdout)), indent=2) + '\n')
        back = run(['node', TOOLS / 'parse-jsonld-array.js', ROOT / out, BASE + out[len('tests/'):]])
        if back.returncode or not ra.isomorphic(ra.parse(back.stdout), ra.read(ROOT / inp)):
            problems.append(f'fromRdf/{name}: the expected JSON-LD does not read back to the input:\n{back.stdout}{back.stderr[-200:]}')
            continue
        entries.append({'@id': f'#t{name}', '@type': ['jld:PositiveEvaluationTest', 'jld:FromRDFTest'], 'name': name,
                        'purpose': f'rdf-array: {purpose}', 'input': f'fromRdf/{name}-in.nq', 'expect': f'fromRdf/{name}-out.jsonld',
                        'option': {'specVersion': 'json-ld-1.1'}})
        dups.append({'test': f'tests/fromRdf-manifest#t{name}', 'duplicates': [f'{JS} "should emit a sequence term as a list (RDF-)"'] if name == 'seq01' else []})
    write('tests/fromRdf-manifest.jsonld', manifest('fromRdf-manifest', 'rdf-array: Transform RDF to JSON-LD (sequences)',
          'rdf-array to JSON-LD: a sequence term is a @list.', entries))
    dups = [d for d in dups if d['duplicates']]
    build_array(problems, dups)
    if problems:
        raise SystemExit('cross-check failed:\n  ' + '\n  '.join(problems))
    write('duplicates.json', json.dumps({'suite': 'json-ld-api-contrib', 'tests': dups}, indent=1) + '\n')
    print(f'{len(TORDF)} toRdf (jsonld-streaming-parser-array = rdflib-array) and {len(FROMRDF)} fromRdf tests '
          f'(rdflib-array, read back by jsonld-streaming-parser-array); array tests: {ARRAY_COUNT[0]}')


ARRAY_COUNT = [0]


def canonical(doc):
    """rdflib-array labels blank nodes at random: relabel them _:b0, _:b1, ... and order the top-level nodes,
    until both are stable, so that a rebuild writes the same file."""
    for _ in range(5):
        text = json.dumps(doc, sort_keys=True)
        labels = {}
        for m in re.finditer(r'"_:([^"]+)"', text):
            labels.setdefault(m.group(1), f'b{len(labels)}')
        text = re.sub(r'"_:([^"]+)"', lambda m: f'"_:{labels[m.group(1)]}"', text)
        new = json.loads(text)
        if isinstance(new, list):
            new.sort(key=lambda n: (str(n.get('@id', '')).startswith('_:'), json.dumps(n, sort_keys=True)))
        if new == doc:
            break
        doc = new
    return doc


def slug(title):
    t = re.sub(r'^JSON-LD-array ', '', title)
    t = re.sub(r'\(§[^)]*\)', '', t)
    return re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')[:60]


def build_array(problems, dups):
    capture = ROOT / '.capture.json'
    r = run(['npx', 'mocha', '-R', 'dot', '--require', TOOLS / 'capture-jsonld-array.js', 'tests/array.js'],
            cwd=JSONLD_JS, env={**os.environ, 'CAPTURE': str(capture)})
    if r.returncode:
        problems.append('jsonld.js-array tests/array.js fails: ' + r.stdout[-300:])
        return
    calls = json.loads(capture.read_text())
    capture.unlink()
    seen, entries = set(), []
    for c in calls:
        if c['mapping'] is None:
            continue  # a precompiled mapping: the same case as its source mapping
        key = (c['data'], c['mapping'])
        if key in seen:
            continue
        seen.add(key)
        n = f'{len(entries) + 1:04d}'
        write(f'tests/array/{n}-in.json', c['data'] + '\n')
        write(f'tests/array/{n}-mapping.json', c['mapping'] + '\n')
        e = {'@id': f'#t{n}', 'name': slug(c['title']), 'purpose': f'rdf-array: {c["title"]}',
             'input': f'array/{n}-in.json', 'mapping': f'array/{n}-mapping.json'}
        if 'error' in c:
            e['@type'] = ['jld:NegativeEvaluationTest', 'ra:JsonLdArrayToRdfTest']
            e['expectErrorCode'] = c['error']['code'] or c['error']['name']
        else:
            e['@type'] = ['jld:PositiveEvaluationTest', 'ra:JsonLdArrayToRdfTest']
            write(f'tests/array/{n}-out.nq', c['nquads'])
            e['expect'] = f'array/{n}-out.nq'
        entries.append(e)
        dups.append({'test': f'tests/array-manifest#t{n}', 'duplicates': [f'jsonld.js-array tests/array.js "{c["title"]}"']})
    write('tests/array-manifest.jsonld', manifest('array-manifest', 'rdf-array: JSON-LD-array to rdf-array',
          'Conventional JSON and a JSON-LD-array mapping to rdf-array (https://rdf-array.github.io/rdf-array/json-ld-array.html); '
          'the input is plain JSON, "mapping" the mapping document, "expect" N-Quads-array or "expectErrorCode" the error code of §3.7.',
          entries, {'ra': 'https://rdf-array.github.io/rdf-array/vocab#', 'mapping': {'@id': 'ra:mapping', '@type': '@id'}}))
    ARRAY_COUNT[0] = len(entries)


if __name__ == '__main__':
    main()
