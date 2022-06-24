Components
##########

``jiraconnector.py`` - Jira CSV export
**************************************

* Automatic export issues per pre-defined filters
* Generate CSV data as if the user would export it from Jira (compatibility & portability)



``jira_csv_parser.py`` - CSV parser/converter for Redmine
*********************************************************

* Date and time data gets converted to datetime objects
* Rename data fields to match Redmine names (e.g. „Summary“ from Jira  „subject“ in Redmine)
* Replace data (e.g. some usernames are different in Jira and Redmine)



``csv_to_redmine.py`` - Redmine CSV import
******************************************

* Synchronize data to existing Redmine tickets based on the Jira key (Custom field in Redmine)
* Create non-existing Redmine issues on the fly and populate them with the Jira data
