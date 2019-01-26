"""
zoho_crm_connector
~~~~~~~~

:copyright: (c) 2019 by GrowthPath Pty Ltd
:licence: MIT, see LICENCE.txt for more details.

This library is based on Zoho's python sdk but is simplified, more pragmatic and modernised.

No database dependency is included. Short-lived access tokens are written to a text file with no alternative at present.

Multi-page requests are returned with yield (so they are generators).

pytest tests are included. You will need to provide authentication details; the tests assume these are in environment variables.

The Zoho licence is not specified at the time I referred to it, so I assumed public domain
"""


import json
import logging
import urllib.parse
from pathlib import Path
from datetime import datetime
from typing import Optional,Tuple
import requests
from requests.adapters import HTTPAdapter,Retry



logger = logging.getLogger()


def _requests_retry_session(
        retries=10,
        backoff_factor=2,
        status_forcelist=(500, 502, 503, 504,429),
        session=None,
        ) -> requests.Session:
    session = session or requests.Session()
    """  A set of integer HTTP status codes that we should force a retry on.
        A retry is initiated if the request method is in ``method_whitelist``
        and the response status code is in ``status_forcelist``."""
    retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


# requests hook to get new token if expiry
def __hook(self, res, *args, **kwargs):
    if res.status_code == requests.codes.unauthorized:
        logger.info('Token expired, refreshing')
        self.auth() # sets the token on self.__session

        req = res.request
        logger.info('Resending request', req.method, req.url, req.headers)
        req.headers['Authorization'] = self.__session.headers['Authorization'] # why is it needed?

        return self.__session.send(res.request)




