// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

/**
 * @title ICariSettlement
 * @notice Standard settlement interface for cross-bank Cari Deposit Account (CDA) transfers
 *         on the Cari Network / ZKsync Prividium.
 *
 *         TERMINOLOGY:
 *         - CDA = Cari Deposit Account (on-chain token representation)
 *         - Cross-bank CDA transfers move value between member banks without touching DDA
 *
 * @dev    Each Cari member bank deploys its own CDA contract and a CariSettlement adapter.
 *         Inter-bank transfers use a burn-at-source / mint-at-destination pattern
 *         coordinated through this interface.
 *
 *         SECURITY GUARDIAN NOTE: Cross-bank settlement messages MUST be
 *         authenticated via the Cari Network validator set. The settlement
 *         operator key requires HSM storage with multi-party authorization.
 *         All cross-bank flows must carry Travel Rule metadata for FinCEN compliance.
 */
interface ICariSettlement {
    /// @notice Status of a cross-bank settlement request.
    enum SettlementStatus {
        PENDING,
        EXECUTED,
        REVERTED,
        EXPIRED
    }

    /// @notice Status of a daily settlement window for net settlement.
    enum SettlementWindowStatus { OPEN, CLOSED, SETTLED }

    /// @notice A daily settlement window for aggregating interbank CDA transfers
    struct SettlementWindow {
        uint256 windowId;
        uint256 openedAt;
        uint256 closesAt;
        SettlementWindowStatus status;
    }

    /// @notice A single bank's net position after netting all transfers in a window
    struct NetSettlementEntry {
        address bank;
        int256 netAmount;  // positive = net receiver (mint CDA), negative = net payer (burn CDA)
    }

    /// @notice A cross-bank settlement request.
    struct SettlementRequest {
        bytes32 settlementId;        // Unique ID for this settlement
        address sourceBank;          // Cari member bank initiating
        address destinationBank;     // Cari member bank receiving
        address originator;          // Sender wallet (source bank)
        address beneficiary;         // Receiver wallet (destination bank)
        uint256 amount;              // Transfer amount (6 decimals)
        bytes32 travelRuleHash;      // Hash of Travel Rule metadata (originator/beneficiary info)
        uint256 createdAt;           // Timestamp of request creation
        uint256 expiresAt;           // Expiry timestamp
        SettlementStatus status;     // Current status
    }

    // --- Events ---

    /// @notice Emitted when a cross-bank CDA settlement is initiated (burn at source).
    event SettlementInitiated(
        bytes32 indexed settlementId,
        address indexed sourceBank,
        address indexed destinationBank,
        address originator,
        address beneficiary,
        uint256 amount,
        bytes32 travelRuleHash
    );

    /// @notice Emitted when a cross-bank CDA settlement is executed (mint at destination).
    event SettlementExecuted(bytes32 indexed settlementId, uint256 executedAt);

    /// @notice Emitted when a cross-bank CDA settlement is reverted (re-mint at source).
    event SettlementReverted(bytes32 indexed settlementId, string reason);

    /// @notice Emitted when a settlement expires without execution.
    event SettlementExpired(bytes32 indexed settlementId);

    /// @notice Emitted when a daily settlement window is opened.
    event SettlementWindowOpened(uint256 indexed windowId, uint256 openedAt, uint256 closesAt);

    /// @notice Emitted when a daily settlement window is closed.
    event SettlementWindowClosed(uint256 indexed windowId, uint256 closedAt);

    /// @notice Emitted when net settlement is executed for a window.
    event NetSettlementExecuted(uint256 indexed windowId, uint256 settledAt, uint256 entryCount);

    // --- Functions ---

    /// @notice Initiate a cross-bank CDA transfer: burns tokens at source, creates settlement request.
    /// @param destinationBank Cari member bank address to receive tokens.
    /// @param originator      Sender's wallet address on the source bank.
    /// @param beneficiary     Receiver's wallet address on the destination bank.
    /// @param amount          Amount to transfer (6 decimals).
    /// @param travelRuleHash  Keccak256 hash of the Travel Rule metadata payload.
    /// @return settlementId   Unique settlement identifier.
    function initiateSettlement(
        address destinationBank,
        address originator,
        address beneficiary,
        uint256 amount,
        bytes32 travelRuleHash
    ) external returns (bytes32 settlementId);

    /// @notice Execute a settlement: mints CDA at the destination bank.
    /// @dev    Called by the Cari Network settlement operator after validating the request.
    /// @param settlementId The settlement to execute.
    function executeSettlement(bytes32 settlementId) external;

    /// @notice Revert a settlement: re-mints CDA at the source bank.
    /// @param settlementId The settlement to revert.
    /// @param reason       Human-readable reason for the revert.
    function revertSettlement(bytes32 settlementId, string calldata reason) external;

    /// @notice Query a settlement request by ID.
    function getSettlement(bytes32 settlementId) external view returns (SettlementRequest memory);

    // --- Daily Net Settlement Functions ---

    /// @notice Open a new daily settlement window for aggregating interbank CDA transfers.
    /// @param closesAt Timestamp when the window closes (typically end of business day)
    /// @return windowId The ID of the newly opened window
    function openSettlementWindow(uint256 closesAt) external returns (uint256 windowId);

    /// @notice Close a settlement window, preventing new settlements from being added.
    /// @param windowId The window to close
    function closeSettlementWindow(uint256 windowId) external;

    /// @notice Execute net settlement for all banks in a closed window.
    /// @param windowId The closed window to settle
    /// @param entries Array of net positions per bank
    function netSettle(uint256 windowId, NetSettlementEntry[] calldata entries) external;

    /// @notice Get a settlement window's details.
    /// @param windowId The window ID to query
    function getSettlementWindow(uint256 windowId) external view returns (SettlementWindow memory);
}
