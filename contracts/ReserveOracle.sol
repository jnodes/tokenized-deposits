// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "./interfaces/IReserveOracle.sol";

/**
 * @title ReserveOracle
 * @notice 1:1 reserve backing attestation oracle for Cari deposits (CDA)
 *         on the Cari Network / ZKsync Prividium.
 *
 *         This oracle ensures every Cari Deposit Account (CDA) token is backed 1:1
 *         by qualifying reserves per GENIUS Act Section 4 (cash, T-bills, Fed deposits).
 *
 * @dev    This oracle receives off-chain reserve attestations from the Issuing Bank's treasury
 *         operations team and makes them available on-chain for the TokenizedDeposit
 *         (CDA) contract to query before every mint.
 *
 *         Attestation sources (pluggable):
 *         - Chainlink Proof of Reserve adapter
 *         - Prividium-native zk-proof attestation circuit
 *         - Off-chain signed attestation from a registered public accounting firm
 *           (GENIUS Act Section 6: monthly attestation requirement)
 *
 *         SECURITY GUARDIAN NOTE:
 *         - ATTESTOR_ROLE key MUST reside in an HSM (Thales Luna / Utimaco).
 *         - Separation of duties: the attestor MUST NOT also hold MINTER_ROLE on the
 *           CDA contract. Treasury operations signs attestations; a separate
 *           minting service executes mints.
 *         - Staleness threshold enforces that attestations cannot be older than
 *           `maxStaleness` seconds (default 24 hours; configurable by admin).
 *         - All state changes emit events for examiner audit trail (OCC/Fed/NYDFS).
 */
contract ReserveOracle is
    IReserveOracle,
    AccessControlUpgradeable,
    PausableUpgradeable,
    UUPSUpgradeable
{
    // --- Roles ---
    bytes32 public constant ATTESTOR_ROLE = keccak256("ATTESTOR_ROLE");
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    // --- Constants ---
    /// @notice Warning threshold percentage (75% of maxStaleness)
    uint256 public constant STALENESS_WARNING_PCT = 75;

    // --- State ---
    uint256 private _totalReserves;       // 6-decimal USD value backing CDA supply
    uint256 private _lastAttestedAt;      // block.timestamp of last attestation
    bytes32 private _attestationHash;     // hash of signed report (IPFS/Arweave CID)
    uint256 public maxStaleness;          // seconds before attestation is considered stale

    // --- Events ---
    event MaxStalenessUpdated(uint256 oldValue, uint256 newValue);

    // --- Errors ---
    error AttestationStaleError(uint256 attestedAt, uint256 threshold);
    error ZeroReserves();
    error InvalidStaleness();

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    /**
     * @notice Initialize the ReserveOracle for CDA reserve backing.
     * @param admin         Consortium multi-sig address.
     * @param attestor      Address authorized to submit reserve attestations (HSM-backed).
     * @param _maxStaleness Maximum age (seconds) of a valid attestation. Default: 86400 (24h).
     */
    function initialize(
        address admin,
        address attestor,
        uint256 _maxStaleness
    ) public initializer {
        if (_maxStaleness == 0) revert InvalidStaleness();

        __AccessControl_init();
        __Pausable_init();

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ATTESTOR_ROLE, attestor);
        _grantRole(UPGRADER_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);

        maxStaleness = _maxStaleness;
    }

    // --- IReserveOracle Implementation ---

    /// @inheritdoc IReserveOracle
    function totalReserves() external view override returns (uint256) {
        return _totalReserves;
    }

    /// @inheritdoc IReserveOracle
    function lastAttestedAt() external view override returns (uint256) {
        return _lastAttestedAt;
    }

    /// @inheritdoc IReserveOracle
    function attestationHash() external view override returns (bytes32) {
        return _attestationHash;
    }

    /// @inheritdoc IReserveOracle
    function canMint(
        uint256 currentSupply,
        uint256 mintAmount
    ) external view override returns (bool) {
        // Stale attestation -> no minting allowed
        if (block.timestamp > _lastAttestedAt + maxStaleness) return false;
        // 1:1 invariant: supply + mint <= reserves
        return (currentSupply + mintAmount) <= _totalReserves;
    }

    /// @inheritdoc IReserveOracle
    function updateAttestation(
        uint256 newTotalReserves,
        bytes32 newAttestationHash
    ) external override onlyRole(ATTESTOR_ROLE) whenNotPaused {
        if (newTotalReserves == 0) revert ZeroReserves();

        _totalReserves = newTotalReserves;
        _lastAttestedAt = block.timestamp;
        _attestationHash = newAttestationHash;

        emit ReserveAttestationUpdated(newTotalReserves, block.timestamp, newAttestationHash);
    }

    // --- Admin ---

    /**
     * @notice Update the maximum staleness threshold.
     * @param newMaxStaleness New threshold in seconds.
     */
    function setMaxStaleness(uint256 newMaxStaleness) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (newMaxStaleness == 0) revert InvalidStaleness();
        uint256 old = maxStaleness;
        maxStaleness = newMaxStaleness;
        emit MaxStalenessUpdated(old, newMaxStaleness);
    }

    /**
     * @notice Check if the current attestation is fresh (not stale).
     * @return True if lastAttestedAt + maxStaleness >= block.timestamp.
     */
    function isAttestationFresh() external view returns (bool) {
        if (_lastAttestedAt == 0) return false;
        return block.timestamp <= _lastAttestedAt + maxStaleness;
    }

    /**
     * @notice Check attestation freshness and emit warning events if approaching staleness.
     * @dev    Callable by anyone (no role restriction) so monitoring systems can call it.
     *         Emits AttestationStale event if attestation is stale.
     *         Emits AttestationStalenessWarning event if attestation is approaching staleness.
     * @return isFresh          True if attestation is not stale.
     * @return secondsUntilStale Seconds remaining until attestation becomes stale (0 if already stale).
     */
    function checkStaleness() external override returns (bool isFresh, uint256 secondsUntilStale) {
        if (_lastAttestedAt == 0) {
            emit AttestationStale(0, maxStaleness, block.timestamp);
            return (false, 0);
        }

        uint256 elapsed = block.timestamp - _lastAttestedAt;
        uint256 warningThreshold = (maxStaleness * STALENESS_WARNING_PCT) / 100;

        // Check if attestation is stale
        if (elapsed > maxStaleness) {
            emit AttestationStale(_lastAttestedAt, maxStaleness, block.timestamp);
            return (false, 0);
        }

        // Check if attestation is approaching staleness (past warning threshold)
        if (elapsed > warningThreshold) {
            emit AttestationStalenessWarning(_lastAttestedAt, maxStaleness, block.timestamp);
            return (true, maxStaleness - elapsed);
        }

        // Attestation is fresh and not approaching staleness
        return (true, maxStaleness - elapsed);
    }

    /**
     * @notice Returns the staleness warning threshold in seconds.
     * @dev    Useful for off-chain monitoring systems to know when to expect warnings.
     * @return The warning threshold in seconds (75% of maxStaleness).
     */
    function stalenessWarningThresholdSeconds() external view returns (uint256) {
        return (maxStaleness * STALENESS_WARNING_PCT) / 100;
    }

    // --- Pause ---

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    // --- UUPS ---

    function _authorizeUpgrade(address) internal override onlyRole(UPGRADER_ROLE) {}
}
