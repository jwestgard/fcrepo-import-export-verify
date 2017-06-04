from csv import DictWriter
import os
import datetime
import sys
import time
import threading
import traceback
from rdflib.compare import isomorphic
from bagit import Bag

from .constants import EXT_BINARY_EXTERNAL
from .iterators import FcrepoWalker, LocalWalker
from .resources import FedoraResource, LocalResource
from .model import Repository


class FedoraImportExportVerifier:
    """Contains logic for performing a verification."""
    def __init__(self, config, loggers):
        self.config = config
        self.loggers = loggers

    def verify_bag(self):
        """Verifies the structure of the bag"""
        console = self.loggers.console
        console.info("Verifying bag...")
        bag = Bag(self.config.dir)
        if bag.is_valid():
            console.info("bag is valid :)")
        else:
            console.info("bag is invalid :(")

    def execute(self):
        """Executes the verification process."""
        config = self.config
        output_dir = self.config.output_dir

        loggers = self.loggers
        logger = loggers.file_only
        console = loggers.console
        console_only = loggers.console_only

        # Check the repository connection
        repo = Repository(config, loggers)
        console.info("Testing connection to {0}...".format(repo.base))
        if repo.is_reachable():
            console.info("Connection successful.")
        else:
            console.error(
                "Connection to {0} failed. Exiting.".format(repo.base)
                )
            sys.exit(1)

        # Set up csv file, if specified
        os.makedirs(output_dir, exist_ok=True)
        datestr = datetime.datetime.today().strftime('%Y%m%d-%H%M')
        csvfilename = "{0}/report-{1}.csv".format(output_dir, datestr)
        csvfile = open(csvfilename, "w")
        fieldnames = ["number", "type", "original", "destination",
                      "verified",
                      "verification"]
        writer = DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        console.info("Starting verification...")
        if config.mode == "export":
            tree = FcrepoWalker(config, logger)
        elif config.mode == "import":
            tree = LocalWalker(config, logger)

        console.info(
            "Running verification on Fedora 4 {0}".format(config.mode)
            )

        if config.bag:
            self.verify_bag()

        console.info("Commencing resource verification...")

        success_count = 0
        failure_count = 0

        def total_count():
            return success_count + failure_count

        def log_summary(logger):
            logger.info(
                "Verified {} resources: successes = {}, failures = {}".format(
                    total_count(), success_count, failure_count)
                    )

        def count_logger():
            while(True):
                time.sleep(10)
                log_summary(console_only)

        t = threading.Thread(target=count_logger)
        t.daemon = True
        t.start()

        # Step through the tree and verify resources
        for filepath in tree:

            # iterator can return None, in which case skip
            if filepath is not None:

                try:

                    # path begins with repository base = fedora resource
                    if filepath.startswith(config.repobase):
                        original = FedoraResource(filepath, config, logger)
                        if not original.is_reachable:
                            verified = False
                            verification = "original not reachable"
                    # path begins with local root dir = local resource
                    elif filepath.startswith(config.dir):
                        original = LocalResource(filepath, config, logger)
                    # any other path indicates an error
                    else:
                        # TODO: Consider handling this error and continuing
                        logger.error(
                            "Resource in unexpected location."
                            )
                        sys.exit(1)

                    # if binaries not included in export
                    if not config.bin:
                        # skip binaries and fcr:metadata
                        if original.type == "binary" or \
                                original.origpath.endswith("/fcr:metadata"):
                            continue
                        # filter refs to binary resources from rdf resources
                        else:
                            original.filter_binary_refs()

                    # create object representing destination resource
                    if filepath.startswith(config.repobase):
                        destination = LocalResource(original.destpath,
                                                    config,
                                                    loggers.file_only)
                    elif filepath.startswith(config.dir):
                        destination = FedoraResource(original.destpath,
                                                     config,
                                                     loggers.file_only)

                    # analyze the resource type
                    if original.type == "binary":
                        if destination.origpath.endswith(EXT_BINARY_EXTERNAL):
                            verified = False
                            verification = "external resource"
                        if original.sha1 == destination.sha1:
                            verified = True
                            verification = original.sha1
                        else:
                            verified = False
                            verification = "{0} != {1}".format(
                                original.sha1, destination.sha1
                                )
                    elif original.type == "rdf":
                        for (s,p,o) in original.graph:
                            if (s,p,o) not in destination.graph:
                                print((s,p,o))
                        if isomorphic(original.graph, destination.graph):
                            verified = True
                            verification = \
                                "{0} triples".format(len(original.graph))
                        else:
                            # print([(s,p,o) for (s,p,o) in destination.graph])
                            verified = False
                            verification = ("{0}+{1} triples - mismatch"
                                            .format(
                                                len(original.graph),
                                                len(destination.graph)
                                                ))

                    logger.info(
                        "RESOURCE {0}: {1} {2}".format(
                            total_count(), original.location, original.type)
                            )

                except Exception as ex:
                    traceback.print_exc()
                    verified = False
                    verification = ("Object could not be verified: {"
                                    "0}".format(ex))

                if not verified:
                    logger.warn(
                        "Resource Mismatch \"{}\"".format(original.relpath)
                        )
                    failure_count += 1
                else:
                    success_count += 1

                if config.verbose:
                    logger.info("  rel  => {}".format(original.relpath))
                    logger.info("  orig => {}".format(original.origpath))
                    logger.info("  dest => {}".format(original.destpath))

                    logger_method = logger.info

                    if not verified:
                        logger_method = logger.warn

                    logger_method(
                        "  Verified original to copy... {0} -- {1}".format(
                            verified, verification)
                            )

                # write csv if exists
                row = {"number":       str(total_count()),
                       "type":         original.type,
                       "original":     original.origpath,
                       "destination":  original.destpath,
                       "verified":     str(verified),
                       "verification": verification}
                writer.writerow(row)

        log_summary(console)
        console.info("Verification complete")

        csvfile.close()
