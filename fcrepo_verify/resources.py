from __future__ import print_function
from hashlib import sha1
from rdflib import Graph
from re import search
import requests
import sys
from urllib.parse import urlparse, quote
from .constants import EXT_BINARY_INTERNAL, EXT_BINARY_EXTERNAL, \
    LDP_NON_RDF_SOURCE
from .utils import get_data_dir


class Resource(object):
    """Common properties of any resource."""
    def __init__(self, inputpath, config, logger):
        self.config = config
        self.origpath = inputpath
        self.logger = logger
        self.data_dir = get_data_dir(config)


class FedoraResource(Resource):
    """Properties and methods for a resource in a Fedora repository."""
    def __init__(self, inputpath, config, logger):
        Resource.__init__(self, inputpath, config, logger)
        self.location = "fedora"
        self.relpath = urlparse(self.origpath).path.rstrip("/")
        head_response = self.fetch_headers()

        # handle various HTTP responses
        if head_response.status_code == 200:
            self.is_reachable = True
            self.headers = head_response.headers
            if inputpath.endswith("/fcr:versions"):
                # before fcrepo-4.8.0, fcr:versions does have ldp_type in
                # the header
                # todo remove when FCREPO-2511 is resolved in all supported
                # versions of fcrepo4 core.
                self.ldp_type = "http://www.w3.org/ns/ldp#RDFSource"
            else:
                self.ldp_type = head_response.links["type"]["url"]
            self.external = False
        elif head_response.status_code == 307:
            self.is_reachable = True
            self.headers = head_response.headers
            self.ldp_type = head_response.links["type"]["url"]
            self.external = True
        elif head_response.status_code in [401, 403, 404]:
            self.is_reachable = False
            self.type = "unknown"
        else:
            self.console.error("Unexpected response from Fedora")
            sys.exit(1)

        # analyze resources that can be reached
        if self.is_binary():
            self.type = "binary"
            self.metadata = self.origpath + "/fcr:metadata"
            self.sha1 = self.lookup_sha1()
            if self.external:
                self.destpath = quote(
                    (self.data_dir + self.relpath + EXT_BINARY_EXTERNAL)
                    )
            else:
                self.destpath = quote(
                    (self.data_dir + self.relpath + EXT_BINARY_INTERNAL)
                    )
        else:
            self.type = "rdf"
            self.destpath = quote(
                (self.data_dir + self.relpath + self.config.ext)
                )
            response = requests.get(self.origpath, auth=self.config.auth)
            if response.status_code == 200:
                self.graph = Graph().parse(
                    data=response.text, format="text/turtle"
                    )

    def fetch_headers(self):
        return requests.head(url=self.origpath, auth=self.config.auth)

    def is_binary(self):
        return self.ldp_type == LDP_NON_RDF_SOURCE

    def filter_binary_refs(self):
        for (s,p,o) in self.graph:
            if o.startswith(self.config.repobase) and \
                FedoraResource(o, self.config, self.logger).is_binary():
                    self.graph.remove((s,p,o))

    def lookup_sha1(self):
        result = ""
        response = requests.get(self.metadata, auth=self.config.auth)
        if response.status_code == 200:
            m = search(
                r"premis:hasMessageDigest[\s]+<urn:sha1:(.+?)>", response.text
                )
            result = m.group(1) if m else ""
        return result


class LocalResource(Resource):
    """Properties and methods for a resource serialized to disk."""
    def __init__(self, inputpath, config, logger):
        Resource.__init__(self, inputpath, config, logger)
        self.location = "local"
        self.relpath = self.origpath[len(self.data_dir):]
        urlinfo = urlparse(config.repo)
        config_repo = urlinfo.scheme + "://" + urlinfo.netloc
        self.type = "unknown"

        if self.is_binary():
            self.type = "binary"
            self.external = False
            if self.origpath.endswith(EXT_BINARY_EXTERNAL):
                self.external = True

            if self.external:
                self.destpath = config_repo + \
                        self.relpath[:-len(EXT_BINARY_EXTERNAL)]
            else:
                self.destpath = config_repo + \
                        self.relpath[:-len(EXT_BINARY_INTERNAL)]

            self.sha1 = self.calculate_sha1()
        elif self.origpath.startswith(self.data_dir) and \
                self.origpath.endswith(config.ext):
            self.type = "rdf"
            self.destpath = config_repo + self.relpath[:-len(config.ext)]
            self.graph = Graph().parse(
                location=self.origpath, format=config.lang
                )
        else:
            msg = "RDF resource lacks expected extension!".format(
                    self.origpath)
            self.logger.error(msg)

    def is_binary(self):
        if self.origpath.endswith(EXT_BINARY_INTERNAL) or \
                self.origpath.endswith(EXT_BINARY_EXTERNAL):
            return True
        else:
            return False

    def calculate_sha1(self):
        with open(self.origpath, "rb") as f:
            sh = sha1()
            while True:
                data = f.read(8192)
                if not data:
                    break
                sh.update(data)
        return sh.hexdigest()