class Zoho_crm:
    """ An authenticated connection to zoho crm.

    Initialise a Zoho CRM connection by providing authentication details including a refresh token.

    Access tokens are obtained when needed.

    The base_url defaults to the live API for US usage;
        another base_url can be provided (for the sandbox API, for instance)"""

    def __init__(self,refresh_token:str,client_id:str,client_secret:str,token_file_dir:Path,
                 base_url=None,
                 default_zoho_user_name:str=None,
                 default_zoho_user_id:str=None):
        """ Initialise a Zoho CRM connection by providing authentication details including a refresh token.
        Access tokens are obtained when needed. The base_url defaults to the live API for US usage;
        another base_url can be provided (for the sandbox API, for instance)
        """
        token_file_name = 'access_token.json'
        self.requests_session = _requests_retry_session()
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url or "https://www.zohoapis.com/crm/v2/"
        self.zoho_user_cache = None #type: dict
        self.default_zoho_user_name = default_zoho_user_name
        self.default_zoho_user_id = default_zoho_user_id
        self.token_file_path = token_file_dir / token_file_name
        self.current_token =self._load_access_token()


    def _validate_response(self, r:requests.Response)->Optional[dict]:
        """ Called internally to deal with Zoho API responses. Will fetch a new access token if necessary.
        Not all errors are explicity handled; errors not handled here have no recovery option anyway,
        so an exception is raised."""
        # https://www.zoho.com/crm/help/api/v2/#HTTP-Status-Codes
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 201:
            return {'result':True} #insert succeeded
        elif r.status_code == 202: #multiple insert succeeded
            return {'result':True}
        elif r.status_code == 204: #co content
            return None
        elif r.status_code == 304:  # nothing changed since the requested modified-since timestamp
            return None
        elif r.status_code == 401:
            #assume invalid token
            self._refresh_access_token()
            #retry the request somehow
            # probably should use a 'retry' exception?
            orig_request = r.request
            orig_request.headers['Authorization'] = 'Zoho-oauthtoken ' + self.current_token['access_token']
            new_resp = self.requests_session.send(orig_request)

            return new_resp.json()
        else:
            raise RuntimeError(f"API failure trying: {r.reason} and status code: {r.status_code} and text {r.text}, attempted url was: {r.url}, unquoted is: {urllib.parse.unquote(r.url)}")


    def yield_page_from_module(self, module_name:str, criteria:str=None, parameters:dict=None,modified_since:datetime=None)->Optional[dict]:
        """ Yields a page of results. Usually called for you by a helper member function, such as get_users
        the API is different for module queries and User queries.

        For use of the criteria parameter, please see search documentation: https://www.zoho.com/crm/help/api-diff/searchRecords.html"""
        page = 1
        if not criteria:
            url = self.base_url + module_name
        else:
            url = self.base_url + f'{module_name}/search'

        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        parameters = parameters or {}
        if criteria:
            parameters['criteria'] = criteria
        if modified_since:
            headers['If-Modified-Since'] = modified_since.isoformat()
        while True:
            parameters['page'] = page
            r = self.requests_session.get(url=url, headers=headers, params=urllib.parse.urlencode(parameters))

            r_json = self._validate_response(r)
            if not r_json:
                return None
            if 'data' in r_json:
                yield r_json['data']
            else:
                raise RuntimeError(f"Did not receive the expected data format in the returned json when: url={url} parameters={parameters}")
            if 'info' in r_json:
                if not r_json['info']['more_records']:
                    break
            else:
                break
            page += 1


    def get_users(self,user_type:str=None)->dict:
        """
        Get zoho users, filtering by a Zoho CRM user type. The default value of None is mapped to 'AllUsers'
        """
        if self.zoho_user_cache is None:
            user_type = 'AllUsers' or user_type
            url = self.base_url + f"users?type={user_type}"
            headers={'Authorization':'Zoho-oauthtoken ' + self.current_token['access_token']}
            r = self.requests_session.get(url=url,headers=headers)
            self.zoho_user_cache =  self._validate_response(r)
        return self.zoho_user_cache


    def finduser_by_name(self, full_name:str)->Tuple[str, str]:
        """ Tries to reutn the user as a tuple(full_name,Zoho user id), using the full full_name provided.
            The user must be active. If no such user is found, return the default user provided
            at initialisation of the Zoho_crm object."""
        users = self.get_users()
        default_user_name = self.default_zoho_user_name
        default_user_id = self.default_zoho_user_id
        for user in users['users']:
            if user['full_name'] == full_name.strip():
                if user['status'] == 'active':
                    return full_name, user['id']
                else:
                    logger.debug(f"User is inactive in zoho crm: {full_name}")
                    return default_user_name, default_user_id

        #not found
        logger.info(f"User not found in zoho: {full_name}")
        return default_user_name,default_user_id


    def get_record(self,module_name,id)->dict:
        """ Call the get record endpoint with an id"""

        url = self.base_url + f'{module_name}/{id}'
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        r = self.requests_session.get(url=url, headers=headers)
        r_json = self._validate_response(r)
        return r_json['data'][0]


    def create_zoho_account(self,data:dict)->Tuple[bool,dict]:
        """creation is done with the Record API and module "Accounts".
        Returns a tuple with a success boolean, and the entire record if successful.
        If unsuccessful, it returns the json data in the API reply.
        See https://www.zoho.com/crm/help/api/v2/#create-specify-records
        """
        module_name = "Accounts"
        url = self.base_url + f'{module_name}'
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        if 'trigger' not in data:
            data['trigger'] = []
        r = self.requests_session.post(url=url,headers=headers,json=data)

        if r.ok:
            account_id = r.json()['data'][0]['details']['id']
            return True,self.get_record(module_name=module_name,id=account_id)
        else:
            return False,r.json()

    def create_zoho_contact(self,data:dict)->Tuple[bool,dict]:
        """creation is done with the Record API and module "Contacts".
        Returns a tuple with a success boolean, and the entire record if successful.
        If unsuccessful, it returns the json data in the API reply.
        See https://www.zoho.com/crm/help/api/v2/#create-specify-records
               """
        module_name = "Contacts"
        url = self.base_url + f'{module_name}'
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        if 'trigger' not in data:
            data['trigger'] = []

        r = self.requests_session.post(url=url, headers=headers, json=data)

        if r.ok and r.status_code in (200,201):
            contact_id = r.json()['data'][0]['details']['id']
            return True, self.get_record(module_name=module_name, id=contact_id)
        else:
            return False, r.json()


    def create_zoho_quote(self,data:dict)->Tuple[bool,dict,Optional[str]]:
        """ Creates a Deal (aka potential).
        The returned result is  a tuple, the last being ID of new record.
        creation is done with the Record API, module is Deals.
        # https://www.zoho.com/crm/help/api/v2/#create-specify-records
        """
        module_name = "Deals"
        url = self.base_url + f'{module_name}'
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        if 'trigger' not in data:
            data['trigger'] = []
        r = self.requests_session.post(url=url,headers=headers,json={'data':[data]})
        if r.ok:
            json_result = r.json()
            try:
                details = json_result['data'][0]['details']['id']
            except KeyError:
                raise
            return True,json_result,json_result['data'][0]['details']['id']
        else:
            return False,r.json(),None


    def update_zoho_quote(self,data:dict)->Tuple[bool,dict]:
        """ updates an existing Dear with the data in the dict. Returns success boolean
        and the json results of the API put"""
        module_name = "Deals"
        url = self.base_url + f"{module_name}/{data['id']}"
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        if 'trigger' not in data:
            data['trigger'] = []
        r = self.requests_session.put(url=url, headers=headers, json={'data':[data]})

        if r.ok and r.status_code == 200:
            return True, r.json()
        else:
            return False, r.json()


    def delete_zoho_quote(self,quote_id)->Tuple[bool,dict]:
        """ deletes a deal based on the Zoho id matching quote_id"""
        module_name = "Deals"
        url = self.base_url + f"{module_name}"
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        r = self.requests_session.delete(url=url, headers=headers, params={'ids': quote_id})

        if r.ok and r.status_code == 200:
            return True, r.json()
        else:
            return False, r.json()


    def _load_access_token(self)->dict:
        try:
            with self.token_file_path.open() as data_file:
                data_loaded = json.load(data_file)
                # validate it
                url = self.base_url + f"users?type='AllUsers'"
                headers = {'Authorization': 'Zoho-oauthtoken ' + data_loaded['access_token']}
                r = self.requests_session.get(url=url, headers=headers)
                r = self.requests_session.post(url=url)
                if r.status_code == 401:
                    data_loaded = self._refresh_access_token()

                return data_loaded
        except (KeyError,FileNotFoundError,IOError) as e:
            new_token = self._refresh_access_token()
            return new_token


    def _refresh_access_token(self)->dict:
        """ This forces a new token so it should only be called
        after we know we need a new token.
        Use load_access_token to get a token, it will call this if it needs to."""
        url=(f"https://accounts.zoho.com/oauth/v2/token?refresh_token="
             f"{self.refresh_token}&client_id={self.client_id}&"
             f"client_secret={self.client_secret}&grant_type=refresh_token")
        r = requests.post(url=url)
        if r.status_code == 200:
            new_token = r.json()
            logger.info(f"New token: {new_token}")
            if 'access_token' not in new_token:
                logger.info(f"Token does not look valid")
            self.current_token = new_token
            with self.token_file_path.open('w') as outfile:
                json.dump(new_token, outfile)
            return new_token
        else:
            raise RuntimeError(f"API failure trying to get access token: {r.reason}")







