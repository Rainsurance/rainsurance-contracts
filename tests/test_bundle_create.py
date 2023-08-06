import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    interface,
)

from scripts.setup import create_bundle

from scripts.util import s2b32

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass

def test_create_bundle_happy_case(
    instance,
    instanceService,
    instanceOperator,
    investor,
    riskpool,
):
    instanceWallet = instanceService.getInstanceWallet()
    riskpoolWallet = instanceService.getRiskpoolWallet(riskpool.getId())
    tokenAddress = instanceService.getComponentToken(riskpool.getId())
    token = interface.IERC20Metadata(tokenAddress)

    bundleFunding = 100000

    # check initialized riskpool
    assert instanceService.bundles() == 0
    assert token.balanceOf(instanceWallet) == 0
    assert token.balanceOf(riskpoolWallet) == 0
    assert token.balanceOf(investor) == 0
    assert token.balanceOf(instanceOperator) >= bundleFunding

    # check riskpool bundles
    assert riskpool.activeBundles() == 0
    assert riskpool.bundles() == 0

    bundleName = 'test bundle'
    bundleLifetimeDays = 90
    minProtectedBalance =  100
    maxProtectedBalance = 5000
    minDurationDays = 1
    maxDurationDays = 15
    place = '10001.saopaulo'
    
    bundleId = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool, 
        bundleFunding, 
        bundleName,
        bundleLifetimeDays,
        minProtectedBalance, 
        maxProtectedBalance, 
        minDurationDays, 
        maxDurationDays, 
        place)

    # check wallet balances against bundle investment
    fixedFee = 0
    fractionalFee = 0.05
    capital_fees = fractionalFee * bundleFunding + fixedFee
    net_capital = bundleFunding - capital_fees
    tf = 10**token.decimals()

    # check riskpool bundles
    assert riskpool.activeBundles() == 1
    assert riskpool.bundles() == 1
    assert riskpool.getBundleId(0) == bundleId

    with brownie.reverts('ERROR:RPL-007:BUNDLE_INDEX_TOO_LARGE'):
        riskpool.getBundleId(1) > 0

    assert instanceService.bundles() == 1
    assert token.balanceOf(riskpoolWallet) == net_capital * tf
    assert token.balanceOf(instanceWallet) == capital_fees * tf

    print('bundle {} created'.format(bundleId))

    # check riskpool statistics
    assert instanceService.getCapital(riskpool.getId()) == net_capital * tf
    assert instanceService.getCapacity(riskpool.getId()) == net_capital * tf
    assert instanceService.getBalance(riskpool.getId()) == net_capital * tf
    assert instanceService.getTotalValueLocked(riskpool.getId()) == 0

    # check bundle statistics
    (
        id, 
        riskpoolId, 
        tokenId, 
        state, 
        bundleFilter, 
        capital, 
        lockedCapital, 
        balance, 
        createdAt, 
        updatedAt
    ) = instanceService.getBundle(bundleId)

    assert id == bundleId
    assert riskpoolId == riskpool.getId()
    assert state == 0 # enum BundleState { Active, Locked, Closed, Burned }
    assert capital == net_capital * tf
    assert lockedCapital == 0
    assert balance == net_capital * tf
    assert createdAt > 0
    assert updatedAt == createdAt

    # check bundle filter data
    (
        filterBundleName,
        filterBundleLifetime,
        filterMinSumInsured,
        filterMaxSumInsured,
        filterMinDuration,
        filterMaxDuration,
        filterplace
    ) = riskpool.decodeBundleParamsFromFilter(bundleFilter)

    assert filterBundleName == bundleName
    assert filterBundleLifetime == bundleLifetimeDays * 24 * 3600

    minSumInsured = riskpool.calculateSumInsured(minProtectedBalance)
    maxSumInsured = riskpool.calculateSumInsured(maxProtectedBalance)
    
    assert filterMinSumInsured == minSumInsured * tf
    assert filterMaxSumInsured == maxSumInsured * tf
    assert filterMinDuration == minDurationDays * 24 * 3600
    assert filterMaxDuration == maxDurationDays * 24 * 3600
    assert filterplace == place

    bundleInfo = riskpool.getBundleInfo(bundleId).dict()
    print('bundleInfo {}'.format(bundleInfo))

    assert bundleInfo['state'] == state
    assert bundleInfo['tokenId'] == tokenId
    assert bundleInfo['owner'] == investor

    assert bundleInfo['name'] == bundleName
    assert bundleInfo['lifetime'] == bundleLifetimeDays * 24 * 3600

    assert bundleInfo['minSumInsured'] == minSumInsured * tf
    assert bundleInfo['maxSumInsured'] == maxSumInsured * tf
    assert bundleInfo['minDuration'] == filterMinDuration
    assert bundleInfo['maxDuration'] == filterMaxDuration
    assert bundleInfo['place'] == filterplace

    assert bundleInfo['capitalSupportedByStaking'] == riskpool.getBundleCapitalCap()
    assert bundleInfo['capital'] == capital
    assert bundleInfo['lockedCapital'] == lockedCapital
    assert bundleInfo['balance'] == balance
    assert bundleInfo['createdAt'] == createdAt


