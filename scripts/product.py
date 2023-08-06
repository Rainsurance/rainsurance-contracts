import time

from brownie.network.account import Account

from brownie import (
    interface,
    Wei,
    Contract, 
    ChainlinkOperator, 
    ChainlinkToken,
    FunctionsOracle,
    RainRiskpool
)
from scripts.util import (
    s2b,
    s2b32,
    contract_from_address,
    wait_for_confirmations,
)

from scripts.instance import GifInstance

# product contract names
NAME_DEFAULT = 'Protection'

# fees

# 10% fee on premium paid
PREMIUM_FEE_FIXED_DEFAULT = 0
PREMIUM_FEE_FRACTIONAL_DEFAULT = 0.1

# 5% fee for staked capital
CAPITAL_FEE_FIXED_DEFAULT = 0
CAPITAL_FEE_FRACTIONAL_DEFAULT = 0.05

# goal: protect balance up to 10'000'000 usdc
# with sum insured percentage of 20% -> 2'000'000 (2 * 10**6)
# with usdc.decimals() == 6 -> 2 * 10**(6 + 6) == 2 * 10**12
SUM_OF_SUM_INSURED_CAP = 2 * 10**12

MAX_ACTIVE_BUNDLES = 10

class GifOracle(object):

    def __init__(self, 
        instance: GifInstance, 
        oracleContractClass,
        oracleProvider: Account,
        chainlinkNodeOperator: Account,
        name,
        publish_source,
        chainLinkTokenAddress=None,
        chainLinkOracleAddress=None,
        chainLinkJobId=None,
        chainLinkPaymentAmount=None,
        oracleAddress=None
    ):
        instanceService = instance.getInstanceService()
        instanceOperatorService = instance.getInstanceOperatorService()
        componentOwnerService = instance.getComponentOwnerService()

        print('------ setting up oracle ------')

        providerRole = instanceService.getOracleProviderRole()
        print('1) grant oracle provider role {} to oracle provider {}'.format(
            providerRole, oracleProvider))

        instanceOperatorService.grantRole(
            providerRole, 
            oracleProvider, 
            {'from': instance.getOwner()})
        
        if chainLinkTokenAddress is None:
            clTokenOwner = oracleProvider
            clTokenSupply = 10**20
            print('2) deploy chainlink (mock) token with token owner (=oracle provider) {} by oracle provider {}'.format(
                clTokenOwner, oracleProvider))
            self.chainlinkToken = ChainlinkToken.deploy(
                clTokenOwner,
                clTokenSupply,
                {'from': oracleProvider},
                publish_source=publish_source)
            chainLinkTokenAddress = self.chainlinkToken.address
        else:
            print('2) reusing chainlink token with address {}'.format(
            chainLinkTokenAddress))
        
        # AnyAPI Oracle/Operator (new)
        if oracleAddress is None and chainLinkOracleAddress is None:
            print('3) deploy chainlink (mock) operator by oracle provider {}'.format(
                oracleProvider))
            self.chainlinkOperator = ChainlinkOperator.deploy(
                {'from': oracleProvider},
                publish_source=publish_source)
            chainLinkOracleAddress = self.chainlinkOperator.address

            print('4) set node operator list [{}] as authorized sender by oracle provider {}'.format(
                chainlinkNodeOperator, oracleProvider))
            self.chainlinkOperator.setAuthorizedSenders([chainlinkNodeOperator])

        # AnyAPI Oracle/Operator (reuse)
        elif oracleAddress is None:
            
            print('3) reusing operator with address {}'.format(
                chainLinkOracleAddress))
            self.chainlinkOperator = contract_from_address(
                ChainlinkOperator, 
                chainLinkOracleAddress)
            
        # Functions Oracle/Operator (reuse)
        else:
            print('3) reusing chainlink functions operator with address {}'.format(
                oracleAddress))
            self.chainlinkOperator = contract_from_address(
                FunctionsOracle, 
                chainLinkOracleAddress)
            

        if chainLinkJobId is None:
            chainLinkJobId = '1'

        if chainLinkPaymentAmount is None:
            chainLinkPaymentAmount = 0

        # AnyAPI Consumer/Client (new)
        if oracleAddress is None:
            print('5) deploy oracle by oracle provider {}'.format(
                oracleProvider))
            
            self.oracle = oracleContractClass.deploy(
                s2b32(name),
                instance.getRegistry(),
                chainLinkTokenAddress,
                chainLinkOracleAddress,
                s2b32(chainLinkJobId),
                chainLinkPaymentAmount,
                {'from': oracleProvider},
                publish_source=publish_source)
        
        # Functions Consumer/Client (reuse)
        else:
            print('5) reusing chainlink functions oracle with address {} and class {}'.format(
            oracleAddress, oracleContractClass._name))
            self.oracle = contract_from_address(oracleContractClass, oracleAddress)
        
        try:
            print('6) oracle {} proposing to instance by oracle provider {}'.format(
                self.oracle, oracleProvider))

            componentOwnerService.propose(
                self.oracle,
                {'from': oracleProvider})

            print('7) approval of oracle id {} by instance operator {}'.format(
                self.oracle.getId(), instance.getOwner()))

            instanceOperatorService.approve(
                self.oracle.getId(),
                {'from': instance.getOwner()})
            
        except Exception as err:
            print(f"Unexpected {err=}")
    
    def getId(self) -> int:
        return self.oracle.getId()
    
    def getClOperator(self) -> ChainlinkOperator:
        return self.chainlinkOperator
    
    def getContract(self):
        return self.oracle


