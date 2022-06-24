# -*- coding: utf-8 -*-
import json
import os
import sys
import appdirs
import importlib
import argparse
from loguru import logger
import jiraconnector
import csv_to_redmine
from pathlib import Path
import datetime
from env_helper import get_appdata, get_temp


def get_config():
    with open("config.json", "r+", encoding="utf-8") as json_data_file:
        config = json.load(json_data_file)
    return config

config = get_config()



def get_build_info():
    with open("jirator.json", "r+") as json_data_file:
        cfg = json.load(json_data_file)
        dev_build_date = cfg["dev_build_date"]
        dev_build_no = cfg["dev_build_no"]

    logger.info("jirator Build %s (%s)" % (dev_build_no, dev_build_date))
    return dev_build_no



def main():
    config = get_config()

    logger_directory = Path(config["log_directory"])
    logger_filename = "jirator.log"
    logger_filepath = logger_directory / logger_filename

    logger.remove()
    logger_c = logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )

    logger_f = logger.add(logger_filepath, level="INFO", encoding="utf8", rotation="1 day", retention="14 days")

    dev_build_no = get_build_info()

    parser = argparse.ArgumentParser(
        description="jirator (Build %s)\nSynchronize Jira issues to Redmine tickets" % dev_build_no
    )
    parser.add_argument(
        "operation",
        metavar="Operation",
        help="Select which operation to perform",
        choices=["query", "filter", "batch", "test"],
        default="batch",
    )
    parser.add_argument("-f", "--filter", metavar="Filter/JQL", help="Filter name or JQL query to use")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug output")
    parser.add_argument("-t", "--trace", action="store_true", help="Enable trace output")

    args = parser.parse_args()

    if args.debug:
        logger.remove(logger_c)
        logger.remove(logger_f)
        logger_c = logger.add(
            sys.stderr,
            level="DEBUG",
            format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        )
        logger_f = logger.add(
            config["log_directory"] + "\\%s_{time}.log" % (__file__), level="DEBUG", encoding="utf8"
        )
        logger.debug("DEBUG message output enabled")

    if args.trace:
        logger.remove(logger_c)
        logger.remove(logger_f)
        logger_c = logger.add(
            sys.stderr,
            level="TRACE",
            format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        )
        logger_f = logger.add(
            config["log_directory"] + "\\%s_{time}.log" % (__file__), level="TRACE", encoding="utf8"
        )
        logger.trace("TRACE message output enabled")

    output = jiraconnector.cli(args.operation, args.filter)
    if output:
        for csvfile in output:
            csv_to_redmine.cli(csvfile)


if __name__ == "__main__":
    main()
