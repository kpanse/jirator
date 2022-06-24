# -*- coding: utf-8 -*-

import re
import sys
import csv
import json
import datetime
import argparse
from dateutil.parser import parse
from loguru import logger
from jira import JIRA
from jira.exceptions import JIRAError
import auth_helper
import pprint
from requests.exceptions import ConnectionError
from requests.exceptions import ReadTimeout
from pathlib import Path
import json


def get_config():
    with open("config.json", "r+", encoding="utf-8") as json_data_file:
        config = json.load(json_data_file)
    return config


config = get_config()


class JiraConnector:
    def __init__(self):
        self.jira = None
        self.connected = False
        self.connect()
        self.get_fields()

    def connect(self):
        # Authentication
        (username, password) = auth_helper.get_or_prompt()

        logger.info("Connecting to JIRA at %s" % config["JIRAServerURL"])
        try:
            self.jira = JIRA(server=config["JIRAServerURL"], basic_auth=(username, password), max_retries=3)
            self.connected = True
        except ConnectionError as e:
            logger.error("Unable to connect to JIRA at %s" % config["JIRAServerURL"])
            logger.error(e)
            self.jira = None
            self.connected = False

            logger.critical("Stopping now!")
            sys.exit(59)

        except json.decoder.JSONDecodeError as e:
            logger.error("Received invalid JSON response from JIRA at %s" % config["JIRAServerURL"])
            logger.error(e)
            self.jira = None
            self.connected = False

            logger.critical("Stopping now!")
            sys.exit(59)

        self.issue_cache = {}

    def get_issue_by_key(self, key, use_cache=True):
        logger.info("Getting JIRA issue %s" % key)
        if key in self.issue_cache and use_cache:
            logger.debug("Using cached issue")
            issue = self.issue_cache[key]
        else:
            try:
                issue = self.jira.issue(key)
            except JIRAError as e:
                logger.error("JIRAError was raised. Raw response:")
                logger.error(e)
                issue = None

            if issue:
                self.issue_cache[issue.key] = issue
            else:
                logger.error("Could not find issue for key '%s'" % key)

        return issue

    def get_assignee(self, key):
        issue = self.get_issue_by_key(key)
        logger.trace("Assignee = %s (%s)" % (issue.fields.assignee.displayName, issue.fields.assignee.name))
        return issue.fields.assignee

    def get_reporter(self, key):
        issue = self.get_issue_by_key(key)
        try:
            logger.trace("Reporter = %s (%s)" % (issue.fields.reporter.displayName, issue.fields.reporter.name))
            return issue.fields.reporter
        except AttributeError:
            logger.error("No reporter in issue")
            return None

    def get_issues_from_filter(self, filter_query):
        logger.info("Getting JIRA issues for query '%s'" % str(filter_query))
        found_issues = []

        block_size = 100
        block_num = 0

        while True:
            start_idx = block_num * block_size
            issues = []
            try:
                issues = self.jira.search_issues(filter_query, start_idx, block_size)
            except JIRAError as e:
                logger.error("There was an exception while searching for issues:")
                logger.error(e.text)

            if len(issues) == 0:
                # Retrieve issues until there are no more to come
                break

            found_issues.extend(issues)
            block_num += 1

        if found_issues:
            logger.success("Got %d JIRA issues" % len(found_issues))
            return found_issues
        else:
            logger.info("Got %d JIRA issues" % len(found_issues))
            return None

    def get_fields(self):
        # see https://community.atlassian.com/t5/Jira-questions/Re-how-to-get-customfield-value-in-python-jira-api/qaq-p/1166836/comment-id/371491#M371491
        jira_fields = self.jira.fields()
        self.jira_fieldsinternal_name = {field["name"]: field["id"] for field in jira_fields}
        self.jira_fieldsdisplay_name = {field["id"]: field["name"] for field in jira_fields}

    def prepare_data_for_export(self, issues):
        issues_for_export = list()

        for idx, issue in enumerate(issues, start=1):
            logger.info("Preparing for export %d / %d: %s" % (idx, len(issues), issue))

            # Create temporary issue where we store the data
            tmp_issue = dict()

            # Some values are top-level, like key
            tmp_issue["Key"] = issue.key

            # Some values do not follow a meaningfull naming convention at all, like Type
            tmp_issue["Type"] = issue.fields.issuetype

            if "parent" in dir(issue.fields):
                tmp_issue["Parent"] = issue.fields.parent.key
            else:
                tmp_issue["Parent"] = None

            # Some other values are within the fields property
            # Getting the data for the jira_csv_fields from the JIRA issue into the temp issue
            # This is ugly as hell, but works for now.
            for var, val in vars(issue.fields).items():

                # Ignore internal class variables
                if var.startswith("__"):
                    continue

                # Ignore parent field (idk weird behavior)
                if var.startswith("parent"):
                    continue

                # Try to get display name for current JIRA field. Skip current field if fail
                try:
                    internal_name = var
                    display_name = self.jira_fieldsdisplay_name[internal_name]
                except KeyError:
                    logger.warning("Could not find JIRA display name for field '%s'. Skipping!" % var)
                    continue

                # Checking if we want the current field's data in the CSV file
                logger.debug("Checking issue field %s / %s" % (internal_name, display_name))
                if display_name in config["JIRAFieldsForExport"]:
                    logger.debug("Exporting field %s / %s" % (internal_name, display_name))

                    field_value = str(val)

                    # Take care of date/time data fields
                    if display_name in config["JIRAFieldsWithDateTime"]:
                        if val:
                            logger.debug("Taking care of date/time field '%s'" % display_name)
                            datetime = parse(val)
                            field_value = datetime.strftime("%Y-%m-%d %H:%M")
                            logger.trace("field_value = %s" % field_value)
                        else:
                            logger.debug("No data in field '%s'" % display_name)
                            field_value = None

                    # Take care of Sprint field (it has more complex data than the others)
                    if display_name in "Sprint":
                        if val:
                            logger.debug("Taking care of special field '%s'" % display_name)
                            val = re.findall(r"name=(Sprint[ 0-9a-zA-Z]*)", str(val))
                            field_value = ",".join(val)
                            logger.trace("field_value = %s" % field_value)
                        else:
                            logger.debug("No data in field '%s'" % display_name)
                            field_value = None

                    # Take care of list values (e.g. Labels, Component/s)
                    if type(val) is list:
                        field_value = ",".join([str(v) for v in val])

                    tmp_issue[display_name] = field_value

            # Adding temporary issue to list of issues to export
            issues_for_export.append(tmp_issue)

        return issues_for_export

    def export_issues_to_csv(self, issues, filename="Export"):
        # Get a list of all issues to export to CSV
        issues_for_export = self.prepare_data_for_export(issues)

        # Get a list of all headings in a single issue
        csv_columns = list(issues_for_export[0].keys())

        # Get timestamp for filename
        export_timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        export_directory = Path(config["export_directory"])
        export_filename = export_timestamp + "_" + filename + ".csv"
        export_filepath = export_directory / export_filename

        logger.info("-".join(["" for x in range(0, 100)]))
        logger.info("Export issues to CSV file")

        Path(config["export_directory"]).mkdir(parents=True, exist_ok=True)

        # Write data to CSV file
        with open(export_filepath, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns, delimiter=";")
            writer.writeheader()
            for data in issues_for_export:
                writer.writerow(data)

        logger.success("Created CSV file '%s'" % export_filepath)
        logger.trace("file = %s" % export_filepath)

        return export_filepath


