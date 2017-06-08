#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import click
import logging

from fcrepo_verify.version import __version__
from fcrepo_verify.model import Config
from fcrepo_verify.loggers import createLoggers
from fcrepo_verify.verifier import FedoraImportExportVerifier


class CredentialsParamType(click.ParamType):
    """A custom credentials parameter type.

    This class produces a tuple(username, password) from a string in the
    form username:password.
    """
    name = 'credentials'

    def convert(self, value, param, ctx):
        try:
            auth = tuple(value.split(":"))
            if len(auth) == 2:
                return auth
            else:
                raise ValueError
        except ValueError:
            self.fail('Credentials must be given in the form user:password.',
                      param, ctx)


@click.command()
@click.option('--outputdir', '-o', help='Path to directory for output files '
                                        'such as csv reports of the '
                                        'verification process.',
              default='output')
@click.option('--user', '-u',
              help='Repository credentials in the form of username:password',
              type=CredentialsParamType(), default=None)
@click.option('--logdir', '-l',
              help='Path to log file (to store details of verification run).',
              default='logs')
@click.option('--loglevel', '-g',
              help='Level of information to output (INFO, WARN, DEBUG, ERROR)',
              default='INFO')
@click.option('--verbose', '-v',
              help='Show detailed info for each resource checked',
              is_flag=True, default=False)
@click.version_option(__version__)
@click.argument('configfile', type=click.Path(exists=True), required=True)
def main(configfile, outputdir, user, logdir, loglevel, verbose):
    """Verify that the resources in Fedora and on disk are the same.

    Using a CONFIGFILE (i.e. path to an fcrepo-import-export configuration
    file) this utility compares two sets of Fedora resources, one in a live
    server and the other serialized to disk, and verifies that the two sets
    are the same.
    """

    level = getattr(logging, loglevel.upper(), None)
    loggers = createLoggers(level, logdir)

    loggers.console.info("version: {0}\n".format(__version__))

    # Create configuration object and setup import/export iterators
    config = Config(configfile, user, loggers, outputdir, verbose)
    # Create and execute verifier logic
    verifier = FedoraImportExportVerifier(config, loggers)
    verifier.execute()


if __name__ == "__main__":
    main()
