// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/token/ERC20/ERC20Upgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";

/**
 * @title MTBankTokenizedDeposit
 * @notice Legacy simplified ERC-20 Cari deposit for M&T Bank on the Cari Network / ZKsync Prividium.
 *         Each token represents a 1:1 bank liability (Cari Deposit Account - CDA) backed
 *         by qualifying reserves (GENIUS Act Section 4 compliant).
 *
 *         NOTE: This is the legacy simplified version. For the full-featured CDA
 *         implementation with reserve oracle integration and cross-bank settlement,
 *         see MTokenizedDeposit.sol.
 *
 *         TERMINOLOGY:
 *         - CDA = Cari Deposit Account (on-chain token representation)
 *         - DDA = Demand Deposit Account (off-chain fiat account at M&T Bank)
 *
 * @dev    Deployed on ZKsync Prividium (private permissioned zkRollup L2).
 *         Upgradeable via UUPS pattern with consortium multi-sig governance.
 */
contract MTBankTokenizedDeposit is
    ERC20Upgradeable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    UUPSUpgradeable
{
    // --- Roles ---
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");
    bytes32 public constant BURNER_ROLE = keccak256("BURNER_ROLE");
    bytes32 public constant COMPLIANCE_ROLE = keccak256("COMPLIANCE_ROLE");
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    // --- Compliance ---
    /// @notice Whitelist of addresses approved by KYC/AML (Cari Network shared registry).
    mapping(address => bool) private _whitelisted;

    /// @notice Addresses frozen by compliance (OFAC, suspicious activity).
    mapping(address => bool) private _frozen;

    // --- Events ---
    event Mint(address indexed to, uint256 amount, string referenceId);
    event Burn(address indexed from, uint256 amount, string referenceId);
    event AddressWhitelisted(address indexed account);
    event AddressRemovedFromWhitelist(address indexed account);
    event AddressFrozen(address indexed account);
    event AddressUnfrozen(address indexed account);

    // --- Errors ---
    error NotWhitelisted(address account);
    error AccountFrozen(address account);

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    /**
     * @notice Initialize the Cari deposit (CDA) contract.
     * @param admin Address of the initial admin (M&T Bank consortium multi-sig).
     */
    function initialize(address admin) public initializer {
        __ERC20_init("M&T Bank Tokenized Deposit (Cari)", "mtUSD");
        __AccessControl_init();
        __Pausable_init();

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(MINTER_ROLE, admin);
        _grantRole(BURNER_ROLE, admin);
        _grantRole(COMPLIANCE_ROLE, admin);
        _grantRole(UPGRADER_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);
    }

    /**
     * @notice Returns 6 decimals (USD-aligned precision).
     */
    function decimals() public pure override returns (uint8) {
        return 6;
    }

    // --- Mint / Burn (GENIUS Act Section 4 & 5) ---
    // DDA <-> CDA Conversion Operations

    /**
     * @notice Mint CDA tokens upon verified fiat deposit (DDA -> CDA).
     * @param to         Whitelisted recipient address to receive CDA.
     * @param amount     Amount of CDA to mint (6 decimals).
     * @param referenceId Core banking reference for reconciliation.
     */
    function mint(
        address to,
        uint256 amount,
        string calldata referenceId
    ) external onlyRole(MINTER_ROLE) whenNotPaused {
        if (!_whitelisted[to]) revert NotWhitelisted(to);
        if (_frozen[to]) revert AccountFrozen(to);
        _mint(to, amount);
        emit Mint(to, amount, referenceId);
    }

    /**
     * @notice Burn CDA tokens on redemption at par (CDA -> DDA, GENIUS Act Section 5).
     * @param from        Address to burn CDA from.
     * @param amount      Amount of CDA to burn.
     * @param referenceId Core banking reference for settlement.
     */
    function burn(
        address from,
        uint256 amount,
        string calldata referenceId
    ) external onlyRole(BURNER_ROLE) whenNotPaused {
        _burn(from, amount);
        emit Burn(from, amount, referenceId);
    }

    // --- Compliance Controls ---

    function whitelistAddress(address account) external onlyRole(COMPLIANCE_ROLE) {
        _whitelisted[account] = true;
        emit AddressWhitelisted(account);
    }

    function removeFromWhitelist(address account) external onlyRole(COMPLIANCE_ROLE) {
        _whitelisted[account] = false;
        emit AddressRemovedFromWhitelist(account);
    }

    function freezeAddress(address account) external onlyRole(COMPLIANCE_ROLE) {
        _frozen[account] = true;
        emit AddressFrozen(account);
    }

    function unfreezeAddress(address account) external onlyRole(COMPLIANCE_ROLE) {
        _frozen[account] = false;
        emit AddressUnfrozen(account);
    }

    function isWhitelisted(address account) external view returns (bool) {
        return _whitelisted[account];
    }

    function isFrozen(address account) external view returns (bool) {
        return _frozen[account];
    }

    // --- Transfer Restrictions ---

    /**
     * @dev Override _update to enforce whitelist and freeze checks on all transfers.
     *      Mint (from=0) and burn (to=0) bypass sender/receiver checks respectively.
     */
    function _update(
        address from,
        address to,
        uint256 amount
    ) internal override whenNotPaused {
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
        super._update(from, to, amount);
    }

    // --- Pause ---

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    // --- UUPS Upgrade ---

    function _authorizeUpgrade(
        address newImplementation
    ) internal override onlyRole(UPGRADER_ROLE) {}
}
