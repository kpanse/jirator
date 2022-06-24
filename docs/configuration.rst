Configuration
#############

You need to configure *jirator* for your specific use-case. All configuration settings are available in ``config.json``.
``config.json`` is written in JSON format, refer to https://www.w3schools.com/js/js_json_syntax.asp.



Redmine
*******

``RMServerURL`` tells the app where to find your Redmine server:

.. code-block:: javascript

    "RMServerURL" : "https://kap02.kpit.com"



``RMApiKey`` is your Redmine user (or even better a dedicated admin user) API key for authentication:

.. code-block:: javascript

    "RMApiKey" : "50891f25e1b6ff34667f26dd505da79926d8d01b"



``RMProjectName`` defines the Redmine project which will be used:

.. code-block:: javascript

    "RMProjectName" : "testing-on-vip-test-benches"



``RMTrackerName`` defines the Redmine tracke which will be used for creating issues:

.. code-block:: javascript    

    "RMTrackerName" : "JIRA Tracker"



``RMUserRenames`` is a dictionary of name pairs in case your Redmine users have different names than the JIRA users. The dictionary's item key is the JIRA display name, the item value is the Redmine username.

.. code-block:: javascript

    "RMUserRenames" : {
        "Balayet Bhuiyan": "Md. Bhuiyan",
        "Benjamin Wiessneth": "Benjamin Wießneth",
        "Camelia Morhan": "Elena Antici"
    }



JIRA
****

``JIRAServerURL`` defines the JIRA server to connect to:

.. code-block:: javascript    

    "JIRAServerURL" : "https://asc.bmw.com/jira"



``JIRALinkURLs`` can be used to automatically fill the Redmines issue's description with links to those JIRA URLs:

.. code-block:: javascript    
    
    "JIRALinkURLs" : ["https://asc.bmw.com/jira/browse/","https://asc.bmwgroup.net/jira/browse/"]



``JIRAFiltersForExport`` is a dictionary of JIRA JQL querys the app will import when run in ``batch`` mode. Each filter needs an unique name and a valid JQL query string.

.. code-block:: javascript

    "JIRAFiltersForExport": {
        "VIP_AP1_0520": "key in childIssuesOf(CCB-4364) AND updated > -2d",
        "VIP_AP2_0520": "key in childIssuesOf(CCB-4365) AND updated > -2d",
    }



``JIRAFieldsForExport`` defines which fields from a given JIRA issue are considered for export/import.

.. code-block:: javascript

    "JIRAFieldsForExport" : [   "Assignee", "Summary", "Labels", "Component/s" ]



``JIRAFieldsWithDateTime`` defines which JIRA issue fields shall be considered as date or time values.

.. code-block:: javascript

    "JIRAFieldsWithDateTime" : ["Created", "Updated", "Duedate", "Resolved"],
