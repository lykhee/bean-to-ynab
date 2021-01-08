
import argparse
import sys
import requests
from collections import namedtuple
from decimal import Decimal
from datetime import datetime
import json

import beancount.loader
import beancount.query.query

API = 'https://api.youneedabudget.com/v1/budgets'


def get_ynab_accounts(auth, budget_id):
    response = requests.get(f'{API}/{budget_id}/accounts', headers=auth)
    response.raise_for_status()
    return accounts_from_json(response.json()['data']['accounts'])


def accounts_from_json(json_accounts):
    result = {}
    for a in json_accounts:
        account = namedtuple('Account', a.keys())(*a.values())
        result[account.id] = account
    return result


def get_ynab_account(token, budget_id, account_id):
    header = get_auth_header(token)
    accounts = get_ynab_accounts(header, budget_id)
    for account in accounts.values():
        if account.id == account_id:
            return account


def get_mapping(ynab_account):
    mapping = {}
    if ynab_account.note is None:
        raise Exception('No mapping found.')
    else:
        for line in ynab_account.note.splitlines():
            k, v = line.split(': ')
            mapping[k] = v
    return mapping


def get_beancount_balance(entries, options, ynab_account):
    mapping = get_mapping(ynab_account)
    if mapping['bean-to-ynab'] == 'true':
        bean_account = mapping['bean']
        bean_exclude = mapping['bean-x']
        if bean_exclude:
            query = f'SELECT value(sum(position)) WHERE account ~ {bean_account} AND account != {bean_exclude};'
        else:
            query = f'SELECT value(sum(position)) WHERE account ~ {bean_account};'
    bean_balance = beancount.query.query.run_query(entries, options, query, numberify=True)[1][0][0]
    return int(Decimal(bean_balance * 1000))


def create_transaction(token, budget_id, account_id, difference):
    header = get_auth_header(token)
    header['Content-type'] = 'application/json'
    data = {
        "transaction": {
            "account_id": f"{account_id}",
            "date": f"{datetime.today().strftime('%Y-%m-%d')}",
            "amount": difference,
            "payee_name": "Automatic Balance Adjustment",
            "memo": "Automatic Balance Adjustment by Beancount",
            "cleared": "cleared",
            "approved": True
        }
    }
    response = requests.post(f'{API}/{budget_id}/transactions', headers=header, data=json.dumps(data))
    return response.raise_for_status()


def get_auth_header(token):
    return {'Authorization': f'Bearer {token}'}


def main():
    parser = argparse.ArgumentParser(
        description='Sync Beancount account balances to YNAB accounts.'
    )
    parser.add_argument('bean', help='Path to the beancount file.', nargs='?', default=None)
    parser.add_argument('--ynab-token', help='Your YNAB API token.', required=True)
    parser.add_argument('--account-id', help='YNAB account id.', required=True)
    args = parser.parse_args()

    # hard-code budget to be used as the 'last-used' budget
    budget_id = 'last-used'

    entries, errors, options = beancount.loader.load_file(args.bean, log_errors=sys.stderr)
    if errors:
        sys.exit(1)

    ynab_account = get_ynab_account(args.ynab_token, budget_id, args.account_id)
    if not ynab_account:
        raise Exception(f'Could not find any account with id {args.account_id}')
    elif ynab_account.on_budget is True:
        raise Exception('The account is not a tracking account.')
    else:
        bean_balance = get_beancount_balance(entries, options, ynab_account)
        difference = bean_balance - ynab_account.balance
        create_transaction(args.ynab_token, budget_id, args.account_id, difference)


if __name__ == '__main__':
    main()
