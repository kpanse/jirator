# -*- coding: utf-8 -*-

import os
import sys
import click
import getpass
import base64
import pickle
import json
from pathlib import Path
import datetime
from loguru import logger


def get_config():
    with open("config.json", "r+") as json_data_file:
        config = json.load(json_data_file)
    return config


config = get_config()


def load():
    try:
        (username, password) = pickle.load(open("auth.pickle", "rb"))
        logger.info("Using credentials from auth file")
    except FileNotFoundError:
        logger.warning("No auth file found")
        return (None, None)
    unsafe_password = base64.b64decode(password).decode("utf-8")
    return (username, unsafe_password)


def save(username, password):
    # Encode password
    unsafe_password = base64.b64encode(password.encode("utf-8"))

    with open("auth.pickle", "wb") as handle:
        pickle.dump((username, unsafe_password), handle, protocol=3)


def delete():
    os.remove("auth.pickle")


def get_or_prompt():
    (username, password) = load()
    if username and password:
        return (username, password)
    else:
        return prompt()


def prompt():
    try:
        username = click.prompt("Please enter username", type=str)
        password = click.prompt("Please enter password", type=str)
    except click.exceptions.Abort:
        logger.error("\nUser aborted")
        return (None, None)

    save(username, password)

    return (username, password)


if __name__ == "__main__":
    logger_directory = Path(config["log_directory"])
    logger_timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    logger_filename = "%s_auth_helper.log" % (logger_timestamp,)
    logger_filepath = logger_directory / logger_filename

    logger.remove()
    logger_c = logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )
    logger_f = logger.add(logger_filepath, level="DEBUG", encoding="utf8")

    print(get_or_prompt())
