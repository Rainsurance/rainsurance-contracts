// SPDX-License-Identifier: MIT
pragma solidity ^0.8.2;

import "../strings.sol";

import "@openzeppelin/contracts/utils/Strings.sol";
import "@etherisc/gif-interface/contracts/components/Oracle.sol";
import {Functions, FunctionsClient} from "./../cl-functions/dev/functions/FunctionsClient.sol";

contract RainOracleCLFunctions is 
    Oracle, FunctionsClient
{
    using strings for bytes32;
    using Functions for Functions.Request;

    mapping(bytes32 /* Chainlink request ID */ => uint256 /* GIF request ID */) public gifRequests;
    uint64 private subscriptionId;
    uint32 private gasLimit;

    //TODO: remove after testing
    bytes32 public latestRequestId;
    bytes public latestResponse;
    bytes public latestError;

    event LogRainRequest(uint256 requestId, bytes32 chainlinkRequestId);
    
    event LogRainFulfill(
        uint256 requestId, 
        bytes32 chainlinkRequestId, 
        uint256 prec,
        uint256 precDays
    );

    event OCRResponse(bytes32 indexed requestId, bytes result, bytes err);

    constructor(
        bytes32 _name,
        address _registry,
        address _chainLinkOperator,
        uint64 _subscriptionId,
        uint32 _gasLimit
    )
        Oracle(_name, _registry)
        FunctionsClient(_chainLinkOperator)
    {
        subscriptionId = _subscriptionId;
        gasLimit = _gasLimit;
    }

    function request(uint256 gifRequestId, bytes calldata input)
        external override
        onlyQuery
    {
        
        (
            uint256 startDate, 
            uint256 endDate, 
            int256 lat,
            int256 lng,
            uint256 coordMultiplier,
            uint256 precMultiplier,
            bytes memory secrets,
            string memory source
        ) = abi.decode(input, (uint256, uint256, int256, int256, uint256, uint256, bytes, string));

        Functions.Request memory req;
        req.initializeRequest(Functions.Location.Inline, Functions.CodeLanguage.JavaScript, source);

        if (secrets.length > 0) {
            req.addRemoteSecrets(secrets);
        }

        string[] memory args = prepareArgs(startDate, endDate, lat, lng, coordMultiplier, precMultiplier);
        req.addArgs(args);

        bytes32 chainlinkRequestId = sendRequest(req, subscriptionId, gasLimit);

        latestRequestId = chainlinkRequestId;

        gifRequests[chainlinkRequestId] = gifRequestId;
        emit LogRainRequest(gifRequestId, chainlinkRequestId);
    }

    function prepareArgs(
        uint256 startDate,
        uint256 endDate,
        int256 lat,
        int256 lng,
        uint256 coordMultiplier,
        uint256 precMultiplier
    ) public pure returns (string[] memory) {
        string[] memory args = new string[](6);
        args[0] = Strings.toString(startDate);
        args[1] = Strings.toString(endDate);
        args[2] = string(abi.encodePacked(lat >= 0 ? "" : "-", Strings.toString(abs(lat))));
        args[3] = string(abi.encodePacked(lng >= 0 ? "" : "-", Strings.toString(abs(lng))));
        args[4] = Strings.toString(coordMultiplier);
        args[5] = Strings.toString(precMultiplier);
        return args;
    }

    function fulfillRequest(
        bytes32 chainlinkRequestId,
        bytes memory response,
        bytes memory err
    ) internal override {
        latestResponse = response;
        latestError = err;

        emit OCRResponse(chainlinkRequestId, response, err);

        if (err.length == 0) {
            (uint256 prec, uint256 precDays) = abi.decode(response, (uint256, uint256));

            uint256 gifRequest = gifRequests[chainlinkRequestId];
            bytes memory data =  abi.encode(prec, precDays);
            _respond(gifRequest, data);

            delete gifRequests[chainlinkRequestId];
            emit LogRainFulfill(gifRequest, chainlinkRequestId, prec, precDays);
        }
    }

  function cancel(uint256 requestId)
        external override
        onlyOwner
    {
        // TODO mid/low priority
        // cancelChainlinkRequest(_requestId, _payment, _callbackFunctionId, _expiration);
    }


// only used for testing of chainlink operator
    function encodeRequestParameters(
        uint256 startDate, 
        uint256 endDate, 
        int256 lat,
        int256 lng,
        uint256 coordMultiplier,
        uint256 precMultiplier,
        bytes memory secrets,
        string memory source
    ) 
        external pure returns(bytes memory parameterData)
    {
        return abi.encode(
            startDate, 
            endDate,
            lat,
            lng,
            coordMultiplier,
            precMultiplier,
            secrets,
            source
        );
    }

    // only used for testing of chainlink operator
    function encodeFulfillParameters(
        bytes32 chainlinkRequestId, 
        uint256 precActual,
        uint256 precDays
    ) 
        external
        pure
        returns(bytes memory parameterData)
    {
        bytes memory response = abi.encode(precActual, precDays);

        return abi.encode(
            chainlinkRequestId, 
            response,
            ""
        );
    }

    /**
    * @notice Allows the Functions oracle address to be updated
    *
    * @param oracle New oracle address
    */
    function updateOracleAddress(address oracle) public onlyOwner {
        setOracle(oracle);
    }

    function addSimulatedRequestId(address oracleAddress, bytes32 requestId) public onlyOwner {
        addExternalRequest(oracleAddress, requestId);
    }

    function abs(int256 x) private pure returns (uint256) {
        return x >= 0 ? uint256(x) : uint256(-x);
    }

    function getCLFunctionsGasLimit() external view returns(uint32 clFunctionsgasLimit) {
        return gasLimit;
    }

    function getCLFunctionsSubscriptionId() external view returns(uint64 clFunctionsSubscriptionId) {
        return subscriptionId;
    }

}