def test_create_name_validation(
    instance,
    instanceService,
    instanceOperator,
    investor,
    riskpool,
):
    instanceWallet = instanceService.getInstanceWallet()
    riskpoolWallet = instanceService.getRiskpoolWallet(riskpool.getId())
    tokenAddress = instanceService.getComponentToken(riskpool.getId())
    token = interface.IERC20(tokenAddress)

    bundleFunding = 10000

    # check initialized riskpool
    assert instanceService.bundles() == 0

    bundleName = ''
    bundleLifetimeDays = 90
    minProtectedBalance =  100
    maxProtectedBalance = 5000
    minDurationDays = 1
    maxDurationDays = 15
    place = '10001.saopaulo'

    bundleId1 = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool, 
        bundleFunding, 
        bundleName,
        bundleLifetimeDays,
        minProtectedBalance, 
        maxProtectedBalance, 
        minDurationDays, 
        maxDurationDays, 
        place)

    assert instanceService.bundles() == 1

    assert len(riskpool.bundleIdsForPlace(place)) == 1
    assert riskpool.bundleIdsForPlace(place) == [bundleId1]

    bundleLifetimeDays = 30

    bundleId2 = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool, 
        bundleFunding, 
        bundleName,
        bundleLifetimeDays,
        minProtectedBalance, 
        maxProtectedBalance, 
        minDurationDays, 
        maxDurationDays, 
        place)

    assert instanceService.bundles() == 2

    assert len(riskpool.bundleIdsForPlace(place)) == 2
    assert riskpool.bundleIdsForPlace(place) == [bundleId1, bundleId2]

    place = '10002.paris'
    bundleName = 'bundle 30 days, paris'

    bundleId3 = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool, 
        bundleFunding, 
        bundleName,
        bundleLifetimeDays,
        minProtectedBalance, 
        maxProtectedBalance, 
        minDurationDays, 
        maxDurationDays, 
        place)

    assert instanceService.bundles() == 3

    with brownie.reverts("ERROR:RAINRP-020:NAME_NOT_UNIQUE"):
        bundleId4 = create_bundle(
            instance, 
            instanceOperator, 
            investor, 
            riskpool, 
            bundleFunding, 
            bundleName,
            bundleLifetimeDays,
            minProtectedBalance, 
            maxProtectedBalance, 
            minDurationDays, 
            maxDurationDays, 
            place)

    assert instanceService.bundles() == 3


