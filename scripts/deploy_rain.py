import time
import os

from brownie.network import accounts
from brownie.network.account import Account
from brownie import (
    interface,
    network,
    web3,
    Usdc,
    DIP,
    RainProduct,
    RainOracle,
    RainOracleCLFunctions,
    RainRiskpool,
    MockRegistryStaking,
)

from scripts.const import (
    BUNDLE_STATE,
    APPLICATION_STATE,
    POLICY_STATE,
    COMPONENT_STATE,
    ZERO_ADDRESS,
    INSTANCE_OPERATOR,
    INVESTOR,
    INSURER,
    CUSTOMER1,
    INSTANCE,
    RISKPOOL,
    INSTANCE_SERVICE,
    PRODUCT,
    ERC20_TOKEN,
    INSTANCE,
    INSTANCE_SERVICE,
    PRODUCT,
    RISKPOOL
)

from scripts.setup import create_bundle, create_risk, apply_for_policy_with_bundle

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
    new_accounts,
    get_package,
    is_forked_network,
    get_iso_datetime,
    s2b32,
    b2s,
    s2b,
)

# product/oracle/riskpool base name
BASE_NAME = 'Rain'

# default setup for all_in_1 -> create_policy
START_DATE = time.time() + 1000
END_DATE = time.time() + 10000
PLACE_ID = '10001.saopaulo'
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
CONTRACT_CLASS_ORACLE = RainOracle # RainOracle | RainOracleCLFunctions
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


def get_deploy_timestamp(name):
    name_timestamp_from = len('Rain')
    name_timestamp_to = name_timestamp_from + 12

    timestamp = name[name_timestamp_from:name_timestamp_to]
    if timestamp[0] == '_':
        return int(timestamp[1:-1])
    
    return int(timestamp[:-2])


def get_policy(process_id, product_address):
    product = contract_from_address(RainProduct, product_address)
    product_contract = (RainProduct._name, product.getId(), str(product))

    token = contract_from_address(interface.IERC20Metadata, product.getToken())
    protected_token = contract_from_address(interface.IERC20Metadata, product.getProtectedToken())
    tf = 10**token.decimals()

    (instance_service, instance_operator, treasury, instance_registry) = get_instance(product)
    riskpool = get_riskpool(product, instance_service)

    meta = instance_service.getMetadata(process_id).dict()
    application = instance_service.getApplication(process_id).dict()
    application_params = riskpool.decodeApplicationParameterFromData(application['data']).dict()
    policy = instance_service.getPolicy(process_id).dict()

    policy_setup = {}
    policy_setup['application'] = {}
    policy_setup['application']['process_id'] = str(process_id)
    policy_setup['application']['product_id'] = meta['productId']
    policy_setup['application']['owner'] = meta['owner']
    policy_setup['application']['state'] = _get_application_state(application['state'])
    policy_setup['application']['premium'] = (application['premiumAmount']/10**token.decimals(), application['premiumAmount'])
    policy_setup['application']['sum_insured'] = (application['sumInsuredAmount']/10**token.decimals(), application['sumInsuredAmount'])

    policy_setup['application']['bundle_id'] = application_params['bundleId']
    policy_setup['application']['duration'] = (application_params['duration']/(24*3600), application_params['duration'])
    policy_setup['application']['protected_balance'] = (application_params['sumInsured']/10**token.decimals(), application_params['sumInsured'])
    policy_setup['application']['protected_wallet'] = application_params['wallet']

    policy_setup['policy'] = {}
    policy_setup['policy']['claims'] = policy['claimsCount']
    policy_setup['policy']['claims_open'] = policy['openClaimsCount']
    policy_setup['policy']['payout'] = (policy['payoutAmount']/10**token.decimals(), policy['payoutAmount'])
    policy_setup['policy']['premium_paid'] = (policy['premiumPaidAmount']/10**token.decimals(), policy['premiumPaidAmount'])
    policy_setup['policy']['state'] = _get_policy_state(policy['state'])

    policy_setup['timestamps'] = {}
    policy_setup['timestamps']['created_at'] = (get_iso_datetime(meta['createdAt']), meta['createdAt'])
    policy_setup['timestamps']['updated_at'] = (get_iso_datetime(policy['updatedAt']), policy['updatedAt'])

    expiry_at = meta['createdAt'] + application_params['duration']
    policy_setup['timestamps']['expiry_at'] = (get_iso_datetime( expiry_at), expiry_at)

    return policy_setup


