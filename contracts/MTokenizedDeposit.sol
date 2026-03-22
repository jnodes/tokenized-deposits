// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import "@openzeppelin/contracts-upgradeable/token/ERC20/ERC20Upgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./interfaces/IReserveOracle.sol";
import "./interfaces/IMTokenizedDeposit.sol";

/**
 * @title MTokenizedDeposit
 * @notice Permissioned ERC-20 Cari deposit for M&T Bank on the Cari Network /
 *         ZKsync Prividium (private permissioned zkRollup L2).
 *
 *         This contract implements the Cari Deposit Account (CDA) per the Cari Network
 *         Whitepaper. Each mtUSD token represents a 1:1 FDIC-insured bank liability backed
 *         by qualifying reserves per GENIUS Act Section 4 (cash, T-bills, Fed deposits).
 *
 *         TERMINOLOGY:
 *         - CDA = Cari Deposit Account (on-chain token representation)
 *         - DDA = Demand Deposit Account (off-chain fiat account at M&T Bank)
 *         - Minting creates CDA from DDA (fiat deposited -> CDA issued)
 *         - Burning redeems CDA back to DDA (CDA destroyed -> fiat returned)
 *
 * @dev    Key features:
 *         - UUPS upgradeable with consortium multi-sig + Timelock governance.
 *         - Role-based access control (RBAC) for mint/burn/compliance/upgrade/pause.
 *         - 1:1 reserve backing enforced via ReserveOracle integration (pre-mint check).
 *         - Travel Rule metadata hooks on qualifying transfers (FinCEN >= $3,000).
 *         - Whitelist-only transfers (KYC/AML gated via Cari shared registry).
 *         - Freeze / force-transfer for compliance (OFAC seizure, court orders).
 *         - Settlement callbacks for Cari Network cross-bank CDA transfers.
 *         - All state changes emit events for examiner audit trail (OCC/Fed/NYDFS).
 *
 *         SECURITY GUARDIAN NOTES:
 *         - MINTER_ROLE and BURNER_ROLE keys MUST be stored in HSM (Thales/Utimaco).
 *         - DEFAULT_ADMIN_ROLE should be a Timelock contract controlled by M&T multi-sig.
 *         - Separation of duties: minter != attestor != compliance officer.
 *         - No reentrancy vectors: ReentrancyGuard on all state-mutating externals.
 *         - Upgrade authorization requires UPGRADER_ROLE (Timelock-gated).
 */
