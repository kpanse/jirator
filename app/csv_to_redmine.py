# -*- coding: iso-8859-1 -*-

import sys
import pprint
import csv
import re
import uuid
import click
import pickle
import argparse
from loguru import logger
import datetime
from redminelib import Redmine
from redminelib.exceptions import ValidationError, ResourceNotFoundError, ResourceAttrError, ServerError
from jiraconnector import JiraConnector
from jira_csv_parser import JIRACSVParser
from pathlib import Path

import json


def get_config():
    with open("config.json", "r+", encoding="utf-8") as json_data_file:
        config = json.load(json_data_file)
    return config


config = get_config()


class CSV2Redmine(object):
    """docstring for CSV2Redmine"""

    def __init__(self, url=None, key=None, project=None):
        super(CSV2Redmine, self).__init__()
        self._test = False

        self.url = url
        self.key = key
        self.project = project

        self.rm_user_cache = {}
        try:
            self.rm_user_cache = pickle.load(open("rm_user_cache.pickle", "rb"))
        except Exception as e:
            raise e
            
        logger.info("-".join(["" for x in range(0, 100)]))
        logger.info("Init Redmine")
        self.connect_to_redmine()
        self.get_rm_project_id()
        self.get_rm_tracker_id()
        self.get_rm_status_id()
        self.get_rm_custom_fields()

    def __del__(self):
        with open("rm_user_cache.pickle", "wb") as handle:
            pickle.dump(self.rm_user_cache, handle, protocol=3)

    def connect_to_redmine(self):
        self.redmine = Redmine(self.url, key=self.key)

    def get_rm_project_id(self):
        logger.info("Getting Redmine project ID...")
        try:
            self.project_id = self.redmine.project.get(self.project)
        except:
            logger.critical("Could not establish connecttion to Redmine. Stopping now!")
            quit()
        logger.info("Using Redmine project ID %d (%s)" % (self.project_id, self.project))

    def get_rm_tracker_id(self):
        trackers = self.redmine.tracker.all()
        self.tracker_ids = {}
        self.tracker_id_by_name = {}
        for tracker in trackers:
            self.tracker_ids[tracker.id] = tracker.name
            self.tracker_id_by_name[tracker.name] = tracker.id

    def get_rm_status_id(self):
        logger.info("Getting Redmine status IDs...")
        status_ids = self.redmine.issue_status.all()

        self.status_ids = dict()
        self.status_id_by_name = dict()
        for status_id in status_ids:
            _id = status_id.id
            _val = status_id.name
            self.status_ids[_id] = _val
            self.status_id_by_name[_val] = _id
            logger.debug("%d: %s" % (_id, _val))

        logger.info("Got %d Redmine status IDs" % len(self.status_ids))

    def get_rm_custom_fields(self):
        # logger.info("Getting Redmine custom fields...")
        # custom_fields = self.redmine.custom_field.all() # Forbidden by admin. duh
        logger.info("Getting Redmine custom fields using workaround...")
        rm_issue = self.search_issue_by_Redmine_ID(1859)
        if rm_issue:
            custom_fields = rm_issue["custom_fields"]
        else:
            logger.critical("Could not get Redmine custom fields. Stopping now!")
            sys.exit(1)

        self.custom_fields = dict()
        self.custom_field_id_by_name = dict()
        for custom_field in custom_fields:
            _id = custom_field.id
            _val = custom_field.name
            self.custom_fields[_id] = _val
            self.custom_field_id_by_name[_val] = _id
            logger.debug("%d: %s" % (_id, _val))
        logger.info("Got %d Redmine custom fields" % len(self.custom_fields))

    def get_rm_users(self):
        _no_success_counter = 0
        _no_success_limit = 10

        for i in range(0, 500):
            try:
                _user = self.redmine.user.get(i)
            except ResourceNotFoundError:
                _no_success_counter += 1
                continue

            if _user:
                user_id = _user.id
                user_lastname = _user.lastname
                user_firstname = _user.firstname
                new_user = {
                    "id": user_id,
                    "lastname": user_lastname,
                    "firstname": user_firstname,
                    "name": "%s %s" % (user_firstname, user_lastname),
                }

                if user_id not in self.rm_user_cache:
                    logger.info("Found new user %s" % new_user)
                    self.rm_user_cache[user_id] = new_user

            if _no_success_counter > _no_success_limit:
                logger.error("Stopping update due to _no_success_limit")
                break

    def get_rm_user_by_name(self, name="current"):
        logger.debug("Looking for %s" % name)
        for user_id, user_data in self.rm_user_cache.items():
            if user_data["name"] == name:
                logger.debug("Using cached user %s" % user_data)
                return user_data
        try:
            logger.info("Getting Redmine user...")
            user = self.redmine.user.get(name)
        except ResourceNotFoundError:
            logger.error("No Redmine user found for name >%s<" % name)
            return None
        return user

    def get_rm_user_by_id(self, user_id=91):
        logger.debug("Looking for %d" % user_id)
        if user_id in self.rm_user_cache:
            user = self.rm_user_cache[user_id]
            logger.debug("Using cached user %s" % user)
        else:
            logger.info("Getting Redmine user...")
            try:
                user = self.redmine.user.get(user_id)
            except ResourceNotFoundError:
                logger.error("No Redmine user found for ID >%d<" % user_id)
                return None
        return user

    def unpack_custom_fields(self, custom_fields):
        issue_custom_fields = list()
        for custom_field in custom_fields:
            _id = custom_field.id
            _name = custom_field.name
            _val = custom_field.value
            issue_custom_fields.append({"name": _name, "id": _id, "value": _val})
            logger.debug("%s (%d): %s" % (_name, _id, _val))

        return issue_custom_fields

    def pack_custom_fields(self, custom_fields):
        issue_custom_fields = list()
        for custom_field in custom_fields:
            _id = custom_field["id"]
            _val = custom_field["value"]
            issue_custom_fields.append({"id": _id, "value": _val})
        return issue_custom_fields

    def process(self, dataset):
        for idx, data in enumerate(dataset, start=1):
            logger.info("-".join(["" for x in range(0, 100)]))
            logger.info("Exporting to Redmine %d / %d: %s" % (idx, len(dataset), data["Key"]))
            update_flag = False

            # Try to get Redmine issue by searching for the 'Key' field with the JIRA id
            current_issue = self.search_issue_by_JIRA_ID(data["Key"])

            if current_issue:
                # We got an issue to use
                logger.info("Using #%d: %s" % (current_issue.id, current_issue.subject))
            else:
                # No issue in Redmine was found, creating one now
                # Display issue data to user
                logger.warning("Could not find suitable Redmine issue. Creating new issue on the fly:")
                logger.warning("")
                for key, val in data.items():
                    try:
                        logger.warning("\t\t%20s: %s" % (key, val[0 : min(60, max(60, len(val)))]))
                    except TypeError:
                        logger.warning("\t\t%20s: %s" % (key, val))
                logger.warning("")

                self.create_redmine_issue(data)

                # Search for newly created issue
                current_issue = self.search_issue_by_JIRA_ID(data["Key"])
                if current_issue:
                    logger.info("Using %d: %s" % (current_issue.id, current_issue.subject))
                else:
                    logger.error("Could not find suitable Redmine issue and creating it failed. Skipping!")
                    continue

            # --------------------------------------------------------------------------------------
            # Handle parents / sub-tickets
            if "parent" in dir(current_issue) and data.get("Parent", None) != None:
                # Check if parent has to be updated
                logger.debug("Current issue has already a parent")
                parent_issue = self.search_issue_by_JIRA_ID(data["Parent"])
                if parent_issue.id != current_issue["parent"].id:
                    logger.debug("Parent issue ID changed")
                    current_issue["parent_issue_id"] = parent_issue.id
                    update_flag = True
            elif "parent" in dir(current_issue) and data.get("Parent", None) == None:
                # Remove parent issue id from current issue
                logger.debug("Current issue has no parent anymore")
                current_issue["parent_issue_id"] = ""
                update_flag = True
            elif data.get("Parent", None) != None and "parent" not in dir(current_issue):
                # Add parent issue id to current issue
                logger.debug("Current issue has new parent")
                parent_issue = self.search_issue_by_JIRA_ID(data["Parent"])
                if parent_issue:
                    current_issue["parent_issue_id"] = int(parent_issue.id)
                    update_flag = True
                else:
                    logger.warning("Parent issue does not exist (yet)")
            else:
                logger.debug("Current issue has no parent")
                pass

            # --------------------------------------------------------------------------------------
            # Handle ticket relations
            # parent_redmine_issue = self.search_issue_by_JIRA_ID(data['Parent'])
            # # if parent_redmine_issue:
            # 	# We got two valid Redmine relations
            # 	# TODO: Check if we have a existing relation which needs to be updated
            # 	# TODO: Check if parent redmine issue does not longer exist
            # 	# TODO: Add new relation (self.redmine.issue_relation.create(issue_id=5382, issue_to_id=5381, relatation_type='relates'))
            # print(current_issue)
            # print(parent_redmine_issue)

            # quit()

            # --------------------------------------------------------------------------------------
            # Handle status/Status
            rm_field_name = "status"
            rm_field_value_id = current_issue.status.id
            rm_field_value = current_issue.status.name

            try:
                jr_value = data[rm_field_name]
            except KeyError as e:
                logger.error("CSV has no data for '%s'" % rm_field_name)
                continue

            if rm_field_value != jr_value:
                logger.info("Updating %s: %s -> %s" % (rm_field_name, rm_field_value, jr_value))
                current_issue.status_id = self.status_id_by_name[jr_value]
                update_flag = True

            # --------------------------------------------------------------------------------------
            # Handle subject/Summary
            rm_field_name = "subject"
            rm_field_value = current_issue.subject

            try:
                jr_value = data[rm_field_name]
            except KeyError as e:
                logger.error("CSV has no data for '%s'" % rm_field_name)
                continue

            if rm_field_value != jr_value:
                logger.info("Updating %s: %s -> %s" % (rm_field_name, rm_field_value, jr_value))
                current_issue.subject = jr_value
                update_flag = True

            # --------------------------------------------------------------------------------------
            # Handle Redmine assignee
            rm_field_id = None
            rm_field_value = None
            rm_field_name = "assigned_to"

            try:
                rm_field_id = str(current_issue.assigned_to)
            except ResourceAttrError:
                rm_field_id == None
                rm_field_value = ""
            else:
                rm_field_value = self.get_rm_user_by_name(rm_field_id)
            jr_field_name = "JIRA Assignee"

            try:
                jr_value = data[jr_field_name]
            except KeyError as e:
                logger.error("CSV has no data for '%s'" % jr_field_name)
                continue

            if rm_field_id != jr_value:
                _new_user = self.get_rm_user_by_name(jr_value)

                if _new_user:
                    _new_user_id = _new_user["id"]
                    _new_user_name = _new_user["name"]
                    if _new_user:
                        if rm_field_id == None:
                            logger.info(
                                "Updating %s: Unassigned -> %s (%d)"
                                % (rm_field_name, _new_user["name"], _new_user["id"])
                            )
                        else:
                            logger.info(
                                "Updating %s: %s (%d) -> %s (%d)"
                                % (
                                    rm_field_name,
                                    rm_field_value["name"],
                                    rm_field_value["id"],
                                    _new_user["name"],
                                    _new_user["id"],
                                )
                            )
                        current_issue.assigned_to_id = _new_user_id
                        update_flag = True
                else:
                    logger.warning(
                        "No Redmine user found for new assignee."
                    )

            # --------------------------------------------------------------------------------------
            # Handle custom fields
            current_issue_custom_fields = self.unpack_custom_fields(current_issue.custom_fields)
            for rm_custom_field in current_issue_custom_fields:
                logger.debug("Checking %s" % rm_custom_field)
                _rm_cf_id = rm_custom_field["id"]
                _rm_cf_value = rm_custom_field["value"]
                _rm_cf_name = rm_custom_field["name"]
                try:
                    jr_value = data[_rm_cf_name]
                except KeyError as e:
                    logger.debug("CSV has no data for custom field '%s'" % _rm_cf_name)
                    continue

                logger.debug("Checking JIRA data for %s = %s" % (_rm_cf_name, jr_value))
                logger.debug("Checking RM data for %s (%d) = %s" % (_rm_cf_name, _rm_cf_id, _rm_cf_value))

                if _rm_cf_value != jr_value:
                    logger.info("Updating %s (%d): %s -> %s" % (_rm_cf_name, _rm_cf_id, _rm_cf_value, jr_value))
                    update_flag = True
                    rm_custom_field["value"] = jr_value

            current_issue.custom_fields = self.pack_custom_fields(current_issue_custom_fields)

            if update_flag:
                logger.info("Updating Redmine ticket...")
                if self._test == False:
                    current_issue.save()
            else:
                logger.info("Skipping Redmine ticket update because nothing changed.")

        logger.info("Processing done")
        return 0

    def search_redmine_issue(self, data):
        logger.info("Trying to match Redmine ticket for current data")

        if data["Tags"] != "":
            logger.debug("Tag has data")

            rp_ccb = re.compile("CCB-([0-9]{2,})")
            rp_redmine = re.compile("#([0-9]{4,})")
            for _tag in data["Tags"]:
                rm = rp_redmine.match(_tag)
                if rm:
                    redmine_id = int(rm.group(1))
                    logger.info("Found Redmine ID in Tags = %d" % redmine_id)
                    issue = self.search_issue_by_Redmine_ID(redmine_id)
                    if issue:
                        return issue

                rm = rp_ccb.match(_tag)
                if rm:
                    ccb_id = rm.group(0)
                    logger.info("Found JIRA ID in Tags = %s" % ccb_id)
                    issue = self.search_issue_by_JIRA_ID(ccb_id)
                    if issue:
                        return issue
        else:
            logger.debug("Tag has no data")

        logger.warning("No issue found using Tag data")
        return self.search_issue_by_title(data["Description"])

    def search_issue_by_JIRA_ID(self, search_query):
        # JIRA ID
        redmine_issues = self.redmine.issue.filter(project_id=self.project, cf_31=search_query, status_id="*")
        if redmine_issues:
            return redmine_issues[0]
        else:
            logger.debug("Could not find issue for JIRA Key >%s<" % search_query)
            return None

    def search_issue_by_Redmine_ID(self, search_query):
        # Redmine ID
        # redmine_issues = self.redmine.issue.filter(
        # 	project_id=self.project, issue_id=search_query
        # )
        redmine_issues = [self.redmine.issue.get(search_query, includes=["children", "relations"])]
        if redmine_issues:
            return redmine_issues[0]
        else:
            logger.error("Could not find issue for Redmine ID >%d<" % search_query)
            return None

    def search_issue_by_title(self, search_query):
        # Title/Subject
        redmine_issues = self.redmine.issue.search('"%s"' % search_query, project_id=self.project, titles_only=True,)
        if redmine_issues:
            if len(redmine_issues) > 1:
                logger.warning("Found more than one issue.")
                return None

            return redmine_issues[0]
        else:
            logger.debug("Could not find issue for Subject >%s<" % search_query)
            return None

    def create_redmine_issue(self, data):
        new_issue = self.redmine.issue.new()
        new_issue.project_id = self.project
        new_issue.tracker_id = self.tracker_id_by_name[config["RMTrackerName"]]
        new_issue.subject = data["subject"]
        new_issue.status = self.status_id_by_name[data["status"]]

        # --------------------------------------------------------------------------------------
        # Add Jira links as description
        description_text = ""
        for jira_link_url in config["JIRALinkURLs"]:
            description_text += "%s%s\n" % (jira_link_url, data["Key"])
        new_issue.description = description_text

        rm_user = self.get_rm_user_by_name(data["JIRA Assignee"])
        rm_user_id = None
        if rm_user:
            rm_user_id = self.get_rm_user_by_name(data["JIRA Assignee"])["id"]

        if rm_user_id:
            new_issue.assigned_to_id = rm_user_id
        else:
            logger.error("Could not find assignee for new Redmine issue. Leaving it unassigned")

        new_issue.custom_fields = [
            {"id": self.custom_field_id_by_name["Key"], "value": data["Key"]},
            {"id": self.custom_field_id_by_name["Issue Type"], "value": data["Issue Type"]},
        ]

        if self._test:
            logger.info("!!!TEST!!! Created new issue #%d: %s" % (9999, new_issue.subject))
            return new_issue
        else:
            try:
                rm_issue = new_issue.save()
            except ServerError as e:
                logger.critical("Encountered ServerError when trying to create new Redmine issue")
                logger.error(e)
                return None

            logger.info("Created new issue #%d: %s" % (rm_issue.id, rm_issue.subject))
            return rm_issue


