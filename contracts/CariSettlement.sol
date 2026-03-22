// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./interfaces/ICariSettlement.sol";
import "./interfaces/IMTokenizedDeposit.sol";

/**
 * @title CariSettlement
 * @notice Cross-bank settlement contract for Cari Deposit Account (CDA) transfers
 *         on the Cari Network / ZKsync Prividium.
 *         Coordinates burn-at-source / mint-at-destination for inter-bank CDA
 *         transfers between M&T Bank and other Cari member institutions.
 *
 *         TERMINOLOGY:
 *         - CDA = Cari Deposit Account (on-chain token representation)
 *         - DDA = Demand Deposit Account (off-chain fiat account)
 *         - Cross-bank CDA transfers do not involve DDA - they move CDA between member banks
 *
 *         OPERATOR ROLE (per Cari Network Whitepaper):
 *         The Operator (M&T Bank) is the centralized entity controlling CDA supply.
 *         - The Operator initiates settlements by burning CDA at source (via MINTER/BURNER roles)
 *         - Settlement execution mints CDA at the destination bank
 *         - The Operator's MINTER_ROLE and BURNER_ROLE are used indirectly via SETTLEMENT_ROLE
 *           callbacks defined in MTokenizedDeposit (settlementMint, settlementBurn)
 *
 * @dev    Flow:
 *         1. Originator bank calls initiateSettlement() -> burns CDA at source.
 *         2. Cari Network validator set verifies the burn and Travel Rule data.
 *         3. Settlement operator calls executeSettlement() -> mints CDA at destination.
 *         4. If execution fails or times out, revertSettlement() re-mints CDA at source.
 *
 *         SECURITY GUARDIAN NOTES:
 *         - SETTLEMENT_OPERATOR_ROLE key MUST be HSM-backed with multi-party auth.
 *         - Travel Rule hash is stored on-chain; full PII is held off-chain (Notabene).
 *         - Settlement expiry prevents indefinite lock-up of burned CDA.
 *         - All operations emit events for the examiner audit trail.
 *         - Reentrancy guard on all state-mutating functions.
 */