def get_bundle(bundle_id, product_address):
    product = contract_from_address(RainProduct, product_address)

    token = contract_from_address(interface.IERC20Metadata, product.getToken())
    protected_token = contract_from_address(interface.IERC20Metadata, product.getProtectedToken())
    tf = 10**token.decimals()

    (instance_service, instance_operator, treasury, instance_registry) = get_instance(product)
    riskpool = get_riskpool(product, instance_service)
    riskpool_contract = (RainRiskpool._name, riskpool.getId(), str(riskpool))

    chain_registry = contract_from_address(interface.IChainRegistryFacadeExt, riskpool.getChainRegistry())
    staking = contract_from_address(interface.IStakingFacade, riskpool.getStaking())

    bundle = instance_service.getBundle(bundle_id).dict()
    bundle_params = riskpool.decodeBundleParamsFromFilter(bundle['filter']).dict()
    capacity = bundle['capital'] - bundle['lockedCapital']
    protection_factor = 100/riskpool.getSumInsuredPercentage()
    available = protection_factor * capacity

    bundle_setup = {}
    bundle_setup['bundle'] = {}
    bundle_setup['bundle']['id'] = bundle['id']
    bundle_setup['bundle']['name'] = bundle_params['name']
    bundle_setup['bundle']['lifetime'] = (bundle_params['lifetime']/(24 * 3600), bundle_params['lifetime'])
    bundle_setup['bundle']['riskpool_id'] = bundle['riskpoolId']
    bundle_setup['bundle']['riskpool'] = riskpool_contract
    bundle_setup['bundle']['state'] = _get_bundle_state(bundle['state'])

    bundle_setup['filter'] = {}
    bundle_setup['filter']['place'] = (bundle_params['place'], s2b32(bundle_params['place']))
    bundle_setup['filter']['duration_min'] = (bundle_params['minDuration']/(24 * 3600), bundle_params['minDuration'])
    bundle_setup['filter']['duration_max'] = (bundle_params['maxDuration']/(24 * 3600), bundle_params['maxDuration'])
    bundle_setup['filter']['protection_min'] = (protection_factor * bundle_params['minSumInsured']/tf, protection_factor * bundle_params['minSumInsured'])
    bundle_setup['filter']['protection_max'] = (protection_factor * bundle_params['maxSumInsured']/tf, protection_factor * bundle_params['maxSumInsured'])

    bundle_setup['financials'] = {}
    bundle_setup['financials']['available'] = (available/tf, available)
    bundle_setup['financials']['balance'] = (bundle['balance']/tf, bundle['balance'])
    bundle_setup['financials']['capacity'] = (capacity/tf, capacity)
    bundle_setup['financials']['capital'] = (bundle['capital']/tf, bundle['capital'])
    bundle_setup['financials']['capital_locked'] = (bundle['lockedCapital']/tf, bundle['lockedCapital'])

    bundle_nft_id = chain_registry.getBundleNftId(instance_service.getInstanceId(), bundle['id'])
    bundle_nft_info = None

    try:
        bundle_nft_info = chain_registry.getNftInfo(bundle_nft_id).dict()
    except Exception as e:
        bundle_nft_info = {'message': 'n/a'}

    bundle_cs = staking.capitalSupport(bundle_nft_id)
    bundle_setup['staking'] = {}
    bundle_setup['staking']['nft_id'] = bundle_nft_id
    bundle_setup['staking']['nft_info'] = bundle_nft_info
    bundle_setup['staking']['capital_support'] = (bundle_cs/tf, bundle_cs)

    bundle_setup['timestamps'] = {}
    bundle_setup['timestamps']['created_at'] = (get_iso_datetime(bundle['createdAt']), bundle['createdAt'])
    bundle_setup['timestamps']['updated_at'] = (get_iso_datetime(bundle['updatedAt']), bundle['updatedAt'])

    open_until = bundle['createdAt'] + bundle_params['lifetime']
    bundle_setup['timestamps']['open_until'] = (get_iso_datetime(open_until), open_until)

    return bundle_setup


