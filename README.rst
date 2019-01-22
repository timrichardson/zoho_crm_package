Zoho CRM Connector
------------------
Zoho provides a Python SDK, but it is Python 2.7 centric and had other
problems.

To use:

Authenticating with Zoho CRM

# notes on sandbox account: https://help.zoho.com/portal/community/topic/api-has-a-sandbox-environment


You need three things:
refresh token
client ID
client secret

These instructions are from the documentation from Zoho for the Python SDK

Step 1: Registering a Zoho Client
=================================

Since Zoho CRM APIs are authenticated with OAuth2 standards, you should register your client app with Zoho. To register your app:

Visit this page https://accounts.zoho.com/developerconsole.
Click on “Add Client ID”.
Enter Client Name, Client Domain and Redirect URI.
Select the Client Type as "Web based".
Click “Create”
Your Client app would have been created and displayed by now.
The newly registered app's Client ID and Client Secret can be found by clicking Options → Edit.
(Options is the three dot icon at the right corner).


Step 2: Generating self-authorized grant and refresh token
==========================================================

For self client apps, the self authorized grant token should be generated from the Zoho Developer Console (https://accounts.zoho.com/developerconsole)

Visit https://accounts.zoho.com/developerconsole
Click Options → Self Client of the client for which you wish to authorize.
Enter one or more (comma separated) valid Zoho CRM scopes that you wish to authorize in the “Scope” field and choose the time of expiry. Provide “aaaserver.profile.READ” scope along with Zoho CRM scopes.
scope can be

ZohoCRM.modules.all,ZohoCRM.users.all,ZohoCRM.org.all,ZohoCRM.settings.all,aaaserver.profile.READ

Copy the grant token for backup. It expires soon, so use it to make a refresh_token


Generate refresh_token from grant token by making a POST request with the URL below
You can't do POST requests by entering  in the browser:

https://accounts.zoho.com/oauth/v2/token?code={grant_token}&redirect_uri={redirect_uri}&client_id={client_id}&client_secret={client_secret}&grant_type=authorization_code

this works with curl:

curl -d "code=1000.2f...68&redirect_uri=https://www.growthpath.com.au/callback&client_id=1000.ZZZZ...99&client_secret=bzz...123&grant_type=authorization_code" -X POST https://accounts.zoho.com/oauth/v2/token

Copy the refresh token ... this doesn't expire, and it's how access is granted




