// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import "forge-std/Script.sol";
import "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import "../contracts/ReserveOracle.sol";
import "../contracts/MTokenizedDeposit.sol";
import "../contracts/CariSettlement.sol";

/**
 * @title DeployAll
 * @notice Deployment script for M&T Bank Cari Deposit Account (CDA) contracts on ZKsync Prividium.
 *
 *         TERMINOLOGY:
 *         - CDA = Cari Deposit Account (on-chain token representation)
 *         - DDA = Demand Deposit Account (off-chain fiat account at M&T Bank)
 *
 *         Deployment order:
 *         1. ReserveOracle (behind ERC1967 proxy) - for 1:1 CDA reserve backing
 *         2. MTokenizedDeposit (behind ERC1967 proxy, linked to oracle) - CDA token contract
 *         3. CariSettlement (behind ERC1967 proxy, linked to token) - cross-bank CDA transfers
 *         4. Link settlement to token (setCariSettlement)
 *         5. Grant operational roles
 *
 *         SECURITY GUARDIAN NOTE:
 *         - In production, the `admin` address MUST be a TimelockController
 *           controlled by an M&T Bank multi-sig (e.g., Gnosis Safe with 3/5 threshold).
 *         - The `attestor` key MUST be HSM-backed (Thales Luna / Utimaco).
 *         - The `minter` and `burner` keys MUST be HSM-backed with SoD.
 *         - NEVER deploy with EOA admin keys in production.
 *
 * @dev    Usage:
 *         # ZKsync Sepolia Testnet:
 *         forge script deploy/DeployAll.s.sol:DeployAll \
 *             --rpc-url $ZKSYNC_SEPOLIA_RPC \
 *             --broadcast --verify \
 *             -vvvv
 *
 *         # ZKsync Prividium Mainnet:
 *         forge script deploy/DeployAll.s.sol:DeployAll \
 *             --rpc-url $PRIVIDIUM_RPC \
 *             --broadcast --verify \
 *             -vvvv
 */
contract DeployAll is Script {
    // =========================================================================
    //                     PLACEHOLDER ADDRESSES
    //                 Replace with M&T Bank multi-sig addresses
    // =========================================================================

    // M&T Bank Timelock/multi-sig (DEFAULT_ADMIN_ROLE on all contracts)
    address constant ADMIN = 0x1111111111111111111111111111111111111111;

    // HSM-backed attestor for reserve oracle
    address constant ATTESTOR = 0x2222222222222222222222222222222222222222;

    // HSM-backed minter (M&T treasury operations)
    address constant MINTER = 0x3333333333333333333333333333333333333333;

    // HSM-backed burner (M&T redemption service)
    address constant BURNER = 0x4444444444444444444444444444444444444444;

    // Compliance officer (KYC/AML/OFAC operations)
    address constant COMPLIANCE = 0x5555555555555555555555555555555555555555;

    // Emergency pause operator
    address constant PAUSER = 0x6666666666666666666666666666666666666666;

    // Cari settlement operator (Cari Network validator set)
    address constant SETTLEMENT_OPERATOR = 0x7777777777777777777777777777777777777777;

    // Settlement initiator (M&T Bank treasury)
    address constant INITIATOR = 0x8888888888888888888888888888888888888888;

    // =========================================================================
    //                        CONFIGURATION
    // =========================================================================

    uint256 constant MAX_STALENESS = 86_400;       // 24 hours
    uint256 constant SETTLEMENT_EXPIRY = 86_400;   // 24 hours

    function run() external {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        vm.startBroadcast(deployerKey);

        // --- 1. Deploy ReserveOracle (CDA reserve backing) ---
        ReserveOracle oracleImpl = new ReserveOracle();
        ERC1967Proxy oracleProxy = new ERC1967Proxy(
            address(oracleImpl),
            abi.encodeCall(ReserveOracle.initialize, (ADMIN, ATTESTOR, MAX_STALENESS))
        );
        ReserveOracle oracle = ReserveOracle(address(oracleProxy));
        console.log("ReserveOracle proxy:", address(oracle));
        console.log("ReserveOracle impl: ", address(oracleImpl));

        // --- 2. Deploy MTokenizedDeposit (CDA token contract) ---
        MTokenizedDeposit tokenImpl = new MTokenizedDeposit();
        ERC1967Proxy tokenProxy = new ERC1967Proxy(
            address(tokenImpl),
            abi.encodeCall(MTokenizedDeposit.initialize, (ADMIN, address(oracle)))
        );
        MTokenizedDeposit token = MTokenizedDeposit(address(tokenProxy));
        console.log("MTokenizedDeposit proxy:", address(token));
        console.log("MTokenizedDeposit impl: ", address(tokenImpl));

        // --- 3. Deploy CariSettlement (cross-bank CDA transfers) ---
        CariSettlement settlementImpl = new CariSettlement();
        ERC1967Proxy settlementProxy = new ERC1967Proxy(
            address(settlementImpl),
            abi.encodeCall(
                CariSettlement.initialize,
                (ADMIN, address(token), SETTLEMENT_EXPIRY)
            )
        );
        CariSettlement settlement = CariSettlement(address(settlementProxy));
        console.log("CariSettlement proxy:", address(settlement));
        console.log("CariSettlement impl: ", address(settlementImpl));

        // --- 4. Link settlement to CDA token ---
        // NOTE: This must be called by ADMIN. If deployer != ADMIN, this step
        // must be executed separately via the multi-sig.
        // token.setCariSettlement(address(settlement));

        // --- 5. Grant roles ---
        // NOTE: These must be called by ADMIN via multi-sig in production.
        // token.grantRole(token.MINTER_ROLE(), MINTER);
        // token.grantRole(token.BURNER_ROLE(), BURNER);
        // token.grantRole(token.COMPLIANCE_ROLE(), COMPLIANCE);
        // token.grantRole(token.PAUSER_ROLE(), PAUSER);
        // settlement.grantRole(settlement.SETTLEMENT_OPERATOR_ROLE(), SETTLEMENT_OPERATOR);
        // settlement.grantRole(settlement.INITIATOR_ROLE(), INITIATOR);

        vm.stopBroadcast();

        console.log("");
        console.log("=== DEPLOYMENT COMPLETE ===");
        console.log("Network: ZKsync Prividium (Cari Network - CDA Platform)");
        console.log("Bank:    M&T Bank");
        console.log("");
        console.log("NEXT STEPS (via M&T multi-sig):");
        console.log("1. token.setCariSettlement(settlement)");
        console.log("2. token.grantRole(MINTER_ROLE, minterAddress)");
        console.log("3. token.grantRole(BURNER_ROLE, burnerAddress)");
        console.log("4. token.grantRole(COMPLIANCE_ROLE, complianceAddress)");
        console.log("5. token.grantRole(PAUSER_ROLE, pauserAddress)");
        console.log("6. settlement.grantRole(SETTLEMENT_OPERATOR_ROLE, operatorAddress)");
        console.log("7. settlement.grantRole(INITIATOR_ROLE, initiatorAddress)");
        console.log("8. oracle.updateAttestation(reserves, hash) -- seed initial CDA reserves");
    }
}
