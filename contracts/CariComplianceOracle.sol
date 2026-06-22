// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";

/**
 * @title CariComplianceOracle
 * @notice On-chain compliance oracle for the Cari Network on ZKsync Prividium.
 *         Stores KYC/AML status, OFAC screening results, and Travel Rule data
 *         for the Cari deposit (CDA) platform.
 *
 *         This oracle gates which addresses may hold or transfer Cari Deposit
 *         Account (CDA) tokens, ensuring regulatory compliance.
 *
 * @dev    Designed for integration with off-chain compliance vendors
 *         (Chainalysis, TRM Labs, Notabene).
 */
contract CariComplianceOracle is AccessControlUpgradeable, UUPSUpgradeable {
    bytes32 public constant ORACLE_UPDATER_ROLE = keccak256("ORACLE_UPDATER_ROLE");
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");

    enum KYCStatus {
        NOT_VERIFIED,
        VERIFIED,
        EXPIRED,
        REJECTED
    }

    enum RiskLevel {
        LOW,
        MEDIUM,
        HIGH,
        BLOCKED
    }

    struct ComplianceRecord {
        KYCStatus kycStatus;
        RiskLevel riskLevel;
        uint256 lastScreenedAt;      // Timestamp of last OFAC/sanctions screening
        uint256 kycExpiresAt;        // KYC expiration timestamp
        bool travelRuleEligible;     // Whether address has Travel Rule info on file
        string jurisdictionCode;     // ISO country code for regulatory mapping
    }

    /// @notice Compliance records keyed by wallet address.
    mapping(address => ComplianceRecord) private _records;

    // --- Events ---
    event ComplianceUpdated(
        address indexed account,
        KYCStatus kycStatus,
        RiskLevel riskLevel,
        uint256 lastScreenedAt
    );
    event TravelRuleStatusUpdated(address indexed account, bool eligible);

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    function initialize(address admin) public initializer {
        __AccessControl_init();
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ORACLE_UPDATER_ROLE, admin);
        _grantRole(UPGRADER_ROLE, admin);
    }

    /**
     * @notice Update compliance record for an address.
     * @dev    Called by off-chain compliance service after KYC/AML/OFAC checks.
     */
    function updateCompliance(
        address account,
        KYCStatus kycStatus,
        RiskLevel riskLevel,
        uint256 kycExpiresAt,
        string calldata jurisdictionCode
    ) external onlyRole(ORACLE_UPDATER_ROLE) {
        _records[account] = ComplianceRecord({
            kycStatus: kycStatus,
            riskLevel: riskLevel,
            lastScreenedAt: block.timestamp,
            kycExpiresAt: kycExpiresAt,
            travelRuleEligible: _records[account].travelRuleEligible,
            jurisdictionCode: jurisdictionCode
        });
        emit ComplianceUpdated(account, kycStatus, riskLevel, block.timestamp);
    }

    /**
     * @notice Update Travel Rule eligibility for an address.
     */
    function updateTravelRuleStatus(
        address account,
        bool eligible
    ) external onlyRole(ORACLE_UPDATER_ROLE) {
        _records[account].travelRuleEligible = eligible;
        emit TravelRuleStatusUpdated(account, eligible);
    }

    /**
     * @notice Check if an address is compliant for CDA token operations.
     * @return True if KYC verified, not expired, risk not BLOCKED, and recently screened.
     */
    function isCompliant(address account) external view returns (bool) {
        ComplianceRecord memory r = _records[account];
        return (
            r.kycStatus == KYCStatus.VERIFIED &&
            r.kycExpiresAt > block.timestamp &&
            r.riskLevel != RiskLevel.BLOCKED &&
            r.lastScreenedAt > 0
        );
    }

    function getComplianceRecord(
        address account
    ) external view returns (ComplianceRecord memory) {
        return _records[account];
    }

    function _authorizeUpgrade(
        address newImplementation
    ) internal override onlyRole(UPGRADER_ROLE) {}
}