def cli(csvfile):
    csvdata = JIRACSVParser(csvfile).load()
    if csvdata:
        return CSV2Redmine(url=config["RMServerURL"], key=config["RMApiKey"], project=config["RMProjectName"]).process(
            csvdata
        )
    else:
        logger.critical("No valid CSV data received from JIRACSVParser. Stopping now!")
        sys.exit(13)


if __name__ == "__main__":
    logger_directory = Path(config["log_directory"])
    logger_timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    logger_filename = "%s_csv_to_redmine.log" % (logger_timestamp)
    logger_filepath = logger_directory / logger_filename

    logger.remove()
    logger_c = logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )
    logger_f = logger.add(logger_filepath, level="DEBUG", encoding="utf8")

    parser = argparse.ArgumentParser(description="CSV2Redmine")
    parser.add_argument("csvfile", type=str, help="CSV file to use")
    parser.add_argument("-dbg", "--debug", action="store_true", help="Enable debug output")
    parser.add_argument("-gu", "--get-users", action="store_true", help="Get Redmine users")
    args = parser.parse_args()

    if args.debug:
        logger.remove(logger_c)
        logger_c = logger.add(
            sys.stderr,
            level="DEBUG",
            format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        )
        logger.debug("Debug message output enabled")

    if args.get_users:
        CSV2Redmine(url=config["RMServerURL"], key=config["RMApiKey"], project=config["RMProjectName"]).get_rm_users()

    cli(args.csvfile)