def get_setup(product_address):

    product = contract_from_address(RainProduct, product_address)
    product_id = product.getId()
    product_name = b2s(product.getName())
    product_contract = (RainProduct._name, str(product))
    product_owner = product.owner()

    token = contract_from_address(interface.IERC20Metadata, product.getToken())
    protected_token = contract_from_address(interface.IERC20Metadata, product.getProtectedToken())

    (instance_service, instance_operator, treasury, instance_registry) = get_instance(product)
    riskpool = get_riskpool(product, instance_service)
    riskpool_id = riskpool.getId()
    riskpool_name = b2s(riskpool.getName())
    riskpool_contract = (RainRiskpool._name, str(riskpool))
    riskpool_sum_insured_cap = riskpool.getSumOfSumInsuredCap()
    riskpool_owner = riskpool.owner()

    riskpool_capital_cap = -1
    try:
        riskpool_capital_cap = riskpool.getRiskpoolCapitalCap()
    except Exception as e:
        print('failed to call riskpool.getRiskpoolCapitalCap(): {}'.format(e))

    riskpool_bundle_cap = riskpool.getBundleCapitalCap()
    riskpool_token = contract_from_address(interface.IERC20Metadata, riskpool.getErc20Token())

    (staking, registry, nft, dip_token) = (None, None, None, None)

    if riskpool.getStaking() != ZERO_ADDRESS:
        staking = contract_from_address(interface.IStakingFacade, riskpool.getStaking())
        staking_contract = (interface.IStakingFacade._name, str(staking))
        staking_owner = staking.owner()
        dip_token = contract_from_address(DIP, staking.getDip())

        registry = contract_from_address(interface.IChainRegistryFacadeExt, staking.getRegistry())
        registry_contract = (interface.IChainRegistryFacadeExt._name, str(registry))
        registry_owner = registry.owner()

        nft = contract_from_address(interface.IChainNftFacade, registry.getNft())
        nft_contract = (interface.IChainNftFacade._name, str(nft))

    setup = {}
    setup['instance'] = {}
    setup['product'] = {}
    setup['feeder'] = {}
    setup['riskpool'] = {}
    setup['bundle'] = {}
    setup['policy'] = {}
    setup['nft'] = {}
    setup['registry'] = {}
    setup['staking'] = {}

    # instance specifics
    setup['instance']['id'] = str(instance_service.getInstanceId())
    setup['instance']['chain'] = (instance_service.getChainName(), instance_service.getChainId())
    setup['instance']['instance_registry'] = instance_service.getRegistry()
    setup['instance']['instance_operator'] = instance_operator
    setup['instance']['release'] = b2s(instance_registry.getRelease())
    setup['instance']['wallet'] = instance_service.getInstanceWallet()
    setup['instance']['products'] = instance_service.products()
    setup['instance']['oracles'] = instance_service.oracles()
    setup['instance']['riskpools'] = instance_service.riskpools()
    setup['instance']['bundles'] = instance_service.bundles()

    wallet_balance = token.balanceOf(instance_service.getInstanceWallet())
    setup['instance']['wallet_balance'] = (wallet_balance / 10 ** token.decimals(), wallet_balance)

    # product specifics
    setup['product']['contract'] = product_contract
    setup['product']['id'] = product_id
    setup['product']['owner'] = product_owner
    setup['product']['state'] = _getComponentState(product.getId(), instance_service)
    setup['product']['riskpool_id'] = product.getRiskpoolId()
    setup['product']['deployed_at'] = (get_iso_datetime(get_deploy_timestamp(product_name)), get_deploy_timestamp(product_name))
    setup['product']['premium_fee'] = _get_fee_spec(product_id, treasury, instance_service)
    setup['product']['token'] = (token.symbol(), str(token), token.decimals())
    setup['product']['protected_token'] = (protected_token.symbol(), str(protected_token), protected_token.decimals())
    setup['product']['applications'] = product.applications()
    setup['product']['policies'] = product.policies()

    # riskpool specifics
    setup['riskpool']['contract'] = riskpool_contract
    setup['riskpool']['id'] = riskpool_id
    setup['riskpool']['owner'] = riskpool_owner
    setup['riskpool']['state'] = _getComponentState(riskpool.getId(), instance_service)
    setup['riskpool']['staking'] = riskpool.getStaking()
    setup['riskpool']['deployed_at'] = (get_iso_datetime(get_deploy_timestamp(riskpool_name)), get_deploy_timestamp(riskpool_name))
    setup['riskpool']['capital_fee'] = _get_fee_spec(riskpool_id, treasury, instance_service)
    setup['riskpool']['token'] = (riskpool_token.symbol(), str(riskpool_token), riskpool_token.decimals())

    setup['riskpool']['sum_insured_cap'] = (riskpool_sum_insured_cap / 10**riskpool_token.decimals(), riskpool_sum_insured_cap)

    try:
        setup['riskpool']['sum_insured_percentage'] = (riskpool.getSumInsuredPercentage()/100, riskpool.getSumInsuredPercentage())
    except Exception as e:
        setup['riskpool']['sum_insured_percentage'] = (1.0, 100)

    setup['riskpool']['bundles'] = riskpool.bundles()
    setup['riskpool']['bundles_active'] = riskpool.activeBundles()
    setup['riskpool']['bundles_max'] = riskpool.getMaximumNumberOfActiveBundles()
    setup['riskpool']['capital_cap'] = (riskpool_capital_cap / 10**riskpool_token.decimals(), riskpool_capital_cap)

    setup['riskpool']['balance'] = (riskpool.getBalance() / 10**riskpool_token.decimals(), riskpool.getBalance())
    setup['riskpool']['capital'] = (riskpool.getCapital() / 10**riskpool_token.decimals(), riskpool.getCapital())
    setup['riskpool']['capacity'] = (riskpool.getCapacity() / 10**riskpool_token.decimals(), riskpool.getCapacity())
    setup['riskpool']['total_value_locked'] = (riskpool.getTotalValueLocked() / 10**riskpool_token.decimals(), riskpool.getTotalValueLocked())

    riskpool_wallet = instance_service.getRiskpoolWallet(riskpool_id)
    setup['riskpool']['wallet'] = riskpool_wallet
    setup['riskpool']['wallet_allowance'] = (riskpool_token.allowance(riskpool_wallet, instance_service.getTreasuryAddress()) / 10**riskpool_token.decimals(), riskpool_token.balanceOf(riskpool_wallet))
    setup['riskpool']['wallet_balance'] = (riskpool_token.balanceOf(riskpool_wallet) / 10**riskpool_token.decimals(), riskpool_token.balanceOf(riskpool_wallet))

    # bundle specifics
    spd = 24 * 3600
    setup['bundle']['apr_max'] = (riskpool.MAX_APR()/riskpool.APR_100_PERCENTAGE(), riskpool.MAX_APR())
    setup['bundle']['capital_cap'] = (riskpool_bundle_cap / 10**riskpool_token.decimals(), riskpool_bundle_cap)
    setup['bundle']['lifetime_min'] = (riskpool.MIN_BUNDLE_LIFETIME()/spd , riskpool.MIN_BUNDLE_LIFETIME())
    setup['bundle']['lifetime_max'] = (riskpool.MAX_BUNDLE_LIFETIME()/spd , riskpool.MAX_BUNDLE_LIFETIME())

    # policy specifics
    setup['policy']['duration_min'] = (riskpool.MIN_POLICY_DURATION()/spd , riskpool.MIN_POLICY_DURATION())
    setup['policy']['duration_max'] = (riskpool.MAX_POLICY_DURATION()/spd , riskpool.MAX_POLICY_DURATION())
    setup['policy']['protection_min'] = (riskpool.MIN_POLICY_COVERAGE()/10**token.decimals() , riskpool.MIN_POLICY_COVERAGE())
    setup['policy']['protection_max'] = (riskpool.MAX_POLICY_COVERAGE()/10**token.decimals() , riskpool.MAX_POLICY_COVERAGE())

    if nft:
        setup['nft']['contract'] = nft_contract
        setup['nft']['name'] = nft.name()
        setup['nft']['symbol'] = nft.symbol()
        setup['nft']['registry'] = nft.getRegistry()

        try:
            setup['nft']['total_minted'] = nft.totalMinted()
        except Exception as e:
            setup['nft']['total_minted'] = 'n/a'
    else:
        setup['nft']['setup'] = 'WARNING nft contract not linked, not ready to use'

    if registry:
        chain_id = registry.toChain(web3.chain_id)
        registry_version = _get_version(registry)
        setup['registry']['contract'] = registry_contract
        setup['registry']['owner'] = registry_owner
        setup['registry']['nft'] = registry.getNft()
        setup['registry']['instances'] = registry.objects(chain_id, 20)
        setup['registry']['riskpools'] = registry.objects(chain_id, 23)
        setup['registry']['bundles'] = registry.objects(chain_id, 40)
        setup['registry']['stakes'] = registry.objects(chain_id, 10)
        setup['registry']['version'] = registry_version
    else:
        setup['registry']['setup'] = 'WARNING registry contract not linked, not ready to use'

    if staking:
        staking_rate = staking.stakingRate(chain_id, riskpool_token)
        staking_version = _get_version(staking)
        wallet_balance = dip_token.balanceOf(staking.getStakingWallet())
        setup['staking']['contract'] = staking_contract
        setup['staking']['chain'] = (web3.chain_id, str(chain_id))
        setup['staking']['owner'] = staking_owner
        setup['staking']['registry'] = staking.getRegistry()
        setup['staking']['dip'] = (dip_token.symbol(), str(dip_token), dip_token.decimals())
        setup['staking']['reward_balance'] = (staking.rewardBalance()/10**dip_token.decimals(), staking.rewardBalance())
        setup['staking']['reward_rate'] = (staking.rewardRate()/10**staking.rateDecimals(), staking.rewardRate())
        setup['staking']['reward_rate_max'] = (staking.maxRewardRate()/10**staking.rateDecimals(), staking.maxRewardRate())
        setup['staking']['stake_balance'] = _getStakeBalance(staking, dip_token)
        setup['staking']['staking_rate_usdt'] = (staking_rate/10**staking.rateDecimals(), staking_rate)
        setup['staking']['wallet'] = staking.getStakingWallet()
        setup['staking']['wallet_balance'] = (wallet_balance/10**dip_token.decimals(), wallet_balance)
        setup['staking']['version'] = staking_version

        swa_raw = dip_token.allowance(staking.getStakingWallet(), staking)
        swa = [swa_raw/10**dip_token.decimals(), swa_raw]
        if staking.address == staking.getStakingWallet():
            setup['staking']['wallet_allowance'] = (swa[0], swa[1], "OK wallet address is contract address")
        else:
            if swa_raw == 0:
                setup['staking']['wallet_allowance'] = (0, 0, "WARNING wallet allowance missing for staking contract, not ready to use")
            elif swa_raw < wallet_balance:            
                setup['staking']['wallet_allowance'] = (swa[0], swa[1], "WARNING wallet allowance not sufficient to cover wallet balance, make sure you know what you are doing")
            else:
                setup['staking']['wallet_allowance'] = (swa[0], swa[1], "OK wallet allowance covers wallet balance")

        if staking.rewardBalance() <= staking.rewardReserves():
            setup['staking']['reward_reserves'] = (staking.rewardReserves()/10**dip_token.decimals(), staking.rewardReserves())
        else:
            reward_reserves_warning = 'WARNING reward reserves missing [DIP]{:.2f} to payout full reward balance'.format(
                (staking.rewardBalance() - staking.rewardReserves())/10**dip_token.decimals())

            setup['staking']['reward_reserves'] = (staking.rewardReserves()/10**dip_token.decimals(), staking.rewardReserves(), reward_reserves_warning)
    else:
        setup['staking']['setup'] = 'WARNING staking contract not linked, not ready to use'

    return (
        setup,
        product,
        riskpool,
        registry,
        staking,
        dip_token,
        token,
        protected_token,
        instance_service
    )


