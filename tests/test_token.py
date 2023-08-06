import pytest

from brownie.network.account import Account

from brownie import (
    chain,
    web3,
    Usdc,
    DIP
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass

def test_token_fixture(
    instanceOperator: Account,
    token,
):
    assert token.name() == 'USD Coin - DUMMY'
    assert token.symbol() == 'USDC'
    assert token.decimals() == 6
    assert token.balanceOf(instanceOperator) == 1000000000000000000000000

def test_usd1_transfer(
    instanceOperator: Account,
    token: Usdc,
    customer: Account,
    investor: Account
):
    block_number = web3.eth.block_number

    chain.mine(3)
    balance0 = token.balanceOf(customer)
    assert balance0 == 0

    # LogUsd1Transfer(from, to, amount, block.timestamp, block.number);
    amount1 = 987 * 10 ** token.decimals()
    amount2 = 200 * 10 ** token.decimals()
    amount3 = 1

    tx1 = token.transfer(customer, amount1, {'from':instanceOperator})
    balance1 = token.balanceOf(customer)
    assert balance1 == amount1

    assert 'LogUsdcTransferFrom' in tx1.events
    assert tx1.events['LogUsdcTransferFrom']['from'] == instanceOperator
    assert tx1.events['LogUsdcTransferFrom']['to'] == customer
    assert tx1.events['LogUsdcTransferFrom']['amount'] == amount1
    assert tx1.events['LogUsdcTransferFrom']['blockNumber'] == block_number + 3 + 1
    block_number += 4

    chain.sleep(10)
    chain.mine(1)

    tx2 = token.transfer(investor, amount2, {'from':customer})
    balance2 = token.balanceOf(customer)
    assert balance2 == amount1 - amount2

    assert 'LogUsdcTransferFrom' in tx2.events
    assert tx2.events['LogUsdcTransferFrom']['from'] == customer
    assert tx2.events['LogUsdcTransferFrom']['to'] == investor
    assert tx2.events['LogUsdcTransferFrom']['amount'] == amount2
    assert tx2.events['LogUsdcTransferFrom']['blockNumber'] == block_number + 1 + 1
    block_number += 2

    chain.sleep(10)
    chain.mine(5)

    tx3 = token.transfer(customer, amount3, {'from':investor})
    balance3 = token.balanceOf(customer)
    assert balance3 == amount1 - amount2 + amount3

    assert 'LogUsdcTransferFrom' in tx3.events
    assert tx3.events['LogUsdcTransferFrom']['from'] == investor
    assert tx3.events['LogUsdcTransferFrom']['to'] == customer
    assert tx3.events['LogUsdcTransferFrom']['amount'] == amount3
    assert tx3.events['LogUsdcTransferFrom']['blockNumber'] == block_number + 5 + 1
    block_number += 6


def test_dip(
    instanceOperator: Account,
    dip: DIP,
):
    assert dip.symbol() == 'DIP'
    assert dip.decimals() == 18
    assert dip.balanceOf(instanceOperator) == 10**9 * 10**18
