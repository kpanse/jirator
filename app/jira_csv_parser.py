# -*- coding: utf-8 -*-

import sys
import pprint
import csv
import re
import uuid
import click
import pickle
from loguru import logger
import datetime
from jiraconnector import JiraConnector

from pathlib import Path

import json


def get_config():
    with open("config.json", "r+", encoding="utf-8") as json_data_file:
        config = json.load(json_data_file)
    return config


config = get_config()


class JIRACSVParser(object):
    """docstring for JIRACSVParser"""

    def __init__(self, report_file):
        super(JIRACSVParser, self).__init__()
        self.date_fields = ["Updated", "Due Date", "Created", "Resolved"]
        self.user_fields = ["JIRA Reporter", "JIRA Assignee"]
        self.field_names = config["FieldMappings"]
        self.redmine_users = config["RMUserRenames"]
        self.redmine_issue_types = config["RMIssueTypeMappings"]
        self.report_file = report_file
        self.csvdata = None

    def load(self):
        logger.info("-".join(["" for x in range(0, 100)]))
        logger.info("Loading CSV file %s" % self.report_file)

        self.parse()
        self.convert_headings()
        self.convert_date_fields()
        self.convert_list_fields()
        # self.convert_jira_users()
        self.convert_redmine_users()
        self.convert_redmine_issue_types()

        logger.info("Found %d rows in CSV file" % len(self.csvdata))

        return self.csvdata

    def parse(self):
        try:
            with open(self.report_file, errors="ignore", encoding="utf-8") as csvfile:
                csvreader = csv.reader(csvfile, delimiter=";", quotechar='"')
                csv_data = list()
                csv_headings = list()
                for i, row in enumerate(csvreader):
                    _data = {}
                    for j, col in enumerate(row):
                        # print(j, col)
                        if i == 0:
                            # if col not in headings:
                            csv_headings.append(col)
                        else:
                            if len(col) == 0:
                                # logger.debug("Empty cell. Skipping!")
                                continue

                            _key = csv_headings[j]
                            # logger.debug("_key = %s" % _key)
                            if _key not in _data:
                                # logger.debug("Adding %s to current row's data" % _key)
                                _data[_key] = col
                            elif type(_data[csv_headings[j]]) is not list:
                                # logger.debug("%s already in current row's data. Converting it to list of values" % _key)
                                _old_val = _data[_key]
                                _data[_key] = list()
                                _data[_key].append(_old_val)
                                _data[_key].append(col)
                            else:
                                # logger.debug("%s already in current row's data. Extending list of values" % _key)
                                _data[_key].append(col)

                    if len(_data) != 0:
                        csv_data.append(_data)
            self.csvdata = csv_data
        except TypeError:
            logger.error("Invalid input data")
            self.csvdata = None

    def convert_headings(self):
        for row in self.csvdata:
            for _from, _to in self.field_names.items():
                if _from in row:
                    row[_to] = row.pop(_from)
                elif _from.lower() in row:
                    row[_to] = row.pop(_from.lower())

    def convert_date_fields(self):
        for row in self.csvdata:
            for date_field in self.date_fields:
                if date_field in row and len(row[date_field]):
                    try:
                        row[date_field] = datetime.datetime.strptime(row[date_field], "%Y-%m-%d %H:%M").date()
                    except ValueError as e:
                        logger.error("Could not convert datefield value '%s': %s" % (row[date_field], e))
                        return None

    def convert_list_fields(self):
        for row in self.csvdata:
            for key, val in row.items():
                if type(val) is list:
                    row[key] = ", ".join(val)

    def convert_redmine_users(self):
        """Converts JIRA CSV user displayName to Redmine user displayNames (e.g. Balayet Bhuiyan -> Md. Bhuiyan)"""
        for row in self.csvdata:
            for user_field in self.user_fields:
                if user_field in row and len(row[user_field]):
                    _current_user = row[user_field]
                    if _current_user in self.redmine_users:
                        _new_user = self.redmine_users[_current_user]
                        row[user_field] = _new_user
                        logger.info("Convert %s: %s -> %s" % (user_field, _current_user, _new_user))

    def convert_redmine_issue_types(self):
        """Converts JIRA CSV user displayName to Redmine user displayNames (e.g. Balayet Bhuiyan -> Md. Bhuiyan)"""
        for row in self.csvdata:
            for user_field in ["Issue Type"]:
                if user_field in row and len(row[user_field]):
                    _current_user = row[user_field]
                    if _current_user in self.redmine_issue_types:
                        _new_user = self.redmine_issue_types[_current_user]
                        row[user_field] = _new_user
                        logger.info("Convert %s: %s -> %s" % (user_field, _current_user, _new_user))


if __name__ == "__main__":
    logger_directory = Path(config["log_directory"])
    logger_timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    logger_filename = "%s_jira_csv_parser.log" % (logger_timestamp)
    logger_filepath = logger_directory / logger_filename

    logger.remove()
    logger_c = logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )
    logger_f = logger.add(logger_filepath, level="DEBUG", encoding="utf8")
