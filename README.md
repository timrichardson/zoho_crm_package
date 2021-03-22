Zoho CRM Connector
==================

Zoho provides a Python SDK, but I found it a bit hard to use and it seems a bit complicated.
For instance, there is a dependency on mysql.
This module is a little more pragmatic and it returns pages of results with yield.
This code is in production use for some years, as of 2021. 


Install
=======

pip install zoho_crm_connector


Authenticating with Zoho CRM
============================

You need three things:

1. refresh token
2. client ID
3. client secret

These instructions are from the documentation from Zoho for the Python SDK

Step 1: Registering a Zoho Client
---------------------------------

Since Zoho CRM APIs are authenticated with OAuth2 standards, you should register your client app with Zoho. To register your app:

Visit this page https://accounts.zoho.com/developerconsole.
Click on “Add Client ID”.
Enter Client Name, Client Domain and Redirect URI.
Select the Client Type as "Web based".
Click “Create”
Your Client app would have been created and displayed by now.
The newly registered app's Client ID and Client Secret can be found by clicking Options → Edit.
(Options is the three dot icon at the right corner).

Note for Sandbox:
^^^^^^^^^^^^^^^^^

You can pass the sandbox url as the base url::

    zoho_crm = Zoho_crm(refresh_token=zoho_keys['refresh_token'],
        client_id=zoho_keys['client_id'],
        client_secret=zoho_keys['client_secret'],
        base_url='https://crmsandbox.zoho.com/crm/v2/',
        token_file_dir=tmp_path_factory.mktemp('zohocrm'))

Please note: Make a separate client ID for your sandbox testing.
Even though the process of getting a grant token and then a refresh token is exactly the same,
it seems to need a distinct client ID via the developer console.

Step 2: Generating self-authorized grant and refresh token
----------------------------------------------------------

Note
----

Zoho CRM can be hosted in different geographies. The URLs below assume you are using the .com version.
If, say, you are using .com.au (Australian hosting) then use the .com.au version of Zoho URLs.
For example, the Zoho Developer Console becomes https://accounts.zoho.com.au/developerconsole

When constructing the connector object, pass hosting = ".COM" or ".AU"
.COM is the default. 
The other geographies are not tested.


Read more about Multi DC: https://www.zoho.com/crm/developer/docs/api/v2/multi-dc.html
When using self-clients for Australia, make the request of accounts.zoho.com.au succeeds. This is contrary to Zoho's documentation

----

For self client apps, the self authorized grant token should be generated from the Zoho Developer Console (https://accounts.zoho.com/developerconsole)

Visit https://accounts.zoho.com/developerconsole
Click Options → Self Client of the client for which you wish to authorize.
Enter one or more (comma separated) valid Zoho CRM scopes that you wish to authorize in the “Scope” field and choose the time of expiry. Provide “aaaserver.profile.READ” scope along with Zoho CRM scopes.
scope can be::

    ZohoCRM.modules.all,ZohoCRM.users.all,ZohoCRM.org.all,ZohoCRM.settings.all,aaaserver.profile.READ

Copy the grant token for backup. It expires soon, so use it to make a refresh_token

Generate refresh_token from grant token by making a POST request with the URL below
You can't do POST requests by entering  in the browser:

https://accounts.zoho.com/oauth/v2/token?code={grant_token}&redirect_uri={redirect_uri}&client_id={client_id}&client_secret={client_secret}&grant_type=authorization_code

this works with curl:

``curl -d "code=1000.2f...68&redirect_uri=https://www.growthpath.com.au/callback&client_id=1000.ZZZZ...99&client_secret=bzz...123&grant_type=authorization_code" -X POST https://accounts.zoho.com/oauth/v2/token``

Copy the refresh token ... this doesn't expire, and it's how access is granted

Usage
=====
See test_zoho_crm_connector.py in tests for some examples.
Note the when searching, parentheses must be escaped. See the code.


    @pytest.fixture(scope='session')
    def zoho_crm(tmp_path_factory)->Zoho_crm:
        zoho_keys = {
            'refresh_token': os.getenv('ZOHOCRM_REFRESH_TOKEN'),
            'client_id': os.getenv('ZOHOCRM_CLIENT_ID'),
            'client_secret': os.getenv('ZOHOCRM_CLIENT_SECRET'),
            'user_id': os.getenv('ZOHOCRM_DEFAULT_USERID')
        }
        if not os.getenv("ZOHO_SANDBOX") or os.getenv("ZOHO_SANDBOX") == "True":
            zoho_crm = Zoho_crm(refresh_token=zoho_keys['refresh_token'],
                                client_id=zoho_keys['client_id'],
                                client_secret=zoho_keys['client_secret'],
                                base_url='https://crmsandbox.zoho.com/crm/v2/',
                                default_zoho_user_id=zoho_keys['user_id'],
                                hosting=".COM",
                                token_file_dir=tmp_path_factory.mktemp('zohocrm'))
        else:
            zoho_crm = Zoho_crm(refresh_token=zoho_keys['refresh_token'],
                                client_id=zoho_keys['client_id'],
                                client_secret=zoho_keys['client_secret'],
                                base_url="https://www.zohoapis.com/crm/v2/", 
                                default_zoho_user_id=zoho_keys['user_id'],
                                hosting=".COM",
                                token_file_dir=tmp_path_factory.mktemp('zohocrm'))

    return zoho_crm



Testing
=======
pytest needs to be installed.

Warning: testing writes an access token to a temporary directory provided by pytest, on linux this is a subdirectory of /tmp.
testing needs a connection to zoho. Set three environment variables, because this is what the tests look for::

    refresh_token': os.getenv('ZOHOCRM_REFRESH_TOKEN'),
    client_id': os.getenv('ZOHOCRM_CLIENT_ID'),
    client_secret': os.getenv('ZOHOCRM_CLIENT_SECRET')

    and also set a Zoho user id as the default user (ZOHOCRM_DEFAULT_USERID). This is an internal Zoho id value, not a user name.


Uploading
=========
python3 setup.py sdist bdist_wheel
 python3 -m twine upload --skip-existing dist/*


Changes
========
v 0.4.0: No longer retry when API limit is reached, raise an exception instead. 
Reason: the Zoho CRM API rate limit is 24 hour rolling, and it can take minutes to get credits back. Too long to wait.

v0.4.1: small changes to readme. Also, v.0.4.0 has a test case using the IN criteria which may be interesting.