
import os
from datetime import datetime,timezone
import pytest
from zoho_crm import Zoho_crm


#this depends on django settings
# notes on sandbox account: https://help.zoho.com/portal/community/topic/api-has-a-sandbox-environment

@pytest.fixture(scope='session')
def zoho_crm(tmp_path_factory)->Zoho_crm:
    zoho_keys = {
        'refresh_token': os.getenv('ZOHOCRM_REFRESH_TOKEN'),
        'client_id': os.getenv('ZOHOCRM_CLIENT_ID'),
        'client_secret': os.getenv('ZOHOCRM_CLIENT_SECRET')
    }

    zoho_crm = Zoho_crm(refresh_token=zoho_keys['refresh_token'],
                        client_id=zoho_keys['client_id'],
                        client_secret=zoho_keys['client_secret'],
                        token_file_dir=tmp_path_factory.mktemp('zohocrm'))
    return zoho_crm


#@pytest.mark.skip
def test_get_contacts(zoho_crm):
    contacts = [c for c in zoho_crm.yield_page_from_module(module_name="Contacts")]
    assert contacts,"Fail, no contacts"


#@pytest.mark.skip
def test_get_users(zoho_crm):
    users = zoho_crm.get_users()
    print(users)
    assert users,"Fail, no users"


#@pytest.mark.skip
def test_get_contacts_simple_search(zoho_crm):
    contacts = []
    for data_block in zoho_crm.yield_page_from_module(module_name='Contacts', criteria='(Full_Name:equals:Mark Purdy)'):
        contacts += data_block
    assert len(contacts)>0,"Fail, no contacts"

#@pytest.mark.skip
def test_get_accounts_simple_search(zoho_crm):
    contacts = []
    for data_block in zoho_crm.yield_page_from_module(module_name='Accounts', criteria='(Account_Name:equals:Damien Bryant Building)'):
        contacts += data_block
    assert len(contacts)>0,"Fail, no contacts"

#@pytest.mark.skip
def test_get_deals(zoho_crm):
    contacts = []
    for data_block in zoho_crm.yield_page_from_module(module_name='Deals'):
        contacts += data_block
    assert len(contacts)>0,"Fail, no deals"


#@pytest.mark.skip
def test_get_deals_with_datetime(zoho_crm):
    data = []
    modified_since = datetime(2018, 5, 1,tzinfo=timezone.utc)
    for data_block in zoho_crm.yield_page_from_module(module_name='Deals', modified_since=modified_since):
        data += data_block
    assert len(data) > 0, "Fail, no data for deals"