contract CariSettlement is
    ICariSettlement,
    AccessControlUpgradeable,
    PausableUpgradeable,
    ReentrancyGuard,
    UUPSUpgradeable
{
    // =========================================================================
    //                              ROLES
    // =========================================================================

    /// @notice Role for Settlement Bank operations (net settlement).
    bytes32 public constant SETTLEMENT_BANK_ROLE = keccak256("SETTLEMENT_BANK_ROLE");

    /// @notice Operator authorized to execute/revert settlements (Cari validator set).
    bytes32 public constant SETTLEMENT_OPERATOR_ROLE = keccak256("SETTLEMENT_OPERATOR_ROLE");

    /// @notice Role for initiating settlements (source bank's minting/treasury service).
    bytes32 public constant INITIATOR_ROLE = keccak256("INITIATOR_ROLE");

    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    // =========================================================================
    //                              STATE
    // =========================================================================

    /// @notice M&T Bank's Cari deposit (CDA) contract on this Prividium instance.
    IMTokenizedDeposit public token;

    /// @notice Default settlement expiry window in seconds (e.g., 24 hours).
    uint256 public settlementExpiry;

    /// @notice Settlement requests keyed by settlementId.
    mapping(bytes32 => SettlementRequest) private _settlements;

    /// @notice Nonce for generating unique settlement IDs.
    uint256 private _nonce;

    /// @notice Next settlement window ID.
    uint256 private _nextWindowId;

    /// @notice Settlement windows by ID.
    mapping(uint256 => SettlementWindow) private _windows;

    /// @notice Registry of Cari member bank addresses.
    mapping(address => bool) public isMemberBank;

    // =========================================================================
    //                              EVENTS
    // =========================================================================

    event MemberBankAdded(address indexed bank);
    event MemberBankRemoved(address indexed bank);
    event SettlementExpiryUpdated(uint256 oldExpiry, uint256 newExpiry);

    // =========================================================================
    //                              ERRORS
    // =========================================================================

    error NotMemberBank(address bank);
    error SettlementNotFound(bytes32 settlementId);
    error SettlementNotPending(bytes32 settlementId, SettlementStatus status);
    error SettlementAlreadyExpired(bytes32 settlementId);
    error SettlementNotExpired(bytes32 settlementId);
    error ZeroAddress();
    error ZeroAmount();
    error InvalidExpiry();
    error WindowNotFound(uint256 windowId);
    error WindowNotOpen(uint256 windowId);
    error WindowNotClosed(uint256 windowId);
    error WindowAlreadyClosed(uint256 windowId);
    error InvalidCloseTime(uint256 closesAt);
    error NetSettlementImbalanced();

    // =========================================================================
    //                            INITIALIZER
    // =========================================================================

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    /**
     * @notice Initialize the CariSettlement contract for CDA transfers.
     * @param admin           M&T Bank Timelock/multi-sig.
     * @param _token          Address of MTokenizedDeposit (CDA contract) on this Prividium instance.
     * @param _settlementExpiry Default expiry window in seconds.
     */
    function initialize(
        address admin,
        address _token,
        uint256 _settlementExpiry
    ) public initializer {
        if (admin == address(0) || _token == address(0)) revert ZeroAddress();
        if (_settlementExpiry == 0) revert InvalidExpiry();

        __AccessControl_init();
        __Pausable_init();

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(UPGRADER_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);
        _grantRole(INITIATOR_ROLE, admin);
        _grantRole(SETTLEMENT_BANK_ROLE, admin);

        token = IMTokenizedDeposit(_token);
        settlementExpiry = _settlementExpiry;
    }

    // =========================================================================
    //                       MEMBER BANK REGISTRY
    // =========================================================================

    /// @notice Register a Cari member bank address.
    function addMemberBank(address bank) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (bank == address(0)) revert ZeroAddress();
        isMemberBank[bank] = true;
        emit MemberBankAdded(bank);
    }

    /// @notice Remove a Cari member bank address.
    function removeMemberBank(address bank) external onlyRole(DEFAULT_ADMIN_ROLE) {
        isMemberBank[bank] = false;
        emit MemberBankRemoved(bank);
    }

    // =========================================================================
    //                    ICariSettlement IMPLEMENTATION
    // =========================================================================

    /// @inheritdoc ICariSettlement
    function initiateSettlement(
        address destinationBank,
        address originator,
        address beneficiary,
        uint256 amount,
        bytes32 travelRuleHash
    )
        external
        override
        onlyRole(INITIATOR_ROLE)
        whenNotPaused
        nonReentrant
        returns (bytes32 settlementId)
    {
        if (!isMemberBank[destinationBank]) revert NotMemberBank(destinationBank);
        if (originator == address(0) || beneficiary == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();

        // Generate unique settlement ID
        settlementId = keccak256(abi.encodePacked(block.chainid, address(this), _nonce++));

        // Burn CDA at source (M&T Bank)
        token.settlementBurn(originator, amount, settlementId);

        // Create settlement record
        _settlements[settlementId] = SettlementRequest({
            settlementId: settlementId,
            sourceBank: address(this),
            destinationBank: destinationBank,
            originator: originator,
            beneficiary: beneficiary,
            amount: amount,
            travelRuleHash: travelRuleHash,
            createdAt: block.timestamp,
            expiresAt: block.timestamp + settlementExpiry,
            status: SettlementStatus.PENDING
        });

        emit SettlementInitiated(
            settlementId,
            address(this),
            destinationBank,
            originator,
            beneficiary,
            amount,
            travelRuleHash
        );
    }

    /// @inheritdoc ICariSettlement
    function executeSettlement(
        bytes32 settlementId
    ) external override onlyRole(SETTLEMENT_OPERATOR_ROLE) whenNotPaused nonReentrant {
        SettlementRequest storage s = _settlements[settlementId];
        if (s.createdAt == 0) revert SettlementNotFound(settlementId);
        if (s.status != SettlementStatus.PENDING) {
            revert SettlementNotPending(settlementId, s.status);
        }
        if (block.timestamp > s.expiresAt) revert SettlementAlreadyExpired(settlementId);

        s.status = SettlementStatus.EXECUTED;

        // Mint CDA at destination bank for the beneficiary
        // NOTE: In a multi-instance Cari deployment, this would call the destination
        // bank's CDA contract via cross-chain message. On a single Prividium instance,
        // we mint directly.
        token.settlementMint(s.beneficiary, s.amount, settlementId);

        emit SettlementExecuted(settlementId, block.timestamp);
    }

    /// @inheritdoc ICariSettlement
    function revertSettlement(
        bytes32 settlementId,
        string calldata reason
    ) external override onlyRole(SETTLEMENT_OPERATOR_ROLE) whenNotPaused nonReentrant {
        SettlementRequest storage s = _settlements[settlementId];
        if (s.createdAt == 0) revert SettlementNotFound(settlementId);
        if (s.status != SettlementStatus.PENDING) {
            revert SettlementNotPending(settlementId, s.status);
        }

        s.status = SettlementStatus.REVERTED;

        // Return CDA to originator at source bank (bypasses reserve check)
        token.settlementReturn(s.originator, s.amount, settlementId);

        emit SettlementReverted(settlementId, reason);
    }

    /**
     * @notice Expire a settlement that has passed its expiry window.
     * @dev    Anyone can call this to clean up. Re-mints CDA to the originator.
     */
    function expireSettlement(bytes32 settlementId) external whenNotPaused nonReentrant {
        SettlementRequest storage s = _settlements[settlementId];
        if (s.createdAt == 0) revert SettlementNotFound(settlementId);
        if (s.status != SettlementStatus.PENDING) {
            revert SettlementNotPending(settlementId, s.status);
        }
        if (block.timestamp <= s.expiresAt) revert SettlementNotExpired(settlementId);

        s.status = SettlementStatus.EXPIRED;

        // Return CDA to originator (bypasses reserve check)
        token.settlementReturn(s.originator, s.amount, settlementId);

        emit SettlementExpired(settlementId);
    }

    /// @inheritdoc ICariSettlement
    function getSettlement(
        bytes32 settlementId
    ) external view override returns (SettlementRequest memory) {
        return _settlements[settlementId];
    }

    // =========================================================================
    //              DAILY NET SETTLEMENT (Cari Whitepaper Section)
    // =========================================================================

    /// @inheritdoc ICariSettlement
    function openSettlementWindow(
        uint256 closesAt
    ) external override onlyRole(SETTLEMENT_BANK_ROLE) whenNotPaused returns (uint256 windowId) {
        if (closesAt <= block.timestamp) revert InvalidExpiry();
        
        windowId = _nextWindowId++;
        _windows[windowId] = SettlementWindow({
            windowId: windowId,
            openedAt: block.timestamp,
            closesAt: closesAt,
            status: SettlementWindowStatus.OPEN
        });
        
        emit SettlementWindowOpened(windowId, block.timestamp, closesAt);
    }

    /// @inheritdoc ICariSettlement
    function closeSettlementWindow(
        uint256 windowId
    ) external override onlyRole(SETTLEMENT_BANK_ROLE) whenNotPaused {
        SettlementWindow storage w = _windows[windowId];
        if (w.openedAt == 0) revert SettlementNotFound(bytes32(windowId));
        if (w.status != SettlementWindowStatus.OPEN) {
            revert SettlementNotPending(bytes32(windowId), SettlementStatus.EXECUTED);
        }
        
        w.status = SettlementWindowStatus.CLOSED;
        emit SettlementWindowClosed(windowId, block.timestamp);
    }

    /// @inheritdoc ICariSettlement
    function netSettle(
        uint256 windowId,
        NetSettlementEntry[] calldata entries
    ) external override onlyRole(SETTLEMENT_BANK_ROLE) whenNotPaused nonReentrant {
        SettlementWindow storage w = _windows[windowId];
        if (w.openedAt == 0) revert SettlementNotFound(bytes32(windowId));
        if (w.status != SettlementWindowStatus.CLOSED) {
            revert SettlementNotPending(bytes32(windowId), SettlementStatus.PENDING);
        }
        
        // Conservation-of-value check: sum of net positions must be zero
        int256 totalNet;
        for (uint256 i = 0; i < entries.length; i++) {
            totalNet += entries[i].netAmount;
        }
        if (totalNet != 0) revert NetSettlementImbalanced();
        
        // Process net settlement entries
        for (uint256 i = 0; i < entries.length; i++) {
            if (entries[i].netAmount > 0) {
                // Net receiver: mint CDA
                token.settlementMint(
                    entries[i].bank,
                    uint256(entries[i].netAmount),
                    bytes32(windowId)
                );
            } else if (entries[i].netAmount < 0) {
                // Net payer: burn CDA
                token.settlementBurn(
                    entries[i].bank,
                    uint256(-entries[i].netAmount),
                    bytes32(windowId)
                );
            }
        }
        
        w.status = SettlementWindowStatus.SETTLED;
        emit NetSettlementExecuted(windowId, block.timestamp, entries.length);
    }

    /// @inheritdoc ICariSettlement
    function getSettlementWindow(
        uint256 windowId
    ) external view override returns (SettlementWindow memory) {
        return _windows[windowId];
    }

    // =========================================================================
    //                              ADMIN
    // =========================================================================

    function setSettlementExpiry(uint256 newExpiry) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (newExpiry == 0) revert InvalidExpiry();
        uint256 old = settlementExpiry;
        settlementExpiry = newExpiry;
        emit SettlementExpiryUpdated(old, newExpiry);
    }

    // =========================================================================
    //                              PAUSE
    // =========================================================================

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    // =========================================================================
    //                            UUPS UPGRADE
    // =========================================================================

    function _authorizeUpgrade(address) internal override onlyRole(UPGRADER_ROLE) {}
}