def test_create_lifetime_validation(
    instance,
    instanceService,
    instanceOperator,
    investor,
    riskpool,
):
    instanceWallet = instanceService.getInstanceWallet()
    riskpoolWallet = instanceService.getRiskpoolWallet(riskpool.getId())
    tokenAddress = instanceService.getComponentToken(riskpool.getId())
    token = interface.IERC20(tokenAddress)

    bundleFunding = 10000

    # check initialized riskpool
    assert instanceService.bundles() == 0

    bundleName = ''
    bundleLifetimeDays = 1 # too short
    minProtectedBalance =  2000
    maxProtectedBalance = 5000
    minDurationDays = 3
    maxDurationDays = 10
    place = s2b32('10001.saopaulo')

    with brownie.reverts("ERROR:RAINRP-021:LIFETIME_INVALID"):
        bundleId1 = create_bundle(
            instance, 
            instanceOperator, 
            investor, 
            riskpool, 
            bundleFunding, 
            bundleName,
            bundleLifetimeDays,
            minProtectedBalance, 
            maxProtectedBalance, 
            minDurationDays, 
            maxDurationDays, 
            place)

    assert instanceService.bundles() == 0

    bundleLifetimeDays = 60  # ok
    bundleId2 = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool, 
        bundleFunding, 
        bundleName,
        bundleLifetimeDays,
        minProtectedBalance, 
        maxProtectedBalance, 
        minDurationDays, 
        maxDurationDays, 
        place)

    assert instanceService.bundles() == 1

    bundleLifetimeDays = 500  # too long

    with brownie.reverts("ERROR:RAINRP-021:LIFETIME_INVALID"):
        bundleId3 = create_bundle(
            instance, 
            instanceOperator, 
            investor, 
            riskpool, 
            bundleFunding, 
            bundleName,
            bundleLifetimeDays,
            minProtectedBalance, 
            maxProtectedBalance, 
            minDurationDays, 
            maxDurationDays, 
            place)

    assert instanceService.bundles() == 1


def test_create_max_protected_balance_validation(
    instance,
    instanceService,
    instanceOperator,
    investor,
    riskpool,
):
    instanceWallet = instanceService.getInstanceWallet()
    riskpoolWallet = instanceService.getRiskpoolWallet(riskpool.getId())
    tokenAddress = instanceService.getComponentToken(riskpool.getId())
    token = interface.IERC20Metadata(tokenAddress)

    bundleFunding = 10000

    # check initialized riskpool
    assert instanceService.bundles() == 0

    bundleName = ''
    bundleLifetimeDays = 90
    minProtectedBalance =  2000
    maxProtectedBalance = 0 # too low
    minDurationDays = 3
    maxDurationDays = 10
    place = s2b32('10001.saopaulo')

    with brownie.reverts("ERROR:RAINRP-022:MAX_PROTECTED_BALANCE_INVALID"):
        bundleId1 = create_bundle(
            instance, 
            instanceOperator, 
            investor, 
            riskpool, 
            bundleFunding, 
            bundleName,
            bundleLifetimeDays,
            minProtectedBalance, 
            maxProtectedBalance, 
            minDurationDays, 
            maxDurationDays, 
            place)

    assert instanceService.bundles() == 0

    maxProtectedBalance = 3000 # ok
    bundleId2 = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool, 
        bundleFunding, 
        bundleName,
        bundleLifetimeDays,
        minProtectedBalance, 
        maxProtectedBalance, 
        minDurationDays, 
        maxDurationDays, 
        place)

    assert instanceService.bundles() == 1

    maxProtectedBalance = 10000000 # too large

    with brownie.reverts("ERROR:RAINRP-022:MAX_PROTECTED_BALANCE_INVALID"):
        bundleId3 = create_bundle(
            instance, 
            instanceOperator, 
            investor, 
            riskpool, 
            bundleFunding, 
            bundleName,
            bundleLifetimeDays,
            minProtectedBalance, 
            maxProtectedBalance, 
            minDurationDays, 
            maxDurationDays, 
            place)

    assert instanceService.bundles() == 1


