// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

/**
 * @title IMTokenizedDeposit
 * @notice Interface for M&T Bank's Cari Deposit Account (CDA) token on Cari Network / ZKsync Prividium.
 *
 *         TERMINOLOGY:
 *         - CDA = Cari Deposit Account (on-chain token representation)
 *         - DDA = Demand Deposit Account (off-chain fiat account)
 *         - Minting creates CDA from DDA (fiat deposited -> CDA issued)
 *         - Burning redeems CDA back to DDA (CDA destroyed -> fiat returned)
 *
 * @dev    Extends ERC-20 with compliance controls, Travel Rule hooks, reserve oracle
 *         integration, and Cari settlement callbacks required for a GENIUS-Act-compliant
 *         FDIC-insured Cari deposit.
 */
interface IMTokenizedDeposit {
    // --- Travel Rule ---

    /// @notice Travel Rule metadata attached to qualifying transfers (>= $3,000).
    struct TravelRuleData {
        bytes32 originatorHash;   // Hash of originator PII (name, account, institution)
        bytes32 beneficiaryHash;  // Hash of beneficiary PII
        string  originatorInstitution;  // "M&T Bank" or Cari member bank name
        string  beneficiaryInstitution; // Destination institution name
    }

    // --- Events ---

    event Mint(address indexed to, uint256 amount, string referenceId);
    event Burn(address indexed from, uint256 amount, string referenceId);
    event ForcedTransfer(address indexed from, address indexed to, uint256 amount, string reason);
    event AddressWhitelisted(address indexed account);
    event AddressRemovedFromWhitelist(address indexed account);
    event AddressFrozen(address indexed account);
    event AddressUnfrozen(address indexed account);
    event ReserveOracleUpdated(address indexed oldOracle, address indexed newOracle);
    event CariSettlementUpdated(address indexed oldSettlement, address indexed newSettlement);
    event OperatorUpdated(address indexed oldOperator, address indexed newOperator);
    event TravelRuleTransfer(
        address indexed from,
        address indexed to,
        uint256 amount,
        bytes32 originatorHash,
        bytes32 beneficiaryHash
    );

    // --- Core Operations (DDA <-> CDA) ---

    function mint(address to, uint256 amount, string calldata referenceId) external;
    function burn(address from, uint256 amount, string calldata referenceId) external;

    /// @notice Transfer with Travel Rule metadata for FinCEN compliance.
    function transferWithTravelRule(
        address to,
        uint256 amount,
        TravelRuleData calldata travelData
    ) external returns (bool);

    /// @notice Compliance-mandated forced transfer (e.g., court order, OFAC seizure).
    function forceTransfer(
        address from,
        address to,
        uint256 amount,
        string calldata reason
    ) external;

    // --- Operator (Cari Whitepaper: centralized supply controller) ---

    /// @notice Designate an Operator address, granting it MINTER_ROLE and BURNER_ROLE.
    function setOperator(address operator) external;

    // --- Compliance ---

    function whitelistAddress(address account) external;
    function removeFromWhitelist(address account) external;
    function freezeAddress(address account) external;
    function unfreezeAddress(address account) external;
    function isWhitelisted(address account) external view returns (bool);
    function isFrozen(address account) external view returns (bool);

    // --- Settlement Callbacks (called by CariSettlement for cross-bank CDA transfers) ---

    event SettlementReturn(address indexed to, uint256 amount, bytes32 indexed settlementId);

    function settlementMint(address to, uint256 amount, bytes32 settlementId) external;
    function settlementBurn(address from, uint256 amount, bytes32 settlementId) external;
    function settlementReturn(address to, uint256 amount, bytes32 settlementId) external;
}
