import time

from brownie.network import accounts
from brownie.network.account import Account

from brownie import (
    interface,
    RainProduct,
    RainRiskpool
)

from scripts.instance import GifInstance
from scripts.util import (
    s2b32, 
    contract_from_address
)

DEFAULT_BUNDLE_FUNDING = 100000
DEFAULT_BUNDLE_MIN_PROTECTED_BALANCE =  100
DEFAULT_BUNDLE_MAX_PROTECTED_BALANCE = 5000
DEFAULT_BUNDLE_MIN_DURATION_DAYS =  1
DEFAULT_BUNDLE_MAX_DURATION_DAYS =  15
DEFAULT_BUNDLE_LIFETIME_DAYS = 90

DEFAULT_PROTECTED_BALANCE = 1000
DEFAULT_PREMIUM = 75

ONE_DAY_DURATION = 1 * 24 * 3600; 

DEFAULT_RISK_PLACE = '10001.saopaulo' #s2b32('10001.saopaulo')
DEFAULT_RISK_START_DATE = time.time() + 100
DEFAULT_RISK_END_DATE = DEFAULT_RISK_START_DATE + 2 * ONE_DAY_DURATION
DEFAULT_RISK_LAT = -23.550620
DEFAULT_RISK_LNG = -46.634370
DEFAULT_RISK_TRIGGER = 0.1
DEFAULT_RISK_EXIT = 1.0
DEFAULT_RISK_PRECIP_HIST = 5.0
DEFAULT_RISK_PRECIP_HIST_DAYS = 1


def fund_account(
    instance: GifInstance, 
    owner: Account,
    account: Account,
    token: interface.IERC20,
    amount: int
):
    token.transfer(account, amount, {'from': owner})
    token.approve(instance.getTreasury(), amount, {'from': account})


def create_bundle(
    instance: GifInstance, 
    instanceOperator: Account,
    investor: Account,
    riskpool: RainRiskpool,
    funding: int = DEFAULT_BUNDLE_FUNDING,
    bundleName: str = '',
    bundleLifetimeDays: int = DEFAULT_BUNDLE_LIFETIME_DAYS,
    minProtectedBalance: int = DEFAULT_BUNDLE_MIN_PROTECTED_BALANCE,
    maxProtectedBalance: int = DEFAULT_BUNDLE_MAX_PROTECTED_BALANCE,
    minDurationDays: int = DEFAULT_BUNDLE_MIN_DURATION_DAYS,
    maxDurationDays: int = DEFAULT_BUNDLE_MAX_DURATION_DAYS,
    place: str = DEFAULT_RISK_PLACE,
) -> int:
    tokenAddress = riskpool.getErc20Token()
    token = contract_from_address(interface.IERC20Metadata, tokenAddress)
    tf = 10 ** token.decimals()

    instanceService = instance.getInstanceService()
    token.transfer(investor, funding * tf, {'from': instanceOperator})
    token.approve(instanceService.getTreasuryAddress(), funding * tf, {'from': investor})
    spd = 24 * 3600

    tx = riskpool.createBundle(
        bundleName,
        bundleLifetimeDays * spd,
        minProtectedBalance * tf,
        maxProtectedBalance * tf,
        minDurationDays * spd,
        maxDurationDays * spd,
        funding * tf, 
        place,
        {'from': investor})

    return tx.events['LogRiskpoolBundleCreated']['bundleId']


def create_risk(
    product: RainProduct,
    insurer: Account, 
    startDate = DEFAULT_RISK_START_DATE,
    endDate = DEFAULT_RISK_END_DATE,
    place = DEFAULT_RISK_PLACE,
    lat = DEFAULT_RISK_LAT,
    long = DEFAULT_RISK_LNG,
    trigger = DEFAULT_RISK_TRIGGER,
    exit = DEFAULT_RISK_EXIT,
    precHist = DEFAULT_RISK_PRECIP_HIST,
    precDays = DEFAULT_RISK_PRECIP_HIST_DAYS
):    
    multiplier = product.getPercentageMultiplier()
    coordMultiplier = product.getCoordinatesMultiplier()
    precMultiplier = product.getPrecipitationMultiplier()

    tx = product.createRisk(startDate, endDate, place, coordMultiplier * lat, coordMultiplier * long, multiplier * trigger, multiplier * exit, precHist * precMultiplier, precDays, {'from': insurer})

    return tx.return_value
    # return tx.events['LogRainRiskDataCreated']['riskId']


def apply_for_policy_with_bundle(
    instance: GifInstance, 
    instanceOperator: Account,
    customer: Account,
    product: RainProduct, 
    bundleId: int,
    riskId: bytes,
    wallet: Account = None,
    sumInsured: int = DEFAULT_PROTECTED_BALANCE,
    premium: int = DEFAULT_PREMIUM,
    transferPremium: bool = True
):
    tokenAddress = product.getToken()
    token = contract_from_address(interface.IERC20Metadata, tokenAddress)
    tf = 10 ** token.decimals()

    # transfer premium funds to customer and create allowance
    if transferPremium and premium > 0:
        premiumPlusFees = product.calculatePremium(premium * tf)
        fund_account(
            instance, 
            instanceOperator,
            customer,
            token,
            premiumPlusFees)

    if not wallet:
        wallet = customer

    tx = product.applyForPolicyWithBundle(
        wallet,
        premium * tf,
        sumInsured * tf,
        riskId,
        bundleId, 
        {'from': customer}) #insurer

    return tx.events['LogRainApplicationCreated']['processId']

# deprecated
def fund_riskpool(
    instance: GifInstance, 
    owner: Account,
    capitalOwner: Account,
    riskpool,
    bundleOwner: Account,
    coin,
    amount: int,
    createBundle: bool = True 
):
    # transfer funds to riskpool keeper and create allowance
    safetyFactor = 2
    coin.transfer(bundleOwner, safetyFactor * amount, {'from': owner})
    coin.approve(instance.getTreasury(), safetyFactor * amount, {'from': bundleOwner})

    # create approval for treasury from capital owner to allow for withdrawls
    maxUint256 = 2**256-1
    coin.approve(instance.getTreasury(), maxUint256, {'from': capitalOwner})

    applicationFilter = bytes(0)

    bundleId = None

    if (createBundle):
        tx = riskpool.createBundle(
            applicationFilter, 
            amount, 
            {'from': bundleOwner})
        bundleId = tx.return_value
    
    return bundleId


def get_bundle_dict(instance, riskpool, bundleIdx):
    return get_bundle(instance, riskpool, bundleIdx).dict()


def get_bundle(instance, riskpool, bundleIdx):
    instanceService = instance.getInstanceService()
    bundleId = riskpool.getBundleId(bundleIdx)
    return instanceService.getBundle(bundleId)