
import os
from datetime import datetime, timezone

import pytest

from zoho_crm_connector import Zoho_crm

""" These tests create records; run in the sandbox account."""

# notes on sandbox account: https://help.zoho.com/portal/community/topic/api-has-a-sandbox-environment



@pytest.fixture(scope='session')
def zoho_crm(tmp_path_factory)->Zoho_crm:
    zoho_keys = {
        'refresh_token': os.getenv('ZOHOCRM_REFRESH_TOKEN'),
        'client_id': os.getenv('ZOHOCRM_CLIENT_ID'),
        'client_secret': os.getenv('ZOHOCRM_CLIENT_SECRET'),
        'user_id': os.getenv('ZOHOCRM_DEFAULT_USERID')
    }
    if os.getenv("ZOHO_SANDBOX") or os.getenv("ZOHO_SANDBOX") == "True":
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
                            base_url="https://www.zohoapis.com/crm/v2/",  #"https://www.zohoapis.com/crm/v2/"
                            default_zoho_user_id=zoho_keys['user_id'],
                            hosting=".COM",
                            token_file_dir=tmp_path_factory.mktemp('zohocrm'))

    return zoho_crm




def count_test_accounts(zoho_crm):
    """ this shows how to search a moduule"""
    accounts = [account for page in
        zoho_crm.yield_page_from_module(module_name="Accounts", criteria='(Account_Name:equals:GrowthPath Pty Ltd)')
                for account in page]
    return len(accounts)

def test_use_in_criteria(zoho_crm):
    """ this shows how to search a moduule"""
    in_list = ["Completed",]
    quotes = [quote for page in
        zoho_crm.yield_page_from_module(module_name="Deals", criteria=f'(Stage:in:{",".join(in_list)})')
                for quote in page]
    return len(quotes)


def test_delete_accounts(zoho_crm):
    accounts = [account for page in
                zoho_crm.yield_page_from_module(module_name="Accounts",
                                                criteria='(Account_Name:equals:GrowthPath Pty Ltd)')
                for account in page]
    for account in accounts:
        success,r = zoho_crm.delete_from_module(module_name='Accounts',record_id=account['id'])
        assert success,"Could not delete a record"

    assert count_test_accounts(zoho_crm) == 0, "Could not delete all records"



def test_delete_and_upsert_account(zoho_crm):
    """ this tests searching, upsert and deleting"""
    #note: https://www.zoho.com/crm/help/api/modules-fields.html#Accounts
    # for information on fields

    # delete all existing records for GrowthPath Pty Ltd
    test_delete_accounts(zoho_crm)
    assert count_test_accounts(zoho_crm) == 0, "Could not delete all records"

    # now there should be none

    zoho_account = {'Account_Name':'GrowthPath Pty Ltd',
                    'Description': '124',
            'Owner': {'name':'Tim Richardson','id':zoho_crm.default_zoho_user_id}
        }
    payload = {'data': [zoho_account]}
    # add a record regardless of any existing data
    success,r = zoho_crm.upsert_zoho_module(module_name='Accounts',payload=payload,
                                            criteria='(Account_Name:equals:GrowthPath Pty Ltd)')
    success, r2 = zoho_crm.upsert_zoho_module(module_name='Accounts', criteria=None, payload=payload)
    assert count_test_accounts(zoho_crm) == 2, "There should be two records now"

    success,r = zoho_crm.upsert_zoho_module(module_name='Accounts', criteria='(Account_Name:equals:GrowthPath Pty Ltd)'
                                            ,payload=payload)
    assert count_test_accounts(zoho_crm) == 2, "There should still be two records now"
    zoho_crm.delete_from_module(module_name="Accounts",record_id=r2['id'])
    assert count_test_accounts(zoho_crm) == 1, "There should be one record now"



#@pytest.mark.skip
def test_add_and_search_contacts(zoho_crm):
    # generator below flattens the list
    contacts = [c for page in zoho_crm.yield_page_from_module(module_name="Contacts") for c in page]
    assert contacts,"Fail, no contacts"


