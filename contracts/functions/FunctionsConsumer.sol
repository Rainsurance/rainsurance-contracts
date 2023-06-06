// SPDX-License-Identifier: MIT
pragma solidity ^0.8.2;

import {Functions, FunctionsClient} from "./dev/functions/FunctionsClient.sol";
// import "@chainlink/contracts/src/v0.8/dev/functions/FunctionsClient.sol"; // Once published
import {ConfirmedOwner} from "@chainlink/contracts/src/v0.8/ConfirmedOwner.sol";

/**
 * @title Functions Consumer contract
 * @notice This contract is a demonstration of using Functions.
 * @notice NOT FOR PRODUCTION USE
 */
contract FunctionsConsumer is FunctionsClient, ConfirmedOwner {
  using Functions for Functions.Request;

  bytes32 public latestRequestId;
  bytes public latestResponse;
  bytes public latestError;

  uint256 public prec;
  uint256 public precDays;

  event OCRResponse(bytes32 indexed requestId, bytes result, bytes err);

  /**
   * @notice Executes once when a contract is created to initialize state variables
   *
   * @param oracle - The FunctionsOracle contract
   */
  // https://github.com/protofire/solhint/issues/242
  // solhint-disable-next-line no-empty-blocks
  constructor(address oracle) FunctionsClient(oracle) ConfirmedOwner(msg.sender) {}

  /**
   * @notice Send a simple request
   *
   * @param source JavaScript source code
   * @param secrets Encrypted secrets payload
   * @param args List of arguments accessible from within the source code
   * @param subscriptionId Funtions billing subscription ID
   * @param gasLimit Maximum amount of gas used to call the client contract's `handleOracleFulfillment` function
   * @return Functions request ID
   */
  function executeRequest(
    string calldata source,
    bytes calldata secrets,
    string[] calldata args,
    uint64 subscriptionId,
    uint32 gasLimit
  ) public onlyOwner returns (bytes32) {
    Functions.Request memory req;
    req.initializeRequest(Functions.Location.Inline, Functions.CodeLanguage.JavaScript, source);
    if (secrets.length > 0) {
      req.addRemoteSecrets(secrets);
    }
    if (args.length > 0) req.addArgs(args);

    bytes32 assignedReqID = sendRequest(req, subscriptionId, gasLimit);
    latestRequestId = assignedReqID;
    return assignedReqID;
  }

  /**
   * @notice Callback that is invoked once the DON has resolved the request or hit an error
   *
   * @param requestId The request ID, returned by sendRequest()
   * @param response Aggregated response from the user code
   * @param err Aggregated error from the user code or from the execution pipeline
   * Either response or error parameter will be set, but never both
   */
  function fulfillRequest(bytes32 requestId, bytes memory response, bytes memory err) internal override {
    latestResponse = response;
    latestError = err;

    emit OCRResponse(requestId, response, err);

    if (err.length == 0) {
      (prec, precDays) = abi.decode(response, (uint256, uint256));

      // (int256 resp1, int256 resp2) = abi.decode(response, (int256, int256));
      // prec = uint256(resp1);
      // precDays = uint256(resp2);
    }

    // //first split the results into individual strings based on the delimiter
    // //string memory s = bytes32ToString(response).toSlice();
    // string memory s = string(abi.encodePacked(response)).toSlice();
    // string memory delim = ",".toSlice();

    // //store each string in an array
    // string[] memory splitResults = new string[](s.count(delim)+ 1);                  
    // for (uint i = 0; i < splitResults.length; i++) {                              
    //     splitResults[i] = s.split(delim).toString();                              
    // }
    
    // prec = stringToUint(splitResults[0]);
    // precDays = stringToUint(splitResults[1]);

    
  }

  // function bytes32ToString(bytes32 x) private pure returns (string) {
  //     bytes memory bytesString = new bytes(32);
  //     uint charCount = 0;
  //     for (uint j = 0; j < 32; j++) {
  //         byte char = byte(bytes32(uint(x) * 2 ** (8 * j)));
  //         if (char != 0) {
  //             bytesString[charCount] = char;
  //             charCount++;
  //         }
  //     }
  //     bytes memory bytesStringTrimmed = new bytes(charCount);
  //     for (j = 0; j < charCount; j++) {
  //         bytesStringTrimmed[j] = bytesString[j];
  //     }
  //     return string(bytesStringTrimmed);
  // }

  // function stringToUint(string s) private pure returns (uint result) {
  //     bytes memory b = bytes(s);
  //     uint i;
  //     result = 0;
      
  //     for (i = 0; i < b.length; i++) {
  //         uint c = uint(b[i]);
  //         if (c >= 48 && c <= 57) {
  //             result = result * 10 + (c - 48);
  //         }
  //     }
  // }

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
}
