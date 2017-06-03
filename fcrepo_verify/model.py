import requests
import sys
from urllib.parse import urlparse
from .constants import EXT_MAP, FEDORA_HAS_VERSIONS, FEDORA_HAS_VERSION, \
    LDP_CONTAINS
from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


class Config():
    """Object representing the options from configuration file and args."""
    def __init__(self, configfile, auth, loggers, output_dir, verbose):
        console = loggers.console
        console.info(
            "Loading configuration options from {0}".format(configfile)
            )
        self.auth = auth
        self.output_dir = output_dir
        self.verbose = verbose

        # initialize config defaults (will be overidden below if in config)
        self.bag = False
        self.versions = False
        self.bin = False
        self.predicates = None

        with open(configfile, "r") as f:
            yaml_data = f.read()

        opts = load(yaml_data, Loader=Loader)

        # log the key/value pairs loaded from configuration
        console.info("Loaded the following configuration options:")
        pad = max([len(k) for k in opts.keys()])
        for key, value in opts.items():
            console.info(
                "  --> {:{align}{pad}} : {}".format(key, value,
                                                    pad=pad, align='>')
                )
            # perform special processing of configuration options as needed
            if key == "mode":
                self.mode = value
            elif key == "external":
                self.external = value
            elif key == "legacyMode":
                self.legacyMode = value
            elif key == "predicates":
                self.predicates = value.split(',')
            elif key == "overwriteTombstones":
                self.overwriteTombstones = value
            elif key == "resource":
                self.repo = value
            elif key == "inbound":
                self.inbound = value
            elif key == "dir":
                self.dir = value
            elif key == "map":
                self.map = value.split(',')
            elif key == "binaries":
                self.bin = value
            elif key == "rdfLang":
                self.lang = value
            elif key == "bag-profile":
                self.bag = True
            elif key == "versions":
                self.versions = value

        # configure default predicates if none specified
        if self.predicates is None:
            self.predicates = [LDP_CONTAINS]

        # add version predicates if version option is enabled
        if self.versions:
            self.predicates.append(FEDORA_HAS_VERSIONS)
            self.predicates.append(FEDORA_HAS_VERSION)

        # if lang not specified in config, set the ext & lang to turtle
        if not hasattr(self, "lang"):
            self.ext = ".ttl"
            self.lang = "text/turtle"
        # set the ext based on the rdfLang
        else:
            if self.lang in EXT_MAP:
                self.ext = EXT_MAP[self.lang]
            else:
                loggers.console.error(
                    "Unrecognized RDF serialization specified in config file!"
                    )
                sys.exit(1)

        # split the repository URI into base and path components
        self.repopath = urlparse(self.repo).path
        self.repobase = self.repo[:-len(self.repopath)]


class Repository():
    """Object representing a live Fedora repository."""
    def __init__(self, config, loggers):
        self.auth = config.auth
        self.path = config.repopath
        self.base = config.repobase
        self.root = self.base + self.path

    def is_reachable(self):
        try:
            response = requests.head(self.root, auth=self.auth)
            return response.status_code == 200
        except requests.ConnectionError:
            return False
