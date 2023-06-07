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
    RainOracleCLFunctions,
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

from scripts.util import (
    contract_from_address,
    s2b32
)

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
PRECIP_HIST = 5.0
PRECIP_HIST_DAYS = 2

# default setup for all_in_1 -> create_bundle
BUNDLE_FUNDING = 10 ** 6

# default setup for all_in_1 -> create_policy
SUM_INSURED_AMOUNT = 2000
PREMIUM_AMOUNT = 300

# contract classes for all_in_1
CONTRACT_CLASS_TOKEN = Usdc
CONTRACT_CLASS_PRODUCT = RainProduct
CONTRACT_CLASS_ORACLE = RainOracleCLFunctions # RainOracle | RainOracleCLFunctions
CONTRACT_CLASS_RISKPOOL = RainRiskpool

def help():
    print('from scripts.deploy_rain import all_in_1, verify_deploy')
    print('(customer, customer2, product, oracle, riskpool, riskpoolWallet, investor, usdc, instance, instanceService, instanceOperator, bundleId, riskId, processId, d) = all_in_1(deploy_all=True)')
    print('verify_deploy(d, usdc, product)')
    print('instanceService.getBundle(bundleId).dict()')
    print('instanceService.getPolicy(processId).dict()')


def help_testnet():
    print('======== deploy instructions for mumbai testnet ========')
    print('* Attention: in order for the following instructions to work you must have loaded the brownie console with the parameter --network=mumbai')
    print('* You can add the mumbai network by running: brownie networks add Ethereum Mumbai host=QUICKNODE_RPC_URL chainid=80001 explorer=https://api-testnet.polygonscan.com/api')
    print('from scripts.deploy_rain import all_in_1, verify_deploy')
    print('from scripts.deploy_product import stakeholders_accounts')
    print("(customer, customer2, product, oracle, riskpool, riskpoolWallet, investor, usdc, instance, instanceService, instanceOperator, bundleId, riskId, processId, d) = all_in_1(stakeholders_accounts=stakeholders_accounts(), deploy_all=False, publish_source=True, chainLinkOracleAddress='0x40193c8518BB267228Fc409a613bDbD8eC5a97b3', chainLinkJobId='ca98366cc7314957b8c012c72f05aeeb', chainLinkPaymentAmount=10**17)")
    print('verify_deploy(d, usdc, product)')
    print('instanceService.getBundle(bundleId).dict()')
    print('instanceService.getPolicy(processId).dict()')
    print('* Attention: do not forget to fund the Oracle Contract with some LINK token! https://faucets.chain.link/mumbai')
    print('========================================================')


def help_testnet_clfunctions():
    print('======== deploy instructions for mumbai testnet + chainlink functions oracle & automation ========')
    print('* Attention: in order for the following instructions to work you must have loaded the brownie console with the parameter --network=mumbai or --network=polygon-test')
    print('* You can add the mumbai network by running: brownie networks add Ethereum Mumbai host=QUICKNODE_RPC_URL chainid=80001 explorer=https://api-testnet.polygonscan.com/api')
    print('* These instructions assume that you have already deployed a full GIF instance before')
    print('* First of all make sure you have the ORACLE_PROVIDER address whitelisted to use the Chainlink Functions beta')
    print('* Clone the following Hardhat project https://github.com/Rainsurance/functions-hardhat-starter-kit and follow its setup inscructions')
    print('* You need to deploy the Chainlink Functions-based Oracle/Client contract by running the task `functions-deploy-rainsurance` (use the ORACLE_PROVIDER account for that)')
    print('* Second you must create a new Chainlink Functions subscription and add that contract as consumer by running the task `functions-sub-create`')
    print('* Then you must register a new Chainlink Upkeep by visiting this website: https://automation.chain.link/mumbai/new (choose Custom Logic / enter the contract address / 700000 as gas limit / fund the contract with LINK)')
    print('* Finally you must add the address of the contract in the `git_instance_adress.txt` file in this projects root directory as `oracle`')
    print('* Now you are all set on the Oracle side! You can run the following instructions inside the brownie console to deploy the GIF Product and RiskPool:')
    print('from scripts.deploy_rain import all_in_1, verify_deploy')
    print('from scripts.deploy_product import stakeholders_accounts')
    print("(customer, customer2, product, oracle, riskpool, riskpoolWallet, investor, usdc, instance, instanceService, instanceOperator, bundleId, riskId, processId, d) = all_in_1(stakeholders_accounts=stakeholders_accounts(), deploy_all=False, publish_source=True, chainLinkOracleAddress='0xeA6721aC65BCeD841B8ec3fc5fEdeA6141a0aDE4')")
    print('verify_deploy(d, usdc, product)')
    print('instanceService.getBundle(bundleId).dict()')
    print('instanceService.getPolicy(processId).dict()')
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
    precHist = PRECIP_HIST,
    precDays = PRECIP_HIST_DAYS
):    
    multiplier = product.getPercentageMultiplier()
    coordMultiplier = product.getCoordinatesMultiplier()
    precMultiplier = product.getPrecipitationMultiplier()
    tx = product.createRisk(startDate, endDate, placeId, coordMultiplier * lat, coordMultiplier * long, multiplier * trigger, multiplier * exit, precHist * precMultiplier, precDays, {'from': insurer})
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