def cli(operation, filter_query=None):
    if operation == "query":
        return query_export(filter_query)
    elif operation == "filter":
        return filter_export(filter_query)
    elif operation == "batch":
        return batch_export()
    elif operation == "test":
        return test_export(filter_query)


def query_export(JIRAfilter_query):
    jc = JiraConnector()
    issues = jc.get_issues_from_filter(JIRAfilter_query)

    if issues:
        return [jc.export_issues_to_csv(issues)]
    else:
        logger.warning("Query did not return any issues")
        return None


def filter_export(JIRAfilter_name):
    jc = JiraConnector()
    try:
        JIRAfilter_query = config["JIRAFiltersForExport"][JIRAfilter_name]
    except KeyError:
        logger.error("There is no filter with the name '%s'" % JIRAfilter_name)
        logger.critical("Stopping now")
        return None

    issues = jc.get_issues_from_filter(JIRAfilter_query)
    if issues:
        return [jc.export_issues_to_csv(issues, filename=JIRAfilter_name)]
    else:
        logger.warning("Filter did not return any issues")
        return None


def batch_export():
    jc = JiraConnector()
    csv_files = []
    for JIRAfilter_name, JIRAfilter_query in config["JIRAFiltersForExport"].items():
        issues = jc.get_issues_from_filter(JIRAfilter_query)
        if issues:
            csv_file = jc.export_issues_to_csv(issues, filename=JIRAfilter_name)
            csv_files.append(csv_file)
        else:
            logger.warning("Filter did not return any issues")

    return csv_files


def test_export(JIRAfilter_query):
    jc = JiraConnector()
    issues = jc.get_issue_by_key(JIRAfilter_query)
    pprint.pprint(issues.fields.resolution)
    return jc.export_issues_to_csv(issues)


if __name__ == "__main__":
    logger_directory = Path(config["log_directory"])
    logger_timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    logger_filename = "%s_jiraconnector.log" % (logger_timestamp)
    logger_filepath = logger_directory / logger_filename

    logger.remove()
    logger_c = logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )
    logger_f = logger.add(logger_filepath, level="DEBUG", encoding="utf8")

    parser = argparse.ArgumentParser(description="CSV2Redmine")
    parser.add_argument("operation", help="Operation to perform", choices=["query", "filter", "batch"])
    parser.add_argument("-f", "--filter", help="JIRA filter name or JQL query to use")
    parser.add_argument("-dbg", "--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    if args.debug:
        logger.remove(logger_c)
        logger_c = logger.add(
            sys.stderr,
            level="DEBUG",
            format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        )
        logger.debug("Debug message output enabled")

    cli(args.operation, args.filter)
