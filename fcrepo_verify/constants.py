__author__ = 'dbernstein'

EXT_MAP = {"application/ld+json":   ".json",
           "application/n-triples": ".nt",
           "application/rdf+xml":   ".xml",
           "text/n3":               ".n3",
           "text/rdf+n3":           ".n3",
           "text/plain":            ".txt",
           "text/turtle":           ".ttl",
           "application/x-turtle":  ".ttl"
           }
LDP_NON_RDF_SOURCE = "http://www.w3.org/ns/ldp#NonRDFSource"
LDP_CONTAINS = "http://www.w3.org/ns/ldp#contains"
FEDORA_HAS_VERSION = "http://fedora.info/definitions/v4/repository#hasVersion"
FEDORA_HAS_VERSIONS = \
    "http://fedora.info/definitions/v4/repository#hasVersions"

EXT_BINARY_INTERNAL = ".binary"
EXT_BINARY_EXTERNAL = ".external"
BAG_DATA_DIR = "/data"

MINIMAL_HEADER = {"Prefer": "return=minimal"}
