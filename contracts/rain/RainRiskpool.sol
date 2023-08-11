// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";

import "@etherisc/gif-interface/contracts/components/BasicRiskpool.sol";
import "@etherisc/gif-interface/contracts/modules/IBundle.sol";
import "@etherisc/gif-interface/contracts/modules/IPolicy.sol";
import "@etherisc/gif-interface/contracts/tokens/IBundleToken.sol";

import "./../gif/BasicRiskpool2.sol";
import "./../registry/IChainRegistryFacade.sol";
import "./../staking/IStakingFacade.sol";

contract RainRiskpool is 
    BasicRiskpool2
{

    struct BundleInfo {
        uint256 bundleId;
        string name;
        IBundle.BundleState state;
        uint256 tokenId;
        address owner;
        uint256 lifetime;
        uint256 minSumInsured;
        uint256 maxSumInsured;
        uint256 minDuration;
        uint256 maxDuration;
        uint256 capitalSupportedByStaking;
        uint256 capital;
        uint256 lockedCapital;
        uint256 balance;
        uint256 createdAt;
        string place;
    }

    event LogRiskpoolCapitalSet(uint256 poolCapitalNew, uint256 poolCapitalOld);
    event LogBundleCapitalSet(uint256 bundleCapitalNew, uint256 bundleCapitalOld);

    event LogAllowAllAccountsSet(bool allowAllAccounts);
    event LogAllowAccountSet(address account, bool allowAccount);

    event LogBundleExpired(uint256 bundleId, uint256 createdAt, uint256 lifetime);
    event LogBundleMismatch(uint256 bundleId, uint256 bundleIdRequested);
    event LogBundleMatchesApplication(uint256 bundleId, uint256 errorId);

    bytes32 public constant EMPTY_STRING_HASH = keccak256(abi.encodePacked(""));
    bytes32 public constant PLACE_WILDCARD_HASH = keccak256(abi.encodePacked("*"));

    uint256 public constant MIN_BUNDLE_LIFETIME = 30 * 24 * 3600; // 30 days
    uint256 public constant MAX_BUNDLE_LIFETIME = 365 * 24 * 3600; // 365 days
    uint256 public constant MIN_POLICY_DURATION = 1 * 24 * 3600; // 1 day
    uint256 public constant MAX_POLICY_DURATION = 15 * 24 * 3600; // 15 days
    uint256 public constant MIN_POLICY_COVERAGE = 100 * 10 ** 6; // as usdt amount ($100)
    uint256 public constant MAX_POLICY_COVERAGE = 5000 * 10 ** 6; // as usdt amount ($5.000)

    mapping(string /* bundle name */ => uint256 /* bundle id */) private _bundleIdForBundleName;

    mapping(bytes32 /* bundle placeId */ => uint256 [] /* bundle id */) private _bundleIdForBundlePlace; // hold list of applications/policies Ids for address

    IChainRegistryFacade private _chainRegistry;
    IStakingFacade private _staking;

    // managed token
    IERC20Metadata private _token;

    // sum insured % of protected amount
    uint256 private _sumInsuredPercentage;
    
    // capital caps
    uint256 private _riskpoolCapitalCap;
    uint256 private _bundleCapitalCap;

    // bundle creation whitelisting
    mapping(address /* potential bundle owner */ => bool /* is allowed to create bundle*/) _allowedAccount;
    bool private _allowAllAccounts;

    modifier onlyAllowedAccount {
        require(isAllowed(_msgSender()), "ERROR:RAINRP-001:ACCOUNT_NOT_ALLOWED_FOR_BUNDLE_CREATION");
        _;
    }

    constructor(
        bytes32 name,
        uint256 sumOfSumInsuredCap,
        uint256 sumInsuredPercentage,
        address erc20Token,
        address wallet,
        address registry
    )
        BasicRiskpool2(name, getFullCollateralizationLevel(), sumOfSumInsuredCap, erc20Token, wallet, registry)
    {
        require(
            sumInsuredPercentage > 0 && sumInsuredPercentage <= 100,
            "ERROR:RAINRP-005:SUM_INSURED_PERCENTAGE_INVALID");

        _sumInsuredPercentage = sumInsuredPercentage;

        _token = IERC20Metadata(erc20Token);

        _riskpoolCapitalCap = sumOfSumInsuredCap;
        _bundleCapitalCap = _riskpoolCapitalCap / 10;
        _allowAllAccounts = true;

        _staking = IStakingFacade(address(0));
        _chainRegistry = IChainRegistryFacade(address(0));
    }

    function setCapitalCaps(
        uint256 poolCapitalCap,
        uint256 bundleCapitalCap
    )
        public
        onlyOwner
    {
        require(poolCapitalCap <= getSumOfSumInsuredCap(), "ERROR:RAINRP-011:POOL_CAPITAL_CAP_TOO_LARGE");
        require(bundleCapitalCap < poolCapitalCap, "ERROR:RAINRP-012:BUNDLE_CAPITAL_CAP_TOO_LARGE");
        require(bundleCapitalCap > 0, "ERROR:RAINRP-013:BUNDLE_CAPITAL_CAP_ZERO");

        uint256 poolCapOld = _riskpoolCapitalCap;
        uint256 bundleCapOld = _bundleCapitalCap;

        _riskpoolCapitalCap = poolCapitalCap;
        _bundleCapitalCap = bundleCapitalCap;

        emit LogRiskpoolCapitalSet(_riskpoolCapitalCap, poolCapOld);
        emit LogBundleCapitalSet(_bundleCapitalCap, bundleCapOld);
    }

    function setAllowAllAccounts(bool allowAllAccounts)
        external
        onlyOwner
    {
        _allowAllAccounts = allowAllAccounts;
        emit LogAllowAllAccountsSet(_allowAllAccounts);
    }

    function isAllowAllAccountsEnabled()
        external
        view
        returns(bool allowAllAccounts)
    {
        return _allowAllAccounts;
    }

    function setAllowAccount(address account, bool allowAccount)
        external
        onlyOwner
    {
        _allowedAccount[account] = allowAccount;
        emit LogAllowAccountSet(account, _allowedAccount[account]);
    }

    function isAllowed(address account)
        public
        view
        returns(bool allowed)
    {
        return _allowAllAccounts || _allowedAccount[account];
    }

    function setStakingAddress(address stakingAddress)
        external
        onlyOwner
    {
        _staking = IStakingFacade(stakingAddress);
        require(_staking.implementsIStaking(), "ERROR:RAINRP-016:STAKING_NOT_ISTAKING");

        _chainRegistry = IChainRegistryFacade(_staking.getRegistry());
    }

    function getStaking()
        external
        view
        returns(IStakingFacade)
    {
        return _staking;
    }


    function getChainRegistry()
        external
        view
        returns(IChainRegistryFacade)
    {
        return _chainRegistry;
    }

    function createBundle(
        string memory name,
        uint256 lifetime,
        uint256 policyMinProtectedBalance,
        uint256 policyMaxProtectedBalance,
        uint256 policyMinDuration,
        uint256 policyMaxDuration,
        uint256 initialAmount,
        string memory place
    ) 
        public
        onlyAllowedAccount
        returns(uint256 bundleId)
    {
        require(
            _bundleIdForBundleName[name] == 0,
            "ERROR:RAINRP-020:NAME_NOT_UNIQUE");
        require(
            lifetime >= MIN_BUNDLE_LIFETIME
            && lifetime <= MAX_BUNDLE_LIFETIME, 
            "ERROR:RAINRP-021:LIFETIME_INVALID");

        // get sum insured bounds from protected balance bounds
        uint256 policyMinSumInsured = calculateSumInsured(policyMinProtectedBalance);
        uint256 policyMaxSumInsured = calculateSumInsured(policyMaxProtectedBalance);
        
        require(
            policyMaxProtectedBalance >= policyMinProtectedBalance
            && policyMaxProtectedBalance <= MAX_POLICY_COVERAGE
            && policyMaxSumInsured <= _bundleCapitalCap,
            "ERROR:RAINRP-022:MAX_PROTECTED_BALANCE_INVALID");
        require(
            policyMinProtectedBalance >= MIN_POLICY_COVERAGE
            && policyMinProtectedBalance <= policyMaxProtectedBalance, 
            "ERROR:RAINRP-023:MIN_PROTECTED_BALANCE_INVALID");
        require(
            policyMaxDuration > 0
            && policyMaxDuration <= MAX_POLICY_DURATION, 
            "ERROR:RAINRP-024:MAX_DURATION_INVALID");
        require(
            policyMinDuration >= MIN_POLICY_DURATION
            && policyMinDuration <= policyMaxDuration, 
            "ERROR:RAINRP-025:MIN_DURATION_INVALID");
        require(
            initialAmount > 0
            && initialAmount <= _bundleCapitalCap, 
            "ERROR:RAINRP-027:RISK_CAPITAL_INVALID");
        require(
            getCapital() + initialAmount <= _riskpoolCapitalCap,
            "ERROR:RAINRP-028:POOL_CAPITAL_CAP_EXCEEDED");
        require(
            keccak256(abi.encodePacked(place)) != EMPTY_STRING_HASH,
            "ERROR:RAINRP-029:PLACE_REQUIRED");

        bytes memory filter = encodeBundleParamsAsFilter(
            name,
            lifetime,
            policyMinSumInsured,
            policyMaxSumInsured,
            policyMinDuration,
            policyMaxDuration,
            place
        );

        bundleId = super.createBundle(filter, initialAmount);

        if(keccak256(abi.encodePacked(name)) != EMPTY_STRING_HASH) {
            _bundleIdForBundleName[name] = bundleId;
        }

        bytes32 bundlePlace = keccak256(abi.encodePacked(place));
        _bundleIdForBundlePlace[bundlePlace].push(bundleId);

        // Register the new bundle with the staking/bundle registry contract. 
        // Staking and registry are set in tandem (the address of the registry is retrieved from staking),
        // so if one is present, its safe to assume the other is too.
        IBundle.Bundle memory bundle = _instanceService.getBundle(bundleId);

        if (address(_chainRegistry) != address(0) && isComponentRegistered(bundle.riskpoolId)) { 
            registerBundleInRegistry(bundle, name, lifetime);
        }
    }

    function getSumInsuredPercentage()
        external
        view
        returns(uint256 sumInsuredPercentage)
    {
        return _sumInsuredPercentage;
    }

    function calculateSumInsured(uint256 protectedBalance)
        public
        view
        returns(uint256 sumInsured)
    {
        return (protectedBalance * _sumInsuredPercentage) / 100;
    }

    function isComponentRegistered(uint256 componentId)
        private
        view
        returns(bool)
    {
        bytes32 instanceId = _instanceService.getInstanceId();
        uint96 componentNftId = _chainRegistry.getComponentNftId(instanceId, componentId);
        return _chainRegistry.exists(componentNftId);
    }

    /**
     * @dev Register the bundle with given id in the bundle registry.
     */    
    function registerBundleInRegistry(
        IBundle.Bundle memory bundle,
        string memory name,
        uint256 lifetime
    )
        private
    {
        bytes32 instanceId = _instanceService.getInstanceId();
        uint256 expiration = bundle.createdAt + lifetime;
        _chainRegistry.registerBundle(
            instanceId,
            bundle.riskpoolId,
            bundle.id,
            name,
            expiration
        );
    }

    function getBundleInfo(uint256 bundleId)
        external
        view
        returns(BundleInfo memory info)
    {
        IBundle.Bundle memory bundle = _instanceService.getBundle(bundleId);
        IBundleToken token = _instanceService.getBundleToken();

        (
            string memory name,
            uint256 lifetime,
            uint256 minSumInsured,
            uint256 maxSumInsured,
            uint256 minDuration,
            uint256 maxDuration,
            string memory place
        ) = decodeBundleParamsFromFilter(bundle.filter);

        address tokenOwner = token.burned(bundle.tokenId) ? address(0) : token.ownerOf(bundle.tokenId);
        uint256 capitalSupportedByStaking = getSupportedCapitalAmount(bundleId);

        info = BundleInfo(
            bundleId,
            name,
            bundle.state,
            bundle.tokenId,
            tokenOwner,
            lifetime,
            minSumInsured,
            maxSumInsured,
            minDuration,
            maxDuration,
            capitalSupportedByStaking,
            bundle.capital,
            bundle.lockedCapital,
            bundle.balance,
            bundle.createdAt,
            place
        );
    }

    function getFilterDataStructure() external override pure returns(string memory) {
        return "(uint256 minSumInsured,uint256 maxSumInsured,uint256 minDuration,uint256 maxDuration,string place)";
    }

    function encodeBundleParamsAsFilter(
        string memory name,
        uint256 lifetime,
        uint256 minSumInsured,
        uint256 maxSumInsured,
        uint256 minDuration,
        uint256 maxDuration,
        string memory place
    )
        public pure
        returns (bytes memory filter)
    {
        filter = abi.encode(
            name,
            lifetime,
            minSumInsured,
            maxSumInsured,
            minDuration,
            maxDuration,
            place
        );
    }

    function decodeBundleParamsFromFilter(
        bytes memory filter
    )
        public pure
        returns (
            string memory name,
            uint256 lifetime,
            uint256 minSumInsured,
            uint256 maxSumInsured,
            uint256 minDuration,
            uint256 maxDuration,
            string memory place
        )
    {
        (
            name,
            lifetime,
            minSumInsured,
            maxSumInsured,
            minDuration,
            maxDuration,
            place
        ) = abi.decode(filter, (string, uint256, uint256, uint256, uint256, uint256, string));
    }

    //TODO: rever onde essa função é chamada pois troquei a assinatura
    function encodeApplicationParameterAsData(
        address wallet,
        uint256 sumInsured,
        uint256 duration,
        uint256 bundleId,
        uint256 premium,
        string memory place,
        bytes32 riskId
    )
        public pure
        returns (bytes memory data)
    {
        data = abi.encode(
            wallet,
            sumInsured,
            duration,
            bundleId,
            premium,
            place,
            riskId
        );
    }

    function decodeApplicationParameterFromData(
        bytes memory data
    )
        public pure
        returns (
            address wallet,
            uint256 sumInsured,
            uint256 duration,
            uint256 bundleId,
            uint256 premium,
            string memory place,
            bytes32 riskId
        )
    {
        (
            wallet,
            sumInsured,
            duration,
            bundleId,
            premium,
            place,
            riskId
        ) = abi.decode(data, (address, uint256, uint256, uint256, uint256, string, bytes32));
    }

    function getBundleFilter(uint256 bundleId) public view returns (bytes memory filter) {
        IBundle.Bundle memory bundle = _instanceService.getBundle(bundleId);
        filter = bundle.filter;
    }

    // default implementation adds new bundle at the end of the active list
    function isHigherPriorityBundle(uint256 firstBundleId, uint256 secondBundleId) 
        public override 
        view 
        returns (bool firstBundleIsHigherPriority) 
    {
        firstBundleIsHigherPriority = true;
    }

    function bundleMatchesApplication(
        IBundle.Bundle memory bundle, 
        IPolicy.Application memory application
    ) 
        public view override
        returns(bool isMatching) 
    {}

     function bundleMatchesApplication2(
        IBundle.Bundle memory bundle, 
        IPolicy.Application memory application
    ) 
        public override
        returns(bool isMatching) 
    {
        (
            , // name not needed
            uint256 lifetime,
            uint256 minSumInsured,
            uint256 maxSumInsured,
            uint256 minDuration,
            uint256 maxDuration,
            string memory place
        ) = decodeBundleParamsFromFilter(bundle.filter);

        // enforce max bundle lifetime
        if(block.timestamp > bundle.createdAt + lifetime) {
            // TODO this expired bundle bundle should be removed from active bundles
            // ideally this is done in the core, at least should be done
            // in basicriskpool template
            // may not be done here:
            // - lockBundle does not work as riskpool is not owner of bundle
            // - remove from active list would modify list that is iterateed over right now...

            emit LogBundleExpired(bundle.id, bundle.createdAt, lifetime);
            return false;
        }

        // detailed match check
        return detailedBundleApplicationMatch(
            bundle.id,
            minSumInsured,
            maxSumInsured,
            minDuration,
            maxDuration,
            place,
            application
        );
    }

    function detailedBundleApplicationMatch(
        uint256 bundleId,
        uint256 minSumInsured,
        uint256 maxSumInsured,
        uint256 minDuration,
        uint256 maxDuration,
        string memory place,
        IPolicy.Application memory application
    )
        public
        returns(bool isMatching)
    {
        (
            , // we don't care about the wallet address here
            , // we don't care about the protected balance here
            uint256 duration,
            uint256 applicationBundleId,
            uint256 premium,
            string memory applicationPlace,
            // we don't care about the risk id here
        ) = decodeApplicationParameterFromData(application.data);

        // if bundle id specified a match is required
        if(applicationBundleId > 0 && bundleId != applicationBundleId) {
            emit LogBundleMismatch(bundleId, applicationBundleId);
            return false;
        }

        uint256 errorId = 0;

        if(application.sumInsuredAmount < minSumInsured) { errorId = 1; }
        if(application.sumInsuredAmount > maxSumInsured) { errorId = 2; }

        // commented code below to indicate how to enforce hard link to stking in this contract
        // if(getSupportedCapitalAmount(bundle.id) < bundle.lockedCapital + application.sumInsuredAmount) {
        //     sumInsuredOk = false;
        // }

        if(duration < minDuration) { errorId = 3; }
        if(duration > maxDuration) { errorId = 4; }
        
        if(premium == 0) { errorId = 5; }

        bytes32 bundlePlace = keccak256(abi.encodePacked(place));

        if(bundlePlace != PLACE_WILDCARD_HASH) {
            if(bundlePlace != keccak256(abi.encodePacked(applicationPlace))) { errorId = 6; }
        }

        emit LogBundleMatchesApplication(bundleId, errorId);
        return (errorId == 0);
    }

    function getSupportedCapitalAmount(uint256 bundleId)
        public view
        returns(uint256 capitalCap)
    {
        // if no staking data provider is available anything goes
        if(address(_staking) == address(0)) {
            return _bundleCapitalCap;
        }

        // otherwise: get amount supported by staking
        uint96 bundleNftId = _chainRegistry.getBundleNftId(
            _instanceService.getInstanceId(),
            bundleId);

        return _staking.capitalSupport(bundleNftId);
    }

    function getRiskpoolCapitalCap() public view returns (uint256 poolCapitalCap) {
        return _riskpoolCapitalCap;
    }

    function getBundleCapitalCap() public view returns (uint256 bundleCapitalCap) {
        return _bundleCapitalCap;
    }

    function getMaxBundleLifetime() public pure returns(uint256 maxBundleLifetime) {
        return MAX_BUNDLE_LIFETIME;
    }

    function bundleIdsForPlace(string calldata place)
        external 
        view
        returns(uint256[] memory)
    {
        bytes32 bundlePlace = keccak256(abi.encodePacked(place));
        return _bundleIdForBundlePlace[bundlePlace];
    }

    function _afterFundBundle(uint256 bundleId, uint256 amount)
        internal
        override
        view
    {
        require(
            _instanceService.getBundle(bundleId).capital <= _bundleCapitalCap, 
            "ERROR:RAINRP-100:FUNDING_EXCEEDS_BUNDLE_CAPITAL_CAP");

        require(
            getCapital() <= _riskpoolCapitalCap, 
            "ERROR:RAINRP-101:FUNDING_EXCEEDS_RISKPOOL_CAPITAL_CAP");
    }

}