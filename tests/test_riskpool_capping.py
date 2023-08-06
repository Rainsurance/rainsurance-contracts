import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    Usdc,
)

from scripts.product import (
    GifProduct,
    GifRiskpool,
)

from scripts.setup import create_bundle
from scripts.util import b2s

from scripts.product import (
    CAPITAL_FEE_FIXED_DEFAULT,
    CAPITAL_FEE_FRACTIONAL_DEFAULT,
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass

def test_riskpool_fixture(
    gifProduct: GifProduct,
    riskpoolWallet: Account,
    token: Usdc,
):
    product = gifProduct.getContract()
    riskpool = gifProduct.getRiskpool().getContract()

    print('product {}'.format(product))
    print('riskpool {}'.format(riskpool))
    print('riskpool.getToken() {}'.format(riskpool.getErc20Token()))
    print('token {}'.format(token))
    print('riskpoolWallet {}'.format(riskpoolWallet))

    print('product {} id {} name {}'.format(
        product,
        product.getId(),
        b2s(product.getName())
    ))

    print('riskpool {} id {} name {}'.format(
        riskpool,
        riskpool.getId(),
        b2s(riskpool.getName())
    ))


def test_riskpool_setting_caps(
    gifProduct: GifProduct,
    riskpoolKeeper,
    customer,
):
    riskpool = gifProduct.getRiskpool().getContract()
    riskpool_cap_old = riskpool.getRiskpoolCapitalCap()
    bundle_cap_old = riskpool.getBundleCapitalCap()

    assert riskpool_cap_old == riskpool.getSumOfSumInsuredCap()
    assert bundle_cap_old == riskpool_cap_old / 10

    riskpool_cap = int(riskpool.getRiskpoolCapitalCap() / 200)
    bundle_cap = int(riskpool_cap / 2)

    assert bundle_cap < riskpool_cap
    assert riskpool_cap < riskpool_cap_old
    assert bundle_cap < bundle_cap_old

    # check setting caps is restricted to riskpool keeper
    with brownie.reverts('Ownable: caller is not the owner'):
        riskpool.setCapitalCaps(
            riskpool_cap,
            bundle_cap,
            {'from': customer})

    tx = riskpool.setCapitalCaps(
        riskpool_cap,
        bundle_cap,
        {'from': riskpoolKeeper})

    assert 'LogRiskpoolCapitalSet' in tx.events
    assert tx.events['LogRiskpoolCapitalSet']['poolCapitalOld'] == riskpool_cap_old
    assert tx.events['LogRiskpoolCapitalSet']['poolCapitalNew'] == riskpool_cap
    
    assert 'LogBundleCapitalSet' in tx.events
    assert tx.events['LogBundleCapitalSet']['bundleCapitalOld'] == bundle_cap_old
    assert tx.events['LogBundleCapitalSet']['bundleCapitalNew'] == bundle_cap

    assert riskpool.getRiskpoolCapitalCap() == riskpool_cap
    assert riskpool.getBundleCapitalCap() == bundle_cap

    # check that doubling capital caps work
    riskpool_cap_new = 2 * riskpool_cap
    bundle_cap_new = int(riskpool_cap_new / 3)

    assert riskpool_cap_new > riskpool_cap
    assert bundle_cap_new > bundle_cap

    tx = riskpool.setCapitalCaps(
        riskpool_cap_new,
        bundle_cap_new,
        {'from': riskpoolKeeper})

    assert 'LogRiskpoolCapitalSet' in tx.events
    assert tx.events['LogRiskpoolCapitalSet']['poolCapitalOld'] == riskpool_cap
    assert tx.events['LogRiskpoolCapitalSet']['poolCapitalNew'] == riskpool_cap_new
    
    assert 'LogBundleCapitalSet' in tx.events
    assert tx.events['LogBundleCapitalSet']['bundleCapitalOld'] == bundle_cap
    assert tx.events['LogBundleCapitalSet']['bundleCapitalNew'] == bundle_cap_new

    assert riskpool.getRiskpoolCapitalCap() == riskpool_cap_new
    assert riskpool.getBundleCapitalCap() == bundle_cap_new


def test_riskpool_enforcing_caps_simple(
    riskpool,
    riskpoolKeeper,
    riskpoolWallet,
    instance,
    instanceService,
    instanceOperator,
    investor,
    token,
):
    riskpool_cap = 5000
    bundle_cap = int(riskpool_cap / 1) - 1
    tf = 10 ** token.decimals()

    riskpool.setCapitalCaps(
        riskpool_cap * tf,
        bundle_cap * tf,
        {'from': riskpoolKeeper})

    # case 1: attempt to created bundle > pool cap
    with brownie.reverts('ERROR:RAINRP-027:RISK_CAPITAL_INVALID'):
        create_bundle(
            instance, 
            instanceOperator, 
            investor, 
            riskpool,
            maxProtectedBalance = bundle_cap - 1,
            funding = riskpool_cap + 1)

    # case 2: attempt to create bundle > bundle cap
    with brownie.reverts('ERROR:RAINRP-027:RISK_CAPITAL_INVALID'):
        create_bundle(
            instance, 
            instanceOperator, 
            investor, 
            riskpool,
            maxProtectedBalance = bundle_cap - 1,
            funding = riskpool_cap)

    # case 3: create bundle == bundle cap
    bundle_id = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool,
        maxProtectedBalance = bundle_cap - 1,
        funding = bundle_cap)

    bundle = instanceService.getBundle(bundle_id).dict()

    assert bundle['capital'] == bundle_cap * tf * (1 - CAPITAL_FEE_FRACTIONAL_DEFAULT)
    assert bundle['balance'] == bundle_cap * tf * (1 - CAPITAL_FEE_FRACTIONAL_DEFAULT)

    # attempt to increase bundle capital via bundle funding
    increase_amount = 500 * tf
    token.approve(instanceService.getTreasuryAddress(), increase_amount, {'from': investor})

    with brownie.reverts('ERROR:RAINRP-100:FUNDING_EXCEEDS_BUNDLE_CAPITAL_CAP'):
        riskpool.fundBundle(
            bundle_id,
            increase_amount,
            {'from': investor})

    # check that defunding, then funding again works
    delta_amount = 100 * tf

    token.approve(instanceService.getTreasuryAddress(), delta_amount, {'from': riskpoolWallet})
    riskpool.defundBundle(
        bundle_id,
        delta_amount,
        {'from': investor})
    
    capital_after_defund = bundle_cap * tf * (1 - CAPITAL_FEE_FRACTIONAL_DEFAULT) - delta_amount

    assert instanceService.getBundle(bundle_id).dict()['capital'] == capital_after_defund

    token.approve(instanceService.getTreasuryAddress(), delta_amount, {'from': investor})
    riskpool.fundBundle(
        bundle_id,
        delta_amount,
        {'from': investor})
    
    capital_after_refund = capital_after_defund + delta_amount * (1 - CAPITAL_FEE_FRACTIONAL_DEFAULT) 

    assert instanceService.getBundle(bundle_id).dict()['capital'] == capital_after_refund


