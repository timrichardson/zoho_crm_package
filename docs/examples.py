#**************** These are some quick and dirty examples taken from a production usage.


import io
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import *

import pytest
import requests
from django.conf import settings
# debugging aid
from django.core.wsgi import get_wsgi_application

from cached_dear.models import KeyValueJson
from core.common_files.api_helpers import get_chunks
from core.common_files.api_helpers import core_consts as consts

application = get_wsgi_application()  # before any imports

from requests.adapters import HTTPAdapter, Retry
from zoho_crm_connector import Zoho_crm
from zoho_crm.models import ZohoCRMSettings

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
logger.addHandler(ch)


class InvalidSalesRep(Exception):
    pass


class CouldNotCreateQuote(Exception):
    pass


class CouldNotCreateZohoRecord(Exception):
    pass


def requests_retry_session(
        retries=3,
        backoff_factor=2,
        status_forcelist=(500, 502, 503, 504),
        session=None,
) -> requests.Session:
    session = session or requests.Session()
    """  A set of integer HTTP status codes that we should force a retry on.
        A retry is initiated if the request method is in ``allowed_methods``
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


# def escape_zoho_characters(input_string) -> str:
#     table = str.maketrans({'(':r'[',
#                            ')':r']'})
#     return input_string.translate(table)

def escape_zoho_characters_v2(input_string) -> str:
    """ Note: this is only needed for searching
    :param input_string:
    :return:
    """
    if r'\(' in input_string or r'\)' in input_string:
        logger.debug(f"Input string {input_string} already escaped")
        return input_string
    else:
        table = str.maketrans({'(': r'\(',
                               ')': r'\)'})
        return input_string.translate(table)


def escape_ampersand(input_string) -> str:
    """ This may fix a problem sending emails with &
    :param input_string:
    :return:
    """
    if r'\&' in input_string:
        logger.debug(f"Input string {input_string} already escaped")
        return input_string
    else:
        table = str.maketrans({'&': r'\&', })
        return input_string.translate(table)


# requests hook to get new token if expiry
def __hook(self, res, *args, **kwargs):
    if res.status_code == requests.codes.unauthorized:
        logger.info('Token expired, refreshing')
        self.auth()  # sets the token on self.__session

        req = res.request
        logger.info('Resending request', req.method, req.url, req.headers)
        req.headers['Authorization'] = self.__session.headers['Authorization']  # why is it needed?

        return self.__session.send(res.request)


def convert_datetime_to_zoho_crm_time(dt: datetime) -> str:
    return datetime.strftime(dt, "%Y-%m-%dT%H:%M:%S%z")


def convert_zoho_datetime_str_to_datetime(dt_string: str) -> datetime:
    # string format is YYYY-MM-DDTHH:MM:SS+10:00
    return datetime.strptime(dt_string, "%Y-%m-%dT%H:%M:%S%z")


class Zoho_crm_enhanced(Zoho_crm):
    # add extra features to the library module
    create_missing_contacts = False
    overwrite_zoho_contacts = False
    create_missing_zoho_accounts = False
    overwrite_zoho_accounts = False
    closing_days = 90
    zoho_quote_amounts_include_tax = True
    quote_stage_mapping = {
        "QuoteDraft": "Draft in Dear",
        "QuoteAuthorised": "Proposal/Price Quote",
        "OrderAuthorised": "Closed (Won)",
        "Voided": "DELETE",
        "DepositPaid": "Closed (Won)",
        "InvoiceAuthorised": "Closed (Won)",
        "InvoicePaid": "Closed (Won)"
    }
    quote_stage_probability = {
        "QuoteDraft": 10,
        "QuoteAuthorised": 25,
        "OrderAuthorised": 100,
        "DepositPaid": 100,
        "InvoiceAuthorised": 100,
        "InvoicePaid": 100
    }
    # include the default stage from the template, e.g. Quoted
    zoho_stages_we_can_change = [
        "Quoted",
        "Draft in Dear",
        "Qualification",
        "Value Proposition",
        "Proposal/Price Quote",
        "Negotiation/Review",
        "Closed (Won)"
    ]
    zoho_quote_custom_field_function = None
    zoho_salesrep_mapping = {}
    zoho_account_email_address = None


    def __init__(self, zoho_crm_email, **kwargs):
        self.quote_template = kwargs.pop('quote_template', None)
        self.order_template = kwargs.pop('order_template', None)
        self.account_template = kwargs.pop('account_template', None)
        self.create_missing_contacts = kwargs.pop('create_missing_contacts', self.create_missing_contacts)
        self.overwrite_zoho_contacts = kwargs.pop('overwrite_zoho_contacts', self.overwrite_zoho_contacts)
        self.create_missing_zoho_accounts = kwargs.pop('create_missing_zoho_accounts',
                                                       self.create_missing_zoho_accounts)
        self.overwrite_zoho_accounts = kwargs.pop('overwrite_zoho_accounts', self.overwrite_zoho_contacts)
        self.quote_stage_mapping = kwargs.pop('quote_stage_mapping', self.quote_stage_mapping)
        self.quote_stage_probability = kwargs.pop('quote_stage_probability', self.quote_stage_probability)
        self.zoho_stages_we_can_change = kwargs.pop('zoho_stages_we_can_change', self.zoho_stages_we_can_change)
        self.zoho_quote_custom_field_function = kwargs.pop('zoho_quote_custom_field_function',
                                                           self.zoho_quote_custom_field_function)
        self.zoho_salesrep_mapping = kwargs.pop('zoho_salesrep_mapping', self.zoho_salesrep_mapping)
        # example {"DEFAULT": {"ZohoUserName": "Jarryd Ponting"}}
        self.closing_days = kwargs.pop('closing_days', self.closing_days)
        self.job_logger = kwargs.pop('job_logger', None)
        self.zoho_crm_email = zoho_crm_email
        self.zoho_error_email_list = kwargs.pop('zoho_error_email_list', [zoho_crm_email])
        self.customer_additional_attribute_for_zoho_account_id = kwargs.pop(
            "customer_additional_attribute_for_zoho_account_id", None)
        self.additional_attributes_mapping = kwargs.pop("additional_attributes_mapping", None)
        if not self.additional_attributes_mapping:
            self.additional_attribute_mapping = KeyValueJson.get_jdata(
                f"ZOHO_CRM-{zoho_crm_email}-additional_attribute_mapping")

        super().__init__(**kwargs)

    def create_zoho_account(self, data: dict) -> Tuple[bool, dict]:
        # creation is done with the Record API
        # https://www.zoho.com/crm/help/api/v2/#create-specify-records
        module_name = "Accounts"

        url = self.base_url + f'{module_name}'
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        if 'trigger' not in data:
            data['trigger'] = []
        r = self.requests_session.post(url=url, headers=headers, json=data)

        if r.ok and r.status_code == 201:
            # get the account
            try:
                account_id = r.json()['data'][0]['details']['id']
                return True, self.get_record_by_id(module_name=module_name, id=account_id)
            except KeyError:
                logger.error(f"While creating Zoho account with {data}")
                logger.error(
                    f"returned data from Zoho create account is incomplete. Error message from Zoho: {r.json()}")
                raise
        else:
            return False, r.json()

    def delete_zoho_account(self, account_id):
        self.delete_from_module(module_name="Accounts", record_id=account_id)

    def update_zoho_accounts(self, data: dict) -> Tuple[bool, List[dict]]:
        # creation is done with the Record API
        # https://www.zoho.com/crm/help/api/v2/#create-specify-records
        module_name = "Accounts"
        url = self.base_url + f'{module_name}'
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        if 'trigger' not in data:
            data['trigger'] = []
        r = self.requests_session.put(url=url, headers=headers, json=data)

        if r.ok:
            # get the accounts
            try:
                zoho_accounts = []
                account_ids = [data_item["details"]["id"] for data_item in r.json()['data']]
                for account_id in account_ids:
                    zoho_accounts.append(self.get_record_by_id(module_name=module_name, id=account_id))
                return True, zoho_accounts
            # account_id = r.json()['data'][0]['details']['id']
            except KeyError:
                logger.exception(f"While updating Zoho account with {data} got {r}")
                print(f"While updating Zoho account with {data}")
                logger.error(
                    f"returned data from Zoho update account is incomplete. Error message from Zoho: {r.json()}")
                print(
                    f"returned data from Zoho update account is incomplete. Error message from Zoho: {r.json()}")
                raise RuntimeError(f"Error in updating Zoho account {data}, returned {str(r)}")
        else:
            return False, r.json()

    def find_zoho_accounts_by_dear_customer_id(self, dear_customer_id) -> List:
        accounts = []
        for data_block in self.yield_page_from_module(module_name='Accounts',
                                                      criteria=f'(DearGUID:equals:{dear_customer_id})'):
            accounts += data_block
        return accounts

    def find_zoho_accounts_by_account_name(self, account_name) -> List:
        accounts = []
        for data_block in self.yield_page_from_module(module_name='Accounts',
                                                      criteria=f'(Account_Name:equals:{account_name})'):
            accounts += data_block
        return accounts

    def attach_file_object_to_zoho_account(self,
                                           zoho_account_id: str,
                                           file_object: io.BytesIO,
                                           file_name: str,
                                           dear_account_id=None,
                                           job_id: int = None) -> Tuple[bool, dict]:
        module_name = "Accounts"
        url = self.base_url + f'{module_name}' + f'/{zoho_account_id}/Attachments'
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        r = self.requests_session.post(url=url, headers=headers, files={'file': (file_name, file_object)})
        if r.ok and r.status_code in (200, 201):
            record_id = r.json()['data'][0]['details']['id']
            return True, r.json()
        else:
            return False, r.json()

    def list_attachments_on_zoho_account(self, zoho_account_id: str) -> Dict:
        """ results a dict keyed by file name. """
        module_name = "Accounts"
        url = self.base_url + f'{module_name}' + f'/{zoho_account_id}/Attachments'
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        r = self.requests_session.get(url=url, headers=headers)
        attachments = {}  # key by name
        if r.ok and r.status_code in (200, 201):
            result = r.json()
            return {a["File_Name"]: a for a in result["data"]}
        else:
            return {}

    def delete_attachment_on_zoho_account(self, zoho_account_id, attachment_id) -> bool:
        module_name = "Accounts"
        url = self.base_url + f'{module_name}' + f'/{zoho_account_id}/Attachments/{attachment_id}'
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        r = self.requests_session.delete(url=url, headers=headers)
        if r.ok and r.status_code in (200, 201):
            return True
        else:
            raise RuntimeError("Could not delete attachment on Zoho account")

    def create_zoho_contact(self, data: dict) -> Tuple[bool, dict]:
        return self.update_zoho_contact(data=data, mode="create")

    def update_zoho_contact(self, data: dict, mode="update") -> Tuple[bool, dict]:
        module_name = "Contacts"
        url = self.base_url + f'{module_name}'
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        if 'trigger' not in data:
            data['trigger'] = []
        if mode == "update":
            r = self.requests_session.put(url=url, headers=headers, json=data)
        elif mode == "create":
            r = self.requests_session.post(url=url, headers=headers, json=data)
        else:
            raise RuntimeError(f"invalid mode {mode} passed to update_zoho_contact, must be one of update or create")
        if r.ok and r.status_code in (200, 201):
            contact_id = r.json()['data'][0]['details']['id']
            return True, self.get_record_by_id(module_name=module_name, id=contact_id)
        elif r.ok and r.status_code == 202:
            # mobile phone errors: the Zoho phone fields
            error_result = r.json()
            if "data" in error_result:
                error_message = error_result["data"][0]
                if error_message.get("code") == "INVALID_DATA":
                    field_api_name = error_message["details"]["api_name"]
                    payload = data["data"][0]
                    if field_api_name not in payload:
                        return False, error_result
                    # can retry since the field is available to be deleted
                    if self.job_logger:
                        self.job_logger(
                            log_message=f"Field: {field_api_name} is invalid according to Zoho in the record {payload} and it is not used for this contact",
                            status=consts.ERRORS_FOUND, )
                    del payload[field_api_name]
                    result, contact = self.update_zoho_contact(data=data, mode=mode)
                    return result, contact
            return False, r.json()
        else:
            return False, r.json()

    def create_zoho_products(self, data: dict) -> Tuple[bool, dict]:
        """ call ike data = {data={'data':[{}]"""
        module_name = "Products"
        url = self.base_url + f'{module_name}'
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        if 'trigger' not in data:
            data['trigger'] = []
        # Product_name is a required field
        for i, product_payload in enumerate(data['data'], start=1):
            if 'Product_Name' not in product_payload or not product_payload['Product_Name']:
                raise CouldNotCreateZohoRecord(
                    f"Product_Name is a required field, not provided in product {i} (1-indexed) in the payload {data=}")
        r = self.requests_session.post(url=url, headers=headers, json=data)
        if r.ok and r.status_code in (200, 201):
            record_id = r.json()['data'][0]['details']['id']
            return True, self.get_record_by_id(module_name=module_name, id=record_id)
        elif r.ok and r.status_code == 202:  # data validation error
            raise CouldNotCreateZohoRecord(f"Data validation error while trying to create Zoho CRM product: {data=}; "
                                           f"Error is: {r.text} ")
        else:
            return False, r.json()

    def update_zoho_one_product(self, data: dict) -> Tuple[bool, dict]:
        """ data looks like this: {"data": [revised_zoho_product]}) """
        if len(data["data"]) != 1:
            raise RuntimeError("There should be only one product in the payload when calling update_zoho_one_product")
        module_name = "Products"
        url = self.base_url + f'{module_name}'
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        if 'trigger' not in data:
            data['trigger'] = []
        r = self.requests_session.put(url=url, headers=headers, json=data)
        if r.ok and r.status_code in (200, 201):
            record_id = r.json()['data'][0]['details']['id']
            return True, self.get_record_by_id(module_name=module_name, id=record_id)
        else:
            return False, r.json()

    def update_zoho_many_products(self, payload: dict) -> bool:
        """ data looks like this: {"data": [revised_zoho_products]})
        """
        module_name = "Products"
        url = self.base_url + f'{module_name}'
        for product_chunk in get_chunks(payload['data'], 100):
            headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
            chunk_payload = {"data": product_chunk}
            if 'trigger' not in payload:
                chunk_payload['trigger'] = []

            r = self.requests_session.put(url=url, headers=headers, json=chunk_payload)
            if r.ok and r.status_code in (200, 201):
                continue
            else:
                return False
        return True

    def get_price_books(self)-> List:
        price_books = []
        for data_block in self.yield_page_from_module(module_name="price_books"):
            price_books += data_block
        return price_books

    def get_product_prices_from_price_book(self, price_book_id) -> List:
        # use the syntax for a related record

        module_name = f"price_books/{price_book_id}/products"
        prices = []
        for data_block in self.yield_page_from_module(module_name=module_name):
            prices += data_block
        return prices


    def set_product_price_in_price_book(self, price_book_id:str, product_id:str, list_price:float) -> List:
        # use the syntax for a related record

        module_name = f"price_books/{price_book_id}/products/{product_id}"
        url = self.base_url + f'{module_name}'
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        r = self.requests_session.put(url=url, headers=headers, json={"data":[{"list_price": list_price}]})
        if r.ok and r.status_code == 200:
            return True, r.json()
        else:
            return False, r.json()


    def create_zoho_quote(self, data: dict) -> Tuple[bool, dict, Optional[str]]:
        """ dict is the data of a Zoho quote. The returned result is a tuple, the last being ID of new record.
        If the attempt to fetch the quote details gives a KeyError, it means Zoho returned an error instead of a quote.
        In that case, raise CouldNotCreateQuote"""
        # creation is done with the Record API
        # https://www.zoho.com/crm/help/api/v2/#create-specify-records
        module_name = "Deals"
        url = self.base_url + f'{module_name}'
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        if 'trigger' not in data:
            data['trigger'] = []
        r = self.requests_session.post(url=url, headers=headers, json={'data': [data]})
        if r.ok:
            json_result = r.json()
            try:
                details = json_result['data'][0]['details']['id']
            except KeyError:  # Zoho returned an error message not a quote
                raise CouldNotCreateZohoRecord(f"Could not create quote: {json_result}")
            return True, json_result, json_result['data'][0]['details']['id']
        else:
            return False, r.json(), None

    def update_zoho_quote(self, data: dict):
        module_name = "Deals"
        url = self.base_url + f"{module_name}/{data['id']}"
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        if 'trigger' not in data:
            data['trigger'] = []
        r = self.requests_session.put(url=url, headers=headers, json={'data': [data]})

        if r.ok and r.status_code == 200:
            return True, r.json()
        else:
            return False, r.json()

    def delete_zoho_quote(self, quote_id):
        module_name = "Deals"
        url = self.base_url + f"{module_name}"
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        r = self.requests_session.delete(url=url, headers=headers, params={'ids': quote_id})

        if r.ok and r.status_code == 200:
            return True, r.json()
        else:
            return False, r.json()

    def create_zoho_order(self, data: dict) -> Tuple[bool, dict, Optional[str]]:
        """ dict is the data of a Zoho quote. The returned result is a tuple, the last being ID of new record.
        If the attempt to fetch the quote details gives a KeyError, it means Zoho returned an error instead of a quote.
        In that case, raise CouldNotCreateQuote"""
        # creation is done with the Record API
        # https://www.zoho.com/crm/help/api/v2/#create-specify-records
        module_name = "Sales_Orders"
        url = self.base_url + f'{module_name}'
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        if 'trigger' not in data:
            data['trigger'] = []
        r = self.requests_session.post(url=url, headers=headers, json={'data': [data]})
        if r.ok and r.status_code == 201:
            json_result = r.json()
            try:
                details = json_result['data'][0]['details']['id']
            except KeyError:  # Zoho returned an error message n
                raise CouldNotCreateZohoRecord(f"Could not create quote: {json_result}")
            return True, json_result, json_result['data'][0]['details']['id']
        else:
            return False, r.json(), None

    def update_zoho_order(self, data: dict):
        module_name = "Sales_Orders"
        url = self.base_url + f"{module_name}/{data['id']}"
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        if 'trigger' not in data:
            data['trigger'] = []
        r = self.requests_session.put(url=url, headers=headers, json={'data': [data]})

        if r.ok and r.status_code == 200:
            return True, r.json()
        else:
            return False, r.json()

    def delete_zoho_order(self, order_id):
        module_name = "Sales_Orders"
        url = self.base_url + f"{module_name}"
        headers = {'Authorization': 'Zoho-oauthtoken ' + self.current_token['access_token']}
        r = self.requests_session.delete(url=url, headers=headers, params={'ids': order_id})

        if r.ok and r.status_code == 200:
            return True, r.json()
        else:
            return False, r.json()




def get_zoho_crm_enhanced(zoho_crm_email=None, **kwargs) -> Zoho_crm_enhanced:
    zoho_crm_email = zoho_crm_email or os.getenv("ZOHO_CRM_EMAIL") or settings.ZOHO_CRM_EMAIL
    settings_row = ZohoCRMSettings.objects.filter(
        zoho_crm_login_emailID__iexact=zoho_crm_email).first()
    zoho_crm = Zoho_crm_enhanced(refresh_token=settings_row.zoho_crm_refresh_token,
                                 client_id=settings_row.zoho_crm_client_id,
                                 client_secret=settings_row.zoho_crm_client_secret,
                                 token_file_dir=Path('/tmp'),
                                 hosting=settings_row.zoho_hosting,
                                 zoho_crm_email=zoho_crm_email,
                                 customer_additional_attribute_for_zoho_account_id=settings_row.dear_additional_attribute_for_zoho_account_id,
                                 **kwargs)
    zoho_crm._refresh_access_token()  # test it
    return zoho_crm


# @pytest.mark.skip
def test_get_contacts():
    zoho_crm = get_zoho_crm_enhanced()
    contacts = [c for c in zoho_crm.yield_page_from_module(module_name="Contacts")]
    assert contacts, "Fail, no contacts"


# @pytest.mark.skip
def test_get_users():
    zoho_crm = get_zoho_crm_enhanced()
    users = zoho_crm.get_users()
    print(users)
    assert users, "Fail, no data"


@pytest.mark.skip
def test_get_contacts_simple_search():
    zoho_crm = get_zoho_crm_enhanced()
    contacts = []
    for data_block in zoho_crm.yield_page_from_module(module_name='Contacts', criteria='(Full_Name:equals:Mark Purdy)'):
        contacts += data_block
    assert len(contacts) > 0, "Fail, no contacts"


@pytest.mark.skip
def test_get_accounts_simple_search():
    zoho_crm = get_zoho_crm_enhanced()
    token = zoho_crm._refresh_access_token()
    contacts = []
    for data_block in zoho_crm.yield_page_from_module(module_name='Accounts',
                                                      criteria='(Account_Name:equals:Damien Bryant Building)'):
        contacts += data_block
    assert len(contacts) > 0, "Fail, no contacts"


# @pytest.mark.skip
def test_get_deals():
    zoho_crm = get_zoho_crm_enhanced()
    token = zoho_crm._refresh_access_token()
    contacts = []
    for data_block in zoho_crm.yield_page_from_module(module_name='Deals'):
        contacts += data_block
    assert len(contacts) > 0, "Fail, no deals"


# @pytest.mark.skip
def test_get_deals_with_datetime():
    zoho_crm = get_zoho_crm_enhanced()
    token = zoho_crm._refresh_access_token()
    data = []
    modified_since = datetime(2018, 5, 1, tzinfo=timezone.utc)
    for data_block in zoho_crm.yield_page_from_module(module_name='Deals', modified_since=modified_since):
        data += data_block
    assert len(data) > 0, "Fail, no data for deals"


def test_get_invoices():
    zoho_crm = get_zoho_crm_enhanced(os.getenv("ZOHO_CRM_EMAIL"))
    token = zoho_crm._refresh_access_token()
    data = []
    for data_block in zoho_crm.yield_page_from_module(module_name='Invoices'):
        data += data_block
    assert len(data) > 0, "Fail, no deals"


if __name__ == '__main__':
    zoho_crm = get_zoho_crm_enhanced()
    new_token = zoho_crm._refresh_access_token()