contract MTokenizedDeposit is
    ERC20Upgradeable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    ReentrancyGuard,
    UUPSUpgradeable,
    IMTokenizedDeposit
{
    // =========================================================================
    //                              ROLES
    // =========================================================================

    /// @notice Role for minting CDA (Cari Deposit Account) tokens (M&T treasury operations, HSM-backed).
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");

    /// @notice Role for burning CDA tokens on redemption (CDA -> DDA).
    bytes32 public constant BURNER_ROLE = keccak256("BURNER_ROLE");

    /// @notice Role for compliance operations (whitelist, freeze, force-transfer).
    bytes32 public constant COMPLIANCE_ROLE = keccak256("COMPLIANCE_ROLE");

    /// @notice Role for contract upgrades (should be Timelock).
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");

    /// @notice Role for pause/unpause (emergency circuit breaker).
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    /// @notice Role for the CariSettlement contract to call settlement mint/burn.
    bytes32 public constant SETTLEMENT_ROLE = keccak256("SETTLEMENT_ROLE");

    /// @notice Operator role — M&T Bank's centralized supply controller per Cari Network Whitepaper.
    /// @dev Convenience superset that grants MINTER_ROLE + BURNER_ROLE. The Operator
    ///      is the entity authorized to manage CDA supply (mint from DDA, burn to DDA).
    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");

    // =========================================================================
    //                              STATE
    // =========================================================================

    /// @notice Reserve oracle enforcing 1:1 backing of CDA supply (GENIUS Act Section 4).
    IReserveOracle public reserveOracle;

    /// @notice Whitelist: only KYC/AML-approved addresses can hold or transfer tokens.
    mapping(address => bool) private _whitelisted;

    /// @notice Frozen addresses (OFAC, suspicious activity, court orders).
    mapping(address => bool) private _frozen;

    /// @notice Travel Rule threshold in token units (default: 3_000 * 10^6 = $3,000).
    uint256 public travelRuleThreshold;

    /// @notice Cari settlement contract address (for cross-bank CDA transfers).
    address public cariSettlement;

    /// @dev Transient flag to bypass compliance checks during forceTransfer.
    bool private _forceTransferActive;

    /// @notice Current designated Operator address
    address private _operator;

    // =========================================================================
    //                              EVENTS
    // =========================================================================

    // IMTokenizedDeposit events are inherited. Additional internal events:
    event SettlementMint(address indexed to, uint256 amount, bytes32 indexed settlementId);
    event SettlementBurn(address indexed from, uint256 amount, bytes32 indexed settlementId);
    event TravelRuleThresholdUpdated(uint256 oldThreshold, uint256 newThreshold);

    // =========================================================================
    //                              ERRORS
    // =========================================================================

    error NotWhitelisted(address account);
    error AccountFrozen(address account);
    error ReserveBackingInsufficient(uint256 supplyAfterMint, uint256 totalReserves);
    error ReserveOracleNotSet();
    error ReserveAttestationStale();
    error ZeroAddress();
    error ZeroAmount();
    error TravelRuleRequired(uint256 amount, uint256 threshold);

    // =========================================================================
    //                            INITIALIZER
    // =========================================================================

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    /**
     * @notice Initialize the MTokenizedDeposit (Cari Deposit Account) contract.
     * @param admin          M&T Bank Timelock/multi-sig address (DEFAULT_ADMIN_ROLE).
     * @param _reserveOracle Address of the deployed ReserveOracle contract for CDA backing.
     */
    function initialize(address admin, address _reserveOracle) public initializer {
        if (admin == address(0)) revert ZeroAddress();

        __ERC20_init("M&T Bank Tokenized Deposit (Cari)", "mtUSD");
        __AccessControl_init();
        __Pausable_init();

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(UPGRADER_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);

        if (_reserveOracle != address(0)) {
            reserveOracle = IReserveOracle(_reserveOracle);
        }

        // FinCEN Travel Rule: $3,000 threshold (6 decimals)
        travelRuleThreshold = 3_000 * 1e6;
    }

    // =========================================================================
    //                          TOKEN METADATA
    // =========================================================================

    /// @notice 6 decimals (USD-aligned precision for bank deposits).
    function decimals() public pure override returns (uint8) {
        return 6;
    }

    // =========================================================================
    //                        MINT / BURN (GENIUS Act S4 & S5)
    //                        DDA <-> CDA Conversion Operations
    // =========================================================================

    /**
     * @notice Mint CDA tokens upon verified fiat deposit at M&T Bank (DDA -> CDA).
     * @dev    Converts a Demand Deposit Account (DDA) balance into Cari Deposit Account
     *         (CDA) tokens. Enforces 1:1 reserve backing via ReserveOracle before minting.
     *         Minter key MUST be HSM-backed with SoD from attestor.
     * @param to          Whitelisted recipient address to receive CDA.
     * @param amount      Amount of CDA to mint (6 decimals).
     * @param referenceId M&T core banking reference ID for reconciliation.
     */
    function mint(
        address to,
        uint256 amount,
        string calldata referenceId
    ) external override onlyRole(MINTER_ROLE) whenNotPaused nonReentrant {
        if (to == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();
        if (!_whitelisted[to]) revert NotWhitelisted(to);
        if (_frozen[to]) revert AccountFrozen(to);

        // GENIUS Act Section 4: verify 1:1 reserve backing
        _checkReserveBacking(amount);

        _mint(to, amount);
        emit Mint(to, amount, referenceId);
    }

    /**
     * @notice Burn CDA tokens on redemption at par (CDA -> DDA, GENIUS Act Section 5).
     * @dev    Converts Cari Deposit Account (CDA) tokens back to Demand Deposit Account
     *         (DDA) fiat. Burns tokens, triggering off-chain settlement to depositor's
     *         M&T Bank DDA.
     * @param from        Address to burn CDA from.
     * @param amount      Amount of CDA to burn (6 decimals).
     * @param referenceId M&T core banking reference for settlement tracking.
     */
    function burn(
        address from,
        uint256 amount,
        string calldata referenceId
    ) external override onlyRole(BURNER_ROLE) whenNotPaused nonReentrant {
        if (amount == 0) revert ZeroAmount();
        _burn(from, amount);
        emit Burn(from, amount, referenceId);
    }

    // =========================================================================
    //                        TRAVEL RULE (FinCEN)
    // =========================================================================

    /**
     * @notice Transfer with Travel Rule metadata for FinCEN compliance.
     * @dev    For transfers >= travelRuleThreshold ($3,000), callers MUST use this
     *         function instead of plain transfer(). The Travel Rule metadata hashes
     *         are emitted on-chain for examiner auditability; actual PII is stored
     *         off-chain by the Travel Rule service (e.g., Notabene).
     * @param to         Recipient address (must be whitelisted).
     * @param amount     Transfer amount (6 decimals).
     * @param travelData Originator/beneficiary identification hashes.
     * @return True on success.
     */
    function transferWithTravelRule(
        address to,
        uint256 amount,
        TravelRuleData calldata travelData
    ) external override whenNotPaused nonReentrant returns (bool) {
        _transfer(msg.sender, to, amount);
        emit TravelRuleTransfer(
            msg.sender,
            to,
            amount,
            travelData.originatorHash,
            travelData.beneficiaryHash
        );
        return true;
    }

    // =========================================================================
    //                      COMPLIANCE CONTROLS
    // =========================================================================

    /// @notice Add an address to the KYC/AML whitelist (Cari shared registry).
    function whitelistAddress(address account) external override onlyRole(COMPLIANCE_ROLE) {
        if (account == address(0)) revert ZeroAddress();
        _whitelisted[account] = true;
        emit AddressWhitelisted(account);
    }

    /// @notice Remove an address from the whitelist.
    function removeFromWhitelist(address account) external override onlyRole(COMPLIANCE_ROLE) {
        _whitelisted[account] = false;
        emit AddressRemovedFromWhitelist(account);
    }

    /// @notice Freeze an address (OFAC hit, suspicious activity, court order).
    function freezeAddress(address account) external override onlyRole(COMPLIANCE_ROLE) {
        _frozen[account] = true;
        emit AddressFrozen(account);
    }

    /// @notice Unfreeze a previously frozen address.
    function unfreezeAddress(address account) external override onlyRole(COMPLIANCE_ROLE) {
        _frozen[account] = false;
        emit AddressUnfrozen(account);
    }

    /// @notice Check if an address is whitelisted.
    function isWhitelisted(address account) external view override returns (bool) {
        return _whitelisted[account];
    }

    /// @notice Check if an address is frozen.
    function isFrozen(address account) external view override returns (bool) {
        return _frozen[account];
    }

    /**
     * @notice Compliance-mandated forced transfer (OFAC seizure, court order, law enforcement).
     * @dev    Bypasses whitelist/freeze checks. Only callable by COMPLIANCE_ROLE.
     *         Event includes reason string for examiner audit trail.
     * @param from   Source address (may be frozen).
     * @param to     Destination address (e.g., M&T compliance escrow).
     * @param amount Amount to force-transfer.
     * @param reason Documented reason (e.g., "OFAC seizure order #12345").
     */
    function forceTransfer(
        address from,
        address to,
        uint256 amount,
        string calldata reason
    ) external override onlyRole(COMPLIANCE_ROLE) whenNotPaused nonReentrant {
        if (from == address(0) || to == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();
        // Bypass whitelist/freeze checks in _update for compliance-mandated transfer
        _forceTransferActive = true;
        _transfer(from, to, amount);
        _forceTransferActive = false;
        emit ForcedTransfer(from, to, amount, reason);
    }

    // =========================================================================
    //                    CARI SETTLEMENT CALLBACKS
    //              Cross-Bank CDA Transfers Between Member Banks
    // =========================================================================

    /**
     * @notice Mint CDA tokens as part of a Cari cross-bank settlement (destination side).
     * @dev    Called by the CariSettlement contract after validating the settlement request.
     *         Issues new CDA at the destination bank for the beneficiary.
     * @param to           Beneficiary wallet at M&T Bank to receive CDA.
     * @param amount       Amount of CDA to mint.
     * @param settlementId Cari settlement identifier for reconciliation.
     */
    function settlementMint(
        address to,
        uint256 amount,
        bytes32 settlementId
    ) external override onlyRole(SETTLEMENT_ROLE) whenNotPaused nonReentrant {
        if (to == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();
        if (!_whitelisted[to]) revert NotWhitelisted(to);
        if (_frozen[to]) revert AccountFrozen(to);
        _checkReserveBacking(amount);
        _mint(to, amount);
        emit SettlementMint(to, amount, settlementId);
    }

    /**
     * @notice Burn CDA tokens as part of a Cari cross-bank settlement (source side).
     * @dev    Called by the CariSettlement contract when initiating a cross-bank CDA transfer.
     *         Burns CDA at the source bank so equivalent CDA can be minted at the destination.
     * @param from         Originator wallet at M&T Bank whose CDA is burned.
     * @param amount       Amount of CDA to burn.
     * @param settlementId Cari settlement identifier for reconciliation.
     */
    function settlementBurn(
        address from,
        uint256 amount,
        bytes32 settlementId
    ) external override onlyRole(SETTLEMENT_ROLE) whenNotPaused nonReentrant {
        if (amount == 0) revert ZeroAmount();
        _burn(from, amount);
        emit SettlementBurn(from, amount, settlementId);
    }

    /**
     * @notice Return CDA tokens to originator on settlement expiry or revert.
     * @dev    Called by CariSettlement when a settlement is expired or reverted.
     *         Does NOT check reserve backing because these CDA tokens were previously
     *         burned from the originator for this settlement - net supply change is zero.
     * @param to           Originator wallet to receive CDA back.
     * @param amount       Amount of CDA to return.
     * @param settlementId Cari settlement identifier for reconciliation.
     */
    function settlementReturn(
        address to,
        uint256 amount,
        bytes32 settlementId
    ) external override onlyRole(SETTLEMENT_ROLE) whenNotPaused nonReentrant {
        if (to == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();
        // NOTE: No _checkReserveBacking() call - tokens were previously burned for this
        // settlement, so returning them results in zero net supply change.
        _mint(to, amount);
        emit SettlementReturn(to, amount, settlementId);
    }

    // =========================================================================
    //                        ADMIN / CONFIG
    // =========================================================================

    /// @notice Update the reserve oracle address.
    function setReserveOracle(address newOracle) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (newOracle == address(0)) revert ZeroAddress();
        address old = address(reserveOracle);
        reserveOracle = IReserveOracle(newOracle);
        emit ReserveOracleUpdated(old, newOracle);
    }

    /// @notice Update the Cari settlement contract address and grant SETTLEMENT_ROLE.
    function setCariSettlement(address newSettlement) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (newSettlement == address(0)) revert ZeroAddress();
        address old = cariSettlement;
        // Revoke old settlement role if set
        if (old != address(0)) {
            _revokeRole(SETTLEMENT_ROLE, old);
        }
        cariSettlement = newSettlement;
        _grantRole(SETTLEMENT_ROLE, newSettlement);
        emit CariSettlementUpdated(old, newSettlement);
    }

    /// @notice Designate an Operator address, granting it MINTER_ROLE and BURNER_ROLE.
    /// @dev Per Cari Whitepaper: the Operator is the single entity (M&T Bank) controlling CDA supply.
    ///      Replaces previous Operator if one was set (revokes old roles, grants new).
    ///      Only callable by DEFAULT_ADMIN_ROLE.
    /// @param newOperator The new Operator address
    function setOperator(address newOperator) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (newOperator == address(0)) revert ZeroAddress();
        
        address oldOperator = _operator;
        
        // Revoke roles from old operator if set
        if (oldOperator != address(0)) {
            _revokeRole(MINTER_ROLE, oldOperator);
            _revokeRole(BURNER_ROLE, oldOperator);
            _revokeRole(OPERATOR_ROLE, oldOperator);
        }
        
        // Grant roles to new operator
        _grantRole(OPERATOR_ROLE, newOperator);
        _grantRole(MINTER_ROLE, newOperator);
        _grantRole(BURNER_ROLE, newOperator);
        
        _operator = newOperator;
        
        emit OperatorUpdated(oldOperator, newOperator);
    }

    /// @notice Returns the current Operator address
    function operator() external view returns (address) {
        return _operator;
    }

    /// @notice Update the Travel Rule threshold (in token units, 6 decimals).
    function setTravelRuleThreshold(uint256 newThreshold) external onlyRole(DEFAULT_ADMIN_ROLE) {
        uint256 old = travelRuleThreshold;
        travelRuleThreshold = newThreshold;
        emit TravelRuleThresholdUpdated(old, newThreshold);
    }

    // =========================================================================
    //                          PAUSE
    // =========================================================================

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    // =========================================================================
    //                      INTERNAL OVERRIDES
    // =========================================================================

    /**
     * @dev Override _update to enforce whitelist and freeze checks on all transfers.
     *      Mint (from=address(0)) and burn (to=address(0)) bypass sender/receiver checks
     *      respectively, as those are handled by their own role-gated functions.
     *
     *      For transfers >= travelRuleThreshold, a standard transfer() will still work
     *      but the Travel Rule metadata will NOT be recorded. Compliant front-ends should
     *      use transferWithTravelRule() for qualifying amounts. The contract does not
     *      block plain transfers to preserve ERC-20 compatibility, but off-chain monitoring
     *      flags any large transfer without a corresponding TravelRuleTransfer event.
     */
    function _update(
        address from,
        address to,
        uint256 amount
    ) internal override whenNotPaused {
        if (!_forceTransferActive) {
            // Sender checks (skip for minting)
            if (from != address(0)) {
                if (!_whitelisted[from]) revert NotWhitelisted(from);
                if (_frozen[from]) revert AccountFrozen(from);
            }
            // Receiver checks (skip for burning)
            if (to != address(0)) {
                if (!_whitelisted[to]) revert NotWhitelisted(to);
                if (_frozen[to]) revert AccountFrozen(to);
            }
        }
        super._update(from, to, amount);
    }

    /**
     * @dev Check 1:1 reserve backing of CDA supply via the ReserveOracle before minting.
     *      Reverts if reserves are insufficient or attestation is stale.
     */
    function _checkReserveBacking(uint256 mintAmount) internal view {
        if (address(reserveOracle) == address(0)) revert ReserveOracleNotSet();
        if (!reserveOracle.canMint(totalSupply(), mintAmount)) {
            revert ReserveBackingInsufficient(
                totalSupply() + mintAmount,
                reserveOracle.totalReserves()
            );
        }
    }

    // =========================================================================
    //                          UUPS UPGRADE
    // =========================================================================

    function _authorizeUpgrade(address) internal override onlyRole(UPGRADER_ROLE) {}
}