#@pytest.mark.skip
def test_get_contact_with_related_record(zoho_crm):
    # make sure we have an account
    test_delete_accounts(zoho_crm)
    assert count_test_accounts(zoho_crm) == 0, "Could not delete all records"

    zoho_account = {
        'Account_Name': 'GrowthPath Pty Ltd',
        'Description': '124',
        'Owner': {'name': 'Tim Richardson', 'id': zoho_crm.default_zoho_user_id}
        }
    acct_payload = {'data': [zoho_account]}
    # add a account record regardless of any existing data
    success, account = zoho_crm.upsert_zoho_module(module_name='Accounts',payload=acct_payload,
                criteria='(Account_Name:equals:GrowthPath Pty Ltd)')
    assert success

    #delete all Tim Richardson contact records
    for c in [c for page in
                zoho_crm.yield_page_from_module(module_name="Contacts",
                                                criteria='((Full_Name:equals:Tim Richardson))')
                for c in page]:
        success, r = zoho_crm.delete_from_module(module_name='Accounts', record_id=account['id'])
        assert success, "Could not delete a record"


    #now upsert a contact record
    #https://www.zoho.com/crm/help/api/modules-fields.html#Contacts
    #to link it to the account, pass the account name as a string
    zoho_contact = {
        'Email': 'tim@growthpath.com.au',
        'First_Name':'Tim',
        'Last_Name':'Richardson',
        'Owner': {'name': 'Tim Richardson', 'id': zoho_crm.default_zoho_user_id},
        #'Account_Name':{'name':account['Account_Name'],'id':account['id']}
        'Account_Name': account['Account_Name']
        }

    zoho_contact2 = {
        'Email': 'tim@smith.com.au',
        'First_Name': 'Tim',
        'Last_Name': 'Smith',
        'Owner': {'name': 'Tim Richardson', 'id': zoho_crm.default_zoho_user_id},
        # 'Account_Name':{'name':account['Account_Name'],'id':account['id']}
        'Account_Name': account['Account_Name']
        }
    contact_payload = {'data': [zoho_contact]}
    success, contact = zoho_crm.upsert_zoho_module(module_name='Contacts', payload=contact_payload,
        criteria = '(Full_Name:equals:Tim Richardson)')
    success, contact = zoho_crm.upsert_zoho_module(module_name='Contacts', payload={'data': [zoho_contact2]},
                                                   criteria='(Full_Name:equals:Tim Smith)')

    # Now find all contacts linked to the account

    success, contacts = zoho_crm.get_related_records(parent_module_name="Accounts", child_module_name="Contacts",
                                                     parent_id=account['id'])

    assert len(contacts) > 0,"Fail, no contacts"


def test_upsert_deal(zoho_crm):
    """ deal is the old name for Potential"""
    zoho_account = {
        'Account_Name': 'GrowthPath Pty Ltd',
        'Description': '124',
        'Owner': {'name': 'Tim Richardson', 'id': zoho_crm.default_zoho_user_id}
        }
    acct_payload = {'data': [zoho_account]}
    # add a account record regardless of any existing data
    success, account = zoho_crm.upsert_zoho_module(module_name='Accounts', payload=acct_payload,
                                                   criteria='(Account_Name:equals:GrowthPath Pty Ltd)')
    assert success

    zoho_contact = {
        'Email': 'tim@growthpath.com.au',
        'First_Name': 'Tim',
        'Last_Name': 'Richardson',
        'Owner': {'name': 'Tim Richardson', 'id': zoho_crm.default_zoho_user_id},
        # 'Account_Name':{'name':account['Account_Name'],'id':account['id']}
        'Account_Name': account['Account_Name']
        }

    success, contacts = zoho_crm.get_related_records(parent_module_name="Accounts", child_module_name="Contacts",
                                                     parent_id=account['id'])

    zoho_deal = {
        'Owner': {'name': 'Tim Richardson', 'id': zoho_crm.default_zoho_user_id},
        'Account_Name': account['Account_Name'],
        'Description': 'test quote',
         'Deal_Name': 'test deal',
     }

    success, deal = zoho_crm.upsert_zoho_module(module_name='Deals', payload={'data': [zoho_deal]},
                                                   criteria='((Deal_Name:equals:test deal)and('
                                                            'Account_Name:equals:GrowthPath Pty Ltd))')

    modified_since = datetime(2018, 5, 1, tzinfo=timezone.utc)
    data = []
    for data_block in zoho_crm.yield_page_from_module(module_name='Deals', modified_since=modified_since):
        data += data_block
    assert len(data) > 0, "Fail, no data for deals"

    assert success


def test_related_records(zoho_crm):
    accounts = [account for page in
                zoho_crm.yield_page_from_module(module_name="Accounts",
                                                criteria='(Account_Name:equals:GrowthPath Pty Ltd)')
                for account in page]
    assert accounts, "Fail, no matching accounts, can't continue with test"
    account = accounts[0]
    success,contacts = zoho_crm.get_related_records(parent_module_name="Accounts",child_module_name="Contacts",parent_id=account['id'])
    assert success

def test_get_deal_list(zoho_crm):
    deals = [deal for page in
                zoho_crm.yield_page_from_module(module_name="Deals") for deal in page for deal in page]
    assert deals, "Fail, no matching accounts, can't continue with test"


#@pytest.mark.skip
def test_get_users(zoho_crm):
    users = zoho_crm.get_users()
    print(users)
    assert users,"Fail, no users"


def get_records_through_coql_query(zoho_crm):
    pass



