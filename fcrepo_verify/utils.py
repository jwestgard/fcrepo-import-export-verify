from .constants import LDP_NON_RDF_SOURCE
from rdflib import Graph, URIRef
from rdflib.compare import graph_diff
import requests
import sys
import fileinput
import tempfile

try:
    from os import scandir
except ImportError:
    from scandir import scandir


def get_child_nodes(node, predicates, auth, logger):
    """Get the children based on specified containment predicates."""
    # check the resource
    head = requests.head(url=node, auth=auth)
    if head.status_code in [200, 307]:
        # check if resource is binary and if so return metadata node
        if hasattr(head, "links") and "type" in head.links and head.links[
                "type"]["url"] == LDP_NON_RDF_SOURCE:
            metadata = [node + "/fcr:metadata"]
            return metadata
        else:
            # get the node's graph
            response = requests.get(url=node, auth=auth)
            graph = Graph().parse(data=response.text, format="text/turtle")
            children = []
            # get all the objects of containment triples
            for cp in predicates:
                predicate = URIRef(cp)
                children.extend(
                    [str(obj) for obj in graph.objects(subject=None,
                                                       predicate=predicate)]
                    )
            return children
    else:
        logger.error("Error communicating with repository.")
        sys.exit(1)


def get_directory_contents(localpath):
    """Get the children based on the directory hierarchy."""
    return [p.path for p in scandir(localpath)]


def get_data_dir(config):
    """Returns the root directory containing serialized fedora objects
    based on the configuration."""
    return config.dir if not config.bag else config.dir + "/data"


def replace_strings_in_file(file, find_str, replace_str):
    """Returns the path of temp file containing the replaced values"""
    temp = tempfile.mkstemp()
    path = temp[1]
    with open(path, "w") as dest:
        with fileinput.input(files=file) as f:
            for line in f:
                line = line.replace(find_str, replace_str)
                dest.write(line)
    return path


def relaxed_compare(graph1, graph2):
    '''Compare two graphs, but treat untyped literals as strings'''
    # if graphs are really identical, comparison is true
    if graph1 == graph2:
        return True
    # if different number of triples, comparison is false
    elif len(graph1) != len(graph2):
        return False
    # otherwise, get the triples that are not identical in both graphs
    else:
        in_both, in_first, in_second = graph_diff(graph1, graph2)
        # compare extra triples in first graph to second
        for (s, p ,o) in in_first:
            v = in_second.value(subject=s, predicate=p)
            if not o.eq(v):
                return False
            else:
                pass
        # compare extra triples in second graph to first
        for (s, p ,o) in in_second:
            v = in_first.value(subject=s, predicate=p)
            if not o.eq(v):
                return False
            else:
                pass
        # if no checks have failed to this point, the graphs are equal
        return True