class GifRiskpool(object):

    def __init__(self, 
        instance: GifInstance, 
        riskpoolContractClass,
        riskpoolKeeper: Account, 
        name, 
        erc20Token: Account,
        riskpoolWallet: Account,
        investor: Account,
        collateralization:int,
        publish_source,
        maxActiveBundles=MAX_ACTIVE_BUNDLES,
        fixedFee=CAPITAL_FEE_FIXED_DEFAULT,
        fractionalFee=CAPITAL_FEE_FRACTIONAL_DEFAULT,
        sumOfSumInsuredCap=SUM_OF_SUM_INSURED_CAP,
        sumInsuredPercentage=100,
        riskpool_address=None,
    ):
        instanceService = instance.getInstanceService()
        instanceOperatorService = instance.getInstanceOperatorService()
        componentOwnerService = instance.getComponentOwnerService()

        print('------ setting up riskpool ------')
        self.riskpool = None

        if riskpool_address:
            print('1) obtain riskpool from address {}'.format(riskpool_address))
            self.riskpool = contract_from_address(RainRiskpool, riskpool_address)

            return

        riskpoolKeeperRole = instanceService.getRiskpoolKeeperRole()

        if instanceService.hasRole(riskpoolKeeperRole, riskpoolKeeper):
            print('1) riskpool keeper {} already has role {}'.format(
                riskpoolKeeper, riskpoolKeeperRole))
        else:
            print('1) grant riskpool keeper role {} to riskpool keeper {}'.format(
                riskpoolKeeperRole, riskpoolKeeper))

            instanceOperatorService.grantRole(
                riskpoolKeeperRole, 
                riskpoolKeeper, 
                {'from': instance.getOwner()})

        print('2) deploy riskpool {} by riskpool keeper {}'.format(
            name, riskpoolKeeper))

        self.riskpool = riskpoolContractClass.deploy(
            s2b(name),
            sumOfSumInsuredCap,
            sumInsuredPercentage,
            erc20Token,
            riskpoolWallet,
            instance.getRegistry(),
            {'from': riskpoolKeeper},
            publish_source=publish_source)
        
        print('3) riskpool {} proposing to instance by riskpool keeper {}'.format(
            self.riskpool, riskpoolKeeper))
        
        tx = componentOwnerService.propose(
            self.riskpool,
            {'from': riskpoolKeeper})
        
        wait_for_confirmations(tx)

        print('4) approval of riskpool id {} by instance operator {}'.format(
            self.riskpool.getId(), instance.getOwner()))
        
        tx = instanceOperatorService.approve(
            self.riskpool.getId(),
            {'from': instance.getOwner()})

        wait_for_confirmations(tx)

        print('5) set max number of bundles to {} by riskpool keeper {}'.format(
            MAX_ACTIVE_BUNDLES, riskpoolKeeper))

        self.riskpool.setMaximumNumberOfActiveBundles(
            maxActiveBundles,
            {'from': riskpoolKeeper})

        # TODO set these to desired initial config
        sumOfSumInsuredCap = self.riskpool.getSumOfSumInsuredCap()
        bundleCap = int(sumOfSumInsuredCap / maxActiveBundles)

        print('6) set capital caps [{}], sum of sum insured: {:.2f}, bundle cap: {:.2f}'.format(
            erc20Token.symbol(),
            sumOfSumInsuredCap/10**erc20Token.decimals(),
            bundleCap/10**erc20Token.decimals()))

        self.riskpool.setCapitalCaps(
            sumOfSumInsuredCap,
            bundleCap,
            {'from': riskpoolKeeper})

        print('7) riskpool wallet {} set for riskpool id {} by instance operator {}'.format(
            riskpoolWallet, self.riskpool.getId(), instance.getOwner()))
        
        instanceOperatorService.setRiskpoolWallet(
            self.riskpool.getId(),
            riskpoolWallet,
            {'from': instance.getOwner()})

        print('8) creating capital fee spec (fixed: {}, fractional: {}) for riskpool id {} by instance operator {}'.format(
            fixedFee, fractionalFee, self.riskpool.getId(), instance.getOwner()))
        
        feeSpec = instanceOperatorService.createFeeSpecification(
            self.riskpool.getId(),
            fixedFee,
            fractionalFee * instanceService.getFeeFractionFullUnit(),
            b'',
            {'from': instance.getOwner()}) 

        print('9) setting capital fee spec by instance operator {}'.format(
            instance.getOwner()))
        
        instanceOperatorService.setCapitalFees(
            feeSpec,
            {'from': instance.getOwner()}) 
    
    def getId(self) -> int:
        return self.riskpool.getId()
    
    def getContract(self):
        return self.riskpool