def _getStakeBalance(staking, dip):
    stake_balance = 0

    try: 
        stake_balance = staking.stakeBalance()
    except Exception as e:
        return ('n/a', 0)

    return (stake_balance/10**dip.decimals(), stake_balance)


def _get_application_state(state):
    return (APPLICATION_STATE[state], state)


def _get_policy_state(state):
    return (POLICY_STATE[state], state)


def _get_bundle_state(state):
    return (BUNDLE_STATE[state], state)

def _getComponentState(component_id, instance_service):
    state = instance_service.getComponentState(component_id)
    return (COMPONENT_STATE[state], state)


def _get_version(versionable):
    (major, minor, patch) = versionable.versionParts()
    return('v{}.{}.{}'.format(major, minor, patch), versionable.version())


def _get_fee_spec(component_id, treasury, instance_service):
    spec = treasury.getFeeSpecification(component_id).dict()

    if spec['componentId'] == 0:
        return 'WARNING no fee spec available, not ready to use'

    return (
        spec['fractionalFee']/instance_service.getFeeFractionFullUnit(), spec['fixedFee'])


def get_riskpool(product, instance_service):
    riskpool_id = product.getRiskpoolId()
    riskpool_address = instance_service.getComponent(riskpool_id)
    return contract_from_address(RainRiskpool, riskpool_address)


