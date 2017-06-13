from __future__ import print_function
from hashlib import sha1
from rdflib import Graph
from re import search
import requests
import sys
import os
from urllib.parse import urlparse, quote
from .constants import EXT_BINARY_INTERNAL, EXT_BINARY_EXTERNAL, \
    LDP_NON_RDF_SOURCE, MINIMAL_HEADER
from .utils import get_data_dir, replace_strings_in_file


class Resource(object):
    """Common properties of any resource."""
    def __init__(self, inputpath, config, logger):
        self.config = config
        self.origpath = inputpath
        self.logger = logger
        self.data_dir = get_data_dir(config)

    def fetch_headers(self, origpath, auth):
        return requests.head(url=origpath, auth=auth)


class FedoraResource(Resource):
    """Properties and methods for a resource in a Fedora repository."""
    def __init__(self, inputpath, config, logger):
        Resource.__init__(self, inputpath, config, logger)
        self.location = "fedora"
        self.relpath = urlparse(self.origpath).path.rstrip("/")
        head_response = self.fetch_headers(self.origpath, self.config.auth)

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
            minimal_resp = requests.get(
                self.origpath, auth=self.config.auth, headers=MINIMAL_HEADER
                )
            if response.status_code == 200 and minimal_resp.status_code == 200:
                self.graph = Graph().parse(
                    data=response.text, format="text/turtle"
                    )
                self.minimal = Graph().parse(
                    data=minimal_resp.text, format="text/turtle"
                    )
                self.server_managed = self.graph - self.minimal
            else:
                self.console.error("Cannot verify RDF resource!")

    def is_binary(self):
        return self.ldp_type == LDP_NON_RDF_SOURCE

    def filter_binary_refs(self):
        for (s, p, o) in self.graph:
            if o.startswith(self.config.repobase) and \
                    FedoraResource(o, self.config, self.logger).is_binary():
                self.graph.remove((s, p, o))

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

        self.mapfrom = self.config.mapFrom
        self.mapto = self.config.mapTo

        self.type = "unknown"

        if self.is_binary():
            self.type = "binary"
            self.external = False
            if self.origpath.endswith(EXT_BINARY_EXTERNAL):
                self.external = True

            if self.external:
                self.destpath = self._resolve_dest_path(EXT_BINARY_EXTERNAL)
            else:
                self.destpath = self._resolve_dest_path(EXT_BINARY_INTERNAL)
            self.sha1 = self.calculate_sha1()
        elif self.origpath.startswith(self.data_dir) and \
                self.origpath.endswith(config.ext):
            self.type = "rdf"
            self.destpath = self._resolve_dest_path(config.ext)

            # replace mapfrom with mapto if mapped otherwise load origpath
            localfilepath = self.origpath

            if self.config.mapFrom is not None:
                localfilepath = replace_strings_in_file(self.origpath,
                                                        self.mapfrom,
                                                        self.mapto)

            self.graph = Graph().parse(
                location=localfilepath, format=config.lang
                )

            if self.config.mapFrom is not None:
                os.remove(localfilepath)

        else:
            msg = "RDF resource lacks expected extension!".format(
                    self.origpath)
            self.logger.error(msg)

    def _resolve_dest_path(self, suffix):

        # remove suffix of relpath
        relative_path = self.relpath[:-len(suffix)]
        # if mapped
        if self.mapfrom is not None:
            # reconstruct source uri
            sourceuri = self._get_base_uri(urlparse(self.mapfrom)) + \
                relative_path
            return sourceuri.replace(self.mapfrom, self.mapto)
        else:
            desturlinfo = urlparse(self.config.repo)
            return self._get_base_uri(desturlinfo) + relative_path

    def _get_base_uri(self, urlinfo):
        return urlinfo.scheme + "://" + urlinfo.netloc

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
