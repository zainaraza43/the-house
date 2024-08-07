from unittest.mock import patch, AsyncMock

import pytest

from the_house.lol_api_utils import (
    get_account_by_riot_id, get_account_info_by_puuid, get_summoner_by_puuid,
    get_match_ids_by_puuid, get_match_details, get_live_match_details, get_champion_icon
)


@pytest.mark.asyncio
async def test_get_account_by_riot_id():
    with patch('the_house.lol_api_utils.fetch_json', new_callable=AsyncMock) as mock_fetch_json:
        await get_account_by_riot_id('username', 'tagline', 'na1')
        mock_fetch_json.assert_called_once()


@pytest.mark.asyncio
async def test_get_account_info_by_puuid():
    with patch('the_house.lol_api_utils.fetch_json', new_callable=AsyncMock) as mock_fetch_json:
        await get_account_info_by_puuid('puuid123', 'na1')
        mock_fetch_json.assert_called_once()


@pytest.mark.asyncio
async def test_get_summoner_by_puuid():
    with patch('the_house.lol_api_utils.fetch_json', new_callable=AsyncMock) as mock_fetch_json:
        await get_summoner_by_puuid('puuid123', 'na1')
        mock_fetch_json.assert_called_once()


@pytest.mark.asyncio
async def test_get_match_ids_by_puuid():
    with patch('the_house.lol_api_utils.fetch_json', new_callable=AsyncMock) as mock_fetch_json:
        await get_match_ids_by_puuid('puuid123', 'na1', 5)
        mock_fetch_json.assert_called_once()


@pytest.mark.asyncio
async def test_get_match_details():
    with patch('the_house.lol_api_utils.fetch_json', new_callable=AsyncMock) as mock_fetch_json:
        await get_match_details('match_id123', 'na1')
        mock_fetch_json.assert_called_once()


@pytest.mark.asyncio
async def test_get_live_match_details():
    with patch('the_house.lol_api_utils.fetch_json', new_callable=AsyncMock) as mock_fetch_json:
        await get_live_match_details('puuid123', 'na1')
        mock_fetch_json.assert_called_once()


@pytest.mark.asyncio
async def test_get_champion_icon():
    with patch('the_house.lol_api_utils.fetch_json', new_callable=AsyncMock) as mock_fetch_json:
        await get_champion_icon(123)
        mock_fetch_json.assert_called_once()
