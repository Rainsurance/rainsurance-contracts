import pytest
import web3

from typing import Dict

from brownie import (
    interface,
    Wei,
    Contract, 
    Usdc,
    RainProduct,
    RainOracle,
    RainRiskpool
)

from brownie.network import accounts
from brownie.network.account import Account
from brownie.network.state import Chain

from scripts.const import (
    ACCOUNTS_MNEMONIC,
    INSTANCE_OPERATOR,
    INSTANCE_WALLET,
    ORACLE_PROVIDER,
    CHAINLINK_NODE_OPERATOR,
    RISKPOOL_KEEPER,
    RISKPOOL_WALLET,
    INVESTOR,
    PRODUCT_OWNER,
    INSURER,
    CUSTOMER1,
    CUSTOMER2,
    REGISTRY_OWNER,
    STAKER,
    OUTSIDER,
    GIF_ACTOR
)

from scripts.instance import (
    GifRegistry,
    GifInstance,
)

from scripts.product import (
    GifRiskpool,
    GifOracle,
    GifProduct,
    GifProductComplete,
)

from scripts.util import (
    get_account,
    get_package,
)

PRODUCT_BASE_NAME = 'RAIN'

CONTRACT_CLASS_TOKEN = Usdc
CONTRACT_CLASS_PRODUCT = RainProduct
CONTRACT_CLASS_ORACLE = RainOracle
CONTRACT_CLASS_RISKPOOL = RainRiskpool

INITIAL_ACCOUNT_FUNDING = '1 ether'

# -- comments below may be used /w 'brownie console'
# mnemonic = 'candy maple cake sugar pudding cream honey rich smooth crumble sweet treat'
# owner = accounts.from_mnemonic(mnemonic, count=1, offset=0)
def get_filled_account(
    accounts,
    account_no,
    funding=INITIAL_ACCOUNT_FUNDING
) -> Account:
    owner = get_account(ACCOUNTS_MNEMONIC, account_no)
    accounts[account_no].transfer(owner, funding)
    return owner

# fixtures with `yield` execute the code that is placed before the `yield` as setup code
# and code after `yield` is teardown code. 
# See https://docs.pytest.org/en/7.1.x/how-to/fixtures.html#yield-fixtures-recommended
@pytest.fixture(autouse=True)
def run_around_tests():
    try:
        yield
        # after each test has finished, execute one trx and wait for it to finish. 
        # this is to ensure that the last transaction of the test is finished correctly. 
    finally:
        accounts[8].transfer(accounts[9], 1)
        # dummy_account = get_account(ACCOUNTS_MNEMONIC, 999)
        # execute_simple_incrementer_trx(dummy_account)

#=== access to gif-contracts contract classes  =======================#

@pytest.fixture(scope="module")
def gifi(): return get_package('gif-interface')

@pytest.fixture(scope="module")
def gif(): return get_package('gif-contracts')

#=== actor account fixtures  ===========================================#

@pytest.fixture(scope="module")
def instanceOperator(accounts) -> Account:
    return get_filled_account(accounts, GIF_ACTOR[INSTANCE_OPERATOR])

@pytest.fixture(scope="module")
def instanceWallet(accounts) -> Account:
    return get_filled_account(accounts, GIF_ACTOR[INSTANCE_WALLET])

@pytest.fixture(scope="module")
def riskpoolKeeper(accounts) -> Account:
    return get_filled_account(accounts, GIF_ACTOR[RISKPOOL_KEEPER])

@pytest.fixture(scope="module")
def riskpoolWallet(accounts) -> Account:
    return get_filled_account(accounts, GIF_ACTOR[RISKPOOL_WALLET])

@pytest.fixture(scope="module")
def investor(accounts) -> Account:
    return get_filled_account(accounts, GIF_ACTOR[INVESTOR])

@pytest.fixture(scope="module")
def productOwner(accounts) -> Account:
    return get_filled_account(accounts, GIF_ACTOR[PRODUCT_OWNER])

@pytest.fixture(scope="module")
def insurer(accounts) -> Account:
    return get_filled_account(accounts, GIF_ACTOR[INSURER])

@pytest.fixture(scope="module")
def oracleProvider(accounts) -> Account:
    return get_filled_account(accounts, GIF_ACTOR[ORACLE_PROVIDER])

@pytest.fixture(scope="module")
def chainlinkNodeOperator(accounts) -> Account:
    return get_filled_account(accounts, GIF_ACTOR[CHAINLINK_NODE_OPERATOR])

@pytest.fixture(scope="module")
def customer(accounts) -> Account:
    return get_filled_account(accounts, GIF_ACTOR[CUSTOMER1])

@pytest.fixture(scope="module")
def customer2(accounts) -> Account:
    return get_filled_account(accounts, GIF_ACTOR[CUSTOMER2])

@pytest.fixture(scope="module")
def theOutsider(accounts) -> Account:
    return get_filled_account(accounts, GIF_ACTOR[OUTSIDER])

#=== gif instance fixtures ====================================================#

@pytest.fixture(scope="module")
def registry(instanceOperator) -> GifRegistry: return GifRegistry(instanceOperator, None)

@pytest.fixture(scope="module")
def instance(instanceOperator, instanceWallet) -> GifInstance: return GifInstance(instanceOperator, instanceWallet)

@pytest.fixture(scope="module")
def instanceService(instance): return instance.getInstanceService()

#=== stable coin fixtures ============================================#

@pytest.fixture(scope="module")
def token(instanceOperator) -> CONTRACT_CLASS_TOKEN: return CONTRACT_CLASS_TOKEN.deploy({'from': instanceOperator})

#=== rain contracts fixtures ========================================#

@pytest.fixture(scope="module")
def gifProductDeploy(
    instance: GifInstance, 
    productOwner: Account, 
    insurer: Account,
    investor: Account, 
    token: CONTRACT_CLASS_TOKEN,
    oracleProvider: Account, 
    chainlinkNodeOperator: Account,
    riskpoolKeeper: Account, 
    riskpoolWallet: Account
) -> GifProductComplete:
    return GifProductComplete(
        instance, 
        CONTRACT_CLASS_PRODUCT,
        CONTRACT_CLASS_ORACLE,
        CONTRACT_CLASS_RISKPOOL,
        productOwner,
        insurer,
        oracleProvider,
        chainlinkNodeOperator,
        riskpoolKeeper, 
        riskpoolWallet,
        investor,
        token,
        name=PRODUCT_BASE_NAME,
        publish_source=False)

@pytest.fixture(scope="module")
def gifProduct(gifProductDeploy) -> GifProduct: return gifProductDeploy.getProduct()

@pytest.fixture(scope="module")
def product(gifProduct) -> CONTRACT_CLASS_PRODUCT: return gifProduct.getContract()

@pytest.fixture(scope="module")
def oracle(gifProduct) -> CONTRACT_CLASS_ORACLE: return gifProduct.getOracle().getContract()

@pytest.fixture(scope="module")
def riskpool(gifProduct) -> CONTRACT_CLASS_RISKPOOL: return gifProduct.getRiskpool().getContract()
