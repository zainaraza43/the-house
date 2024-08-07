import pytest
from the_house.db_utils import (
    create_user, get_user_by_user_table_id, get_user_by_discord_account_id,
    create_guild, create_bank, get_bank_by_user_and_guild, get_guild_by_guild_id,
    set_lol_account, get_lol_account, get_all_league_of_legends_accounts,
    set_bank_coins, increment_multiple_bank_coins, get_banks_sorted_by_coins_for_guild,
    get_all_banks
)
from the_house.models import User, LeagueOfLegendsAccount, Guild, Bank
from unittest.mock import MagicMock


@pytest.fixture
def mock_db(mocker):
    mock_db = MagicMock()
    mocker.patch('the_house.services.db', mock_db)
    return mock_db


def test_create_user(mock_db):
    user = create_user(123456789)
    mock_db.add.assert_called_once_with(user)
    mock_db.commit.assert_called_once()


def test_get_user_by_user_table_id(mock_db):
    user = get_user_by_user_table_id(1)
    mock_db.query().filter().first.assert_called_once()


def test_get_user_by_discord_account_id(mock_db):
    user = get_user_by_discord_account_id(123456789)
    mock_db.query().filter().first.assert_called_once()


def test_create_guild(mock_db):
    guild = create_guild(987654321)
    mock_db.add.assert_called_once_with(guild)
    mock_db.commit.assert_called_once()


def test_create_bank(mock_db):
    bank = create_bank(1, 987654321)
    mock_db.add.assert_called_once_with(bank)
    mock_db.commit.assert_called_once()


def test_get_bank_by_user_and_guild(mock_db):
    bank = get_bank_by_user_and_guild(1, 987654321)
    mock_db.query().filter_by().first.assert_called_once()


def test_get_guild_by_guild_id(mock_db):
    guild = get_guild_by_guild_id(987654321)
    mock_db.query().filter().first.assert_called_once()


def test_set_lol_account(mock_db):
    set_lol_account(1, 987654321, 'na1', 'puuid123')
    mock_db.query().filter_by().first.assert_called_once()
    mock_db.commit.assert_called()


def test_get_lol_account(mock_db):
    account = get_lol_account(1, 987654321)
    mock_db.query().filter_by().first.assert_called_once()


def test_get_all_league_of_legends_accounts(mock_db):
    accounts = get_all_league_of_legends_accounts()
    mock_db.query().all.assert_called_once()


def test_set_bank_coins(mock_db):
    set_bank_coins(1, 987654321, 100)
    mock_db.query().filter_by().first.assert_called_once()
    mock_db.commit.assert_called_once()


def test_increment_multiple_bank_coins(mock_db):
    banks = [Bank(coins=10), Bank(coins=20)]
    increment_multiple_bank_coins(banks, 5)
    assert banks[0].coins == 15
    assert banks[1].coins == 25
    mock_db.commit.assert_called_once()


def test_get_banks_sorted_by_coins_for_guild(mock_db):
    banks = get_banks_sorted_by_coins_for_guild(987654321)
    mock_db.query().filter().order_by().all.assert_called_once()


def test_get_all_banks(mock_db):
    banks = get_all_banks()
    mock_db.query().all.assert_called_once()