def test_riskpool_enforcing_caps_multiple_bundles(
    riskpool,
    riskpoolKeeper,
    riskpoolWallet,
    instance,
    instanceService,
    instanceOperator,
    investor,
    token,
):
    riskpool_cap = 5000
    bundle_cap = int(riskpool_cap * 2 / 3)
    tf = 10 ** token.decimals()

    assert 2 * bundle_cap > riskpool_cap

    riskpool.setCapitalCaps(
        riskpool_cap * tf,
        bundle_cap * tf,
        {'from': riskpoolKeeper})

    # case 3: attempt to create 2 bundles, each < bundle cap, summed > pool cap

    # 1st bundle -> check this is ok
    bundle_id1 = create_bundle(
            instance, 
            instanceOperator, 
            investor, 
            riskpool,
            maxProtectedBalance = bundle_cap - 1,
            funding=bundle_cap)

    # verify there's no room for a second such bundle
    with brownie.reverts('ERROR:RAINRP-028:POOL_CAPITAL_CAP_EXCEEDED'):
        create_bundle(
                instance, 
                instanceOperator, 
                investor, 
                riskpool,
                maxProtectedBalance = bundle_cap - 1,
                funding=bundle_cap)

    # case 4: as 3, withdraw from 1st bundle as much as is needed to get: summed == pool cap    # try again with reduced funding for 2nd bundle
    second_bundle_funding_max = riskpool_cap - bundle_cap
    bundle_id2 = create_bundle(
                instance, 
                instanceOperator, 
                investor, 
                riskpool,
                maxProtectedBalance = bundle_cap - 1,
                funding=second_bundle_funding_max)

    assert riskpool.getCapital() == riskpool_cap * tf * (1 - CAPITAL_FEE_FRACTIONAL_DEFAULT) 
    assert instanceService.getBundle(bundle_id1).dict()['capital'] == bundle_cap * tf * (1 - CAPITAL_FEE_FRACTIONAL_DEFAULT) 
    assert instanceService.getBundle(bundle_id2).dict()['capital'] == second_bundle_funding_max * tf * (1 - CAPITAL_FEE_FRACTIONAL_DEFAULT) 

    # verify that funding bundles is not possible even with its capital < bundle_cap
    increase_amount = 500 * tf
    token.approve(instanceService.getTreasuryAddress(), increase_amount, {'from': investor})

    # try to fund bundl 1
    with brownie.reverts('ERROR:RAINRP-100:FUNDING_EXCEEDS_BUNDLE_CAPITAL_CAP'):
        riskpool.fundBundle(
            bundle_id1,
            increase_amount,
            {'from': investor})

    # try to fund bundl 2
    with brownie.reverts('ERROR:RAINRP-101:FUNDING_EXCEEDS_RISKPOOL_CAPITAL_CAP'):
        riskpool.fundBundle(
            bundle_id2,
            increase_amount,
            {'from': investor})