def get_instance(product):
    gif = get_package('gif-contracts')

    registry_address = product.getRegistry()
    registry = contract_from_address(gif.RegistryController, registry_address)

    instance_service_address = registry.getContract(s2b('InstanceService'))
    instance_service = contract_from_address(gif.InstanceService, instance_service_address)
    instance_operator = instance_service.getInstanceOperator()

    treasury_address = registry.getContract(s2b('Treasury'))
    treasury = contract_from_address(gif.TreasuryModule, treasury_address)

    return (instance_service, instance_operator, treasury, registry)


def new_risk(d):    
    return create_risk(d[PRODUCT],d[INSURER]) 


def new_bundle(d) -> int:
    return create_bundle(
        d[INSTANCE],
        d[INSTANCE_OPERATOR],
        d[INVESTOR],
        d[RISKPOOL]
    ) 


def new_policy(
    d,
    bundleId,
    riskId,
    sum_insured_amount = SUM_INSURED_AMOUNT,
    premium_amount = PREMIUM_AMOUNT,
):
    processId = apply_for_policy_with_bundle(
        d[INSTANCE],
        d[INSTANCE_OPERATOR],
        d[CUSTOMER1],
        d[PRODUCT],
        bundleId,
        riskId,
        sumInsured=sum_insured_amount,
        premium=premium_amount
    )

    return processId