class GifProduct(object):

    def __init__(self,
        instance: GifInstance,
        productContractClass,
        productOwner: Account,
        insurer: Account,
        name, 
        erc20Token: Account,
        oracle: GifOracle,
        riskpool: GifRiskpool,
        publish_source,
        fixedFee=PREMIUM_FEE_FIXED_DEFAULT,
        fractionalFee=PREMIUM_FEE_FRACTIONAL_DEFAULT,
    ):
        self.oracle = oracle
        self.riskpool = riskpool
        self.token = erc20Token

        instanceService = instance.getInstanceService()
        instanceOperatorService = instance.getInstanceOperatorService()
        componentOwnerService = instance.getComponentOwnerService()
        registry = instance.getRegistry()

        print('------ setting up product ------')

        productOwnerRole = instanceService.getProductOwnerRole()
        print('1) grant product owner role {} to product owner {}'.format(
            productOwnerRole, productOwner))

        instanceOperatorService.grantRole(
            productOwnerRole,
            productOwner, 
            {'from': instance.getOwner()})

        print('2) deploy product {} by product owner {}'.format(
            name, productOwner))
        
        self.product = productContractClass.deploy(
            s2b32(name),
            registry,
            erc20Token.address,
            oracle.getId(),
            riskpool.getId(),
            insurer,
            {'from': productOwner},
            publish_source=publish_source)

        print('3) product {} proposing to instance by product owner {}'.format(
            self.product, productOwner))
        
        componentOwnerService.propose(
            self.product,
            {'from': productOwner})

        print('4) approval of product id {} by instance operator {}'.format(
            self.product.getId(), instance.getOwner()))
        
        instanceOperatorService.approve(
            self.product.getId(),
            {'from': instance.getOwner()})

        print('5) setting erc20 product token {} for product id {} by instance operator {}'.format(
            erc20Token, self.product.getId(), instance.getOwner()))

        instanceOperatorService.setProductToken(
            self.product.getId(), 
            erc20Token,
            {'from': instance.getOwner()}) 

        print('6) creating premium fee spec (fixed: {}, fractional: {}) for product id {} by instance operator {}'.format(
            fixedFee, fractionalFee, self.product.getId(), instance.getOwner()))
        
        feeSpec = instanceOperatorService.createFeeSpecification(
            self.product.getId(),
            fixedFee,
            fractionalFee * instanceService.getFeeFractionFullUnit(),
            b'',
            {'from': instance.getOwner()}) 

        print('7) setting premium fee spec by instance operator {}'.format(
            instance.getOwner()))

        instanceOperatorService.setPremiumFees(
            feeSpec,
            {'from': instance.getOwner()}) 

    
    def getId(self) -> int:
        return self.product.getId()

    def getToken(self):
        return self.token

    def getOracle(self) -> GifOracle:
        return self.oracle

    def getRiskpool(self) -> GifRiskpool:
        return self.riskpool
    
    def getContract(self):
        return self.product

    def getPolicy(self, policyId: str):
        return self.policy.getPolicy(policyId)

class GifProductComplete(object):

    def __init__(self,
        instance: GifInstance,
        productContractClass,
        oracleContractClass,
        riskpoolContractClass,
        productOwner: Account,
        insurer: Account,
        oracleProvider: Account,
        riskpoolKeeper: Account,
        riskpoolWallet: Account,
        investor: Account,
        erc20Token: Account,
        chainlinkNodeOperator: Account,
        chainLinkTokenAddress=None,
        chainLinkOracleAddress=None,
        chainLinkJobId=None,
        chainLinkPaymentAmount=None,
        oracleAddress=None,
        name=NAME_DEFAULT,
        publish_source=False,
    ):
        instanceService = instance.getInstanceService()
        instanceOperatorService = instance.getInstanceOperatorService()
        componentOwnerService = instance.getComponentOwnerService()
        registry = instance.getRegistry()

        self.token = erc20Token
        baseName = '{}_{}'.format(name, str(int(time.time()))) # FIXME

        self.oracle = GifOracle(
                instance,
                oracleContractClass,
                oracleProvider, 
                # TODO analyze how to set a separate chainlink operator node account
                chainlinkNodeOperator,
                '{}_Oracle'.format(baseName),
                publish_source,
                chainLinkTokenAddress,
                chainLinkOracleAddress,
                chainLinkJobId,
                chainLinkPaymentAmount,
                oracleAddress)

        self.riskpool = GifRiskpool(
            instance, 
            riskpoolContractClass,
            riskpoolKeeper, 
            '{}_Riskpool'.format(baseName),
            erc20Token, 
            riskpoolWallet, 
            investor, 
            instanceService.getFullCollateralizationLevel(),
            publish_source)

        self.product = GifProduct(
            instance,
            productContractClass,
            productOwner, 
            insurer, 
            '{}_Product'.format(baseName),
            erc20Token, 
            self.oracle,
            self.riskpool,
            publish_source)

    def getToken(self):
        return self.token

    def getOracle(self) -> GifOracle:
        return self.oracle

    def getRiskpool(self) -> GifRiskpool:
        return self.riskpool

    def getProduct(self) -> GifProduct:
        return self.product