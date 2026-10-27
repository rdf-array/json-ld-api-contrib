# json-ld-api-contrib

Tests that every [rdf-array](https://github.com/rdf-array/rdf-array) JSON-LD processor can share, but that
the W3C JSON-LD suite does not contain because they test what rdf-array adds: a JSON-LD `@list` is one
sequence term `( e1 e2 … )`. Laid out like the `tests/` directory of
[json-ld-api-array](https://github.com/rdf-array/json-ld-api-array), the rdf-array fork of the W3C suite,
with the same manifest format, so a runner of one runs the other. Published at
<https://rdf-array.github.io/json-ld-api-contrib/>.

| Manifest | Tests |
|---|---|
| [tests/toRdf-manifest.jsonld](tests/toRdf-manifest.jsonld) | JSON-LD to N-Quads-array: lists, empty and nested lists, `@container: @list`, null elements, node objects, named graphs |
| [tests/fromRdf-manifest.jsonld](tests/fromRdf-manifest.jsonld) | N-Quads-array to expanded JSON-LD: a sequence is a `@list` |
| [tests/array-manifest.jsonld](tests/array-manifest.jsonld) | [JSON-LD-array](https://rdf-array.github.io/rdf-array/docs/json-ld-array.html): conventional JSON and a mapping document to N-Quads-array, or the error code of its §3.7; type `ra:JsonLdArrayToRdfTest`, with the mapping in `"mapping"` |

## How the expectations were made

[bin/build.py](bin/build.py) holds every case and writes every file. Each toRdf input is read by
jsonld-streaming-parser-array and by rdflib-array, and the two readings must be isomorphic. Each fromRdf
expectation is rdflib-array's output, with its blank nodes relabelled, and must read back to the input with
jsonld-streaming-parser-array. The JSON-LD-array tests are captured from jsonld.js-array's own test run, the
only implementation so far. `python3 bin/build.py --check` rebuilds and fails if anything would change.

Two rdflib-array number quirks, not list matters, are kept out of the cases: it writes the double `1.5` as
`"1.5"` (JSON-LD's canonical form is `"1.5E0"`), and its fromRdf writes typed numbers as native JSON numbers.
[contrib-duplicates.md](https://github.com/rdf-array/rdf-array/blob/main/management/contrib-duplicates.md) in
rdf-array/rdf-array lists which implementation test each case reproduces.