def inspect_fee(
    d,
    netPremium,
):
    instanceService = d[INSTANCE_SERVICE]
    product = d[PRODUCT]

    feeSpec = product.getFeeSpecification()
    fixed = feeSpec[1]
    fraction = feeSpec[2]
    fullUnit = product.getFeeFractionFullUnit()

    (feeAmount, totalAmount) = product.calculateFee(netPremium)

    return {
        'fixedFee': fixed,
        'fractionalFee': int(netPremium * fraction / fullUnit),
        'feeFraction': fraction/fullUnit,
        'netPremium': netPremium,
        'fees': feeAmount,
        'totalPremium': totalAmount
    }


#TODO: rever
# def best_quote(
#     d,
#     protectedBalance,
#     durationDays
# ):
#     token = contract_from_address(Usdc, d[ERC20_TOKEN])

#     return best_quote(
#         d[INSTANCE_SERVICE],
#         d[PRODUCT],
#         d[RISKPOOL],
#         token,
#         protectedBalance,
#         durationDays)


#TODO: rever
# def best_quote(
#     instanceService,
#     product,
#     riskpool,
#     token,
#     protectedBalance,
#     durationDays
# ):
#     return best_premium(
#         instanceService,
#         riskpool,
#         product,
#         protectedBalance * 10 ** token.decimals(),
#         durationDays)


#TODO: rever
# def best_premium(
#     instanceService,
#     riskpool,
#     product,
#     protectedBalance,
#     durationDays
# ):
#     sumInsured = riskpool.calculateSumInsured(protectedBalance)
#     bundleData = get_bundle_data(instanceService, riskpool)
#     aprMin = 100.0
#     bundleId = None

#     for idx in range(len(bundleData)):
#         bundle = bundleData[idx]

#         if sumInsured < bundle['minSumInsured']:
#             continue

#         if sumInsured > bundle['maxSumInsured']:
#             continue

#         if durationDays < bundle['minDuration']:
#             continue

#         if durationDays > bundle['maxDuration']:
#             continue

#         if aprMin < bundle['apr']:
#             continue

#         bundleId = bundle['bundleId']
#         aprMin = bundle['apr']

#     if not bundleId:
#         return {'bundleId':None, 'apr':None, 'premium':sumInsured, 'netPremium':sumInsured, 'comment':'no matching bundle'}

#     duration = durationDays * 24 * 3600
#     netPremium = product.calculateNetPremium(sumInsured, duration, bundleId)
#     premium = product.calculatePremium(netPremium)

#     return {'bundleId':bundleId, 'apr':aprMin, 'premium':premium, 'netPremium':netPremium, 'comment':'recommended bundle'}


#TODO: rever all_in_one x all_in_1_base
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
        new_bundle,
        new_risk,
        new_policy,
        stakeholders_accounts,
        registry_address,
        usdc_address,
        deploy_all=deploy_all,
        publish_source=publish_source,
        chainLinkOracleAddress=chainLinkOracleAddress,
        chainLinkJobId=chainLinkJobId,
        chainLinkPaymentAmount=chainLinkPaymentAmount)


#TODO: rever
def verify_deploy(
    d, 
    token,
    product
):
    verify_deploy_base(
        from_component,
        d, 
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