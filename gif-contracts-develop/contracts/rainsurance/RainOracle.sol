// SPDX-License-Identifier: MIT
pragma solidity 0.8.2;

import "./strings.sol";

import "@openzeppelin/contracts/utils/Strings.sol";
import "@chainlink/contracts/src/v0.8/ChainlinkClient.sol";
import "@etherisc/gif-interface/contracts/components/Oracle.sol";

contract RainOracle is 
    Oracle, ChainlinkClient 
{
    using strings for bytes32;
    using Chainlink for Chainlink.Request;
    
    mapping(bytes32 /* Chainlink request ID */ => uint256 /* GIF request ID */) public gifRequests;
    bytes32 private jobId;
    uint256 private payment;

    event LogRainRequest(uint256 requestId, bytes32 chainlinkRequestId);
    
    event LogRainFulfill(
        uint256 requestId, 
        bytes32 chainlinkRequestId, 
        bytes32 placeId, 
        uint256 startDate, 
        uint256 endDate, 
        uint256 aaay
    );

    constructor(
        bytes32 _name,
        address _registry,
        address _chainLinkToken,
        address _chainLinkOperator,
        bytes32 _jobId,
        uint256 _payment
    )
        Oracle(_name, _registry)
    {
        updateRequestDetails(
            _chainLinkToken, 
            _chainLinkOperator, 
            _jobId, 
            _payment);
    }

    function updateRequestDetails(
        address _chainLinkToken,
        address _chainLinkOperator,
        bytes32 _jobId,
        uint256 _payment
    ) 
        public 
        onlyOwner 
    {
        if (_chainLinkToken != address(0)) { setChainlinkToken(_chainLinkToken); }
        if (_chainLinkOperator != address(0)) { setChainlinkOracle(_chainLinkOperator); }
        
        jobId = _jobId;
        payment = _payment;
    }

    function request(uint256 gifRequestId, bytes calldata input)
        external override
        onlyQuery
    {
        Chainlink.Request memory request_ = buildChainlinkRequest(
            jobId,
            address(this),
            this.fulfill.selector
        );

        (
            uint256 startDate, 
            uint256 endDate, 
            int256 lat,
            int256 long
        ) = abi.decode(input, (uint256, uint256, int256, int256));

        request_.add("startDate", Strings.toString(startDate));
        request_.add("endDate", Strings.toString(endDate));
        string memory latSign = lat >= 0 ? "" : "-";
        string memory latString = string(abi.encodePacked(latSign, Strings.toString(abs(lat)))); 
        request_.add("lat", latString);
        string memory longSign = lat >= 0 ? "" : "-";
        string memory longString = string(abi.encodePacked(longSign, Strings.toString(abs(long)))); 
        request_.add("long", longString);

        bytes32 chainlinkRequestId = sendChainlinkRequest(request_, payment);

        gifRequests[chainlinkRequestId] = gifRequestId;
        emit LogRainRequest(gifRequestId, chainlinkRequestId);
    }

    function fulfill(
        bytes32 chainlinkRequestId, 
        bytes32 placeId, 
        uint256 startDate, 
        uint256 endDate, 
        uint256 aaay
    )
        public recordChainlinkFulfillment(chainlinkRequestId) 
    {
        uint256 gifRequest = gifRequests[chainlinkRequestId];
        bytes memory data =  abi.encode(placeId, startDate, endDate, aaay);        
        _respond(gifRequest, data);

        delete gifRequests[chainlinkRequestId];
        emit LogRainFulfill(gifRequest, chainlinkRequestId, placeId, startDate, endDate, aaay);
    }

    function cancel(uint256 requestId)
        external override
        onlyOwner
    {
        // TODO mid/low priority
        // cancelChainlinkRequest(_requestId, _payment, _callbackFunctionId, _expiration);
    }

    // only used for testing of chainlink operator
    function encodeFulfillParameters(
        bytes32 chainlinkRequestId, 
        bytes32 placeId, 
        uint256 startDate, 
        uint256 endDate, 
        uint256 aaay
    ) 
        external
        pure
        returns(bytes memory parameterData)
    {
        return abi.encode(
            chainlinkRequestId, 
            placeId, 
            startDate, 
            endDate, 
            aaay
        );
    }


    function abs(int256 x) private pure returns (uint256) {
        return x >= 0 ? uint256(x) : uint256(-x);
    }

    function getChainlinkJobId() external view returns(bytes32 chainlinkJobId) {
        return jobId;
    }

    function getChainlinkPayment() external view returns(uint256 paymentAmount) {
        return payment;
    }

    function getChainlinkToken() external view returns(address linkTokenAddress) {
        return chainlinkTokenAddress();
    }

    function getChainlinkOperator() external view returns(address operator) {
        return chainlinkOracleAddress();
    }
}