def test_create_min_protected_balance_validation(
    instance,
    instanceService,
    instanceOperator,
    investor,
    riskpool,
):
    instanceWallet = instanceService.getInstanceWallet()
    riskpoolWallet = instanceService.getRiskpoolWallet(riskpool.getId())
    tokenAddress = instanceService.getComponentToken(riskpool.getId())
    token = interface.IERC20Metadata(tokenAddress)

    bundleFunding = 10000

    # check initialized riskpool
    assert instanceService.bundles() == 0

    bundleName = ''
    bundleLifetimeDays = 90
    minProtectedBalance =  0 # too low
    maxProtectedBalance = 5000
    minDurationDays = 3
    maxDurationDays = 10
    place = s2b32('10001.saopaulo')

    with brownie.reverts("ERROR:RAINRP-023:MIN_PROTECTED_BALANCE_INVALID"):
        bundleId1 = create_bundle(
            instance, 
            instanceOperator, 
            investor, 
            riskpool, 
            bundleFunding, 
            bundleName,
            bundleLifetimeDays,
            minProtectedBalance, 
            maxProtectedBalance, 
            minDurationDays, 
            maxDurationDays, 
            place)

    assert instanceService.bundles() == 0

    minProtectedBalance = maxProtectedBalance - 1 # ok
    bundleId2 = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool, 
        bundleFunding, 
        bundleName,
        bundleLifetimeDays,
        minProtectedBalance, 
        maxProtectedBalance, 
        minDurationDays, 
        maxDurationDays, 
        place)

    assert instanceService.bundles() == 1

    minProtectedBalance = maxProtectedBalance + 1 # too large

    with brownie.reverts("ERROR:RAINRP-022:MAX_PROTECTED_BALANCE_INVALID"):
        bundleId3 = create_bundle(
            instance, 
            instanceOperator, 
            investor, 
            riskpool, 
            bundleFunding, 
            bundleName,
            bundleLifetimeDays,
            minProtectedBalance, 
            maxProtectedBalance, 
            minDurationDays, 
            maxDurationDays, 
            place)

    assert instanceService.bundles() == 1


def test_create_capital_validation(
    instance,
    instanceService,
    instanceOperator,
    investor,
    riskpool,
):
    instanceWallet = instanceService.getInstanceWallet()
    riskpoolWallet = instanceService.getRiskpoolWallet(riskpool.getId())
    tokenAddress = instanceService.getComponentToken(riskpool.getId())
    token = interface.IERC20Metadata(tokenAddress)

    bundleFunding = 0 # too low

    # check initialized riskpool
    assert instanceService.bundles() == 0

    bundleName = ''
    bundleLifetimeDays = 90
    minProtectedBalance =  1000
    maxProtectedBalance = 5000
    minDurationDays = 3
    maxDurationDays = 10
    place = s2b32('10001.saopaulo')

    with brownie.reverts("ERROR:RAINRP-027:RISK_CAPITAL_INVALID"):
        bundleId1 = create_bundle(
            instance, 
            instanceOperator, 
            investor, 
            riskpool, 
            bundleFunding, 
            bundleName,
            bundleLifetimeDays,
            minProtectedBalance, 
            maxProtectedBalance, 
            minDurationDays, 
            maxDurationDays, 
            place)

    assert instanceService.bundles() == 0

    bundleFunding = maxProtectedBalance # ok
    bundleId2 = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool, 
        bundleFunding, 
        bundleName,
        bundleLifetimeDays,
        minProtectedBalance, 
        maxProtectedBalance, 
        minDurationDays, 
        maxDurationDays, 
        place)

    assert instanceService.bundles() == 1

    bundleFunding = 1000000 * 10**token.decimals() # too large

    with brownie.reverts("ERROR:RAINRP-027:RISK_CAPITAL_INVALID"):
        bundleId3 = create_bundle(
            instance, 
            instanceOperator, 
            investor, 
            riskpool, 
            bundleFunding, 
            bundleName,
            bundleLifetimeDays,
            minProtectedBalance, 
            maxProtectedBalance, 
            minDurationDays, 
            maxDurationDays, 
            place)

    assert instanceService.bundles() == 1
