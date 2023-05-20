import time
import os

from brownie.network import accounts
from brownie.network.account import Account
from brownie import (
    interface,
    network,
    web3,
    Usdc,
    RainProduct,
    RainOracle,
    RainRiskpool
)

from scripts.deploy_product import (
    all_in_1_base,
    verify_deploy_base,
    from_component_base,
    from_registry_base,
    fund_and_create_allowance,
    get_product_token,
    get_riskpool_token,
    get_bundle_id,
    to_token_amount
)

from scripts.util import s2b32

# product/oracle/riskpool base name
BASE_NAME = 'Rain'

# default setup for all_in_1 -> create_policy
START_DATE = time.time() + 1000
END_DATE = time.time() + 10000
PLACE_ID = s2b32('10001.saopaulo')
LAT_FLOAT = -23.550620
LONG_FLOAT = -46.634370
TRIGGER = 0.1
EXIT = 1.0
APH = 5.0

# default setup for all_in_1 -> create_bundle
BUNDLE_FUNDING = 10 ** 6

# default setup for all_in_1 -> create_policy
SUM_INSURED_AMOUNT = 2000
PREMIUM_AMOUNT = 300

# contract classes for all_in_1
CONTRACT_CLASS_TOKEN = Usdc
CONTRACT_CLASS_PRODUCT = RainProduct
CONTRACT_CLASS_ORACLE = RainOracle
CONTRACT_CLASS_RISKPOOL = RainRiskpool

def help():
    print('from scripts.deploy_rain import all_in_1, verify_deploy')
    print('(customer, customer2, product, oracle, riskpool, riskpoolWallet, investor, usdc, instance, instanceService, instanceOperator, bundleId, riskId, processId, d) = all_in_1(deploy_all=True)')
    print('verify_deploy(d, usdc, product)')
    print('instanceService.getBundle(bundleId).dict()')
    print('instanceService.getPolicy(processId).dict()')


def help_testnet():
    print('======== deploy instructions for mumbai testnet ========')
    print('Attention: in order for the following instructions to work you must have loaded the brownie console with the parameter --network=mumbai')
    print('You can add the mumbai network by running: brownie networks add Ethereum Mumbai host=QUICKNODE_RPC_URL chainid=80001 explorer=https://api-testnet.polygonscan.com/api')
    print('from scripts.deploy_rain import all_in_1, verify_deploy')
    print('from scripts.deploy_product import stakeholders_accounts')
    print("(customer, customer2, product, oracle, riskpool, riskpoolWallet, investor, usdc, instance, instanceService, instanceOperator, bundleId, riskId, processId, d) = all_in_1(stakeholders_accounts=stakeholders_accounts(), deploy_all=False, publish_source=True, chainLinkTokenAddress='0x326C977E6efc84E512bB9C30f76E30c160eD06FB', chainLinkOracleAddress='0x40193c8518BB267228Fc409a613bDbD8eC5a97b3', chainLinkJobId='ca98366cc7314957b8c012c72f05aeeb', chainLinkPaymentAmount=10**17)")
    print('verify_deploy(d, usdc, product)')
    print('instanceService.getBundle(bundleId).dict()')
    print('instanceService.getPolicy(processId).dict()')
    print('Attention: do not forget to fund the Oracle Contract with some LINK token! https://faucets.chain.link/mumbai')
    print('========================================================')


def create_bundle(
    instance, 
    instance_operator,
    riskpool,
    investor,
    bundle_funding = BUNDLE_FUNDING
):
    # fund riskpool with risk bundle
    token = get_riskpool_token(riskpool)
    funding_amount = to_token_amount(token, bundle_funding)

    fund_and_create_allowance(
        instance,
        instance_operator,
        investor,
        token,
        funding_amount)

    # create new risk bundle
    bundle_filter = bytes(0)
    tx = riskpool.createBundle(
        bundle_filter,
        funding_amount, 
        {'from': investor})

    return get_bundle_id(tx)

def create_risk(
    product,
    insurer,
    startDate = START_DATE,
    endDate = END_DATE,
    placeId = PLACE_ID,
    lat = LAT_FLOAT,
    long = LONG_FLOAT,
    trigger = TRIGGER,
    exit = EXIT,
    aph = APH
):    
    multiplier = product.getPercentageMultiplier()
    coordMultiplier = product.getCoordinatesMultiplier()
    tx = product.createRisk(startDate, endDate, placeId, coordMultiplier * lat, coordMultiplier * long, multiplier * trigger, multiplier * exit, aph, {'from': insurer})
    return tx.events['LogRainRiskDataCreated']['riskId']

def create_policy(
    instance, 
    instance_operator,
    product,
    riskId,
    customer,
    insurer,
    sum_insured_amount = SUM_INSURED_AMOUNT,
    premium_amount = PREMIUM_AMOUNT,
):
    token = get_product_token(product)

    fund_and_create_allowance(
        instance,
        instance_operator,
        customer,
        token,
        premium_amount)

    tx = product.applyForPolicy(customer, premium_amount, sum_insured_amount, riskId, {'from': insurer})

    return tx.events['LogRainPolicyApplicationCreated']['policyId']

def all_in_1(
    stakeholders_accounts=None,
    registry_address=None,
    usdc_address=None,
    deploy_all=False,
    publish_source=False,
    chainLinkTokenAddress=None,
    chainLinkOracleAddress=None,
    chainLinkJobId=None,
    chainLinkPaymentAmount=None
):
    return all_in_1_base(
        BASE_NAME,
        CONTRACT_CLASS_TOKEN, 
        CONTRACT_CLASS_PRODUCT, 
        CONTRACT_CLASS_ORACLE, 
        CONTRACT_CLASS_RISKPOOL,
        create_bundle,
        create_risk,
        create_policy,
        stakeholders_accounts,
        registry_address,
        usdc_address,
        deploy_all=deploy_all,
        publish_source=publish_source,
        chainLinkTokenAddress=chainLinkTokenAddress,
        chainLinkOracleAddress=chainLinkOracleAddress,
        chainLinkJobId=chainLinkJobId,
        chainLinkPaymentAmount=chainLinkPaymentAmount)


def verify_deploy(
    stakeholder_accounts, 
    token,
    product
):
    verify_deploy_base(
        from_component,
        stakeholder_accounts, 
        token, 
        product)

def from_component(
    component_address,
    product_id=0,
    oracle_id=0,
    riskpool_id=0
):
    return from_component_base(
        component_address,
        CONTRACT_CLASS_PRODUCT,
        CONTRACT_CLASS_ORACLE,
        CONTRACT_CLASS_RISKPOOL,
        product_id, 
        oracle_id, 
        riskpool_id)

def from_registry(
    registry_address,
    product_id=0,
    oracle_id=0,
    riskpool_id=0
):
    return from_registry_base(
        registry_address,
        CONTRACT_CLASS_PRODUCT,
        CONTRACT_CLASS_ORACLE,
        CONTRACT_CLASS_RISKPOOL,
        product_id, 
        oracle_id, 
        riskpool_id)